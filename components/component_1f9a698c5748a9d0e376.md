# Remote-file transport performs identity/path checks, backups, revision fencing, readback, and restore

ID: `component_1f9a698c5748a9d0e376`

Remote file operations resolve a bound provider/account/host/path, reject path escapes and route mismatch, save preimages before writes, check expected digests, separately inspect readback, and restore from retained backup.

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

A changed file on an isolated scratch path is not evidence that Hermes loaded it or that the intended agent behavior changed.

## Source records


## Evidence pointers

- `ev_32bd137d93ad527c7c33` — FILE CATALOG row 936 (Saved source row; no new live test)

## Recorded relationships


## Open questions and issues

- `issue_e60976c995de3756da2b`: Current runtime health not established. A changed file on an isolated scratch path is not evidence that Hermes loaded it or that the intended agent behavior changed.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
