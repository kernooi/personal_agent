# Deterministic Wordle advice

Vision extracts a 6×5 board, submitted lowercase guesses and five feedback states:
`correct`, `present_elsewhere`, `absent`, `unknown`. Incomplete text is separate.
Unknown letters (`?`) or colors prompt confirmation instead of a guess. Wrong
dimensions, too many rows or malformed output are rejected.

The solver first matches exact positions, then allocates remaining unmatched
letter occurrences. Excess occurrences are absent. Each candidate must reproduce
every observed feedback row exactly. Gray never means globally absent when another
occurrence is green/yellow. Contradictions or dictionary gaps produce no candidate,
not a relaxed constraint. Recommendations rank distinct-letter frequency, positional
frequency and alphabetical tie-breaks. The solver never types/submits a guess.

The bundled historical possible-guess list is from
[Tab Atkins' wordle-list](https://github.com/tabatkins/wordle-list), pinned at commit
`255b9469c4dad99a3b95cc4ddbe139b3d3747868`, with 14,855 entries. Its MIT license,
source metadata and SHA-256 hashes are packaged under `src/jarvis/data/`.
It is not a current official NYT solution list or today's answer lookup. Some
historical guesses may be rejected by today's game. Candidate counts reflect only
this dictionary. A separately selected trusted local UTF-8 word list can replace it.
Nothing is fetched at runtime. No spoiler search occurs.

Synthetic fixtures and deterministic feedback tests establish solver behavior.
Actual screenshot-to-board accuracy requires local-model/Windows tests; a mocked
board does not establish real visual recognition. Displayed row interpretations
let the owner check unclear letters/colors before relying on a recommendation.

The initial native runs exposed incorrect or missing model letters; advice was
withheld and those failed readings are preserved. The current pipeline detects
a regular grid only for explicit Wordle questions, reads supported feedback colors
independently from pixels, and requires the local vision model to transcribe letters
into a strict row schema. The crop stays inside authorized pixels; analyzed regions
are recorded. Unsupported layouts/colors fall back to the original-image vision
path rather than inventing a grid.

Real local-model runs r4 and r5 read CRANE, then CRANE + SLATE correctly, including
all displayed colors. The solver found 180 and 39 historical-list candidates and
recommended AISLE and BAILE respectively. Both suggestions independently reproduce
every displayed clue. This is fixture evidence, not a claim about today's NYT board
or acceptance of every historical word.

The later owner-confirmed NYT layout used slightly different row and column
geometry. The detector now tests only nearby vertical height/spacing variants,
including half-pixel rounding, and complete symmetric inner/outer tile outlines.
Every submitted cell still needs exact supported feedback colors; incomplete,
irregular or contradictory grids are not accepted by relaxing colors/letters.
Two actual screen-to-broker-to-local-model-to-solver requests read one submitted
row and produced clue-consistent suggestions. See m5-nyt-board-layout-v1.json;
the actual letters were not independently ground-truth scored. Natural word
prediction requests use the same validation, and unsupported/unreadable boards
withhold suggestions instead of publishing an unchecked model guess.
