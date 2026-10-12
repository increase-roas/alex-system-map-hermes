#!/usr/bin/env python3
"""Read-only Claude Code asset validator. Python 3.9+, stdlib only.

CLI contract:
  python3 -B asset_guard.py --root /absolute/project --scan
  python3 -B asset_guard.py --root /absolute/project --event PreToolUse < input.json
  python3 -B asset_guard.py --root /absolute/project --print-config
--scan emits {ok, errors, policy, limitations}, exits 0/1. Hook mode reads one
JSON object from stdin, emits {} on success or Anthropic's event-specific deny /
block JSON on failure, exits 0 so Claude consumes that JSON. --event pins the
expected event, including when stdin is malformed. Without it a valid input
hook_event_name is required; undecidable input exits 2 (no fabricated event).
--print-config only prints settings JSON; it never installs or writes settings.
Generated command hooks need Claude Code 2.1.295+: PreToolUse/PostToolUse use
onFailure: block for missing/crashing/timed-out scripts; Stop ignores onFailure.
No custom environment variables. Relative tool paths use input.cwd, falling
back to --root; the root must be explicitly chosen by the integrator.

CUSTOM POLICY (stricter than vendor defaults/recommendations): required skill
name matching folder, lowercase hyphen names <=64 chars, description >=20 chars
with literal 'Use when', <=500 BODY lines, direct local Markdown references
only (root file or one subdirectory, no chains); required agent name/description
and explicit tools; rule paths list OR scope: global (not both); connector card
beside each .mcp.json at .claude/connector-cards/<server>.md; only stdio/http/sse.
All connector env values are exact ${VAR}; headers exact ${VAR} or Bearer ${VAR};
no defaults, shell launch strings, URL credentials/query/fragment, unknown server
fields or inline credential arguments. Public args may be literal. This is a
conservative credential-pattern check, NOT proof arbitrary strings are secret-free.

Frontmatter is an EXPLICIT YAML SUBSET, not a YAML parser: flat unique keys;
plain/JSON-double/YAML-single-quoted scalars; JSON scalar arrays or indented
string lists; simple | / > blocks. Nested mappings, tags, anchors, aliases,
comments in plain values, YAML implicit ambiguous scalars and other forms are
rejected, not silently guessed. For richer vendor YAML use an independently
reviewed real YAML parser in a future version. Unknown flat fields are retained,
not a claim of full skill/agent/settings schema validation.

Scan boundary: recursively under --root (no symlinks), excluding .git,
node_modules, .venv, __pycache__, .next. Recognizes every SKILL.md and .mcp.json,
and .claude/{rules/**/*.md,agents/**/*.md,settings.json,settings.local.json}.
Write/Edit on any skill-support or connector-card file triggers a full overlay
scan, so dependent references/cards are checked without writing. Unrelated
Write/Edit is left to normal permissions; Bash/other tools are not predicted.
PostToolUse/Stop scans all assets, including changes already made by Bash or
external actors, but CANNOT undo them. No daemon, filesystem lock, TOCTOU
guarantee, hook self-protection, global-home scan, vendor runtime availability
check, or connector read authorization. A persistent Stop failure stays blocked
even on stop_hook_active; repair the asset or disable the hook explicitly.

Official sources reviewed 2026-10-12 (live docs, not a pinned JSON Schema):
https://code.claude.com/docs/en/hooks
https://code.claude.com/docs/en/memory
https://code.claude.com/docs/en/skills
https://code.claude.com/docs/en/sub-agents
https://code.claude.com/docs/en/mcp
https://code.claude.com/docs/en/settings
https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import unquote, urlsplit

POLICY = "Claude Code custom policy v1 (not full vendor JSON Schema)"
LIMITATIONS = [
    "Description checks are syntactic; semantic quality is not established.",
    "Bash/external writes are detected after execution; no undo or filesystem lock.",
    "Only the configured root is scanned; symlinks are rejected, excluded trees ignored.",
    "Frontmatter accepts a documented strict YAML subset, not all vendor YAML.",
    "Markdown inline/reference links only; bare prose and dynamic references not resolved.",
    "Credential-pattern checks cannot prove arbitrary literal strings are secret-free.",
    "Settings validation is targeted hook-shape validation, not complete JSON Schema.",
    "Hooks must be installed/enabled by integrator; no self-protection or read gate.",
]
EVENTS = set("SessionStart Setup UserPromptSubmit UserPromptExpansion PreToolUse "
             "PermissionRequest PermissionDenied PostToolUse PostToolUseFailure PostToolBatch "
             "Notification MessageDisplay SubagentStart SubagentStop TaskCreated TaskCompleted "
             "Stop StopFailure TeammateIdle InstructionsLoaded ConfigChange CwdChanged "
             "DirectoryAdded FileChanged WorktreeCreate WorktreeRemove PreCompact PostCompact "
             "PreModelSwitch PostModelSwitch Elicitation ElicitationResult SessionEnd".split())
HOOK_EVENTS = {"PreToolUse", "PostToolUse", "Stop"}
LLM_EVENTS = set("PermissionDenied PostToolBatch PostToolUse PostToolUseFailure "
                 "PreToolUse Stop SubagentStop TaskCompleted TaskCreated TeammateIdle "
                 "UserPromptExpansion UserPromptSubmit".split())
SKIP = {".git", "node_modules", ".venv", "__pycache__", ".next"}
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SERVER = re.compile(r"[A-Za-z0-9_-]+\Z")
ENV = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")
SENSITIVE = re.compile(r"(?i)(?:api[-_]?key|token|secret|password|passwd|authorization|credential)")


class Invalid(ValueError):
    """Messages are static; never include input content or credential values."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def load_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def bad_constant(_):
        raise Invalid("non-finite JSON number")

    def finite_float(value):
        number = float(value)
        require(math.isfinite(number), "non-finite JSON number")
        return number

    try:
        data = json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant,
                          parse_float=finite_float)
    except (ValueError, TypeError):
        raise Invalid("invalid JSON (syntax, duplicate keys or non-finite values)") from None
    require(isinstance(data, dict), "JSON top level must be an object")
    return data


def scalar(value):
    require(bool(value), "empty scalar is unsupported; use an explicit value")
    if value.startswith('"') or value.startswith("["):
        try:
            parsed = json.loads(value)
        except ValueError:
            raise Invalid("unsupported quoted scalar or flow list; use JSON syntax") from None
        require(isinstance(parsed, str) or (isinstance(parsed, list) and
                all(isinstance(x, str) for x in parsed)), "only strings or string lists supported here")
        return parsed
    if value.startswith("'"):
        require(value.endswith("'") and len(value) >= 2, "unclosed single quote")
        inner = value[1:-1]
        require("'" not in inner.replace("''", ""), "unsupported single-quoted scalar")
        return inner.replace("''", "'")
    require(not any(c in value for c in "\t\r\n"), "unsupported whitespace in YAML scalar")
    require(value[0] not in "!&*{}|>@`%#?," and ": " not in value and
            " #" not in value and not value.endswith(":"), "unsupported YAML scalar syntax")
    # Reject rather than silently turn YAML implicit types into strings.
    require(not re.fullmatch(r"(?i:true|false|null|yes|no|on|off|~|[-+]?\.inf|\.nan)", value) and
            not re.match(r"[-+]?\d", value) and not value.startswith("- "),
            "implicit YAML types or sequence syntax unsupported; quote string values")
    return value


def frontmatter(text):
    lines = text.splitlines()
    require(lines and lines[0] == "---", "frontmatter must start on first line")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise Invalid("unclosed frontmatter") from None
    data, i = {}, 1
    while i < end:
        line = lines[i]
        i += 1
        if not line.strip():
            continue
        require("\t" not in line, "tabs unsupported in frontmatter")
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):(?: +(.*))?", line)
        require(match is not None, "unsupported YAML structure; only flat keys supported")
        key, value = match.groups()
        require(key not in data, "duplicate frontmatter key")
        if value in ("|", ">"):
            block = []
            while i < end and (not lines[i].strip() or lines[i].startswith("  ")):
                require("\t" not in lines[i], "tabs unsupported in block scalar")
                require(not lines[i].startswith("   "), "complex block indentation unsupported")
                block.append(lines[i][2:] if lines[i].strip() else "")
                i += 1
            require(bool(block), "empty block scalar")
            # Simple folding only; reject paragraph/chomping semantics we do not implement.
            if value == ">":
                require(all(block), "folded block paragraphs unsupported; use literal block")
            data[key] = ("\n" if value == "|" else " ").join(block) + "\n"
        elif value is None:
            items = []
            while i < end and lines[i].startswith("  - "):
                item = scalar(lines[i][4:])
                require(isinstance(item, str), "nested list unsupported")
                items.append(item)
                i += 1
            require(bool(items), "nested mapping or empty field unsupported")
            data[key] = items
        elif value in ("true", "false"):
            data[key] = value == "true"
        else:
            data[key] = scalar(value)
    body = "\n".join(lines[end + 1:])
    return data, body


def local_links(text):
    """Recognize inline and reference-definition Markdown links, not bare prose."""
    destinations = re.findall(r"!?\[[^\]\n]*\]\(([^\n]*?)\)", text)
    destinations += re.findall(r"(?m)^\s*\[[^\]\n]+\]:\s*(\S+)", text)
    result = []
    for destination in destinations:
        target = destination.strip().split(' "', 1)[0].split(" '", 1)[0].strip("<>")
        if not target or target.startswith("#") or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        require(not target.startswith("//"), "protocol-relative link unsupported")
        result.append(unquote(target.split("#", 1)[0]))
    return result


class Tree:
    def __init__(self, root, overlay=None):
        self.root = root.resolve()
        require(self.root.is_dir(), "root directory does not exist")
        self.overlay = overlay or {}

    def safe(self, path):
        path = Path(os.path.abspath(path))
        require(path.is_relative_to(self.root), "path outside configured root")
        cursor = self.root
        for part in path.relative_to(self.root).parts:
            cursor /= part
            require(not cursor.is_symlink(), "symlink not allowed in asset tree")
        return path

    def read(self, path):
        path = self.safe(path)
        if path in self.overlay:
            return self.overlay[path]
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise Invalid("asset missing, unreadable, or not UTF-8") from None

    def files(self):
        result = set(self.overlay)
        def onerror(_):
            raise Invalid("cannot enumerate configured root")
        for base, dirs, files in os.walk(self.root, followlinks=False, onerror=onerror):
            dirs[:] = [d for d in dirs if d not in SKIP]
            for d in dirs:
                require(not (Path(base) / d).is_symlink(), "symlink directory in scan boundary")
            for name in files:
                path = Path(base) / name
                if kind(path) or self.related(path):
                    self.safe(path)
                    result.add(path)
        return sorted(result)

    def related(self, path):
        parts = path.relative_to(self.root).parts
        if any(p in SKIP for p in parts):
            return False
        if ".claude" in parts:
            idx = parts.index(".claude")
            if idx + 1 < len(parts) and parts[idx + 1] == "connector-cards":
                return True
        for directory in path.parents:
            if not directory.is_relative_to(self.root):
                break
            skill = directory / "SKILL.md"
            if skill in self.overlay or skill.is_file():
                return True
        return False


def kind(path):
    if path.name == "SKILL.md":
        return "skill"
    if path.name == ".mcp.json":
        return "mcp"
    parts = path.parts
    if ".claude" in parts:
        idx = parts.index(".claude")
        tail = parts[idx + 1:]
        if len(tail) == 1 and tail[0] in ("settings.json", "settings.local.json"):
            return "settings"
        if len(tail) >= 2 and path.suffix == ".md" and tail[0] in ("agents", "rules"):
            return tail[0]
    return None


def validate_name(name):
    require(isinstance(name, str) and len(name) <= 64 and NAME.fullmatch(name),
            "custom name policy: lowercase letters/digits/hyphens, 1..64 characters")


def description(value, skill=False):
    require(isinstance(value, str) and len(value.strip()) >= 20,
            "custom description policy: at least 20 characters (syntactic, not semantic quality)")
    if skill:
        require("Use when" in value, "custom skill description must include 'Use when' (syntactic check)")


def skill(tree, path, text):
    fm, body = frontmatter(text)
    validate_name(fm.get("name"))
    require(fm["name"] == path.parent.name, "custom skill folder must equal frontmatter name")
    description(fm.get("description"), skill=True)
    require(len(body.splitlines()) <= 500, "custom skill BODY limit is 500 lines")
    require(nonempty(body), "skill body must not be empty")
    for link in local_links(body):
        reference = Path(link)
        require(not reference.is_absolute() and ".." not in reference.parts and
                1 <= len(reference.parts) <= 2 and "?" not in link,
                "custom references policy: only direct files, at most one subdirectory")
        target = tree.safe(path.parent / reference)
        require(target != path, "self reference unsupported")
        support = tree.read(target)
        require(not local_links(support), "custom references policy: no chained local references")


def rule(text):
    fm, body = frontmatter(text)
    paths = fm.get("paths")
    if "paths" in fm:
        require("scope" not in fm and isinstance(paths, list) and paths and
                all(nonempty(p) for p in paths), "custom rules require nonempty paths list OR scope: global")
    else:
        require(fm.get("scope") == "global", "custom rules require paths or explicit scope: global; vendor paths are optional")
    require(nonempty(body), "rule body must not be empty")


def agent(text):
    fm, body = frontmatter(text)
    validate_name(fm.get("name"))
    description(fm.get("description"))
    tools = fm.get("tools")
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",")]
    require(isinstance(tools, list) and tools and all(nonempty(t) for t in tools),
            "custom subagent policy requires explicit nonempty tools; vendor allows inheritance")
    require(all(re.fullmatch(r"[A-Za-z0-9_.*:-]+(?:\([^\n]*\))?", t) for t in tools),
            "unsupported tool-name syntax")
    require(nonempty(body), "subagent body must not be empty")


def placeholder(text):
    return isinstance(text, str) and ENV.fullmatch(text) is not None


def substitutions(value):
    require(isinstance(value, str), "connector strings required")
    # Only exact ${VAR} expansions; no $VAR, default values or shell substitution.
    cleaned = ENV.sub("ENV_VALUE", value)
    require("$" not in cleaned, "custom connector env placeholder policy: only ${VAR}, no defaults")
    return cleaned


def url(value):
    require(nonempty(value), "HTTP/SSE URL required")
    parsed = urlsplit(substitutions(value))
    if placeholder(value):
        return
    require(parsed.scheme in ("http", "https") and parsed.hostname and
            not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
            "custom URL policy: HTTP(S), no inline credentials/query/fragment")
    try:
        parsed.port
    except ValueError:
        raise Invalid("invalid URL port") from None


def connector(tree, path, text):
    data = load_json(text)
    require(set(data) == {"mcpServers"} and isinstance(data["mcpServers"], dict),
            "custom .mcp.json requires only mcpServers object")
    for name, entry in data["mcpServers"].items():
        require(isinstance(name, str) and SERVER.fullmatch(name), "invalid MCP server name")
        require(isinstance(entry, dict), "MCP entry must be an object")
        transport = entry.get("type", "stdio")
        require(isinstance(transport, str) and transport in ("stdio", "http", "sse"),
                "custom MCP transport policy: stdio/http/sse only")
        allowed = {"type", "command", "args", "env"} if transport == "stdio" else {"type", "url", "headers"}
        allowed |= {"timeout", "alwaysLoad"}
        require(set(entry) <= allowed, "unsupported MCP fields under strict custom policy")
        if "timeout" in entry:
            require(type(entry["timeout"]) is int and entry["timeout"] >= 1000, "MCP timeout must be integer >=1000ms")
        if "alwaysLoad" in entry:
            require(type(entry["alwaysLoad"]) is bool, "MCP alwaysLoad must be boolean")
        if transport == "stdio":
            command = entry.get("command")
            require(nonempty(command), "stdio command required")
            clean = substitutions(command)
            require(not re.search(r"[\s;&|`<>]", clean), "custom stdio command must be one executable, not shell text")
            args = entry.get("args", [])
            require(isinstance(args, list) and all(isinstance(a, str) for a in args), "stdio args must be a string array")
            expect_secret = False
            for arg in args:
                clean = substitutions(arg)
                require(not re.search(r"(?i)(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,})", clean), "credential-like literal argument rejected")
                if expect_secret:
                    require(placeholder(arg), "credential argument must be exact ${VAR}")
                    expect_secret = False
                if SENSITIVE.search(arg) and arg.startswith("-"):
                    if "=" in arg:
                        require(placeholder(arg.split("=", 1)[1]), "credential flag value must be exact ${VAR}")
                    else:
                        expect_secret = True
                elif "=" in arg and SENSITIVE.search(arg.split("=", 1)[0]):
                    require(placeholder(arg.split("=", 1)[1]), "credential assignment must use ${VAR}")
                if "://" in arg:
                    url(arg)
            require(not expect_secret, "credential flag missing value")
            env = entry.get("env", {})
            require(isinstance(env, dict) and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)
                    and placeholder(v) for k, v in env.items()), "custom connector env: every value must be exact ${VAR}")
        else:
            url(entry.get("url"))
            headers = entry.get("headers", {})
            require(isinstance(headers, dict), "headers must be an object")
            for key, value in headers.items():
                require(nonempty(key) and re.fullmatch(r"[A-Za-z0-9-]+", key), "invalid header name")
                require(isinstance(value, str) and (placeholder(value) or
                        (value.startswith("Bearer ") and placeholder(value[7:]))),
                        "custom headers require exact ${VAR} or Bearer ${VAR}")
        card = tree.read(path.parent / ".claude" / "connector-cards" / (name + ".md"))
        require(nonempty(card), "custom connector card must not be empty")


def settings(text):
    data = load_json(text)
    if "hooks" not in data:
        return  # Other settings intentionally outside targeted validation.
    hooks = data["hooks"]
    require(isinstance(hooks, dict), "settings hooks must be an object")
    for event, groups in hooks.items():
        require(event in EVENTS, "unknown hook event in reviewed vendor event set")
        require(isinstance(groups, list), "hook event requires array of matcher groups")
        for group in groups:
            require(isinstance(group, dict), "hook matcher group must be an object")
            require("matcher" not in group or isinstance(group["matcher"], str), "hook matcher must be string")
            handlers = group.get("hooks")
            require(isinstance(handlers, list) and handlers, "hook group requires nonempty hooks array")
            for handler in handlers:
                require(isinstance(handler, dict), "hook handler must be object")
                ht = handler.get("type")
                require(isinstance(ht, str) and ht in ("command", "http", "prompt", "agent", "mcp_tool"), "unsupported hook handler type")
                for field in ("if", "statusMessage"):
                    if field in handler:
                        require(isinstance(handler[field], str), "common hook string field has wrong type")
                if ht in ("prompt", "agent"):
                    require(event in LLM_EVENTS or (ht == "prompt" and event == "PermissionRequest"),
                            "prompt/agent handler unsupported on this vendor hook event")
                if ht == "http":
                    require(event not in ("SessionStart", "Setup"), "HTTP handler unsupported on this vendor hook event")
                if "onFailure" in handler:
                    require(ht in ("command", "http") and handler["onFailure"] in ("block", "continue"),
                            "onFailure must be block/continue on command/http (Claude Code 2.1.295+)")
                for key in ("timeout",):
                    if key in handler:
                        value = handler[key]
                        require(type(value) in (int, float) and math.isfinite(value) and value > 0, "hook timeout must be positive finite number")
                for key in ("async", "asyncRewake", "once"):
                    if key in handler:
                        require(type(handler[key]) is bool, "hook boolean field has wrong type")
                if handler.get("async") or handler.get("asyncRewake"):
                    require(ht == "command" and event == "PostToolUse", "custom async policy permits only command PostToolUse (cannot block)")
                if ht == "command":
                    require(nonempty(handler.get("command")), "command hook requires command string")
                    if "args" in handler:
                        require(isinstance(handler["args"], list) and all(isinstance(a, str) for a in handler["args"]), "hook args must be string array")
                elif ht == "http":
                    url(handler.get("url"))
                    if "headers" in handler:
                        require(isinstance(handler["headers"], dict) and all(isinstance(v, str) for v in handler["headers"].values()), "HTTP hook headers must be string map")
                    if "allowedEnvVars" in handler:
                        require(isinstance(handler["allowedEnvVars"], list) and all(nonempty(v) for v in handler["allowedEnvVars"]), "allowedEnvVars must be string list")
                elif ht == "mcp_tool":
                    require(nonempty(handler.get("server")) and nonempty(handler.get("tool")), "mcp_tool hook requires server and tool")
                    require("input" not in handler or isinstance(handler["input"], dict), "MCP hook input must be object")
                else:
                    require(nonempty(handler.get("prompt")), "prompt/agent hook requires prompt string")
                    require("model" not in handler or nonempty(handler["model"]), "hook model must be nonempty string")


def scan(tree):
    errors = []
    try:
        files = tree.files()
    except Invalid as exc:
        return [{"path": ".", "message": str(exc)}]
    for path in files:
        asset_type = kind(path)
        if not asset_type:
            continue
        try:
            text = tree.read(path)
            if asset_type == "skill":
                skill(tree, path, text)
            elif asset_type == "mcp":
                connector(tree, path, text)
            elif asset_type == "rules":
                rule(text)
            elif asset_type == "agents":
                agent(text)
            else:
                settings(text)
        except (Invalid, OSError, ValueError, RecursionError):
            # Do not expose JSON/YAML content via exception context.
            exc = sys.exc_info()[1]
            message = str(exc) if isinstance(exc, Invalid) else "asset validation failed safely"
            errors.append({"path": str(path.relative_to(tree.root)), "message": message})
    return errors


def proposed(tree, payload):
    tool = payload.get("tool_name")
    require(nonempty(tool), "hook tool_name required")
    if tool not in ("Write", "Edit"):
        return []
    inp = payload.get("tool_input")
    require(isinstance(inp, dict), "Write/Edit tool_input must be object")
    filename = inp.get("file_path")
    require(nonempty(filename), "Write/Edit file_path required")
    cwd = payload.get("cwd", str(tree.root))
    require(nonempty(cwd) and Path(cwd).is_absolute(), "hook cwd must be absolute directory path")
    raw = Path(filename)
    path = tree.safe(raw if raw.is_absolute() else Path(cwd) / raw)
    if not kind(path) and not tree.related(path):
        return []
    require(not any(p in SKIP for p in path.relative_to(tree.root).parts), "proposed asset in excluded tree")
    if tool == "Write":
        value = inp.get("content")
        require(isinstance(value, str), "Write content must be string")
    else:
        old, new = inp.get("old_string"), inp.get("new_string")
        require(isinstance(old, str) and old and isinstance(new, str), "Edit requires nonempty old_string and string new_string")
        replace_all = inp.get("replace_all", False)
        require(type(replace_all) is bool, "Edit replace_all must be boolean")
        current = tree.read(path)
        count = current.count(old)
        require(count > 0, "Edit old_string not found; cannot safely simulate")
        require(replace_all or count == 1, "Edit old_string ambiguous; cannot safely simulate")
        require(old != new, "Edit old_string and new_string must differ")
        value = current.replace(old, new, -1 if replace_all else 1)
    return scan(Tree(tree.root, {path: value}))


def blocked(event, errors):
    # Paths are evidence in --scan; hook reasons never echo potentially sensitive paths.
    reason = POLICY + ": " + "; ".join(e["message"] for e in errors[:8])
    if event == "PreToolUse":
        return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}
    return {"decision": "block", "reason": reason}


def config(root):
    # Exact shell quoting supports spaces in both script and project paths.
    base = "python3 -B " + shlex.quote(str(Path(__file__).resolve())) + " --root " + shlex.quote(str(root))
    return {"hooks": {event: [dict(
        **({"matcher": "Write|Edit"} if event == "PreToolUse" else {}),
        hooks=[{"type": "command", "command": base + " --event " + event,
                **({"onFailure": "block"} if event != "Stop" else {})}])]
        for event in ("PreToolUse", "PostToolUse", "Stop")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, type=Path, help="Explicit project scan boundary")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scan", action="store_true")
    mode.add_argument("--print-config", action="store_true")
    mode.add_argument("--event", choices=sorted(HOOK_EVENTS), help="Pin expected event; recommended for fail-closed malformed stdin")
    args = parser.parse_args()
    event = args.event
    try:
        tree = Tree(args.root)
        if args.print_config:
            print(json.dumps(config(tree.root), indent=2))
            return 0
        if args.scan:
            errors = scan(tree)
            print(json.dumps({"ok": not errors, "errors": errors, "policy": POLICY, "limitations": LIMITATIONS}))
            return 1 if errors else 0
        payload = load_json(sys.stdin.read())
        incoming = payload.get("hook_event_name")
        require(incoming in HOOK_EVENTS if isinstance(incoming, str) else False, "supported hook_event_name required")
        if event:
            require(event == incoming, "hook event disagrees with pinned --event")
        else:
            event = incoming
        errors = proposed(tree, payload) if event == "PreToolUse" else scan(tree)
        print(json.dumps(blocked(event, errors) if errors else {}))
        return 0
    except (Invalid, OSError, ValueError, TypeError, RecursionError):
        exc = sys.exc_info()[1]
        message = str(exc) if isinstance(exc, Invalid) else "validator failed safely"
        errors = [{"path": ".", "message": message}]
        if event:
            print(json.dumps(blocked(event, errors)))
            return 0
        print(json.dumps({"ok": False, "errors": errors, "policy": POLICY}))
        return 1 if args.scan else 2


if __name__ == "__main__":
    sys.exit(main())
