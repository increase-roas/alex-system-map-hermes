# Research: AI repair of Alex's local agent instructions

As of: 2026-10-21, America/Detroit. Effort: one focused investigation plus independent verification. Coverage: best-effort external research and targeted inspection of the current repair feature. Status: research and proposed design, not an implementation or approval to change agent rules.

## Question and finish line

How should Review & fix find contradictions and unnecessary duplication in Alex's actual local agent files, produce a justified fix, and finish the approved change across the systems that consume it?

A useful answer identifies a documented engineering pattern, checks it against the current code, distinguishes automatic preparation from Alex's requested approval, and names the smallest worthwhile additions. The user's trailing "and" is treated as a request to continue this research, with no additional requirement inferred.

## Recommendation

Keep the current dashboard, native Python/Git repair service, subscribed Codex proposal worker and existing instruction generator. Extend them into one workflow:

**Scan current files -> resolve applicable sources -> propose the smallest change -> check the candidate -> Alex approves the exact change -> update source and generated copies -> verify and report.**

The documented pattern is source-controlled configuration management combined with AI proposal review and behavioral evaluation. The specific design below is an inference for this installation, not a universal standard or a vendor-certified auto-fixer. GitLab documents a close production example: source-owned instruction modules, generated projections, provenance checks, automated review and human review of changed meaning. OpenAI describes concise instruction entry points and targeted documentation maintenance. Anthropic describes checking actual outcomes with appropriate evaluation methods. [S1, S5, S6]

For Alex, "auto fix" should mean the AI writes the proposed wording and the software carries out the approved change and its follow-through. His preceding request explicitly asked to approve the proposal. This research does not turn that into unattended permission to rewrite meaning, start a schedule, change hooks or call a paid provider.

## What the documentation establishes

| Finding | Evidence and classification | Implication here |
|---|---|---|
| Handwritten instructions and generated instructions need different review and ownership. Source revisions/checksums matter. | Direct statement, GitLab [S1]. | Change the owning source and regenerate its dependents. A copied rule is not automatically redundant junk. |
| An AI instruction file change can affect many sessions; review should check unsupported additions and lost exceptions. | Direct statement, GitLab [S1]. | Evaluate the preservation of meaning, not only whether the diff applies. |
| Codex discovers global and project guidance using defined filenames, directory order and a byte budget. | Direct statement, OpenAI [S2]. | Determine what applies in the actual working directory. A deeper intentional override is not necessarily a contradiction. |
| Claude concatenates applicable instruction files; conflicting user/project rules can lead it to follow either one. Imports and path scope affect loading. | Direct statement, Anthropic [S3]. | Do not use a single guessed precedence algorithm for every agent. |
| Claude documents a native instruction audit with findings and proposed edits. Changes wait for a request to apply. | Direct statement, Anthropic [S3]. | Reuse or compare with native capabilities before building another audit engine. |
| Cursor rules use metadata for activation, including descriptions, globs and alwaysApply. Its documented precedence differs from Codex. | Direct statement, Cursor [S4]. | Include activation metadata and agent-specific loading in the model of applicable rules. |
| Short entry points with links to deeper sources reduce document bloat and support maintenance. | Direct statement, OpenAI [S5], also consistent with Cursor [S4]. | Keep the large setup reference as reference material; keep always-loaded instructions focused. |
| Agent evaluation should inspect outcomes, use deterministic graders where possible and model graders where necessary, and learn from real failures. | Direct statement, Anthropic [S6]. | A valid JSON response and a clean text patch do not prove better agent behavior. |
| Git can check patch applicability without writing and defaults to rejecting a patch with inapplicable hunks. | Direct statement, Git [S7]. | Preserve exact-before checks. There is no reason to replace the existing hash-bound writer merely to adopt Git apply. |

These are engineering recommendations, not additional approval gates. This report adds no guards or hooks.

## Native option discovered

Claude's current documentation describes `/doctor prompt-audit`, optionally scoped to a file or directory. It checks outdated/conflicting instructions and gives proposed edits. The documented minimum is Claude Code 2.1.283 and it depends on the bundled `/claude-api` skill being enabled. [S3]

The installed CLI reports **2.1.301**. That proves version compatibility only. This research did not invoke the audit, establish that its bundled skill is enabled, or prove a stable headless JSON integration. The general CLI documentation describes print mode, but does not establish that this specific interactive audit is a supported structured backend endpoint. [S8]

Recommendation: treat the native audit as a candidate for a scoped comparison or independent review, not as a reason to replace the working dashboard engine or silently add another provider. Any future provider use follows existing authorization and usage limits.

## Current local feature: inspected state

Inspection anchor: `alex-system-map` HEAD `4d99c8f16d74aea10c9357828e358728ec2ccd3a` on 2026-10-21. This section is source inspection, not a fresh Apply test. Earlier real proposal evidence is recorded separately in `reviews/receipts/20261021-real-rule-review/FINAL_REVIEW.md`.

| Capability | What is present | Evidence |
|---|---|---|
| Actual local inventory | Selected roots for shared sources, skills, cards, guards, distribution tools, Codex, Claude, Cursor and Director. Paths, aliases and generated references are modeled. | `tools/local_files.py:34`, `:374`, `:386`. |
| Candidate discovery | Exact repeated instruction lines and a few declaration patterns. Findings explicitly say candidate, not complete semantic detection. | `tools/local_files.py:403-436`. |
| AI-written proposed fix | Current target plus indexed shared authority and related findings. Maximum eight files / 128 KiB; up to five related findings. Coverage limitations are disclosed. | `tools/local_file_ai.py:112-156`. |
| Authority grounding | The server designates Alex's configured gate source only when it is supplied, and scopes that hint to overlapping actions and scope. | `tools/local_file_ai.py:155-174`. |
| Mechanical proposal validation | Structured fields, literal source-line citations, unique nonoverlapping edits, content screening and a fresh context comparison. | `tools/local_file_ai.py:182-247`. |
| Frozen approval and recovery | Source/context hashes, expiring preview, verified preimage, undo copy, serialized Apply, atomic replacement, readback, scoped Git publication and conditional Undo. | `tools/local_file_repairs.py:253-335`, `:337-402`, `:412-550`. |
| Honest partial completion | Source-applied/publish-pending can be shown. Generated publication is explicitly pending; it is not inferred from a successful push. | `tools/local_file_repairs.py:446-459`, `:481-517`. |
| Existing generator | Shared source becomes Codex/home generated instructions, Claude imports and Cursor MDC. Rules-only mode excludes app-owned Codex config writes. | `~/.agents/tools/unify/build_instructions.py:206-249`, `:294-319`. |

This is already a useful proposal-and-apply foundation. It is not a whole-machine semantic auditor, an agent-specific effective-instruction resolver, or end-to-end proof that every consumer received a repair. Skills, executable hooks and app settings need their owning workflows, not this generic Markdown writer. [L1, L2]

## The three useful gaps

### 1. Determine what actually applies, then group findings

**Recommendation:** extend the current inventory with agent, working-directory, activation and source-ownership metadata. Build an inspectable relationship view: handwritten source, generated output/import, intentional alias, applicable override, inactive file and unresolved reference. Use installed-version behavior and current configuration, not a universal "newest file wins" rule. [S2-S4]

Run mechanical checks first for broken references, exact duplicates, generated drift and invalid rule metadata. Use the AI for semantic conflicts: the same action in the same applicable scope with incompatible requirements. It should classify intentional scope differences and historical quotations explicitly rather than "fixing" them.

For broader review, retrieve bounded groups of related sources. Show files considered and omissions on every result. When a context limit prevents a whole group from being inspected, call the result partial. A high confidence score cannot turn missing evidence into coverage.

**Cost:** moderate extension of the inventory/context code; no new service. Broader semantic coverage consumes more of the existing AI plan, so reuse results while all source and configuration fingerprints match. Do not introduce a background schedule under this research request.

### 2. Test whether the proposed rule changes behavior correctly

**Recommendation:** preserve the existing exact-citation and stale-source checks, then add a small behavior test set drawn from real failures. Compare the candidate with the current rules in isolated disposable contexts. The candidate should improve the failing case while preserving the relevant exceptions and other requested behavior. A separate review can assess intent; deterministic checks should assess paths, formats, hashes and generated outputs. Neither reviewer confidence nor a second model's agreement is proof by itself. [S1, S6]

For the actual security-scope contradiction found earlier, useful cases include:

- Own-stack work covered by Alex's standing authorization proceeds.
- Client production, outside contact and spend remain subject to their applicable canonical conditions.
- An own-stack exception does not spread to a different action or outside scope.
- Historical quotations and unrelated rules remain unchanged.
- A stale supporting source invalidates approval without writing.

The exact categories and expected answers must come from current Alex-approved policy; these examples do not create a new policy. Tests simulate decisions and tool requests instead of contacting people or changing live systems.

**Cost:** a bounded number of model calls for affected behavior, plus inexpensive static checks. Reuse the existing CLI/login and test framework. No paid model migration or universal full-suite rerun is recommended.

### 3. Finish synchronization independently and prove each destination

**Observed wiring:** the current post-commit hook calls `sync_notes.py`, and only on its success calls `build_instructions.py apply --rules-only`, followed by `cards_to_sheet.py`. It runs asynchronously and states that a commit is not publication proof. [L3]

**Inference:** a failed remote notes sync can prevent local instruction regeneration in that invocation. This control-flow dependency is visible in source; this research did not induce or prove a specific failed regeneration at runtime. The startup notice separately reports plugin drift and a Javar sync failure. Those notices are not proof that this particular rule proposal was applied or distributed.

**Recommendation:** let local rules-only generation finish independently of remote publication. Reuse the native generator instead of creating a competing sync mechanism. Track the originating source revision and expected output hashes in the existing repair receipt. Show separate local/generated/remote states and an actionable failure reason. Source-updated can be true while a remote consumer is pending; do not describe the entire repair as complete in that state.

Generated outputs should be validated as faithful projections of their registered sources, not compared for blanket byte equality across all agents. This installation intentionally uses Claude imports and generated Codex/Cursor content. GitLab's identical-entrypoint rule is specific to GitLab, not a requirement to erase these harness differences. [S1, L4]

A successful source push proves remote source durability. It does not prove generated publication, a remote machine's readback or an already-running agent's adoption. Codex's documented discovery occurs at run start. Report next-session/reload requirements according to each consumer; a file hash alone cannot establish live adoption. [S2]

**Cost:** moderate repair-orchestration/receipt integration plus the existing generator and destination readbacks. No new scheduler, plugin or hook is needed as an initial step; any eventual existing-hook edit is a separately scoped implementation change.

## The one-approval experience

One card per connected issue should show:

1. **Problem:** the two current passages, with paths and line evidence, and why they conflict in this scope.
2. **AI recommendation:** the proposed wording, the authority that supports it and the intent preserved.
3. **Impact:** the owning source plus generated or remote consumers affected; disclose exclusions.
4. **Checks:** candidate behavior and generation checks, with uncertain results stated plainly.
5. **Approve proposed fix:** approve the frozen change once. The software applies that exact source change, follows the approved generation/publication sequence and reports destination states. Editing or stale evidence requires a fresh preview.
6. **Result / Undo:** show source update, durable push, local generated readbacks and remote status. Undo remains conditional on unchanged applied content and must account for generated dependents; never overwrite newer work.

Related findings can be grouped into one reviewable proposal when ownership and recovery are coherent. Do not claim an atomic multi-repository transaction. The present writer changes one source at a time; wider batches need explicit per-source state, overlap handling and recovery rather than a loop that blindly clicks Apply.

Suggested completion states: **Ready for approval**, **Source updated**, **Local copies verified**, **Remote publication pending**, **Repair verified**, **Newer edit needs review**. These are UI recommendations, not a second task board.

## Practical implementation order

1. First, complete the existing single-source repair journey: independent local regeneration, output readbacks and truthful consumer status. This addresses the concrete wiring gap with the smallest change.
2. Next, add applicable-source resolution and grouped review to reduce irrelevant duplicate findings and repeated approvals.
3. Then add behavior evaluations using the actual contradictions and failures already observed. Keep the existing mechanical tests; do not rewrite the repair engine.

No scheduled automation, agent-rule edit, hook edit, native Claude audit, approval Apply or provider change was performed for this research. The earlier pending rule proposal was not applied by this task.

## Sources, dates and limitations

Official pages were located with Exa search and fetched using Exa contents through Composio on **2026-10-21**. Live crawl was requested. Fetch success proves retrieved content, not vendor certification of this design. Page update dates were not exposed unless listed below; undated documentation is marked as such rather than assigned an invented date.

| ID | Source | Page date | Use |
|---|---|---|---|
| S1 | [GitLab: reviewing AI instruction files](https://docs.gitlab.com/development/ai_instruction_files_review/) | Not exposed; fetched 2026-10-21 | Ownership, source fidelity, provenance, review, generated projections and targeted fixes. |
| S2 | [OpenAI: custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | Not exposed; fetched 2026-10-21, canonical response redirected to ChatGPT Learn | Codex discovery, override order, size and session boundary. |
| S3 | [Anthropic: how Claude remembers your project](https://code.claude.com/docs/en/claude-md) | Not exposed; fetched 2026-10-21 | Scope/import behavior, conflicting rules, native prompt audit and prerequisites. |
| S4 | [Cursor: rules](https://cursor.com/docs/rules) | Not exposed; fetched 2026-10-21 | MDC activation metadata, scope, precedence and focused rules. |
| S5 | [OpenAI: harness engineering](https://openai.com/index/harness-engineering/) | 2026-02-11 | Short instruction maps, deeper sources, mechanical checks and targeted maintenance. |
| S6 | [Anthropic: demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | 2026-01-09 | Outcome-based evaluation, real failure cases and calibrated graders. |
| S7 | [Git: git-apply](https://git-scm.com/docs/git-apply) | Page version/date not captured; fetched 2026-10-21 | Read-only applicability checks and patch rejection behavior. |
| S8 | [Anthropic: CLI reference](https://code.claude.com/docs/en/cli-reference) | Not exposed; fetched 2026-10-21 | General print-mode contract only; not proof of prompt-audit headless integration. |
| L1 | `docs/LOCAL_FILE_AI_PROPOSALS.md` and `tools/local_file_ai.py` | Current checkout inspected 2026-10-21 | Bounded AI proposal behavior. |
| L2 | `docs/LOCAL_FILE_REPAIRS.md`, `tools/local_file_repairs.py`, `tools/local_files.py` | Current checkout inspected 2026-10-21 | Inventory, source ownership, frozen Apply, publication and Undo. |
| L3 | `~/.agents/tools/unify/hooks/post-commit` | Live file inspected 2026-10-21 | Existing asynchronous generation/publication control flow. |
| L4 | `~/.agents/tools/unify/build_instructions.py` | Live file inspected 2026-10-21 | Harness-specific outputs and rules-only mode. |

Research trace: Exa search logs include `log_nbBSah8s-NMS`, `log_X6N-nfpczOkB` and `log_kroz66Ws42HA`; verified contents logs are `log_hySipp_bekRQ` and `log_WRIA51ZiwseK`. The fetched six-page response is held in the task's temporary evidence directory; this report paraphrases rather than republishes vendor pages.

Live-file inspection fingerprints (SHA-256):
- `/Users/alexlobaito/.agents/tools/unify/hooks/post-commit`: `3bb8b8fe2c7788b39cb1a046ca1df8b1989fb712f91eee713b89aac2c070450c`
- `/Users/alexlobaito/.agents/tools/unify/build_instructions.py`: `0ee189da821540ff086f267eca50278f9a779981599b23f8167150dcf7afcf14`

Gaps: no universal method can prove arbitrary natural-language rules consistent; no whole-machine or every-project coverage was established; native Claude audit runtime/headless behavior and all consumer adoption were not tested. A fresh scoped experiment is required before replacing the existing proposal engine. Findings do not authorize implementation.
