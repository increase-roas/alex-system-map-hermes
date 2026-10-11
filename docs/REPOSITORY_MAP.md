# Mapped repository lookup

Use [system-repository-lookup](../skills/system-repository-lookup/SKILL.md) before building a duplicate controller, connector wrapper or shared procedure. Canonical project folder: `skills/system-repository-lookup`; the three project discovery links use `../../skills/system-repository-lookup`. Resolve real paths before resolving skill document references. No global skill/config installation is part of this package.

## Catalog anchors and bounded candidates

The catalog retains historical repository metadata and source rows, not content inspection or runtime proof. Inspect the listed records rather than converting these lookup observations into canonical facts automatically.

| Repository | Catalog record and source row | Pinned tree SHA (observed 2026-10-09) | Candidate paths and interpretation |
| --- | --- | --- | --- |
| [increase-roas/alex-director](https://github.com/increase-roas/alex-director) | `record_9dcc24cf7ecbbf0845d2`; S04-04 GitHub row 24 | `808683875b32859d814374d256219870c8d76428` | `STACK.md`, `STACK_DETAIL.md`, `mission-graphs/`, `skills/`: existing Director/control-plane map and related source documents. `STACK.md` was read at this SHA; its own date is 2026-10-01 and its routes are subordinate to current app cards. |
| [increase-roas/agents-home](https://github.com/increase-roas/agents-home) | `record_1a52dfd4d46498b86fc7`; S04-04 GitHub row 28 | `2882cc41efb863601d2a64081ccc6d0442bab887` | `skills/`, `instructions/claude.md`, `instructions/claude-style.md`, `tools/connectors/hub/README.md`: shared skill/rule/connector source candidates. Tree proves these paths exist; it does not prove full coverage of today's local shared instruction home or installation on another host. |
| [increase-roas/master-connector-repo](https://github.com/increase-roas/master-connector-repo) | `record_ef6c863a2497fedabef1`; S04-04 GitHub row 29 | `bc6daa656b9314a0bf1db0e12d17df3e832b1988` | `tools/_inventory.md`, `tools/README.md`, `sources/2026-09-29_inventory-composio.csv`, `sources/2026-09-29_mcp-cli-api-inventory.csv`, `knowledge/`, `system/`: connector inventory and operational source candidates. `tools/_inventory.md` was read at this SHA; its dated counts/placeholders require a fresh check before use as current truth. |

The package retains metadata-only tree receipts at `reports/repository-trees/alex-director.json`, `reports/repository-trees/agents-home.json`, and `reports/repository-trees/master-connector-repo.json`. All three receipts state `truncated: false` and retain `paths` plus SHA. If receipts are absent after transport, repeat permitted live reads and store new scoped evidence; do not claim the old files are packaged here.

Current-session evidence: gh readback identified `increaseroasir`; private metadata/tree reads succeeded through the card's org route. The primary's Composio repository read with account `github_lipase-modern` returned `No connected account matched`; do not replace Alex's principal with active Javante. An expired Composio account and the card's historical org OAuth restriction are distinct observations. Recheck current route/card/identity before reuse.

Local comparison candidates on Alex's Mac are `~/Projects/master-connector-repo` (observed branch `fix/observatory-typed-receipts`) and `~/Documents/Codex/master-agent-operations-sdk` (observed branch `feat/sdk-mem0`). These branch observations are session checkpoints, not promises. No SDK remote was found in the current session; no GitHub URL or catalog mapping is invented for it. Locate/check a checkout on the current host before using these examples.

## Exact read-only examples

Run from the foundation package root for catalog calls. Use the current card first and stop if identity is not `increaseroasir`.

```bash
python3 tools/catalog.py search director
python3 tools/catalog.py record record_9dcc24cf7ecbbf0845d2
gh api -X GET user --jq .login
gh api -X GET repos/increase-roas/alex-director --jq '{full_name,private,default_branch}'
gh api -X GET repos/increase-roas/alex-director/commits/main --jq .sha
```

Pin the returned commit SHA for a current investigation. The literal SHA below reproduces this session's historical lookup; do not confuse it with today's main.

```bash
gh api -X GET 'repos/increase-roas/alex-director/git/trees/808683875b32859d814374d256219870c8d76428?recursive=1' --jq '{sha,truncated,paths:[.tree[].path]}'
gh api -X GET repos/increase-roas/alex-director/contents/STACK.md -f ref=808683875b32859d814374d256219870c8d76428 --jq '{path,sha,size,html_url}'
```

After checking the file size fits the task's bounded read, inspect the chosen nonsecret document through the contents endpoint with the same pinned ref. `-X GET` is essential: gh flags otherwise can turn a contents request into a mutation. Preserve pinned content URL and Git blob SHA in the evidence receipt. For local metadata comparison (no branch switching):

```bash
git -C ~/Projects/master-connector-repo branch --show-current
git -C ~/Projects/master-connector-repo rev-parse HEAD
git -C ~/Projects/master-connector-repo status --short
git -C ~/Documents/Codex/master-agent-operations-sdk branch --show-current
git -C ~/Documents/Codex/master-agent-operations-sdk rev-parse HEAD
git -C ~/Documents/Codex/master-agent-operations-sdk status --short
```

Do not print remote URLs that might embed credentials; compare sanitized owner/repository metadata only. Do not print config, secret-bearing files or logs. Existing path matches do not establish a maintained API contract: read its small defining files and record the exact revision before proposing reuse.

## Portable acceptance

Run these from the foundation package root with `check_acceptance.py`. Native creator structural validation is an additional host check, not behavioral proof.

```text
file:skills/system-repository-lookup/SKILL.md non-empty
file:docs/REPOSITORY_MAP.md non-empty
contains:skills/system-repository-lookup/SKILL.md::gh api -X GET user --jq .login
contains:docs/REPOSITORY_MAP.md::record_9dcc24cf7ecbbf0845d2
contains:docs/REPOSITORY_MAP.md::record_1a52dfd4d46498b86fc7
contains:docs/REPOSITORY_MAP.md::record_ef6c863a2497fedabef1
absent:skills/system-repository-lookup/SKILL.md::/Users/
cmd:python3 -c "from pathlib import Path; p=Path.cwd(); n='system-repository-lookup'; assert all((p/d/'skills'/n).is_symlink() and (p/d/'skills'/n).resolve()==(p/'skills'/n).resolve() for d in ('.cursor','.agents','.claude'))"
```

Configured local links and structural validity do not prove fresh Cursor selection, remote delivery, or successful repository reuse. Missing runtime selection receipt: `BLOCKED (missing_evidence)` for that claim.
