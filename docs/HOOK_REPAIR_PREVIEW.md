# Actual hook repair in Review & fix

Alex's request, 2026-10-22: inspect and repair the executable hook, research the right fix first, and show a tested proposal before changing the installed source.

## What is reviewed

The registered source is `~/.agents/tools/approvals/receipt_store_guard.py`. The fixed owner follows the configured Claude, Codex and Cursor wrappers to their shared `receipt_store_guard.reason` dependency. These are inspected configuration/import relationships, not a claim that each host has fired the hook during this review.

`Inspect blocking hook` selects that source and prepares the repair intent. `Review & fix` retrieves the applicable official documentation, runs the baseline, asks AI for a narrow code repair, performs the existing separate simulation/documentary assessment, then runs the exact candidate in executable tests. Nothing writes to the live hook during proposal or testing.

## Research and decision

As of 2026-10-22, the installed CLIs reported Claude Code 2.1.301 and Codex 0.160.0. Retrieved official documentation is undated/unversioned unless the retrieval record says otherwise; matching installed versions remains a gap.

- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks): command hooks receive JSON through stdin. Exit 0 with no output leaves the ordinary permission flow intact; structured deny output or exit 2 blocks the tool. This defines the protocol tested here.
- [Python shlex reference](https://docs.python.org/3/library/shlex.html): shell lexical parsing handles quoting and tokens, but lexical splitting is not a complete shell interpreter. The existing guard already has a stricter parser which retains command boundaries and separators.
- Local source evidence: `read_only_command` requires every command segment to be read-only. When that proof fails, `command_targets` gathers operands across segments. The later trust-anchor scan can treat a proven source-view operand as an attempted modification because `source_view` recognizes only one simple command. A mixed source read plus unrelated script therefore needs an operation-level diagnosis.

**No vendor-native fix was found for this custom guard.** The proposed parser correction is a custom repair to Alex's code, informed by its existing contract and tests. Vendor documentation establishes the hook protocol; it does not endorse a particular change to Alex's approval policy.

## Executable proof

The server owns the test inputs and expected results. AI cannot supply a test command. Exact copied baseline and candidate bytes run with synthetic HOME and receipt paths. The requested commands are JSON input only; they are never executed.

The fixed profile checks the harmless mixed source read, an ordinary source read and inert vocabulary; genuine store writes/deletes, signer imports/copies and direct guard replacement/edit must remain denied. Malformed JSON must retain its documented deny response. The existing canonical `test_receipt_store_guard_narrow.py`, when present, runs in a separate confined controller. A proxy forwards each `reason` input to another confined process running the exact copied hook. Candidate stdout never supplies controller completion. Completion requires the statically counted tests to finish with zero failures, errors or skips. Its content hash is bound with the tested source and runner. The copied hook receives only the captured `approval_check.ID_RE` regex constant. The real checker, issuer and external approval service never run.

Before candidate execution, a fixed launcher initializes the native macOS sandbox with default deny. Existing nonsecret canaries prove denial of outside reads/writes, network connection and process fork/exec. Candidate/test files are read-only; only disposable scratch is writable. Processes have time, output, CPU and file-size limits. Native isolation failure is unavailable evidence, never an unsandboxed fallback. `sandbox_init` is deprecated and availability on future macOS versions remains a limitation.

## Approval and delivery

The preview separates executable results from AI simulation, syntax checks and documentary support. Failed/unavailable executable evidence remains visible and cannot be approved. One approval still binds the exact immutable bundle and existing native owner lifecycle, source readback, Git publication and conditional Undo. Coupled script/settings repairs install the approved source first and accept only the other exact frozen candidate hashes as dependencies.

The preview does not prove live hook activation, diagnosis of every historical refusal, or repair of all hooks. Only the specifically registered receipt hook has this executable profile. Other executable targets retain their stated syntax-only scope until a real behavior profile exists.
