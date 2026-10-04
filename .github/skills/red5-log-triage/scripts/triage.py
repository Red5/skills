#!/usr/bin/env python3
"""Summarize a red5.log into a short triage report.

Parses entries, folds stack traces into the entry above them, collapses repeats of the same
message into one signature, tags each signature with a category and (when recognized) a known
issue from ../references/knowledge.json, and prints the highest-priority findings first.

Standard library only. Reads plain, .gz and .zip logs.
"""
import argparse
import collections
import gzip
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KNOWLEDGE = os.path.join(HERE, "..", "references", "knowledge.json")

# 2026-09-28 18:54:21,159 [main] INFO  org.red5.server.Launcher - message
LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),?(\d{3})? \[([^\]]*)\] (\w+)\s+(\S+) - (.*)$")
STACK_HINT = re.compile(r"^(\s+at |\s*Caused by:|\s*\.\.\. \d+ (more|common))")
PRIORITY = {"investigate": 0, "watch": 1, "unrecognized": 2, "noise": 3}
LEVEL_RANK = {"ERROR": 0, "FATAL": 0, "WARN": 1}


def open_log(path):
    """Return a text stream for a plain, gzip or zip log."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    if path.endswith(".zip"):
        zf = zipfile.ZipFile(path)
        names = [n for n in zf.namelist() if not n.endswith("/")]
        pick = next((n for n in names if "red5" in os.path.basename(n).lower()), names[0])
        return io.TextIOWrapper(zf.open(pick), encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def resolve_path(target):
    if os.path.isfile(target):
        return target
    if os.path.isdir(target):
        cands = sorted(
            (f for f in os.listdir(target) if "red5" in f.lower() and ".log" in f.lower()),
            key=lambda f: (f != "red5.log", f),
        )
        if cands:
            return os.path.join(target, cands[0])
    sys.exit(f"no red5 log found at: {target}")


def normalize(msg):
    msg = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", msg, flags=re.I)
    msg = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b", "<ip>", msg)
    msg = re.sub(r"0x[0-9a-f]+", "<hex>", msg, flags=re.I)
    msg = re.sub(r"\b[0-9a-f]{16,}\b", "<hex>", msg, flags=re.I)
    msg = re.sub(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{8,}\b", "<id>", msg)
    return re.sub(r"\d+", "<n>", msg)


class Knowledge:
    def __init__(self, path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.logger_rules = data.get("logger_rules", [])
        self.events = []
        for ev in data.get("events", []):
            ev = dict(ev)
            ev["_re"] = re.compile(ev["pattern"], re.I | re.S)
            self.events.append(ev)
        self.issues = []
        for issue in data.get("known_issues", []):
            issue = dict(issue)
            issue["_re"] = re.compile(issue["pattern"], re.I | re.S)
            self.issues.append(issue)

    def category(self, logger):
        for prefix, cat in self.logger_rules:
            if logger.startswith(prefix):
                return cat
        return "other"

    def match(self, logger, message):
        text = f"{logger} {message}"
        for issue in self.issues:
            if issue["_re"].search(text):
                return issue
        return None


def parse(stream, levels):
    """Yield one dict per log entry; keep stack text only for the levels we report on."""
    cur = None
    for raw in stream:
        line = raw.rstrip("\n")
        m = LINE.match(line)
        if m:
            if cur:
                yield cur
            ts, _ms, thread, level, logger, msg = m.groups()
            cur = {"ts": ts, "thread": thread, "level": level, "logger": logger, "msg": msg, "extra": []}
        elif cur and line.strip() and cur["level"] in levels and len(cur["extra"]) < 60:
            cur["extra"].append(line)
    if cur:
        yield cur


def exception_summary(entry):
    """Best one-line cause: the last 'Caused by' (or the first exception-looking line)."""
    extra = entry["extra"]
    caused = [l.strip() for l in extra if l.strip().startswith("Caused by:")]
    if caused:
        return caused[-1][:300]
    for l in extra:
        if not STACK_HINT.match(l) and re.search(r"(Exception|Error)\b", l):
            return l.strip()[:300]
    m = re.search(r"([\w.]+(?:Exception|Error))(: .*)?", entry["msg"])
    return m.group(0)[:300] if m else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", nargs="?", default=".", help="log file, or a directory containing red5.log")
    ap.add_argument("--levels", default="WARN,ERROR", help="levels to report on (default WARN,ERROR)")
    ap.add_argument("--top", type=int, default=25, help="number of findings to print (default 25)")
    ap.add_argument("--category", help="only show findings in this category")
    ap.add_argument("--knowledge", default=DEFAULT_KNOWLEDGE, help="path to knowledge.json")
    ap.add_argument("--json", metavar="PATH", help="also write all findings as JSON")
    args = ap.parse_args()

    path = resolve_path(os.path.expanduser(args.path))
    knowledge = Knowledge(args.knowledge)
    levels = {l.strip().upper() for l in args.levels.split(",")}

    level_counts = collections.Counter()
    first_ts = last_ts = None
    launcher_starts = []  # "Red5 Server x.y.z" banner lines
    script_starts = []  # red5pro.sh "Start red5pro server" lines (Pro installs); one boot logs both
    stops = []
    versions = []
    pro_versions = []
    events = {}  # event id -> {title, note, count, first, last}
    os_line = None
    per_minute = collections.Counter()
    sigs = {}
    total = 0

    with open_log(path) as stream:
        for e in parse(stream, levels):
            total += 1
            level_counts[e["level"]] += 1
            first_ts = first_ts or e["ts"]
            last_ts = e["ts"]
            if e["logger"].endswith("Launcher") and "Red5 Server" in e["msg"]:
                launcher_starts.append(e["ts"])
                versions.append(e["msg"].split(" (")[0])
            msg = e["msg"]
            if e["logger"].endswith("red5pro.sh"):
                if "Start red5pro server" in msg:
                    script_starts.append(e["ts"])
                elif "Stop red5pro server" in msg:
                    stops.append(e["ts"])
            m_ver = re.search(r"Version - server: (\S+) pro: (\S+)", msg)
            if m_ver and not pro_versions:
                versions.append(f"server {m_ver.group(1)}")
                pro_versions.append(m_ver.group(2))
            text = f"{e['logger']} {msg}"
            for ev in knowledge.events:
                if ev["_re"].search(text):
                    rec = events.setdefault(ev["id"], {"title": ev["title"], "note": ev["note"], "count": 0, "first": e["ts"], "last": e["ts"]})
                    rec["count"] += 1
                    rec["last"] = e["ts"]
            if "Operating system:" in e["msg"] and os_line is None:
                os_line = e["msg"]
            if e["level"] not in levels:
                continue
            per_minute[e["ts"][:16]] += 1
            issue = knowledge.match(e["logger"], e["msg"])
            key = f"known:{issue['id']}" if issue else f"{e['level']}|{e['logger']}|{normalize(e['msg'])}"
            sig = sigs.get(key)
            if sig is None:
                has_exc = bool(exception_summary(e))
                sigs[key] = sig = {
                    "level": e["level"], "logger": e["logger"], "count": 0, "first": e["ts"], "last": e["ts"],
                    "message": e["msg"][:400], "cause": exception_summary(e), "has_exception": has_exc,
                    "category": issue["category"] if issue else knowledge.category(e["logger"]),
                    "known": issue["id"] if issue else None,
                    "severity": issue["severity"] if issue else "unrecognized",
                    "title": issue["title"] if issue else None,
                    "meaning": issue["meaning"] if issue else None,
                    "next_steps": issue["next_steps"] if issue else None,
                    "levels_seen": set(),
                }
            sig["count"] += 1
            sig["last"] = e["ts"]
            sig["levels_seen"].add(e["level"])
            if e["level"] in ("ERROR", "FATAL"):
                sig["level"] = "ERROR"

    starts = script_starts or launcher_starts
    findings = sorted(
        sigs.values(),
        key=lambda s: (
            PRIORITY[s["severity"]],
            LEVEL_RANK.get(s["level"], 2),
            0 if s["has_exception"] else 1,
            -s["count"],
        ),
    )
    for f in findings:
        f["levels_seen"] = sorted(f["levels_seen"])

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"findings": findings, "events": events, "starts": starts, "stops": stops}, fh, indent=2)

    shown = [f for f in findings if not args.category or f["category"] == args.category]

    print(f"file:       {path}")
    print(f"entries:    {sum(level_counts.values())}  ({', '.join(f'{k} {v}' for k, v in level_counts.most_common())})")
    print(f"window:     {first_ts} -> {last_ts}")
    if versions:
        print(f"server:     {versions[0]}" + (f"  (Pro {pro_versions[0]})" if pro_versions else ""))
    if os_line:
        print(f"platform:   {os_line.split('Operating system:')[-1].strip()}")
    if stops:
        print(f"stops:      {len(stops)} server stop(s) at {', '.join(stops[:6])}{' ...' if len(stops) > 6 else ''}")
    if len(starts) > 1 or stops:
        print(f"restarts:   {len(starts)} server launch(es) at {', '.join(starts[:6])}{' ...' if len(starts) > 6 else ''}")
    elif starts:
        print("restarts:   1 server launch in this log")
    if per_minute:
        minute, n = per_minute.most_common(1)[0]
        print(f"busiest:    {minute} with {n} {'/'.join(sorted(levels))} entries")

    if events:
        print("\nnotable events (any log level):")
        for rec in sorted(events.values(), key=lambda r: r["first"]):
            span = rec["first"] if rec["first"] == rec["last"] else f"{rec['first']} .. {rec['last']}"
            print(f"  x{rec['count']:<4} {span}  {rec['title']}")
            print(f"        {rec['note']}")

    reported = sum(f["count"] for f in findings)
    print(f"\n{len(findings)} distinct {'/'.join(sorted(levels))} findings covering {reported} entries")

    by_cat = collections.defaultdict(lambda: [0, 0])
    for f in findings:
        by_cat[f["category"]][0] += 1
        by_cat[f["category"]][1] += f["count"]
    print("\nby category (distinct, entries):")
    for cat, (d, n) in sorted(by_cat.items(), key=lambda kv: -kv[1][1]):
        print(f"  {cat:<12} {d:>4} {n:>8}")

    print(f"\ntop findings (priority: investigate > watch > unrecognized > noise):")
    for i, f in enumerate(shown[: args.top], 1):
        tag = f["severity"] if f["known"] else "unrecognized"
        head = f["title"] or f["message"][:110]
        print(f"\n{i}. [{tag}] [{f['category']}] {f['level']} x{f['count']}  {f['first']} .. {f['last']}")
        print(f"   {head}")
        print(f"   logger: {f['logger']}")
        if f["known"]:
            print(f"   what it means: {f['meaning']}")
            print(f"   next: {f['next_steps']}")
        else:
            print(f"   message: {f['message'][:220]}")
        if f["cause"]:
            print(f"   cause: {f['cause']}")
    hidden = len(shown) - args.top
    if hidden > 0:
        print(f"\n({hidden} more findings not shown; use --top or --json)")


if __name__ == "__main__":
    main()
