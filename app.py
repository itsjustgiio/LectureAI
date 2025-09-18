import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
import shutil

from core.config import (
    load_state, save_state,
    ensure_class_dir, ensure_day_dir,
    open_in_explorer,  # helper to open folders
)
from core.services.transcriber import transcribe_file
from core.services.summarizer import summarize_text
from core.utils.chunking import chunk_text
from core.storage import save_texts, save_meta

# --- Fix DPI scaling issues on Windows ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Win 8.1+
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Win 7
    except Exception:
        pass

# --- Color Palette ---
COLORS = {
    "PRIMARY":   "#1E3A8A",  # Navy
    "SECONDARY": "#3B82F6",  # Sky Blue
    "BG":        "#F3F4F6",  # App background
    "TEXT":      "#111827",  # Near Black
    "ACCENT":    "#10B981",  # Emerald
    "MUTED":     "#6B7280",  # Muted Gray
    "WHITE":     "#FFFFFF",  # Card background
    "BORDER":    "#E5E7EB",  # Light border
}

STATE = load_state()

# -------------------- Custom Input Dialog --------------------
def custom_input_dialog(title, prompt, default=""):
    dialog = tk.Toplevel()
    dialog.title(title)
    dialog.geometry("400x180")  # wider & taller

    dialog.resizable(False, False)  # prevent shrinking

    label = tk.Label(dialog, text=prompt, font=("Segoe UI", 11))
    label.pack(pady=5)

    entry_var = tk.StringVar(value=default)
    entry = tk.Entry(dialog, textvariable=entry_var, width=35, font=("Segoe UI", 11))
    entry.pack(pady=5)

    result = {"value": None}

    def on_ok():
        result["value"] = entry_var.get().strip()
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    ok_btn = tk.Button(dialog, text="OK", command=on_ok, width=10)
    ok_btn.pack(side="left", padx=20, pady=10)

    cancel_btn = tk.Button(dialog, text="Cancel", command=on_cancel, width=10)
    cancel_btn.pack(side="right", padx=20, pady=10)

    entry.focus_set()  # focus entry automatically
    dialog.grab_set()
    dialog.wait_window()
    return result["value"]


class LectureApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lecture Summarizer")
        self.geometry("1200x700")
        self.configure(bg=COLORS["BG"])

        # active selection
        self.selected_class: str | None = None
        self.selected_folder: str | None = None
        self.selected_day: str | None = None
        self.model_var = tk.StringVar(value="base")
        self.max_chunk = tk.IntVar(value=1000)
        self.font_size = tk.IntVar(value=12)
        self.current_audio = tk.StringVar(value="No file chosen")
        self.status = tk.StringVar(value="Ready.")

        # UI
        self._setup_style()
        self._build_sidebar()
        self._build_main()

    # -------------------- Styling --------------------
    def _setup_style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass

        s.configure(".", background=COLORS["BG"], foreground=COLORS["TEXT"], font=("Segoe UI", 10))

        s.configure("Sidebar.TFrame", background=COLORS["WHITE"], borderwidth=1, relief="solid")

        s.configure(
            "Sidebar.Treeview",
            background=COLORS["WHITE"],
            fieldbackground=COLORS["WHITE"],
            foreground=COLORS["TEXT"],
            borderwidth=0,
            rowheight=32
        )
        s.map(
            "Sidebar.Treeview",
            background=[("selected", COLORS["SECONDARY"])],
            foreground=[("selected", COLORS["WHITE"])],
        )
        s.layout("Sidebar.Treeview", s.layout("Treeview"))

        s.configure("TNotebook", background=COLORS["BG"], borderwidth=0)
        s.configure("TNotebook.Tab", background=COLORS["WHITE"], padding=(12, 6))
        s.map("TNotebook.Tab", background=[("selected", COLORS["BG"])])

        s.configure("Card.TFrame", background=COLORS["WHITE"], borderwidth=1, relief="solid")

        s.configure("Accent.TButton", background=COLORS["ACCENT"], foreground=COLORS["WHITE"], padding=8, borderwidth=0)
        s.map("Accent.TButton", background=[("active", "#0ea371")])

    # -------------------- Sidebar --------------------
    def _build_sidebar(self):
        outer = ttk.Frame(self, padding=(10, 10, 8, 10))
        outer.pack(side=tk.LEFT, fill=tk.Y)

        card = ttk.Frame(outer, style="Sidebar.TFrame")
        card.pack(fill=tk.Y, expand=False)

        header = ttk.Frame(card, style="Sidebar.TFrame")
        header.pack(fill=tk.X, padx=10, pady=(10, 6))
        ttk.Label(header, text="Classes", font=("Segoe UI Semibold", 11), background=COLORS["WHITE"]).pack(anchor="w")

        treewrap = ttk.Frame(card, style="Sidebar.TFrame")
        treewrap.pack(fill=tk.BOTH, expand=True, padx=8)

        self.tree = ttk.Treeview(
            treewrap,
            style="Sidebar.Treeview",
            show="tree",
            selectmode="browse"
        )
        vscroll = ttk.Scrollbar(treewrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        treewrap.columnconfigure(0, weight=1)
        treewrap.rowconfigure(0, weight=1)

        self.tree.column("#0", width=220, stretch=True)

        self.menu_day = tk.Menu(self, tearoff=0)
        self.menu_day.add_command(label="Open Folder", command=self._open_selected_day_folder)
        self.menu_day.add_command(label="Rename Day", command=self._rename_day)
        self.menu_day.add_command(label="Delete Day…", command=self._delete_day)

        self.menu_folder = tk.Menu(self, tearoff=0)
        self.menu_folder.add_command(label="Delete Folder…", command=self._delete_folder)

        self.menu_class = tk.Menu(self, tearoff=0)
        self.menu_class.add_command(label="Rename Class", command=self._rename_class)
        self.menu_class.add_command(label="Delete Class…", command=self._delete_class)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Double-1>", self._on_double_click)

        footer = ttk.Frame(card, style="Sidebar.TFrame")
        footer.pack(fill=tk.X, padx=8, pady=(8, 10))
        ttk.Button(footer, text="+ New Class", command=self._add_class).pack(fill=tk.X)
        ttk.Button(footer, text="+ New Folder", command=self._add_folder).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(footer, text="+ Add Notes", command=self._add_notes).pack(fill=tk.X, pady=(6, 0))

        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for cname, data in STATE["classes"].items():
            class_id = self.tree.insert("", "end", text=cname, open=True)

            # show notes directly under class
            for nname in data.get("notes", []):
                self.tree.insert(class_id, "end", text=nname)

            # show folders and their notes
            folders = data.get("folders", {})
            STATE["classes"][cname]["folders"] = folders
            for fname, notes in folders.items():
                folder_id = self.tree.insert(class_id, "end", text=fname, open=True)
                for nname in notes:
                    self.tree.insert(folder_id, "end", text=nname)



    def _on_select(self, _event):
        selection = self.tree.selection()
        if not selection:  # ✅ nothing selected, bail out
            return

        node = selection[0]
        parent = self.tree.parent(node)
        gparent = self.tree.parent(parent)

        if gparent:  # note inside folder
            self.selected_class = self.tree.item(gparent, "text")
            self.selected_folder = self.tree.item(parent, "text")
            self.selected_day = self.tree.item(node, "text")
        elif parent:  # folder selected
            self.selected_class = self.tree.item(parent, "text")
            self.selected_folder = self.tree.item(node, "text")
            self.selected_day = None
        else:  # class selected
            self.selected_class = self.tree.item(node, "text")
            self.selected_folder = None
            self.selected_day = None

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)

        parent = self.tree.parent(item)
        gparent = self.tree.parent(parent)

        if gparent:  # it's a day
            self.menu_day.post(event.x_root, event.y_root)
        elif parent:  # it's a folder
            self.menu_folder.post(event.x_root, event.y_root)
        else:  # it's a class
            self.menu_class.post(event.x_root, event.y_root)

    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        parent = self.tree.parent(item)
        gparent = self.tree.parent(parent)
        if gparent:  # day
            cname = self.tree.item(gparent, "text")
            dname = self.tree.item(item, "text")
            day_dir = ensure_day_dir(cname, dname)
            open_in_explorer(day_dir)

    def _open_selected_day_folder(self):
        node = self.tree.selection()[0]
        parent = self.tree.parent(node)
        gparent = self.tree.parent(parent)
        if gparent:  # day
            cname = self.tree.item(gparent, "text")
            dname = self.tree.item(node, "text")
            open_in_explorer(ensure_day_dir(cname, dname))

    def _rename_day(self):
        node = self.tree.selection()[0]
        parent = self.tree.parent(node)
        gparent = self.tree.parent(parent)
        if not gparent:
            return
        cname = self.tree.item(gparent, "text")
        old_name = self.tree.item(node, "text")
        new_name = custom_input_dialog("Rename Day", f"Rename '{old_name}' to:", old_name)
        if new_name and new_name.strip():
            days = STATE["classes"][cname]["folders"][self.tree.item(parent, "text")]
            idx = days.index(old_name)
            old_dir = Path("data") / cname / old_name
            new_dir = Path("data") / cname / new_name
            try:
                if old_dir.exists() and not new_dir.exists():
                    old_dir.rename(new_dir)
            except Exception as e:
                messagebox.showwarning("Rename Warning", f"Renamed in app, but folder rename failed:\n{e}")
            days[idx] = new_name
            save_state(STATE)
            self._refresh_tree()

    def _rename_class(self):
        node = self.tree.selection()[0]
        kind = self.tree.parent(node)
        if kind:
            return
        old_name = self.tree.item(node, "text")
        new_name = custom_input_dialog("Rename Class", f"Rename '{old_name}' to:", old_name)
        if new_name and new_name.strip() and new_name not in STATE["classes"]:
            old_dir = Path("data") / old_name
            new_dir = Path("data") / new_name
            try:
                if old_dir.exists() and not new_dir.exists():
                    old_dir.rename(new_dir)
            except Exception as e:
                messagebox.showwarning("Rename Warning", f"Renamed in app, but folder rename failed:\n{e}")
            STATE["classes"][new_name] = STATE["classes"].pop(old_name)
            save_state(STATE)
            self._refresh_tree()
        elif new_name in STATE["classes"]:
            messagebox.showerror("Error", "A class with that name already exists.")

    def _delete_day(self):
        node = self.tree.selection()[0]
        parent = self.tree.parent(node)
        gparent = self.tree.parent(parent)
        if not gparent:
            return
        cname = self.tree.item(gparent, "text")
        dname = self.tree.item(node, "text")
        if not messagebox.askyesno("Delete Day", f"Remove '{dname}' from {cname}?"):
            return
        days = STATE["classes"][cname]["folders"][self.tree.item(parent, "text")]
        if dname in days:
            days.remove(dname)
            save_state(STATE)
        day_dir = Path("data") / cname / dname
        if day_dir.exists() and messagebox.askyesno("Delete Files", f"Also delete files in:\n{day_dir}?"):
            try:
                shutil.rmtree(day_dir)
            except Exception as e:
                messagebox.showwarning("Delete Warning", f"Could not delete folder:\n{e}")
        self._refresh_tree()

    def _delete_folder(self):
        node = self.tree.selection()[0]
        parent = self.tree.parent(node)

        # make sure it's a folder (parent is class, not root, and children are days)
        if not parent or self.tree.parent(parent):
            messagebox.showerror("Error", "Select a folder to delete.")
            return

        cname = self.tree.item(parent, "text")
        folder_name = self.tree.item(node, "text")

        if not messagebox.askyesno("Delete Folder", f"Delete folder '{folder_name}' in class '{cname}'?\n(This will also delete all days inside it)"):
            return

        # remove from state
        folders = STATE["classes"][cname].get("folders", {})
        if folder_name in folders:
            del folders[folder_name]
            save_state(STATE)

        self._refresh_tree()

    def _delete_class(self):
        node = self.tree.selection()[0]
        parent = self.tree.parent(node)
        if parent:
            return
        cname = self.tree.item(node, "text")
        if not messagebox.askyesno("Delete Class", f"Remove class '{cname}' from the app?"):
            return
        STATE["classes"].pop(cname, None)
        save_state(STATE)
        class_dir = Path("data") / cname
        if class_dir.exists() and messagebox.askyesno("Delete Files", f"Also delete ALL files in:\n{class_dir}?"):
            try:
                shutil.rmtree(class_dir)
            except Exception as e:
                messagebox.showwarning("Delete Warning", f"Could not delete folder:\n{e}")
        self._refresh_tree()
        self.selected_class, self.selected_folder, self.selected_day = None, None, None

    def _add_class(self):
        name = custom_input_dialog("New Class", "Enter class name:", "New Class")
        if not name:
            return
        if name in STATE["classes"]:
            messagebox.showerror("Error", "Class already exists.")
            return
        STATE["classes"][name] = {"folders": {}}
        ensure_class_dir(name)
        save_state(STATE)
        self._refresh_tree()

    def _add_folder(self):
        if not self.selected_class:
            messagebox.showerror("Error", "Select a class first.")
            return

        folder_name = custom_input_dialog("New Folder", "Enter folder name:", "New Folder")
        if not folder_name:
            return

        folders = STATE["classes"][self.selected_class].setdefault("folders", {})
        if folder_name in folders:
            messagebox.showerror("Error", f"Folder '{folder_name}' already exists.")
            return

        folders[folder_name] = []
        save_state(STATE)
        self._refresh_tree()

    def _add_notes(self):
        if not self.selected_class:
            messagebox.showerror("Error", "Select a class or folder first.")
            return

        # If folder selected, put notes inside it
        if self.selected_folder:
            folder_days = STATE["classes"][self.selected_class]["folders"][self.selected_folder]
            default_name = f"Notes {len(folder_days) + 1}"
            note_name = custom_input_dialog("New Notes", "Enter notes name:", default_name)
            if not note_name:
                return
            folder_days.append(note_name)
        else:
            # No folder, put notes directly under class
            class_days = STATE["classes"][self.selected_class].setdefault("notes", [])
            default_name = f"Notes {len(class_days) + 1}"
            note_name = custom_input_dialog("New Notes", "Enter notes name:", default_name)
            if not note_name:
                return
            class_days.append(note_name)

        ensure_day_dir(self.selected_class, note_name)
        save_state(STATE)
        self._refresh_tree()

    # -------------------- Main Area: Notebook + Status --------------------
    def _build_main(self):
        right = ttk.Frame(self, padding=(8, 10, 10, 10))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_transcript_tab()
        self._build_summary_tab()
        self._build_split_tab()

        statusbar = ttk.Frame(right)
        statusbar.pack(fill=tk.X, pady=(6, 0))
        self.status_lbl = ttk.Label(statusbar, textvariable=self.status)
        self.status_lbl.pack(side=tk.LEFT, padx=4)
        self.progress = ttk.Progressbar(statusbar, mode="indeterminate", length=200)
        self.progress.pack(side=tk.RIGHT, padx=4)

    def _build_transcript_tab(self):
        frame = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(frame, text="Transcript")

        ttk.Label(frame, text="Audio File").pack(anchor="w", pady=(4, 0))
        ttk.Button(frame, text="Choose File", command=self._choose_audio).pack(anchor="w", pady=4)
        ttk.Label(frame, textvariable=self.current_audio, foreground=COLORS["MUTED"]).pack(anchor="w", pady=(0, 10))

        ttk.Label(frame, text="Whisper Model").pack(anchor="w")
        ttk.Combobox(frame, textvariable=self.model_var, values=["tiny", "base", "small", "medium", "large"], state="readonly")\
            .pack(anchor="w", pady=4)

        ttk.Button(frame, text="Transcribe Audio", command=self._transcribe, style="Accent.TButton")\
            .pack(fill=tk.X, pady=10)

        self.transcript_txt = tk.Text(frame, wrap="word")
        self._style_text(self.transcript_txt)
        self.transcript_txt.pack(fill=tk.BOTH, expand=True)

    def _build_summary_tab(self):
        frame = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(frame, text="Summary")

        ttk.Label(frame, text="Max Chunk Length").pack(anchor="w")
        ttk.Scale(frame, from_=300, to=2000, variable=self.max_chunk, orient="horizontal").pack(fill=tk.X, pady=6)

        ttk.Button(frame, text="Summarize Text", command=self._summarize, style="Accent.TButton")\
            .pack(fill=tk.X, pady=10)

        self.summary_txt = tk.Text(frame, wrap="word")
        self._style_text(self.summary_txt)
        self.summary_txt.pack(fill=tk.BOTH, expand=True)

    def _build_split_tab(self):
        frame = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(frame, text="Split View")

        left = ttk.Frame(frame, padding=8)
        right = ttk.Frame(frame, padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left, text="Transcript").pack(anchor="w")
        self.transcript_txt_split = tk.Text(left, wrap="word")
        self._style_text(self.transcript_txt_split)
        self.transcript_txt_split.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="Summary").pack(anchor="w")
        self.summary_txt_split = tk.Text(right, wrap="word")
        self._style_text(self.summary_txt_split)
        self.summary_txt_split.pack(fill=tk.BOTH, expand=True)

    def _style_text(self, widget: tk.Text):
        widget.configure(
            bg=COLORS["WHITE"],
            fg=COLORS["TEXT"],
            insertbackground=COLORS["TEXT"],
            highlightthickness=1,
            highlightbackground=COLORS["BORDER"],
            relief="flat",
            padx=10,
            pady=10,
            font=("Segoe UI", 11),
        )

    # -------------------- Busy helpers --------------------
    def _busy(self, on: bool, msg: str = ""):
        if on:
            if msg:
                self.status.set(msg)
            self.progress.start(10)
        else:
            self.progress.stop()
            if msg:
                self.status.set(msg)

    # -------------------- Actions --------------------
    def _choose_audio(self):
        path = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg"), ("All files", "*.*")]
        )
        if path:
            self.current_audio.set(Path(path).name)
            self._chosen_path = path

    def _transcribe(self):
        if not (self.selected_class and self.selected_day):
            messagebox.showerror("Error", "Select a class and day first.")
            return
        if not hasattr(self, "_chosen_path"):
            messagebox.showerror("Error", "Choose an audio file first.")
            return

        def work():
            try:
                self._busy(True, "Transcribing…")
                text = transcribe_file(self._chosen_path, model_name=self.model_var.get())
                for w in (self.transcript_txt, self.transcript_txt_split):
                    w.delete("1.0", tk.END)
                    w.insert(tk.END, text)
                self._busy(False, "Transcription complete.")
            except Exception as e:
                self._busy(False, "Error")
                messagebox.showerror("Transcription Error", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _summarize(self):
        if not (self.selected_class and self.selected_day):
            messagebox.showerror("Error", "Select a class and day first.")
            return
        transcript = self.transcript_txt.get("1.0", tk.END).strip()
        if not transcript:
            messagebox.showerror("Error", "No transcript to summarize yet.")
            return

        def work():
            try:
                self._busy(True, "Summarizing…")
                chunks = chunk_text(transcript, max_chars=int(self.max_chunk.get()))
                results = [summarize_text(c) for c in chunks]
                summary = "\n\n".join(results)

                for w in (self.summary_txt, self.summary_txt_split):
                    w.delete("1.0", tk.END)
                    w.insert(tk.END, summary)

                day_dir = Path("data") / self.selected_class / self.selected_day
                save_texts(day_dir, transcript, summary)
                if hasattr(self, "_chosen_path"):
                    save_meta(day_dir, self._chosen_path, self.model_var.get())
                self._busy(False, "Summary complete.")
            except Exception as e:
                self._busy(False, "Error")
                messagebox.showerror("Summarization Error", str(e))

        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    app = LectureApp()
    app.mainloop()
