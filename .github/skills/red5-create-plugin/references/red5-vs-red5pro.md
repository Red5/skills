# Red5 plugin or Red5 Pro plugin

Read this before choosing. "Red5 plugin" and "Red5 Pro plugin" sound like one thing with two names; they are two separate extension points with different base classes, manifest keys, dependencies and loaders.

## Contents

- Side by side
- How to choose
- How the facts were established
- What a Pro plugin adds on top

## Side by side

| | Red5 (open source) | Red5 Pro |
| --- | --- | --- |
| Base class | `org.red5.server.plugin.Red5Plugin` (abstract, implements `IRed5Plugin`) | `com.red5pro.plugin.Red5ProPlugin`, which extends `Red5Plugin` |
| You implement | `doStart()`, `doStop()`, `getName()` | `doStartProPlugin(FileSystemXmlApplicationContext)`, `doStopProPlugin()`, `getName()` |
| `getName()` | Returns `null` in the base class, so you must override it | Same, override it |
| Manifest main class key | `Red5-Plugin-Main-Class` (optional `Red5-Plugin-Main-Method`, a static factory) | `Red5Pro-Plugin-Main-Class` |
| Version banner key | None | `<PluginName>-Version`, read with `getManifestValue(NAME + "-Version")` |
| Instantiation | Public no-argument constructor (or the static main method) | Created by Red5 Pro; the example plugin keeps its constructor empty and works in the start method |
| Loaded from | `<red5 root>/plugins/*.jar` and `*.zip` | `<red5pro root>/plugins/*.jar` |
| Loader | `org.red5.server.plugin.PluginLauncher`, a bean in `conf/red5.xml` | Red5 Pro's pluginator (`com.red5pro.activation.ProPluginator`), which is itself a jar in `plugins/` |
| Dependencies | Public: `org.red5:red5-server`, `red5-server-common`, `red5-io` on Maven Central | `com.red5pro:*` in a private repository (credentials), or the jars from a Red5 Pro server |
| Pro-only APIs | No | `ProStream`, `ProStreamService`, `Red5ProIO`, `submitTask` / `scheduleTask` executors, `LicenseManager`, `isReady()`, WHIP/WHEP, restreamer, clustering |
| Runs on | Open source Red5, and a Red5 Pro server (see below) | Red5 Pro servers only |

## How to choose

Ask what the plugin needs to do.

- **Needs packet-level access to a published stream, WebRTC/WHIP/WHEP, restreaming, clustering or the plugin executors:** Red5 Pro plugin. Those classes only exist in Red5 Pro, so the plugin cannot load on open source Red5.
- **Needs application scopes, connection or scope events, an application adapter, plain stream listeners or its own network service:** an open source plugin is enough, and it reaches the widest audience.
- **Unsure:** start open source. Moving to Pro later means changing the base class, the two lifecycle methods, the manifest key and the dependencies.

Also ask who will run it. A Pro plugin means every user needs a Red5 Pro server, and building it needs the Red5 Pro jars.

An open source plugin jar can be placed in a Red5 Pro server too: a Red5 Pro server's `conf/red5.xml` defines the same `pluginLauncher` bean, so the open source loader runs there as well. That was read from a Red5 Pro 16.3 install's configuration, not tested by loading a jar.

Do not put `Red5-Plugin-Main-Class` and `Red5Pro-Plugin-Main-Class` in the same jar. The Red5 Pro example plugin's `pom.xml` says "don't use both". The reason is not stated there; most likely each loader would try to start it.

## How the facts were established

So that a reader can tell what was verified from what is likely:

- Open source side: read from the Red5 server source (`PluginLauncher`, `Red5Plugin`, `IRed5Plugin`, `PluginRegistry`). `PluginLauncher` lists `plugins/` for `.jar` and `.zip` files, opens each manifest, reads `Red5-Plugin-Main-Class`, creates the class (constructor, or the static method named by `Red5-Plugin-Main-Method`), calls `setApplicationContext` and `setServer`, registers it in `PluginRegistry`, then calls `doStart()`.
- Pro side: the class relationships and methods were read with `javap` from a Red5 Pro 16.3 install (`Red5ProPlugin extends Red5Plugin`; the `submitTask`, `scheduleTask`, `isReady`, `getManifestValue` and `getProperty` methods exist). The manifest keys come from the Red5 Pro example plugin and match the built-in Pro plugins in that install (for example the WHIP plugin jar has `Red5Pro-Plugin-Main-Class` and `WhipPlugin-Version`).
- Not verified: how the pluginator calls `doStartProPlugin` and what license checks run before it. Treat the Pro lifecycle as "the server calls your start method once, after the license is accepted" and consult Red5 Pro documentation for anything finer.

## What a Pro plugin adds on top

These come from `Red5ProPlugin` and the Red5 Pro jars, and are what you give up by choosing open source:

- Plugin executors: `submitTask`, `scheduleTask` and related methods, with the thread pools managed by the server. The base `doStopProPlugin()` stops them.
- `isReady()` to tell whether the server has finished starting.
- `ProStream` and `ProStreamService.getProStream(scope, name)` for stream-level hooks, and `Red5ProIO.copy(packet)` to take a safe copy of a packet.
- Cluster and licensing helpers, and a registry for Pro services.

The base class also has `setOrder` / `getOrder` and a plugin load order setting, so the order plugins start in is configurable in some way. Check the Red5 Pro documentation before relying on load order.
