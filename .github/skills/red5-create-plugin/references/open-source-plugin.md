# Building a Red5 (open source) plugin

Checked against the Red5 server source (`PluginLauncher`, `Red5Plugin`, `IRed5Plugin`, `PluginRegistry`, and the built-in `WebSocketPlugin`) and compiled with Maven. No Red5 Pro classes are involved, and no license is needed.

## Contents

- Project layout
- How the server loads it
- Dependencies
- Lifecycle
- Build, deploy, verify
- Troubleshooting
- Other styles of extension

## Project layout

```
my-plugin/
  pom.xml
  src/main/java/com/acme/myplugin/MyPlugin.java    extends Red5Plugin
```

`scripts/scaffold.py --type red5` generates this, and it compiles.

## How the server loads it

At startup `org.red5.server.plugin.PluginLauncher` (the `pluginLauncher` bean in `conf/red5.xml`) lists `<red5 root>/plugins` for `.jar` and `.zip` files. For each one it:

1. opens the manifest and reads `Red5-Plugin-Main-Class`; jars without it are skipped silently;
2. loads that class;
3. creates the plugin: with a public no-argument constructor, or, if the manifest has `Red5-Plugin-Main-Method`, by calling that static method, which must return an `IRed5Plugin`;
4. calls `setApplicationContext` and `setServer`, registers the plugin in `PluginRegistry`, and calls `doStart()`;
5. logs `Loaded plugin: <class>`, or a warning with the exception if anything failed.

Consequences: the class needs a public no-argument constructor and must not do heavy work in it; `server` is available in `doStart()` but not in the constructor; a plugin that throws in `doStart()` is logged and skipped.

## Dependencies

Public artifacts on Maven Central, all `provided` scope because the server ships them:

- `org.red5:red5-server` (contains `Red5Plugin`)
- `org.red5:red5-server-common`
- `org.red5:red5-io`
- `org.slf4j:slf4j-api` and `org.springframework:spring-context`

Use the version your server runs; the scaffold detects it from `--server-dir` (the `red5-server-common-<version>.jar` in `lib/`), or take it from `--red5-version` when there is no install, in which case the default is the Red5 Pro example plugin's version and not the latest. The `slf4j.version` and `spring.version` properties in the generated `pom.xml` are compile-time only (the server provides those libraries), but match them to your server's if you can. The Red5 MQTT plugin in the Red5 GitHub organization uses the same artifacts and Java 21.

## Lifecycle

- `doStart()` is called once after the server is up. The generated plugin registers a scope listener and also configures application scopes that already exist, because a listener only hears about scopes created afterwards (the built-in `WebSocketPlugin` does the same).
- `doStop()` should undo what `doStart()` did: remove listeners, stop threads, close resources.
- Override `getName()`; the base class returns `null`, and `PluginRegistry` looks plugins up by name (`PluginRegistry.getPlugin(name)`).

## Worked example: track live applications

Scope notifications have properties that matter for the code. All checked in the Red5 source (`Server`, `Scope`, `BasicScope`):

- **They arrive on another thread, after a delay.** `Server.notifyScopeCreated` and `notifyScopeRemoved` do not call listeners directly; they schedule a one-shot job on the scheduling service. Use thread-safe collections, and do not assume the callback runs before other code in the same thread.
- **A created event can arrive for a scope you have already seen.** A plugin that starts while applications are running enumerates them in `doStart()`, and the delayed created events for those scopes can also arrive. Make the handler idempotent.
- **The removed event comes from `Scope.stop()`**, and only when the scope is enabled, running and has a handler. `stop()` does not detach the scope from its parent, so its name and path are still valid in the callback. A scope without a handler produces no removed event, so a counter keyed on removals can drift for such scopes.
- **Enumeration at start covers application scopes directly under each global scope** (`getBasicScopeNames(ScopeType.APPLICATION)`), which is what the generated `doStart()` does. Room scopes and anything deeper are not visited.

```java
private final Set<String> liveApps = ConcurrentHashMap.newKeySet();

private void configureApplication(IScope appScope) {
    // add() returns false if it was already there, which makes this safe to call twice for the same scope
    if (liveApps.add(appScope.getPath() + '/' + appScope.getName())) {
        log.info("Application started: {} (live: {})", appScope.getName(), liveApps.size());
    }
}

private void cleanupApplication(IScope appScope) {
    if (liveApps.remove(appScope.getPath() + '/' + appScope.getName())) {
        log.info("Application stopped: {} (live: {})", appScope.getName(), liveApps.size());
    }
}
```

Use the same key expression in both places. This example was compiled but not run in a server.

## Build, deploy, verify

```bash
mvn package
cp target/my-plugin-1.0.0.jar <red5>/plugins/
```

Restart Red5 and look in `log/red5.log` for `Loaded plugin: com.acme.myplugin.MyPlugin` and the plugin's own `Starting` and `started` lines. There is no properties-file convention in the base class; add your own if you need one.

## Troubleshooting

- **No `Loaded plugin` line and no warning.** The manifest has no `Red5-Plugin-Main-Class`, or the jar is not in `plugins/`. Check with `unzip -p my-plugin.jar META-INF/MANIFEST.MF`.
- **`Error loading plugin class`.** The class name in the manifest is wrong, or a dependency it needs is missing from the server's classpath.
- **`Error loading plugin: ...` with an exception.** The constructor or `doStart()` threw. The exception is in the log. Typical causes: no public no-argument constructor, or using `server` in the constructor.
- **The plugin loads but does nothing for existing applications.** It only configured scopes created after it started; see Lifecycle.

## Other styles of extension

Not every open source add-on is a `Red5Plugin` subclass. For example the Red5 MQTT plugin is configured through Spring XML in `red5.xml` (per its own `AGENTS.md`). If the developer wants an application-level feature and not a server-level plugin, a web application with its own Spring configuration may fit better. Say so if what they describe is really application logic.
