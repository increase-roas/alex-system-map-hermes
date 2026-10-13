# Langflow repair and browser acceptance

Observed October 12, 2026, America/Detroit. Worker: Codex GPT-6. Implementation commit: 31d08cf. Current served checkout: /Users/alexlobaito/Projects/system-map-ir. Professional standard used: server-side least privilege, deny-by-default remote permissions, same-origin local bootstrap, optimistic version checks, regression tests plus real browser and engine acceptance.

## Seen working

- Local browser imports the existing harmless chat-echo fixture into the saved flow store.
- Editing Input Text to `Local browser save verified` and saving succeeded, changing the version from 9f513a4830 to d4bbfd5349.
- Run 67d8edd7 returned `Langflow browser acceptance 2026-10-12` using engine 1.12.5 and the saved version. A second harmless run also succeeded.
- Reload retained the saved flow setting and the first completed run in the same browser session.
- Tailnet browser renders the same saved flow and explicitly says read-only. Import, Save and Run controls are disabled. Owner-only run history is absent remotely.
- The tailnet browser downloaded valid Langflow JSON using Export JSON.
- All 17 GEPA connections render, including all three previously missing Judge score connections. All 18 routing-template connections render. No missing-handle error008 remains in those checks.
- Actual browser viewport 390x844 measured, document width 390. Component-list bottom 412.2 and settings/sidebar top 424.2: separate by 12px, no overlap. Keyboard Tab from Message to the flow reaches Run. Desktop measured 1440x1000 with sidebar within viewport; default 1280 screenshot also inspected.

## Access boundary

All 11 live network checks passed in network.json. Tests include real Serve reads and rejected import/save/run/stop methods; spoofing localhost Host through real Serve returned 403. Unlisted-identity and untrusted-Host cases also tested locally with synthetic headers.

Remote /api/health has exactly ok and loopback_only; no local token or paths. Cache-Control is no-store. The local bootstrap still supplies the owner credential exclusively over trusted loopback requests for existing app compatibility. That credential was rotated without logging its value. Listener is 127.0.0.1:3200. Both npm dev/start now default to loopback. The existing tailnet owner login has read-only access in ignored app/.data/langflow/access.json. No new identity or public exposure was introduced.

## Automated checks

- Langflow tests including real engine: 59 passed, zero failures/skips. Command: LANGFLOW_LIVE_ENGINE=1 LANGFLOW_LFX_BIN=$HOME/.venvs/langflow-dashboard/bin/lfx LANGFLOW_CONFIG_DIR=$HOME/.venvs/langflow-dashboard/config node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/*.test.mts
- Flow node-kit suite passed, including four tests that failed before the fix.
- Network regressions reproduced three failures before the fix and passed afterward; remote health regression also passes.
- Final npm run build exit 0; see build.log. Build skips lint by project configuration, so this is not a lint-pass claim.
- Independent same-family verifier reran policy, route and network tests, inspected source, and repeated live read-only health/permission checks. No actionable defect found. This is not other-family or Director acceptance.

## Evidence and limits

Evidence: local-run.png, mobile-390.png, tailnet-readonly.png, tailnet-dom.txt, network.json, build.log. Browser screenshots during emulation were subject to the in-app pane capture scale; the dimension and overlap assertions above use actual DOM measurements. The default-viewport tailnet screenshot was visually inspected.

No physical phone, touch gestures or separate tailnet device was exercised. Real Stop remains covered by a stand-in process test; browser runs finished before a Stop check could be exercised. Development console includes transient React Flow sizing warnings during viewport/navigation changes; no console errors were captured on the local Langflow or tailnet tabs. The React Flow Pro subscription warning is informational; the project owns Pro.

The existing development server remains running on loopback port 3200 and private Serve remains configured to that port. No boot-time startup installation or new recurring job was created. Existing generated Python cache changes and pre-existing review packet were left untouched. Source changes were committed; backups are under ~/Backups/system-map-langflow-fix-20261012.

Formal other-family alex-reviewer receipt and Director acceptance are pending. The Claude Bridge card states every invocation has a startup cost; no paid review was launched without spending approval.
