---
name: red5-log-triage
description: Triage a Red5 or Red5 Pro server log (red5.log) to find what is wrong, rank the problems and suggest next steps. Use this whenever someone shares, attaches or points at a red5.log (or red5.log.1, a rotated or zipped log, or a directory containing one) and asks what is wrong, why a stream or server failed, why clients dropped, what the errors mean, or wants a summary of a customer's log, even if they only say "can you look at this log". Covers startup failures, WebRTC/WHIP/WHEP, RTMP, RTSP, MoQ, clustering and A/V sync problems.
---

# red5-log-triage

Turn a large `red5.log` into a short, ranked list of what matters, so a support person can see the cause and the next step without reading tens of thousands of lines.

A busy log is mostly repetition: one failure can write the same warning thousands of times, and routine noise is often logged at WARN. The bundled script collapses repeats, ranks them, and labels the ones it recognizes. Your job is to read that output, check the recognized labels against the evidence, work out the unrecognized findings yourself, and explain the result in plain language.

## Prerequisites

- Python 3 in PATH. No other dependencies.
- The log can be plain text, `.gz` or `.zip`, or a directory (the script picks `red5.log` first).

## Workflow

1. Run the triage script on the log or directory the user gave you:

   ```bash
   python3 <skill-dir>/scripts/triage.py /path/to/red5.log
   ```

   `<skill-dir>` is this skill's folder, `.github/skills/red5-log-triage` in the skills repo. Use the full path if you are not running from the repo root.

   Options: `--top N` (findings to print, default 25), `--levels WARN,ERROR` (add `INFO` or `DEBUG` to widen), `--category webrtc` (focus on one area), `--json out.json` (all findings, machine-readable).

2. Read the header and the "notable events" block first. They give the time window, server version, platform, server stops and restarts, the busiest minute, and key INFO-level events such as licensing and trial-mode refusals. These frame everything else. A stop or restart right before a burst of warnings usually explains the burst: every client was dropped and reconnected at once, so freezes and reconnect storms right after it are a symptom of the restart, not a separate media fault. Who or what caused the restart is rarely in the log, so ask.

3. Work through the findings in the order printed (investigate, watch, unrecognized, noise). For each recognized finding the script prints what it means and what to check next. Treat that as a lead, not a verdict. Entries described as "inferred" in `references/knowledge.json` were written from reading logs, not from Red5 source, so say "likely" when you pass them on.

4. For the unrecognized findings, read the printed `cause:` line (the last `Caused by`, or the exception). Then look at the surrounding lines for context, because the explanation is usually a few lines earlier:

   ```bash
   grep -n "2026-09-15 09:53:3" /path/to/red5.log | grep -v "ConnManager" | head -60
   ```

   Use the first timestamp the script printed for that finding. INFO lines just before the first warning usually show which client, stream or session started it. During startup or a reconnect burst the same few INFO lines repeat hundreds of times, so drop them with `grep -v` (or look at only `" WARN \| ERROR "` lines) until the useful lines stand out.

5. Separate cause from symptom. A flood of write failures, SCTP errors and DTLS errors is usually one client-disconnect or network event echoing through several loggers. Find the earliest entry in the burst and report that as the cause, and describe the rest as consequences.

6. Report back (see below). Offer to add anything you worked out to `references/knowledge.json` so the next person gets it for free.

## How to report

Keep it short and lead with the answer. Support people forward this to customers or engineers, so it should stand on its own:

- **Summary**: one or two sentences. What is the most likely problem, and how confident are you?
- **Evidence**: the top few findings with counts and timestamps, quoting the key log line.
- **Likely cause and next steps**: what to check or ask the customer.
- **Probably harmless**: noisy findings you saw and deliberately set aside, so nobody chases them.
- **Unknowns**: anything you could not explain, with the log lines the engineer should look at.

If nothing looks wrong, say that plainly and mention what you checked. A log with only noise and a clean startup is a valid result.

## Judgment guidelines

- **Counts need context.** 12,000 warnings in four minutes during a load test is different from 12,000 over a month. Compare with the time window and the number of sessions.
- **Do not over-claim.** The script sees only what was logged. Say what the log supports and what would need confirming on the server or client side.
- **Startup failures come first.** If an application failed to start, its streams cannot work, so anything downstream is a distraction until that is fixed.
- **WARN is not always a problem.** Several routine messages are logged at WARN. Rely on the recognized `noise` labels, and use your own judgment for new ones.
- **Check the first occurrence.** The first entry in a burst is more informative than the thousandth.
- **Logs contain personal data and secrets.** Startup output can include the license key, and expect IP addresses, usernames, user-agent strings and stream names, and sometimes cloud account IDs or bucket names inside exception text. Quote only what is needed to make the point, and keep full excerpts out of anything shared widely.

## Extending the knowledge

`references/knowledge.json` holds two lists, both plain JSON:

- `logger_rules`: a logger-name prefix mapped to a category. First match wins, so put specific prefixes before general ones.
- `known_issues`: a regex matched against `<logger> <message>`, with a title, what it means, and next steps. All repeats of one issue merge into a single finding even when ids or names in the message differ. Set `severity` to `investigate`, `watch` or `noise`.

When you work out a new pattern during a triage, add it here, keep the wording honest ("inferred" when it is not confirmed from source), and run the script again on the same log to confirm it matches and merges as expected.
