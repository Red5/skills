---
name: red5-create-plugin
description: Help a developer create their own plugin for the Red5 (open source) or Red5 Pro media server, and make sure they understand how the two plugin types differ. Generates a ready-to-build Maven project, then guides building, deploying and verifying it. Use this whenever someone wants to write, start, scaffold, extend or debug a Red5 or Red5 Pro plugin, custom stream processing, a stream or packet listener, a publish hook, or server-side extension, or asks how Red5 plugins work or which kind to build, even if they do not say "skill" or "scaffold".
---

# red5-create-plugin

Create a Red5 or Red5 Pro server plugin. The two are different products with different base classes, manifest keys and dependencies, and picking the wrong one is the most common way to lose a day. So the first job is to make sure the developer knows which one they are building.

## Prerequisites

- Java 21 and Maven 3.6 or newer.
- Python 3 (for the scaffold script).
- For a Red5 Pro plugin: the Red5 Pro jars, either from an installed Red5 Pro server (best) or from the private Red5 Pro Maven repository with credentials.

## Workflow

### 1. Establish which type, and say what the difference means for them

If the developer did not say, ask. Then explain the difference in terms of their goal, using the table below. Details and evidence are in `references/red5-vs-red5pro.md`.

| | Red5 (open source) plugin | Red5 Pro plugin |
| --- | --- | --- |
| Runs on | Red5 open source, and also a Red5 Pro server (its `conf/red5.xml` has the same plugin launcher) | Red5 Pro server only |
| Base class | `org.red5.server.plugin.Red5Plugin` | `com.red5pro.plugin.Red5ProPlugin` (itself a subclass of `Red5Plugin`) |
| Lifecycle methods | `doStart()` / `doStop()` | `doStartProPlugin(FileSystemXmlApplicationContext)` / `doStopProPlugin()` |
| Jar manifest key | `Red5-Plugin-Main-Class` | `Red5Pro-Plugin-Main-Class`, plus a `<Name>-Version` entry for the version banner |
| Dependencies | Public, on Maven Central (`org.red5:red5-server` and others) | `com.red5pro:*` jars: private repository with credentials, or taken from a Red5 Pro server |
| Extra APIs | Scopes, application adapter, stream listeners | Adds `ProStream`, `ProStreamService`, `Red5ProIO`, plugin executors, WHIP/WHEP, clustering |

If you cannot ask (an unattended run, or the request already says enough), pick using the table, and state the assumption and the reason in your reply so the developer can correct it.

Guide the choice. If they need Pro-only capabilities (`ProStream` packet access, WebRTC/WHIP/WHEP, restreaming, clustering, plugin executors) they need a Pro plugin, and it will not run on open source Red5. If they want it to run on any Red5 server, or have no Pro license, build the open source kind. On a Pro server, a plugin that only needs scope or connection events, or plain stream listeners, can also be an open source plugin and stays portable; one that needs packet-level `ProStream` access or its stream-termination events needs Pro. Never put both manifest keys in one jar: the Red5 Pro example plugin says not to, and the two keys belong to different loaders.

### 2. Gather what the scaffold needs

- Plugin name and Java package (for example `MyPlugin`, `com.acme.myplugin`). If they gave none, propose a name from what the plugin does and `com.<their org>.<name>`, and say which you used.
- The server to build against. Ask for the install directory of the target Red5 or Red5 Pro server. Building against the server's own jars guarantees the API matches what will run, and avoids guessing versions. With no install available, pass `--red5-version <version>` (open source) or `--red5pro-version <version>` (Pro) to name the versions, and tell them to check the version properties in the generated `pom.xml`.
- For Pro: whether they want the stream-listener starter (a publish hook that attaches a packet listener to each new stream).

### 3. Generate the project

```bash
python3 <skill-dir>/scripts/scaffold.py --type pro --name MyPlugin --package com.acme.myplugin \
    --server-dir /path/to/red5pro --with-listener --out ./my-plugin
```

`<skill-dir>` is the folder this `SKILL.md` was loaded from. Use `--type red5` for an open source plugin; `--with-listener` is Pro only. Without `--server-dir` or an explicit version flag the script falls back to the versions in the Red5 Pro example plugin (Red5 2.0.29, Red5 Pro 15.2.0), which are not the latest, and says so. `scripts/scaffold.py --help` lists every option.

Read the script's output to the developer: it prints the class, the manifest key used and the next commands.

### 4. Build

```bash
cd my-plugin && mvn package      # add -o to work offline from the local Maven cache
```

A build with `--server-dir` reads the server's jars from disk and needs no network for them; Maven still needs its own build plugins cached or downloadable.

All Red5 and Red5 Pro dependencies are `provided`, because the server supplies them at runtime. Only dependencies the server does not ship belong inside the plugin jar. If the build cannot resolve `com.red5pro` artifacts, see the dependency options in `references/pro-plugin.md`.

### 5. Deploy and verify

Copy the jar into the server's `plugins/` directory. A Pro plugin also needs its properties file copied into the server's `conf/` directory, because it is read from there at runtime and not from inside the jar. Restart the server and look in `log/red5.log`:

- Pro: the plugin logs `Starting <Name> version <version>`.
- Open source: the launcher logs `Loaded plugin: <fully.qualified.Class>`.

If it does not appear, work through the troubleshooting list in the matching reference file. The `red5-log-triage` skill in this repository can summarize a log that is too long to read.

Do not copy a jar into a running server or restart it without the developer's say-so. Servers are often shared or in use, and a restart drops every connected client. The generated project has been compiled against real servers, but loading it in a running server has not been tested by this skill, so say so when reporting.

### 6. Help them build the real thing

The generated classes have `TODO` markers where their logic goes. The reference files for each type include a worked example (counting packets per stream for Pro, tracking live applications for open source) that shows where per-item state belongs and the threading rules, so read the matching one before writing logic. Other typical next steps are there too: reading properties, running background tasks on the plugin executor, and exposing HTTP endpoints.

## Things worth warning about

The Red5 Pro example plugin (https://github.com/red5pro/example-plugin) is the reference this skill was built from. It is a good map of the API, but copying it as is has several traps, listed with details in `references/pro-plugin.md`. The generated code avoids them: the stream listener uses a bounded queue and is started by the publish hook, the scope listener also configures applications that were already running, the version banner does not print a literal `${buildNumber}`, and nothing writes debug dump files.

If the developer is adapting the example directly instead of using the scaffold, point out those traps.
