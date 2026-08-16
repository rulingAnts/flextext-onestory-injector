"""Build a Story (serializer model) from a parsed ``.flextext`` text.

Where each decision comes from:

* one phrase = one Verse (D3), identical to the viewer's forward mapping;
* Verse 1 is an EMPTY ``first="true"`` verse -- the story-notes slot. All
  141 stories in the reference project have exactly this shape, so a story
  without it would be the only one of its kind in the file;
* NationalBt comes from the word glosses via align.py (holes, phrase rule,
  trailing holes dropped); InternationalBt from the phrase-level gls (D4);
* the stage DEFAULT is derived from what the import actually contains --
  a stage names the NEXT task, so a fully-glossed story's next task is
  adding anchors. The user picks from a closed list; never free text,
  because an unknown stage value throws OneStory's loader out and the
  WHOLE project fails to open;
* Tasks* strings are copied from the project's own stories (harvested by
  the caller); with no stories to copy from the caller must refuse;
* provenance is one StateTransition, FromState == ToState == stage,
  ``WindowsUserName="OseStoryInjector\\<hostname>"`` -- honest about being a
  tool, never a fabricated person (D5).

Anchors (gotcha 2): never emitted. OneStory Editor itself never writes an
empty <Anchors> (1,410 real blocks, zero empty; its serializer asserts
non-empty), and 157 verses in the reference project's biblical stories
have no Anchors at all. Anchors are the facilitator's NEXT TASK after a
glossed import -- which the derived stage says explicitly.
"""

from __future__ import annotations

import socket
import time
import uuid
from typing import List, Optional

from .align import HOLE
from .flextext_reader import Text
from .ose_serializer import (
    CraftingInfo,
    LANG_INTERNATIONAL_BT,
    LANG_NATIONAL_BT,
    LANG_VERNACULAR,
    StateTransition,
    Story,
    StoryLine,
    Verse,
)

INJECTOR_NAME = "OseStoryInjector"

# Stage ladder (plan §3.4): the stage names the next task.
STAGE_FULLY_GLOSSED = "ProjFacAddAnchors"          # vern + glosses + free
STAGE_NEEDS_FREE = "ProjFacTypeInternationalBT"    # vern + glosses
STAGE_NEEDS_GLOSS = "ProjFacTypeNationalBT"        # vern only
STAGE_NEEDS_VERN = "ProjFacTypeVernacular"         # nothing usable


def new_guid(existing: set) -> str:
    """Lowercase uuid4, guaranteed absent from the project."""
    while True:
        g = str(uuid.uuid4()).lower()
        if g not in existing:
            existing.add(g)
            return g


def now_z() -> str:
    """OSE's timestamp shape, measured: 2021-08-30T07:06:36Z."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def derive_stage(text: Text) -> str:
    has_vern = any(p.vernacular_line() for p in text.phrases)
    has_gloss = any(p.gloss_line() for p in text.phrases)
    has_free = any(p.free for p in text.phrases)
    if has_vern and has_gloss and has_free:
        return STAGE_FULLY_GLOSSED
    if has_vern and has_gloss:
        return STAGE_NEEDS_FREE
    if has_vern:
        return STAGE_NEEDS_GLOSS
    return STAGE_NEEDS_VERN


def build_story(
    text: Text,
    *,
    story_name: str,
    non_biblical: bool,
    crafter_key: str,
    facilitator_key: str,
    stage: str,
    tasks: dict,
    existing_guids: set,
    hostname: Optional[str] = None,
    phrase_mode: str = "marker",
) -> Story:
    """Assemble the Story. All arguments are explicit: the UI collects them,
    and nothing here invents a value that OneStory treats as configuration.
    """
    stamp = now_z()
    host = hostname or socket.gethostname()

    verses: List[Verse] = [
        # the story-notes slot; OSE's own invariant, 141/141
        Verse(guid=new_guid(existing_guids), first=True)
    ]
    for phrase in text.phrases:
        lines: List[StoryLine] = []
        vern = phrase.vernacular_line()
        if vern:
            lines.append(StoryLine(LANG_VERNACULAR, vern))
        gloss = phrase.gloss_line(phrase_mode)
        if gloss:
            lines.append(StoryLine(LANG_NATIONAL_BT, gloss))
        if phrase.free:
            lines.append(StoryLine(LANG_INTERNATIONAL_BT, phrase.free))
        verses.append(Verse(guid=new_guid(existing_guids), lines=lines))

    return Story(
        name=story_name,
        stage=stage,
        tasks_allowed_pf=tasks["TasksAllowedPf"],
        tasks_required_pf=tasks["TasksRequiredPf"],
        tasks_allowed_cit=tasks["TasksAllowedCit"],
        tasks_required_cit=tasks["TasksRequiredCit"],
        guid=new_guid(existing_guids),
        stage_datetime_stamp=stamp,
        crafting_info=CraftingInfo(
            non_biblical=non_biblical,
            story_crafter=crafter_key,
            project_facilitator=facilitator_key,
        ),
        transitions=[
            StateTransition(
                logged_in_member_id=facilitator_key,
                from_state=stage,
                to_state=stage,
                transition_datetime=stamp,
                windows_user_name=f"{INJECTOR_NAME}\\{host}",
            )
        ],
        verses=verses,
    )


def loss_report(text: Text, phrase_mode: str = "marker") -> List[str]:
    """What the .flextext held that OneStory cannot -- shown, never silent."""
    notes: List[str] = []
    hole_count = 0
    phrase_words = 0
    for p in text.phrases:
        g = p.gloss_line(phrase_mode)
        hole_count += g.split().count(HOLE) if g else 0
        phrase_words += sum(1 for w in p.words if not w.is_punct and " " in w.text)
    if hole_count:
        notes.append(
            f"{hole_count} word(s) had no gloss; written as '{HOLE}' so the "
            "remaining glosses stay under the right words."
        )
    if phrase_words:
        if phrase_mode == "marker":
            notes.append(
                f"{phrase_words} phrase-word(s) (one analysis spanning several "
                "words) carry the underscore-joined gloss on their first word "
                "and a '<' on each following word, meaning 'belongs to the "
                "word before'. OneStory has no phrase-word concept."
            )
        else:
            notes.append(
                f"{phrase_words} phrase-word(s) were glossed on their first "
                f"word with '{HOLE}' on the rest -- indistinguishable from "
                "unglossed words, and not reconstructible on export."
            )
    notes.append(
        "Not carried over (OneStory has no equivalent): morpheme breakdowns, "
        "part-of-speech tags, literal translations, notes, and audio "
        "segment timing."
    )
    return notes
