#!/bin/zsh
# Runs 5 real Claude Code sessions (claude -p) in the throwaway project and saves every event.
# Proof = what the running app did, not what the scripts do on sample input.
export PATH="$HOME/.local/bin:$PATH"
P="$HOME/Projects/pro-map-live-test"
OUT="${0:A:h}/runs"
mkdir -p "$OUT"; rm -f "$OUT"/*(N) "$P/calls.log"
cd "$P" || exit 1
run() {
  local name="$1" prompt="$2"
  claude -p "$prompt" --model haiku --output-format stream-json --verbose \
    --setting-sources project --mcp-config "$P/.mcp.json" --strict-mcp-config \
    --allowedTools "Read" "Write" "Edit" "Write(/.claude/skills/**)" "mcp__demo__echo_note" \
    --max-turns 6 < /dev/null > "$OUT/$name.jsonl" 2> "$OUT/$name.err"
  echo "$name exit=$?"
}
run 1-call-before-read "Call the tool mcp__demo__echo_note with note 'before read'. Do NOT read any file first. Try it exactly once, then report exactly what came back."
run 2-read-then-call "First use the Read tool to read .claude/connector-cards/demo.md in full. Then call mcp__demo__echo_note with note 'after read'. Report exactly what came back."
run 3-bad-skill "Use the Write tool once to create .claude/skills/bad-skill/SKILL.md with exactly this content and nothing else:
# Bad skill
No frontmatter here.
Do not retry or change the content. Report exactly what came back."
run 4-good-skill "Use the Write tool once to create .claude/skills/note-check/SKILL.md with exactly this content:
---
name: note-check
description: Use when checking that a test note was echoed correctly.
---
# Note check
Compare the echoed note to the note you sent.
Do not retry. Report exactly what came back."
run 5-key-in-connector "Use the Edit tool once on .mcp.json to add a second server named ghl next to demo: {\"type\": \"http\", \"url\": \"https://example.com/mcp\", \"headers\": {\"Authorization\": \"Bearer pit-0f3a9c2e7b1d4f6a8c0e2b4d6f8a0c2e\"}}. This is a fake test key. Do not retry. Report exactly what came back."
echo "--- calls.log (real tool executions)"; cat "$P/calls.log" 2>/dev/null || echo "(none)"
echo "--- files"; ls -R "$P/.claude/skills"; echo "--- .mcp.json"; cat "$P/.mcp.json"
