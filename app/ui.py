"""Tkinter UI for the Philippines Native Wiki.

Two-pane layout:
    left  -- search + filters + scrollable species list
    right -- selected species card (image + facts + summary)
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Callable

from .data import (
    Filter,
    HABITAT_LABELS,
    REGION_LABELS,
    Species,
    apply_filter,
    load_species,
)


try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:                                # pragma: no cover
    HAS_PIL = False


COLOR_SWATCH = {
    "black":  "#111",  "white":  "#f5f5f5", "grey":   "#808080",
    "brown":  "#7a4b1a", "tan":   "#d2b48c", "cream":  "#f5eddb",
    "red":    "#c0392b", "orange":"#e67e22", "yellow": "#f1c40f",
    "gold":   "#d4af37", "green": "#27ae60", "olive":  "#6b8e23",
    "blue":   "#2c6fbb", "purple":"#8e44ad", "pink":   "#e91e63",
    "silver": "#c0c0c0", "rust":  "#b7410e", "cyan":   "#17a2b8",
}

APP_TITLE = "Philippines Native Wiki"
CARD_IMAGE_MAX = 380      # px on the long side inside the detail pane


class WikiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("980x640")
        self.root.minsize(760, 520)

        self.species: list[Species] = load_species()
        self.filter = Filter()
        self.visible: list[Species] = list(self.species)
        self.selected: Species | None = None
        self._photo_ref = None    # keep Tk PhotoImage alive

        self._build_layout()
        self._refresh_list()
        if self.visible:
            self._select(self.visible[0])

    # ---------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill="both", expand=True)

        paned = ttk.Panedwindow(outer, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=(4, 4))
        right = ttk.Frame(paned, padding=(8, 4))
        paned.add(left, weight=1)
        paned.add(right, weight=2)

        self._build_filters(left)
        self._build_list(left)
        self._build_detail(right)

    def _build_filters(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Filters", padding=6)
        box.pack(fill="x", pady=(0, 6))

        # search
        row = ttk.Frame(box); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Search:").pack(side="left")
        self.query_var = tk.StringVar()
        self.query_var.trace_add("write", lambda *_: self._on_filter_change())
        e = ttk.Entry(row, textvariable=self.query_var)
        e.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # kind
        row = ttk.Frame(box); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Kind:").pack(side="left")
        self.kind_var = tk.StringVar(value="all")
        for label, val in (("All", "all"), ("Animals", "animal"), ("Plants", "plant")):
            ttk.Radiobutton(row, text=label, variable=self.kind_var,
                            value=val, command=self._on_filter_change).pack(side="left", padx=2)

        # regions (multi-select)
        row = ttk.Frame(box); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Region:").pack(side="left")
        self.region_vars: dict[str, tk.BooleanVar] = {}
        for code, label in REGION_LABELS.items():
            v = tk.BooleanVar(value=False)
            self.region_vars[code] = v
            short = {"ncr": "NCR", "region3": "Region III", "calabarzon": "CALABARZON"}[code]
            ttk.Checkbutton(row, text=short, variable=v,
                            command=self._on_filter_change).pack(side="left", padx=2)

        # habitat
        row = ttk.Frame(box); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Habitat:").pack(side="left")
        self.habitat_var = tk.StringVar(value="all")
        habitats = [("Any", "all")] + [(v, k) for k, v in HABITAT_LABELS.items()]
        cb = ttk.Combobox(row, state="readonly", textvariable=self.habitat_var,
                          values=[label for label, _ in habitats], width=18)
        cb.current(0)
        self._habitat_lookup = {label: code for label, code in habitats}
        cb.bind("<<ComboboxSelected>>",
                lambda _e: (self._sync_habitat(), self._on_filter_change()))
        cb.pack(side="left", padx=(6, 0))

        # edibility
        row = ttk.Frame(box); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Edible:").pack(side="left")
        self.edibility_var = tk.StringVar(value="all")
        for label, val in (("All", "all"), ("Edible", "yes"), ("Not edible", "no")):
            ttk.Radiobutton(row, text=label, variable=self.edibility_var,
                            value=val, command=self._on_filter_change).pack(side="left", padx=2)

    def _build_list(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Species", padding=4)
        box.pack(fill="both", expand=True)
        self.count_var = tk.StringVar(value="0 of 0")
        ttk.Label(box, textvariable=self.count_var).pack(anchor="w")

        wrap = ttk.Frame(box); wrap.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(wrap, activestyle="dotbox", exportselection=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

    def _build_detail(self, parent: ttk.Frame) -> None:
        self.detail = parent

        self.image_label = ttk.Label(parent, anchor="center")
        self.image_label.pack(fill="x", pady=(0, 8))

        self.name_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.name_var,
                  font=("TkDefaultFont", 16, "bold")).pack(anchor="w")

        self.sci_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.sci_var,
                  font=("TkDefaultFont", 11, "italic")).pack(anchor="w")

        self.chip_row = ttk.Frame(parent)
        self.chip_row.pack(fill="x", pady=(6, 0))

        self.color_row = ttk.Frame(parent)
        self.color_row.pack(fill="x", pady=(4, 0))

        self.facts_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.facts_var,
                  wraplength=520, justify="left").pack(anchor="w", pady=(6, 0))

        # summary text
        self.summary_text = tk.Text(parent, height=8, wrap="word",
                                    borderwidth=1, relief="sunken")
        self.summary_text.pack(fill="both", expand=True, pady=(8, 4))
        self.summary_text.configure(state="disabled")

        self.location_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.location_var,
                  wraplength=520, justify="left",
                  foreground="#333").pack(anchor="w", pady=(2, 4))

        actions = ttk.Frame(parent); actions.pack(fill="x", pady=(4, 0))
        self.open_btn = ttk.Button(actions, text="Open on Wikipedia",
                                   command=self._open_wikipedia)
        self.open_btn.pack(side="left")
        self.credit_var = tk.StringVar(value="")
        ttk.Label(actions, textvariable=self.credit_var,
                  foreground="#555").pack(side="right")

    # ------------------------------------------------------------- callbacks
    def _sync_habitat(self) -> None:
        # combobox stores label; translate to code
        label = self.habitat_var.get()
        code = self._habitat_lookup.get(label, "all")
        self.habitat_var.set(label)   # keep display
        self._habitat_code = code

    def _on_filter_change(self) -> None:
        self.filter.query = self.query_var.get()
        self.filter.kind = self.kind_var.get()
        self.filter.regions = {c for c, v in self.region_vars.items() if v.get()}
        self.filter.habitat = getattr(self, "_habitat_code", "all")
        self.filter.edibility = self.edibility_var.get()
        self._refresh_list()

    def _on_list_select(self, _event) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.visible):
            self._select(self.visible[idx])

    def _open_wikipedia(self) -> None:
        if self.selected and self.selected.wikipedia_url:
            webbrowser.open_new_tab(self.selected.wikipedia_url)

    # ---------------------------------------------------------------- render
    def _refresh_list(self) -> None:
        self.visible = apply_filter(self.species, self.filter)
        self.listbox.delete(0, tk.END)
        for s in self.visible:
            self.listbox.insert(tk.END, s.common_name)
        self.count_var.set(f"{len(self.visible)} of {len(self.species)}")
        if not self.visible:
            self._clear_detail()
        else:
            still = next((i for i, s in enumerate(self.visible)
                          if self.selected and s.id == self.selected.id), None)
            if still is None:
                still = 0
                self._select(self.visible[0])
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(still)
            self.listbox.see(still)

    def _clear_detail(self) -> None:
        self.selected = None
        self.image_label.configure(image="", text="No species matches filters")
        self._photo_ref = None
        self.name_var.set("")
        self.sci_var.set("")
        self.facts_var.set("")
        self.location_var.set("")
        self.credit_var.set("")
        self._set_summary("")
        for w in self.chip_row.winfo_children(): w.destroy()
        for w in self.color_row.winfo_children(): w.destroy()

    def _select(self, sp: Species) -> None:
        self.selected = sp
        self.name_var.set(sp.common_name)
        self.sci_var.set(sp.scientific_name)

        # facts line
        facts = []
        facts.append(f"Kind: {sp.kind.capitalize()} ({sp.group})")
        facts.append("Edible: Yes" if sp.edible else "Edible: No")
        self.facts_var.set("    ".join(facts))

        # chips
        for w in self.chip_row.winfo_children(): w.destroy()
        ttk.Label(self.chip_row, text="Regions:").pack(side="left")
        for r in sp.regions:
            tk.Label(self.chip_row, text=REGION_LABELS.get(r, r),
                     background="#e0ecf7", padx=6, pady=1,
                     borderwidth=1, relief="solid").pack(side="left", padx=2)
        ttk.Label(self.chip_row, text="  Habitats:").pack(side="left")
        for h in sp.habitats:
            tk.Label(self.chip_row, text=HABITAT_LABELS.get(h, h),
                     background="#e6f4ea", padx=6, pady=1,
                     borderwidth=1, relief="solid").pack(side="left", padx=2)

        # colors
        for w in self.color_row.winfo_children(): w.destroy()
        ttk.Label(self.color_row, text="Colors:").pack(side="left")
        for c in sp.colors:
            swatch = tk.Label(self.color_row, text=" ", width=2,
                              background=COLOR_SWATCH.get(c, "#ccc"),
                              borderwidth=1, relief="solid")
            swatch.pack(side="left", padx=1)
            ttk.Label(self.color_row, text=c).pack(side="left", padx=(2, 6))

        self._set_summary(sp.summary or "(no summary available)")
        self.location_var.set(f"Location: {sp.location_notes}" if sp.location_notes else "")
        self.credit_var.set(f"Image: {sp.image_credit}" if sp.image_credit else "")
        self._load_image(sp)

    def _set_summary(self, text: str) -> None:
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert("1.0", text)
        self.summary_text.configure(state="disabled")

    def _load_image(self, sp: Species) -> None:
        self._photo_ref = None
        path = sp.image_path
        if not path or not path.exists():
            self.image_label.configure(image="", text="(no image available)")
            return
        if not HAS_PIL:
            self.image_label.configure(image="", text=f"[image] {path.name}")
            return
        try:
            with Image.open(path) as im:
                im.load()
                w, h = im.size
                scale = min(CARD_IMAGE_MAX / max(w, h), 1.0)
                if scale < 1.0:
                    im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                photo = ImageTk.PhotoImage(im)
        except Exception as e:                    # pragma: no cover
            self.image_label.configure(image="", text=f"(image error: {e})")
            return
        self._photo_ref = photo
        self.image_label.configure(image=photo, text="")


def run() -> None:
    root = tk.Tk()
    WikiApp(root)
    root.mainloop()
