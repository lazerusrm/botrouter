# BotRouter plugin

BotRouter turns the existing routed-bot runtime into a guided, repeatable operator workflow. It does not contain or distribute credentials and does not reimplement the runtime.

The bundled skill runs a read-only doctor, launches provider-owned login flows, delegates private provider configuration to `adapters.sh`, runs regressions, and activates through the existing recovery/supervisor path.

See [`docs/SHAREABLE_OPERATOR_PLUGIN.md`](../../docs/SHAREABLE_OPERATOR_PLUGIN.md) for architecture, installation, authentication boundaries, and release guidance.
