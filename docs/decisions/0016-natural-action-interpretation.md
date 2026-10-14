# 0016 — Natural action wording within existing controller scopes

The owner reported that minor changes in wording made Spotify, YouTube and app
control unusable. The active combined profile uses the legacy conversation path;
the earlier semantic conversation/currency/research work did not replace media
request parsing. This change applies to the shared backend used by GUI and terminal.

Read service, explicit owner operation and title as independent fields for simple
requests. Support a bare service suffix and polite requests. An explicitly named
playlist may default to Spotify only when the configured desktop backend is the
registered playlist-search capability. An unspecified generic song/video does not
silently choose a service. Prefer one exact retrieved title over substring matches;
duplicate exact titles or broad channel searches still require a genuine choice.

For unfamiliar action wording, use one bounded structured local-model call to
extract application/media, operation, service and literal target text. Reviewed
owner verb families limit operations; current configuration and controller-owned
service selection limit services. Target text must occur in the current request.
Queries never originate in history or model invention. This language stage has no
effect scope. It compiles accepted meanings into the existing controller entrypoint;
the original target resolution, model proposal, broker authorization, single-use
approval, journaling, cancellation and independent verification still apply.

Whole structured responses are strict, reject extra/duplicate fields, and bind
request identity/revision/deadline. Snapshot controller selection and profile before
interpretation and reject changes. Journal only request fingerprints and target
span indices, not raw prompts or extracted titles. Repeated request identities do
not repeat interpretation or effects. No model-supplied path, URL, command, selector
or browser primitive becomes authority. Negation, explanatory requests, private
URLs and unrelated compound mutations cannot acquire this action interpretation.

Explain capabilities from actual configured app/media context, including the
desktop Spotify search backend. Preserve controller-owned media selection across
ordinary conversation; clear pending multi-step continuation on unrelated requests.
This permits a fresh selected playback request without replaying unfinished work.

Real semantic fallback requires a separately matching passed `--language-report`.
The frozen wording corpora exercise actual local inference and independently observed
synthetic controller postconditions. Its acceptance is 100% correctness and zero
unauthorized dispatches. Reports bind profile, runtime/model digest, frozen corpus
and implementation contract. V1 is retained; v2 adds a negative word inside a real
song title, and v3 adds separation from general research/currency lookups. Existing
Notepad/app/media gates remain required and
are refreshed for changed contracts; historical reports and failed attempts remain.
Simulation can evaluate unqualified candidates. No Windows effect is exercised by
the wording evaluation, and it does not establish native UI compatibility.

Supported browser control remains the supervised YouTube/Netflix media controller.
General page interaction, arbitrary browser commands and generic UI are outside
this change. Native app/media testing still requires attended readiness and stop.

Native Spotify navigation can temporarily rebuild its labelled search control.
Repeat only read-only control lookup within the existing gate/deadline; never repeat
URI navigation, text delivery or invocation. Other identity/window errors fail
immediately, and cancellation or expiry stops the read wait. Live Chrome updates
still need explicit registration review; interpretation does not grant binary trust.
