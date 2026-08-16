# FlexText → OneStory Injector

A small Windows desktop tool (Python/Tkinter) that adds a story from a
`.flextext` file (FLEx interlinear XML — also produced by FlexText Editor) into
a SIL OneStory Editor `.onestory` project, **including the word-gloss line**,
which otherwise has to be retyped by hand.

This is a **temporary bridge**. The preferred long-term path is OneStory Editor
importing these files itself
([PR #18](https://github.com/bobeaton/OneStoryEditor/pull/18) and a planned
native `.flextext` importer). This tool exists so teams don't wait on that.

## Using it

1. **Close OneStory Editor.** The injector refuses to run against a file that
   changes under it, but don't race it.
2. **Work on a copy of the project** until you trust the result.
3. `python3 main.py` (or the installed Windows build).
4. Pick the `.flextext`, pick the project, pick the story (a file can hold
   several — one is imported at a time), the target story set, crafter,
   facilitator, and stage.
5. **Answer the biblical / non-biblical question.** There is no default: the
   project stores this per story, teams use both kinds, and the XML attribute
   is negatively named (`NonBiblicalStory="false"` means biblical) so a silent
   default would be dangerously easy to get backwards.
6. Read the preview and the loss report, then Inject.

A timestamped backup is written next to the project before every injection
(`.onestory-injector-backups/`), with a receipt. **Undo last injection**
restores it — and refuses if anything else has touched the file since.

## What it writes, and what it never writes

Writes: one `<story>` with `CraftingInfo` (the biblical flag, crafter,
facilitator), one honest `TransitionHistory` entry
(`WindowsUserName="OseStoryInjector\<hostname>"`), and the verses — an empty
`first="true"` story-notes verse (OneStory's own invariant, 141/141 in the
reference project), then one verse per `.flextext` phrase: Vernacular,
NationalBt (word glosses), InternationalBt (free translation).

Never writes: Anchors, TestQuestions, Retellings, ConsultantNotes, CoachNotes,
morphology, POS tags. A `.flextext` contains none of them and inventing them
would be worse than omitting them.

### The three OneStory realities this design answers

**Adapt It glossing.** OneStory's word-glossing UI is an Adapt It integration:
a knowledge base in a separate Adapt It project folder, taught only when a
user confirms glosses in that form (`AddEntryPair` on OK). Injected stories
arrive with their gloss line already complete, so the KB is neither needed nor
touched — no corruption is possible, the KB just doesn't learn the imported
pairs. (OneStory's own SayMore import behaves identically.)

**Verse anchors.** Never emitted, including for biblical stories. OneStory
itself never writes an empty `<Anchors>` (1,410 real blocks, zero empty; its
serializer asserts non-empty), and verses without anchors are a normal state
even in biblical stories (157 in the reference project). Adding anchors is the
facilitator's next task after import — which is exactly what the default stage
(`ProjFacAddAnchors`) tells OneStory to say.

**Phrase-words.** `.flextext` can treat several space-separated baseline words
as one analytical word with one gloss. OneStory cannot — a single space is its
entire word model, and the Adapt It integration is word-based too. The surface
words are kept verbatim (fusing them would alter the text); the joint gloss
goes under the first word, underscore-joined, and each following word gets a
backward-pointing `<`:

```
ru weni
river_bank <
```

`<` means "belongs to the word before" — deliberately distinct from `***`
("not glossed yet"), so nobody 'fixes' a finished phrase-word, and an exporter
can reconstruct the original single word. Collision-checked: 0 of 15,723 real
gloss tokens even contain a `<`. When the injector detects phrase-words in the
chosen story it shows the count and examples and asks which convention to use
(`<` recommended; `***` holes available for teams that prefer the old rule —
an *unglossed* phrase-word gets `***` on every token either way).

`***` is the hole marker throughout: a translator's mark for "this word has no
gloss", chosen because OneStory literally cannot represent an empty slot
(doubled spaces are discarded by its own tokenizer) and because `***` is what
FLEx shows for a missing analysis. Trailing holes are dropped; medial ones are
load-bearing and kept.

## Safety design

The target file is **never parsed and re-serialized**. It is read once, in
binary; the new story block is spliced in as bytes; and the write is verified
**byte-identical outside the inserted range** before it replaces the original
(temp file + fsync + atomic replace). Real projects contain thousands of
legitimate bare LFs inside note fields — any text-mode round trip would rewrite
them all and light the whole file up as modified in the team's Mercurial sync.

The injector refuses, loudly, rather than guesses: unknown encodings, projects
with no sets or no stories (nothing to copy task configuration from),
self-closed sets, a wrong set name at the moment of injection (duplicate
`SetName`s are addressed by index), files that changed on disk since opening,
and undo after anything else has modified the file.

Byte-exactness of the emitted story is verified against real OneStory output:
987/987 verses and 63/63 CraftingInfo blocks in the reference project
re-render identically through this serializer.

## Tests

```bash
python3 tests/run_tests.py
```

Synthetic fixtures only (placeholder language "Alpha", ISO `qaa`). If a real
project is present in `sample/` (git-ignored, local only), the suite also runs
a full inject → verify → undo cycle on a **copy** of it.

## Building the Windows app

On Windows (see `packaging/`):

```
pip install pyinstaller
pyinstaller packaging/injector.spec
ISCC.exe packaging\installer.iss
```

PyInstaller `--onedir` (plain folder, no self-extraction), then a per-user
Inno Setup installer (no admin rights needed). The build is unsigned;
SmartScreen will warn on first run.

## Licence

AGPL-3.0-or-later (see `LICENSE`). The `<story>` serialization structure is
adapted from OneStory Editor (MIT, © 2021 SIL International) — see
`THIRD-PARTY-NOTICES.md`. Never commit a real `.onestory`, `.flextext`, or
`.eaf` to this repo; `sample/` is git-ignored for local test data.
