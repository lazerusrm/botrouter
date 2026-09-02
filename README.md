# BotRouter

BotRouter gives Grok Bot a reliable way to use different AI subscriptions and
models without losing its normal tools. It keeps browser control, Computer,
search, shell, connected apps, memory, approvals, and long-running work in the
same conversation.

[![CI](https://img.shields.io/github/actions/workflow/status/lazerusrm/botrouter/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/lazerusrm/botrouter/actions/workflows/ci.yml)
[![license](https://img.shields.io/npm/l/grok-bot-setup?style=flat-square&color=green)](LICENSE)
[![GitHub](https://img.shields.io/github/stars/lazerusrm/botrouter?style=flat-square&logo=github)](https://github.com/lazerusrm/botrouter)

## The easy way

If you use Grok Bot on Windows, you do **not** need to install Linux tools in
PowerShell. BotRouter runs inside the computer provided to your bot.

Open the Grok Bot conversation you want to configure and paste this:

> Set up BotRouter from https://github.com/lazerusrm/botrouter. Keep the setup in this main conversation and do the work for me. Check the repository before running it, install only what is missing, guide me through any account logins without exposing my passwords or tokens, run the tests, apply the setup, resume after any restart, and finish one real browser or tool smoke test before saying it is done. Work quietly and only interrupt me for a login, an important confirmation, a choice you genuinely need, or a blocker you cannot fix.

The bot should handle the terminal work. You may see a login page or a masked
secret card when a provider needs your account. Complete that step yourself,
then tell the bot to continue.

If the Grok Bot computer reconnects during setup, return to the same
conversation and say:

> Resume the BotRouter setup and finish the smoke test.

That is usually all you need.

## What setup changes

BotRouter:

- lets each bot use Codex, native Grok Bot, Grok Build, Cursor, or automatic routing;
- keeps native browser DOM, Computer, search, shell, files, and connected-app tools available;
- silently retries short provider failures instead of filling chat with errors;
- keeps working until the requested outcome is complete;
- uses the existing Grok Bot approval and masked-secret interfaces;
- fixes the desktop dock that can block clicks near the bottom of the screen.

It does not copy account credentials into this repository. Provider logins stay
in their own local credential stores on the Grok Bot computer.

## Choosing a model

Send these commands directly to the configured bot:

| Command | Result |
|---|---|
| `/model` | Show the current model and available choices |
| `/model auto` | Let BotRouter choose a Codex model |
| `/model grok` | Use native Grok Bot |
| `/model luna-medium` | Use Codex Luna at medium effort |
| `/model terra-high` | Use Codex Terra at high effort |
| `/model sol-xhigh` | Use Codex Sol at xhigh effort |
| `/groksub high` | Use Grok Build with high thinking |
| `/cursorsub composer-2.5 fast` | Use Cursor Composer 2.5 Fast |
| `/model reset` | Return to that bot's configured default |

Luna always uses Fast mode. A model change made while the bot is already
working applies to its next task; it does not move a half-finished response to a
different provider.

## If you prefer a terminal

Run these commands **inside the Grok Bot Linux computer**, not in Windows
PowerShell:

```bash
git clone https://github.com/lazerusrm/botrouter.git ~/botrouter
cd ~/botrouter
plugins/botrouter/scripts/botrouter doctor
plugins/botrouter/scripts/botrouter test
plugins/botrouter/scripts/botrouter apply --yes
```

After the Grok Bot computer reconnects:

```bash
cd ~/botrouter
plugins/botrouter/scripts/botrouter resume
```

Run one real task through the bot. When it succeeds:

```bash
plugins/botrouter/scripts/botrouter complete --yes
```

The setup checkpoint is deliberately kept until that real smoke test succeeds.
A restart by itself is not treated as completion.

## After a Grok Bot computer reset

Ask the same bot:

> Recover BotRouter from https://github.com/lazerusrm/botrouter, resume the existing setup, and verify it with one real tool task.

Or run this inside the bot's Linux terminal:

```bash
git clone https://github.com/lazerusrm/botrouter.git ~/botrouter
cd ~/botrouter
./scripts/bootstrap.sh
```

### What survives an update?

There are two kinds of updates:

| Update | What happens |
|---|---|
| Grok Bot refreshes its host software inside the same computer | BotRouter's watchdog restores the routing modules and host hooks automatically. Your local logins and browser profile remain. |
| Grok Bot replaces the entire computer | The current computer has no persistent disk mount, so no local file is guaranteed to survive. The GitHub repository remains available and the bootstrap command rebuilds the non-secret setup. |

After a full replacement, expect to sign in to Codex, Grok Build, Cursor, and
websites again. BotRouter deliberately does not upload those credentials or
browser cookies somewhere else. Per-bot model overrides stored on the old
computer also need to be selected again with `/model`.

The practical recovery anchor is this GitHub repository plus the original Grok
Bot conversation and memory. Ask the bot to run the recovery prompt above; the
bootstrap now reapplies the host routing, Computer/browser fixes, provider
adapters, and any user-level desktop fix it can perform without administrator
access.

## Common problems

| What you see | What to do |
|---|---|
| `/model` does not show choices | Ask the bot to run the BotRouter doctor and recover the host |
| The bot cannot click near the bottom of the screen | Run `plugins/botrouter/scripts/botrouter fix-desktop --yes` inside the bot computer |
| The bot says SSH is missing | Run `plugins/botrouter/scripts/botrouter install-system-deps` with administrator access |
| Setup stopped after a restart | Return to the same conversation and say “Resume the BotRouter setup” |
| A provider asks for authentication | Complete its official login or masked secret card; never paste credentials into ordinary chat |
| The bot reports a transient provider error | Ask it to continue once; BotRouter normally retries these internally |

## Technical notes

The public npm command remains `grok-bot-setup` for compatibility, but the
GitHub workflow above is the recommended installation path for current Grok Bot
computers.

- [Model, tool, approval, and recovery operations](docs/BOT_HARNESS_OPERATIONS.md)
- [Reusable Auto-review classifier contract](docs/AUTO_REVIEW.md)
- [Plugin and distribution design](docs/SHAREABLE_OPERATOR_PLUGIN.md)
- [Detailed adapter reference](docs/GUIDE_CUSTOM_INFERENCE.md)
- [Install using your own bot](INSTALL_WITH_YOUR_BOT.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

BotRouter is MIT licensed. Issues and pull requests are welcome.
