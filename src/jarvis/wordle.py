"""Deterministic, duplicate-aware Wordle advice; never submits a guess."""

from collections import Counter
from pathlib import Path

from jarvis.domain import Denied


def feedback(answer, guess):
    if len(answer) != 5 or len(guess) != 5 or not (answer + guess).isascii():
        raise Denied("WORDLE_WORD_LENGTH")
    result = ["absent"] * 5
    remaining = Counter()
    for index, (letter, proposed) in enumerate(zip(answer, guess, strict=True)):
        if letter == proposed:
            result[index] = "correct"
        else:
            remaining[letter] += 1
    for index, letter in enumerate(guess):
        if result[index] != "correct" and remaining[letter] > 0:
            result[index] = "present_elsewhere"
            remaining[letter] -= 1
    return result


def load_words(path=""):
    """Explicit operator-owned dictionary, never today's answer or a hidden fetch."""
    file = Path(path) if path else Path(__file__).with_name("data") / "wordle-words.txt"
    if not file.is_file() or file.stat().st_size > 2_000_000:
        raise Denied("WORDLE_DICTIONARY_UNAVAILABLE")
    words = sorted(set(file.read_text(encoding="utf-8").split()))
    if (
        not words
        or len(words) > 20000
        or any(
            len(word) != 5 or not word.isascii() or not word.isalpha() or word != word.lower()
            for word in words
        )
    ):
        raise Denied("WORDLE_DICTIONARY_INVALID")
    return words


def solve(board, words):
    if any("?" in row.letters or "unknown" in row.feedback for row in board.guesses):
        return "Some submitted letters or tile colors are unclear. Please confirm them first."
    if len(board.guesses) + bool(board.incomplete) > 6:
        raise Denied("WORDLE_BOARD_INVALID")
    candidates = [
        word
        for word in words
        if all(feedback(word, row.letters) == row.feedback for row in board.guesses)
    ]
    if not candidates:
        return (
            "No word in the configured dictionary matches every row. "
            "Check the board interpretation or dictionary coverage."
        )
    if board.guesses and board.guesses[-1].feedback == ["correct"] * 5:
        return "The observed board is solved."
    if len(board.guesses) == 6:
        return "All six submitted rows are used. No next guess remains."
    counts = Counter(letter for word in candidates for letter in set(word))
    positions = Counter((index, letter) for word in candidates for index, letter in enumerate(word))
    ranked = sorted(
        candidates,
        key=lambda word: (
            -sum(counts[c] for c in set(word)),
            -sum(positions[i, c] for i, c in enumerate(word)),
            word,
        ),
    )
    prefix = "Ignoring the unfinished row, " if board.incomplete else ""
    return (
        f"{prefix}{len(candidates)} candidate(s) in the configured dictionary "
        "match every submitted row. "
        f"Try {ranked[0].upper()}; it favors common remaining letters and positions. "
        "This is advice only; I have not entered a guess."
    )


def board_advice(board, dictionary=""):
    rows = "\n".join(row.letters.upper() + ": " + ", ".join(row.feedback) for row in board.guesses)
    return (
        "Observed Wordle rows:\n"
        + (rows or "No submitted guesses.")
        + "\n"
        + solve(board, load_words(dictionary))
    )
