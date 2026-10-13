---
description: Fan out the read-only reviewers in parallel over the changed files and fail closed on any CRITICAL
argument-hint: "[base-ref] -- acceptance text"
allowed-tools: Agent, Bash(git diff:*), Bash(git ls-files:*), Bash(git status:*), Bash(git log:*), Read, Grep, Glob
---

Review the changes on this branch with five read-only reviewers at once, then merge their verdicts. Fail closed: any CRITICAL means NOT READY.

Arguments: `$ARGUMENTS`

## 1. Gather (do not skip: subagents get no parent context)
- **Base:** the first word of the arguments if it is a git ref, otherwise `c833d7f` (the base of branch `langflow-dashboard`).
- **Acceptance text:** everything after `--` in the arguments; otherwise the user's task statement from this conversation, quoted verbatim; otherwise write "none given" and tell the reviewers to judge general correctness.
- **Changed files:** `git diff --name-only <base>` plus `git ls-files --others --exclude-standard`. Drop `reports/`, `.claude/`, lockfiles, `node_modules/`, `.next/` and binary files. If nothing is left, say "no code changes against <base>, nothing to review" and stop.
- **Diff text:** `git diff <base> -- <files>`. Untracked files have no diff: list them as NEW FILE and tell reviewers to Read them in full. If the diff is over about 120 KB, split it into an `app/` batch and a `tools/` batch and give each reviewer the batch it needs. Never truncate silently.

## 2. Fan out, in ONE message (parallel Agent calls)
Reviewers: `correctness-reviewer` (also covers the HTTP contract and canvas-to-API type parity), `security-reviewer`, `data-layer-guard`, `silent-failure-hunter`, `performance-reviewer`.

Each call's prompt must contain, because the reviewer sees nothing else:
1. The base ref and the full changed-file list.
2. The acceptance text.
3. The diff text (or the NEW FILE paths to Read).
4. "You have no parent context. Follow AGENTS.md. Report only findings above 80% confidence with file:line and a concrete failure scenario. End with the severity count line and the verdict line."

Do not pass `model` above `sonnet`. The reviewers pin their own model.

## 3. Merge, fail closed
- Read each reply's `Severity:` and `Verdict:` lines. A reviewer that errors, returns no verdict line, or ignores the format counts as NOT READY: re-run it once, then treat it as NOT READY.
- Any CRITICAL from any reviewer means `OVERALL: NOT READY`. HIGH findings do not change the verdict on their own: list them first and say the caller decides.
- Merge duplicates across reviewers. Sort findings CRITICAL first, each with `file:line` and the one-line failure scenario.

## 4. Report
```
correctness-reviewer   CRITICAL n HIGH n MEDIUM n LOW n   READY | NOT READY
security-reviewer      ...
data-layer-guard       ...
silent-failure-hunter  ...
performance-reviewer   ...
OVERALL: READY | NOT READY
```
Then the findings. Close with two lines. First: the security reviewer runs on Sonnet under the cost cap, so for a change that adds the Langflow proxy or a new mutation path a deeper pass is still worth asking Alex about. Second: READY here means no CRITICAL was found by the reviewers; it does not replace `/verify` or the `alex-reviewer` packet, and only the Director marks work verified.
