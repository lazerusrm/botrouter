# Optional Cua Driver desktop fallback

BotRouter can use [Cua Driver](https://cua.ai/docs/use-cua-with/grok-bot) for
accessibility-based control of native applications on the Grok Bot computer.
It is optional: Cua does not route models, preserve memory, or replace the
agent loop.

## Tool order

Use the first path that fits:

1. Existing API, connector, CLI, or saved helper.
2. Grok Bot's native `browser_*` DOM tools for webpages.
3. Cua Driver for native applications, file dialogs, browser chrome, or a page
   whose native DOM has actually failed.
4. Grok Bot's native `Computer` for canvas, pixel-only UI, or a surface Cua
   cannot reach.

This order avoids duplicating the existing browser driver and keeps the model's
tool context small. BotRouter does not expose Cua's complete MCP catalog or a
public MCP endpoint.

## Install and verify

Run inside the Grok Bot Linux computer:

```bash
plugins/botrouter/scripts/botrouter install-cua --yes
plugins/botrouter/scripts/botrouter cua-doctor
```

The install command uses Cua's official stable installer, prints the installed
version, runs `cua-driver doctor`, and starts its private local daemon.
BotRouter's ordinary `doctor` reports whether the optional executable is
present but does not fail when it is absent.

On Debian/Ubuntu X11 boxes, install `at-spi2-core` and `dbus-x11` first. The
daemon starts in a private D-Bus session, allowing applications launched through
Cua to use AT-SPI. Re-run `install-cua --yes` after a box reboot if the daemon is
not managed by a system service.

Linux requires an x86_64 X11 or XWayland desktop and AT-SPI 2. Run `cua-doctor`
from the same desktop environment the bot controls; a successful binary install
does not prove that a different display's accessibility bus is reachable.

## Agent contract

When Cua is installed, routed models receive a short conditional
instruction to call the local executable through the existing Shell tool. The
agent must:

1. Discover the exact application and window.
2. Get fresh window state.
3. Act through the newest returned element token or index when available.
4. Get fresh state and verify the result.

Use one Cua CLI call per Shell round so native Auto-review sees the exact action.
Cua's own runtime permission policy remains active. A normal task may use the
driver but may not install, update, reconfigure, or expose it.

Do not configure a public Streamable HTTP MCP tunnel for this local path. That
adds a network-accessible desktop-control boundary without helping models that
already execute inside the Grok Bot computer.

## Smoke test

Use a disposable bot and a harmless native application. Require it to identify
the app and one visible control using Cua, perform one reversible interaction,
verify the resulting state, and return one completion message. Confirm the host
log shows the intended third-party model and that no browser Task subagent was
created.

Keep native browser DOM even if this test passes. Cua earns its place only when
native-app completion is more reliable than pixel Computer on the same task.
