# Building a Red5 Pro plugin

Based on the Red5 Pro example plugin (https://github.com/red5pro/example-plugin, commit 3c79c10 reviewed) and checked against the jars of Red5 Pro 16.2 and 16.3 installs. A Red5 Pro plugin runs only on a Red5 Pro server.

## Contents

- Project layout
- Dependencies: three ways to get the Red5 Pro jars
- Lifecycle
- Properties
- Background tasks
- Listening to stream packets
- Build, deploy, verify
- Troubleshooting
- Traps in the example plugin

## Project layout

```
my-plugin/
  pom.xml
  src/main/java/com/acme/myplugin/
    MyPlugin.java            extends Red5ProPlugin
    MyStreamListener.java    optional: per-stream packet listener
    MyPublishHook.java       optional: attaches the listener when a publisher starts
  src/main/resources/my-plugin.properties   copied to the server's conf/ at deploy time
```

`scripts/scaffold.py --type pro` generates this, and it compiles.

## Dependencies: three ways to get the Red5 Pro jars

The Red5 Pro Maven repository (`red5pro.jfrog.io`) needs credentials. Everything the server ships is `provided` scope; the plugin jar should contain only your own classes and any third-party library the server does not already have.

1. **Build against an installed server (recommended).** `scaffold.py --server-dir /path/to/red5pro` generates a `pom.xml` that points at the jars in the server's directory (`system` scope, through a `red5.server.dir` property). The API you compile against is the API that will run. Override the location with `mvn -Dred5.server.dir=/other/path package`. The core Red5 Pro jar there is named `lib/red5pro-<codename>-<version>.jar`; the Maven artifact `red5pro-mega` has the same core classes (`Red5ProPlugin`, `ProStream`, `LicenseManager`).
2. **Maven coordinates with credentials.** Add the repository credentials to `~/.m2/settings.xml` under server id `red5pro-ext-release`, then use `com.red5pro:red5pro-mega` and `com.red5pro:red5pro-common` at versions matching your server. Without `--server-dir` the scaffold uses the example's versions (Red5 Pro 15.2.0, Red5 2.0.29), which you must adjust.
3. **Install the jars into your local Maven repository** with `mvn install:install-file` for each jar. The example plugin's README does this, but it names the core jar `red5pro-mega-<version>.jar`; in the server installs checked it is `red5pro-<codename>-<version>.jar`, so use the file you actually have.

## Lifecycle

Red5 Pro creates the plugin and calls `doStartProPlugin(FileSystemXmlApplicationContext)` to start it and `doStopProPlugin()` to stop it. In the generated plugin:

- `doStartProPlugin` logs a version banner, reads properties, honors the `enable` flag, and registers a scope listener. It also walks the application scopes that already exist, because a scope listener only hears about scopes created after it is added.
- `doStopProPlugin` removes the listener, undoes per-application setup, and calls `super.doStopProPlugin()`, which stops the plugin's executors.
- `getName()` must return the same name used for the manifest version entry (`<Name>-Version`) and for lookups such as `LicenseManager.getInstance().getPlugin(NAME)`.

The `server` field (the Red5 `Server`) is provided by the base class and is set before your start method runs.

## Properties

The example reads `conf/<name>.properties` relative to the server's working directory. The generated plugin reads it from the directory in the `red5.config_root` system property (falling back to `conf`), and logs a warning and uses defaults if the file is missing. The file inside the jar's `src/main/resources` is a template: copy it into the server's `conf/` when deploying. The generated file has `enable=true`; the example ships `enable=false`.

The generated plugin does not override `getProperty(String)`, which the example does. It exposes its own `prop(key, default)` so values the base class looks up are not changed.

## Background tasks

Use the plugin executor instead of creating threads:

```java
MyPlugin.submit(() -> { /* work */ });
MyPlugin.schedule(task, initialDelayMs, repeatDelayMs);
```

These look the plugin up with `LicenseManager.getInstance().getPlugin(NAME)` and return `null` when the plugin is not registered, for example when it is disabled, so check for `null` if the result matters.

## Listening to stream packets

`ProStream` is the Red5 Pro stream object. `ProStreamService.getProStream(scope, streamName)` returns it once the stream exists, which is after the publish request, so the generated `PublishHook` retries for about five seconds. The listener implements `IStreamListener.packetReceived(IBroadcastStream, IStreamPacket)`. Rules the generated listener follows, and yours should too:

- **Copy the packet** with `Red5ProIO.copy(packet)` before keeping it; the server reuses the buffer.
- **Never do heavy work on the receive thread.** Hand packets to a worker through a bounded queue and drop (and count) packets when it is full. An unbounded queue grows without limit when processing is slower than the stream.
- **Clean up on termination.** Register a `ProStreamTerminationEventListener`; in `streamStopped` remove the listener, cancel the worker and clear the queue.
- Packet types are `AudioData`, `VideoData` and `MetaData`.

The publish hook is an `IStreamPublishSecurity` registered on the application's `MultiThreadedApplicationAdapter` (`registerStreamPublishSecurity`). It is also called to allow or deny a publish: return `false` from `isPublishAllowed` to reject it. The generated hook always returns `true`. The adapter can be missing when a scope is created; the generated plugin logs a warning in that case.

## Worked example: count packets per stream

State for one stream belongs in that stream's listener instance: the generated `PublishHook` creates one `MyStreamListener` per publish, so its fields are per stream and need no map keyed by stream name. Count in `packetReceived`, which sees every packet, and not in `process()`, which only sees the packets that fit in the bounded queue (when the worker falls behind, packets are dropped, so counting there undercounts). Report in `stop()`, which the termination listener calls when the stream stops.

```java
private final AtomicLong audioPackets = new AtomicLong();
private final AtomicLong videoPackets = new AtomicLong();
private final AtomicBoolean reported = new AtomicBoolean();

@Override
public void packetReceived(IBroadcastStream stream, IStreamPacket packet) {
    if (!running || packet == null) {
        return;
    }
    if (packet instanceof AudioData) {
        audioPackets.incrementAndGet();
    } else if (packet instanceof VideoData) {
        videoPackets.incrementAndGet();
    }
    // ... the generated copy-and-queue code follows
}

public void stop() {
    // ... generated cleanup ...
    if (reported.compareAndSet(false, true)) {
        log.info("Stream {} in {} stopped: audio={} video={}", streamName, scope.getName(), audioPackets.get(), videoPackets.get());
    }
}
```

`AudioData` and `VideoData` are in `org.red5.server.net.rtmp.event`. Count the original packet, as above, and not the copy: this example was compiled but not run, so whether `Red5ProIO.copy` keeps the concrete packet type is not verified. If you only need counts, delete the copy-and-queue code from `packetReceived` so every packet is not copied for nothing.

## Build, deploy, verify

```bash
mvn package
cp target/my-plugin-1.0.0.jar <red5pro>/plugins/
cp src/main/resources/my-plugin.properties <red5pro>/conf/
```

Restart the server and check `log/red5.log` for `Starting MyPlugin version ...`. In the logs of a Red5 Pro server, plugins also show up as `Init Red5 Pro plugin: <name>` and `Start Red5 Pro plugin: <name>`.

## Troubleshooting

- **Nothing in the log about the plugin.** The jar must be in `plugins/`, and the manifest must have `Red5Pro-Plugin-Main-Class` naming the class. Check with `unzip -p my-plugin.jar META-INF/MANIFEST.MF`. Make sure the class extends `Red5ProPlugin`.
- **Loaded but does nothing.** Check the `enable` property in the file in `conf/`, and that the file is in `conf/` and not only in the jar.
- **`ClassNotFoundException` at runtime.** A dependency the server does not provide was left out of the jar, or one it does provide was bundled and conflicts. Server-provided libraries are `provided` scope.
- **`NoSuchMethodError` or `IncompatibleClassChangeError`.** The plugin was compiled against different Red5 Pro versions than the server runs. Rebuild with `--server-dir` pointing at that server.
- **Build cannot resolve `com.red5pro` artifacts.** See the three dependency options above.
- **Version banner shows `null` or an unexpected value.** `getManifestValue(NAME + "-Version")` reads the manifest entry named `<Name>-Version`, so the entry in `pom.xml` must use exactly the same name as `NAME`.

## Traps in the example plugin

Found by reading the example at the reviewed commit. The generated code avoids each; if the developer is copying from the example, tell them.

1. **The listener's `start()` is never called by the publish hook.** The hook adds the listener straight to the stream, so the worker that drains the queue never runs, and every packet is copied into a queue nobody reads. On a long stream that is unbounded memory growth.
2. **`stop()` uses `provision`, which is `null` with the `(scope, streamName, dumpAV)` constructor** that the hook uses. Its result depends on what `RestreamerPlugin.findStream(null)` does, so treat that path as untested (it is not called from the hook anyway, see 1).
3. **The hook passes `dumpAV = true`**, which writes audio and video dump files to `java.io.tmpdir` for every publisher. That is a debugging aid and should be off by default.
4. **`MyServlet` is `abstract` but `web.xml` registers it as a servlet class**, which cannot be instantiated. Also, `src/main/webapp/WEB-INF/web.xml` is not packaged into a plain `jar` build. Treat the servlet files as a pattern for an application's own `WEB-INF/web.xml` and write a concrete servlet.
5. **The manifest version uses `${buildNumber}`** but the pom has no build-number plugin, so the banner would print the literal `${buildNumber}`.
6. **A missing properties file is logged as an error but startup continues** and still reports "Plugin started", because the load is inside a `catch (Throwable)`.
7. **The scope listener misses applications that were already running** when the plugin started; nothing walks the existing scopes. (Red5's own `WebSocketPlugin` does.)
8. **The README and `pom.xml` disagree** on versions (README: Red5 Pro 15.0.0, Red5 2.0.22, jar 1.0.0; pom: 15.2.0, 2.0.29, 1.0.1). Trust the pom, and match your server.
9. **`enable=false` in the shipped properties**, so the example does nothing until it is changed.
