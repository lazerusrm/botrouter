# BotRouter: shareable operator plugin

## Decision

Ship the harness as two layers:

1. **`grok-bot-setup` runtime** — routing, tools, browser/DOM/Computer adapters, Auto-review, continuation, host injection, and supervisor integration.
2. **`botrouter` Codex plugin** — one setup/operations skill plus a thin command wrapper around the runtime.

This avoids a second implementation of deployment and authentication. A setup agent can operate the wrapper semi-autonomously while the existing CLI remains the source of truth.

## Why there is no custom MCP server

The useful operations already exist as local commands. Wrapping them in an MCP server would add another privileged process, protocol surface, authentication boundary, and failure mode without adding capability. The plugin skill can call the wrapper directly. Add an MCP server later only if a remote control plane needs a stable network API; require gateway authentication and narrowly scoped methods at that point.

## Setup flow

```text
doctor (read-only)
  -> install-runtime, only when absent
  -> provider-owned interactive login
  -> configure the selected provider privately
  -> test
  -> apply --yes
  -> resume after restart
  -> doctor + one real bot smoke test
  -> complete --yes
```

The setup agent owns this sequence in its main thread. It continues through safe, reversible steps and pauses only for login, a consequential confirmation, or a real unresolved blocker. It does not delegate onboarding to another bot because that loses the user's choices and login context.

`apply --yes` writes a mode-0600 checkpoint before the supervisor restart. The returning setup thread runs `resume`; the checkpoint then remains until one real target-bot task succeeds and the operator runs `complete --yes`. This prevents a restart from being mistaken for completion.

BotRouter requires an OpenSSH client so Shell-based remote workflows do not advertise capability and then fail on a missing executable. `doctor` checks it and `install-system-deps` installs Debian/Ubuntu's `openssh-client` with existing administrator access. Container images should include it at build time; live package installation alone is not durable across image replacement.

## Authentication matrix

| Lane | Portable flow | Stored by | Plugin behavior |
|---|---|---|---|
| Codex | `codex login --device-auth` | Codex CLI/keyring | Launch login; inspect presence only |
| Grok CLI | `grok login --device-auth` | Grok CLI | Launch login; inspect presence only |
| Claude | `claude login` | Claude CLI/keyring | Launch login; inspect presence only |
| API-key provider | Interactive `adapters use <provider>` | Existing runtime configuration | Never put keys in command arguments |
| Cursor subscription | No supported portable plugin flow | Cursor | Require local account-owner authentication |

Credential files and subscription tokens are not plugin assets. Never commit them, package them, print them, or copy them between people, homes, or machines. A third-party runtime reading a CLI credential store is credential delegation by that account owner.

## Commands

From the plugin root:

```bash
scripts/botrouter doctor
scripts/botrouter auth-status
scripts/botrouter install-system-deps
scripts/botrouter install-runtime
scripts/botrouter login codex
scripts/botrouter configure grok-session
scripts/botrouter test
scripts/botrouter apply --yes
scripts/botrouter resume
scripts/botrouter complete --yes
```

`GROK_BOT_SETUP_ROOT` can point at a non-default runtime checkout.

## Installation from this repository

The repository marketplace manifest is `.agents/plugins/marketplace.json`. Configure this non-default local marketplace once, then install the plugin:

```bash
codex plugin marketplace add /absolute/path/to/botrouter
codex plugin add botrouter@botrouter
```

Start a new Codex thread after installation so its skill inventory refreshes.

## Distribution

- Keep the plugin in `plugins/botrouter` and the marketplace entry in `.agents/plugins/marketplace.json`.
- Publish the repository rather than copying the plugin directory alone; the runtime and operator versions should be reviewed together.
- Validate the plugin and run the runtime tests before release.
- Do not promise that every provider is present. The doctor reports capabilities, and onboarding configures only the lanes the user chooses.
- Keep bot memories, routines, account connections, and business-specific workflows outside the plugin.

## Future remote API boundary

If remote fleet management becomes necessary, expose only read-only health, auth-presence, test, staged-deploy, and supervisor-safe activation methods. Use the existing authenticated host gateway, never expose shell, never return credential material, and keep activation separately authorized. Until then, scripts are the smaller and safer interface.
