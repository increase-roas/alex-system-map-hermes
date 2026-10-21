#!/usr/bin/env python3
"""One source for global instructions; each tool gets a generated file.

  python3 build_instructions.py init    # first time: split today's two files into ~/.agents/instructions/
  python3 build_instructions.py plan    # show what the generated files would change (default)
  python3 build_instructions.py apply   # back up and write ~/.codex/AGENTS.md, ~/.claude/CLAUDE.md, the styles
                                        # and the CODEX_SETTINGS keys in ~/.codex/config.toml
  python3 build_instructions.py render  # repo-only tools/unify/out: inlined Codex/home rules + personal Claude roles
  python3 build_instructions.py check   # read-only SHA-256 source/generated/installed comparison (exit 1 on drift)

Sources (edit these, never the generated files):
  ~/.agents/instructions/shared.md        hard rules and tool routing for every agent (rule files)
  ~/.agents/instructions/claude.md        Claude-only rules
  ~/.agents/instructions/codex.md         Codex-only rules
  ~/.agents/instructions/shared-style.md  working style for every agent
  ~/.agents/instructions/claude-style.md  Claude voice and format -> output style ~/.claude/output-styles/alex-big-brother.md
  ~/.agents/instructions/codex-style.md   Codex voice and delegation -> developer_instructions in ~/.codex/config.toml;
                                          its APP_SECTIONS ("## Voice", "## Delegation and model routing") also
                                          -> the end of ~/.codex/AGENTS.md (see below)
  CODEX_SETTINGS below                    top-level ~/.codex/config.toml keys the build sets (talk length, progress notes)
Rules load as instructions; voice and working style load as system/developer instructions (Limits tab).
The Codex app never delivers config.toml developer_instructions to its chats (0 of 29 app threads vs 66 of 66
codex exec threads, 2026-10-01/02, master-connector-repo work/2026-10-02_codex-voice/notes/scan.md), so the
APP_SECTIONS of codex-style.md also go into ~/.codex/AGENTS.md, the one file every Codex surface reads: the Voice,
and since Alex 2026-10-02 ("i want the credit saver in codexs app chats") the model routing. The working style
(shared-style.md) stays out. Size: Limits tab row 3 (6,000 characters before the routing; 8,000 with it, a workbook
follow-up in work/2026-10-02_codex-voice/notes/round-2.md). Codex reads at most 32 KiB of AGENTS.md per chat
(project_doc_max_bytes), project files included.
Codex 0.160.0 leaves @path literal (probe_codex_imports.py); Codex and home rules are inlined.
Sources default to this checkout, never a different live checkout. AGENTS_INSTR is an explicit override.
The narrow installer is install_generated.py; roles are never added to this module's broad apply.
"""
import argparse, contextlib, difflib, fcntl, hashlib, json, os, re, stat, sys, tempfile, time, tomllib, uuid
from pathlib import Path

H = os.path.expanduser("~")
ROOT = Path(__file__).resolve().parents[2]
SRC = os.environ.get("AGENTS_INSTR", str(ROOT / "instructions"))
DEFAULT_PROJECT_DOC_MAX_BYTES = 32768
OUT = {"codex": f"{H}/.codex/AGENTS.md", "claude": f"{H}/.claude/CLAUDE.md",
       "claude_style": f"{H}/.claude/output-styles/alex-big-brother.md", "codex_config": f"{H}/.codex/config.toml",
       "cursor": f"{H}/.cursor/rules/agent-routing.mdc", "home_agents": f"{H}/AGENTS.md"}
STYLE_HEAD = ("---\nname: Alex big brother\ndescription: Big-brother voice, explain-it-like-he's-5 answers, autonomous working style\n"
              "keep-coding-instructions: true\n---\n<!-- GENERATED from ~/.agents/instructions/ (claude-style.md + shared-style.md). Edit there, then rebuild. -->\n\n")
DEV_BEGIN, DEV_END = "# BEGIN generated developer_instructions (build_instructions.py)", "# END generated developer_instructions"
HEADER = "<!-- GENERATED from ~/.agents/instructions/ by build_instructions.py. Edit the sources there, then rebuild. -->\n\n"
SHARED_SECTIONS = ["Own the outcome", "Keep execution efficient"]
# Top-level ~/.codex/config.toml keys every rebuild sets (Alex, 2026-10-02; scan: work/2026-10-02_codex-voice).
CODEX_SETTINGS = {"model_verbosity": "low",             # Alex 2026-10-20: "output low is good" (was medium)
                  "model_reasoning_summary": "concise"}  # it defaults to "none": no visible progress while it thinks
# codex-style.md sections the Codex app chats also get, through ~/.codex/AGENTS.md (they never see developer_instructions)
APP_SECTIONS = ["Voice", "Delegation and model routing"]


def sections(text):
    parts = re.split(r"(?m)^(?=# )", text)
    return {p.splitlines()[0][2:].strip() if p.startswith("# ") else "_pre": p.rstrip() + "\n" for p in parts if p.strip()}


def init():
    if os.path.exists(f"{SRC}/shared.md"):
        sys.exit("sources already exist; edit them instead")
    os.makedirs(SRC, exist_ok=True)
    codex = open(OUT["codex"]).read().replace(HEADER, "")
    claude = open(OUT["claude"]).read().replace(HEADER, "")
    sec = sections(codex)
    shared = "\n".join(sec[s] for s in SHARED_SECTIONS if s in sec)
    only = "\n".join(v for k, v in sec.items() if k not in SHARED_SECTIONS)
    open(f"{SRC}/shared.md", "w").write(shared)
    open(f"{SRC}/codex.md", "w").write(only)
    open(f"{SRC}/claude.md", "w").write(claude.rstrip() + "\n")
    print("wrote", SRC, "(shared.md, codex.md, claude.md)")


def assignment_key(line):
    """Find the assignment separator outside quoted TOML key components.

    Let tomllib decode the full key grammar, including escapes and dotted keys.
    Return a canonical simple root key, or None for dotted assignments.
    """
    quote = None
    escaped = False
    for index, character in enumerate(line):
        if quote:
            if quote == '"' and escaped:
                escaped = False
            elif quote == '"' and character == "\\":
                escaped = True
            elif character == quote:
                quote = None
        elif character in ("'", '"'):
            quote = character
        elif character == "#":
            break
        elif character == "=":
            parsed = tomllib.loads(line[:index] + " = 0")
            key, value = next(iter(parsed.items()))
            return key if value == 0 else None
    raise ValueError("could not locate TOML assignment separator")


def top_assignments(config):
    """Locate whole root assignments without interpreting text inside values.

    Every assignment, including arbitrary quoted/dotted keys, is consumed as one
    complete parsed TOML unit. Table headers are considered only between units.
    """
    tomllib.loads(config)
    lines = config.splitlines(keepends=True)
    spans, index = {}, 0
    while index < len(lines):
        stripped = lines[index].lstrip()
        if stripped.startswith("["):
            break
        if not stripped.strip() or stripped.startswith("#"):
            index += 1
            continue
        key = assignment_key(lines[index])
        end = index + 1
        while True:
            try:
                tomllib.loads("".join(lines[index:end]))
                break
            except tomllib.TOMLDecodeError:
                if end >= len(lines):
                    raise ValueError("could not locate complete top-level TOML assignment") from None
                end += 1
        if key is not None:
            spans[key] = (index, end)
        index = end
    return lines, spans, index


def with_dev_instructions(config, text):
    """Replace an existing marked OR unmarked top-level value; never add a duplicate key."""
    if "\'\'\'" in text:
        sys.exit("codex-style.md / shared-style.md can't contain three single quotes")
    block = f"{DEV_BEGIN}\ndeveloper_instructions = \'\'\'\n{text.rstrip()}\n\'\'\'\n{DEV_END}\n"
    lines, spans, table = top_assignments(config)
    if "developer_instructions" in spans:
        start, end = spans["developer_instructions"]
        if start and lines[start - 1].strip() == DEV_BEGIN:
            start -= 1
        if end < len(lines) and lines[end].strip() == DEV_END:
            end += 1
        return "".join(lines[:start]) + block + "".join(lines[end:])
    prefix = "".join(lines[:table])
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    return prefix + block + "\n" + "".join(lines[table:])


def with_settings(config, settings):
    """Replace complete top-level settings only; preserve strings and table-scoped keys."""
    lines, spans, _ = top_assignments(config)
    replacements = {spans[key][0]: (spans[key][1], f"{key} = {json.dumps(value)}\n")
                    for key, value in settings.items() if key in spans}
    output, index = [], 0
    while index < len(lines):
        if index in replacements:
            end, value = replacements[index]
            output.append(value)
            index = end
        else:
            output.append(lines[index])
            index += 1
    return "".join(f"{key} = {json.dumps(value)}\n" for key, value in settings.items() if key not in spans) + "".join(output)


def app_sections(text):
    """The APP_SECTIONS of codex-style.md, in APP_SECTIONS order, as top-level '# ' sections for AGENTS.md.
    Only the heading level changes ('## Voice' -> '# Voice'); every line under a heading is copied as is."""
    parts = {p.splitlines()[0][3:].strip(): p for p in re.split(r"(?m)^(?=## )", text) if p.startswith("## ")}
    for s in APP_SECTIONS:
        if s not in parts:
            sys.exit(f"codex-style.md has no '## {s}' section")
    return "\n".join(parts[s][1:].rstrip() + "\n" for s in APP_SECTIONS)


def read_src(f):
    """App rules stay in the cards. The always-loaded file must not paste a card index."""
    path = f"{SRC}/{f}"
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as stream:
        text = stream.read().rstrip() + "\n"
    if "{{CARD_INDEX}}" in text:
        sys.exit(f"{f} still has {{{{CARD_INDEX}}}}; put the rule in the card, not the always-loaded file")
    return text


def generated_header(body, sources):
    """Hash the UTF-8 payload (not this header); paths are relative to the repo."""
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return ("<!-- GENERATED by tools/unify/build_instructions.py; DO NOT EDIT.\n"
            f"Sources: {', '.join(sources)}\nPayload-SHA256: {digest}\n-->\n\n")


def doc_limit(config):
    value = tomllib.loads(config).get("project_doc_max_bytes", DEFAULT_PROJECT_DOC_MAX_BYTES)
    if type(value) is not int or value <= 0:
        raise ValueError("project_doc_max_bytes must be a positive integer")
    return value


def instruction_docs(config=""):
    shared = read_src("shared.md")
    codex = read_src("codex.md")
    style = read_src("codex-style.md")
    sources = ["instructions/shared.md"]
    body = shared
    if codex:
        body += "\n" + codex
        sources.append("instructions/codex.md")
    if style:
        body += "\n" + app_sections(style)
        sources.append("instructions/codex-style.md (Voice; Delegation and model routing)")
    docs = {"codex": generated_header(body, sources) + body,
            "home_agents": generated_header(shared, ["instructions/shared.md"]) + shared}
    limit = doc_limit(config)
    for name, text in docs.items():
        if re.search(r"(?m)^\s*@\S+\s*$", text):
            raise ValueError(f"{name}: unresolved @import; inline canonical rules instead")
        size = len(text.encode("utf-8"))
        if size > limit:
            raise ValueError(f"{name}: {size} bytes exceeds project_doc_max_bytes={limit}")
    # Both can load together in a project under the user's home directory.
    if sum(len(text.encode("utf-8")) for text in docs.values()) > limit:
        raise ValueError(f"combined Codex and home AGENTS.md exceed project_doc_max_bytes={limit}")
    return docs


def build(baseline=None, *, rules_only=False):
    r = read_src
    if baseline is None:
        baseline = snapshot_outputs()
    state = baseline["codex_config"]
    cfg = state[0].decode("utf-8") if state is not None else ""
    codex_style = r("codex-style.md") + "\n" + r("shared-style.md")
    generated = {**instruction_docs(cfg),
            # Claude Code reads @imports, so it points at the sources instead of a pasted copy (audit 2026-10-13).
            # Codex and Cursor can't, so they keep generated copies.
            "claude": HEADER + "@~/.agents/instructions/claude.md\n@~/.agents/instructions/shared.md\n",
            "claude_style": STYLE_HEAD + r("claude-style.md") + "\n" + r("shared-style.md"),
            "cursor": "---\ndescription: Local shared agent routing and execution rules\nalwaysApply: true\n---\n" + HEADER + r("shared.md"),
            }

    if not rules_only:
        generated["codex_config"] = with_settings(with_dev_instructions(cfg, codex_style), CODEX_SETTINGS)
    return generated


def snapshot(path):
    """Read a regular file once; reject symlinks/FIFOs and detect changes during read."""
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"target is not a regular file: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        data = stream.read()
        after = os.fstat(stream.fileno())
    identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode)
    if identity(before) != identity(opened) or identity(opened) != identity(after):
        raise RuntimeError(f"target changed during read: {path}")
    return data, stat.S_IMODE(after.st_mode), identity(after)


def snapshot_outputs():
    return {key: snapshot(path) for key, path in OUT.items()}


class PlannedChanges(dict):
    def __init__(self, changed, baseline):
        super().__init__(changed)
        self.baseline = baseline


def check_baseline(baseline):
    for key, state in baseline.items():
        if snapshot(OUT[key]) != state:
            raise RuntimeError(f"target changed since plan: {OUT[key]}")


def sans_markers(data: bytes) -> bytes:
    """Codex rewrites config.toml when its app saves a setting and drops comments (2026-10-10, 2026-10-11)."""
    marks = {DEV_BEGIN.encode(), DEV_END.encode()}
    return b"\n".join(line for line in data.split(b"\n") if line.strip() not in marks)


def plan(show=True, *, rules_only=False):
    # The config candidate and comparisons use the SAME initial byte snapshot.
    baseline = snapshot_outputs()
    new = build(baseline, rules_only=True) if rules_only else build(baseline)
    # App-owned config supplies the document budget, never a rules-only write/backup target.
    if rules_only:
        baseline.pop("codex_config")
    config_values = tomllib.loads(new["codex_config"]) if not rules_only else None
    changed = {}
    for k in new:
        path = OUT[k]
        old = baseline[k][0] if baseline[k] is not None else None
        if k == "codex_config" and old is not None and tomllib.loads(old.decode("utf-8")) == config_values:
            continue  # App serialization can change comments, whitespace and strings without changing values.
        if old != new[k].encode("utf-8"):
            changed[k] = new[k]
            if show:
                if k == "codex_config":
                    print(f"{path}: generated settings/instructions would change (values hidden)")
                else:
                    d = difflib.unified_diff((old or b"").decode("utf-8").splitlines(), new[k].splitlines(), path, path + " (generated)", lineterm="", n=1)
                    print("\n".join(d))
    check_baseline(baseline)
    if show:
        print("\nno changes" if not changed else f"\n{len(changed)} file(s) would change: {', '.join(changed)}")
    return PlannedChanges(changed, baseline)


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stage(path, data, mode):
    """Stage on the target filesystem; target bytes remain intact on failure."""
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".build-instructions-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        return name
    except BaseException:
        os.unlink(name)
        raise


@contextlib.contextmanager
def generator_lock(home=None):
    # Lock the full read/build/write sequence for cooperating generator processes.
    directory = os.path.join(H if home is None else home, ".agents")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, ".build-instructions.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError("generator lock is not a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def apply(*, rules_only=False):
    with generator_lock():
        changed = plan(show=False, rules_only=True) if rules_only else plan(show=False)
        if not changed:
            print("already up to date")
            return
        staged = {}
        try:
            for k, text in changed.items():
                old = changed.baseline[k]
                staged[k] = stage(OUT[k], text.encode("utf-8"), old[1] if old is not None else 0o600)
            check_baseline(changed.baseline)
            # All exact-byte backups complete before the first destination replacement.
            bak = os.path.join(H, "Backups", "unify-bak")
            os.makedirs(bak, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex
            for k in changed:
                old = changed.baseline[k]
                if old is not None:
                    destination = os.path.join(bak, os.path.basename(OUT[k]) + f".{k}.bak-{stamp}")
                    temporary = stage(destination, old[0], old[1])
                    try:
                        os.replace(temporary, destination)
                    finally:
                        if os.path.exists(temporary):
                            os.unlink(temporary)
            fsync_dir(bak)
            check_baseline(changed.baseline)
            for k in changed:
                # Narrow the external-writer race; flock cannot lock unrelated writers.
                if snapshot(OUT[k]) != changed.baseline[k]:
                    raise RuntimeError(f"target changed before replace: {OUT[k]}")
                os.replace(staged[k], OUT[k])
                del staged[k]
                fsync_dir(os.path.dirname(OUT[k]))
                print("wrote", OUT[k], "(backup in ~/Backups/unify-bak)")
        finally:
            for temporary in staged.values():
                if os.path.exists(temporary):
                    os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="plan", choices=["init", "plan", "apply", "render", "check"])
    parser.add_argument("--out-dir", type=Path, default=ROOT / "tools/unify/out")
    parser.add_argument("--codex-config", type=Path, help="Budget config; defaults to --home/.codex/config.toml")
    parser.add_argument("--home", type=Path, default=Path(H), help="Read-only installed-home comparison for check")
    parser.add_argument("--rules-only", action="store_true", help="Generate rule documents without changing app-owned Codex config (plan/apply only)")
    args = parser.parse_args()
    if args.rules_only and args.command not in ("plan", "apply"):
        parser.error("--rules-only requires plan or apply")
    config = args.codex_config if args.codex_config is not None else args.home / ".codex/config.toml"
    if args.command in ("render", "check"):
        import generated_bundle
        if args.command == "render":
            generated_bundle.render(args.out_dir, config)
            return 0
        result = generated_bundle.check(args.out_dir, args.home, config)
        print(json.dumps(result, indent=2))
        return int(bool(result["problems"]))
    action = {"init": init, "plan": plan, "apply": apply}[args.command]
    action(rules_only=True) if args.rules_only else action()
    return 0


if __name__ == "__main__":
    sys.exit(main())
