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


# ---------------------------------------------------------------------------
# Story level
# ---------------------------------------------------------------------------
#
# Attribute order is part of byte-exactness, and it is not a guess: all 141
# stories in the reference project use ONE ordering, with every attribute
# always present. Measured, not read off the schema.
STORY_ATTR_ORDER = (
    "name",
    "stage",
    "TasksAllowedPf",
    "TasksRequiredPf",
    "TasksAllowedCit",
    "TasksRequiredCit",
    "CountRetellingsTests",
    "CountTestingQuestionTests",
    "guid",
    "stageDateTimeStamp",
)

# Member roles inside <CraftingInfo>, in emission order.
MEMBER_ROLES = (
    "StoryCrafter",
    "ProjectFacilitator",
    "BackTranslator",
    "Consultant",
    "Coach",
)


def render_member_role(role: str, member_id: str, depth: int) -> List[str]:
    """Render one member-role element, as two lines.

    These are NEVER self-closed: the element carries whitespace-only
    content, which forces the open/close form. Measured on a binary read of
    the reference project, the separator is CRLF plus the element's own
    indent, identical in all 414 occurrences:

        <StoryCrafter memberID="...">
        </StoryCrafter>

    Two lines are returned rather than one string, so the caller's CRLF
    join produces the break -- returning an embedded newline here would put
    a literal '\\n' in the middle of a "line" and diff against every story
    OSE has written.
    """
    pad = INDENT * depth
    return [f'{pad}<{role} memberID="{esc_attr(member_id)}">', f"{pad}</{role}>"]


@dataclass
class CraftingInfo:
    """`<CraftingInfo>`.

    ``non_biblical`` is the ONE thing the user must be asked: OneStory is
    used for both biblical and non-biblical storying, and a project holds a
    mix -- 93 biblical to 48 non-biblical in the reference project. There is
    no safe default, so the injector prompts rather than guessing.

    Note the attribute is negative (`NonBiblicalStory`), so a *biblical*
    story is ``NonBiblicalStory="false"``. Easy to invert by accident.
    """

    non_biblical: bool
    story_crafter: Optional[str] = None
    project_facilitator: Optional[str] = None
    back_translator: Optional[str] = None
    consultant: Optional[str] = None
    coach: Optional[str] = None

    def member_for(self, role: str) -> Optional[str]:
        return {
            "StoryCrafter": self.story_crafter,
            "ProjectFacilitator": self.project_facilitator,
            "BackTranslator": self.back_translator,
            "Consultant": self.consultant,
            "Coach": self.coach,
        }[role]


def render_crafting_info(info: CraftingInfo, depth: int) -> List[str]:
    pad = INDENT * depth
    flag = "true" if info.non_biblical else "false"
    out = [f'{pad}<CraftingInfo NonBiblicalStory="{flag}">']
    for role in MEMBER_ROLES:
        member_id = info.member_for(role)
        if member_id:
            out.extend(render_member_role(role, member_id, depth + 1))
    out.append(f"{pad}</CraftingInfo>")
    return out


@dataclass
class StateTransition:
    """One `<StateTransition />` inside `<TransitionHistory>`.

    Attribute order measured across 1,272 real occurrences, all self-closed:
    LoggedInMemberId, FromState, ToState, TransitionDateTime, WindowsUserName.

    The injector emits exactly ONE, with FromState == ToState == the story's
    stage, preserving the invariant that a story's `stage` equals its last
    ToState (141/141 in the reference project). WindowsUserName is honest
    provenance -- the injector's own name plus hostname, never a fabricated
    MACHINE\\User pretending a person did this.
    """

    logged_in_member_id: str
    from_state: str
    to_state: str
    transition_datetime: str
    windows_user_name: str


def render_transition_history(
    transitions: List[StateTransition], depth: int
) -> List[str]:
    pad = INDENT * depth
    out = [f"{pad}<TransitionHistory>"]
    for t in transitions:
        out.append(
            f'{pad}{INDENT}<StateTransition'
            f' LoggedInMemberId="{esc_attr(t.logged_in_member_id)}"'
            f' FromState="{esc_attr(t.from_state)}"'
            f' ToState="{esc_attr(t.to_state)}"'
            f' TransitionDateTime="{esc_attr(t.transition_datetime)}"'
            f' WindowsUserName="{esc_attr(t.windows_user_name)}" />'
        )
    out.append(f"{pad}</TransitionHistory>")
    return out


@dataclass
class Story:
    """A `<story>`.

    Every attribute is always emitted -- 141 of 141 in the reference project
    carry all ten -- so none of these are optional.
    """

    name: str
    stage: str
    tasks_allowed_pf: str
    tasks_required_pf: str
    tasks_allowed_cit: str
    tasks_required_cit: str
    guid: str
    stage_datetime_stamp: str
    crafting_info: CraftingInfo
    verses: List[Verse] = dc_field(default_factory=list)
    transitions: List[StateTransition] = dc_field(default_factory=list)
    count_retellings_tests: str = "0"
    count_testing_question_tests: str = "0"

    def attrs(self) -> "OrderedDictLike":
        return {
            "name": self.name,
            "stage": self.stage,
            "TasksAllowedPf": self.tasks_allowed_pf,
            "TasksRequiredPf": self.tasks_required_pf,
            "TasksAllowedCit": self.tasks_allowed_cit,
            "TasksRequiredCit": self.tasks_required_cit,
            "CountRetellingsTests": self.count_retellings_tests,
            "CountTestingQuestionTests": self.count_testing_question_tests,
            "guid": self.guid,
            "stageDateTimeStamp": self.stage_datetime_stamp,
        }


# Only used for the type hint above; kept loose so this module stays
# dependency-free on older Pythons.
OrderedDictLike = dict


def render_story(story: Story, depth: int = 2) -> List[str]:
    """Render a whole `<story>`.

    Default depth 2 gives the measured indent ladder: story at 4 spaces,
    CraftingInfo and Verses at 6, Verse at 8.

    Child order is CraftingInfo, TransitionHistory, Verses -- 141/141 in
    the reference project, and the schema's sequence is order-significant.
    """
    pad = INDENT * depth
    attrs = " ".join(
        f'{k}="{esc_attr(v)}"' for k, v in story.attrs().items()
    )
    out = [f"{pad}<story {attrs}>"]
    out.extend(render_crafting_info(story.crafting_info, depth + 1))
    if story.transitions:
        out.extend(render_transition_history(story.transitions, depth + 1))
    out.extend(render_verses(story.verses, depth + 1))
    out.append(f"{pad}</story>")
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
