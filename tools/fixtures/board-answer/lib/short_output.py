#!/usr/bin/env python3
"""Short tool results (ticket agent-ops-foundation-58, plan item 9.2). Claude Code caps one tool result at 25,000
tokens, so scripts print only the lines the next step needs, page long lists, say how to get the rest, and errors
say what to change.

  page(lines, limit, offset, more, width)  print one page; when anything is cut (rows or long lines) a last line
                                           says the exact command for the next page, all rows, or full lines
  cmd(base, **flags)                       shell-quoted command for that hint
  fail(prog, what, fix)                    "<prog>: <what>. Fix: <fix>" for sys.exit()/stderr
"""
import shlex

DEFAULT_LIMIT = 40   # rows per page; ~40 board rows is about 6,000 chars, well under the 25,000-token cap
WIDTH = 400          # one row never carries more than this many chars unless --full (width 0)


def cmd(base, **flags):
    return base + "".join(f" --{k.replace('_', '-')} {shlex.quote(str(v))}" for k, v in flags.items()
                          if v is not None and v is not False)


def clip(line, width=WIDTH):
    line = " / ".join(str(line).splitlines())  # one row is one physical line
    return line if not width or len(line) <= width else line[: width - 3] + "..."


def page(lines, limit=DEFAULT_LIMIT, offset=0, more="", width=WIDTH):
    """Print lines[offset:offset+limit] (limit 0 = all; width 0 = never clip). Returns the number printed."""
    lines = list(lines)
    offset = max(0, offset or 0)
    end = len(lines) if not limit or limit <= 0 else min(len(lines), offset + limit)
    clipped = 0
    for line in lines[offset:end]:
        row = clip(line, width)
        clipped += row.endswith("...") and row != " / ".join(str(line).splitlines())
        print(row)
    hints, full = [], " --full" if not width else ""
    if end < len(lines):
        hints.append(f"showing {offset + 1}-{end} of {len(lines)}; next page: {more} --offset {end} --limit {limit}"
                     f"{full}; all: {more} --limit 0{full}")
    if clipped:
        hints.append(f"{clipped} long row(s) cut at {width} chars; these rows whole: "
                     f"{more} --offset {offset} --limit {limit or 0} --full")
    if hints:
        print("(" + "; ".join(hints) + ")")
    return max(0, end - offset)


def fail(prog, what, fix):
    return f"{prog}: {what}. Fix: {fix}"
