# Consolidated edit independent findings

Compiled by supervisor from audit_build_sources read-only review. Full acceptance withheld.

**CONTROLLED-01 PARTIAL** POST edit API now exists; allowlist remains2fixtures and no frontend edit call. Maintained catalog/docs UI acceptance fails.

**CONTROLLED-02 PARTIAL** Only nonnegative integer revision and optional string label checked; maintained schema/stable IDs/refs/monotonic revision not validated.

**CONTROLLED-03 UNVERIFIED** No lock or final CAS; simultaneous stale writes, crash/restore and verified backup invariants missing.

**CONTROLLED-04 UNVERIFIED** Fixture freshCLI/hash proof only; no app restart or maintained canonical/derived view agreement.

**CONTROLLED-05 UNVERIFIED** Rename/delete/unreadable/malformed/original identity cases not tested.

**CONTROLLED-06 PARTIAL** Preview screened, lexical allowlist remains symlink escape risk; no endpoint-specific canary tests.

**CONTROLLED-07 PARTIAL** New proof only preview hash/negative revision; module/test/API source hashes omitted; prior fixture subproof not full acceptance.
