# Auto-review classifier contract

BotRouter keeps Grok Bot's native Auto-review boundary. It changes the first
classifier transport, not the meaning of authorization, approval cards, or
tool execution.

## Inputs and trust

Every decision receives Grok Bot's unchanged system policy, native risk target,
conversation context, standing Auto Run rules, attempt index, and mode.

- Direct user messages and user-form answers are trusted instructions.
- A scheduled routine is trusted only when Grok Bot marks it as user-authored.
  In stored `automation.json`, that is `provenance: "user"`.
- Hidden prompts without the trusted-automation marker, assistant narration,
  tool output, webpages, documents, and messages from other parties are
  evidence, not authorization.
- Standing allow rules authorize only their stated action and destination.
  Standing block rules always win.

An agent-created routine normally has `provenance: "untrusted"`. Do not change
that automatically. It may be promoted only after the user directly confirms
the routine's exact actions and scope.

## Decision flow

1. Grok Bot extracts and bounds the trusted context and builds the exact native
   risk target.
2. Codex Luna-low classifies the call through the local authenticated shim.
3. A schema-valid Codex `ALLOW` proceeds through Grok Bot's normal executor.
4. A Codex `BLOCK` is sent to Grok Bot's original stock classifier with the
   same arguments. The stock result adjudicates the disputed call.
5. A Codex transport, timeout, malformed-output, or validation failure also
   falls back to the stock classifier.
6. If stock adjudication of a valid Codex block fails, the Codex block is
   preserved. If both classifiers fail, Grok Bot's native retry/manual
   fail-closed behavior remains authoritative.

This is intentionally asymmetric. Stock can remove a Codex false-positive
block, but a classifier outage cannot turn a blocked action into an automatic
execution.

## Verified stock implementation

The installed Grok Bot build `cf33483` contains a readable bundled host with
original module paths, but no host source map or separate TypeScript sources.
Its pre-patch backup confirms that the stock classifier is one authenticated
`ClassifySandAutoReview` RPC. The box sends the native risk target, bounded
conversation context, parent conversation ID, attempt index, and mode. Cursor's
backend owns the stock prompt and model policy, so the stock model name and
server implementation cannot be recovered from the box.

The local bundle does expose the surrounding contract:

- Context is capped at four assistant messages, two trusted user messages, two
  form-answer messages, and 4,000 characters per message. Current-intent
  Computer call summaries are also included.
- Hidden messages are excluded unless they carry the trusted-automation marker.
  Bot memory is not an authorization source.
- The policy recognizes only five reasons to block: an unauthorized outbound
  or binding effect, unauthorized data or credential exfiltration, unauthorized
  destructive data loss, unauthorized host compromise or persistence, or a
  matching trusted block instruction. Uncertainty and task mismatch alone are
  instructed to allow.
- Personal, user, and project Auto Run rules are merged and de-duplicated.
  Matching block rules override allow rules.
- Screenshot, move, wait, and scroll Computer actions bypass model review.
  Click and drag require a declared purpose. Mutating Computer targets are
  fingerprinted with the exact action, declared purpose, box generation, and
  display identity; the display identity is checked again before execution.
- A classifier failure becomes a manual-review rejection. A valid block can
  become a native approval card; cards are exact-fingerprint, one-shot
  decisions, and a new user-message epoch retires stale pending cards.
- Routine writes originating in a visible turn or handoff-resume are stored as
  user provenance. Other origins are untrusted unless the user later confirms
  and promotes that exact routine.

These are implementation details, not a stable public API. Re-audit the bundle
after a Grok Bot host update and keep the injector fail-closed when an expected
anchor or contract changes.

## Approvals and batches

Grok Bot still owns approval cards, reviewed-target fingerprints, and
Approve/Deny/Always decisions. BotRouter never fabricates approval state.

A batch may contain many native tool calls. Each call is still classified, but
the same current trusted instruction or matching standing rule should authorize
every call within its scope without one card per item. A one-time approval is
bound to the exact reviewed call. Use an explicit batch instruction or a
carefully scoped Always rule when future calls of that kind should auto-run;
never reuse one approval across changed recipients, destinations, or effects.

## Integration rules

- Reuse Grok Bot's context extractor and risk-target builders. Do not rebuild
  authorization from the visible transcript alone.
- Pass the original serialized arguments to both classifiers.
- Never log proposed arguments, message bodies, credentials, or tokens.
- Keep Abort authoritative and preserve the native fail-closed path.
- Test four paths: Codex allow, Codex block/stock allow, both block, and
  classifier failure.
- A live proof must use a harmless proposed or reversible action and confirm
  the native audit decision without bypassing the approval UI.
