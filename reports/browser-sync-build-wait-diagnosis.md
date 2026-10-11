# Browser sync build wait diagnosis

UNVERIFIED — root cause and effective deadline. The current build remains present at the last observation; no build success is claimed.

Observations13:09:01–13:10:21UTC: shell56200→npm56212→node56233 stayed present, elapsed07:34→08:54, CPU0.0%, sleeping state. Its project fd12 moved from Next builtin-request-context.js to route-matcher.js. This demonstrates changing dependency-file activity, not compilation percentage or an ETA.

Two exact reads of builtin-request-context.js succeeded in0.022s/0.021s,1148bytes, SHA3e86a0515c7ce492f8ab348a0d723b7fc55877bdbb9573ee702288a03db5b4f3. A bounded1second sample exposed read/uv_fs_read/kevent labels. Raw stack output was discarded. Neither observation establishes a code defect, deadlock or general filesystem latency.

The visible successor command chain contains npm run build/next build without a visible timeout wrapper. An external outer deadline is NOT_PROVEN. The predecessor receipt955300be remains saved with its actual600second timeout; that timeout does not prove this successor is bounded.

Proof: `reports/run-receipts/browser-sync-recovery-20261010-1249-955300be-c21b-4676-92eb-30f1e7436f1d.json` SHA `93e535e886165db3cc9a1ce7e4ebc2d80910365b514b8cec24483b82af1af97e`; safe ps/lsof/read/sample projections are recorded in the JSON. SKIP_ACCEPTANCE_BUILD finding remains `reports/browser-sync-build-drift-20261010-1304.json`; it is not accepted as build evidence.

Primary should keep a single build owner and establish the existing successor deadline/cleanup before any retry. Capture actual exit/build result when it completes. If a retry is needed, sole implementation owner must use the required bounded production build path and verify the previous process group is gone. This diagnosis grants no signal or implementation authority. Never use SKIP_ACCEPTANCE_BUILD as successful build evidence.

external_wait — actual successor exit/result and effective deadline/cleanup remain missing. Accepted transaction guards preserved. This diagnosis changed only its two report files.
