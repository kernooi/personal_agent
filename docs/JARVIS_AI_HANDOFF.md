# JARVIS: portable AI handoff

## Read first

Read AGENTS.md and the full project specification before architectural changes.
[Current state](JARVIS_CURRENT_STATE.md#current-update-2026-10-18) summarizes the
latest behavior; [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md) owns progress and
[BUILD_LOG](BUILD_LOG.md) owns actual commands/results. Preserve the existing
uncommitted work, frozen corpora and all failed evaluation reports.

M6 speech accuracy remains unresolved. small.en and Kokoro/Michael are installed
and selected privately; base.en is preserved. Automatic application-name speech
hints are OFF after attended literal-cord false positives. See [voice setup](VOICE.md),
[M6 evidence](M6_TEST_REPORT.md) and [decision 0024](decisions/0024-local-speech-vocabulary.md).
Do not claim a fix from synthetic speech or relax acceptance gates. Fake tests and
local-model simulation qualifications are authorized; fresh native microphone,
speaker, screen or app/media tests need their own attended scope/readiness.

## Original architecture handoff: historical snapshot

The sections below describe the original 2026-10-17 audit. Subsequent voice
implementation and test outcomes are maintained in the linked documents above,
not duplicated as a growing list of "latest" entries in this handoff.

Snapshot: **2026-10-17**, Asia/Kuala_Lumpur. Audited repository baseline: **d96c1c4**, `Add M5 screen assistance, animated companion and natural vision answers`. This document reports inspected source and existing evidence. The audit ran no tests, inference, service probes or desktop actions and changed only the two requested context reports. It contains no credentials, account data or screenshots.

**Do not assume a capability is missing solely because it belongs to a later milestone in the original specification. Inspect the implementation first.**

## Product and current stack

JARVIS is an existing local-first Windows desktop assistant with a real chat GUI and terminal interface. It is not an unrestricted autonomous computer operator. The model proposes bounded actions; trusted controllers and the permission broker resolve targets, authorize delivery and independently verify outcomes. The owner values natural conversation and straightforward app/media use, while the current repository retains strict safety, registration and qualification boundaries.

The recorded target PC runs Windows 11 build 26200 with RTX 4070/12 GB, 32 GB RAM and Ryzen 5 5600X; M6 rechecked CPU/RAM/GPU resources. Python 3.13.2 runs in `.venv`, with package support >=3.12,<3.14. Stack: Pydantic, HTTPX/HTTPCore, SQLite, Tkinter/Tcl, ctypes/comtypes UIA, Playwright/installed Chrome, WinRT media and pypdf. M6 adds locked sounddevice/PortAudio, faster-whisper/CTranslate2 CPU int8, NumPy and installed Windows SAPI. No Electron frontend, GUI HTTP server or speech cloud is required.

## What already works

Implemented capabilities include local text chat, simulated execution, real packaged Microsoft Notepad lifecycle, discovered installed-application open/focus/restore/minimize/normal-close, bounded public web research, generic provider-supported currency conversion, dedicated Chrome YouTube search/playback, native Spotify playback plus song/playlist search, real read-only screen questions, deterministic Wordle advice, bounded screen watching and an animated desktop orb. GUI and terminal use the same controllers. These capabilities have different evidence levels; do not label the whole system complete because some paths pass.

The private combined setup enables apps, currency, SearXNG, YouTube, Spotify desktop and screen reads. Netflix and screen watching are disabled. The primary text model is `qwen3:8b`, served by standalone Ollama 0.40.2 on fixed `127.0.0.1:11434`; the separate vision model is `qwen2.5vl:3b`. Existing cloud-disabled evidence is operator verified. Loopback/version checks do not cryptographically attest a reused server's cloud configuration.

The active combined text profile is `profiles/notepad-m2-concurrent-v1.toml`: `planner-m2-v10`, `decision-m2-v1`, context 4096, output 512, task 120 seconds, thinking disabled, two-minute residency and targeted window input. It omits `assistant_version`, which means **legacy mode**. Optional semantic `assistant-v1` and faster `assistant-v2` implementations/examples exist, but are not automatically active. Do not mistake candidate code or historical qualification for the current launch configuration.

## How the GUI actually works

Launch the existing GUI with:

```powershell
.\.venv\Scripts\pythonw.exe scripts\Chat-JarvisGUI.py
```

It is a dark slate Tkinter application with rounded chat bubbles, antialiased branding/send artwork, an expanding composer with focus/placeholder feedback, smooth scrolling, copy/full-message viewing, activity dots/elapsed time, session controls, Details diagnostics and Stop/Esc. The visible reminder explains attended real app/media scope and Ctrl+Alt+Shift+F10. Animations and real controls are deliberately always selected for this dedicated GUI by prior owner instruction. Ordinary CLI/profile defaults remain simulation.

`Chat-JarvisGUI.py` imports `Chat-JarvisAll.py`'s command factory. `ChatSession` prepares services in a background startup thread, launches `jarvis.gui_worker` over private stdin/stdout pipes and reads framed events on another thread. `gui_worker` invokes the existing CLI chat loop, framing whole output callbacks as `ready`, `reply` or `diagnostic`; model text cannot manufacture framing. Tk timers poll a bounded queue on the main UI thread. Responses are complete messages, not streamed tokens or displayed internal reasoning. Multiline composer text becomes one bounded terminal request. Rendering keeps at most 256 bubbles/150,000 characters; model conversation context is separately bounded.

The GUI supports shared tools/slash commands plus local wake addressing with "JARVIS", voice status and Settings beside Details. Spoken replies are always on; the manual Mic/Stop speaking controls and speech toggle were removed. Voice remains a half-duplex frontend to ChatWindow.send_text, not a new assistant. Owned workers handle bounded capture/STT/SAPI; only addressed requests reach the GUI/backend, approval/control text needs review, and stale results cannot submit. Capture pauses through processing/speech; Stop/Esc/global stop retain authority. Settings can disable microphone listening. Explicit lab mode keeps manual PTT. Voice and M5 share one orb with screen privacy priority. No recordings enter logs or text IPC, no runtime model downloads, and missing setup leaves text chat usable. Wake changes remain untested at owner request. Registration/inspection/evaluation remain CLI/scripts; no model picker/onboarding, reminders view or account manager exists.

## Startup and shutdown

The dedicated GUI automatically prepares already approved local infrastructure through `gui_startup.py`. It validates private startup/profile configuration and the registered standalone Ollama executable hash/version, reuses the expected server or starts it with process-local cloud-disabled/loopback/private-model settings. A fresh launch must log cloud disabled. It checks installed models, preloads only the configured text model with an empty request and observes `/api/ps`. It never downloads weights.

In parallel it checks the existing local Docker Desktop Linux engine and owned SearXNG container. It can start installed Docker Desktop or recreate a removed ephemeral container only from the approved cached digest-pinned image, existing private mounts, loopback binding and `--pull never`. No machine installation, image download, startup entry or restart policy is added. Search service failure can leave local chat available with a warning; missing required files or model readiness blocks startup. The plain combined terminal launcher does not perform this service bootstrap.

The child CLI loads strict configs, inspects model metadata, validates separate real-mode qualification reports, composes adapters, opens its journal and registers the global stop hotkey. Missing/changed registration or qualification fails without simulated/cloud substitution. End session/window close sends stop/quit cooperatively. App effects already delivered cannot be rolled back by cancellation. The managed Chrome context closes; unrelated apps are not force-killed. Infrastructure services remain running.

## Architecture, state and authority

Trace requests through `cli.py`/`bootstrap.py`, `ApplicationConversation` and `Conversation`, owner intent/language handling, `Broker`, registry/adapters, then independent observations and presentation. Not every turn is a generic model-tool loop: controllers route explicit capabilities, and some requests use specialized typed model stages. Fixed YouTube/Spotify workflows perform search, resolve, open and play as separate broker transactions. There is no universal multi-step task planner or persistent routine engine.

`core.py`, `policy.py`, `storage.py` and `domain.py` implement scope/revision/session/deadline/grant checks, exact single-use approvals, intent journaling before effects, cancellation at admission, request deduplication and evidence-bound completion. SQLite persists tasks, actions, attempts, events and consumed approvals. It is an action journal, not a personal memory vault. Ordinary raw chat prompts/reasoning are not saved as transcript history. Some canonical arguments and evidence metadata persist; do not claim the journal contains no user-related data.

Conversation keeps 16 in-memory messages with byte/context reservations and oldest-pair eviction. Numeric operands, media selections and screen dialogue are specialized transient context. Unknown delivered outcomes still require manual review and never automatic replay; the current code has not removed those gates. Targeted lifecycle mode tolerates unrelated input/focus changes while preserving the named exact target. This exception does not authorize arbitrary typing/clicking or general browser interaction.

## Windows, research and currency

Application discovery uses trusted Windows AppsFolder metadata and verified EXE/package identities, including bounded signed launcher/runtime association. It cannot open any arbitrary path on any device. Some entries are unsupported, elevated, tray-only or absent from discovery. Historical 145-supported/51-unavailable catalog counts are not native tests of every app. Sole/selected verified windows generally need no reference confirmation; ambiguity still needs selection. Normal close may hide an app to tray rather than terminate it. Notepad text, unsaved changes, mixed tabs or unknown state always block automatic close. No save/discard or force kill is exposed.

Public research uses the user-controlled local **SearXNG JSON API**, not Brave or a paid required provider. Replaceable provider contracts exist; an additional provider name alone is not an implemented adapter. JARVIS separately validates public URLs, fetches HTTPS pages, extracts bounded HTML/text/PDF, tracks dates and binds citations to retrieved excerpts. Public fetch rejects localhost/private destinations, rechecks DNS/peer/redirects, and does not inherit browser credentials. Only the configured loopback search endpoint has its separate infrastructure permission. Some sites block requests or require JS/login; no bypass is implemented. Queries derive from the current owner public topic, not private history/screens. Small web caches are session-only. Broad semantic/freshness/conflict qualification remains incomplete despite a passing narrow retrieval gate.

Currency uses fixed Frankfurter v2/ECB endpoints and validated provider metadata, supporting provider-advertised codes rather than only MYR/JPY or an invented ISO list. Amount arithmetic is local Decimal; only pair parameters are disclosed. Effective date, retrieval/expiry, source provenance, cache/stale policy and refresh/source inspection exist. Rates are daily reference estimates, not executable bank prices. Identity/supplied-rate paths do not fetch but require cached membership. Explicit monetary intent is required; unrelated numeric questions/topic changes should release currency context. Bounded language coverage can still limit complex wording.

## Browser and Spotify

Playwright launches installed signed stable Chrome with a dedicated persistent private JARVIS profile, never attaches to ordinary Chrome, and exposes reviewed semantic media operations. Manual login is allowed; cookies stay separate from public research. Chrome updates can require registration refresh. YouTube search/open/current/play/pause/resume have live evidence, but ads, service state and manual interaction remain important failure boundaries. Current-video inspection supports a controlled handoff after manual ad skipping. This is not general website automation.

Spotify backends are explicitly selected: official Web API, Windows playback-only, or installed desktop search. The current desktop backend uses verified Store Spotify, exact-package encoded search URI, labelled accessibility search/filter/result controls and independent Windows media state. Named songs/playlists can proceed on unique verified matches; ambiguous titles/owners require numbered choices. The app must expose its expected visible search/results UI. No generic keystrokes, account/library changes, scraping credentials or web-player fallback exist. Reported playback is not proof of audible sound. Netflix title/manual-login and Spotify API code exist, but live setup/validation is incomplete; Netflix protected playback is unsupported.

## Screen understanding and companion

With enabled private screen configuration, “What am I looking at?” through the GUI can request a real main-monitor screenshot without a per-request selection prompt. Optional selected-window/all-monitor scopes remain distinct. Native GDI captures visible pixels into transient PNG; geometry, session/identity, exclusions, password/protection flags, expiry, cancellation and a visible stop indicator are checked. This cannot see hidden/minimized/protected content or guarantee detection of all secrets.

Local vision produces structured description/text/objects/activity candidates and uncertainty. Private vision context is 8192. One explicitly incomplete GPU response may retry on CPU using a bounded thumbnail of the same frame, same model and deadline; it may lose detail or take 45–60 seconds. A new fixed handoff passes bounded structured evidence to the primary text model once for natural explanation, with no action tools or public research. Invalid synthesis falls back honestly. Up to two fresh same-target screen discussion pairs remain private and clear on topic change/revoke. Reference binding does not prove correct perception or entailment.

Wordle uses image grid/color work, local letter reading and deterministic duplicate-aware filtering over a licensed historical word list. It never enters guesses. Watching exists as separately enabled bounded foreground-window sampling; private watching is currently off, and full real-vision watch validation remains open.

The black orb with two animated white eyes is implemented and connected to actual capture/analysis events. Native GDI+ rendering, alpha overlay, Tcl timers, gaze/blinks/fades, click-through, nonactivation, capture exclusion and stop/shutdown checks exist. A smaller rounded charcoal stop badge replaced the red panel; its latest appearance lacks native visual retesting. Existing short performance evidence is about 60 FPS, not a soak guarantee.

## Evidence, gaps and next work

Latest M6 full suite: **1587 passed in 53.45 seconds**, including 56 new voice/UI cases; lint/format/dependencies clean. Fresh local-model/fake-effect gates pass: apps 31/31, browser 27/27, Spotify 25/25, language 33/33. All six strict readers match, retaining unchanged Notepad 24/24 and conversation 41/41 reports. The initial stale-app reader report is preserved alongside the later pass. Earlier two-model synthetic integration passed 7/7 without real screen capture. Native app/media/vision/orb reports remain separate historical evidence. M6 enumerated 8 microphone endpoints, 4 outputs and 2 SAPI voices, but performed no real recording/playback or STT-model inference. Broad M5 and M6 remain **NOT FULLY VERIFIED**; neither mocks nor old native passes establish new speech acceptance.

Confirmed gaps include bounded wording, incomplete research semantics, unreliable/slow vision, app/service-layout dependencies, stale historical documentation and machine-specific launcher/report filenames. Large controllers and cooperative shutdown warrant soak review. M6's implementation exists, but its English base.en asset setup, real microphone/speaker/interruption, device-loss and voice-to-screen GUI acceptance are pending. No reminders, calendar/email, persistent personal memory, user routine engine, proactive briefings or consumer installer exists.

Prioritize pending M6 download/attended approvals, native audio acceptance and remaining M5/reliability work. The explicit setup and production-GUI synthetic-fixture lab are prepared in `scripts/Setup-JarvisVoice.py` and `scripts/Test-JarvisVoice.py`; neither downloads nor records automatically. Then consider durable reminders/notifications, inspectable memory, scoped calendar/email and typed routines before briefings. Later add hardware-aware onboarding/installer release tests. General visual UI remains separately scoped M8 work; stop after M6 for owner review.

Read `AGENTS.md`, `JARVIS_Project_Specification.md`, `README.md`, `docs/JARVIS_CURRENT_STATE.md`, dated build/implementation records and ADRs 0010/0012/0014–0019 first. Trace current launcher, GUI transport, CLI composition, broker, then relevant adapter/tests. Keep secrets/private profiles outside Git; never copy another PC's `.venv`, registration or qualification as authority. Preserve failures and acceptance gates. Ask before installations, model downloads, new account authority or attended native testing. Do not implement later milestones from this audit alone. When evidence is absent, say **“Not verified from available code/evidence.”**
