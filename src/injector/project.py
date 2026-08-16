"""Byte-level operations on a ``.onestory`` project file.

THE PRIME DIRECTIVE: the target file is NEVER round-tripped through a
parser or a text-mode read. Real projects contain thousands of legitimate
bare LFs inside note fields (8,946 in the reference project) alongside
CRLF structure; any text-mode I/O or re-serialization would rewrite them
all and present the whole file as modified to the team's Mercurial sync.
So:

* the file is read ONCE, in binary;
* everything we learn about it (sets, members, stages, offsets) is derived
  from that byte string;
* injection is ``head + fragment + tail`` on bytes;
* the guaranteed invariant, asserted after every write, is that the result
  is byte-identical to the original outside the inserted range.

Reading string values OUT of those bytes for display (set names, member
names) decodes a copy; the original bytes stay authoritative.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


class ProjectError(Exception):
    """Every refusal is loud and specific. Guessing corrupts projects."""


def _unescape(value: str) -> str:
    return (
        value.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&amp;", "&")
    )


# ---------------------------------------------------------------------------
# Comment-aware byte scanning
# ---------------------------------------------------------------------------
#
# A comment may legally contain "</stories>" or a fake "<stories ...>", so
# every structural scan must see comments as opaque. XML forbids nested
# comments, which keeps this a flat interval list.

_COMMENT = re.compile(rb"<!--.*?-->", re.S)


def _comment_spans(data: bytes) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in _COMMENT.finditer(data)]


def _outside(pos: int, spans: List[Tuple[int, int]]) -> bool:
    return not any(a <= pos < b for a, b in spans)


@dataclass
class StorySet:
    """One `<stories SetName="...">` element, located by byte offsets."""

    index: int                 # position among sets -- the authoritative key
    set_name: str              # decoded, unescaped, for display + assertion
    open_start: int            # offset of '<' of the open tag
    open_end: int              # offset just past '>' of the open tag
    close_start: Optional[int] # offset of '<' of '</stories>'; None = self-closed
    self_closed: bool
    story_names: List[str] = field(default_factory=list)


@dataclass
class Member:
    name: str
    member_type: str
    member_key: str

    def has_role(self, role: str) -> bool:
        return role in [r.strip() for r in self.member_type.split(",")]


class OneStoryProject:
    """A loaded project: original bytes plus what was learned from them."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        with open(self.path, "rb") as f:      # binary, always
            self.data = f.read()
        self.sha256 = hashlib.sha256(self.data).hexdigest()
        try:
            self.text = self.data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ProjectError(
                f"Not UTF-8 at byte {e.start}: refusing to touch a file whose "
                "encoding I cannot prove. Every OneStory file measured is UTF-8."
            )
        # len(text) == len(data) only for pure ASCII; all offsets kept in
        # BYTES, so any regex over self.text converts positions via encode.
        self._comment_spans = _comment_spans(self.data)
        self.sets = self._find_sets()
        self.members = self._find_members()

    # -- character-offset -> byte-offset ------------------------------------
    def _b(self, char_pos: int) -> int:
        return len(self.text[:char_pos].encode("utf-8"))

    # -- discovery -----------------------------------------------------------
    def _find_sets(self) -> List[StorySet]:
        sets: List[StorySet] = []
        for m in re.finditer(r"<stories\b([^>]*?)(/?)>", self.text):
            if not _outside(self._b(m.start()), self._comment_spans):
                continue
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            name = _unescape(attrs.get("SetName", ""))
            self_closed = m.group(2) == "/"
            close_start = None
            if not self_closed:
                c = self.text.find("</stories>", m.end())
                while c != -1 and not _outside(self._b(c), self._comment_spans):
                    c = self.text.find("</stories>", c + 1)
                if c == -1:
                    raise ProjectError(
                        f'Set "{name}": no closing </stories> outside comments. '
                        "The file may be truncated; refusing."
                    )
                close_start = c
            body = "" if self_closed else self.text[m.end():close_start]
            names = [
                _unescape(n)
                for n in re.findall(r'<story\s[^>]*?name="([^"]*)"', body)
            ]
            sets.append(
                StorySet(
                    index=len(sets),
                    set_name=name,
                    open_start=m.start(),
                    open_end=m.end(),
                    close_start=close_start,
                    self_closed=self_closed,
                    story_names=names,
                )
            )
        if not sets:
            raise ProjectError(
                "No <stories> sets found. A valid project has at least one; "
                "refusing to guess where a story belongs."
            )
        return sets

    def _find_members(self) -> List[Member]:
        out = []
        for m in re.finditer(r"<Member\s([^>]*?)/?>", self.text):
            if not _outside(self._b(m.start()), self._comment_spans):
                continue
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            if "memberKey" in attrs:
                out.append(
                    Member(
                        name=_unescape(attrs.get("name", "")),
                        member_type=_unescape(attrs.get("memberType", "")),
                        member_key=attrs["memberKey"],
                    )
                )
        return out

    # -- harvesting for defaults ---------------------------------------------
    def stages_in_use(self) -> List[str]:
        from collections import Counter
        c = Counter(re.findall(r'<story\s[^>]*?stage="([^"]*)"', self.text))
        return [s for s, _ in c.most_common()]

    def harvest_tasks(self) -> Optional[dict]:
        """Most-common Tasks* attribute values across existing stories.

        These strings are project configuration (which UI panes are open to
        the facilitator); a wrong value silently HIDES lines in OSE. Copying
        the project's own dominant values is the only safe source. Returns
        None when the project has no stories at all -- the caller must then
        refuse rather than invent values (fail closed, plan §3.4).
        """
        from collections import Counter
        found: dict = {}
        for attr in ("TasksAllowedPf", "TasksRequiredPf",
                     "TasksAllowedCit", "TasksRequiredCit"):
            vals = re.findall(rf'{attr}="([^"]*)"', self.text)
            if not vals:
                return None
            found[attr] = Counter(vals).most_common(1)[0][0]
        return found

    def guids(self) -> set:
        return set(re.findall(r'guid="([^"]*)"', self.text))

    # -- insertion -------------------------------------------------------------
    def insertion_offset(self, set_index: int, expect_name: str) -> int:
        """Byte offset at which a new story block is spliced in.

        The set is addressed by INDEX and the name is re-asserted, because
        duplicate SetNames resolve a name lookup to the wrong set silently.
        The offset is the start of the line holding ``</stories>``, so the
        block lands after the last existing story.
        """
        try:
            s = self.sets[set_index]
        except IndexError:
            raise ProjectError(f"No set at index {set_index}.")
        if s.set_name != expect_name:
            raise ProjectError(
                f'Set {set_index} is named "{s.set_name}", not "{expect_name}". '
                "The file changed since it was inspected; re-open it."
            )
        if s.self_closed:
            raise ProjectError(
                f'Set "{s.set_name}" is self-closed (<stories ... />). '
                "Expanding it is possible but untested against OSE; refusing "
                "for now -- add a story to this set in OneStory Editor once, "
                "then retry."
            )
        line_start = self.text.rfind("\n", 0, s.close_start) + 1
        return self._b(line_start)

    def splice(self, offset: int, block: bytes) -> bytes:
        """head + block + tail. The block must end with CRLF."""
        if not block.endswith(b"\r\n"):
            raise ProjectError("Internal: story block must end with CRLF.")
        return self.data[:offset] + block + self.data[offset:]


# ---------------------------------------------------------------------------
# Write path: backup, verify, receipt, undo
# ---------------------------------------------------------------------------

def verify_splice(original: bytes, result: bytes, offset: int, block: bytes) -> None:
    """The invariant that catches every corruption mode we have hit so far
    (text-mode reads, phantom normalisation, off-by-BOM offsets)."""
    if result[:offset] != original[:offset]:
        raise ProjectError("VERIFY FAILED: bytes before the insertion changed.")
    if result[offset:offset + len(block)] != block:
        raise ProjectError("VERIFY FAILED: inserted block differs.")
    if result[offset + len(block):] != original[offset:]:
        raise ProjectError("VERIFY FAILED: bytes after the insertion changed.")
    # structural sanity on a decoded COPY (the file itself is already written
    # from `result`, not from this parse)
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(result.decode("utf-8"))
    except Exception as e:
        raise ProjectError(f"VERIFY FAILED: result is not well-formed XML: {e}")


def backup_path_for(project_path: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(project_path)
    bdir = os.path.join(os.path.dirname(project_path), ".onestory-injector-backups")
    os.makedirs(bdir, exist_ok=True)
    return os.path.join(bdir, f"{base}.{stamp}.bak")


def inject(project: OneStoryProject, set_index: int, expect_name: str,
           block: bytes) -> dict:
    """Backup -> splice -> verify -> atomic replace -> receipt.

    Refuses if the file changed on disk since it was loaded (OSE running,
    or a sync landing) -- the offsets would be stale.
    """
    with open(project.path, "rb") as f:
        now = f.read()
    if hashlib.sha256(now).hexdigest() != project.sha256:
        raise ProjectError(
            "The project file changed on disk since it was opened "
            "(OneStory Editor running, or a send/receive landed). "
            "Close OSE, then re-open the file here."
        )

    offset = project.insertion_offset(set_index, expect_name)
    result = project.splice(offset, block)
    verify_splice(project.data, result, offset, block)

    bak = backup_path_for(project.path)
    shutil.copy2(project.path, bak)

    tmp = project.path + ".injector-tmp"
    with open(tmp, "wb") as f:
        f.write(result)
        f.flush()
        os.fsync(f.fileno())
    with open(tmp, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != hashlib.sha256(result).hexdigest():
            os.unlink(tmp)
            raise ProjectError("VERIFY FAILED: temp file readback mismatch.")
    os.replace(tmp, project.path)

    receipt = {
        "project": project.path,
        "backup": bak,
        "sha256_before": project.sha256,
        "sha256_after": hashlib.sha256(result).hexdigest(),
        "offset": offset,
        "block_bytes": len(block),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(bak + ".receipt.json", "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
    return receipt


def undo(receipt: dict) -> None:
    """Restore the backup -- but ONLY if the file is still exactly the
    post-injection state. If anything (OSE, a sync, a person) touched it
    since, restoring would destroy their work; refuse and say why."""
    path = receipt["project"]
    with open(path, "rb") as f:
        current = hashlib.sha256(f.read()).hexdigest()
    if current != receipt["sha256_after"]:
        raise ProjectError(
            "REFUSING to undo: the project has been modified since the "
            "injection (perhaps by OneStory Editor or a send/receive). "
            f"Restore manually from the backup if you are sure:\n  {receipt['backup']}"
        )
    shutil.copy2(receipt["backup"], path)
