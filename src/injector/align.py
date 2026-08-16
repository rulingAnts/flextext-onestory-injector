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
  remaining tokens get holes/markers. A gloss with internal spaces is
  period-joined so it stays one token (``river.bank`` -- the Leipzig
  Glossing Rules convention for a multi-word gloss of a single element).

* Trailing holes are dropped from the emitted gloss line (D1): OneStory
  pads short gloss lines at the end anyway, so trailing ``***`` carry no
  information, while MEDIAL holes are load-bearing and always kept.
"""

from __future__ import annotations

from typing import List, Optional

HOLE = "***"

# Joins the words of a multi-word gloss into one token. A period follows
# the Leipzig Glossing Rules convention (child.PL, put.on), which FLEx
# users already read. Unlike HOLE and PHRASE_CONT this is a joiner, not a
# parsed marker, so uniqueness does not matter.
GLOSS_JOINER = "."

# Phrase-continuation marker (backward-pointing): this surface token belongs
# to the PREVIOUS token's gloss -- the pair was glossed as one analytical
# word. Distinct from HOLE on purpose: HOLE means "not glossed yet, work to
# do"; the marker means "deliberately glossed as a unit, nothing to do".
# Collision-checked: 0 of 15,723 gloss tokens in the reference project even
# contain a '<'. An exporter can reconstruct the original phrase-word from
# it; HOLE never can (ambiguous with genuinely unglossed).
PHRASE_CONT = "<"

# How to write the continuation tokens of a phrase-word:
#   "marker" (recommended): river.bank <      -- round-trippable, honest
#   "holes"  (plan D2):     river.bank ***    -- reads as unglossed work
PHRASE_MODES = ("marker", "holes")


def join_gloss(gloss: str) -> str:
    """Collapse whitespace runs in a gloss to single GLOSS_JOINERs.

    A gloss containing a space would split into two tokens and shift every
    following gloss one word left -- the exact failure the whole alignment
    exists to prevent.
    """
    return GLOSS_JOINER.join(gloss.split())


def gloss_tokens_for_word(
    baseline_text: str, gloss: Optional[str], phrase_mode: str = "marker"
) -> List[str]:
    """Gloss tokens for one ``.flextext`` word, honouring the phrase rule.

    Returns exactly as many tokens as ``baseline_text`` has surface tokens,
    so callers can concatenate per-word results and keep parity by
    construction.

    An UNGLOSSED phrase-word gets holes on every token regardless of mode:
    there is no unit gloss for a marker to continue, and holes are the
    honest "work to do" state.
    """
    if phrase_mode not in PHRASE_MODES:
        raise ValueError(f"phrase_mode must be one of {PHRASE_MODES}")
    n_surface = len(baseline_text.split())
    if n_surface == 0:
        return []
    g = join_gloss(gloss) if gloss and gloss.strip() else ""
    if not g:
        return [HOLE] * n_surface
    cont = PHRASE_CONT if phrase_mode == "marker" else HOLE
    return [g] + [cont] * (n_surface - 1)


def strip_trailing_holes(tokens: List[str]) -> List[str]:
    """Drop trailing holes only. Medial holes are load-bearing, and
    trailing PHRASE_CONT markers are never dropped -- they carry the
    phrase-word information."""
    end = len(tokens)
    while end > 0 and tokens[end - 1] == HOLE:
        end -= 1
    return tokens[:end]


def build_gloss_line(pairs: List[tuple], phrase_mode: str = "marker") -> str:
    """Build the NationalBt line from (baseline_text, gloss) word pairs.

    If no word has a real gloss, returns '' -- the StoryLine is then
    omitted entirely, which is the normal OneStory state for an unglossed
    verse (700 of 2,362 vernacular verses in the reference project).
    """
    toks: List[str] = []
    for baseline_text, gloss in pairs:
        toks.extend(gloss_tokens_for_word(baseline_text, gloss, phrase_mode))
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
