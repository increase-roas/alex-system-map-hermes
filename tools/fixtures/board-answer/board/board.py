#!/usr/bin/env python3
"""Task board (plan item 0.1, Alex 2026-10-14): one task list + one append-only progress log for every agent.

Pattern: Anthropic, "Effective harnesses for long-running agents" (task list + progress log + a commit per step,
read both at every session start). Board: ~/.agents/board/tasks.json; log: ~/.agents/board/progress.md.
Rules live at the top of tasks.json. Edit the board only with this tool: every write takes a lock and replaces
the file atomically, so two agents never overwrite each other.

  board.py summary                          short session-start view (empty when there is no board)
  board.py show [--mission M] [--status S] [--owner O] [--limit N] [--offset N]   tickets, one line each, paged
  board.py claim <ticket> --owner <agent:session>   open -> doing; prints a lease token; refuses a fresh claim
  board.py done <ticket> --lease <t> --proof "<...>"  doing -> done; proof required (output path, log id, PR)
    Reworded finish line: --reworded-by "<Alex's quoted words>" --reworded-source "<transcript/record + UTC>"
    Both citation fields are required and recorded; callers must verify the actual human source.
  board.py block <ticket> --lease <t> --on <who> --need "<one action>" --kind <approval|denial|external>
    --approval-item-id <decision-page item id> | --denial-source <local record path> --denial-scope <exact action>
    | --external-prerequisite <what must happen>; all kinds also require --resume-predicate '<JSON>'
    Resume JSON: {"ticket":"mission-03","status":"done"} or {"path":"read.json","field":"decision","equals":"YES"}.
    Paths are absolute or relative to the repo holding board/. Approval predicates must read a JSON object whose
    item_id (answer) or id (item) matches approval_item_id. JSON fields are top-level; no commands are executed.
    Denial sources must be JSON objects with an id or item_id, decision "NO", and scope matching denial_scope
    byte for byte. If both identifiers exist they must agree. Locate the actual denial; never invent a record.
    This identifies a prerequisite, NOT an approval: fresh exact-scope approval/permission checks still apply.
  board.py release <ticket> --lease <t>     back to open, owner cleared   (--force overrides a lease; logged)
  board.py note <ticket> "<text>"           progress line only, status unchanged
    block/note --link "<exact settings URL>" (or "none: <why>") stores ticket.link for Alex's asks (plan D4)
  board.py add --mission M --source-item 0.2 --step N --title T --done-means D [--part b] [--owner alex]
  board.py sync                             derive plan status from tickets, regenerate plans/INDEX.md (0.8)
  board.py check                            validate the board; exit 1 on problems
  board.py blockers --check                 read-only stale/opaque blocker report; exit 1 if any need reconciliation
    Opaque = missing/invalid structure or unresolvable record; stale = resume predicate matches saved evidence.
    Legacy free-text rows still load/show, but are reported. No check unblocks tickets or clears other gates.

Every transition also moves the mission's plan status (approved -> running -> done, never from draft, never back to
approved, never when the plan body changed after approval) and regenerates plans/INDEX.md. With AGENTS_BOARD_COMMIT=1
it also commits that board state to main with "[skip ci]" (commit per step; off until Alex approves, ticket -03).

Every transition appends one progress line. AGENTS_BOARD_DIR overrides the board folder (tests).
"""
import argparse, calendar, contextlib, fcntl, hashlib, json, os, re, secrets, stat, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import short_output  # noqa: E402  (aof-58: paged, clipped results)

STATUSES = ("open", "doing", "blocked", "done")
LEASE_HOURS = 12  # a "doing" ticket untouched this long may be claimed by another owner
BLOCKER_KINDS = ("approval", "denial", "external")
MAX_BLOCKER_RECORD_BYTES = 1024 * 1024  # Local decision/prerequisite records, not bulk exports.
BLOCKER_FIELDS = ("blocker_kind", "approval_item_id", "denial_source", "denial_scope", "external_prerequisite",
                  "resume_predicate")


def board_dir():
    return os.environ.get("AGENTS_BOARD_DIR") or os.path.join(os.path.expanduser("~"), ".agents", "board")


def database_export(board):
    """The database exporter owns this projection, including its schema evolution."""
    return isinstance(board, dict) and board.get("source") == "director.tasks"


def require_legacy_writes(board=None):
    """Refuse before creating locks/journals or changing any board/plan bytes.

    Check the on-disk authority even when a caller supplies an old in-memory
    board. Only the database exporter may replace a database projection.
    """
    if database_export(board):
        sys.exit("board: director.tasks is a generated read-only export; use the task-list MCP for mutations")
    try:
        current = load()
    except FileNotFoundError:
        return  # Preserve legacy helpers that initialize a missing board.
    if database_export(current):
        sys.exit("board: director.tasks is a generated read-only export; use the task-list MCP for mutations")


def display_tickets(board):
    return board["tasks"] if database_export(board) else board["tickets"]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ticket_hash(t):
    """Approval binding: an edit to a ticket's title or done_means voids its approval."""
    return hashlib.sha256((t.get("title", "") + "\n" + t.get("done_means", "")).encode()).hexdigest()[:16]


@contextlib.contextmanager
def locked():
    require_legacy_writes()
    d = board_dir()
    with open(os.path.join(d, ".lock"), "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            require_legacy_writes()
            recover_answer()
            yield
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def load():
    with open(os.path.join(board_dir(), "tasks.json"), encoding="utf-8") as f:
        return json.load(f)


def save(board):
    require_legacy_writes(board)
    d = board_dir()
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tasks.", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(board, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, os.path.join(d, "tasks.json"))


def log(ticket_id, status, owner, text):
    require_legacy_writes()
    line = f"- {now()} | {ticket_id} | {status} | {owner or '-'} | {' '.join(str(text).split())}\n"
    with open(os.path.join(board_dir(), "progress.md"), "a", encoding="utf-8") as f:
        f.write(line)


def prepare_answer(ticket_id, operation):
    """Write rollback metadata before touching progress. Caller holds the lock.

    This is process-interruption recovery, not an atomic two-file transaction or
    a power-loss guarantee. All board writers must use the same lock.
    """
    require_legacy_writes()
    d = board_dir()
    progress = os.path.join(d, "progress.md")
    offset = os.path.getsize(progress) if os.path.exists(progress) else 0
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".answer.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"ticket": ticket_id, "operation": operation, "progress_offset": offset}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, os.path.join(d, ".answer-pending.json"))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def recover_answer():
    """Keep a committed answer's line; roll back an uncommitted/torn append.

    Called before every locked write, so another writer cannot extend the log
    before recovery. Leave the journal in place if recovery fails; refuse writes.
    """
    require_legacy_writes()
    d = board_dir()
    pending = os.path.join(d, ".answer-pending.json")
    if not os.path.exists(pending):
        return
    with open(pending, encoding="utf-8") as f:
        entry = json.load(f)
    if not isinstance(entry, dict) or set(entry) != {"ticket", "operation", "progress_offset"}:
        raise ValueError("board: invalid pending answer journal schema; no writes performed")
    if not isinstance(entry["ticket"], str) or not entry["ticket"]:
        raise ValueError("board: invalid pending answer ticket; no writes performed")
    if not isinstance(entry["operation"], str) or not re.fullmatch(r"[0-9a-f]{32}", entry["operation"]):
        raise ValueError("board: invalid pending answer operation; no writes performed")
    progress = os.path.join(d, "progress.md")
    size = os.path.getsize(progress) if os.path.exists(progress) else 0
    offset = entry["progress_offset"]
    if type(offset) is not int or not 0 <= offset <= size:
        raise ValueError("board: invalid pending answer progress offset; no writes performed")
    board = load()
    tickets = [t for t in board["tickets"] if t.get("id") == entry["ticket"]]
    if len(tickets) != 1:
        raise ValueError("board: pending answer ticket must exist exactly once; no writes performed")
    answers = tickets[0].get("answers", [])
    if not isinstance(answers, list) or any(not isinstance(a, dict) for a in answers):
        raise ValueError("board: invalid pending answer ticket answers; no writes performed")
    committed = any(a.get("operation") == entry["operation"] for a in answers)
    if not committed:
        if os.path.exists(progress):
            with open(progress, "r+b") as f:
                f.truncate(entry["progress_offset"])
                f.flush()
                os.fsync(f.fileno())
    os.unlink(pending)


def find(board, ticket_id):
    for t in board["tickets"]:
        if t["id"] == ticket_id:
            return t
    sys.exit(f"board: no ticket {ticket_id!r} (board.py show lists them)")


def _age_hours(stamp):
    try:
        return (time.time() - calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))) / 3600
    except (TypeError, ValueError):
        return 1e9


def lanes(board, mission):
    """-> {lane name: set of ticket ids} from missions.<m>.lanes (Alex 2026-10-14 lane split); 'main' = the rest."""
    raw = (board.get("missions", {}).get(mission) or {}).get("lanes") or {}
    return {k: set(v.get("tickets") or []) for k, v in raw.items() if isinstance(v, dict) and "tickets" in v}


def ticket_lane(board, t):
    return next((name for name, ids in lanes(board, t.get("mission")).items() if t["id"] in ids), "main")


def owner_lane(board, mission, owner):
    """An owner like 'claude-code:lane-javar' belongs to lane-javar; any owner naming no lane is the main lane."""
    return next((name for name in lanes(board, mission) if name in (owner or "")), "main")


def check_link(link):
    """--link: the deepest page Alex acts on (exact settings URL), or "none: <why no page exists>" (plan D4)."""
    if link is not None and not link.strip():
        sys.exit("board: --link needs the exact settings URL, or \"none: <why no page exists>\"")
    return link.strip() if link is not None else None


def read_blocker_record(path):
    """Bound local evidence I/O, including a regular path replaced with a FIFO before open."""
    path = os.path.join(root(), path)
    regular_error = "record must be a regular file, not a pipe, device or directory; use a saved JSON file"
    if not stat.S_ISREG(os.stat(path).st_mode):
        raise ValueError(regular_error)
    # The precheck avoids opening special files; O_NONBLOCK and fstat cover a
    # replacement between stat and open without waiting for a FIFO writer.
    with open(path, "rb", opener=lambda name, flags: os.open(name, flags | os.O_NONBLOCK)) as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(regular_error)
        size_error = f"record exceeds {MAX_BLOCKER_RECORD_BYTES} bytes; use a smaller saved JSON record"
        if info.st_size > MAX_BLOCKER_RECORD_BYTES:
            raise ValueError(size_error)
        raw = f.read(MAX_BLOCKER_RECORD_BYTES + 1)
        if len(raw) > MAX_BLOCKER_RECORD_BYTES:  # Still bounded if the file grew after fstat.
            raise ValueError(size_error)
    return json.loads(raw.decode("utf-8"))


def blocker_problems(t, board, check_resume=False):
    """Validate one prerequisite against local evidence only. Matching evidence is a reconciliation hint, not authority."""
    def text(value):
        return isinstance(value, str) and bool(value.strip())

    kind = t.get("blocker_kind")
    if kind not in BLOCKER_KINDS:
        return ["opaque: blocker_kind must be approval, denial or external (reconcile legacy free text)"]
    out = []
    if not (text(t.get("blocked_on")) and text(t.get("need"))):
        out.append("opaque: blocked_on/need must be nonblank text")
    if kind == "approval":
        item = t.get("approval_item_id")
        if not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_\-.~:@+]{1,200}", item):
            out.append("opaque: approval needs a decision-page approval_item_id")
    elif kind == "denial":
        source = t.get("denial_source")
        try:
            if not text(source):
                raise ValueError("must resolve to a local denial record path")
            doc = read_blocker_record(source)
            if not isinstance(doc, dict) or doc.get("decision") != "NO":
                raise ValueError('record must be a JSON object with decision "NO"')
            ids = [doc[k] for k in ("id", "item_id") if k in doc]
            if not ids or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_\-.~:@+]{1,200}", value)
                              for value in ids) or any(value != ids[0] for value in ids):
                raise ValueError("record needs an identifiable id or item_id (both must agree if present)")
            if not text(doc.get("scope")) or doc["scope"] != t.get("denial_scope"):
                raise ValueError("record scope must match denial_scope byte for byte")
        except (OSError, ValueError) as exc:
            out.append(f"opaque: denial_source cannot be checked ({exc})")
        if not text(t.get("denial_scope")):
            out.append("opaque: denial needs denial_scope (the exact action refused)")
    elif not text(t.get("external_prerequisite")):
        out.append("opaque: external needs external_prerequisite")
    fields = {"approval": ("approval_item_id",), "denial": ("denial_source", "denial_scope"),
              "external": ("external_prerequisite",)}
    if any(t.get(k) is not None for k in BLOCKER_FIELDS[1:-1] if k not in fields[kind]):
        out.append("opaque: blocker has fields for another kind; record each prerequisite separately")
    predicate = t.get("resume_predicate")
    matched = False
    if isinstance(predicate, dict) and set(predicate) == {"ticket", "status"} and kind != "approval":
        target = next((row for row in board["tickets"] if isinstance(row, dict)
                       and row.get("id") == predicate["ticket"]), None)
        if not text(predicate["ticket"]) or target is None or predicate["ticket"] == t.get("id"):
            out.append("opaque: resume_predicate.ticket must resolve to another board ticket")
        elif predicate["status"] not in STATUSES:
            out.append("opaque: resume_predicate.status must be a board status")
        else:
            matched = target.get("status") == predicate["status"]
    elif isinstance(predicate, dict) and set(predicate) == {"path", "field", "equals"}:
        try:
            if not text(predicate["path"]) or not text(predicate["field"]):
                raise ValueError("path/field must be nonblank text")
            doc = read_blocker_record(predicate["path"])
            if not isinstance(doc, dict) or predicate["field"] not in doc:
                raise ValueError("field not found in JSON object")
            if kind == "approval":
                ids = [doc[k] for k in ("id", "item_id") if k in doc]
                if not ids or any(value != t.get("approval_item_id") for value in ids):
                    raise ValueError("record does not identify approval_item_id")
            value = doc[predicate["field"]]
            matched = type(value) is type(predicate["equals"]) and value == predicate["equals"]
        except (OSError, ValueError) as exc:
            out.append(f"opaque: resume_predicate record cannot be checked ({exc})")
    else:
        out.append("opaque: resume_predicate needs {ticket, status} or {path, field, equals}; approval requires JSON")
    if check_resume and matched and not out:
        out.append("stale: resume_predicate matches saved evidence; reconcile this prerequisite only, not other gates")
    return out


def transition(ticket_id, status, owner=None, proof=None, on=None, need=None, lease=None, force=False,
               reworded_by=None, reworded_source=None, link=None, blocker_kind=None, approval_item_id=None,
               denial_source=None, denial_scope=None, external_prerequisite=None, resume_predicate=None):
    """Change a ticket's status under the board lock. A claim returns a lease token; done/block/release on a claimed
    ticket must present it, so a second session with the same owner name, or a worker whose lease was taken over,
    cannot finish or drop someone else's claim. --force overrides and is written into the progress line."""
    link = check_link(link)
    with locked():
        board = load()
        t = find(board, ticket_id)
        held = t["status"] == "doing" and t.get("lease")
        fresh = held and _age_hours(t.get("updated")) < LEASE_HOURS
        if status == "doing":
            if lanes(board, t.get("mission")):
                want, mine = ticket_lane(board, t), owner_lane(board, t.get("mission"), owner)
                if want != mine and not force:
                    sys.exit(f"board: {ticket_id} belongs to {want}, not your lane ({mine}); leave it to {want} "
                             "(--force only with Alex's say-so; it is logged)")
            if t["status"] == "done" and not force:
                sys.exit(f"board: {ticket_id} is already done; reopen it with --force only if the proof is wrong")
            if fresh and lease != t["lease"] and not force:
                sys.exit(f"board: {ticket_id} is claimed by {t.get('owner')} (since {t.get('updated')}); pick another "
                         "ticket, or pass that claim's --lease to renew it")
            t["owner"] = owner
            if not (held and lease == t["lease"]):
                t["lease"] = secrets.token_hex(4)
        else:
            if held and lease != t["lease"] and not force:
                sys.exit(f"board: {ticket_id} is claimed by {t.get('owner')}; pass its --lease (from the claim) or --force")
            if status == "done":
                if not (proof or "").strip():
                    sys.exit("board: done needs --proof (command output path, log id, commit or PR)")
                if t["status"] != "doing" and not force:
                    sys.exit(f"board: claim {ticket_id} first (board.py claim {ticket_id} --owner <agent>), then mark it done")
                if "approval_hash" in t and t["approval_hash"] != ticket_hash(t):  # "" or null is a broken hash, not none
                    # the finish line was reworded after approval: only Alex's own words make that legitimate
                    if not (reworded_by or "").strip() or not (reworded_source or "").strip():
                        sys.exit(f"board: {ticket_id} title/done_means changed after approval; prove the ORIGINAL finish "
                                 "line, or pass --reworded-by \"<Alex's quoted words>\" and "
                                 "--reworded-source \"<transcript/record + UTC>\"")
                    try:  # the audit line comes first: no REWORDED record, no rebound finish line
                        log(ticket_id, "done", t.get("owner"), f"REWORDED by {reworded_by.strip()} "
                            f"(source: {reworded_source.strip()}) (before completion)")
                    except OSError as exc:
                        sys.exit(f"board: could not write the REWORDED audit line ({exc}); {ticket_id} stays open")
                    t["reworded_by"] = reworded_by.strip()
                    t["reworded_source"] = reworded_source.strip()
                    t["approval_hash"] = ticket_hash(t)
                if proof.strip() not in t.setdefault("proof", []):  # a retried done never duplicates proof
                    t["proof"].append(proof.strip())
            elif status == "blocked":
                details = dict(zip(BLOCKER_FIELDS, (blocker_kind, approval_item_id, denial_source, denial_scope,
                                                    external_prerequisite, resume_predicate)))
                candidate = dict(t, blocked_on=on, need=need, **details)
                bad = blocker_problems(candidate, board)
                if bad:
                    sys.exit("board: " + "; ".join(bad))
                t["blocked_on"], t["need"] = on, need
                for key, value in details.items():
                    t.pop(key, None)
                    if value is not None:
                        t[key] = value
                if link:
                    t["link"] = link
            elif status == "open":
                t["owner"] = None
            t.pop("lease", None)
        if status != "blocked":
            t.pop("blocked_on", None)
            t.pop("need", None)
            for key in BLOCKER_FIELDS:
                t.pop(key, None)
        t["status"], t["updated"] = status, now()
        t["progressed"] = t["updated"]
        save(board)
        text = proof if status == "done" else (f"on {on}: {need}" if status == "blocked" else "")
        if status == "blocked":
            text += " | blocker: " + json.dumps({k: t[k] for k in BLOCKER_FIELDS if k in t}, sort_keys=True)
        if status == "blocked" and link:
            text += f" (link: {link})"
        if status == "done" and (reworded_by or "").strip():
            citation_source = f" (source: {reworded_source.strip()})" if (reworded_source or "").strip() else ""
            text = f"REWORDED by {reworded_by.strip()}{citation_source} | {text}"
        try:  # the transition is saved; a missing progress line is recoverable with board.py note
            log(ticket_id, status, t.get("owner"), ("FORCED " if force else "") + (text or ""))
        except OSError as exc:
            print(f"board: saved, but progress.md was not written ({exc}); add it with board.py note", file=sys.stderr)
        after_change(board, f"{ticket_id}: {status}" + (f" ({t.get('owner')})" if t.get("owner") else ""))
    return t


def add(mission, source_item, title, done_means, step, mode="S", part=None, also=None, owner=None):
    """New ticket under an approved mission (e.g. a parity gap, plan 0.2): next free id, placed after the last ticket
    of the same or an earlier step, approval_hash recorded. Scope beyond the approved plan needs Alex's yes first."""
    with locked():
        board = load()
        if mission not in board.get("missions", {}):
            sys.exit(f"board: unknown mission {mission!r}")
        nums = [int(t["id"].rsplit("-", 1)[1]) for t in board["tickets"] if t.get("mission") == mission]
        t = {"id": f"{mission}-{(max(nums) + 1) if nums else 0:02d}", "mission": mission, "source_item": source_item,
             "step": step, "mode": mode, "title": title, "done_means": done_means, "owner": owner, "status": "open",
             "proof": [], "updated": now()}
        if part:
            t["part"] = part
        if also:
            t["also_items"] = also
        t["approval_hash"] = ticket_hash(t)
        pos = 0  # after the last ticket whose step is the same or earlier; first when none is
        for i, other in enumerate(board["tickets"]):
            if isinstance(other.get("step"), int) and other["step"] <= step:
                pos = i + 1
        board["tickets"].insert(pos, t)
        save(board)
        log(t["id"], "added", owner, f"{source_item}{part or ''}: {title}")
        after_change(board, f"{t['id']}: added")
    return t


def note(ticket_id, text, link=None):
    link = check_link(link)
    with locked():
        board = load()
        t = find(board, ticket_id)
        if link:
            t["link"] = link
        log(ticket_id, "note", t.get("owner"), text + (f" (link: {link})" if link else ""))
        t["progressed"] = now()  # a note is progress for stale detection; it does not renew a claim's lease
        save(board)
        after_change(board, f"{ticket_id}: note")


def answer(ticket_id, source, text, force=False):
    """Record Alex's answer to a ticket blocked on him and unblock it (status open, owner kept). The source must say
    where his words are (transcript id + UTC), so the answer can be checked later."""
    if not (source or "").strip() or not (text or "").strip():
        sys.exit("board: answer needs --source '<transcript id + UTC>' and --text '<his answer>'")
    with locked():
        board = load()
        t = find(board, ticket_id)
        waiting = t["status"] == "blocked" and t.get("blocked_on") == "alex"
        if not waiting and not force:
            sys.exit(f"board: {ticket_id} is not blocked on alex (status {t['status']}); --force to record anyway")
        operation = secrets.token_hex(16)
        t.setdefault("answers", []).append({"ts": now(), "source": source.strip(), "text": text.strip(),
                                            "operation": operation})
        if waiting:
            t["status"] = "open"
            t.pop("blocked_on", None)
            t.pop("need", None)
            for key in BLOCKER_FIELDS:
                t.pop(key, None)
        t["updated"] = t["progressed"] = now()
        prepare_answer(ticket_id, operation)
        try:
            try:
                log(ticket_id, "answer", t.get("owner"), f"Alex ({source.strip()}): {text.strip()}")
            except OSError as exc:
                sys.exit(f"board: could not write the answer's progress line ({exc}); {ticket_id} unchanged, retry")
            save(board)
        finally:
            # Also handles exceptions/KeyboardInterrupt. SIGKILL is recovered by
            # the next locked operation; committed operation IDs prevent rollback.
            recover_answer()
        after_change(board, f"{ticket_id}: answer")
    return t


def sync():
    with locked():
        board = load()
        warnings = after_change(board, "board: sync plans + index")
    return warnings


def problems(board):
    if not isinstance(board, dict) or not isinstance(board.get("tickets"), list) or not isinstance(board.get("missions"), dict):
        return ["tasks.json must be an object with a 'missions' object and a 'tickets' list"]
    out, seen = [], set()
    missions = board["missions"]
    for t in board["tickets"]:
        if not isinstance(t, dict):
            out.append(f"ticket is not an object: {str(t)[:40]}")
            continue
        tid = t.get("id", "?")
        if tid in seen:
            out.append(f"duplicate ticket id {tid}")
        seen.add(tid)
        m = t.get("mission")
        if m not in missions:
            out.append(f"{tid}: mission {m!r} is not in missions")
        elif not re.fullmatch(re.escape(m) + r"-\d{2,}", tid):
            out.append(f"{tid}: id must be <mission>-NN")
        if t.get("status") not in STATUSES:
            out.append(f"{tid}: status {t.get('status')!r} not in {STATUSES}")
        if not t.get("done_means"):
            out.append(f"{tid}: no done_means")
        if t.get("status") == "done" and not t.get("proof"):
            out.append(f"{tid}: done without proof")
        if t.get("status") == "doing" and not (t.get("owner") and t.get("lease")):
            out.append(f"{tid}: doing without owner/lease (claim it with board.py claim)")
        if t.get("status") == "doing":
            age = min(_age_hours(t.get("updated")), _age_hours(t.get("progressed")))
            if age > STALE_AFTER_HOURS:
                held = "age unknown" if age >= 1e9 else f"{int(age * 60)}m" if age < 2 else f"{int(age)}h"
                out.append(f"{tid}: doing with no update for {held} ({t.get('owner')}): "
                           f"finish it or board.py release {tid} --force with a note")
        if t.get("status") == "blocked" and not (t.get("blocked_on") and t.get("need")):
            out.append(f"{tid}: blocked without blocked_on/need")
        if t.get("status") == "blocked":
            out.extend(f"{tid}: {issue} (needs {t.get('blocked_on')}: {t.get('need')})"
                       for issue in blocker_problems(t, board, check_resume=True))
        if t.get("approval_hash") and t["approval_hash"] != ticket_hash(t):
            out.append(f"{tid}: title/done_means edited after approval; needs Alex's yes (then update approval_hash)")
    return out


def line(t):
    who = f" [{t['owner']}]" if t.get("owner") else ""
    extra = f" (needs {t.get('blocked_on')}: {t.get('need')})" if t["status"] == "blocked" else ""
    extra += f" <{t['link']}>" if t.get("link") and t["status"] != "done" else ""
    src = (t.get("source_item") or "") + (t.get("part") or "")
    return f"{t['id']} {t['status']:<7} {src:<9} {t['title']}{who}{extra}"


# ---- Plans keep themselves current (plan item 0.8) ------------------------------------------------------------
STALE_DRAFT_DAYS, STALE_RUNNING_DAYS = 14, 3
STALE_AFTER_HOURS = 1  # a doing claim with no update or note this long is flagged (Alex 2026-10-15: "every hour")
INDEX_HEADER = "<!-- GENERATED by tools/board/board.py (plan item 0.8). Do not hand-edit: run `board.py sync`. -->"


def root():
    """Repo root that holds board/ and plans/ (~/.agents, or a test folder)."""
    return os.path.dirname(os.path.abspath(board_dir()))


def home():
    return os.path.expanduser("~")


def read_plan(path):
    """-> (front matter dict, header bytes incl. fences, body bytes), or None when there is no front matter."""
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.startswith(b"---\n"):
        return None
    end = raw.find(b"\n---\n", 3)
    if end < 0:
        return None
    fm = {}
    for row in raw[4:end].decode("utf-8", "replace").splitlines():
        k, sep, v = row.partition(":")
        if sep:
            fm[k.strip()] = v.strip()
    return fm, raw[:end + 5], raw[end + 5:]


def plan_state(fm, body, tickets):
    """-> (status, warning). draft never moves; an approval only holds while the body hash still matches."""
    cur = fm.get("status", "draft")
    if cur == "draft":
        return cur, None
    if not fm.get("approved_by") or fm.get("body_sha256") != hashlib.sha256(body).hexdigest():
        return cur, "plan body changed after approval: get Alex's yes, then record the new body_sha256"
    if tickets and all(t.get("status") == "done" and t.get("proof") for t in tickets):
        return "done", None
    if cur in ("running", "done") or any(t.get("status") in ("doing", "blocked", "done") for t in tickets):
        return "running", None  # once started, a plan never falls back to approved
    return "approved", None


def set_plan_status(path, status):
    require_legacy_writes()
    fm, header, body = read_plan(path)
    new_header = re.sub(rb"(?m)^status:.*$", b"status: " + status.encode(), header, count=1)
    if b"\nstatus:" not in new_header:
        new_header = new_header[:-4] + b"status: " + status.encode() + b"\n---\n"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".plan.", suffix=".md")
    with os.fdopen(fd, "wb") as f:
        f.write(new_header + body)
    os.replace(tmp, path)


def sync_plans(board):
    """Move each mission's plan status from its tickets; returns warnings. Caller holds the lock."""
    require_legacy_writes(board)
    warnings = []
    for m, info in board.get("missions", {}).items():
        path = os.path.join(root(), info.get("plan", ""))
        parsed = read_plan(path) if info.get("plan") and os.path.isfile(path) else None
        if not parsed:
            warnings.append(f"{m}: plan file missing or has no front matter ({info.get('plan')})")
            continue
        fm, _, body = parsed
        new, warn = plan_state(fm, body, [t for t in board["tickets"] if t.get("mission") == m])
        if warn:
            warnings.append(f"{m}: {warn}")
        if new != fm.get("status"):
            set_plan_status(path, new)
            log(m, "plan", "-", f"{info.get('plan')} status {fm.get('status')} -> {new}")
        info["status"] = new
    return warnings


def _ledger_missions():
    try:
        with open(os.path.join(home(), "Alex-Director", "DIRECTOR_STATE.md"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    out = []
    for blk in re.split(r"\n## Mission: ", text)[1:]:
        def get(k):
            m = re.search(r"^" + k + r":\s*(.*)$", blk, re.M)
            return m.group(1).strip() if m else ""
        mid = get("MISSION_ID")
        if mid and not mid.endswith(":"):
            out.append((mid, (get("STATUS").split(" ") or [""])[0], get("MISSION_GRAPH").replace(home(), "~")))
    return out


def index_text(board):
    """plans/INDEX.md: pointers only, never copies."""
    import glob
    h = home()
    rows = ["# Plan index (pointers only, never copies)", "", INDEX_HEADER, "",
            "## Plans in this folder", "", "| Plan | Mission | Status | Approved | Tickets done |", "|---|---|---|---|---|"]
    for path in sorted(glob.glob(os.path.join(root(), "plans", "*.md"))):
        name = os.path.basename(path)
        if name in ("README.md", "INDEX.md"):
            continue
        parsed = read_plan(path)
        fm = parsed[0] if parsed else {}
        ts = [t for t in board.get("tickets", []) if t.get("mission") == fm.get("mission")]
        done = f"{sum(t.get('status') == 'done' for t in ts)}/{len(ts)}" if ts else "no board tickets"
        rows.append(f"| [{name}]({name}) | {fm.get('mission', '?')} | {fm.get('status', '?')} | "
                    f"{fm.get('approved_at', '-')} | {done} |")
    rows += ["", "## Plans elsewhere", ""]
    elsewhere = []
    for pattern in ("Documents/Codex/*/PLAN*.md", "Documents/Codex/*/*/PLAN*.md", "Documents/Codex/*/*/HANDOFF*.md",
                    "Documents/Codex/*/*/reviews/*plan*review*.md", ".agents/docs/plans/*.md", "Alex-Director/*plan*.md"):
        elsewhere += glob.glob(os.path.join(h, pattern))
    rows += [f"- `{p.replace(h, '~')}`" for p in sorted(set(elsewhere))] or ["- none"]
    rows += ["", "## Director missions (ledger: `~/Alex-Director/DIRECTOR_STATE.md`)", "",
             "| Mission id | Status | Mission graph |", "|---|---|---|"]
    rows += [f"| {mid} | {st} | `{graph}` |" for mid, st, graph in _ledger_missions()]
    rows += ["", "## Chat handoffs (chat_guard.py)", ""]
    handoffs = sorted(glob.glob(os.path.join(h, ".agents", "runtime", "chat-guard", "handoffs", "*.md")))
    rows += [f"- `{p.replace(h, '~')}`" for p in handoffs] or ["- none"]
    return "\n".join(rows) + "\n"


def write_index(board):
    require_legacy_writes(board)
    path = os.path.join(root(), "plans", "INDEX.md")
    if not os.path.isdir(os.path.dirname(path)):
        return
    text = index_text(board)
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return
    except OSError:
        pass
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".index.", suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def stale_flags(board):
    """Session-start flags: drafts older than 14 days, running missions with no ticket progress in 3 days."""
    import glob
    flags = []
    for path in sorted(glob.glob(os.path.join(root(), "plans", "*.md"))):
        parsed = read_plan(path)
        if not parsed or parsed[0].get("status") != "draft":
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})_", os.path.basename(path))
        born = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%d")) if m else os.path.getmtime(path)
        days = (time.time() - born) / 86400
        if days > STALE_DRAFT_DAYS:
            flags.append(f"draft {os.path.basename(path)} is {int(days)} days old (approve or archive it)")
    for t in board.get("tickets", []):
        if t.get("status") == "blocked" and t.get("blocked_on") == "alex":
            age = _age_hours(t.get("updated"))
            if age >= 1e9:  # missing or unreadable timestamp: say so instead of inventing a wait
                flags.append(f"{t['id']} blocked on alex (age unknown): if he answered, "
                             f"board.py answer {t['id']} --source ... --text ...")
            elif age > 1:
                flags.append(f"{t['id']} blocked on alex for {int(age)}h: if he answered, "
                             f"board.py answer {t['id']} --source ... --text ...")
    for mission, info in board.get("missions", {}).items():
        ts = [t for t in board.get("tickets", []) if t.get("mission") == mission]
        # Untimestamped tickets fall back to the mission's approval time; with neither there is no evidence of
        # idleness (a missing stamp used to read as "41666666 days").
        ages = [a for a in (_age_hours(t.get("progressed") or t.get("updated")) for t in ts) if a < 1e9]
        ages = ages or [a for a in [_age_hours(info.get("approved_at"))] if a < 1e9]
        if info.get("status") == "running" and ages:
            idle = min(ages) / 24
            if idle > STALE_RUNNING_DAYS:
                flags.append(f"{mission} is running with no ticket progress for {int(idle)} days")
    return flags


def _status_line_only(r, path):
    """True only when the working copy equals HEAD except for the front matter's status: line (header minus that
    line and the whole body must be byte-identical). A status: line added anywhere else does not count."""
    head = subprocess.run(["git", "-C", r, "show", f"HEAD:{path}"], capture_output=True, timeout=30)
    if head.returncode:
        return False
    with open(os.path.join(r, path), "rb") as f:
        current = f.read()

    def parts(raw):
        if not raw.startswith(b"---\n"):
            return None
        fence = re.search(rb"\n---\r?\n", raw[3:])  # the FIRST closing fence, whatever its line ending
        if not fence or b"\r" in raw[:3 + fence.end()]:
            return None  # a carriage return anywhere in the front matter: never treat it as status-only
        header = raw[:3 + fence.end()]
        if len(re.findall(rb"(?m)^status:", header)) != 1:  # exactly one status key, before and after
            return None
        return re.sub(rb"(?m)^status:[^\n]*\n", b"", header, count=1), raw[len(header):]

    before, after = parts(head.stdout), parts(current)
    return before is not None and before == after


def commit_state(message):
    """Commit per step (Anthropic long-running harness) for board state only: board/tasks.json, board/progress.md,
    plans/INDEX.md and a plan's status line. OFF unless AGENTS_BOARD_COMMIT=1: committing board state straight to
    main is an exception to plan rule 4 that waits for Alex's yes (ticket agent-ops-foundation-03). A plan file is
    included only when its uncommitted diff is the status line alone; never fails a transition; [skip ci]."""
    require_legacy_writes()
    if os.environ.get("AGENTS_BOARD_COMMIT") != "1" or os.environ.get("AGENTS_BOARD_NO_COMMIT"):
        return
    r = root()
    try:
        git = lambda *a, **kw: subprocess.run(["git", "-C", r, *a], capture_output=True, text=True, timeout=30, **kw)
        if git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
            return
        board = load()
        plans = sorted({i["plan"] for i in board.get("missions", {}).values() if i.get("plan")})
        paths = ["board/tasks.json", "board/progress.md", "plans/INDEX.md"] + plans
        paths = [p for p in paths if not git("ls-files", "--error-unmatch", p).returncode]
        for p in [p for p in paths if p in plans and not _status_line_only(r, p)]:
            paths.remove(p)
            print(f"board: not committing {p}: it has edits beyond its status line (review them through the PR lane)",
                  file=sys.stderr)
        if not paths or not git("diff", "--quiet", "HEAD", "--", *paths).returncode:
            return
        env = dict(os.environ, AGENTS_ALLOW_UNTRACKED="1")  # commits only its own tracked paths
        res = git("commit", "-q", "--only", "-m", f"{message} [skip ci]", "--", *paths, env=env)
        if res.returncode:
            print(f"board: saved, but the board commit failed ({(res.stderr or res.stdout).strip()[:160]}); "
                  "commit board/ and plans/ by hand", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"board: saved, but the board commit failed ({exc.__class__.__name__})", file=sys.stderr)


def after_change(board, message):
    """Caller holds the lock: derive plan status, regenerate the index, save, commit."""
    require_legacy_writes(board)
    try:
        warnings = sync_plans(board)
        save(board)
        write_index(board)
    except Exception as exc:  # noqa: BLE001
        warnings = [f"plan sync failed ({exc.__class__.__name__}: {exc})"]
    for w in warnings:
        print(f"board: {w}", file=sys.stderr)
    commit_state(message)
    return warnings


def summary(lane=None):
    """Session-start line. Missing board -> empty; a broken board -> one warning line, never an exception."""
    try:
        board = load()
    except OSError:
        return ""
    except ValueError as exc:
        return f"[board] tasks.json is not valid JSON ({exc.__class__.__name__}); run board.py check."
    try:
        return _summary(board, lane)
    except Exception as exc:  # malformed structure must never break a session start
        return f"[board] tasks.json is malformed ({exc.__class__.__name__}); run board.py check."


def _summary(board, lane=None):
    if database_export(board):
        tickets = display_tickets(board)
        counts = {}
        for ticket in tickets:
            status = ticket.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        statuses = ", ".join(f"{status}: {count}" for status, count in sorted(counts.items()))
        return (f"[board] director.tasks generated export: {len(tickets)} tasks ({statuses}); "
                "read-only; use the task-list MCP for mutations.")
    parts = []
    for m, info in board.get("missions", {}).items():
        ts = [t for t in board["tickets"] if t.get("mission") == m]
        if not ts or all(t["status"] == "done" for t in ts):
            continue
        done = sum(t["status"] == "done" for t in ts)
        unverified = sum(t["status"] == "done" and t.get("verified") is False for t in ts)
        doing = [f"{t['id']} {t['title'][:48]} ({t.get('owner')})" for t in ts if t["status"] == "doing"]
        alex = [t for t in ts if t["status"] != "done" and (t.get("owner") == "alex" or t.get("blocked_on") == "alex")]
        opens = [(t.get("step") if isinstance(t.get("step"), int) else 999, i, t) for i, t in enumerate(ts)
                 if t["status"] == "open" and t.get("owner") != "alex" and (lane is None or ticket_lane(board, t) == lane)]
        nxt = min(opens, key=lambda x: x[:2])[2] if opens else None  # lowest step first, then board order
        s = f"{m} ({info.get('status', '?')}, {info.get('plan', 'no plan')}): {done}/{len(ts)} done" + (f" ({unverified} unverified claims)" if unverified else "")
        if doing:
            s += "; doing: " + ", ".join(doing)
        if nxt:
            s += f"; next{' in ' + lane if lane else ''}: {nxt['id']} {nxt['title'][:48]}"
        if alex:
            s += f"; waiting on Alex: {len(alex)} (first: {alex[0]['id']} {alex[0]['title'][:60]})"
        parts.append(s)
    flags = stale_flags(board)
    if not parts and not flags:
        return ""
    if flags:
        parts.append("stale: " + "; ".join(flags[:3]))
    bad = problems(board)
    tail = f" Board problems: {len(bad)} (board.py check)." if bad else ""
    return ("[board] " + " | ".join(parts) + ". Claim before working: board.py claim <id> --owner <agent>; "
            "~/.agents/board/tasks.json." + tail)


OBSERVATORY = os.path.expanduser("~/Documents/Codex/2026-10-03/i-want-you-to-improve-my/outputs/director-observatory")
_BOARD_READ = ("import json,sys; sys.path.insert(0, sys.argv[1]); m = __import__(sys.argv[2]); "
               "print(json.dumps(m.read_live('status_board')))")


def agent_boards(timeout=30):
    """Javar's and Javante's STATUS.md in-progress lines via the observatory's read-only status_board view
    (plan 0.1 link). Fails soft: any error is one 'unavailable' line. AGENTS_BOARD_REMOTE=0 skips it; tests
    point AGENTS_BOARD_OBSERVATORY at a fixture."""
    folder = os.environ.get("AGENTS_BOARD_OBSERVATORY")
    if os.environ.get("AGENTS_BOARD_REMOTE") == "0" or (os.environ.get("AGENTS_BOARD_DIR") and not folder):
        return []
    folder = folder or OBSERVATORY
    procs, out = {}, []
    for name, module in (("Javar", "live_javar"), ("Javante", "live_javante")):
        try:
            if not os.path.isdir(folder):
                raise OSError("observatory missing")
            procs[name] = subprocess.Popen([sys.executable, "-c", _BOARD_READ, folder, module], stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        except Exception:
            procs[name] = None
    for name in ("Javar", "Javante"):
        p = procs[name]
        try:
            if p is None:
                raise OSError("not started")
            stdout, _ = p.communicate(timeout=timeout)
            r = json.loads(stdout)
            lines = r.get("lines") if isinstance(r, dict) else None
            if p.returncode != 0 or r.get("ok") is not True or r.get("error") or not isinstance(lines, list) \
                    or not all(isinstance(x, str) for x in lines):
                raise ValueError("bad status_board response")
            shown = [x[:160] for x in lines][:5]
            out.append(f"[board] {name} STATUS.md in progress: " + ("; ".join(shown) if shown else
                       ("none" if r.get("exists") is True else "no STATUS.md found")) + " (plan 0.1)")
        except Exception:
            if p is not None and p.poll() is None:
                with contextlib.suppress(OSError):
                    os.killpg(p.pid, 9)  # whole group: the route's ssh/helper child goes too
                with contextlib.suppress(Exception):
                    p.communicate(timeout=5)
            out.append(f"[board] {name} STATUS.md: unavailable (observatory status_board read failed; plan 0.1)")
    return out


def main(argv):
    p = argparse.ArgumentParser(prog="board.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary"); s.add_argument("--lane", help="only this lane's next ticket (main = tickets no lane lists)")
    s = sub.add_parser("show"); s.add_argument("--mission"); s.add_argument("--status"); s.add_argument("--owner")
    s.add_argument("--limit", type=int, default=short_output.DEFAULT_LIMIT, help="lines per page (0 = all)")
    s.add_argument("--offset", type=int, default=0, help="skip this many matching tickets")
    s.add_argument("--full", action="store_true", help="never cut a long line")
    s = sub.add_parser("claim"); s.add_argument("ticket"); s.add_argument("--owner", required=True)
    s.add_argument("--lease", help="renew your own claim"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("done"); s.add_argument("ticket"); s.add_argument("--proof", required=True)
    s.add_argument("--reworded-by", help="Alex's quoted words; a changed finish line also requires --reworded-source")
    s.add_argument("--reworded-source", help="transcript/record pointer + UTC for Alex's words; caller must verify it")
    s.add_argument("--lease"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("block"); s.add_argument("ticket"); s.add_argument("--on", required=True); s.add_argument("--need", required=True)
    s.add_argument("--kind", dest="blocker_kind", choices=BLOCKER_KINDS, required=True)
    s.add_argument("--approval-item-id", help="item id on Alex's decision page; resume JSON must identify this item")
    s.add_argument("--denial-source", help='absolute or repo-relative JSON denial: id/item_id, decision "NO", scope')
    s.add_argument("--denial-scope", help="the exact action refused; must match the denial record scope byte for byte")
    s.add_argument("--external-prerequisite", help="the external event required before resuming")
    s.add_argument("--resume-predicate", type=json.loads, required=True, help="JSON: {ticket, status} or {path, field, equals}")
    s.add_argument("--lease"); s.add_argument("--force", action="store_true")
    s.add_argument("--link", help="exact settings URL Alex acts on, or \"none: <why>\"")
    s = sub.add_parser("release"); s.add_argument("ticket"); s.add_argument("--lease"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("note"); s.add_argument("ticket"); s.add_argument("text"); s.add_argument("--link")
    s = sub.add_parser("add"); s.add_argument("--mission", required=True); s.add_argument("--source-item", required=True)
    s.add_argument("--title", required=True); s.add_argument("--done-means", required=True)
    s.add_argument("--step", type=int, required=True); s.add_argument("--mode", default="S"); s.add_argument("--part")
    s.add_argument("--also", action="append"); s.add_argument("--owner")
    s = sub.add_parser("answer"); s.add_argument("ticket"); s.add_argument("--source", required=True)
    s.add_argument("--text", required=True); s.add_argument("--force", action="store_true")
    s = sub.add_parser("check")
    s.add_argument("--limit", type=int, default=short_output.DEFAULT_LIMIT, help="problems per page (0 = all)")
    s.add_argument("--offset", type=int, default=0); s.add_argument("--full", action="store_true", help="never cut a line")
    s = sub.add_parser("blockers", help="list blocked tickets; --check lists only stale/opaque prerequisites")
    s.add_argument("--check", action="store_true")
    s.add_argument("--limit", type=int, default=short_output.DEFAULT_LIMIT)
    s.add_argument("--offset", type=int, default=0); s.add_argument("--full", action="store_true")
    sub.add_parser("sync")
    a = p.parse_args(argv)
    if a.cmd == "summary":
        s = summary(a.lane)
        if s:
            print(s)
        for row in agent_boards():
            print(row)
    elif a.cmd == "show":
        rows = [line(t) for t in display_tickets(load())
                if not ((a.mission and t.get("mission") != a.mission) or (a.status and t["status"] != a.status)
                        or (a.owner and t.get("owner") != a.owner))]
        more = short_output.cmd("board.py show", mission=a.mission, status=a.status, owner=a.owner)
        short_output.page(rows, a.limit, a.offset, more=more, width=0 if a.full else short_output.WIDTH)
    elif a.cmd == "claim":
        t = transition(a.ticket, "doing", owner=a.owner, lease=a.lease, force=a.force)
        print(line(t))
        print(f"lease={t['lease']}  (pass --lease {t['lease']} to done/block/release)")
    elif a.cmd == "done":
        print(line(transition(a.ticket, "done", proof=a.proof, lease=a.lease, force=a.force,
                              reworded_by=a.reworded_by, reworded_source=a.reworded_source)))
    elif a.cmd == "block":
        details = {k: getattr(a, k) for k in BLOCKER_FIELDS}
        print(line(transition(a.ticket, "blocked", on=a.on, need=a.need, lease=a.lease, force=a.force, link=a.link, **details)))
    elif a.cmd == "release":
        print(line(transition(a.ticket, "open", lease=a.lease, force=a.force)))
    elif a.cmd == "note":
        note(a.ticket, a.text, a.link)
    elif a.cmd == "add":
        print(line(add(a.mission, a.source_item, a.title, a.done_means, a.step, a.mode, a.part, a.also, a.owner)))
    elif a.cmd == "answer":
        t = answer(a.ticket, a.source, a.text, a.force)
        try:  # the answer is already saved and logged; a reader that went away doesn't make it a failure
            print(line(t))
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            os._exit(0)
    elif a.cmd == "sync":
        warnings = sync()
        print(f"board sync: plans + plans/INDEX.md current; {len(warnings)} warning(s)")
    elif a.cmd == "check":
        bad = problems(load())
        short_output.page(bad, a.limit, a.offset, more="board.py check", width=0 if a.full else short_output.WIDTH)
        print(f"board check: {len(bad)} problem(s)")
        return 1 if bad else 0
    elif a.cmd == "blockers":
        board = load()
        tickets = [t for t in board["tickets"] if isinstance(t, dict) and t.get("status") == "blocked"]
        rows = [f"{t.get('id', '?')}: {issue} (needs {t.get('blocked_on')}: {t.get('need')})" for t in tickets
                for issue in blocker_problems(t, board, check_resume=True)] if a.check else [line(t) for t in tickets]
        short_output.page(rows, a.limit, a.offset, more="board.py blockers" + (" --check" if a.check else ""),
                          width=0 if a.full else short_output.WIDTH)
        print(f"board blockers: {len(rows)} {'problem(s)' if a.check else 'blocked ticket(s)'}; read-only, no gates cleared")
        return 1 if a.check and rows else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
