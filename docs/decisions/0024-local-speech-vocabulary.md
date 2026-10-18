# Local spelling context for speech recognition

Status after attended check: automatic app-name hints are an experimental opt-in,
OFF by default. Attended r1 passed only 1/4 exact cases; the owner confirmed both
literal-cord utterances were heard as Discord. This disproves treating synthetic
non-regression as owner accuracy. Private automatic hints were explicitly disabled
with backup. Optional custom terms can also bias recognition. No native retest
after disabling; original homophone problem remains unresolved. Preserve failures.

The owner reports hearing "Discord" transcribed as "this cord". Increasing the
model size and correcting capture do not by themselves supply expected spelling
for acoustically similar app/personal names. Do not hardcode a this-cord alias or
rewrite arbitrary recognized sentences into application requests.

Use faster-whisper's documented hotwords option as bounded decoder input. Collect
only friendly installed names through the existing fixed read-only application
catalog operation, when the private applications configuration enables it. Do
not inspect windows, launch apps, read paths into speech hints or expose new tools.
Audio discovery returns at most 64 validated names in its owned bounded IPC. Pass
them only to the next recording worker; never persist automatic OS vocabulary in
voice.toml, transcript history, logs or journals. Optional explicit user spellings
may be saved in private voice settings through the existing Settings dialog.

Explicit spellings precede compact OS names. Bound the combined vocabulary to 512
characters and 64 entries; use the active speech tokenizer to retain complete
terms under 160 tokens. No previous-chat conditioning, prefix command, LLM rewrite,
additional transcription pass, audio retry, new model or provider fallback. The
model may still choose ordinary words. Transcript confidence/review, exact corpus
gates, Stop, half-duplex, expiry and all existing broker qualifications remain.
Spelling hints are evidence/context, not application identity or permission.

GUI Settings provides optional one-per-line names and an automatic application-name
checkbox. Disabling automatic hints affects the next worker; user spellings are
independent. Catalog failure is surfaced as APP_VOCABULARY_UNAVAILABLE metadata;
speech retains its selected local recognizer, without hidden provider substitution.

Tests use synthetic app catalogs/names, verify fixed catalog-only access, bounds,
invalid IPC/control/path rejection, no automatic persistence, explicit settings,
disable behavior and absence of transcript replacement. Separate synthetic/native
fixtures distinguish Discord requests from literal cord sentences. Earlier failed
general-recognition corpus/results remain immutable; the new four-case spelling
corpus is not qualification of the original seven cases or full M6.

Reference: [faster-whisper hotwords API](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py).
