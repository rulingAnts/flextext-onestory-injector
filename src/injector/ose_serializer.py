"""OneStory `<story>` serialization, byte-compatible with OneStory Editor.

PROVENANCE AND LICENCE
----------------------
The element/attribute inventory and ordering in this module is a Python
adaptation of the ``GetXml`` serialization in OneStory Editor:

    StoryEditor/VerseData.cs   -- VerseData.GetXml, LineData.AddXml, AddXmlField
    StoryEditor/StoryData.cs   -- the <story> element

    OneStory Editor is Copyright 2021 SIL International and is licensed
    under the MIT License. The above copyright notice and the MIT
    permission notice are reproduced in THIRD-PARTY-NOTICES.md.

The *byte formatting* below (UTF-8, CRLF between elements, two-space
indent, ``<x />`` with a leading space, no XML prologue) is NOT adapted
from OneStory Editor. It reproduces the defaults of .NET's XmlTextWriter,
which is what ``OseXmlSerializer`` ends up using, and was established by
measuring real project files rather than by reading anyone's source.

This file as a whole is part of an AGPL-3.0-or-later work. MIT permits
that combination; SIL's notice is retained as MIT requires.

WHY A HAND-WRITTEN EMITTER
--------------------------
No Python XML library reproduces .NET's output. ``ElementTree`` gets
``<x />`` right and can indent by two, but writes
``<?xml version='1.0' encoding='utf-8'?>`` with single quotes and LF
endings. Since we are splicing a fragment into an existing file we must
match its bytes exactly, so the string is built directly.

MEASURED FORMAT (from a real 141-story project and SIL's own sample)
--------------------------------------------------------------------
    encoding    UTF-8. Zero null bytes; the "writes UTF-16" comment in
                OseXmlSerializer.cs is simply wrong.
    prologue    VARIES between OSE versions -- `<?xml version="1.0"?>`
                with no BOM, or a BOM plus encoding and standalone. We
                never write one: we splice into the middle of a file.
    newlines    CRLF *between elements*. Text content may legitimately
                contain bare LF -- 8,946 of them live in note fields,
                because AddXmlField calls RemoveCarriageReturns on the
                value while the writer emits CRLF for structure. Never
                normalise a whole document.
    indent      two spaces per level
    empty       `<x />` -- space before the slash, 7,267 occurrences,
                zero tight `<x/>`
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import List, Optional

# Structural line break. Content newlines are deliberately NOT this --
# see the module docstring.
CRLF = "\r\n"
INDENT = "  "

# StoryLine order is fixed and order-significant: the schema declares an
# xs:sequence, and 0 of 2,511 verses in the reference project deviate.
# `lang` is one of these four KEYWORDS, never a BCP-47 code -- OSE's
# setter has a `default:` case that is a no-op in release builds, so an
# unrecognised value is silently discarded on load.
LANG_VERNACULAR = "Vernacular"
LANG_NATIONAL_BT = "NationalBt"
LANG_INTERNATIONAL_BT = "InternationalBt"
LANG_FREE_TRANSLATION = "FreeTranslation"

STORYLINE_ORDER = (
    LANG_VERNACULAR,
    LANG_NATIONAL_BT,
    LANG_INTERNATIONAL_BT,
    LANG_FREE_TRANSLATION,
)


def esc_text(value: str) -> str:
    """Escape XML text content, matching XmlTextWriter.

    XmlTextWriter escapes `&`, `<` and `>` in text nodes. It does *not*
    escape quotes there -- that is attribute-only -- so a story whose text
    contains a quote must not come back with `&quot;` or the round trip
    stops being byte-identical.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def esc_attr(value: str) -> str:
    """Escape an attribute value, matching XmlTextWriter.

    Attributes additionally escape the double quote, and escape CR/LF/TAB
    numerically so they survive attribute-value normalisation on re-read.
    In practice no attribute in the reference project contains any of
    them, but emitting a raw newline inside an attribute would silently
    corrupt the value on the next load.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\r", "&#xD;")
        .replace("\n", "&#xA;")
        .replace("\t", "&#x9;")
    )


def remove_carriage_returns(value: str) -> str:
    """Port of StoryData.RemoveCarriageReturns.

    OSE normalises field values to CRLF in memory on SetValue, then strips
    the CRs again when serializing. That asymmetry is why note fields in a
    real project contain bare LFs while the structure uses CRLF.
    """
    return value.replace("\r", "")


@dataclass
class StoryLine:
    """One `<StoryLine>`; `lang` must be one of the four keywords above."""

    lang: str
    text: str


@dataclass
class Verse:
    """One `<Verse>`.

    Attribute emission follows VerseData.GetXml exactly:
      * `guid` always
      * `first` ONLY when true
      * `visible` ONLY when false
    Anything else OSE can hold on a verse -- Anchors, TestQuestions,
    Retellings, ConsultantNotes, CoachNotes, ExegeticalHelps -- is
    deliberately never written. A `.flextext` contains none of it, and
    inventing it would be worse than omitting it.
    """

    guid: str
    lines: List[StoryLine] = dc_field(default_factory=list)
    first: bool = False
    visible: bool = True

    def line(self, lang: str) -> Optional[StoryLine]:
        for ln in self.lines:
            if ln.lang == lang:
                return ln
        return None


def render_verse(verse: Verse, depth: int) -> List[str]:
    """Render one `<Verse>` as a list of already-indented lines."""
    pad = INDENT * depth
    attrs = [f'guid="{esc_attr(verse.guid)}"']
    if verse.first:
        attrs.append('first="true"')
    if not verse.visible:
        attrs.append('visible="false"')
    head = " ".join(attrs)

    # A field with no data is OMITTED, never emitted empty: AddXmlField is
    # guarded on field.HasData, and all 5,802 StoryLines in the reference
    # project have non-whitespace text.
    present = [
        ln
        for lang in STORYLINE_ORDER
        for ln in (verse.line(lang),)
        if ln is not None and ln.text.strip() != ""
    ]

    if not present:
        # Self-closing, with the leading space XmlTextWriter emits.
        return [f"{pad}<Verse {head} />"]

    out = [f"{pad}<Verse {head}>"]
    for ln in present:
        body = esc_text(remove_carriage_returns(ln.text))
        out.append(f'{pad}{INDENT}<StoryLine lang="{esc_attr(ln.lang)}">{body}</StoryLine>')
    out.append(f"{pad}</Verse>")
    return out


def render_verses(verses: List[Verse], depth: int) -> List[str]:
    """Render the `<Verses>` container."""
    pad = INDENT * depth
    if not verses:
        return [f"{pad}<Verses />"]
    out = [f"{pad}<Verses>"]
    for v in verses:
        out.extend(render_verse(v, depth + 1))
    out.append(f"{pad}</Verses>")
    return out


def to_bytes(lines: List[str], trailing_newline: bool = True) -> bytes:
    """Join rendered lines with CRLF and encode UTF-8, no BOM.

    No XML prologue is ever produced: this output is spliced into an
    existing document whose prologue must be left exactly as found.
    """
    text = CRLF.join(lines)
    if trailing_newline:
        text += CRLF
    return text.encode("utf-8")
