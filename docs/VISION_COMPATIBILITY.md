# Local vision compatibility and resource observations

## 2026-10-17 — Primary-model answer handoff

Validated image interpretations can now be explained by the active primary text
model through a dedicated private, read-only response contract. Both models remain
replaceable through configuration. The text stage receives structured evidence,
not pixels, and cannot invoke tools. Wordle remains deterministic. See
[the handoff report](SCREEN_CHAT_HANDOFF.md) for exact tests, timings and limits.
The change improves presentation/context; it cannot correct every perception error.

## 2026-10-17 — Incomplete GPU responses and CPU recovery

The owner's game-identification request failed after 16.865 seconds during vision.
Its redacted journal category was `VISION_CANCELLED_OR_INCOMPLETE`. The actual
private Ollama log shows `Unexpected empty grammar stack after accepting piece:
@ (31)`, runner exit status 1 and HTTP 200. This was a runtime failure, not proof
of user cancellation. [Related qwen2.5vl GPU failures](https://github.com/ollama/ollama/issues/18369)
are reported upstream; that report does not independently prove the precise CUDA
cause on this machine. A subsequent authorized full-main-display read succeeded:
0.871 s capture, 7.696 s vision. Game identification accuracy was not independently
scored, and no screenshot or private description was saved.

The adapter now distinguishes actual cancellation from an incomplete runtime
response. For explicit `done:false` with an empty or matching model identity, it
may make **one CPU retry** using the same installed model and a bounded derivative
of the same in-memory image. It never recaptures, uploads, changes models, accepts
partial JSON or extends the existing action/inference deadline. Cancellation,
model identity/digest, completion, truncation and strict interpretation/Wordle
validation still apply. Missing completion fields or another model do not trigger
recovery. Ordinary GPU requests retain their original resolution and settings.

Two optional private `screen.toml` settings control this path (defaults shown):

```toml
cpu_retry_on_incomplete = true
cpu_retry_max_pixels = 147456
```

These belong at the top level, before any `[companion]` table. Recovery downsizes
only oversized images, preserves the whole image/aspect ratio, and reports that
fine details may be unclear. A 2560×1440 frame becomes 512×288 at the default cap.
It adds no click/type or other desktop effects. A game name should be supported
by a visible title/logo or distinctive evidence; otherwise the prompt calls for
uncertainty rather than guessing a famous title.

Actual recovery checks used synthetic pixels, an explicitly simulated first
incomplete response, and real local CPU inference. This proves the recovery path;
it does not claim a deterministic reproduction of the original GPU crash:

- `m5-vision-cpu-recovery-v1.json`: real CPU result on the same small synthetic
  image, 43.50 s; runtime reported zero VRAM allocation for that model.
- `m5-vision-cpu-fullscreen-v1.json`: full-resolution CPU recovery hit the existing
  60 s transport limit. Failed evidence preserved, no partial answer accepted.
- `m5-vision-cpu-fullscreen-v2.json`: bounded 512×288 derivative of a 2560×1440
  synthetic frame completed in 46.78 s, strict output accepted, resolution warning
  included. CPU prompt evaluation accounted for 41.10 s. Original deadline and
  transport limits remained unchanged.

CPU recovery is substantially slower and may still time out under load. Tiny text,
game titles and Wordle recognition through the thumbnail path remain unqualified.
This workaround improves failure handling; it does not repair the upstream runtime
or establish universal vision accuracy. No driver/runtime/model was installed or
downloaded. Historical failures and broader M5 limits remain in place.

Inspection on this machine found only `qwen3:8b` (Q4_K_M, 5,225,388,164 bytes),
advertising completion/tools/thinking but no vision. The runtime reported
Ollama 0.40.2. No vision download is implicit in M5 or GUI startup.

Initial candidate: `qwen2.5vl:3b`, approximately 3.2 GB, advertised for image/text
and structured document/object understanding. The [official model entry](https://ollama.com/library/qwen2.5vl:3b)
specifies Ollama 0.7.0 minimum. Alternatives include [gemma3:4b](https://ollama.com/library/gemma3:4b)
(approximately 3.4 GB, minimum 0.6) and the larger [llama3.2-vision:11b](https://ollama.com/library/llama3.2-vision:11b).
These catalog claims are selection inputs, not JARVIS compatibility measurements.

Actual host: RTX 4070 (12,282 MiB VRAM, 11,243 MiB free at initial inspection),
Ryzen 5 5600X, 33,454,824 KiB visible system memory; approximately 20,112,512 KiB
free at inspection. Workload changes these figures. This is the desktop, despite
the older laptop context in the original spec. No laptop fit or latency is claimed.

The owner approved and downloaded qwen2.5vl:3b into the existing private model
directory. Current installed digest is
`79d4979787523c92629bc043c0584a5132d6758e40b429586203a6b1094cb6f8`,
3,203,638,247 bytes, qwen2vl/clip 3.8B Q4_K_M, advertising vision and completion.
The first downloaded tag reported digest
`fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1`
and 3,200,627,168 bytes; the identity changed after initial loading. The cause was
not established. Later r4/r5 runs used the stable current digest. The adapter now
checks digest both before and after each inference and rejects a changed identity.
No other vision model was installed and qwen3 remains the main chat model.

The runtime successfully performed real image inference. One concurrent nvidia-smi
snapshot showed 5,568 MiB used, 6,444 MiB free and 38% GPU utilization; this is
whole-GPU use, not isolated or peak model memory. First cold error inference took
37.58 seconds (39.406 seconds end to end); the later four-workflow r5 run took
7.86–9.901 seconds per request end to end. These measurements do not promise
latency under another GPU workload. Vision uses one request at a time, configured context
and output limits, a task deadline and `keep_alive=0`. The text model need not
remain resident: Ollama may evict it under memory pressure. JARVIS does not promise
immediate model unloading or alter other software's GPU use.

`VisionProvider.inspect/analyze` keeps models replaceable. The Ollama implementation
reuses the existing bounded HTTP client, checks installed digest/local identity and
advertised vision before capture, rejects remote identities and parses a complete
strict observation schema. It has no tool calls, arbitrary endpoints or pull API.
The owning profile's verified local-mode evidence is reused, not newly attested.

Full-main-display inference at 2560x1440 required 4,254 input tokens for the
reported request, exceeding the initial private 4,096 context. The runtime
rejected it with HTTP 400 before producing an answer. Private vision configuration
and the example now use context_tokens=8192; the text context stays unchanged.
The same real broker request then succeeded with 0.795 s capture and 9.392 s
vision inference. This is pipeline evidence, not independently scored word advice.
Restart chat after changing the private configuration.

Actual live-model image quality and timings are recorded in M5_TEST_REPORT.md and
the preserved native reports. Error text and two Wordle states passed; the public
photo was described as an orange flower with species uncertain. Species-level
recognition and peak RAM/VRAM/CPU measurements remain unverified. Mocks verify
the interface and policy; they cannot establish OCR/vision accuracy.
