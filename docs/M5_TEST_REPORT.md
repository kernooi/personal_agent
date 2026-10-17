# M5 test report — 2026-10-15

**Milestone: NOT FULLY VERIFIED.** Implementation and limited real local vision validation are present. Remaining compatibility and recognition gaps are not waived. No M6/M7/M8 capability was implemented.

2026-10-17 private handoff: the primary text model now explains structured vision
observations through a bounded read-only schema. Both models ran sequentially on
synthetic image data; frozen corpus plus the two-model case passed 7/7. Full suite
1531 passed, six current-source controller/language gates pass, and GUI simulation
startup reaches ready. No native screenshot or real app/media effect was used for
this change. Perception accuracy remains limited; source references alone do not
prove every paraphrase. See [handoff implementation and evidence](SCREEN_CHAT_HANDOFF.md).

2026-10-17 follow-up: diagnosed the game's incomplete answer as an Ollama runner
crash, added one bounded same-frame CPU recovery and corrected the misleading
stopped-request message. Synthetic full-display recovery succeeded after a
documented full-resolution CPU timeout; no real screenshot was stored. Full pytest
1501 passed. See [runtime diagnosis and exact recovery evidence](VISION_COMPATIBILITY.md).
The initial failed response in recovery tests was explicitly injected; actual CPU
inference and strict parsing were real. Game/thumbnail recognition accuracy remains
unverified. Existing screen privacy, cancellation, expiry and local-only constraints
were retained.

Subsequent owner-authorized usability change: explicit screen questions now read
the whole main monitor without selecting a window or confirming each capture.
Optional window selection remains. Actual main-display capture passed at 2560x1440,
DPI 96 with no stored image; full-screen recognition was not rerun. See
[capture evidence](evaluations/m5-whole-screen-native-v1.json) and the latest
BUILD_LOG entry for regression/qualification results. This supersedes the initial
mandatory display-selection instructions, not exclusions or local-only handling.

Full-display inference subsequently exposed a 4,254-token request exceeding the
initial 4,096 vision context. Raising only private vision configuration to 8,192
resolved the runtime rejection; real 2560x1440 capture plus local inference through
the broker succeeded. See [context correction evidence](evaluations/m5-screen-context-fix-v1.json).
No private screenshot/description was retained and game-answer accuracy was not
independently scored in that retest. The earlier capture-only evidence remains
distinct from this later inference pass.

The owner subsequently reproduced an unaccepted vision result even at context
8192 and identified the game as NYT Wordle. The regular-grid detector had assumed
identical row/column spacing; the displayed board used different vertical pixel
rounding. Bounded independent vertical geometry now finds its one submitted row.
Two real main-display broker reads with the original second-word phrasing extract
letters and produce suggestions independently consistent with every observed clue.
Vision took 4.476 / 4.665 s. Letter ground truth was not independently scored.
See [NYT layout evidence](evaluations/m5-nyt-board-layout-v1.json).

Failures now have fixed safe stage/category messages and `/screen-status` reports
loaded context. Concise output bounds and explicit truncated-response rejection
prevent partial answers from becoming guesses. Unknown exception text and private
validation inputs are not persisted. These changes do not remove broader M5 gaps.

## Implementation

Created: `screen_data.py`, `screen_capture.py`, `screen_worker.py`,
`screen_indicator.py`, `screen_vision.py`, `screen_image.py`, `screen_tools.py`,
`screen_fake.py`, `screen_fixture.py`, `wordle.py`, packaged `data/wordle-*`,
`scripts/Test-JarvisScreen.py`, `tests/test_screen.py`, `tests/test_screen_image.py`,
`config/examples/screen.toml`, this report, capture/privacy/vision/Wordle docs and
decision 0017. Python modules are under `src/jarvis/`.

Modified: AGENTS, README, pyproject package-data, BUILD_LOG, IMPLEMENTATION_PLAN,
shared Chat-JarvisAll launcher, application/media/M2 evaluation contract hashes,
application_tools, conversation, CLI, core broker, policy, storage and terminal.
No dependency was added. Existing GUI uses the shared launcher and CLI worker;
no separate GUI model or vision execution path was introduced.

`screen_data.py` defines strict configuration, targets, private observations and Wordle output. `screen_capture.py` and `screen_worker.py` implement bounded native visible-pixel capture with exact process/window identity, exclusion checks and lossless PNG. `screen_vision.py` sends only authorized images and bounded visual context to the configured local image model. `screen_tools.py` uses the existing broker, grants, cancellation, journal and independent binding checks. No model chooses capture paths, arbitrary regions or executable actions.

`screen_indicator.py` provides a visible responsive capture indicator and session notification invalidation. Conversation, application chat, CLI, terminal and the shared GUI launcher integrate screen questions and scope controls. Startup does not capture. Normal chat/web history and logs receive no screenshot or private description. The current and one previous structured observation support bounded comparisons; image history is not retained.

`wordle.py` implements two-pass duplicate-letter feedback and exact candidate filtering. The packaged 14,855-word historical dictionary has source, license and hashes. A strictly detected regular grid can be cropped inside authorized pixels; supported feedback colors come from pixels and the local model transcribes letters using a required schema. Unknown/contradictory evidence withholds advice. The solver does not type, submit guesses or look up today's answer.

## Host and approved setup

Actual host: Windows 11 Home 10.0.26200, Ryzen 5 5600X, 33,454,824 KiB system memory, RTX 4070 / 12,282 MiB VRAM, existing project-local Python 3.13. Initial free memory was 20,112,512 KiB RAM / 11,243 MiB VRAM; these are snapshots.

Initially only text-only qwen3:8b was installed. After explicit owner approval, downloaded qwen2.5vl:3b using the existing standalone Ollama 0.40.2:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = "$env:LOCALAPPDATA\Jarvis\models"
$env:OLLAMA_NO_CLOUD = '1'
& "$env:LOCALAPPDATA\Jarvis\runtime\ollama-v0.40.2\bin\ollama.exe" pull qwen2.5vl:3b 2>&1 |
  Out-File -LiteralPath "$env:LOCALAPPDATA\Jarvis\m5-vision-download.log" -Encoding utf8
```

Exit 0. Current vision digest: `79d4979787523c92629bc043c0584a5132d6758e40b429586203a6b1094cb6f8`, 3,203,638,247 bytes, qwen2vl/clip 3.8B Q4_K_M, completion + vision. The initially reported tag digest changed after first loading; cause unestablished, both identities are recorded in VISION_COMPATIBILITY.md. Before/after inference digest checks now reject identity changes. qwen3:8b remains the main chat model, unchanged digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.

Created the absent private `%LOCALAPPDATA%\Jarvis\screen.toml` from the example, enabled on-demand capture with qwen2.5vl:3b. Watching remains disabled in that file. No runtime installation, other model download, OS/global setting, startup entry, administrator request or cloud fallback. The existing verified text-profile local-mode evidence was reused; this session did not restart Ollama or create a new cloud-disabled startup attestation. Doctor is observational.

## Actual native/model evidence

All captures were restricted to the newly owned fixture. No ordinary app, full display or private user content was captured. Actual image region was 802-by-622 physical pixels, DPI 96. Reports refuse overwrite and failed reports are retained.

| Evidence | Actual result |
|---|---|
| Native capture-only r1/r2 | Failed indicator handshake; Windows CRLF fixed |
| Native capture-only r3 | Correct covered-window denial; no occlusion bypass |
| Native capture-only r4 | Four genuine captures passed; scripted interpretation, no recognition claim |
| Real vision r1–r3 | Error/illustration read, but Wordle letters missing/wrong; advice withheld |
| Real vision r4 and r5 | Error text, public flower photo and both Wordle states passed limited content review |
| Excluded owned Python window, r5 | CAPTURE_EXCLUDED; capture generation zero |
| Physical stop, r5 | User pressed Ctrl+Alt+Shift+F10 with fixture focused; next request CANCELLED, zero new captures |
| Watch r1–r3 | Foreground acquisition/wait failures; reports retained |
| Watch r4 | Three genuine native samples, one change, stopped at bound; scripted interpretation, not live-vision watching qualification |
| Actual lock/disconnect, protected/password windows | NOT RUN natively |
| Full display/desktop, high DPI, multi-monitor movement | NOT RUN natively |

See [real vision r5](evaluations/m5-screen-windows-v1-r5.json) and [native watching r4](evaluations/m5-screen-watch-windows-v1-r4.json). The watch-only report's `pipeline_passed=false` means it did not run the separate four-scene pipeline; its own watch exit gate passed with three samples and one change. Earlier pipeline success alone was never a recognition accuracy pass.

The model read the pandas ModuleNotFoundError and gave relevant advice. It described the public photograph as an orange flower with radial petals and left the species uncertain; **species identification is not validated**. It read CRANE and then CRANE + SLATE with all expected colors. The solver found 180 then 39 candidates, recommended AISLE then BAILE, and an independent feedback simulation verified both suggestions against every displayed row. Historical dictionary words may not be accepted by today's game. This is not a live NYT-site test.

The photograph is the scikit-learn sample `flower.jpg`, obtained from its official repository and displayed only in the fixture. Its [source README](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/datasets/images/README.txt) specifies CC BY 2.0 and links the flower to [Flickr / vultilion](https://www.flickr.com/photos/vultilion/6056698931/sizes/z/in/photostream/). The private fixture PNG was resized to 640-by-427 using Windows System.Drawing. The first Wikimedia candidate returned HTTP 403 and was not bypassed. No image is committed as a screenshot history. A private owned-fixture diagnostic image was used during debugging and removed afterward.

## Performance and deterministic checks

First cold error inference: 37.58 seconds vision / 39.406 seconds total. Later r5 end-to-end timings: error 9.901 s, photo 8.912 s, Wordle 8.837 s, refresh 7.86 s. Capture calls were typically 0.39–0.81 s. One whole-GPU snapshot during vision: 5,568 MiB used, 6,444 MiB free, utilization 38%. Peak isolated RAM/VRAM/CPU were not measured. One request at a time, bounded images/context/output/deadlines and `keep_alive=0` limit residency; this is not a latency guarantee.

Final full pytest: **1,407 passed**, exit 0, 59.40 s. Focused screen suite: **84 passed**, exit 0, 1.92 s, including post-inference model identity change rejection and required Wordle letter schema. Lint, formatting, dependency and diff checks exited 0. Six existing text/controller qualifications pass unchanged 100% gates; M2 r3/r4 failures remain preserved. Simulation GUI-worker startup reached Ready, accepted /quit, exited 0 and had empty stderr; screen configuration was omitted from that no-effects probe. Observational doctor reported configured screen with captured=false and browser_launched=false. Exact commands/reports are recorded in BUILD_LOG.md. No tests/gates were weakened. Initial fake-profile/expectation failures and stored-success validation omission were fixed rather than deleted. Existing frozen corpora and all earlier results are retained.

## Remaining completion gates

M5 is usable for explicit permitted-window questions on this PC, with conservative failures. It is not fully verified: real vision across a bounded watch session, species-level recognition, wider real-app/site corpus, native exclusion/protection and lock/disconnect transitions, high DPI/multi-monitor and full-display scopes remain unvalidated. Geometry/event mocks are not hardware evidence. A fresh M5 recognition corpus needs broader independent scoring before claiming general screen reliability. Full-display tests require their own explicit scope approval.

GDI cannot see covered/hidden/minimized/protected/offscreen pixels. The visible indicator must remain outside a selected window. Display capture can reject shell or inaccessible intersecting windows. Oversized targets fail; general tiling, downscaling, OCR fallback and full-document reading are not implemented. Exclusion heuristics cannot detect all secrets. Public research never inherits screen data. Existing app/media capability gates remain separate and mandatory.
