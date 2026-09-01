---
name: botrouter
description: Install, authenticate, diagnose, test, deploy, or recover the BotRouter harness. Use for routed-bot setup, provider login/status, model-router health, browser/DOM/Computer readiness, SSH readiness, supervisor-safe activation, or sharing the harness with another operator.
---

# BotRouter

Use the bundled `scripts/botrouter` as the stable entrypoint. Resolve it relative to this skill as `../../scripts/botrouter`.

## Operating contract

1. Run `doctor` first. It is read-only, verifies required commands including SSH, and never prints credential contents.
2. If the runtime is absent, explain that `install-runtime` clones the public repository, then run it only when installation is within the user's request.
3. Use `auth-status` to identify missing provider-owned login. Use `login codex`, `login grok`, or `login claude` to launch that provider's normal interactive flow. Never copy an auth file or subscription token between people, account homes, or machines.
4. For API-key providers, run `configure <provider>` and let the existing adapters CLI prompt privately. Never put a key in command arguments, chat, logs, or committed files.
5. Run `test` after setup or changes. Use `apply --yes` only when the user asked to deploy/activate and a host restart is acceptable. It writes a durable checkpoint before restart.
6. After restart, run `resume`, verify one real task through the target bot, then run `complete --yes`.

Keep the setup in this main conversation. Do not delegate onboarding to another bot: the main thread owns the user's choices, login handoffs, and completion check.

Routine recoverable errors belong in diagnostics, not chat. Continue automatically when a safe alternate path remains. Interrupt the user only for an interactive login, a consequential confirmation, a missing choice that changes the setup, or a blocker that remains after recovery.

## Commands

```bash
../../scripts/botrouter doctor
../../scripts/botrouter auth-status
../../scripts/botrouter install-system-deps
../../scripts/botrouter install-runtime
../../scripts/botrouter login codex|grok|claude
../../scripts/botrouter configure <provider>
../../scripts/botrouter test
../../scripts/botrouter apply --yes
../../scripts/botrouter resume
../../scripts/botrouter complete --yes
```

`GROK_BOT_SETUP_ROOT` overrides runtime discovery. Without it, the wrapper checks its source repository, `~/grok-bot-setup`, and `/workspace/setup`.

## Security boundary

- Credential presence and file mode may be inspected; credential contents may not.
- Subscription authentication is local delegation by that account owner, not a portable plugin secret.
- Bind proxies to loopback unless the user explicitly configures a protected private network.
- Never start `host-main.cjs` manually. Activation must remain supervisor-owned through the existing adapters CLI.
- Do not weaken Auto-review to make onboarding pass. Fix tool shape, authentication, or trusted context instead.

Detailed architecture and distribution guidance lives in the repository's `docs/SHAREABLE_OPERATOR_PLUGIN.md`.
