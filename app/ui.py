"""Tkinter UI for the Philippines Native Wiki.

Two-pane layout:
    left  -- search + filters + scrollable species list
    right -- scrollable species card (image + facts + summary + sources)

The right pane is a Canvas holding an inner Frame; the whole card scrolls
together, so long summaries never spill off the bottom of the window --
matching the scrolling pattern used in the ExoPiNet wiki. Mouse-wheel
bindings cover Windows/macOS (<MouseWheel>) and X11 (<Button-4/5>) so
Raspberry Pi OS behaves the same as the desktop build.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

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
CARD_IMAGE_MAX = 340      # px on the long side inside the detail pane

ABOUT_TEXT = (
    "Philippines Native Wiki\n"
    "60 plants and animals native to Metro Manila, Region III, and CALABARZON.\n\n"
    "Text: excerpts from the English Wikipedia (CC BY-SA 4.0), fetched via the\n"
    "MediaWiki REST summary API. Each species card shows the source article and\n"
    "links back to it.\n\n"
    "Images: lead photos from Wikimedia Commons. Each image retains its original\n"
    "licence; the author + licence string is displayed on the species card and\n"
    "recorded in data/species.json.\n\n"
    "Curated regional, habitat, colour, and edibility tags are original to this\n"
    "project (MIT-licensed) -- see scripts/seed.py."
)


class WikiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1020x680")
        self.root.minsize(780, 540)

        self.species: list[Species] = load_species()
        self.filter = Filter()
        self.visible: list[Species] = list(self.species)
        self.selected: Species | None = None
        self._photo_ref = None            # keep Tk PhotoImage alive
        self._wraplength = 500            # updated on canvas resize
        self._wrap_widgets: list[tk.Widget] = []   # widgets whose wraplength tracks the canvas

        self._build_menu()
        self._build_layout()
        self._refresh_list()
        if self.visible:
            self._select(self.visible[0])

    # ------------------------------------------------------------------ menu
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        helpm = tk.Menu(menubar, tearoff=False)
        helpm.add_command(label="About / Sources", command=self._show_about)
        menubar.add_cascade(label="Help", menu=helpm)
        self.root.config(menu=menubar)

    def _show_about(self) -> None:
        messagebox.showinfo(APP_TITLE, ABOUT_TEXT, parent=self.root)

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
        right = ttk.Frame(paned, padding=(4, 4))
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
        self.habitat_var = tk.StringVar(value="Any")
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
        # Scroll infrastructure: Canvas + inner Frame + Scrollbar
        self._canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._inner = ttk.Frame(self._canvas, padding=(6, 4, 6, 12))
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw",
        )

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse-wheel wiring: bind at the root level, then dispatch only if
        # the pointer is currently over the detail canvas (or a descendant).
        # Enter/Leave on the canvas itself doesn't fire when the pointer moves
        # onto child widgets, so per-widget binding is the reliable option.
        self.root.bind_all("<MouseWheel>", self._on_wheel_windows, add="+")
        self.root.bind_all("<Button-4>", self._on_wheel_x11_up, add="+")
        self.root.bind_all("<Button-5>", self._on_wheel_x11_down, add="+")

        # --------------- content widgets (all inside self._inner)
        self.image_label = tk.Label(self._inner, anchor="center")
        self.image_label.pack(fill="x", pady=(0, 8))

        self.name_var = tk.StringVar(value="")
        n = ttk.Label(self._inner, textvariable=self.name_var,
                      font=("TkDefaultFont", 16, "bold"))
        n.pack(anchor="w")

        self.sci_var = tk.StringVar(value="")
        ttk.Label(self._inner, textvariable=self.sci_var,
                  font=("TkDefaultFont", 11, "italic"),
                  foreground="#444").pack(anchor="w")

        self.chip_row = ttk.Frame(self._inner)
        self.chip_row.pack(fill="x", pady=(6, 0))

        self.color_row = ttk.Frame(self._inner)
        self.color_row.pack(fill="x", pady=(4, 0))

        self.facts_var = tk.StringVar(value="")
        f = ttk.Label(self._inner, textvariable=self.facts_var,
                      justify="left")
        f.pack(anchor="w", pady=(6, 0))
        self._wrap_widgets.append(f)

        # ---- Summary
        ttk.Separator(self._inner, orient="horizontal").pack(fill="x", pady=(10, 4))
        ttk.Label(self._inner, text="Summary",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar(value="")
        s = ttk.Label(self._inner, textvariable=self.summary_var,
                      justify="left")
        s.pack(anchor="w", pady=(2, 0))
        self._wrap_widgets.append(s)

        # ---- Location
        ttk.Separator(self._inner, orient="horizontal").pack(fill="x", pady=(10, 4))
        ttk.Label(self._inner, text="Where to find it",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.location_var = tk.StringVar(value="")
        loc = ttk.Label(self._inner, textvariable=self.location_var,
                        justify="left", foreground="#333")
        loc.pack(anchor="w", pady=(2, 0))
        self._wrap_widgets.append(loc)

        # ---- Sources
        ttk.Separator(self._inner, orient="horizontal").pack(fill="x", pady=(10, 4))
        ttk.Label(self._inner, text="Sources",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")

        self.text_source_var = tk.StringVar(value="")
        ts = ttk.Label(self._inner, textvariable=self.text_source_var,
                       justify="left", foreground="#333")
        ts.pack(anchor="w", pady=(2, 0))
        self._wrap_widgets.append(ts)

        self.image_source_var = tk.StringVar(value="")
        ims = ttk.Label(self._inner, textvariable=self.image_source_var,
                        justify="left", foreground="#333")
        ims.pack(anchor="w", pady=(2, 0))
        self._wrap_widgets.append(ims)

        self.source_buttons = ttk.Frame(self._inner)
        self.source_buttons.pack(anchor="w", pady=(6, 0))

    # ------------------------------------------------------- scroll plumbing
    def _on_inner_configure(self, _event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        # Keep the inner frame the same width as the canvas so labels wrap.
        self._canvas.itemconfigure(self._canvas_window, width=event.width)
        pad = 24  # room for the scrollbar + inner padding
        new_wrap = max(200, event.width - pad)
        if new_wrap != self._wraplength:
            self._wraplength = new_wrap
            for w in self._wrap_widgets:
                w.configure(wraplength=new_wrap)

    def _pointer_over_canvas(self, event) -> bool:
        """True if the event's pointer is inside the detail canvas subtree."""
        try:
            w = self.root.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return False
        while w is not None:
            if w is self._canvas:
                return True
            w = getattr(w, "master", None)
        return False

    def _on_wheel_windows(self, event) -> None:
        if not self._pointer_over_canvas(event):
            return
        self._canvas.yview_scroll(int(-event.delta / 60), "units")

    def _on_wheel_x11_up(self, event) -> None:
        if not self._pointer_over_canvas(event):
            return
        self._canvas.yview_scroll(-3, "units")

    def _on_wheel_x11_down(self, event) -> None:
        if not self._pointer_over_canvas(event):
            return
        self._canvas.yview_scroll(3, "units")

    # ------------------------------------------------------------- callbacks
    def _sync_habitat(self) -> None:
        label = self.habitat_var.get()
        self._habitat_code = self._habitat_lookup.get(label, "all")

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

    def _open_url(self, url: str) -> None:
        if url:
            webbrowser.open_new_tab(url)

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
        self.summary_var.set("")
        self.location_var.set("")
        self.text_source_var.set("")
        self.image_source_var.set("")
        for w in self.chip_row.winfo_children(): w.destroy()
        for w in self.color_row.winfo_children(): w.destroy()
        for w in self.source_buttons.winfo_children(): w.destroy()
        self._canvas.yview_moveto(0.0)

    def _select(self, sp: Species) -> None:
        self.selected = sp
        self.name_var.set(sp.common_name)
        self.sci_var.set(sp.scientific_name)

        # facts line
        facts = [f"Kind: {sp.kind.capitalize()} ({sp.group})",
                 "Edible: Yes" if sp.edible else "Edible: No"]
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

        self.summary_var.set(sp.summary or "(no summary available)")
        self.location_var.set(sp.location_notes or "(no regional notes)")

        # ---- sources
        self.text_source_var.set(
            f'Text: English Wikipedia article "{sp.common_name}" (CC BY-SA 4.0)'
        )

        if sp.image_file:
            credit = sp.image_credit or "Wikimedia Commons"
            self.image_source_var.set(f"Image: {credit} — via Wikimedia Commons")
        else:
            self.image_source_var.set("Image: none (no free image on Wikimedia Commons)")

        for w in self.source_buttons.winfo_children(): w.destroy()
        if sp.wikipedia_url:
            ttk.Button(self.source_buttons, text="Open Wikipedia article",
                       command=lambda u=sp.wikipedia_url: self._open_url(u)).pack(side="left", padx=(0, 6))
        if sp.image_source_url:
            ttk.Button(self.source_buttons, text="Open image on Commons",
                       command=lambda u=sp.image_source_url: self._open_url(u)).pack(side="left")

        self._load_image(sp)

        # Jump scroll to top when switching entries
        self._canvas.update_idletasks()
        self._canvas.yview_moveto(0.0)

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
