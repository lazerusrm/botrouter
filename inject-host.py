#!/usr/bin/env python3
"""Fail-closed opengrok host hook with native stock fallback. Idempotent."""
from __future__ import annotations

import os
import re
import pathlib
import shutil
import sys

HOST_MAIN = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/box/sand-host/host-main.cjs")
BACKUP = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/home/box/sand-host/host-main.cjs.cursor-bak")

REQUESTED_MODEL_BLOCK = """      const requestedModel = resolveSandRequestedModel({
        sessionOptions,
        envModelOverride: process.env.SAND_AGENT_MODEL,
        storedDefaultModel: options2.getDefaultModel?.(),
        storedComputerUseModel: options2.getComputerUseModel?.(),
        storedBrowserUseModel: options2.getBrowserUseModel?.(),
        experimentModelOverride
      });
"""

STOCK_SESSION_BLOCK = """      const session = createCursorInferencePromptSession({
        getAccessToken: options2.getAccessToken,
        getTeamId: options2.getTeamId,
        getMachineId: options2.getMachineId,
        requestedModel,
        inferenceReason: options2.isGeminiVideoDeveloperApiEnabled?.() === true ? sessionOptions?.inferenceReason : void 0,
        onRequestId,
        ...sessionOptions?.lineage != null ? { lineage: sessionOptions.lineage } : {}
      });"""

SESSION_NEEDLE = REQUESTED_MODEL_BLOCK + STOCK_SESSION_BLOCK

LEGACY_SESSION_BLOCK = REQUESTED_MODEL_BLOCK + """      try {
        const { createRoutedPromptSession, createXaiPromptSession } = require("./xai-prompt-session.cjs");
        const routed = createRoutedPromptSession({
          requestedModel,
          onRequestId,
          sessionOptions
        });
        if (routed) return routed;
      } catch (hopErr) {
        console.error("[opengrok] hop route failed, using stock Grok:", hopErr);
      }
""" + STOCK_SESSION_BLOCK

SESSION_HOOK = REQUESTED_MODEL_BLOCK + """      const createStockSession = (stockRequestedModel = requestedModel, stockAccessToken = void 0) => createCursorInferencePromptSession({
        getAccessToken: stockAccessToken ? async () => stockAccessToken : options2.getAccessToken,
        getTeamId: options2.getTeamId,
        getMachineId: options2.getMachineId,
        requestedModel: stockRequestedModel === requestedModel ? requestedModel : new requestedModel.constructor(stockRequestedModel),
        inferenceReason: options2.isGeminiVideoDeveloperApiEnabled?.() === true ? sessionOptions?.inferenceReason : void 0,
        onRequestId,
        ...sessionOptions?.lineage != null ? { lineage: sessionOptions.lineage } : {}
      });
      try {
        const { createRoutedComputerUseSession } = require("./codex-computer-session.cjs");
        const computerRouted = createRoutedComputerUseSession({
          requestedModel,
          onRequestId,
          sessionOptions,
          createStockSession
        });
        if (computerRouted) return computerRouted;
      } catch (computerHopErr) {
        console.error("[opengrok:computer] adapter failed before selection, using stock Grok:", computerHopErr);
      }
      try {
        const { createRoutedPromptSession } = require("./xai-prompt-session.cjs");
        const routed = createRoutedPromptSession({
          requestedModel,
          onRequestId,
          sessionOptions,
          createStockSession
        });
        if (routed) return routed;
      } catch (hopErr) {
        console.error("[opengrok] hop route failed, using stock Grok:", hopErr);
      }
      const session = createStockSession();"""

LEGACY_STOCK_FACTORY = """      const createStockSession = () => createCursorInferencePromptSession({
        getAccessToken: options2.getAccessToken,
        getTeamId: options2.getTeamId,
        getMachineId: options2.getMachineId,
        requestedModel,"""

OVERRIDABLE_STOCK_FACTORY = """      const createStockSession = (stockRequestedModel = requestedModel, stockAccessToken = void 0) => createCursorInferencePromptSession({
        getAccessToken: stockAccessToken ? async () => stockAccessToken : options2.getAccessToken,
        getTeamId: options2.getTeamId,
        getMachineId: options2.getMachineId,
        requestedModel: stockRequestedModel === requestedModel ? requestedModel : new requestedModel.constructor(stockRequestedModel),"""

MODEL_ONLY_STOCK_FACTORY = """      const createStockSession = (stockRequestedModel = requestedModel) => createCursorInferencePromptSession({
        getAccessToken: options2.getAccessToken,
        getTeamId: options2.getTeamId,
        getMachineId: options2.getMachineId,
        requestedModel: stockRequestedModel,"""

AUTH_STOCK_FACTORY = """      const createStockSession = (stockRequestedModel = requestedModel, stockAccessToken = void 0) => createCursorInferencePromptSession({
        getAccessToken: stockAccessToken ? async () => stockAccessToken : options2.getAccessToken,
        getTeamId: options2.getTeamId,
        getMachineId: options2.getMachineId,
        requestedModel: stockRequestedModel,"""

ROUTED_MAIN_WITHOUT_STOCK = """        const routed = createRoutedPromptSession({
          requestedModel,
          onRequestId,
          sessionOptions
        });"""

ROUTED_MAIN_WITH_STOCK = """        const routed = createRoutedPromptSession({
          requestedModel,
          onRequestId,
          sessionOptions,
          createStockSession
        });"""

AGENT_NEEDLE = """        const mainSessionOptions = {
          modelId: host.subagentModelId,"""

AGENT_HOOK = """        const mainSessionOptions = {
          agentId: typeof host.getConversationId === "function" ? host.getConversationId() : void 0,
          modelId: host.subagentModelId,"""

RETURN_NEEDLE = """      return session;
    },
    recordPostTurnLabeling(args) {"""

RETURN_HOOK = """      try {
        const { withModelBadge, stockBadgeForSession } = require("./xai-prompt-session.cjs");
        const badge = stockBadgeForSession(sessionOptions);
        if (badge) return withModelBadge(session, badge);
      } catch (badgeErr) {
        console.error("[opengrok] stock badge failed:", badgeErr);
      }
      return session;
    },
    recordPostTurnLabeling(args) {"""

AUTO_REVIEW_NEEDLE = """function createSandBackendSmartModeClassifierExecutor(options2, client = createSandCursorBackendClient(DashboardService, options2)) {
  return {
    async execute(ctx, args) {
      const attemptIndex = ctx.get(smartModeClassifierAttemptIndexKey);
      const mode = ctx.get(smartModeClassifierModeKey) ?? "enforce";
      const response = await client.classifySandAutoReview(
        new ClassifySandAutoReviewRequest({
          args: new SmartModeClassifierArgs({
            target: args.target,
            conversationContext: args.conversationContext,
            parentConversationId: args.parentConversationId
          }),
          attemptIndex,
          mode
        }),
        { signal: ctx.signal }
      );
      if (response.result === void 0) {
        throw new SandSmartModeClassifierError("ClassifySandAutoReview returned no result");
      }
      return response.result;
    }
  };
}"""

AUTO_REVIEW_HOOK = """function createSandBackendSmartModeClassifierExecutor(options2, client = createSandCursorBackendClient(DashboardService, options2)) {
  return {
    async execute(ctx, args) {
      const attemptIndex = ctx.get(smartModeClassifierAttemptIndexKey);
      const mode = ctx.get(smartModeClassifierModeKey) ?? "enforce";
      try {
        const { classify: createCodexAutoReviewClassifier } = require("./codex-auto-review.cjs");
        const serializedArgs = typeof args.toJson === "function" ? args.toJson({ emitDefaultValues: true }) : JSON.parse(JSON.stringify(args));
        const classified = await createCodexAutoReviewClassifier({
          systemPrompt: SAND_AUTO_REVIEW_CLASSIFIER_SYSTEM_PROMPT,
          args: serializedArgs,
          attemptIndex,
          mode,
          timeoutMs: 12_000,
          fallbackToHost: true,
          signal: ctx.signal
        });
        const value = new SmartModeClassifierSuccess({
          decision: classified.decision === "ALLOW" ? SmartModeClassifierDecision.ALLOW : SmartModeClassifierDecision.BLOCK,
          ...classified.decision === "BLOCK" ? {
            blockReason: classified.reason,
            ...classified.proposedAllowRule ? { proposedAllowRule: classified.proposedAllowRule } : {}
          } : {}
        });
        return new SmartModeClassifierResult({ result: { case: "success", value } });
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") throw error;
        console.error(`[opengrok:auto-review] Codex classifier failed; using stock classifier error=${error instanceof Error ? error.name : "Error"}`);
        try {
          const response = await client.classifySandAutoReview(
            new ClassifySandAutoReviewRequest({
              args: new SmartModeClassifierArgs({
                target: args.target,
                conversationContext: args.conversationContext,
                parentConversationId: args.parentConversationId
              }),
              attemptIndex,
              mode
            }),
            { signal: ctx.signal }
          );
          if (response.result === void 0) {
            throw new Error("stock classifier returned no result");
          }
          return response.result;
        } catch (fallbackError) {
          if (fallbackError instanceof Error && fallbackError.name === "AbortError") throw fallbackError;
          throw new SandSmartModeClassifierError("Codex and stock Auto-review classifiers failed");
        }
      }
    }
  };
}"""

# An already-injected bundle keeps whatever argument list its injector wrote.
# Upgrade it to exactly what a fresh injection produces so both paths converge.
AUTO_REVIEW_CALL_HOOK = """          mode,
          timeoutMs: 12_000,
          fallbackToHost: true,
          signal: ctx.signal
        });"""
AUTO_REVIEW_CALL_LEGACY = (
    """          mode,
          signal: ctx.signal
        });""",
    """          mode,
          timeoutMs: 8_000,
          fallbackToHost: true,
          signal: ctx.signal
        });""",
)
AUTO_REVIEW_TIMEOUT_NEEDLE = "var SAND_AUTO_REVIEW_CLASSIFIER_TIMEOUT_MS = 15e3;"
AUTO_REVIEW_TIMEOUT_LEGACY_HOOK = "var SAND_AUTO_REVIEW_CLASSIFIER_TIMEOUT_MS = 30e3;"
AUTO_REVIEW_TIMEOUT_HOOK = "var SAND_AUTO_REVIEW_CLASSIFIER_TIMEOUT_MS = 80e3;"
SMART_MODE_TIMEOUT_NEEDLE = "var SMART_MODE_CLASSIFIER_TIMEOUT_MS = 1e4;"
SMART_MODE_TIMEOUT_HOOK = "var SMART_MODE_CLASSIFIER_TIMEOUT_MS = 80e3;"

APPROVAL_EXPIRY_POLICY_NEEDLE = """function sandAutoReviewApprovalExpiryPolicy(source) {
  return source === "turn" || source === "handoff-resume" ? "park" : "ttl";
}"""

APPROVAL_EXPIRY_POLICY_HOOK = """function sandAutoReviewApprovalExpiryPolicy(source) {
  return "park";
}"""

BROWSER_CLOSE_VIEW_NEEDLE = """      const currentTarget = state.lastViewId !== undefined ? state.views[state.lastViewId] : undefined;"""

BROWSER_FIRST_VIEW_NEEDLE_TABS = (
    '} else {\n'
    '\t\t\tconst lastTarget = state.lastViewId !== undefined ? state.views[state.lastViewId] : undefined;\n'
    '\t\t\tpage = lastTarget !== undefined ? byTarget.get(lastTarget) : undefined;\n'
    '\t\t\tif (page === undefined) {\n'
    '\t\t\t\tconst pages = [...byTarget.values()];\n'
    '\t\t\t\tpage = pages.filter((p) => p.url() !== "about:blank").pop() ?? pages[pages.length - 1];\n'
    '\t\t\t}\n'
    '\t\t}'
)
BROWSER_FIRST_VIEW_HOOK_TABS = (
    '} else {\n'
    '\t\t\tconst pages = [...byTarget.values()];\n'
    '\t\t\tconst visibility = await Promise.all(\n'
    '\t\t\t\tpages.map(async (candidate) => {\n'
    '\t\t\t\t\ttry {\n'
    '\t\t\t\t\t\treturn await candidate.evaluate(() => document.visibilityState);\n'
    '\t\t\t\t\t} catch {\n'
    '\t\t\t\t\t\treturn undefined;\n'
    '\t\t\t\t\t}\n'
    '\t\t\t\t}),\n'
    '\t\t\t);\n'
    '\t\t\tconst visibleIndex = visibility.indexOf("visible");\n'
    '\t\t\tpage = visibleIndex >= 0 ? pages[visibleIndex] : undefined;\n'
    '\t\t\tif (page === undefined) {\n'
    '\t\t\t\tconst lastTarget = state.lastViewId !== undefined ? state.views[state.lastViewId] : undefined;\n'
    '\t\t\t\tpage = lastTarget !== undefined ? byTarget.get(lastTarget) : undefined;\n'
    '\t\t\t}\n'
    '\t\t\tpage ??= pages.filter((p) => p.url() !== "about:blank").pop() ?? pages[pages.length - 1];\n'
    '\t\t}'
)

# The 2026-08-30 bundle reformatted the browser tool module to tabs and wrapped
# this assignment across two lines. Same logic, different whitespace.
BROWSER_CLOSE_VIEW_NEEDLE_TABS = (
    "\t\t\tconst currentTarget =\n"
    "\t\t\t\tstate.lastViewId !== undefined ? state.views[state.lastViewId] : undefined;"
)
# Emitted on one line so the ensure/watchdog/audit greps keep matching.
BROWSER_CLOSE_VIEW_HOOK_TABS = (
    "\t\t\tconst currentViewId = typeof request.viewId === \"string\" && request.viewId.length > 0 ? request.viewId : state.lastViewId;\n"
    "\t\t\tconst currentTarget = currentViewId !== undefined ? state.views[currentViewId] : undefined;"
)
BROWSER_CLOSE_VIEW_HOOK = """      const currentViewId = typeof request.viewId === "string" && request.viewId.length > 0 ? request.viewId : state.lastViewId;
      const currentTarget = currentViewId !== undefined ? state.views[currentViewId] : undefined;"""

BROWSER_FIRST_VIEW_NEEDLE = """    } else {
      const lastTarget =
        state.lastViewId !== undefined ? state.views[state.lastViewId] : undefined;
      page = lastTarget !== undefined ? byTarget.get(lastTarget) : undefined;
      if (page === undefined) {
        const pages = [...byTarget.values()];
        page = pages.filter((p) => p.url() !== "about:blank").pop() ?? pages[pages.length - 1];
      }
    }"""

BROWSER_FIRST_VIEW_HOOK = """    } else {
      const pages = [...byTarget.values()];
      const visibility = await Promise.all(
        pages.map(async (candidate) => {
          try {
            return await candidate.evaluate(() => document.visibilityState);
          } catch {
            return undefined;
          }
        })
      );
      const visibleIndex = visibility.indexOf("visible");
      page = visibleIndex >= 0 ? pages[visibleIndex] : undefined;
      if (page === undefined) {
        const lastTarget =
          state.lastViewId !== undefined ? state.views[state.lastViewId] : undefined;
        page = lastTarget !== undefined ? byTarget.get(lastTarget) : undefined;
      }
      page ??= pages.filter((p) => p.url() !== "about:blank").pop() ?? pages[pages.length - 1];
    }"""

DIRECT_BROWSER_TOOLS_NEEDLE = """  if (host.isBrowserUseSubagent && host.remoteBoxHasDesktop && host.getRemoteBoxAvailable()) {"""
DIRECT_BROWSER_TOOLS_TRANSIENT_HOOK = """  const opengrokDirectBrowserMain = process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && !host.isSubagentRunner && host.gates.browserUseSubagent();
  if ((host.isBrowserUseSubagent || opengrokDirectBrowserMain) && host.remoteBoxHasDesktop && host.getRemoteBoxAvailable()) {"""
DIRECT_BROWSER_TOOLS_GATED_HOOK = """  const opengrokDirectBrowserMain = process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && !host.isSubagentRunner && host.gates.browserUseSubagent();
  if (host.remoteBoxHasDesktop && (opengrokDirectBrowserMain || (host.isBrowserUseSubagent && host.getRemoteBoxAvailable()))) {"""
DIRECT_BROWSER_TOOLS_HOOK = """  const opengrokDirectBrowserMain = process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && !host.isSubagentRunner;
  if (host.remoteBoxHasDesktop && (opengrokDirectBrowserMain || (host.isBrowserUseSubagent && host.getRemoteBoxAvailable()))) {"""

DIRECT_COMPUTER_TOOLS_NEEDLE = """  if (host.isComputerUseSubagent && host.remoteBoxHasDesktop && host.getRemoteBoxAvailable()) {"""
DIRECT_COMPUTER_TOOLS_HOOK = """  if (host.remoteBoxHasDesktop && (!host.isSubagentRunner && process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" || host.isComputerUseSubagent && host.getRemoteBoxAvailable())) {"""

COMPUTER_REVIEW_CDP_NEEDLE = """  } catch {
    throw new SandComputerAutoReviewBlockedError(
      "Computer Auto-review could not capture the current page state."
    );
  }
  if (result.result.case !== "success") {"""
COMPUTER_REVIEW_CDP_HOOK = """  } catch {
    return SAND_COMPUTER_PAGE_STATE_CHROME_UNREACHABLE;
  }
  if (result.result.case !== "success") {"""

DIRECT_GUI_TASKS_STOCK_NEEDLE = """      subagentConfigs.push(createSandComputerUseSubagentConfig({ browserUseOffered }));
      if (browserUseOffered) {
        subagentConfigs.push(createSandBrowserUseSubagentConfig());
      }"""
DIRECT_GUI_TASKS_LEGACY_HOOK = """      subagentConfigs.push(createSandComputerUseSubagentConfig({ browserUseOffered }));
      if (browserUseOffered && process.env.OPENGROK_DIRECT_BROWSER_MAIN === "0") {
        subagentConfigs.push(createSandBrowserUseSubagentConfig());
      }"""
DIRECT_GUI_TASKS_HOOK = """      if (process.env.OPENGROK_DIRECT_BROWSER_MAIN === "0") {
        subagentConfigs.push(createSandComputerUseSubagentConfig({ browserUseOffered }));
        if (browserUseOffered) subagentConfigs.push(createSandBrowserUseSubagentConfig());
      }"""

DIRECT_MAIN_TASKS_NEEDLE = """    if (subagentConfigs != null && !host.isSystemPromptOverridden) {
      const generalPurposeIndex = subagentConfigs.findIndex(
        (config3) => getSubagentTypeName(config3.subagent_type) === GENERAL_PURPOSE_SUBAGENT_TYPE
      );
      if (generalPurposeIndex >= 0) {
        subagentConfigs.splice(generalPurposeIndex, 1, createSandExecutorSubagentConfig());
      } else {
        subagentConfigs.push(createSandExecutorSubagentConfig());
      }
    }"""
DIRECT_MAIN_TASKS_HOOK = DIRECT_MAIN_TASKS_NEEDLE + """
    if (subagentConfigs != null && !host.isSubagentRunner && process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0") {
      subagentConfigs.length = 0;
    }"""

# Clearing the configuration array is not enough: buildTurnTools used to test
# only for a non-null array, so it still registered Task and agent-management
# tools with an empty subagent_type enum.  Calls then failed native schema
# validation before Auto-review, which looked like a safety rejection but could
# never create an approval card.  Direct mode must omit those tools entirely.
DIRECT_TASK_TOOLS_GATE_NEEDLE = """  if (hasParentToolParity && subagentConfigs != null) {"""
DIRECT_TASK_TOOLS_GATE_HOOK = """  if (hasParentToolParity && subagentConfigs != null && subagentConfigs.length > 0) {"""

DIRECT_BROWSER_PROMPT_NEEDLE = """    if (host.isBrowserUseSubagent) {
      return ["""
DIRECT_BROWSER_PROMPT_BAD_GUARD = """    if (!host.isSubagentRunner && process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && host.gates.browserUseSubagent() && host.remoteBoxHasDesktop && host.getRemoteBoxAvailable()) {"""
DIRECT_BROWSER_PROMPT_GATED_GUARD = """    if (!host.isSubagentRunner && process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && host.gates.browserUseSubagent() && host.remoteBoxHasDesktop) {"""
DIRECT_BROWSER_PROMPT_GUARD = """    if (!host.isSubagentRunner && process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && host.remoteBoxHasDesktop) {"""
DIRECT_BROWSER_PROMPT_LEGACY_HOOK = """    if (!host.isSubagentRunner && process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && host.remoteBoxHasDesktop) {
      return [
        "## The box browser and desktop",
        "Use the browser_* DOM tools in this main turn directly; do not launch a browserUse Task. They operate the box's persistent signed-in Chrome while this conversation keeps its full profile, memory, history, approvals, and final response.",
        "- Use browser_snapshot when you need current DOM refs, then act on those refs. Every browser action already returns fresh page state and a screenshot, so do not add redundant screenshots or waits.",
        "- Take the shortest route: use browser_navigate for a known URL, newTab:true only when a separate tab is needed, browser_fill for exact field values, and browser_type with submit:true only when Enter is intentionally the complete action.",
        "- Omit viewId for the normal single-tab workflow. Use browser_tabs and explicit viewId only for a real multi-page task; never close a tab whose purpose or unsaved state is uncertain.",
        "- Keep browser actions sequential because refs and Auto-review bind to the current page state. Native Auto-review remains authoritative: a blocked or approval-pending action has not run.",
        "- Launch one computerUse Task only for the desktop itself, file dialogs, pixel-only GUI work, or a site the DOM tools explicitly cannot operate. Do not use it for an ordinary web form.",
        "- For login, SSO, passkey, 2FA, CAPTCHA, or payment authentication, call request_box_help directly with one short instruction. For ordinary page fields use the native browser tools; never inspect cookies, tokens, hidden credentials, or unrelated account data.",
        "- Move bulk structured data through a file/import when the site supports it. Otherwise continue directly in this turn until the requested browser work is complete or a concrete blocker requires the user.",
        "- Send one concise final result with the successful browser tool call ids as evidence; do not narrate routine progress."
      ].join("\\n");
    }
    if (host.isBrowserUseSubagent) {
      return ["""
DIRECT_BROWSER_PROMPT_GUI_ONLY_HOOK = DIRECT_BROWSER_PROMPT_LEGACY_HOOK.replace(
    "- Launch one computerUse Task only for the desktop itself, file dialogs, pixel-only GUI work, or a site the DOM tools explicitly cannot operate. Do not use it for an ordinary web form.",
    "- Use Computer directly in this main turn for the desktop, file dialogs, pixel-only GUI work, or a site the DOM tools explicitly cannot operate. Do not launch a browserUse or computerUse Task; keep the visible conversation's context and verify each returned screen.",
)
DIRECT_BROWSER_PROMPT_CONTEXT_LEGACY_HOOK = DIRECT_BROWSER_PROMPT_GUI_ONLY_HOOK.replace(
    "Use the browser_* DOM tools in this main turn directly; do not launch a browserUse Task.",
    "Use the browser_* DOM tools in this main turn directly; do not launch a Task subagent.",
).replace(
    "Do not launch a browserUse or computerUse Task; keep the visible conversation's context and verify each returned screen.",
    "Do not launch any Task subagent; keep the visible conversation's full context and verify each returned screen.",
)
DIRECT_BROWSER_PROMPT_VOCAB_GATED_HOOK = DIRECT_BROWSER_PROMPT_CONTEXT_LEGACY_HOOK.replace(
    "Use the browser_* DOM tools in this main turn directly; do not launch a Task subagent.",
    "Use the browser_* DOM tools in this main turn directly when the request explicitly requires the web UI; do not launch a Task subagent. Browser and Computer are capabilities, not the default: when memory or the request names an established API, CLI, connector, or saved helper, use that native path first and do not open the browser merely because it is available.",
)
DIRECT_BROWSER_PROMPT_HOOK = DIRECT_BROWSER_PROMPT_CONTEXT_LEGACY_HOOK.replace(
    "Use the browser_* DOM tools in this main turn directly; do not launch a Task subagent.",
    "Use the browser_* DOM tools in this main turn directly whenever they are the best way to complete the task; the latest prompt does not need to name the browser when saved context or the task itself implies it. Do not launch a Task subagent. If saved context names an established API, CLI, connector, or saved helper suitable for the exact task, prefer that path.",
)
DIRECT_BROWSER_PROMPT_STOCK_TAIL = """    if (host.isBrowserUseSubagent) {
      return ["""
DIRECT_BROWSER_PROMPT_VOCAB_GATED_BLOCK = DIRECT_BROWSER_PROMPT_VOCAB_GATED_HOOK.removesuffix(
    DIRECT_BROWSER_PROMPT_STOCK_TAIL
)
DIRECT_BROWSER_PROMPT_BLOCK = DIRECT_BROWSER_PROMPT_HOOK.removesuffix(DIRECT_BROWSER_PROMPT_STOCK_TAIL)

# Stock Grok's base prompt required an acknowledgement before every tool and
# frequent progress bubbles. The UI already has an activity animation, so that
# policy produced exactly the noisy request -> ack -> updates -> result flow the
# user rejected. Patch the policy at its source as well as enforcing it in the
# Codex adapter; stock fallback must have the same user-facing contract.
STOCK_TURN_REPLY_FIRST_NEEDLE = r'''"1. Reply first. On any turn a person opened \u2014 a user message, a burst of them, a ping while you work \u2014 your very first action is a plain text SendToUser, before any tool call: answer directly if it's quick, or acknowledge the request and name your first step if it's real work. Never open such a turn with a tool call. The one exception is a bare emoji tapback: when a ReactToMessage reaction is the whole response (a reply would be overkill), that reaction is the turn \u2014 send it alone, no SendToUser needed. A hidden self-initiated wake (a [routine] run or a background task finishing) is not one of these turns: nobody is waiting, so start straight in on the work and send a message only when its outcome is worth surfacing.",'''
STOCK_TURN_REPLY_FIRST_HOOK = '''"1. Work quietly. For real work, the interface activity animation is the opening acknowledgement: start with the next useful tool and do not send an intention, plan, or preliminary summary. If no tools are needed, answer once in SendToUser. A hidden self-initiated wake starts directly on the work and surfaces only its complete outcome when required.",'''

STOCK_WORK_OUT_LOUD_NEEDLE = '''"3. Work out loud. Do the work while keeping the user posted on meaningful beats; never vanish into a long run of silent tool calls.",'''
STOCK_WORK_OUT_LOUD_HOOK = '''"3. Work silently while the activity animation is visible. Send only the completed result, or an actual question, choice, approval/authentication handoff, or concrete blocker that requires the user.",'''

STOCK_REPLY_SECTION_NEEDLE = r'''heading: "## Reply first, then keep the user posted",
      body: [
        `The first thing you do on every user-visible turn is a plain text SendToUser that addresses the user's latest message, before any tool call, browsing, shell command, MCP call, screenshot, or extended private reasoning. If it's quick or conversational, put the direct answer in that first SendToUser; if it's real work, send a short acknowledgement plus your concrete first step, then start working. That opening acknowledgement must be a text SendToUser: a widget, ${cloudAgentsEnabled ? "attachment, or cursor-agent card" : "or attachment"} never counts as it. The worst and most common way to fail is a brand-new agent diving straight into tool calls (${cloudAgentsEnabled ? "launching a cloud agent, reading files" : "reading files"}, running a shell command) with no opening text reply: the user sees pure silence and assumes the app is frozen. So even when your obvious first move is ${cloudAgentsEnabled ? "launching a cloud agent or surfacing a card" : "surfacing a card"}, lead with the one-line text reply and send the card right after. Long hidden thinking before that first SendToUser feels just as stuck, so don't.`,
        `- This holds for bursts too: when the user fires several messages in a row, or pings again while you're mid-task, your first move is still a quick SendToUser acknowledging what they just sent (a one-line "On it, looking now" is enough), never silently diving back into the work.`,
        "- Then keep them posted at a steady cadence: the user is watching a live chat, not a progress bar. On any multi-step or long-running task, send a short update on each meaningful beat (a step finished, a real result, a decision, a blocker, a change of plan) so they always know where things stand. The worst way to fail is to go heads-down through a long silent run and resurface only at the end, which from their side is indistinguishable from a frozen app, so never let a long stretch of work pass with no word. The failure on the other side is a wall of low-value bubbles narrating routine mechanics, retries, minor snags, or self-correcting hiccups, so fold those into the next real update or omit them. When in doubt, err toward a quick update rather than long silence.",
        "- Keep each update short: frequent one-liners are exactly right on a long task, so what you trim is the trivial-mechanic play-by-play (every command, every retry), never the cadence itself. Surface real results and blockers promptly, and never disappear into a long silent stretch on something the user is waiting on.",
        `- Keep updates substantive and specific to what changed, never canned: say what you found or where things stand ("Found it, the auth state comes from the sidebar query."), and don't repeat the same "still working on X" phrasing across bubbles. Fold trivial mechanics under one intent ("Setting up the project") rather than narrating each command.`,
        `- Don't over-prove that an action worked by narrating UI evidence ("the count ticked from 233 to 244, with an Undo option showing"); just state the result plainly ("Reposted it.").`,
        `- When something fails or you're blocked, say what's wrong and the single most likely next step in a sentence or two; don't fire off an unprompted numbered troubleshooting guide or a root-cause/infra essay unless the user asks for detail. Not "How to fix, easiest first: 1... 2... 3...", just "That failed because the auth listener wasn't running. Want me to retry it on your main machine?".`,
        "- Close the loop with a short recap once the work is done."
      ]'''
STOCK_REPLY_SECTION_RETITLED_HOOK = '''heading: "## Quiet execution and one delivery",
      body: [
        "For real work, start with the next useful tool. The interface activity animation already shows that work is in progress, so do not send an acknowledgement, intention, plan, preliminary summary, or routine progress update.",
        "Use SendToUser once when the requested outcome is complete. Use it earlier only for an actual question or choice, a native approval or authentication handoff, or a concrete blocker that requires the user. If the request is quick or conversational and needs no tools, answer once in SendToUser.",
        "A correction or a request to continue carries the same unfinished goal and its prior context. Apply the correction and keep working; do not answer with a promise to do the work later.",
        "Do not send multiple recaps. Deliver one concise verified result, or one clear question or blocker when the user truly must act."
      ]'''
# The slim prompt edits address base sections by their original control heading.
# Retitling this section makes the stock bundle abort during module startup even
# though `node --check` succeeds, so change only its body and preserve the key.
STOCK_REPLY_SECTION_HOOK = STOCK_REPLY_SECTION_RETITLED_HOOK.replace(
    'heading: "## Quiet execution and one delivery"',
    'heading: "## Reply first, then keep the user posted"',
    1,
)

STOCK_ACK_DELIVERY_NEEDLE = r'''"And it bites harder, with more at stake, on the results the user is actually waiting on. Reply first and deliver last are two separate obligations, and the opening acknowledgement does NOT discharge delivery: ack \u2260 delivery. If you ran something for the user, the actual output goes inside a SendToUser before you yield; an `On it` at the top never counts as having reported back. So whenever a turn produced a result the user is waiting on, the last thing you do before ending it is SendToUser that result.",
        "- Wrong: SendToUser `Running both now`, run the commands, then type the results as plain assistant text and end the turn. The user only ever saw `Running both now` and never got the answer.",
        "- Right: SendToUser `Running both now`, run the commands, then SendToUser the actual output. The ack opened the turn; the result closed it.",'''
STOCK_ACK_DELIVERY_HOOK = '''"For real work, the activity animation opens the turn and SendToUser closes it. Run the tools without an acknowledgement, then put the verified outcome inside one SendToUser before yielding.",
        "- Wrong: send `Running both now`, run the commands, and make the user wait through extra chat bubbles.",
        "- Right: run the commands while the activity animation is visible, then send the actual verified output once.",'''

STOCK_SLIM_REPLY_FIRST_NEEDLE = r'''`On every turn opened by a person (including a burst of messages or a ping while you work), your first action must be a plain-text SendToUser before every other tool call or extended reasoning. Answer immediately if quick; otherwise acknowledge the request and name your first step. A widget, ${options2.cloudAgentsEnabled ? "attachment, or cursor-agent card" : "or attachment"} is not this opening reply. Hidden self-initiated wakes such as [routine] runs and background completions are different: start the work directly and message only when the result is worth surfacing.`,'''
STOCK_SLIM_REPLY_FIRST_HOOK = '''`For real work opened by a person, the activity animation is the progress signal: start with the next useful tool and do not send an opening acknowledgement or plan. If no tools are needed, answer once in SendToUser. Hidden self-initiated wakes start directly on the work and surface only the complete outcome when required.`,'''

STOCK_SLIM_PROGRESS_NEEDLE = '''"Keep the user posted at meaningful beats during long work. Use brief, specific updates for results, decisions, blockers, or changed plans; omit command-by-command narration, retries, and self-correcting mechanics. Never disappear into a long silent run.",'''
STOCK_SLIM_PROGRESS_HOOK = '''"Work silently while the activity animation is visible. Send one completed result, or interrupt only for an actual decision, approval/authentication handoff, or concrete blocker that requires the user.",'''

STOCK_SLIM_DELIVERY_NEEDLE = r'''"Reply-first and delivery are separate obligations: ack \u2260 delivery. An opening \u201COn it\u201D does not deliver later output. If a turn produced a result someone awaits, SendToUser that result before yielding and close the loop. Deciding or drafting in scratch text is not sending. Never end a person-opened turn with silence or only an acknowledgement.",'''
STOCK_SLIM_DELIVERY_HOOK = '''"The activity animation is the opening signal and delivery is one verified SendToUser at the end. Deciding or drafting in scratch text is not sending. Never end a person-opened work turn without its completed result, actual question, or concrete blocker.",'''

STOCK_TOOL_PROGRESS_NEEDLE = '''Keep the user posted with meaningful beats, not just at the end: post an update for a real result, decision, blocker, or change of plan, and batch or omit routine mechanics, retries, and minor snags rather than narrating each one; prefer fewer, higher-signal updates over a play-by-play. Still, never vanish into a long silent run on something the user is waiting on.'''
STOCK_TOOL_PROGRESS_HOOK = '''The interface activity animation is the progress signal. For real work, do not send acknowledgements, intentions, preliminary summaries, or routine progress updates; send one verified completion, or an actual question, choice, approval/authentication handoff, or concrete blocker that requires the user.'''

AUTOMATION_CONTEXT_NEEDLE = '''"Use that pointer only if the task truly needs earlier conversational detail; the parent transcript has deliberately not been copied into this prompt.",'''
AUTOMATION_CONTEXT_HOOK = '''"Before acting, use shared durable memory and inspect the parent transcript pointer for repeated or continuing work so you retain the latest outcome, method corrections, approvals, and unfinished goal instead of restarting from a blank interpretation.",
    "When the saved instruction or memory names an exact native API, CLI, or helper, use it before generic MCP discovery and before browser or Computer. Continue until the saved outcome is complete, then return one concise complete result.",'''

AUTOMATION_MAIN_THREAD_NEEDLE = '''      const shouldRunAsSubagent = !isGroup && runAsSubagent === true;'''
AUTOMATION_MAIN_THREAD_LEGACY_HOOK = '''      const shouldRunAsSubagent = process.env.OPENGROK_DIRECT_BROWSER_MAIN === "0" && !isGroup && runAsSubagent === true;'''
AUTOMATION_MAIN_THREAD_HOOK = '''      const shouldRunAsSubagent = process.env.OPENGROK_AUTOMATION_PARENT_RUNNER === "0" && !isGroup && runAsSubagent === true;'''

STOCK_POLICY_PATCHES = (
    (STOCK_TURN_REPLY_FIRST_NEEDLE, STOCK_TURN_REPLY_FIRST_HOOK, "quiet turn opening"),
    (STOCK_WORK_OUT_LOUD_NEEDLE, STOCK_WORK_OUT_LOUD_HOOK, "silent tool execution"),
    (STOCK_REPLY_SECTION_NEEDLE, STOCK_REPLY_SECTION_HOOK, "one-delivery section"),
    (STOCK_ACK_DELIVERY_NEEDLE, STOCK_ACK_DELIVERY_HOOK, "single delivery examples"),
    (STOCK_SLIM_REPLY_FIRST_NEEDLE, STOCK_SLIM_REPLY_FIRST_HOOK, "slim quiet opening"),
    (STOCK_SLIM_PROGRESS_NEEDLE, STOCK_SLIM_PROGRESS_HOOK, "slim silent execution"),
    (STOCK_SLIM_DELIVERY_NEEDLE, STOCK_SLIM_DELIVERY_HOOK, "slim one-delivery rule"),
    (STOCK_TOOL_PROGRESS_NEEDLE, STOCK_TOOL_PROGRESS_HOOK, "SendToUser quiet-progress contract"),
    (AUTOMATION_CONTEXT_NEEDLE, AUTOMATION_CONTEXT_HOOK, "automation memory and helper continuity"),
)

DIRECT_BROWSER_STATIC_NEEDLE = """function withDynamicToolPlacement(tool) {
  if (SAND_FORCED_STATIC_TOOL_NAMES.has(tool.name)) {"""
DIRECT_BROWSER_STATIC_HOOK = """function withDynamicToolPlacement(tool) {
  if (SAND_FORCED_STATIC_TOOL_NAMES.has(tool.name) || process.env.OPENGROK_DIRECT_BROWSER_MAIN !== "0" && typeof tool.toolIdentifier === "string" && tool.toolIdentifier.startsWith("BROWSER_")) {"""

BAD_MARKERS = (
    'process.env.SAND_INFERENCE_PROVIDER || "xai"',
    "inferenceProvider !== \"cursor\"",
)


def write_atomic(path: pathlib.Path, text: str) -> None:
    """Never truncate the live bundle in place: a crash mid-write would leave a host that cannot start."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", errors="surrogateescape")
    shutil.copymode(path, tmp)
    os.replace(tmp, path)


_WORD = re.compile(r"[A-Za-z0-9_$]")


def _tolerant_pattern(needle: str) -> "re.Pattern[str]":
    """Match this anchor regardless of how the bundle is indented or line-wrapped.

    A host bundle upgrade reformatted the browser module from spaces to tabs and
    wrapped one assignment across two lines. Nothing about the code changed, but
    exact-string anchors stopped matching and the whole injection failed closed,
    which silently drops every agent onto stock Grok until someone re-anchors by
    hand. Whitespace between two identifier characters must still exist, so
    tokens cannot be glued together; anywhere else it is optional.
    """
    tokens = needle.split()
    parts = [re.escape(tokens[0])]
    for previous, token in zip(tokens, tokens[1:]):
        joint = r"\s+" if (_WORD.match(previous[-1]) and _WORD.match(token[0])) else r"\s*"
        parts.append(joint + re.escape(token))
    return re.compile("".join(parts))


def anchor_span(text: str, needle: str):
    """Locate an anchor exactly, else tolerantly. None when absent, (-1, -1) when ambiguous."""
    count = text.count(needle)
    if count == 1:
        start = text.index(needle)
        return (start, start + len(needle))
    if count > 1:
        return (-1, -1)
    matches = list(_tolerant_pattern(needle).finditer(text))
    if len(matches) == 1:
        return matches[0].span()
    return None if not matches else (-1, -1)


def patch(text: str, needle: str, hook: str) -> str:
    """Replace exactly one anchor. Ambiguity means the bundle changed shape; refuse rather than mis-patch."""
    span = anchor_span(text, needle)
    if span is None or span == (-1, -1):
        found = "ambiguous" if span == (-1, -1) else "missing"
        print(f"ERROR: anchor {found}, refusing to patch: {needle.strip()[:70]!r}", file=sys.stderr)
        raise SystemExit(3)
    if text[span[0]:span[1]] != needle:
        print(f"re-anchored after a bundle reformat: {needle.strip()[:60]!r}")
    return text[:span[0]] + hook + text[span[1]:]


def patch_all(text: str, needle: str, hook: str, expected: int) -> str:
    """Replace an exact number of equivalent anchors, tolerating formatting only."""
    matches = list(_tolerant_pattern(needle).finditer(text))
    if len(matches) != expected:
        print(
            f"ERROR: expected {expected} anchors, found {len(matches)}, refusing to patch: {needle.strip()[:70]!r}",
            file=sys.stderr,
        )
        raise SystemExit(3)
    for match in reversed(matches):
        text = text[:match.start()] + hook + text[match.end():]
    return text


def main() -> int:
    text = HOST_MAIN.read_text(encoding="utf-8", errors="surrogateescape")
    # A bundle with none of our hooks is pristine stock (for example after an
    # upstream upgrade); it must become the rollback backup, not the old one.
    stock = "createRoutedPromptSession" not in text and not any(m in text for m in BAD_MARKERS)
    if any(m in text for m in BAD_MARKERS) and BACKUP.is_file():
        print("restoring stock host-main (old global-xai hook present)")
        write_atomic(HOST_MAIN, BACKUP.read_text(encoding="utf-8", errors="surrogateescape"))
        text = HOST_MAIN.read_text(encoding="utf-8", errors="surrogateescape")

    changed = False
    # Upgrade the briefly shipped retitled section. It passed syntax checking
    # but violated the stock slim-prompt control-heading map at module startup.
    if anchor_span(text, STOCK_REPLY_SECTION_RETITLED_HOOK) not in (None, (-1, -1)):
        text = patch(text, STOCK_REPLY_SECTION_RETITLED_HOOK, STOCK_REPLY_SECTION_HOOK)
        changed = True
        print("restored the stock slim-prompt control heading")
    for needle, hook, label in STOCK_POLICY_PATCHES:
        hook_span = anchor_span(text, hook)
        if hook_span is not None and hook_span != (-1, -1):
            print(f"{label} already patched")
        elif anchor_span(text, needle) is None:
            print(f"ERROR: could not find stock policy for {label}", file=sys.stderr)
            return 19
        else:
            text = patch(text, needle, hook)
            changed = True
            print(f"patched {label}")

    if AUTOMATION_MAIN_THREAD_HOOK in text:
        print("scheduled automations already stay on the parent runner")
    elif AUTOMATION_MAIN_THREAD_LEGACY_HOOK in text:
        text = patch(text, AUTOMATION_MAIN_THREAD_LEGACY_HOOK, AUTOMATION_MAIN_THREAD_HOOK)
        changed = True
        print("decoupled scheduled parent execution from browser rollback")
    elif anchor_span(text, AUTOMATION_MAIN_THREAD_NEEDLE) is None:
        print("ERROR: could not find scheduled-automation execution gate", file=sys.stderr)
        return 20
    else:
        text = patch(text, AUTOMATION_MAIN_THREAD_NEEDLE, AUTOMATION_MAIN_THREAD_HOOK)
        changed = True
        print("kept scheduled automations on the parent runner")

    if "createRoutedComputerUseSession" in text:
        if AUTH_STOCK_FACTORY in text:
            text = patch(text, AUTH_STOCK_FACTORY, OVERRIDABLE_STOCK_FACTORY)
            changed = True
            print("made native Cursor model parameters selectable")
        elif MODEL_ONLY_STOCK_FACTORY in text:
            text = patch(text, MODEL_ONLY_STOCK_FACTORY, OVERRIDABLE_STOCK_FACTORY)
            changed = True
            print("made native Cursor authentication selectable")
        elif LEGACY_STOCK_FACTORY in text:
            text = patch(text, LEGACY_STOCK_FACTORY, OVERRIDABLE_STOCK_FACTORY)
            changed = True
            print("made the native Cursor model and authentication selectable")
        if ROUTED_MAIN_WITHOUT_STOCK in text:
            text = patch(text, ROUTED_MAIN_WITHOUT_STOCK, ROUTED_MAIN_WITH_STOCK)
            changed = True
            print("passed stock fallback into the main Codex route")
        print("main + computer session route hooks already present")
    elif anchor_span(text, LEGACY_SESSION_BLOCK) is not None:
        text = patch(text, LEGACY_SESSION_BLOCK, SESSION_HOOK)
        changed = True
        print("upgraded legacy main hook with computer-use route")
    elif anchor_span(text, SESSION_NEEDLE) is not None:
        text = patch(text, SESSION_NEEDLE, SESSION_HOOK)
        changed = True
        print("injected main + computer session route hooks")
    elif "createRoutedPromptSession" in text:
        print("ERROR: found an unknown legacy route hook", file=sys.stderr)
        return 2
    else:
        print("ERROR: could not find createSession needle", file=sys.stderr)
        return 2

    if "agentId: typeof host.getConversationId" in text:
        print("agentId sessionOptions hook already present")
    elif anchor_span(text, AGENT_NEEDLE) is None:
        print("ERROR: could not find mainSessionOptions needle", file=sys.stderr)
        return 3
    else:
        text = patch(text, AGENT_NEEDLE, AGENT_HOOK)
        changed = True
        print("injected agentId into mainSessionOptions")

    if "stockBadgeForSession(sessionOptions)" in text:
        print("stock model badge hook already present")
    elif anchor_span(text, RETURN_NEEDLE) is None:
        print("ERROR: could not find stock session return needle", file=sys.stderr)
        return 5
    else:
        text = patch(text, RETURN_NEEDLE, RETURN_HOOK)
        changed = True
        print("injected stock model badge hook")

    if "createCodexAutoReviewClassifier" in text and AUTO_REVIEW_CALL_HOOK not in text:
        for legacy in AUTO_REVIEW_CALL_LEGACY:
            if legacy in text:
                text = patch(text, legacy, AUTO_REVIEW_CALL_HOOK)
                changed = True
                print("upgraded the Codex Auto-review call to the 12s bound and host fallback")
                break
        else:
            print("ERROR: injected Auto-review call has an unknown shape", file=sys.stderr)
            return 16

    if "createCodexAutoReviewClassifier" in text:
        print("Codex Luna-max Auto-review hook already present")
    elif anchor_span(text, AUTO_REVIEW_NEEDLE) is None:
        print("ERROR: could not find Auto-review classifier needle", file=sys.stderr)
        return 6
    else:
        text = patch(text, AUTO_REVIEW_NEEDLE, AUTO_REVIEW_HOOK)
        changed = True
        print("injected Codex Luna-max Auto-review classifier")

    if COMPUTER_REVIEW_CDP_HOOK in text:
        print("Computer review already tolerates pre-CDP native dialogs")
    elif anchor_span(text, COMPUTER_REVIEW_CDP_NEEDLE) is None:
        print("ERROR: could not find Computer review CDP probe", file=sys.stderr)
        return 18
    else:
        text = patch(text, COMPUTER_REVIEW_CDP_NEEDLE, COMPUTER_REVIEW_CDP_HOOK)
        changed = True
        print("allowed Computer review before Chrome CDP starts")

    if AUTO_REVIEW_TIMEOUT_HOOK in text:
        print("Auto-review classifier timeout already extended")
    elif AUTO_REVIEW_TIMEOUT_LEGACY_HOOK in text:
        text = patch(text, AUTO_REVIEW_TIMEOUT_LEGACY_HOOK, AUTO_REVIEW_TIMEOUT_HOOK)
        changed = True
        print("upgraded Auto-review classifier timeout to 80s")
    elif anchor_span(text, AUTO_REVIEW_TIMEOUT_NEEDLE) is None:
        print("ERROR: could not find Auto-review timeout needle", file=sys.stderr)
        return 7
    else:
        text = patch(text, AUTO_REVIEW_TIMEOUT_NEEDLE, AUTO_REVIEW_TIMEOUT_HOOK)
        changed = True
        print("extended Auto-review classifier timeout to 80s")

    if SMART_MODE_TIMEOUT_HOOK in text:
        print("shared Smart Mode classifier timeout already extended")
    elif anchor_span(text, SMART_MODE_TIMEOUT_NEEDLE) is None:
        print("ERROR: could not find shared Smart Mode classifier timeout needle", file=sys.stderr)
        return 8
    else:
        text = patch(text, SMART_MODE_TIMEOUT_NEEDLE, SMART_MODE_TIMEOUT_HOOK)
        changed = True
        print("extended shared Smart Mode classifier timeout to 80s")

    if APPROVAL_EXPIRY_POLICY_HOOK in text:
        print("native approvals already park until the user responds")
    elif anchor_span(text, APPROVAL_EXPIRY_POLICY_NEEDLE) is None:
        print("ERROR: could not find native approval expiry policy", file=sys.stderr)
        return 9
    else:
        text = patch(text, APPROVAL_EXPIRY_POLICY_NEEDLE, APPROVAL_EXPIRY_POLICY_HOOK)
        changed = True
        print("removed the background approval user-response TTL")

    if BROWSER_CLOSE_VIEW_HOOK in text or BROWSER_CLOSE_VIEW_HOOK_TABS in text:
        print("native browser close already scoped to the caller view")
    elif BROWSER_CLOSE_VIEW_NEEDLE_TABS in text:
        text = patch(text, BROWSER_CLOSE_VIEW_NEEDLE_TABS, BROWSER_CLOSE_VIEW_HOOK_TABS)
        changed = True
        print("bound native browser close to the caller view (tab-formatted bundle)")
    elif anchor_span(text, BROWSER_CLOSE_VIEW_NEEDLE) is None:
        print("ERROR: could not find native browser close view binding", file=sys.stderr)
        return 10
    else:
        text = patch(text, BROWSER_CLOSE_VIEW_NEEDLE, BROWSER_CLOSE_VIEW_HOOK)
        changed = True
        print("scoped native browser close to the caller view")

    if BROWSER_FIRST_VIEW_HOOK in text or BROWSER_FIRST_VIEW_HOOK_TABS in text:
        print("fresh browser workers already adopt the visible tab")
    elif BROWSER_FIRST_VIEW_NEEDLE_TABS in text:
        text = patch(text, BROWSER_FIRST_VIEW_NEEDLE_TABS, BROWSER_FIRST_VIEW_HOOK_TABS)
        changed = True
        print("fresh browser views adopt the visible tab (tab-formatted bundle)")
    elif anchor_span(text, BROWSER_FIRST_VIEW_NEEDLE) is None:
        print("ERROR: could not find native browser first-view binding", file=sys.stderr)
        return 11
    else:
        text = patch(text, BROWSER_FIRST_VIEW_NEEDLE, BROWSER_FIRST_VIEW_HOOK)
        changed = True
        print("made fresh browser workers adopt the visible tab")

    if DIRECT_COMPUTER_TOOLS_HOOK in text:
        print("main turns already receive native Computer directly")
    elif anchor_span(text, DIRECT_COMPUTER_TOOLS_NEEDLE) is None:
        print("ERROR: could not find native Computer tool gate", file=sys.stderr)
        return 16
    else:
        text = patch(text, DIRECT_COMPUTER_TOOLS_NEEDLE, DIRECT_COMPUTER_TOOLS_HOOK)
        changed = True
        print("exposed native Computer directly to main turns")

    if DIRECT_BROWSER_TOOLS_HOOK in text:
        print("main turns already receive native browser tools")
    elif DIRECT_BROWSER_TOOLS_GATED_HOOK in text:
        text = patch(text, DIRECT_BROWSER_TOOLS_GATED_HOOK, DIRECT_BROWSER_TOOLS_HOOK)
        changed = True
        print("removed the browser-subagent gate from main browser tools")
    elif DIRECT_BROWSER_TOOLS_TRANSIENT_HOOK in text:
        text = patch(text, DIRECT_BROWSER_TOOLS_TRANSIENT_HOOK, DIRECT_BROWSER_TOOLS_HOOK)
        changed = True
        print("removed worker gates from main browser tools")
    elif anchor_span(text, DIRECT_BROWSER_TOOLS_NEEDLE) is None:
        print("ERROR: could not find native browser tool gate", file=sys.stderr)
        return 12
    else:
        text = patch(text, DIRECT_BROWSER_TOOLS_NEEDLE, DIRECT_BROWSER_TOOLS_HOOK)
        changed = True
        print("exposed native browser tools to main turns")

    if DIRECT_GUI_TASKS_HOOK in text:
        print("GUI Tasks already limited to rollback mode")
    elif DIRECT_GUI_TASKS_LEGACY_HOOK in text:
        text = patch(text, DIRECT_GUI_TASKS_LEGACY_HOOK, DIRECT_GUI_TASKS_HOOK)
        changed = True
        print("limited computerUse and browserUse Tasks to rollback mode")
    elif anchor_span(text, DIRECT_GUI_TASKS_STOCK_NEEDLE) is None:
        print("ERROR: could not find GUI Task registration", file=sys.stderr)
        return 13
    else:
        text = patch(text, DIRECT_GUI_TASKS_STOCK_NEEDLE, DIRECT_GUI_TASKS_HOOK)
        changed = True
        print("limited computerUse and browserUse Tasks to rollback mode")

    if DIRECT_MAIN_TASKS_HOOK in text:
        print("all hidden Tasks already limited to rollback mode")
    elif anchor_span(text, DIRECT_MAIN_TASKS_NEEDLE) is None:
        print("ERROR: could not find main Task registration", file=sys.stderr)
        return 17
    else:
        text = patch(text, DIRECT_MAIN_TASKS_NEEDLE, DIRECT_MAIN_TASKS_HOOK)
        changed = True
        print("limited all hidden Tasks to rollback mode")

    task_gate_hooks = len(list(_tolerant_pattern(DIRECT_TASK_TOOLS_GATE_HOOK).finditer(text)))
    task_gate_needles = len(list(_tolerant_pattern(DIRECT_TASK_TOOLS_GATE_NEEDLE).finditer(text)))
    if task_gate_hooks == 2 and task_gate_needles == 0:
        print("empty Task and agent-management schemas already omitted")
    elif task_gate_hooks + task_gate_needles == 2 and task_gate_needles > 0:
        text = patch_all(text, DIRECT_TASK_TOOLS_GATE_NEEDLE, DIRECT_TASK_TOOLS_GATE_HOOK, task_gate_needles)
        changed = True
        print("omitted Task and agent-management tools when no subagent type is available")
    else:
        print(
            f"ERROR: unexpected Task tool gates current={task_gate_hooks} stock={task_gate_needles}",
            file=sys.stderr,
        )
        return 18

    if DIRECT_BROWSER_STATIC_HOOK in text:
        print("direct browser tools already bypass dynamic placement")
    elif anchor_span(text, DIRECT_BROWSER_STATIC_NEEDLE) is None:
        print("ERROR: could not find dynamic browser tool placement", file=sys.stderr)
        return 15
    else:
        text = patch(text, DIRECT_BROWSER_STATIC_NEEDLE, DIRECT_BROWSER_STATIC_HOOK)
        changed = True
        print("kept direct browser tools in the initial model schema")

    for obsolete_guard in (DIRECT_BROWSER_PROMPT_BAD_GUARD, DIRECT_BROWSER_PROMPT_GATED_GUARD):
        if obsolete_guard in text:
            text = patch(text, obsolete_guard, DIRECT_BROWSER_PROMPT_GUARD)
            changed = True
            print("removed worker gates from the main browser prompt")

    if DIRECT_BROWSER_PROMPT_BLOCK in text and DIRECT_BROWSER_PROMPT_VOCAB_GATED_BLOCK in text:
        text = patch(text, DIRECT_BROWSER_PROMPT_VOCAB_GATED_BLOCK, "")
        changed = True
        print("removed duplicate prompt-vocabulary browser gate")
    elif DIRECT_BROWSER_PROMPT_BLOCK in text:
        print("main prompt already uses native DOM and Computer directly")
    elif DIRECT_BROWSER_PROMPT_VOCAB_GATED_BLOCK in text:
        text = patch(text, DIRECT_BROWSER_PROMPT_VOCAB_GATED_BLOCK, DIRECT_BROWSER_PROMPT_BLOCK)
        changed = True
        print("removed prompt-vocabulary browser gate")
    elif DIRECT_BROWSER_PROMPT_CONTEXT_LEGACY_HOOK in text:
        text = patch(text, DIRECT_BROWSER_PROMPT_CONTEXT_LEGACY_HOOK, DIRECT_BROWSER_PROMPT_HOOK)
        changed = True
        print("made API/CLI/helper the default ahead of available GUI tools")
    elif DIRECT_BROWSER_PROMPT_GUI_ONLY_HOOK in text:
        text = patch(text, DIRECT_BROWSER_PROMPT_GUI_ONLY_HOOK, DIRECT_BROWSER_PROMPT_HOOK)
        changed = True
        print("removed remaining hidden-Task guidance from the main prompt")
    elif DIRECT_BROWSER_PROMPT_LEGACY_HOOK in text:
        text = patch(text, DIRECT_BROWSER_PROMPT_LEGACY_HOOK, DIRECT_BROWSER_PROMPT_HOOK)
        changed = True
        print("moved pixel/desktop work from a Task into the main turn")
    elif anchor_span(text, DIRECT_BROWSER_PROMPT_NEEDLE) is None:
        print("ERROR: could not find browser prompt gate", file=sys.stderr)
        return 14
    else:
        text = patch(text, DIRECT_BROWSER_PROMPT_NEEDLE, DIRECT_BROWSER_PROMPT_HOOK)
        changed = True
        print("adapted the main prompt for direct native DOM tools")

    if changed:
        if stock or not BACKUP.is_file():
            shutil.copy2(HOST_MAIN, BACKUP)
            print(f"backed up {BACKUP}")
        write_atomic(HOST_MAIN, text)

    text = HOST_MAIN.read_text(encoding="utf-8", errors="surrogateescape")
    ok = (
        "createRoutedPromptSession" in text
        and "createRoutedComputerUseSession" in text
        and "const createStockSession" in text
        and "agentId: typeof host.getConversationId" in text
        and "stockBadgeForSession(sessionOptions)" in text
        and "createCodexAutoReviewClassifier" in text
        and AUTO_REVIEW_TIMEOUT_HOOK in text
        and SMART_MODE_TIMEOUT_HOOK in text
        and APPROVAL_EXPIRY_POLICY_HOOK in text
        and (BROWSER_CLOSE_VIEW_HOOK in text or BROWSER_CLOSE_VIEW_HOOK_TABS in text)
        and (BROWSER_FIRST_VIEW_HOOK in text or BROWSER_FIRST_VIEW_HOOK_TABS in text)
        and DIRECT_COMPUTER_TOOLS_HOOK in text
        and DIRECT_BROWSER_TOOLS_HOOK in text
        and DIRECT_GUI_TASKS_HOOK in text
        and DIRECT_MAIN_TASKS_HOOK in text
        and text.count(DIRECT_TASK_TOOLS_GATE_HOOK) == 2
        and DIRECT_TASK_TOOLS_GATE_NEEDLE not in text
        and DIRECT_BROWSER_STATIC_HOOK in text
        and DIRECT_BROWSER_PROMPT_HOOK in text
        and AUTOMATION_MAIN_THREAD_HOOK in text
        and all(anchor_span(text, hook) not in (None, (-1, -1)) for _, hook, _ in STOCK_POLICY_PATCHES)
    )
    print("createRoutedPromptSession", text.count("createRoutedPromptSession"))
    print("createRoutedComputerUseSession", text.count("createRoutedComputerUseSession"))
    print("createStockSession", text.count("createStockSession"))
    print("createCursorInferencePromptSession", text.count("createCursorInferencePromptSession"))
    print("createCodexAutoReviewClassifier", text.count("createCodexAutoReviewClassifier"))
    print("sharedSmartModeTimeout80s", text.count(SMART_MODE_TIMEOUT_HOOK))
    print("approvalParkUntilUserResponse", text.count(APPROVAL_EXPIRY_POLICY_HOOK))
    print("browserCloseCallerView", text.count(BROWSER_CLOSE_VIEW_HOOK) + text.count(BROWSER_CLOSE_VIEW_HOOK_TABS))
    print("browserFirstViewVisibleTab", text.count(BROWSER_FIRST_VIEW_HOOK) + text.count(BROWSER_FIRST_VIEW_HOOK_TABS))
    print("directComputerMainTools", text.count(DIRECT_COMPUTER_TOOLS_HOOK))
    print("directBrowserMainTools", text.count(DIRECT_BROWSER_TOOLS_HOOK))
    print("directBrowserMainPrompt", text.count(DIRECT_BROWSER_PROMPT_HOOK))
    print("directBrowserStaticTools", text.count(DIRECT_BROWSER_STATIC_HOOK))
    print("guiTasksRollbackOnly", text.count(DIRECT_GUI_TASKS_HOOK))
    print("allTasksRollbackOnly", text.count(DIRECT_MAIN_TASKS_HOOK))
    print("emptyTaskSchemasOmitted", text.count(DIRECT_TASK_TOOLS_GATE_HOOK))
    print("scheduledAutomationParentRunner", text.count(AUTOMATION_MAIN_THREAD_HOOK))
    print("quietStockPolicyPatches", sum(text.count(hook) for _, hook, _ in STOCK_POLICY_PATCHES))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
