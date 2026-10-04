#!/usr/bin/env python3
"""Generate a Maven project for a Red5 or Red5 Pro server plugin.

  scaffold.py --type pro  --name MyPlugin --package com.acme.myplugin --server-dir /usr/local/red5pro
  scaffold.py --type red5 --name MyPlugin --package com.acme.myplugin --red5-version 2.0.46

The two types are different products: a Red5 (open source) plugin extends org.red5.server.plugin.Red5Plugin and runs on any Red5
server; a Red5 Pro plugin extends com.red5pro.plugin.Red5ProPlugin and runs only on Red5 Pro. See ../references/red5-vs-red5pro.md.

Standard library only. Templates live in ../assets.
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

# defaults match the red5pro/example-plugin pom; --server-dir replaces them with what the target server actually ships
DEFAULT_RED5 = "2.0.29"
DEFAULT_PRO = "15.2.0"
DEFAULT_PRO_COMMON = "14.3.0.5"

# jars in a Red5 Pro server's lib directory that are libraries, not the core Red5 Pro jar
PRO_LIBRARY_PREFIXES = ("common", "internal", "notifications", "crypto", "ice", "srt", "cauldron", "moq")


def die(msg):
    sys.exit(f"error: {msg}")


def render(text, values):
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", value)
    left = re.findall(r"@@[A-Z_]+@@", text)
    if left:
        die(f"template placeholders not filled: {sorted(set(left))}")
    return text


def read_asset(*parts):
    with open(os.path.join(ASSETS, *parts), encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def dep(group, artifact, version, scope="provided", exclude_all=False):
    excl = ""
    if exclude_all:
        excl = (
            "\n            <exclusions>\n                <exclusion>\n                    <groupId>*</groupId>\n"
            "                    <artifactId>*</artifactId>\n                </exclusion>\n            </exclusions>"
        )
    return (
        f"        <dependency>\n            <groupId>{group}</groupId>\n            <artifactId>{artifact}</artifactId>\n"
        f"            <version>{version}</version>\n            <scope>{scope}</scope>{excl}\n        </dependency>"
    )


def system_dep(artifact, relpath):
    return (
        f"        <dependency>\n            <groupId>local</groupId>\n            <artifactId>{artifact}</artifactId>\n"
        f"            <version>1</version>\n            <scope>system</scope>\n"
        f"            <systemPath>${{red5.server.dir}}/{relpath}</systemPath>\n        </dependency>"
    )


def find_one(server_dir, pattern, what):
    hits = sorted(glob.glob(os.path.join(server_dir, pattern)))
    if not hits:
        die(f"{what} not found in {server_dir} (looked for {pattern}); is --server-dir a Red5 server directory?")
    return hits[0]


def version_of(path, prefix):
    name = os.path.basename(path)[: -len(".jar")]
    return name[len(prefix):]


def detect_pro_core_jar(server_dir):
    """The core Red5 Pro jar is lib/red5pro-<codename>-<version>.jar (the Maven artifact red5pro-mega has the same classes)."""
    for path in sorted(glob.glob(os.path.join(server_dir, "lib", "red5pro-*.jar"))):
        rest = os.path.basename(path)[len("red5pro-"):]
        if rest.startswith(PRO_LIBRARY_PREFIXES) or rest.endswith("-dist.jar") or "plugin" in rest.lower():
            continue
        return path
    die(f"core Red5 Pro jar (lib/red5pro-<codename>-<version>.jar) not found in {server_dir}; is this a Red5 Pro server, not open source Red5?")


def server_dependencies(kind, server_dir, red5_version, pro_version, pro_common_version):
    """Return (dependency xml, property xml, repositories xml, notes)."""
    notes = []
    common_deps = [
        dep("org.slf4j", "slf4j-api", "${slf4j.version}"),
        dep("org.springframework", "spring-context", "${spring.version}"),
    ]
    if server_dir:
        rel = lambda p: os.path.relpath(p, server_dir).replace(os.sep, "/")
        jars = {
            "red5-server": find_one(server_dir, "red5-server.jar", "red5-server.jar"),
            "red5-server-common": find_one(server_dir, "lib/red5-server-common-*.jar", "red5-server-common jar"),
            "red5-io": find_one(server_dir, "lib/red5-io-*.jar", "red5-io jar"),
        }
        if kind == "pro":
            jars["red5pro"] = detect_pro_core_jar(server_dir)
            jars["red5pro-common"] = find_one(server_dir, "lib/red5pro-common-*.jar", "red5pro-common jar")
        deps = [system_dep(name, rel(path)) for name, path in jars.items()]
        # everything else the plugin needs at compile time also comes from the server's own lib directory
        for artifact, pattern in (("slf4j-api", "lib/slf4j-api-*.jar"), ("spring-context", "lib/spring-context-[0-9]*.jar"),
                                  ("spring-core", "lib/spring-core-[0-9]*.jar"), ("spring-beans", "lib/spring-beans-[0-9]*.jar"),
                                  ("mina-core", "lib/mina-core-*.jar")):
            hits = sorted(glob.glob(os.path.join(server_dir, pattern)))
            if hits:
                deps.append(system_dep(artifact, rel(hits[0])))
        props = f"        <red5.server.dir>{server_dir}</red5.server.dir>"
        notes.append(
            f"compiles against the jars in {server_dir} (system scope), so the API matches the server you will deploy to. "
            "Build elsewhere with: mvn -Dred5.server.dir=/path/to/server package"
        )
        return "\n".join(deps), props, "", notes

    if kind == "red5":
        props = ""
        deps = [
            dep("org.red5", "red5-server", "${red5.version}", exclude_all=True),
            dep("org.red5", "red5-server-common", "${red5.version}", exclude_all=True),
            dep("org.red5", "red5-io", "${red5.version}", exclude_all=True),
        ] + common_deps
        return "\n".join(deps), props, "", notes

    props = (
        f"        <red5.version>{red5_version}</red5.version>\n"
        f"        <red5pro.version>{pro_version}</red5pro.version>\n"
        f"        <red5pro-common.version>{pro_common_version}</red5pro-common.version>"
    )
    repos = (
        "    <repositories>\n        <repository>\n            <id>central</id>\n            <url>https://repo.maven.apache.org/maven2</url>\n"
        "        </repository>\n        <!-- private: needs credentials in ~/.m2/settings.xml (server id red5pro-ext-release) or the jars installed locally -->\n"
        "        <repository>\n            <id>red5pro-ext-release</id>\n            <url>https://red5pro.jfrog.io/red5pro/ext-release-local</url>\n"
        "        </repository>\n    </repositories>"
    )
    deps = [
        dep("com.red5pro", "red5pro-mega", "${red5pro.version}", exclude_all=True),
        dep("com.red5pro", "red5pro-common", "${red5pro-common.version}", exclude_all=True),
        dep("org.red5", "red5-server", "${red5.version}", exclude_all=True),
        dep("org.red5", "red5-server-common", "${red5.version}", exclude_all=True),
        dep("org.red5", "red5-io", "${red5.version}", exclude_all=True),
    ] + common_deps
    notes.append(
        f"using default versions (Red5 Pro {pro_version}, Red5 {red5_version}); change the properties in pom.xml to match your server, "
        "or re-run with --server-dir to build against the server's own jars"
    )
    return "\n".join(deps), props, repos, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--type", required=True, choices=["red5", "pro"], help="red5 = open source Red5 plugin, pro = Red5 Pro plugin")
    ap.add_argument("--name", required=True, help="plugin class name, for example MyPlugin (Plugin is appended if missing)")
    ap.add_argument("--package", required=True, help="Java package, for example com.acme.myplugin")
    ap.add_argument("--group-id", help="Maven groupId (default: first two parts of the package)")
    ap.add_argument("--artifact-id", help="Maven artifactId (default: kebab-case of the name)")
    ap.add_argument("--out", help="output directory (default: ./<artifact-id>)")
    ap.add_argument("--server-dir", help="installed Red5 or Red5 Pro server to build against; versions and jars are detected from it")
    ap.add_argument("--red5-version", help=f"org.red5 version when no --server-dir (default {DEFAULT_RED5}, the example plugin's version, not the latest)")
    ap.add_argument("--red5pro-version", default=DEFAULT_PRO, help=f"com.red5pro red5pro-mega version when no --server-dir (default {DEFAULT_PRO})")
    ap.add_argument("--red5pro-common-version", default=DEFAULT_PRO_COMMON, help=argparse.SUPPRESS)
    ap.add_argument("--with-listener", action="store_true", help="pro only: add a publish hook and a per-stream packet listener")
    ap.add_argument("--force", action="store_true", help="write into a non-empty output directory")
    args = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", args.name):
        die("--name must be a Java identifier such as MyPlugin")
    if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*", args.package):
        die("--package must look like com.acme.myplugin (lowercase)")
    if args.with_listener and args.type != "pro":
        die("--with-listener is only available for --type pro (ProStream is a Red5 Pro API)")

    cls = args.name if args.name.endswith("Plugin") else args.name + "Plugin"
    base = cls[: -len("Plugin")] or cls
    artifact = args.artifact_id or re.sub(r"(?<!^)(?=[A-Z])", "-", cls).lower()
    group = args.group_id or ".".join(args.package.split(".")[:2])
    out = os.path.abspath(args.out or artifact)
    server_dir = os.path.abspath(os.path.expanduser(args.server_dir)) if args.server_dir else None
    if server_dir and not os.path.isdir(server_dir):
        die(f"--server-dir {server_dir} is not a directory")
    if os.path.isdir(out) and os.listdir(out) and not args.force:
        die(f"{out} is not empty (use --force to write into it)")

    red5_version = args.red5_version or DEFAULT_RED5
    if server_dir:
        red5_version = version_of(find_one(server_dir, "lib/red5-server-common-*.jar", "red5-server-common jar"), "red5-server-common-")
    deps, props, repos, notes = server_dependencies(args.type, server_dir, red5_version, args.red5pro_version, args.red5pro_common_version)
    props_file = f"{artifact}.properties"
    listener, hook = f"{base}StreamListener", f"{base}PublishHook"

    values = {
        "PACKAGE": args.package, "CLASS": cls, "GROUP_ID": group, "ARTIFACT_ID": artifact, "RED5_VERSION": red5_version,
        "DEPENDENCIES": deps, "PROPS_FILE": props_file, "LISTENER": listener, "HOOK": hook,
    }
    src = os.path.join(out, "src", "main", "java", *args.package.split("."))

    if args.type == "red5":
        pom = render(read_asset("red5", "pom.xml.tmpl"), values)
        if server_dir:  # system scope: the template's version property is unused but harmless
            pom = pom.replace("    <properties>\n", "    <properties>\n" + props + "\n", 1)
        write(os.path.join(out, "pom.xml"), pom)
        write(os.path.join(src, f"{cls}.java"), render(read_asset("red5", "Plugin.java.tmpl"), values))
    else:
        values["PROPERTIES"] = props
        values["REPOSITORIES"] = repos
        if args.with_listener:
            values["HOOK_IMPORTS"] = ""
            values["HOOK_FIELD"] = f"\n    private final {hook} publishHook = new {hook}();\n"
            values["HOOK_REGISTER"] = (
                "        // attach the publish hook so each new publisher gets a stream listener\n"
                "        if (appScope.getHandler() instanceof org.red5.server.adapter.MultiThreadedApplicationAdapter adapter) {\n"
                "            adapter.registerStreamPublishSecurity(publishHook);\n"
                "        } else {\n"
                "            log.warn(\"Scope {} has no application adapter yet; the publish hook was not registered\", appScope.getName());\n"
                "        }\n"
            )
            values["HOOK_UNREGISTER"] = (
                "        if (appScope.getHandler() instanceof org.red5.server.adapter.MultiThreadedApplicationAdapter adapter) {\n"
                "            adapter.unregisterStreamPublishSecurity(publishHook);\n"
                "        }\n"
            )
            write(os.path.join(src, f"{listener}.java"), render(read_asset("pro", "StreamListener.java.tmpl"), values))
            write(os.path.join(src, f"{hook}.java"), render(read_asset("pro", "PublishHook.java.tmpl"), values))
        else:
            for key in ("HOOK_IMPORTS", "HOOK_FIELD", "HOOK_REGISTER", "HOOK_UNREGISTER"):
                values[key] = ""
        write(os.path.join(out, "pom.xml"), render(read_asset("pro", "pom.xml.tmpl"), values))
        write(os.path.join(src, f"{cls}.java"), render(read_asset("pro", "Plugin.java.tmpl"), values))
        write(os.path.join(out, "src", "main", "resources", props_file), render(read_asset("pro", "plugin.properties.tmpl"), values))
    write(os.path.join(out, ".gitignore"), "target/\n")

    kind = "Red5 Pro" if args.type == "pro" else "Red5 (open source)"
    manifest = "Red5Pro-Plugin-Main-Class" if args.type == "pro" else "Red5-Plugin-Main-Class"
    print(f"created {kind} plugin project in {out}")
    print(f"  class:    {args.package}.{cls}  (manifest {manifest})")
    for note in notes:
        print(f"  note:     {note}")
    print("\nnext:")
    print(f"  cd {out} && mvn -o package   # drop -o if the dependencies are not already in ~/.m2")
    print(f"  cp target/{artifact}-1.0.0.jar <server>/plugins/")
    if args.type == "pro":
        print(f"  cp src/main/resources/{props_file} <server>/conf/")
    print("  restart the server, then look in log/red5.log for:")
    print(f"    {'Starting ' + cls + ' version' if args.type == 'pro' else 'Loaded plugin: ' + args.package + '.' + cls}")


if __name__ == "__main__":
    main()
