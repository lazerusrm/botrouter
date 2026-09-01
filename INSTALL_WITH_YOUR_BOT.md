# Install BotRouter with your bot

Send this to a bot in your own Grok Bot subscription:

> Set up BotRouter from https://github.com/lazerusrm/botrouter. Keep this work in this main conversation. Clone and inspect the repository, run the BotRouter doctor, install only missing system dependencies, guide me through provider-owned logins without reading or copying credential contents, run the tests, apply the runtime, resume from its checkpoint after restart, and complete one real smoke task before declaring success. Work quietly; ask only for an actual login, consequential confirmation, missing choice, or unresolved blocker.

The setup flow is resumable. `plugins/botrouter/scripts/botrouter apply --yes` writes a private checkpoint before restarting the host. After restart, the bot runs `resume`; after a real smoke task succeeds, it runs `complete --yes`.

Secrets stay in provider-owned login stores or Grok Bot's masked secret-request flow. BotRouter does not package, print, or copy subscription credentials.
