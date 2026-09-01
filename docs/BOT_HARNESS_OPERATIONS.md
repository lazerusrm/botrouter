# Bot harness operations

This is the current operator contract for the routed Grok Bot harness. It describes the live behavior added by `xai-prompt-session.cjs`; the older custom-provider guide remains useful for rebuilding the base adapter.

## Model selection

Selections are per bot and persistent until reset. A command sent while a bot is working applies to the next user task; it does not migrate an in-flight inference response between providers.

| Command | Backend |
|---|---|
| `/model` | Show the saved selection and available commands |
| `/model auto` or `/codex` | Automatic Codex subscription routing |
| `/model grok` or `/grok` | Native Grok Bot usage |
| `/model groksub` | Separate Grok Build subscription, Grok 4.6 xhigh |
| `/groksub off\|low\|medium\|high\|xhigh` | Grok Build subscription with explicit effort |
| `/model sol-<level>` | Codex Sol; `level` is low, medium, high, xhigh, or max |
| `/model terra-<level>` | Codex Terra; same levels |
| `/model luna-<level>` | Codex Luna; same levels and always Fast |
| `/cursorsub composer-2.5 standard\|fast` | Cursor subscription, Composer 2.5 |
| `/cursorsub grok-4.6 low\|medium\|high\|xhigh standard\|fast` | Cursor subscription, Grok 4.6 |
| `/cursorsub grok-4.5 low\|medium\|high\|xhigh standard\|fast` | Cursor subscription, Grok 4.5 |
| `/model once <model>` | Use one normalized model selection for the next task |
| `/model reset` | Return to the bot's configured default |

Short aliases `/cursor`, `/cursorsub`, `/composer`, and `/composer-2.5` select Composer 2.5 Fast. Use the exact spelling `composer-2.5`; `composer2.5`, `composer 2.5`, and `composer-2.5-fast` are not command syntax.

Composer supports Standard or Fast, not Grok-style effort levels. Cursor-hosted Grok supports both effort and Standard/Fast. Grok Build and Cursor subscription usage are separate from native Grok Bot usage and from Codex usage.

## Visible model identity

The first user-visible send in a streamed response carries a model badge. Composer 2.5 Fast is `🧩C2.5F`; Standard is `🧩C2.5`. Cursor-hosted Grok is labeled with its model, effort, and optional `F`. Codex uses the Luna, Terra, or Sol family badge and effort. A generic avatar is UI chrome and is not proof of the inference backend.

For authoritative verification, inspect `/tmp/sand-host.log`. Cursor-subscription requests log the saved selection, exact `requestedModel`, and non-secret parameters, for example:

```text
[opengrok] user Cursor subscription override agent=<uuid> selection=cursorsub-composer-2.5-fast requestedModel=composer-2.5 parameters=[{"id":"fast","value":"true"}]
```

## Tools and continuation

Routing changes the inference provider, not the host tool surface. The selected model receives the native host tools available to that bot, including search, browser DOM, Computer, shell, files, MCP tools, and connected apps. Availability still depends on the bot/session configuration and authentication state.

The harness suppresses routine preliminary status sends when work remains. Tool success continues the same user turn. A successful final `send_message`, a genuine user question, or a concrete blocker terminates the turn. The final-send latch prevents a provider from resending the same completion after the delivery result, but it does not stop browser actions, Computer actions, tool retries, or ordinary model continuation before completion.

Repeated GUI observation/action cycles and repeated tool failures are bounded. These are recovery fuses, not a replacement for normal completion: the main turn retains responsibility for finishing the requested outcome whenever safe tools remain.

## Auto-review and saved helpers

Auto-review reads trusted user instructions chronologically. The newest applicable direct request governs the current turn; an older scheduled-routine restriction does not erase a newer visible instruction. Bot-to-bot `SendToAgent` calls are same-account coordination, not publication to an outside recipient. Any later external send, payment, deletion, or other consequential action is reviewed on its own merits.

A fresh request or approval for an exact outbound recipient and message is sufficient for that turn, regardless of whether the bot implements the send through an API, browser, helper, or shell wrapper. The reviewer runs at Luna medium to reduce false destination blocks. A failed approved send is retried once with the identical call; diagnostics stay read-only and separate so recovery does not create a second approval fingerprint. Different content or destinations still require their own authorization.

The shell adapter can bind a simple Python helper already stored under `/home/box` or `/workspace` into the reviewed generated-script directory. It accepts an absolute Python interpreter plus an absolute `.py` path, or `./script.py` with an allowed working directory. The resolved script must remain under an allowed root and pass the regular-file, size, and content checks. This permits known local automation helpers without weakening review for arbitrary shell commands.

## Credentials

Credential lanes remain independent:

- Codex/ChatGPT authentication: `~/.codex/auth.json` and the local Codex shim.
- Grok Build authentication: `~/.grok/auth.json`.
- Cursor subscription authentication: `~/sand-data/cursor-auth-token`.
- Native Grok Bot authentication: the host's normal credential flow.

`cursor-auth-token` must be owned by the box user and mode `0600`. Never print credentials in logs, tests, documentation, or chat. Copying an authenticated subscription token delegates that account to the box and should only be done with the account owner's authorization.

## Deployment and verification

An in-place host bundle refresh is self-healing: the home-directory watchdog
reinstalls and validates the routed runtime beside the refreshed host. A full
computer/container replacement is different. This box has no persistent Docker
mounts, so no local repository, model override, provider credential, or browser
profile is guaranteed to survive. Recovery therefore starts from the public
GitHub bootstrap and requires the account owner to repeat any provider or
website login that the platform did not restore.

The stock automation desktop may launch a 137-pixel Plank dock over the bottom
of its 1280×800 screen. That window intercepts coordinate clicks even when
Chrome is visible behind it. Disable it once per box image:

```bash
plugins/botrouter/scripts/botrouter fix-desktop --yes
```

The command makes Plank auto-hide immediately with a ten-second reveal delay,
so ordinary coordinate clicks reach the page while the desktop supervisor keeps
its expected dock process. It preserves the original wrapper at
`/usr/local/lib/botrouter/box-plank.original`.

Keep these copies identical after changing the routed session:

```text
~/grok-bot-setup/xai-prompt-session.cjs
~/.local/share/opengrok/xai-prompt-session.cjs
~/.local/share/opengrok-deploy-stage/xai-prompt-session.cjs
~/sand-host/xai-prompt-session.cjs
```

Run the complete router regression before activation:

```bash
cd ~/.local/share/opengrok
node test-auto-router-session.cjs
```

Activate through `/tmp/sand-supervisor/command.json` with a `restart` command and verify `/tmp/sand-supervisor/status.json` reports `hostRunning: true` with the command ID acknowledged. Do not launch `host-main.cjs` manually: the supervisor owns its environment, credential renewer, health state, and lifecycle.

After activation, verify all of the following:

1. The saved per-bot override under `~/sand-data/model-overrides/<agent-uuid>.json` is correct.
2. `/tmp/sand-host.log` reports the intended backend and exact model.
3. One real task uses a native tool and produces one completion message.
4. No further inference occurs after the successful final send.
5. `/tmp/sand-supervisor/status.json` remains healthy.

## Fast diagnosis

| Symptom | Check |
|---|---|
| Model command rejected | Run `/model`; then use exact syntax from the table above |
| Wrong or ambiguous badge | Verify `requestedModel` in `/tmp/sand-host.log`; badges are presentation, logs are authoritative |
| Same final answer repeats | Look for multiple successful `send_message` results in one turn and a missing `terminal Cursor SendToUser` log |
| Work stops before completion | Check whether the last send was genuinely final, `needs_input`, or a concrete blocker; progress sends must not latch completion |
| Browser/Computer loops | Inspect the agent transcript and `audit.jsonl` for repeated observations/actions and the computer recovery fuse |
| Bottom of screen does not click | Run `botrouter fix-desktop --yes`; a Plank dock may be intercepting the bottom 137 pixels |
| Auto-review contradicts a recent request | Confirm the newest direct instruction is included in trusted context; older routine constraints must not override it |
| Saved Python helper is “not bound” | Use an allowed absolute `.py` path (and optional absolute interpreter) or `./script.py` from an allowed working directory |
| Cursor subscription unavailable | Check token existence, ownership, mode `0600`, JWT shape, and expiration without printing the token |
| UI reconnects after deployment | Check supervisor status and restart through the supervisor rather than launching the host directly |
