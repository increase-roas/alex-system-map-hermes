# Guardrails template (Claude Code + Hermes)

A ready-to-use kit. Drop it next to any project, run one command, and three rules are enforced:

1. **Skills are added the right way.** A SKILL.md with a bad header (missing name, no "Use when" description, name too long) is refused before it is written.
2. **Connectors are added the right way.** A connector with a pasted key, or with no connector card, is refused. Keys must be `${VAR}` references.
3. **The connector card is read before first use.** Calling a connector tool before reading its whole card in that session is refused. After a full read, the call goes through.

Think of it like a bouncer with a checklist at each door: no proper ID, no entry.

**Status:** seen working live in real Claude Code sessions (v2.1.296) in a test folder on 2026-10-12. See `proof/`. Not installed in any real project yet.

## Claude Code: install in 3 steps

```
python3 install.py --project /absolute/path/to/project --tool mcp__ghl__contacts_list
```
- `--tool` lists each connector tool the project may use (exact name; run `/mcp` in Claude Code to see them). Tools you do not list are refused.
- `--server NAME` adds a connector that lives in your user settings instead of the project's `.mcp.json`.
- `--batches file.json` for "many tools in one call" tools like Composio (copy `templates/batches.example.json`).
- `--dry-run` shows the changes without writing.

Then:
1. Fill in each new card in `<project>/.claude/connector-cards/` (replace every TODO).
2. `python3 check.py --project /absolute/path/to/project` must say **RESULT: PASS**.
3. Restart Claude Code in that project; `/hooks` lists the new hooks.

Undo: `python3 uninstall.py --project /absolute/path/to/project` (backup kept).

## Hermes: install for one profile

```
python3 hermes/install_hermes.py --home ~/.hermes/profiles/NAME --route EXACT_TOOL_NAME=SERVER:SERVER.md
```
It prints a hooks block. Merge it into that profile's `config.yaml`, start Hermes and approve the hooks when asked. Use a test profile first, not a live agent. The Hermes guard is stricter: it blocks routes it cannot check (terminal, patch, delegation, batch) instead of guessing.

## Files

| File | What it is |
|---|---|
| `install.py`, `check.py`, `uninstall.py` | Claude Code installer, checker, remover |
| `hooks/asset_guard.py` | Checks skills, connectors, rules, subagents and settings before they are written |
| `hooks/read_gate.py` | Refuses a connector call until its card has been fully read |
| `hermes/hermes_guard.py`, `hermes/install_hermes.py` | Same idea for Hermes |
| `templates/` | Connector card, SKILL.md, `.mcp.json` and batch examples in the official formats |
| `proof/` | Live run receipt and transcripts |

## Sticky notes (first-timer gotchas)

- Needs Python 3.9+ and Claude Code 2.1.295+ (for `onFailure: "block"`, so a crashed hook blocks instead of letting the call through).
- Claude Code always asks before an agent writes inside `.claude/`. That prompt is separate from these hooks; both apply.
- A card read only counts in the same session, and only if the whole file was read. Editing a card means it must be read again.
- These hooks run as your user. They stop honest mistakes; they are not a lock against someone who can edit your files. For that, use managed settings.
- Client walls (which customer account a call may touch) and spend/send/delete approval are separate checks, not part of this kit.

Sources: [Hooks](https://code.claude.com/docs/en/hooks), [Skills best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [MCP](https://code.claude.com/docs/en/mcp), [Hermes hooks](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks).
