"""Tkinter UI for the injector.

Deliberately plain: file pickers, one dropdown per decision, a preview,
and an Inject button that is disabled until every required answer exists.

UI rules that are policy, not taste:

* Biblical / non-biblical has NO DEFAULT. The XML attribute is negatively
  named (NonBiblicalStory="false" means biblical), projects hold a mix,
  and a silent wrong answer files the story in the wrong category. The
  user must click one.
* The stage is a closed list -- the derived default plus every stage the
  project already uses. Never free text: one unknown stage value and the
  whole project fails to open in OneStory Editor.
* The preview and loss report are shown BEFORE the write. The preview is
  the safety feature; nothing is written until Inject.
* Always offered the last receipt's Undo, which refuses if the file
  changed since the injection.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .flextext_reader import read_flextext, FlexTextFile
from .ose_serializer import render_story, to_bytes
from .project import OneStoryProject, ProjectError, inject, undo, suggest_set_index
from .story_builder import build_story, derive_stage, loss_report
from .align import PHRASE_CONT

PAD = {"padx": 8, "pady": 4}


class InjectorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("FlexText → OneStory Injector")
        root.minsize(760, 620)

        self.flex: FlexTextFile | None = None
        self.project: OneStoryProject | None = None
        self.last_receipt: dict | None = None

        r = 0
        # --- files ---------------------------------------------------------
        self.flex_var = tk.StringVar()
        self.proj_var = tk.StringVar()
        tk.Label(root, text=".flextext file:").grid(row=r, column=0, sticky="e", **PAD)
        tk.Entry(root, textvariable=self.flex_var, width=58, state="readonly").grid(row=r, column=1, sticky="we", **PAD)
        tk.Button(root, text="Choose…", command=self.pick_flextext).grid(row=r, column=2, **PAD)
        r += 1
        tk.Label(root, text=".onestory project:").grid(row=r, column=0, sticky="e", **PAD)
        tk.Entry(root, textvariable=self.proj_var, width=58, state="readonly").grid(row=r, column=1, sticky="we", **PAD)
        tk.Button(root, text="Choose…", command=self.pick_project).grid(row=r, column=2, **PAD)
        r += 1
        tk.Label(root, fg="#884400", justify="left", wraplength=680, text=(
            "Work on a COPY of the project, and close OneStory Editor first. "
            "A timestamped backup is made before every injection."
        )).grid(row=r, column=0, columnspan=3, sticky="w", **PAD)
        r += 1

        # --- choices ---------------------------------------------------------
        self.text_var = tk.StringVar()
        self.set_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.bib_var = tk.StringVar(value="")          # deliberately no default
        self.crafter_var = tk.StringVar()
        self.facil_var = tk.StringVar()
        self.stage_var = tk.StringVar()
        self.phrase_var = tk.StringVar(value="marker")

        tk.Label(root, text="Story to import:").grid(row=r, column=0, sticky="e", **PAD)
        self.text_dd = ttk.Combobox(root, textvariable=self.text_var, state="disabled")
        self.text_dd.grid(row=r, column=1, columnspan=2, sticky="we", **PAD)
        self.text_dd.bind("<<ComboboxSelected>>", lambda e: self.on_text_chosen())
        r += 1
        tk.Label(root, text="Into story set:").grid(row=r, column=0, sticky="e", **PAD)
        self.set_dd = ttk.Combobox(root, textvariable=self.set_var, state="disabled")
        self.set_dd.grid(row=r, column=1, columnspan=2, sticky="we", **PAD)
        r += 1
        tk.Label(root, text="Story name:").grid(row=r, column=0, sticky="e", **PAD)
        tk.Entry(root, textvariable=self.name_var).grid(row=r, column=1, columnspan=2, sticky="we", **PAD)
        r += 1

        tk.Label(root, text="Story type:").grid(row=r, column=0, sticky="e", **PAD)
        f = tk.Frame(root)
        tk.Radiobutton(f, text="Biblical story", variable=self.bib_var,
                       value="biblical", command=self.on_bib_chosen).pack(side="left")
        tk.Radiobutton(f, text="Non-biblical story", variable=self.bib_var,
                       value="nonbiblical", command=self.on_bib_chosen).pack(side="left", padx=12)
        f.grid(row=r, column=1, columnspan=2, sticky="w", **PAD)
        r += 1

        # Only shown when the chosen text actually contains phrase-words --
        # words whose baseline spans several space-separated tokens under one
        # gloss. OneStory has no such concept, so the user chooses how the
        # continuation tokens are written.
        self.phrase_frame = tk.LabelFrame(root, text="Phrase-words detected")
        self.phrase_label = tk.Label(self.phrase_frame, justify="left", anchor="w")
        self.phrase_label.pack(fill="x", padx=8, pady=(4, 2))
        tk.Radiobutton(
            self.phrase_frame,
            text=f"Mark continuation words with '{PHRASE_CONT}' "
                 "(recommended -- points at the word the gloss belongs to)",
            variable=self.phrase_var, value="marker",
            command=self.update_preview,
        ).pack(anchor="w", padx=8)
        tk.Radiobutton(
            self.phrase_frame,
            text="Write '***' holes instead (they will look like unglossed words)",
            variable=self.phrase_var, value="holes",
            command=self.update_preview,
        ).pack(anchor="w", padx=8, pady=(0, 6))
        self.phrase_frame.grid(row=r, column=0, columnspan=3, sticky="we",
                               padx=8, pady=4)
        self.phrase_frame.grid_remove()   # hidden until detection says otherwise
        r += 1

        tk.Label(root, text="Story crafter:").grid(row=r, column=0, sticky="e", **PAD)
        self.crafter_dd = ttk.Combobox(root, textvariable=self.crafter_var, state="disabled")
        self.crafter_dd.grid(row=r, column=1, columnspan=2, sticky="we", **PAD)
        r += 1
        tk.Label(root, text="Project facilitator:").grid(row=r, column=0, sticky="e", **PAD)
        self.facil_dd = ttk.Combobox(root, textvariable=self.facil_var, state="disabled")
        self.facil_dd.grid(row=r, column=1, columnspan=2, sticky="we", **PAD)
        r += 1
        tk.Label(root, text="Stage (next task):").grid(row=r, column=0, sticky="e", **PAD)
        self.stage_dd = ttk.Combobox(root, textvariable=self.stage_var, state="disabled")
        self.stage_dd.grid(row=r, column=1, columnspan=2, sticky="we", **PAD)
        r += 1

        # --- preview ---------------------------------------------------------
        tk.Label(root, text="Preview / loss report:").grid(row=r, column=0, sticky="ne", **PAD)
        self.preview = tk.Text(root, height=14, width=86, state="disabled", wrap="word")
        self.preview.grid(row=r, column=1, columnspan=2, sticky="nsew", **PAD)
        root.grid_rowconfigure(r, weight=1)
        root.grid_columnconfigure(1, weight=1)
        r += 1

        # --- actions ---------------------------------------------------------
        f2 = tk.Frame(root)
        self.inject_btn = tk.Button(f2, text="Inject story", state="disabled",
                                    command=self.do_inject)
        self.inject_btn.pack(side="left", padx=8)
        self.undo_btn = tk.Button(f2, text="Undo last injection", state="disabled",
                                  command=self.do_undo)
        self.undo_btn.pack(side="left", padx=8)
        f2.grid(row=r, column=0, columnspan=3, pady=10)

        for v in (self.text_var, self.set_var, self.name_var,
                  self.crafter_var, self.facil_var, self.stage_var):
            v.trace_add("write", lambda *_: self.refresh_ready())

    # ------------------------------------------------------------------ IO --
    def pick_flextext(self):
        path = filedialog.askopenfilename(
            title="Choose a .flextext file",
            filetypes=[("FLEx interlinear", "*.flextext"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.flex = read_flextext(path)
        except Exception as e:
            messagebox.showerror("Cannot read file", str(e))
            return
        if not self.flex.texts:
            messagebox.showerror("Nothing to import",
                                 "No usable texts were found in that file.")
            return
        self.flex_var.set(path)
        self.text_dd["values"] = [t.title for t in self.flex.texts]
        self.text_dd["state"] = "readonly"
        self.text_dd.current(0)
        self.on_text_chosen()

    def pick_project(self):
        path = filedialog.askopenfilename(
            title="Choose a .onestory project (a COPY, with OSE closed)",
            filetypes=[("OneStory project", "*.onestory"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.project = OneStoryProject(path)
            if self.project.harvest_tasks() is None:
                raise ProjectError(
                    "This project has no stories yet, so there is nothing to "
                    "copy the task-panel configuration from. Create one story "
                    "in OneStory Editor first, then retry."
                )
        except ProjectError as e:
            self.project = None
            messagebox.showerror("Cannot use this project", str(e))
            return
        self.proj_var.set(path)
        self.set_dd["values"] = [
            f"{s.index}: {s.set_name}  ({len(s.story_names)} stories)"
            for s in self.project.sets]
        self.set_dd["state"] = "readonly"
        self.set_dd.current(0)

        members = sorted(self.project.members, key=lambda m: m.name.lower())
        crafters = [m for m in members if m.has_role("Crafter")] or members
        facils = [m for m in members if m.has_role("ProjectFacilitator")] or members
        self._crafters, self._facils = crafters, facils
        self.crafter_dd["values"] = [m.name for m in crafters]
        self.facil_dd["values"] = [m.name for m in facils]
        self.crafter_dd["state"] = self.facil_dd["state"] = "readonly"
        if crafters:
            self.crafter_dd.current(0)
        if facils:
            self.facil_dd.current(0)
        self._refresh_stages()
        self.refresh_ready()

    # ------------------------------------------------------------- helpers --
    def chosen_text(self):
        if not self.flex or not self.text_var.get():
            return None
        for t in self.flex.texts:
            if t.title == self.text_var.get():
                return t
        return None

    def on_bib_chosen(self):
        """OneStory's UI groups stories BY SET -- the Panorama view has a
        separate Non-Biblical Stories pane -- so the category the user just
        picked determines which set the story belongs in. Select it for
        them; they can still override, and do_inject warns on contradiction.
        (This is the fix for every import landing 'biblical': the attribute
        was written correctly, but into the biblical set.)"""
        if self.project and self.bib_var.get():
            idx = suggest_set_index(self.project.sets,
                                    self.bib_var.get() == "nonbiblical")
            if idx is not None:
                self.set_dd.current(idx)
        self.refresh_ready()

    def on_text_chosen(self):
        t = self.chosen_text()
        if t:
            self.name_var.set(t.title)
            n = t.phrase_word_count()
            if n:
                ex = ", ".join(
                    f'“{w}” = “{g}”' if g else f'“{w}”'
                    for w, g in t.phrase_word_examples()
                )
                self.phrase_label.config(text=(
                    f"This story glosses {n} multi-word unit(s) as single "
                    f"words (e.g. {ex}).\nOneStory can only pair glosses "
                    "word-for-word, so choose how the extra words are marked:"))
                self.phrase_frame.grid()
            else:
                self.phrase_frame.grid_remove()
        self._refresh_stages()
        self.update_preview()
        self.refresh_ready()

    def _refresh_stages(self):
        t = self.chosen_text()
        stages: list = []
        if t:
            stages.append(derive_stage(t))
        if self.project:
            stages += [s for s in self.project.stages_in_use() if s not in stages]
        if stages:
            self.stage_dd["values"] = stages
            self.stage_dd["state"] = "readonly"
            self.stage_dd.current(0)

    def update_preview(self):
        t = self.chosen_text()
        self.preview["state"] = "normal"
        self.preview.delete("1.0", "end")
        if t:
            out = [f"{len(t.phrases)} verse(s) will be created "
                   f"(plus the empty story-notes verse).", ""]
            for i, p in enumerate(t.phrases[:8], 1):
                out.append(f"Verse {i}:")
                out.append(f"  {p.vernacular_line()}")
                g = p.gloss_line(self.phrase_var.get())
                if g:
                    out.append(f"  {g}")
                if p.free:
                    out.append(f"  {p.free}")
                out.append("")
            if len(t.phrases) > 8:
                out.append(f"… and {len(t.phrases) - 8} more verse(s).")
            out.append("")
            out += ["Loss report:"] + [
                f"  • {n}" for n in loss_report(t, self.phrase_var.get())]
            if self.flex and self.flex.warnings:
                out += ["", "Warnings:"] + [f"  ⚠ {w}" for w in self.flex.warnings]
            self.preview.insert("1.0", "\n".join(out))
        self.preview["state"] = "disabled"

    def refresh_ready(self):
        ready = all([
            self.flex is not None,
            self.project is not None,
            self.chosen_text() is not None,
            self.set_var.get() != "",
            self.name_var.get().strip() != "",
            self.bib_var.get() in ("biblical", "nonbiblical"),
            self.crafter_var.get() != "",
            self.facil_var.get() != "",
            self.stage_var.get() != "",
        ])
        self.inject_btn["state"] = "normal" if ready else "disabled"

    # -------------------------------------------------------------- actions --
    def do_inject(self):
        t = self.chosen_text()
        set_index = int(self.set_var.get().split(":", 1)[0])
        set_name = self.project.sets[set_index].set_name
        name = self.name_var.get().strip()

        if name in self.project.sets[set_index].story_names:
            if not messagebox.askyesno(
                    "Duplicate name",
                    f'"{name}" already exists in set "{set_name}".\n\n'
                    "Inject anyway as a second story with the same name?"):
                return

        # A story is EXPERIENCED as biblical/non-biblical by the set it is
        # in, whatever CraftingInfo says. Injecting a contradiction is
        # allowed (archives are mixed) but never silent.
        non_biblical = (self.bib_var.get() == "nonbiblical")
        chosen = self.project.sets[set_index]
        if chosen.character() is not None and chosen.character() != non_biblical:
            kind = "non-biblical" if non_biblical else "biblical"
            other = "biblical" if non_biblical else "non-biblical"
            sug = suggest_set_index(self.project.sets, non_biblical)
            hint = (f'\n\nThe "{self.project.sets[sug].set_name}" set is where '
                    f"{kind} stories live in this project.") if sug is not None else ""
            if not messagebox.askyesno(
                    "Set does not match story type",
                    f'You marked this story {kind}, but every existing story in '
                    f'"{chosen.set_name}" is {other}. OneStory Editor groups '
                    f"stories by set, so it will appear among the {other} "
                    f"stories.{hint}\n\nInject into \"{chosen.set_name}\" anyway?"):
                return

        crafter = next(m for m in self._crafters if m.name == self.crafter_var.get())
        facil = next(m for m in self._facils if m.name == self.facil_var.get())

        story = build_story(
            t,
            story_name=name,
            non_biblical=non_biblical,
            crafter_key=crafter.member_key,
            facilitator_key=facil.member_key,
            stage=self.stage_var.get(),
            tasks=self.project.harvest_tasks(),
            existing_guids=self.project.guids(),
            phrase_mode=self.phrase_var.get(),
        )
        block = to_bytes(render_story(story))

        if not messagebox.askyesno(
                "Confirm injection",
                f'Add "{name}" ({len(t.phrases)} verses) to set "{set_name}" in\n'
                f"{self.project.path}?\n\nA backup is made first."):
            return
        try:
            self.last_receipt = inject(self.project, set_index, set_name, block)
        except ProjectError as e:
            messagebox.showerror("Injection refused", str(e))
            return
        self.undo_btn["state"] = "normal"
        messagebox.showinfo(
            "Done",
            f'"{name}" was added.\n\nBackup:\n{self.last_receipt["backup"]}\n\n'
            "Open the project in OneStory Editor and check the story before "
            "trusting the result.")
        # reload so a second injection uses fresh offsets
        self.project = OneStoryProject(self.project.path)

    def do_undo(self):
        if not self.last_receipt:
            return
        try:
            undo(self.last_receipt)
        except ProjectError as e:
            messagebox.showerror("Undo refused", str(e))
            return
        messagebox.showinfo("Undone", "The project was restored from the backup.")
        self.undo_btn["state"] = "disabled"
        self.project = OneStoryProject(self.last_receipt["project"])
        self.last_receipt = None


def main():
    root = tk.Tk()
    InjectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
