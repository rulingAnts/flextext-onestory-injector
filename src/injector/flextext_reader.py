"""Read a ``.flextext`` (FLEx interlinear XML export).

Parsing the INPUT with a real XML parser is fine -- the byte-preservation
rules apply to the ``.onestory`` target we splice into, never to the
``.flextext`` we only read.

Structure walked::

    <document>
      <interlinear-text>              (a file may hold several; user picks ONE)
        <item type="title" lang=".."> (story name candidate)
        <paragraphs><paragraph><phrases><phrase>
          <item type="txt">           phrase-level baseline (not trusted for
                                      tokenisation -- see below)
          <item type="gls">           free translation -> InternationalBt
          <words><word>
            <item type="txt">         surface form(s); internal space = a
                                      phrase-word (one analysis, several
                                      surface tokens)
            <item type="gls">         word gloss -> NationalBt token
            <item type="punct">       punctuation "word"

The Vernacular line is ALWAYS reconstructed from the word items, never
taken from the phrase-level txt: the gloss line must be token-parallel to
the vernacular, and only reconstruction makes that true by construction.
Punctuation words are attached to the preceding surface token without a
space (or to the following one at phrase start), matching how the text
was typed, and consume no gloss slot.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional

from .align import build_gloss_line, collapse_whitespace


@dataclass
class WordToken:
    """One ``<word>`` as it affects the two aligned lines."""

    text: str                 # surface text (may contain internal spaces)
    gloss: Optional[str]      # word-level gls, None when absent/empty
    is_punct: bool = False


@dataclass
class Phrase:
    words: List[WordToken] = field(default_factory=list)
    free: str = ""            # phrase-level gls (free translation)

    def vernacular_line(self) -> str:
        """Reconstruct the baseline with punctuation attached."""
        parts: List[str] = []
        pending_leading: str = ""
        for w in self.words:
            if w.is_punct:
                if parts:
                    parts[-1] += w.text
                else:
                    pending_leading += w.text
            else:
                token = pending_leading + w.text
                pending_leading = ""
                parts.append(token)
        if pending_leading:
            # punctuation-only phrase; keep it rather than lose text
            parts.append(pending_leading)
        return collapse_whitespace(" ".join(parts))

    def gloss_line(self, phrase_mode: str = "marker") -> str:
        """The NationalBt line, token-parallel to vernacular_line().

        Punctuation is merged into its neighbour's surface token above, so
        for parity the merged word's token count must be computed the same
        way. Leading punctuation glues onto the FOLLOWING word's first
        surface token and changes nothing about token counts; trailing
        punctuation likewise. Hence pairs are built from non-punct words
        only, using each word's own surface text.
        """
        pairs = [(w.text, w.gloss) for w in self.words if not w.is_punct]
        return build_gloss_line(pairs, phrase_mode)

    def phrase_words(self):
        """Words spanning several surface tokens (internal space)."""
        return [w for w in self.words if not w.is_punct and " " in w.text]


@dataclass
class Text:
    title: str
    phrases: List[Phrase] = field(default_factory=list)

    def phrase_word_count(self) -> int:
        return sum(len(p.phrase_words()) for p in self.phrases)

    def phrase_word_examples(self, limit: int = 3):
        out = []
        for p in self.phrases:
            for w in p.phrase_words():
                out.append((w.text, w.gloss or ""))
                if len(out) >= limit:
                    return out
        return out


@dataclass
class FlexTextFile:
    texts: List[Text] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _item_text(el: ET.Element, item_type: str) -> Optional[str]:
    for item in el.findall("item"):
        if item.get("type") == item_type:
            return item.text or ""
    return None


def read_flextext(path: str) -> FlexTextFile:
    """Parse the file. Raises ET.ParseError on malformed XML."""
    tree = ET.parse(path)
    root = tree.getroot()
    out = FlexTextFile()

    for it_index, itext in enumerate(root.iter("interlinear-text")):
        title = _item_text(itext, "title") or f"Untitled {it_index + 1}"
        text = Text(title=collapse_whitespace(title))

        for phrase_el in itext.iter("phrase"):
            phrase = Phrase()

            # free translation: phrase-level gls. When both a pre-words and
            # post-words gls exist, the LAST one wins (matches the sibling
            # reader's documented behaviour).
            for item in phrase_el.findall("item"):
                if item.get("type") == "gls":
                    phrase.free = collapse_whitespace(item.text or "")

            words_el = phrase_el.find("words")
            if words_el is not None:
                for word_el in words_el.findall("word"):
                    punct = _item_text(word_el, "punct")
                    if punct is not None:
                        if punct != "":
                            phrase.words.append(
                                WordToken(text=punct, gloss=None, is_punct=True)
                            )
                        continue
                    txt = _item_text(word_el, "txt")
                    if txt is None or txt.strip() == "":
                        # padding word (forward exporter emits empty txt for
                        # unpaired glosses); its gls, if any, has no surface
                        # anchor -- note and skip.
                        g = _item_text(word_el, "gls")
                        if g and g.strip():
                            out.warnings.append(
                                f"'{text.title}': a gloss with no baseline word "
                                f"was skipped (phrase {len(text.phrases) + 1})"
                            )
                        continue
                    gls = _item_text(word_el, "gls")
                    phrase.words.append(
                        WordToken(
                            text=collapse_whitespace(txt),
                            gloss=(gls if gls and gls.strip() else None),
                        )
                    )

            if phrase.vernacular_line():
                text.phrases.append(phrase)
            elif phrase.free:
                # A free translation with no baseline at all -- keep it as a
                # verse with only an InternationalBt line rather than lose it.
                text.phrases.append(phrase)

        if text.phrases:
            out.texts.append(text)
        else:
            out.warnings.append(f"'{text.title}': no usable phrases; text skipped")

    return out
