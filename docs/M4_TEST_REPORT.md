# M4 validation report — 2026-10-11

Spotify follow-up: Windows media backend is live-tested on Spotify Store package
1.304.258.0. Final checks: 927 tests passed; lint/format/dependency/diff clean.
Current model gates pass 12/12 native cases (`m4-windows-media-model-v1-r3.json`)
and 22/22 original cases (`m4-qwen3-8b-simulation-v1-r12.json`). Attended report
`m4-windows-spotify-v1-r2.json` passed current/pause/resume/next/previous and physical
global stop with zero new admissions; failed harness report r1 preserved. No API
credentials or global media keys. See BUILD_LOG and ADR 0007 for limits and the
final backwards-compatible API scope serialization fix after native validation.

Verdict: **NOT FULLY VERIFIED**. Implementation and offline checks are present;
the attended YouTube workflow and physical stop passed. The user's later selected
Spotify Windows backend also passed live playback and physical stop (see below).
Optional Spotify API and Netflix setup remain pending. No M5/M8 work, commit or push.

## Environment and baseline

Started from clean commit `885c8ff`. Baseline: 753 tests passed in 21.91 seconds;
lint, formatting and dependency checks passed. Python 3.13.2 on
Windows 11 10.0.26200, RTX 4070 / 32 GB / Ryzen 5 5600X.
Installed signed stable Chrome 154.0.8037.98, Playwright 1.63.0.
See [binary identity and browser limits](BROWSER_COMPATIBILITY.md).

The dedicated empty profile was created at
`%LOCALAPPDATA%\Jarvis\browser\chrome`; registration and YouTube-only media config
are private under `%LOCALAPPDATA%\Jarvis`. No everyday Chrome state was copied or
attached. Added locked project-only Playwright 1.63.0, greenlet 3.5.6 and pyee 13.0.1;
no bundled browser or model download. Existing local Ollama 0.40.2 was retained.
The actual current startup log at 2026-10-11 13:00:35.111+08:00 says
`Ollama cloud disabled: true`; endpoint is 127.0.0.1:11434. This is observed startup
evidence, not programmatic cloud/offline attestation. No server settings changed.

## Commands actually run

All Python commands use `.\.venv\Scripts\python.exe` from the repository.

| Command | Exit/result |
| --- | --- |
| `-m piptools compile --extra dev --extra windows --extra browser --strip-extras --allow-unsafe --generate-hashes --output-file requirements-dev.lock pyproject.toml` | 0; generated lock |
| `-m pip install --require-hashes -r requirements-dev.lock` | 0; project `.venv` only |
| `-m pip install --no-deps --no-build-isolation -e .` | 0 |
| `-m jarvis inspect-chrome` | 0; installed signed stable Chrome identity |
| `-m jarvis register-chrome --output "$env:LOCALAPPDATA\Jarvis\chrome-registration.json"` | 0; exclusive empty private profile creation, no browser launch |
| `-m pytest -q --tb=short` | Final 0; 909 passed in 23.06 s (baseline 753; 156 new M4 tests) |
| `-m pytest tests/test_media.py tests/test_browser_worker.py tests/test_browser_protocol.py -q --tb=short` | 0; intermediate 144 passed in 2.13 s; subsequent tests included in full 909 |
| `-m ruff check .` | Latest 0 after fixing line lengths/imports |
| `-m ruff format --check .` | Final 0; 98 files |
| `-m pip check` | 0; no broken requirements |
| `git diff --check` | 0 |
| `-m jarvis doctor --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" --media-config "$env:LOCALAPPDATA\Jarvis\media-m4-v1.toml"` | 0; model ready, browser not launched, no public providers contacted |

Offline tests use fake browser/service state; real sockets and process launch are
forbidden in the broker fixtures. They cover strict records/RPC, stale replies and
generations, ordinals, result mutation, revocation/expiry/single-use authorization,
journal privacy, unsupported operations, cancellation, timeout/crash/manual review,
DNS/private destinations, installed-Chrome launch options/profile leases, downloads,
YouTube identity/state classifications, Netflix title selection, Spotify denial,
expiry/scopes/devices and accepted commands with wrong observed playback.

## Actual local model, fake media

Command prefix: `-m jarvis eval-media --live --profile
"$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" --report
docs/evaluations/<report>.json`. Uses qwen3:8b digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`,
Ollama 0.40.2, unchanged simulation profile and frozen 22-case corpus.

| Report suffix | Exit | Actual result |
| --- | --- | --- |
| `m4-qwen3-8b-simulation-v1-r1` | 1 | 8/22; unnecessary model clarifications; zero unauthorized effects |
| `m4-qwen3-8b-simulation-v1-r2` | 0 | 22/22 after required fields and narrow planner instructions |
| `m4-qwen3-8b-simulation-v1-r3` | 0 | 22/22 after lint/source finalization |
| `m4-qwen3-8b-simulation-v1-r4` | 1 | 21/22; unique title incorrectly clarified; zero unauthorized effects |
| `m4-qwen3-8b-simulation-v1-r5` | 0 | 22/22 after unique title instruction and diagnostics |
| `m4-qwen3-8b-simulation-v1-r6` | 0 | 22/22 after metadata/read-only ad wait changes |
| `m4-qwen3-8b-simulation-v1-r7` | 0 | 22/22 after visible locator/error classification |
| `m4-qwen3-8b-simulation-v1-r8` | 0 | 22/22 after player-title fallback and DNS classification |
| `m4-qwen3-8b-simulation-v1-r9` | 0 | 22/22; source used for successful attended Chrome workflow |
| `m4-qwen3-8b-simulation-v1-r10` | 0 | 22/22; current source, after presentation and Spotify configured-limit fixes |

Failed reports are preserved. Qualification is source/profile/model/runtime/corpus
bound with a 100% gate; historical passes do not qualify changed source. This is
actual local inference with fake media, not real-platform verification.
The final source contract is
`3bde788a34167e29894a5153dac8ac7fae66c17951505a3c291274f40eccffb1`.
An observational check returned True for current M4 qualification and both existing
M2 model/conversation answer-only reports. Those older M2 reports are preserved,
not newly attended Notepad evidence. Prior failed assistant-v2 reports remain failed.

## Attended installed Chrome

With explicit user readiness, ran `-m jarvis test-media --windows --attended
--interactive --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml"
--browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json"
--media-report docs/evaluations/m4-qwen3-8b-simulation-v1-r3.json
--report docs/evaluations/m4-windows-youtube-v1-r1.json`.

Exit 1. Actual model → Conversation → broker → installed Chrome search took
7.602 seconds and ended NEEDS_REVIEW without verified observation. No open/play
step followed. The owned test context closed during lab cleanup. The user confirmed
Chrome opened and then closed. No automatic replay occurred. This run exposed
missing retained worker diagnostic classification; subsequent code retains safe
typed failure codes. Subsequent attended runs were explicitly authorized; each
unknown outcome required the user's manual confirmation before another test.

| Live report suffix | Matching model report | Exit/result |
| --- | --- | --- |
| `m4-windows-youtube-v1-r1` | model r3 | 1; unknown search, diagnostic unavailable |
| `m4-windows-youtube-v1-r2` | model r5 | 1; search verified; open saw correct ID/ad but no title, no playback claim |
| `m4-windows-youtube-v1-r3` | model r6 | 1; search verified, open automation error; no replay |
| `m4-windows-youtube-v1-r4` | model r7 | 1; network policy stopped search; diagnostic retained |
| `m4-windows-youtube-v1-r5` | model r8 | 1; search/open verified; ad did not clear within bounded wait |
| `m4-windows-youtube-v1-r6` | model r9 | **0 / PASS**; full actual model/Chrome workflow and physical global stop |

Each run used the command above with the corresponding model/live filenames.
Final successful command was:

```powershell
.\.venv\Scripts\python.exe -m jarvis test-media --windows --attended --interactive `
  --profile "$env:LOCALAPPDATA\Jarvis\profiles\notepad-m2-v10.toml" `
  --browser-registration "$env:LOCALAPPDATA\Jarvis\chrome-registration.json" `
  --media-report docs/evaluations/m4-qwen3-8b-simulation-v1-r9.json `
  --report docs/evaluations/m4-windows-youtube-v1-r6.json
```

Actual verified public video ID: `dQw4w9WgXcQ`; title: Rick Astley - Never Gonna
Give You Up (Official Video) (4K Remaster). Bounded search: 5.170 s; open: 2.680 s;
play: 1.250 s; pause: 1.116 s; resume: 1.149 s; current: 0.733 s. Five read-only
samples observed ad/ad/ad/ad/playing; no ad skip or requested-playback claim during
ads. Dedicated-profile launch-only autoplay permission allowed natural ad playback;
no global preference or restriction bypass. The native hotkey was observed with
Chrome focused; the next pause was CANCELLED in 0.007 s with **zero new admissions**.
All desktop/Notepad execution counters remained zero. Owned context closed normally.

The successful native worker and browser adapter are unchanged after this live run.
Final changes improve the browser/Notepad mode banner, natural cancellation display,
and Spotify's configured result limit; these passed offline regression and fresh
model qualification r10. The historical live report keeps its actual source hash.
Audible audio, normal-Chrome coexistence and live user-takeover behavior are not
established. Offline takeover/generation tests passed; do not claim live coverage.

Spotify: **BLOCKED** — no approved OAuth token/account/device setup. Official API
adapter and deterministic tests exist, no authenticated web fallback.
Netflix: **NOT RUN** — manual dedicated-profile login pending. Title search/open
is implemented but live compatibility unverified; protected playback unsupported.
The user explicitly selected "Leave Spotify and Netflix setup pending" after the
YouTube test. No account creation, token request, login or new service setup ran.
See [service setup and restrictions](MEDIA_COMPATIBILITY.md).

## Remaining limits

No arbitrary browser selectors/JS, account mutation, uploads, downloads, CAPTCHA
or DRM bypass. Public research/currency never inherit browser auth. Bounded public
labels alone enter media proposals; private queries/labels/auth are omitted from
journal records. Browser DNS filtering is not full background-traffic or peer
attestation. Compound search-and-play needs separate turns. Stop/cancellation after
delivery may leave an unknown effect and requires manual inspection.

Important code: `media_data.py`, `media_tools.py`, `browser_worker.py`,
`browser_transport.py`, `chrome_identity.py`, `spotify_api.py`, `media_evaluation.py`,
`media_lab.py` and existing broker/storage/policy/CLI integration. Persistent
instructions, examples, generated lock, ADR 0006 and privacy/compatibility documents
were added/updated. Prior milestone results and unrelated work remain preserved.
Final Git status/diff inspection contains source, tests, non-secret examples and
public synthetic/lab evidence only. No profile directories, cookies, storage-state,
tokens, credentials, screenshots, raw authenticated DOM or private journals were
added. The complete private browser profile remains outside Git. Exact interactive
startup commands are in [README](../README.md).
