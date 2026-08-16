#!/usr/bin/env python3
"""The injector's test suite. Plain python, no framework:

    python3 tests/run_tests.py

Every fixture is synthetic -- placeholder language "Alpha", ISO qaa. No real
vernacular text, story titles or member data appear anywhere in this repo.

The suite ends with a real-data pass (byte-exact serializer comparison and
a full inject/undo cycle on a COPY) that runs only when sample/ contains a
project; it is skipped, loudly, when absent.
"""

import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from injector import align
from injector.flextext_reader import read_flextext
from injector.ose_serializer import (
    CRLF, CraftingInfo, StateTransition, Story, StoryLine, Verse,
    render_story, render_verse, to_bytes,
)
from injector.project import (
    OneStoryProject, ProjectError, inject, undo, verify_splice,
    suggest_set_index,
)
from injector.story_builder import build_story, derive_stage, loss_report
from injector.flextext_reader import Text, Phrase, WordToken

fail = 0


def ok(cond, what):
    global fail
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        fail += 1


def eq(actual, expected, what):
    global fail
    if actual == expected:
        print("  ok   " + what)
    else:
        print(f"  FAIL {what}\n         expected {expected!r}\n         actual   {actual!r}")
        fail += 1


# ---------------------------------------------------------------- align --
print("\n--- align: holes, phrase rule, trailing holes ---")
eq(align.underscore_join("big house"), "big_house", "gloss spaces -> underscore")
eq(align.gloss_tokens_for_word("ka", "one"), ["one"], "simple word")
eq(align.gloss_tokens_for_word("ka", None), ["***"], "unglossed word -> hole")
eq(align.gloss_tokens_for_word("ka mo", "big house"),
   ["big_house", "<"], "phrase-word (marker mode): '<' points backward")
eq(align.gloss_tokens_for_word("ka mo", "big house", "holes"),
   ["big_house", "***"], "phrase-word (holes mode): plan-D2 behaviour")
eq(align.gloss_tokens_for_word("ka mo si", None),
   ["***", "***", "***"], "UNGLOSSED phrase-word: holes in every mode")
eq(align.build_gloss_line([("ka", "g1"), ("mo", None), ("si", "g3")]),
   "g1 *** g3", "medial hole kept")
eq(align.build_gloss_line([("ka", "g1"), ("mo", None), ("si", None)]),
   "g1", "trailing holes dropped (D1)")
eq(align.build_gloss_line([("ka", None), ("mo", None)]),
   "", "all holes -> no gloss line at all")
eq(align.build_gloss_line([("ka mo", "big house"), ("si", "g")]),
   "big_house < g", "phrase-word then normal word (marker)")
eq(align.build_gloss_line([("si", "g"), ("ka mo", "big house")]),
   "g big_house <", "TRAILING marker never stripped -- it carries the phrase")
eq(align.build_gloss_line([("ka mo", "big house"), ("si", "g")], "holes"),
   "big_house *** g", "holes mode preserved for teams that want it")
try:
    align.build_gloss_line([("ka", "g")], "bogus")
    ok(False, "unknown phrase_mode must raise")
except ValueError:
    ok(True, "unknown phrase_mode refused")

# -------------------------------------------------------------- reader --
print("\n--- flextext reader ---")
FLEXTEXT = """<?xml version="1.0" encoding="utf-8"?>
<document version="2">
 <interlinear-text guid="t1">
  <item type="title" lang="qaa">Alpha Story One</item>
  <paragraphs>
   <paragraph><phrases>
    <phrase>
     <item type="txt" lang="qaa">Ka mo si.</item>
     <words>
      <word><item type="txt" lang="qaa">Ka</item><item type="gls" lang="en">one</item></word>
      <word><item type="txt" lang="qaa">mo</item><item type="gls" lang="en"></item></word>
      <word><item type="txt" lang="qaa">si</item><item type="gls" lang="en">three</item></word>
      <word><item type="punct" lang="qaa">.</item></word>
     </words>
     <item type="gls" lang="en">The first sentence.</item>
    </phrase>
    <phrase>
     <words>
      <word><item type="punct" lang="qaa">“</item></word>
      <word><item type="txt" lang="qaa">ru weni</item><item type="gls" lang="en">river bank</item></word>
      <word><item type="txt" lang="qaa">ta</item></word>
      <word><item type="punct" lang="qaa">”</item></word>
     </words>
    </phrase>
   </phrases></paragraph>
  </paragraphs>
 </interlinear-text>
</document>
"""
with tempfile.NamedTemporaryFile("w", suffix=".flextext", delete=False,
                                 encoding="utf-8") as tf:
    tf.write(FLEXTEXT)
    ftpath = tf.name
ft = read_flextext(ftpath)
os.unlink(ftpath)
eq(len(ft.texts), 1, "one text")
t = ft.texts[0]
eq(t.title, "Alpha Story One", "title")
eq(len(t.phrases), 2, "two phrases")
eq(t.phrases[0].vernacular_line(), "Ka mo si.", "punct attached, no space")
eq(t.phrases[0].gloss_line(), "one *** three", "empty gls is a hole; punct has no slot")
eq(t.phrases[0].free, "The first sentence.", "free translation")
eq(t.phrases[1].vernacular_line(), "“ru weni ta”",
   "leading punct glued to next word; trailing to previous")
eq(t.phrases[1].gloss_line(), "river_bank <",
   "phrase-word: marker on continuation; trailing HOLE dropped after it")
eq(t.phrases[1].gloss_line("holes"), "river_bank",
   "holes mode: continuation merges into dropped trailing holes")
eq(t.phrase_word_count(), 1, "phrase-word detection for the UI")
eq(t.phrase_word_examples(), [("ru weni", "river bank")],
   "phrase-word example for the UI dialog")

# ---------------------------------------------------------- serializer --
print("\n--- serializer: synthetic story shape ---")
story = build_story(
    t, story_name="Alpha Story One", non_biblical=True,
    crafter_key="mem-00000000-0000-0000-0000-000000000001",
    facilitator_key="mem-00000000-0000-0000-0000-000000000002",
    stage=derive_stage(t),
    tasks={"TasksAllowedPf": "A", "TasksRequiredPf": "B",
           "TasksAllowedCit": "C", "TasksRequiredCit": "D"},
    existing_guids=set(), hostname="testhost",
)
eq(derive_stage(t), "ProjFacAddAnchors", "fully-glossed -> AddAnchors stage")
lines = render_story(story)
block = CRLF.join(lines) + CRLF
ok(block.startswith('    <story name="Alpha Story One"'), "story indent 4, name first")
ok('NonBiblicalStory="true"' in block, "non-biblical flag honoured")
ok('first="true" />' in block, "empty first verse present, self-closed")
ok("<Anchors" not in block, "no Anchors ever emitted (gotcha 2)")
ok('WindowsUserName="OseStoryInjector\\testhost"' in block, "honest provenance")
ok("\n" not in block.replace("\r\n", ""), "no bare LFs in emitted block")
ok("&lt;" in block and "river_bank <" not in block,
   "phrase marker is escaped to &lt; in the file, never a bare <")
attr_order = re.search(r"<story (.*?)>", block).group(1)
eq(re.findall(r'(\w+)="', attr_order),
   ["name", "stage", "TasksAllowedPf", "TasksRequiredPf", "TasksAllowedCit",
    "TasksRequiredCit", "CountRetellingsTests", "CountTestingQuestionTests",
    "guid", "stageDateTimeStamp"],
   "story attribute order matches the measured OSE order")
ok(any("no gloss" in n for n in loss_report(t)), "loss report mentions holes")
ok(any("'<'" in n for n in loss_report(t, "marker")),
   "loss report (marker) explains the backward pointer")
ok(any("indistinguishable" in n for n in loss_report(t, "holes")),
   "loss report (holes) warns about ambiguity")

# ------------------------------------------------------------- project --
print("\n--- project: set discovery hazards ---")

def proj(body: str) -> OneStoryProject:
    with tempfile.NamedTemporaryFile("wb", suffix=".onestory", delete=False) as f:
        f.write(body.encode("utf-8"))
        p = f.name
    pr = OneStoryProject(p)
    os.unlink(p)
    return pr

BASE = (
    '<?xml version="1.0"?>\r\n<StoryProject ProjectName="Alpha">\r\n'
    '  <Members>\r\n'
    '    <Member name="Alpha Person" memberType="Crafter, ProjectFacilitator" memberKey="mem-1" />\r\n'
    '  </Members>\r\n'
    '{sets}'
    '</StoryProject>\r\n'
)
ONESET = BASE.format(sets=(
    '  <stories SetName="Stories">\r\n'
    '    <story name="Old One" stage="ProjFacTypeVernacular" TasksAllowedPf="A" '
    'TasksRequiredPf="B" TasksAllowedCit="C" TasksRequiredCit="D" '
    'CountRetellingsTests="0" CountTestingQuestionTests="0" guid="g-1" '
    'stageDateTimeStamp="2021-01-01T00:00:00Z">\r\n'
    '      <CraftingInfo NonBiblicalStory="false">\r\n'
    '      </CraftingInfo>\r\n      <Verses>\r\n'
    '        <Verse guid="g-2" first="true" />\r\n'
    '      </Verses>\r\n    </story>\r\n'
    '  </stories>\r\n'
))

p = proj(ONESET)
eq(len(p.sets), 1, "one set found")
eq(p.sets[0].set_name, "Stories", "set name")
eq(p.sets[0].story_names, ["Old One"], "existing story listed")
eq(len(p.members), 1, "member found")
ok(p.members[0].has_role("ProjectFacilitator"), "role parsing")
eq(p.harvest_tasks(), {"TasksAllowedPf": "A", "TasksRequiredPf": "B",
                       "TasksAllowedCit": "C", "TasksRequiredCit": "D"},
   "tasks harvested from sibling story")

# hazard: comment containing </stories>
TRICKY = BASE.format(sets=(
    '  <!-- do not be fooled: </stories> <stories SetName="Fake"> -->\r\n'
    '  <stories SetName="A &amp; B">\r\n  </stories>\r\n'
))
p2 = proj(TRICKY)
eq(len(p2.sets), 1, "comment with fake tags ignored")
eq(p2.sets[0].set_name, "A & B", "SetName entity unescaped")
off = p2.insertion_offset(0, "A & B")
ok(off > 0, "insertion offset found in empty (but open) set")
try:
    p2.insertion_offset(0, "Wrong Name")
    ok(False, "wrong expected name must raise")
except ProjectError:
    ok(True, "wrong expected name refused")

# hazard: self-closed set
SELF = BASE.format(sets='  <stories SetName="Empty" />\r\n')
p3 = proj(SELF)
try:
    p3.insertion_offset(0, "Empty")
    ok(False, "self-closed set must refuse")
except ProjectError:
    ok(True, "self-closed set refused, not guessed")

# hazard: duplicate SetName -> index addressing still deterministic
DUP = BASE.format(sets=(
    '  <stories SetName="Same">\r\n  </stories>\r\n'
    '  <stories SetName="Same">\r\n  </stories>\r\n'
))
p4 = proj(DUP)
eq(len(p4.sets), 2, "duplicate names: both sets found")
ok(p4.insertion_offset(1, "Same") > p4.insertion_offset(0, "Same"),
   "index addressing distinguishes duplicates")

# hazard: no sets at all
try:
    proj('<?xml version="1.0"?>\r\n<StoryProject>\r\n</StoryProject>\r\n')
    ok(False, "zero-set project must refuse")
except ProjectError:
    ok(True, "zero-set project refused")

# ------------------------------------------ set character / suggestion --
print("\n--- biblical/non-biblical: set character drives the suggestion ---")
CHAR = BASE.format(sets=(
    '  <stories SetName="Stories">\r\n'
    '    <story name="B1" stage="s" TasksAllowedPf="A" TasksRequiredPf="B" '
    'TasksAllowedCit="C" TasksRequiredCit="D" CountRetellingsTests="0" '
    'CountTestingQuestionTests="0" guid="g-b1" stageDateTimeStamp="2021-01-01T00:00:00Z">\r\n'
    '      <CraftingInfo NonBiblicalStory="false">\r\n      </CraftingInfo>\r\n'
    '      <Verses>\r\n        <Verse guid="g-b2" first="true" />\r\n      </Verses>\r\n'
    '    </story>\r\n  </stories>\r\n'
    '  <stories SetName="Non-Biblical Stories">\r\n'
    '    <story name="N1" stage="s" TasksAllowedPf="A" TasksRequiredPf="B" '
    'TasksAllowedCit="C" TasksRequiredCit="D" CountRetellingsTests="0" '
    'CountTestingQuestionTests="0" guid="g-n1" stageDateTimeStamp="2021-01-01T00:00:00Z">\r\n'
    '      <CraftingInfo NonBiblicalStory="true">\r\n      </CraftingInfo>\r\n'
    '      <Verses>\r\n        <Verse guid="g-n2" first="true" />\r\n      </Verses>\r\n'
    '    </story>\r\n  </stories>\r\n'
))
pc = proj(CHAR)
eq(pc.sets[0].character(), False, "all-biblical set -> character False")
eq(pc.sets[1].character(), True, "all-non-biblical set -> character True")
eq(suggest_set_index(pc.sets, False), 0, "biblical story -> Stories set")
eq(suggest_set_index(pc.sets, True), 1, "non-biblical story -> Non-Biblical set")
eq(p.sets[0].character(), False, "single-set project: character from its stories")
eq(suggest_set_index(p.sets, True), None,
   "no matching set exists -> None (UI warns instead of guessing)")

# ------------------------------------------------ inject / verify / undo --
print("\n--- inject -> verify -> undo, on a synthetic file ---")
tmpdir = tempfile.mkdtemp()
ppath = os.path.join(tmpdir, "alpha.onestory")
with open(ppath, "wb") as f:
    f.write(ONESET.encode("utf-8"))

pr = OneStoryProject(ppath)
block_bytes = to_bytes(render_story(story))
receipt = inject(pr, 0, "Stories", block_bytes)
with open(ppath, "rb") as f:
    after = f.read()
orig = ONESET.encode("utf-8")
ok(len(after) == len(orig) + len(block_bytes), "size delta == block size")
o = receipt["offset"]
ok(after[:o] == orig[:o] and after[o + len(block_bytes):] == orig[o:],
   "byte-identical outside the inserted range")
pr2 = OneStoryProject(ppath)
eq(pr2.sets[0].story_names, ["Old One", "Alpha Story One"],
   "new story visible on re-parse, after the old one")

# stale-handle refusal
try:
    inject(pr, 0, "Stories", block_bytes)
    ok(False, "stale in-memory project must refuse a second inject")
except ProjectError:
    ok(True, "stale project handle refused (file changed on disk)")

# undo
undo(receipt)
with open(ppath, "rb") as f:
    ok(f.read() == orig, "undo restores byte-identical original")
# undo again -> file no longer matches sha256_after -> refuse
try:
    undo(receipt)
    ok(False, "second undo must refuse")
except ProjectError:
    ok(True, "undo refused once the file no longer matches the receipt")

# ---------------------------------------------------- real-data (optional) --
print("\n--- real-data pass (skipped unless sample/ has a project) ---")
sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample")
reals = [f for f in os.listdir(sample_dir) if f.endswith(".onestory")] \
    if os.path.isdir(sample_dir) else []
if not reals:
    print("  SKIP: no .onestory in sample/ (expected on machines without one)")
else:
    real = os.path.join(sample_dir, reals[0])
    rp = OneStoryProject(real)
    print(f"  loaded: {len(rp.data):,} bytes, {len(rp.sets)} sets, "
          f"{len(rp.members)} members")
    ok(len(rp.sets) >= 1, "real project: sets found")
    ok(rp.harvest_tasks() is not None, "real project: tasks harvested")
    # full inject/undo cycle ON A COPY
    import shutil as _sh
    cpath = os.path.join(tmpdir, "copy.onestory")
    _sh.copy2(real, cpath)
    rc = OneStoryProject(cpath)
    tasks = rc.harvest_tasks()
    st = build_story(
        t, story_name="Injector Self-Test qaa", non_biblical=True,
        crafter_key=rc.members[0].member_key,
        facilitator_key=rc.members[0].member_key,
        stage=derive_stage(t), tasks=tasks,
        existing_guids=rc.guids(), hostname="testhost",
    )
    blk = to_bytes(render_story(st))
    r = inject(rc, 0, rc.sets[0].set_name, blk)
    with open(cpath, "rb") as f:
        aft = f.read()
    oo = r["offset"]
    ok(aft[:oo] == rc.data[:oo] and aft[oo + len(blk):] == rc.data[oo:],
       "REAL project: byte-identical outside inserted range")
    rr = OneStoryProject(cpath)
    ok("Injector Self-Test qaa" in rr.sets[0].story_names,
       "REAL project: story present on re-parse")
    undo(r)
    with open(cpath, "rb") as f:
        ok(f.read() == rc.data, "REAL project: undo byte-identical")

print(f"\n{fail} FAILURE(S)\n" if fail else "\nall passed\n")
sys.exit(1 if fail else 0)
