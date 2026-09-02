#!/usr/bin/env python3
"""Synthetic idempotence and legacy-upgrade tests for the host injector."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("inject_host", HERE / "inject-host.py")
INJECT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INJECT)


def host_fixture(session_block: str) -> str:
    return "\n".join([
        "prefix",
        session_block,
        INJECT.AGENT_NEEDLE,
        INJECT.RETURN_NEEDLE,
        INJECT.AUTO_REVIEW_NEEDLE,
        INJECT.SMART_MODE_TIMEOUT_NEEDLE,
        INJECT.AUTO_REVIEW_TIMEOUT_NEEDLE,
        INJECT.APPROVAL_EXPIRY_POLICY_NEEDLE,
        INJECT.BROWSER_CLOSE_VIEW_NEEDLE,
        INJECT.BROWSER_FIRST_VIEW_NEEDLE,
        INJECT.DIRECT_COMPUTER_TOOLS_NEEDLE,
        INJECT.COMPUTER_REVIEW_CDP_NEEDLE,
        INJECT.DIRECT_BROWSER_TOOLS_NEEDLE,
        INJECT.DIRECT_GUI_TASKS_STOCK_NEEDLE,
        INJECT.DIRECT_MAIN_TASKS_NEEDLE,
        INJECT.DIRECT_TASK_TOOLS_GATE_NEEDLE,
        INJECT.DIRECT_TASK_TOOLS_GATE_NEEDLE,
        INJECT.DIRECT_BROWSER_STATIC_NEEDLE,
        INJECT.DIRECT_BROWSER_PROMPT_NEEDLE,
        INJECT.AUTOMATION_MAIN_THREAD_NEEDLE,
        *[needle for needle, _hook, _label in INJECT.STOCK_POLICY_PATCHES],
        "suffix",
    ])


class InjectorTests(unittest.TestCase):
    def run_injector(self, initial: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            host = Path(tmp) / "host-main.cjs"
            backup = Path(tmp) / "host-main.cjs.cursor-bak"
            host.write_text(initial)
            for _ in range(2):
                subprocess.run(
                    ["python3", str(HERE / "inject-host.py"), str(host), str(backup)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            return host.read_text()

    def assert_current(self, text: str) -> None:
        self.assertEqual(text.count("createRoutedComputerUseSession"), 2)
        self.assertEqual(text.count("createRoutedPromptSession"), 2)
        self.assertIn("const createStockSession", text)
        self.assertIn(INJECT.ROUTED_MAIN_WITH_STOCK, text)
        self.assertNotIn(INJECT.ROUTED_MAIN_WITHOUT_STOCK, text)
        self.assertIn("agentId: typeof host.getConversationId", text)
        self.assertIn("stockBadgeForSession(sessionOptions)", text)
        self.assertEqual(text.count("createCodexAutoReviewClassifier"), 2)
        self.assertIn("fallbackToHost: true", text)
        self.assertIn("client.classifySandAutoReview", text)
        self.assertIn(INJECT.AUTO_REVIEW_BLOCK_ADJUDICATION_MARKER, text)
        self.assertIn(INJECT.AUTO_REVIEW_TIMEOUT_HOOK, text)
        self.assertIn(INJECT.SMART_MODE_TIMEOUT_HOOK, text)
        self.assertIn(INJECT.APPROVAL_EXPIRY_POLICY_HOOK, text)
        self.assertIn(INJECT.BROWSER_CLOSE_VIEW_HOOK, text)
        self.assertIn(INJECT.BROWSER_FIRST_VIEW_HOOK, text)
        self.assertIn(INJECT.DIRECT_COMPUTER_TOOLS_HOOK, text)
        self.assertIn(INJECT.COMPUTER_REVIEW_CDP_HOOK, text)
        self.assertNotIn(INJECT.COMPUTER_REVIEW_CDP_NEEDLE, text)
        self.assertIn(INJECT.DIRECT_BROWSER_TOOLS_HOOK, text)
        self.assertNotIn(INJECT.DIRECT_BROWSER_TOOLS_GATED_HOOK, text)
        self.assertNotIn(INJECT.DIRECT_BROWSER_TOOLS_TRANSIENT_HOOK, text)
        self.assertIn(INJECT.DIRECT_GUI_TASKS_HOOK, text)
        self.assertNotIn(INJECT.DIRECT_GUI_TASKS_LEGACY_HOOK, text)
        self.assertIn(INJECT.DIRECT_MAIN_TASKS_HOOK, text)
        self.assertEqual(text.count(INJECT.DIRECT_TASK_TOOLS_GATE_HOOK), 2)
        self.assertNotIn(INJECT.DIRECT_TASK_TOOLS_GATE_NEEDLE, text)
        self.assertIn(INJECT.DIRECT_BROWSER_STATIC_HOOK, text)
        self.assertNotIn(INJECT.DIRECT_BROWSER_STATIC_NEEDLE, text)
        self.assertIn(INJECT.DIRECT_BROWSER_PROMPT_HOOK, text)
        self.assertEqual(text.count(INJECT.DIRECT_BROWSER_PROMPT_HOOK), 1)
        self.assertNotIn(INJECT.DIRECT_BROWSER_PROMPT_VOCAB_GATED_HOOK, text)
        self.assertNotIn("when the request explicitly requires the web UI", text)
        self.assertNotIn(INJECT.DIRECT_BROWSER_PROMPT_GATED_GUARD, text)
        self.assertNotIn("host.gates.browserUseSubagent()", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertNotIn("getRemoteBoxAvailable", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertIn("Use Computer directly in this main turn", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertIn("Do not launch a Task subagent", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertIn("Do not launch any Task subagent", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertIn("the latest prompt does not need to name the browser", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertNotIn("explicitly requires the web UI", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertIn("saved helper", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertNotIn("Launch one computerUse Task", INJECT.DIRECT_BROWSER_PROMPT_HOOK)
        self.assertIn(INJECT.AUTOMATION_MAIN_THREAD_HOOK, text)
        self.assertNotIn(INJECT.AUTOMATION_MAIN_THREAD_LEGACY_HOOK, text)
        self.assertNotIn(INJECT.AUTOMATION_MAIN_THREAD_NEEDLE, text)
        for needle, hook, _label in INJECT.STOCK_POLICY_PATCHES:
            self.assertIn(hook, text)
            self.assertNotIn(needle, text)
        self.assertIn("activity animation already shows that work is in progress", text)
        self.assertIn("inspect the parent transcript pointer", text)
        self.assertIn('heading: "## Reply first, then keep the user posted"', INJECT.STOCK_REPLY_SECTION_HOOK)
        self.assertNotIn('heading: "## Quiet execution and one delivery"', text)
        self.assertNotIn(INJECT.AUTO_REVIEW_TIMEOUT_NEEDLE, text)
        self.assertNotIn(INJECT.AUTO_REVIEW_TIMEOUT_LEGACY_HOOK, text)
        self.assertNotIn(INJECT.SMART_MODE_TIMEOUT_NEEDLE, text)
        self.assertNotIn(INJECT.APPROVAL_EXPIRY_POLICY_NEEDLE, text)
        self.assertNotIn(INJECT.BROWSER_CLOSE_VIEW_NEEDLE, text)
        self.assertNotIn(INJECT.BROWSER_FIRST_VIEW_NEEDLE, text)
        self.assertNotIn(INJECT.DIRECT_COMPUTER_TOOLS_NEEDLE, text)
        self.assertNotIn(INJECT.DIRECT_BROWSER_TOOLS_NEEDLE, text)
        self.assertNotIn(INJECT.DIRECT_GUI_TASKS_STOCK_NEEDLE, text)

    def test_survives_a_bundle_reformat(self):
        """A host upgrade that only reformats code must not take the router offline.

        The 2026-08-30 bundle switched the browser module from spaces to tabs and
        wrapped one assignment over two lines. Exact-string anchors stopped
        matching, injection failed closed, and every agent silently ran on stock
        Grok until the anchors were rewritten by hand.
        """
        stock = host_fixture(INJECT.SESSION_NEEDLE)
        for label, reformat in (
            ("tabs", lambda x: re.sub(r"^( +)", lambda m: "\t" * (len(m.group(1)) // 2), x, flags=re.M)),
            ("wide", lambda x: re.sub(r"^( +)", lambda m: m.group(1) * 2, x, flags=re.M)),
            ("wrapped", lambda x: x.replace(" ? ", "\n        ? ").replace(" : ", "\n        : ")),
        ):
            with self.subTest(reformat=label):
                self.assert_current(self.run_injector(reformat(stock)))

    def test_refuses_an_ambiguous_anchor(self):
        """Two matches means the bundle changed shape: refuse rather than mis-patch."""
        doubled = host_fixture(INJECT.SESSION_NEEDLE) + "\n" + INJECT.AGENT_NEEDLE
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_injector(doubled)

    def test_injects_stock_bundle_idempotently(self):
        self.assert_current(self.run_injector(host_fixture(INJECT.SESSION_NEEDLE)))

    def test_upgrades_legacy_main_only_hook_idempotently(self):
        self.assert_current(self.run_injector(host_fixture(INJECT.LEGACY_SESSION_BLOCK)))

    def test_upgrades_codex_block_to_stock_adjudication(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        legacy = current.replace(INJECT.AUTO_REVIEW_HOOK, INJECT.AUTO_REVIEW_LEGACY_HOOK, 1)
        self.assert_current(self.run_injector(legacy))

    def test_stock_adjudicates_codex_blocks(self):
        script = f'''
const Module = require("module");
let codexResult;
let stockResult;
let stockCalls = 0;
const originalRequire = Module.prototype.require;
Module.prototype.require = function(id) {{
  if (id === "./codex-auto-review.cjs") return {{ classify: async () => {{
    if (codexResult instanceof Error) throw codexResult;
    return codexResult;
  }} }};
  return originalRequire.apply(this, arguments);
}};
const smartModeClassifierAttemptIndexKey = "attempt";
const smartModeClassifierModeKey = "mode";
const SAND_AUTO_REVIEW_CLASSIFIER_SYSTEM_PROMPT = "policy";
const SmartModeClassifierDecision = {{ ALLOW: "ALLOW", BLOCK: "BLOCK" }};
class SmartModeClassifierSuccess {{ constructor(value) {{ Object.assign(this, value); }} }}
class SmartModeClassifierResult {{ constructor(value) {{ Object.assign(this, value); }} }}
class SmartModeClassifierArgs {{ constructor(value) {{ Object.assign(this, value); }} }}
class ClassifySandAutoReviewRequest {{ constructor(value) {{ Object.assign(this, value); }} }}
class SandSmartModeClassifierError extends Error {{}}
{INJECT.AUTO_REVIEW_HOOK}
const ctx = {{ get: (key) => key === "attempt" ? 0 : "enforce", signal: undefined }};
const args = {{ target: {{}}, conversationContext: [], parentConversationId: "test", toJson: () => ({{ target: {{}} }}) }};
const client = {{ classifySandAutoReview: async () => {{
  stockCalls++;
  if (stockResult instanceof Error) throw stockResult;
  return {{ result: new SmartModeClassifierResult({{ result: stockResult }}) }};
}} }};
(async () => {{
  const run = async (codex, stock) => {{
    codexResult = codex;
    stockResult = stock;
    stockCalls = 0;
    const result = await createSandBackendSmartModeClassifierExecutor({{}}, client).execute(ctx, args);
    return {{ decision: result.result.value.decision, stockCalls }};
  }};
  const out = [];
  out.push(await run({{ decision: "ALLOW" }}, {{ case: "success", value: {{ decision: "BLOCK" }} }}));
  out.push(await run({{ decision: "BLOCK", reason: "review" }}, {{ case: "success", value: {{ decision: "ALLOW" }} }}));
  out.push(await run({{ decision: "BLOCK", reason: "review" }}, new Error("stock offline")));
  out.push(await run(new Error("codex offline"), {{ case: "success", value: {{ decision: "BLOCK" }} }}));
  console.log(JSON.stringify(out));
}})();
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            '[{"decision":"ALLOW","stockCalls":0},{"decision":"ALLOW","stockCalls":1},{"decision":"BLOCK","stockCalls":1},{"decision":"BLOCK","stockCalls":1}]',
        )

    def test_upgrades_bad_direct_browser_prompt_guard(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        bad = current.replace(INJECT.DIRECT_BROWSER_PROMPT_GUARD, INJECT.DIRECT_BROWSER_PROMPT_BAD_GUARD, 1)
        fixed = self.run_injector(bad)
        self.assert_current(fixed)
        self.assertNotIn(INJECT.DIRECT_BROWSER_PROMPT_BAD_GUARD, fixed)

    def test_upgrades_transient_main_browser_tool_gate(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        transient = current.replace(INJECT.DIRECT_BROWSER_TOOLS_HOOK, INJECT.DIRECT_BROWSER_TOOLS_TRANSIENT_HOOK, 1)
        self.assert_current(self.run_injector(transient))

    def test_upgrades_subagent_gated_main_browser_tools(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        gated = current.replace(INJECT.DIRECT_BROWSER_TOOLS_HOOK, INJECT.DIRECT_BROWSER_TOOLS_GATED_HOOK, 1)
        self.assert_current(self.run_injector(gated))

    def test_upgrades_browser_only_direct_mode_to_no_gui_tasks(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        legacy = current.replace(INJECT.DIRECT_GUI_TASKS_HOOK, INJECT.DIRECT_GUI_TASKS_LEGACY_HOOK, 1)
        legacy = legacy.replace(INJECT.DIRECT_BROWSER_PROMPT_HOOK, INJECT.DIRECT_BROWSER_PROMPT_LEGACY_HOOK, 1)
        fixed = self.run_injector(legacy)
        self.assert_current(fixed)

    def test_upgrades_gui_only_direct_mode_to_no_hidden_tasks(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        legacy = current.replace(INJECT.DIRECT_BROWSER_PROMPT_HOOK, INJECT.DIRECT_BROWSER_PROMPT_GUI_ONLY_HOOK, 1)
        legacy = legacy.replace(INJECT.DIRECT_MAIN_TASKS_HOOK, INJECT.DIRECT_MAIN_TASKS_NEEDLE, 1)
        self.assert_current(self.run_injector(legacy))

    def test_upgrades_context_preserving_prompt_to_api_first(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        legacy = current.replace(INJECT.DIRECT_BROWSER_PROMPT_HOOK, INJECT.DIRECT_BROWSER_PROMPT_CONTEXT_LEGACY_HOOK, 1)
        self.assert_current(self.run_injector(legacy))

    def test_removes_prompt_vocabulary_gate_without_duplication(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        gated = current.replace(INJECT.DIRECT_BROWSER_PROMPT_HOOK, INJECT.DIRECT_BROWSER_PROMPT_VOCAB_GATED_HOOK, 1)
        self.assert_current(self.run_injector(gated))

    def test_removes_duplicate_old_and_new_browser_prompts(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        duplicated = current.replace(
            INJECT.DIRECT_BROWSER_PROMPT_HOOK,
            INJECT.DIRECT_BROWSER_PROMPT_VOCAB_GATED_BLOCK + INJECT.DIRECT_BROWSER_PROMPT_HOOK,
            1,
        )
        self.assert_current(self.run_injector(duplicated))

    def test_preserves_slim_prompt_control_heading(self):
        """Retitling a keyed base section passes syntax check but aborts startup."""
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        broken = current.replace(
            INJECT.STOCK_REPLY_SECTION_HOOK,
            INJECT.STOCK_REPLY_SECTION_RETITLED_HOOK,
            1,
        )
        self.assert_current(self.run_injector(broken))

    def test_upgrades_empty_task_schema_gates_idempotently(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        legacy = current.replace(INJECT.DIRECT_TASK_TOOLS_GATE_HOOK, INJECT.DIRECT_TASK_TOOLS_GATE_NEEDLE, 1)
        self.assert_current(self.run_injector(legacy))

    def test_decouples_automation_parent_runner_from_browser_rollback(self):
        current = self.run_injector(host_fixture(INJECT.SESSION_NEEDLE))
        legacy = current.replace(INJECT.AUTOMATION_MAIN_THREAD_HOOK, INJECT.AUTOMATION_MAIN_THREAD_LEGACY_HOOK, 1)
        self.assert_current(self.run_injector(legacy))

    def test_fresh_browser_view_prefers_visible_tab(self):
        script = f"""
const makePage = (id, visibility, url) => ({{
  id,
  evaluate: async () => visibility,
  url: () => url,
}});
(async () => {{
  let page;
  const byTarget = new Map([
    ["stale", makePage("signed-out", "hidden", "https://my.waveapps.com/login")],
    ["active", makePage("signed-in", "visible", "https://next.waveapps.com/dashboard")],
  ]);
  const state = {{ lastViewId: "old-worker", views: {{ "old-worker": "stale" }} }};
  if (false) {{
{INJECT.BROWSER_FIRST_VIEW_HOOK}
  console.log(page.id);
}})();
"""
        result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "signed-in")

    def test_scheduled_automation_parent_runner_has_independent_rollback(self):
        script = f"""
const decide = (runAsSubagent, isGroup) => {{
{INJECT.AUTOMATION_MAIN_THREAD_HOOK}
  return shouldRunAsSubagent;
}};
delete process.env.OPENGROK_AUTOMATION_PARENT_RUNNER;
process.env.OPENGROK_DIRECT_BROWSER_MAIN = "0";
const browserRollback = decide(true, false);
process.env.OPENGROK_AUTOMATION_PARENT_RUNNER = "0";
const automationRollback = decide(true, false);
const group = decide(true, true);
console.log(JSON.stringify({{ browserRollback, automationRollback, group }}));
"""
        result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
        self.assertEqual(
            result.stdout.strip(),
            '{"browserRollback":false,"automationRollback":true,"group":false}',
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
