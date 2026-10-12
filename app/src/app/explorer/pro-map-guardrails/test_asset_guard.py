"""Real CLI/hook contract tests. Run with python3 -B test_asset_guard.py.

Every subprocess runs the production script with JSON stdin. Temporary fixture
trees live ONLY beside this file and cleanup removes only each owned tree.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "asset_guard.py"
SKILL = "---\nname: sample\ndescription: Use when checking sample assets for correctness.\n---\n# Sample\nValidate the input.\n"
AGENT = "---\nname: reviewer\ndescription: Review proposed assets for correctness.\ntools: Read, Grep\n---\nReview only.\n"


class AssetGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="asset-guard-fixture-", dir=HERE)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def put(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def run_guard(self, payload=None, *flags):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), *flags],
            input=json.dumps(payload) if payload is not None else "",
            text=True, capture_output=True, timeout=15,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertTrue(SCRIPT.is_file(), "production validator not implemented")
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertTrue(result.stdout.strip(), result)
        return result.returncode, json.loads(result.stdout)

    def scan(self, valid):
        code, data = self.run_guard(None, "--scan")
        self.assertEqual(code, 0 if valid else 1, data)
        self.assertEqual(data["ok"], valid, data)
        if not valid:
            self.assertTrue(data["errors"], data)
        return data

    def pre(self, path, content=None, tool="Write", **extra):
        args = {"file_path": path, **extra}
        if content is not None:
            args["content"] = content
        return self.run_guard({"hook_event_name": "PreToolUse", "cwd": str(self.root),
                               "tool_name": tool, "tool_input": args})

    def deny(self, result):
        code, data = result
        self.assertEqual(code, 0, data)  # JSON decisions must exit zero.
        self.assertEqual(data["hookSpecificOutput"]["permissionDecision"], "deny", data)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertTrue(data["hookSpecificOutput"]["permissionDecisionReason"])

    def connector(self, entry, name="demo", card=True):
        self.put(".mcp.json", json.dumps({"mcpServers": {name: entry}}))
        if card:
            self.put(f".claude/connector-cards/{name}.md", "# Connector\nRead-only custom card.\n")

    def test_valid_project_and_vendor_optional_stdio_type(self):
        self.put(".claude/skills/sample/SKILL.md", SKILL)
        self.put(".claude/agents/reviewer.md", AGENT)
        self.put(".claude/rules/python.md", '---\npaths:\n  - "src/**/*.py"\n---\nCheck Python.\n')
        self.connector({"command": "python3", "args": ["server.py"], "env": {"KEY": "${DEMO_KEY}"}})
        self.put(".claude/settings.json", '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"python3 -B guard.py"}]}]}}')
        self.scan(True)

    def test_skill_required_name_length_folder_description_and_body(self):
        path = ".claude/skills/sample/SKILL.md"
        for bad in [SKILL.replace("name: sample", "name: " + "a" * 65),
                    SKILL.replace("name: sample", "name: other"),
                    SKILL.replace("name: sample\n", ""),
                    SKILL.replace("Use when checking sample assets for correctness.", "Good"),
                    SKILL.replace("Use when", "Used for"),
                    SKILL + "line\n" * 499]:
            with self.subTest(content=bad[:80]):
                self.put(path, bad)
                self.scan(False)
        self.put(path, SKILL + "line\n" * 498)  # Exactly 500 body lines.
        self.scan(True)

    def test_skill_name_boundary(self):
        name = "a" * 64
        self.put(f"skills/{name}/SKILL.md", SKILL.replace("name: sample", "name: " + name))
        self.scan(True)

    def test_frontmatter_rejects_unsupported_yaml_and_duplicates(self):
        for fm in ["name: sample\nname: sample", "name: &anchor sample", "name: *alias",
                   "name: !!str sample", 'name: {value: sample}', 'name: "sample',
                   "name: sample # comment", "metadata:\n  nested: value",
                   "name: yes", "name:\t sample", "name: sample\n---\n"]:
            with self.subTest(fm=fm):
                self.put("skills/sample/SKILL.md", "---\n" + fm + "\ndescription: Use when checking sample inputs.\n---\nBody\n")
                self.scan(False)

    def test_frontmatter_quotes_blocks_and_lists(self):
        self.put("skills/sample/SKILL.md", "---\nname: 'sample'\ndescription: >\n  Use when checking assets\n  for correctness.\nallowed-tools: [\"Read\", \"Grep\"]\n---\nBody\n")
        self.put(".claude/rules/global.md", "---\nscope: global\n---\nGlobal policy.\n")
        self.scan(True)

    def test_frontmatter_missing_or_unclosed(self):
        for value in ["No frontmatter", "---\nname: sample\n", "\n" + SKILL]:
            self.put("skills/sample/SKILL.md", value)
            self.scan(False)

    def test_references_direct_existing_only_and_no_chains(self):
        self.put("skills/sample/SKILL.md", SKILL + "[Guide](references/guide.md)\n")
        self.scan(False)
        self.put("skills/sample/references/guide.md", "# Guide\n")
        self.scan(True)
        self.put("skills/sample/references/guide.md", "[Other](other.md)\n")
        self.put("skills/sample/references/other.md", "Other\n")
        self.scan(False)
        self.put("skills/sample/references/guide.md", "Guide\n")
        for link in ["references/deep/guide.md", "../outside.md", "/outside.md"]:
            self.put("skills/sample/SKILL.md", SKILL + f"[Guide]({link})\n")
            self.scan(False)
        self.put("skills/sample/SKILL.md", SKILL + "[Official](https://code.claude.com/docs/en/skills)\n")
        self.scan(True)

    def test_rule_requires_paths_or_explicit_global_custom_policy(self):
        for value in ["Global per vendor but not custom", "---\npaths: []\n---\nBody",
                      "---\npaths: '**/*.py'\n---\nBody", "---\nscope: local\n---\nBody",
                      "---\npaths: [\"src/**\"]\nscope: global\n---\nBody"]:
            self.put(".claude/rules/nested/rule.md", value)
            self.scan(False)
        self.put(".claude/rules/nested/rule.md", "---\npaths: [\"src/**\"]\n---\nBody")
        self.scan(True)

    def test_subagent_explicit_required_fields(self):
        for key in ["name: reviewer\n", "description: Review proposed assets for correctness.\n", "tools: Read, Grep\n"]:
            self.put(".claude/agents/reviewer.md", AGENT.replace(key, ""))
            self.scan(False)
        for tools in ["[]", '""', '"Read,,Grep"', "[1]", "true"]:
            self.put(".claude/agents/reviewer.md", AGENT.replace("Read, Grep", tools))
            self.scan(False)
        self.put(".claude/agents/reviewer.md", AGENT.replace("Read, Grep", '["Read", "Grep"]'))
        self.scan(True)

    def test_mcp_valid_http_and_sse(self):
        for transport in ["http", "sse"]:
            self.connector({"type": transport, "url": "https://example.com/mcp",
                            "headers": {"Authorization": "Bearer ${DEMO_KEY}"}})
            self.scan(True)

    def test_mcp_rejects_missing_card_empty_card_and_bad_name(self):
        self.connector({"command": "python3"}, card=False)
        self.scan(False)
        self.put(".claude/connector-cards/demo.md", " ")
        self.scan(False)
        self.connector({"command": "python3"}, name="bad.name", card=False)
        self.scan(False)

    def test_mcp_invalid_shapes_and_transport(self):
        for entry in [None, [], {}, {"type": "ws", "url": "wss://example.com"},
                      {"type": "http", "command": "python3"}, {"url": "https://example.com"},
                      {"command": ""}, {"command": "python3", "args": "server.py"},
                      {"command": "python3", "args": [1]},
                      {"command": "python3", "env": []},
                      {"type": "stdio", "command": "python3", "url": "https://example.com"}]:
            with self.subTest(entry=entry):
                self.connector(entry)
                self.scan(False)
        for obj in [{}, {"mcpServers": []}, {"mcpServers": {"": {"command": "python3"}}}]:
            self.put(".mcp.json", json.dumps(obj))
            self.scan(False)

    def test_mcp_strict_placeholders_no_inline_secret_or_fallback(self):
        for entry in [
            {"command": "python3", "env": {"KEY": "fake-inline-value"}},
            {"command": "python3", "env": {"KEY": "${KEY:-fake}"}},
            {"command": "python3", "env": {"KEY": "$KEY"}},
            {"command": "python3", "env": {"KEY": "prefix-${KEY}"}},
            {"command": "python3", "args": ["--token", "fake-inline-value"]},
            {"command": "python3", "args": ["--api-key=fake-inline-value"]},
            {"command": "sh -c 'echo fake-inline-value'"},
            {"type": "http", "url": "https://user:fake@example.com/mcp"},
            {"type": "http", "url": "https://example.com/mcp?token=fake"},
            {"type": "http", "url": "https://example.com", "headers": {"Authorization": "Bearer fake"}},
            {"type": "http", "url": "https://example.com", "headersHelper": "echo fake"},
            {"command": "python3", "token": "fake"},
        ]:
            with self.subTest(entry=entry):
                self.connector(entry)
                data = self.scan(False)
                self.assertNotIn("fake-inline-value", json.dumps(data))
        self.connector({"command": "python3", "args": ["--token", "${DEMO_KEY}"]})
        self.scan(True)

    def test_json_invalid_duplicate_keys_and_nonfinite(self):
        for value in ['{', '{"hooks":{},"hooks":{}}', '{"timeout":NaN}', '[]']:
            self.put(".claude/settings.json", value)
            self.scan(False)
        self.put(".claude/settings.json", "{}")
        for value in ['{', '{"mcpServers":{},"mcpServers":{}}']:
            self.put(".mcp.json", value)
            self.scan(False)

    def test_settings_targeted_hook_validation(self):
        for hooks in [[], {"ImaginaryEvent": []}, {"Stop": {}}, {"Stop": [{}]},
                      {"Stop": [{"matcher": 1, "hooks": []}]},
                      {"Stop": [{"hooks": [{"type": "command"}]}]},
                      {"Stop": [{"hooks": [{"type": "bad", "command": "x"}]}]},
                      {"Stop": [{"hooks": [{"type": "command", "command": "x", "timeout": -1}]}]},
                      {"PreToolUse": [{"hooks": [{"type": "command", "command": "x", "async": True}]}]},
                      {"Stop": [{"hooks": [{"type": "http", "url": "not-url"}]}]},
                      {"Stop": [{"hooks": [{"type": "prompt", "prompt": 7}]}]},
                      {"Stop": [{"hooks": [{"type": "mcp_tool", "server": "demo"}]}]}]:
            with self.subTest(hooks=hooks):
                self.put(".claude/settings.local.json", json.dumps({"hooks": hooks}))
                self.scan(False)
        self.put(".claude/settings.local.json", json.dumps({"unvalidatedVendorSetting": {"anything": True},
            "hooks": {"Stop": [{"hooks": [{"type": "prompt", "prompt": "Review $ARGUMENTS"},
                {"type": "agent", "prompt": "Review"}, {"type": "http", "url": "https://example.com"},
                {"type": "mcp_tool", "server": "demo", "tool": "review"}]}]}}))
        self.scan(True)  # Deliberately NOT a complete vendor JSON Schema.

    def test_write_simulates_without_writing(self):
        path = ".claude/skills/sample/SKILL.md"
        code, data = self.pre(path, SKILL)
        self.assertEqual((code, data), (0, {}))
        self.assertFalse((self.root / path).exists())
        self.deny(self.pre(path, SKILL.replace("Use when", "Used for")))
        self.assertFalse((self.root / path).exists())

    def test_edit_single_replace_and_replace_all(self):
        target = self.put("skills/sample/SKILL.md", SKILL + "echo echo\n")
        before = target.read_bytes()
        self.deny(self.pre(str(target), tool="Edit", old_string="Use when", new_string="Used for"))
        self.assertEqual(self.pre(str(target), tool="Edit", old_string="echo", new_string="okay", replace_all=True), (0, {}))
        self.deny(self.pre(str(target), tool="Edit", old_string="echo", new_string="okay"))
        self.assertEqual(target.read_bytes(), before)

    def test_malformed_edits_fail_closed(self):
        target = self.put("skills/sample/SKILL.md", SKILL)
        for extra in [{}, {"old_string": "", "new_string": "x"},
                      {"old_string": "absent", "new_string": "x"},
                      {"old_string": 3, "new_string": "x"},
                      {"old_string": "sample", "new_string": "x", "replace_all": "true"}]:
            self.deny(self.pre(str(target), tool="Edit", **extra))
        self.deny(self.pre("skills/missing/SKILL.md", tool="Edit", old_string="x", new_string="y"))

    def test_pre_validates_reference_and_card_edits_as_whole_overlay(self):
        self.put("skills/sample/SKILL.md", SKILL + "[Ref](references/ref.md)\n")
        ref = self.put("skills/sample/references/ref.md", "Reference\n")
        self.deny(self.pre(str(ref), "[Chained](other.md)"))
        self.connector({"command": "python3"})
        self.deny(self.pre(".claude/connector-cards/demo.md", " "))

    def test_pre_allows_repair_of_invalid_file(self):
        self.put("skills/sample/SKILL.md", "broken")
        self.assertEqual(self.pre("skills/sample/SKILL.md", SKILL), (0, {}))

    def test_pre_other_tools_not_predicted_and_unrelated_write_not_validated(self):
        self.put("skills/sample/SKILL.md", "broken")
        self.assertEqual(self.pre("normal.txt", "ordinary content"), (0, {}))
        self.assertEqual(self.run_guard({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                       "tool_input": {"command": "external-change"}}), (0, {}))

    def test_post_and_stop_full_scan_block_but_never_undo(self):
        target = self.put(".claude/rules/external.md", "external invalid change")
        for event in ["PostToolUse", "Stop"]:
            code, data = self.run_guard({"hook_event_name": event, "tool_name": "Bash",
                                        "tool_input": {"command": "external-change"}, "stop_hook_active": True})
            self.assertEqual(code, 0)
            self.assertEqual(data["decision"], "block")
            self.assertIn("custom policy", data["reason"])
            self.assertEqual(target.read_text(), "external invalid change")
        self.put(".claude/rules/external.md", "---\nscope: global\n---\nRule\n")
        self.assertEqual(self.run_guard({"hook_event_name": "Stop"}), (0, {}))

    def test_hook_input_errors_have_event_specific_fail_closed_decisions(self):
        for payload in [{"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {}},
                        {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": []},
                        {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": 2}}]:
            self.deny(self.run_guard(payload))
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(self.root),
                                 "--event", "Stop"], input="{", text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")

    def test_outside_root_and_symlinks_deny_without_reading_outside(self):
        self.deny(self.pre("../outside/SKILL.md", SKILL))
        link = self.root / ".claude"
        link.symlink_to(HERE, target_is_directory=True)
        self.deny(self.pre(".claude/skills/sample/SKILL.md", SKILL))
        self.scan(False)

    def test_print_config_is_runnable_hook_contract(self):
        code, config = self.run_guard(None, "--print-config")
        self.assertEqual(code, 0)
        hooks = config["hooks"]
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "Write|Edit")
        self.assertNotIn("matcher", hooks["Stop"][0])
        self.assertNotIn("matcher", hooks["PostToolUse"][0])  # All tools, including Bash.
        for event, groups in hooks.items():
            handler = groups[0]["hooks"][0]
            if event in ("PreToolUse", "PostToolUse"):
                self.assertEqual(handler["onFailure"], "block")
            else:
                self.assertNotIn("onFailure", handler)
            command = groups[0]["hooks"][0]["command"]
            self.assertIn(" -B ", command)
            self.assertIn(f"--event {event}", command)
        self.put(".claude/settings.json", json.dumps(config))
        self.scan(True)

    def test_settings_failure_policy_and_unsupported_handler_events(self):
        for event, handler in [
            ("PreToolUse", {"type": "command", "command": "python3", "onFailure": "maybe"}),
            ("SessionStart", {"type": "prompt", "prompt": "Review"}),
            ("PermissionRequest", {"type": "agent", "prompt": "Review"}),
        ]:
            self.put(".claude/settings.json", json.dumps({"hooks": {event: [{"hooks": [handler]}]}}))
            self.scan(False)

    def test_frontmatter_does_not_misparse_yaml_implicit_dates_numbers_or_types(self):
        for value in ["2026-10-12", "0x12", ".nan", "- item", "? key", "|+", ">-"]:
            self.put("skills/sample/SKILL.md", SKILL.replace("name: sample", f"name: sample\nextra: {value}"))
            self.scan(False)

    def test_generated_commands_execute_from_different_cwd(self):
        import shlex
        _, config = self.run_guard(None, "--print-config")
        for event, groups in config["hooks"].items():
            command = groups[0]["hooks"][0]["command"]
            payload = {"hook_event_name": event, "tool_name": "Write",
                       "cwd": str(self.root), "tool_input": {"file_path": "skills/sample/SKILL.md", "content": SKILL}}
            result = subprocess.run(shlex.split(command), input=json.dumps(payload),
                                    cwd=HERE, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {})

    def test_pre_write_checks_every_asset_family(self):
        for path, content in [
            (".claude/agents/reviewer.md", AGENT.replace("tools: Read, Grep\n", "")),
            (".claude/rules/rule.md", "No explicit scope"),
            (".claude/settings.json", "{"),
            (".mcp.json", '{"mcpServers":{"demo":{"type":"http","url":"https://example.com"}}}'),
        ]:
            with self.subTest(path=path):
                self.deny(self.pre(path, content))
                self.assertFalse((self.root / path).exists())

    def test_nonfinite_json_exponent_and_malformed_write(self):
        self.put(".claude/settings.json", '{"other":1e999}')
        self.scan(False)
        self.deny(self.pre("skills/sample/SKILL.md", tool="Write"))

    def test_settings_common_handler_fields_types(self):
        for field, value in [("if", 1), ("statusMessage", []), ("onFailure", "bad"),
                             ("args", [1]), ("async", "true")]:
            handler = {"type": "command", "command": "python3", field: value}
            self.put(".claude/settings.json", json.dumps({"hooks": {"PreToolUse": [{"hooks": [handler]}]}}))
            self.scan(False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
