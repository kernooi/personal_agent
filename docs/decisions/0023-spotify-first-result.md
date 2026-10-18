# 0023: First Spotify result for play requests

Date: 2026-10-18. Implemented; fake/model qualification passed. Live playback
behavior was not retested for this selection change.

The owner requests immediate first-result playback when asking for music on
Spotify, instead of a numbered list and another choice turn. This standing
preference applies to song and playlist play requests in the existing installed
Spotify backend, through both GUI and terminal conversation.

SpotifyFlow chooses ordinal 1 from the fresh, successfully retrieved results for
a play goal. Explicit artist/playlist-owner constraints still require matching
title/creator metadata: choose the first result satisfying those constraints,
or explain that nothing was played if none match. Search-only requests still
show their results. No results means no selection or play.

The shared workflow gains selection/prompt hooks; its default YouTube behavior
is unchanged. Each search, selection and play remains a separate existing model
proposal/broker phase with exact target binding, journal, cancellation, expiry,
single-use approval and independent postcondition verification. No direct UI
effect, additional provider/model, account/library change, retry or replay.

Preserve m4-spotify-desktop-corpus-v1 and request-language-corpus-v3 plus all
historical reports. New desktop v2/language v4 fixtures express the owner-selected
behavior; their gates remain 100% correctness and zero unauthorized dispatches.
No earlier failure is converted into a passing report. The changed sources
invalidate existing bound M2, applications, language and media reports. Fresh
actual-local-model evaluation against synthetic targets is required before
real combined controls can start; do not bypass validation or edit old reports.

After reviewing the implementation, the owner explicitly resumed fake-only
tests and actual-local-model qualifications against synthetic targets for this
change. This does not authorize another native microphone/speaker or real app/
media test. Test results and report refresh must be recorded as actually observed;
live playback remains pending without separate attended scope.

Validation: 1658 fake-only tests passed. Actual qwen3:8b gates passed model 24/24,
conversation 41/41, apps 31/31, language 33/33, browser 27/27 and Spotify desktop
25/25, all with zero unauthorized dispatches. Existing qualification functions
accept all six fresh reports against the current profile/model/runtime/contract.
The shared launcher selects these reports; old reports remain untouched. See
[summary](../evaluations/spotify-first-result-qualification-v1.json).
