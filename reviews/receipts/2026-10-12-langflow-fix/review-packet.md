NODE: langflow-local-tailnet-fix-20261012
WORKER: Codex GPT-6
IMPLEMENTATION: 31d08cf

ACCEPTANCE:
1. Local browser imports, edits, saves, reloads and runs a harmless Langflow flow using the installed pinned engine.
2. Existing private tailnet endpoint renders the current checkout and saved flow, with no save/run/import/stop capability remotely.
3. Remote health exposes neither local credential nor filesystem paths; spoofed local Host cannot elevate a tailnet caller.
4. Narrow browser panels do not overlap; keyboard operation remains usable.
5. Previously missing Judge score connections and legacy routing connections render.
6. Automated regression tests and production compilation pass.

EVIDENCE: RESULTS.md, network.json, build.log, local-run.png, mobile-390.png, tailnet-readonly.png, tailnet-dom.txt, implementation diff.

Independent same-family technical review passed. Other-family review is pending spending authorization through the documented Claude Bridge route. Only Director may mark VERIFIED.
