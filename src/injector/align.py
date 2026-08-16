"""Vernacular/gloss tier alignment for the OneStory direction.

Ported from ``docs/js/interlinear-align.js`` in ``ose-interlinear-viewer``
(AGPL-3.0-or-later, same copyright holder -- no third-party rights involved),
plus the import-direction rules that module does not need:

* HOLE (``***``) is the only way to express "this word has no gloss" in a
  whitespace-paired string. OneStory Editor's own splits pass
  ``StringSplitOptions.RemoveEmptyEntries`` (GlossingForm.cs), so a doubled
  space is discarded -- an empty slot is UNREPRESENTABLE and a hole must be
  a visible token. ``***`` is what FLEx shows for a missing analysis, and
  0 of 1,662 gloss lines in the reference project contain even one ``*``.

* Phrase-words (gotcha 3): a ``.flextext`` word whose baseline text contains
  an internal space is ONE analytical word over several surface tokens.
  OneStory has no such concept -- a single space is the entire word model --
  and neither does the Adapt It glossing integration. So the surface tokens
  are kept verbatim in the Vernacular line (fusing them would alter the
  text), the joint gloss goes under the FIRST surface token, and the
  remaining tokens get holes. A gloss with internal spaces is
  underscore-joined so it stays one token (the rumah_besar rule, D2).

* Trailing holes are dropped from the emitted gloss line (D1): OneStory
  pads short gloss lines at the end anyway, so trailing ``***`` carry no
  information, while MEDIAL holes are load-bearing and always kept.
"""

from __future__ import annotations

from typing import List, Optional

HOLE = "***"


def underscore_join(gloss: str) -> str:
    """Collapse whitespace runs in a gloss to single underscores.

    A gloss containing a space would split into two tokens and shift every
    following gloss one word left -- the exact failure the whole alignment
    exists to prevent.
    """
    return "_".join(gloss.split())


def gloss_tokens_for_word(baseline_text: str, gloss: Optional[str]) -> List[str]:
    """Gloss tokens for one ``.flextext`` word, honouring the phrase rule.

    Returns exactly as many tokens as ``baseline_text`` has surface tokens,
    so callers can concatenate per-word results and keep parity by
    construction.
    """
    n_surface = len(baseline_text.split())
    if n_surface == 0:
        return []
    g = underscore_join(gloss) if gloss and gloss.strip() else ""
    first = g if g else HOLE
    return [first] + [HOLE] * (n_surface - 1)


def strip_trailing_holes(tokens: List[str]) -> List[str]:
    """Drop trailing holes only. Medial holes are load-bearing."""
    end = len(tokens)
    while end > 0 and tokens[end - 1] == HOLE:
        end -= 1
    return tokens[:end]


def build_gloss_line(pairs: List[tuple]) -> str:
    """Build the NationalBt line from (baseline_text, gloss) word pairs.

    If no word has a real gloss, returns '' -- the StoryLine is then
    omitted entirely, which is the normal OneStory state for an unglossed
    verse (700 of 2,362 vernacular verses in the reference project).
    """
    toks: List[str] = []
    for baseline_text, gloss in pairs:
        toks.extend(gloss_tokens_for_word(baseline_text, gloss))
    toks = strip_trailing_holes(toks)
    if all(t == HOLE for t in toks):
        return ""
    return " ".join(toks)


def collapse_whitespace(text: str) -> str:
    """Single spaces only, trimmed (D11).

    Matches the collapse the viewer's exporter applies, so
    export -> inject -> export is stable, and matches how OneStory itself
    tokenises (single-space delimiter, empties removed).
    """
    return " ".join(text.split())
