"""
PDF Stamper — מערכת חותמות PDF
מוסיף חותמת "התקבל" או "שולם" + timestamp על קבצי PDF
"""

import os
import sys
import threading
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox
import fitz  # PyMuPDF
from PIL import Image

# ─── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def get_app_dir():
    """Returns the app's root directory — works both in dev mode and as EXE."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ─── Configuration ─────────────────────────────────────────────────────────────
STAMP_CONFIGS = {
    "received": {
        "label": "התקבל",
        "file": "received.jpg",
        "fg": ("#2563EB", "#1D4ED8"),
        "hover": ("#1D4ED8", "#1E40AF"),
        "ts_color": (0.10, 0.55, 0.20),   # green timestamp
    },
    "paid": {
        "label": "שולם",
        "file": "paid.jpg",
        "fg": ("#16A34A", "#15803D"),
        "hover": ("#15803D", "#166534"),
        "ts_color": (0.10, 0.55, 0.20),   # green timestamp
    },
}

POSITIONS = {
    "ימין למטה": "bottom-right",
    "שמאל למטה": "bottom-left",
    "ימין למעלה": "top-right",
    "שמאל למעלה": "top-left",
}


# ─── Main Application ──────────────────────────────────────────────────────────
class PDFStamperApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("מערכת חותמות PDF")
        self.geometry("680x720")
        self.minsize(540, 600)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._selected_files = []   # list of absolute PDF paths
        self._stamp_type = None     # "received" | "paid"
        self._processing = False

        self._build_ui()

    # ══════════════════════════════════════════════════ UI Construction ══

    def _build_ui(self):
        self._build_header()
        self._build_stamp_buttons()
        self._build_file_section()
        self._build_action_section()
        self._build_log_section()

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray90", "gray15"))
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr,
            text="מערכת חותמות PDF - עבור חברת רוזין",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, pady=(15, 3))

        ctk.CTkLabel(
            hdr,
            text="חתימה אוטומטית על מסמכי PDF",
            font=ctk.CTkFont(size=13),
            text_color=("gray55", "gray65"),
        ).grid(row=1, column=0, pady=(0, 15))

    # ── Stamp-type buttons ────────────────────────────────────────────────
    def _build_stamp_buttons(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, padx=30, pady=(18, 4), sticky="ew")
        frame.grid_columnconfigure((0, 1), weight=1)

        for col, (key, cfg) in enumerate(STAMP_CONFIGS.items()):
            pad = (0, 10) if col == 0 else (10, 0)
            ctk.CTkButton(
                frame,
                text=f"חתום {cfg['label']}  ✓",
                height=65,
                font=ctk.CTkFont(size=16, weight="bold"),
                fg_color=cfg["fg"],
                hover_color=cfg["hover"],
                corner_radius=10,
                command=lambda k=key: self._on_stamp_selected(k),
            ).grid(row=0, column=col, padx=pad, sticky="ew")

        self._hint_lbl = ctk.CTkLabel(
            frame,
            text="בחר סוג חותמת ←",
            font=ctk.CTkFont(size=12),
            text_color=("gray55", "gray65"),
        )
        self._hint_lbl.grid(row=1, column=0, columnspan=2, pady=(8, 0))

    # ── File list section ─────────────────────────────────────────────────
    def _build_file_section(self):
        box = ctk.CTkFrame(self)
        box.grid(row=2, column=0, padx=30, pady=(6, 6), sticky="ew")
        box.grid_columnconfigure(0, weight=1)

        # toolbar
        bar = ctk.CTkFrame(box, fg_color="transparent")
        bar.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")
        bar.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            bar, text="קבצי PDF שנבחרו:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            bar, text="הוסף קבצים +", width=140,
            font=ctk.CTkFont(size=12),
            command=self._add_files,
        ).grid(row=0, column=1)

        ctk.CTkButton(
            bar, text="נקה הכל", width=88,
            font=ctk.CTkFont(size=12),
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self._clear_files,
        ).grid(row=0, column=2, padx=(6, 0))

        self._file_count_lbl = ctk.CTkLabel(
            bar, text="0 קבצים",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        )
        self._file_count_lbl.grid(row=0, column=3, sticky="e")

        # scrollable list
        self._file_list = ctk.CTkScrollableFrame(box, height=115)
        self._file_list.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")
        self._file_list.grid_columnconfigure(0, weight=1)

    # ── Action section (settings + create button) ─────────────────────────
    def _build_action_section(self):
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=3, column=0, padx=30, pady=(0, 6), sticky="ew")
        box.grid_columnconfigure(0, weight=1)

        # options row
        opts = ctk.CTkFrame(box, fg_color="transparent")
        opts.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(opts, text="מיקום חותמת:", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(0, 6))

        self._position_var = ctk.StringVar(value="ימין למטה")
        ctk.CTkOptionMenu(
            opts,
            variable=self._position_var,
            values=list(POSITIONS.keys()),
            width=145,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=1)

        self._all_pages_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts,
            text="חתום על כל הדפים (לא רק עמוד ראשון)",
            variable=self._all_pages_var,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=2, padx=18)

        # "צור חותמת" button
        self._create_btn = ctk.CTkButton(
            box,
            text="צור חותמת",
            height=52,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=("#DC2626", "#B91C1C"),
            hover_color=("#B91C1C", "#991B1B"),
            corner_radius=10,
            state="disabled",
            command=self._start_stamping,
        )
        self._create_btn.grid(row=1, column=0, sticky="ew")

    # ── Log / progress section ────────────────────────────────────────────
    def _build_log_section(self):
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=4, column=0, padx=30, pady=(4, 14), sticky="nsew")
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)

        self._progress = ctk.CTkProgressBar(box)
        self._progress.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self._progress.set(0)

        self._log_box = ctk.CTkTextbox(
            box,
            font=ctk.CTkFont(family="Courier New", size=11),
            state="disabled",
        )
        self._log_box.grid(row=1, column=0, sticky="nsew")

        self._status_lbl = ctk.CTkLabel(
            box,
            text="מוכן לעבודה",
            font=ctk.CTkFont(size=11),
            text_color=("gray55", "gray65"),
        )
        self._status_lbl.grid(row=2, column=0, pady=(4, 0))

    # ══════════════════════════════════════════════════ Event Handlers ══

    def _on_stamp_selected(self, key):
        self._stamp_type = key
        cfg = STAMP_CONFIGS[key]
        self._hint_lbl.configure(
            text=f"חותמת נבחרת: {cfg['label']}",
            text_color=cfg["fg"][0],
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._update_create_btn()

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="בחר קבצי PDF",
            filetypes=[("PDF Files", "*.pdf")],
        )
        added = 0
        for f in files:
            if f not in self._selected_files:
                self._selected_files.append(f)
                self._add_file_row(f)
                added += 1
        if added:
            self._refresh_file_count()
            self._update_create_btn()

    def _add_file_row(self, path):
        row = ctk.CTkFrame(
            self._file_list,
            fg_color=("gray92", "gray18"),
            corner_radius=6,
        )
        row.pack(fill="x", padx=2, pady=2)
        row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            row,
            text=os.path.basename(path),
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).grid(row=0, column=0, padx=(8, 4), pady=3, sticky="w")

        ctk.CTkButton(
            row,
            text="✕",
            width=26,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color=("gray75", "gray35"),
            hover_color=("gray60", "gray45"),
            command=lambda p=path, r=row: self._remove_file(p, r),
        ).grid(row=0, column=1, padx=4)

    def _remove_file(self, path, row_widget):
        self._selected_files.remove(path)
        row_widget.destroy()
        self._refresh_file_count()
        self._update_create_btn()

    def _clear_files(self):
        self._selected_files.clear()
        for w in self._file_list.winfo_children():
            w.destroy()
        self._refresh_file_count()
        self._update_create_btn()

    def _refresh_file_count(self):
        n = len(self._selected_files)
        self._file_count_lbl.configure(text=f"{n} קבצים")

    def _update_create_btn(self):
        ready = bool(self._stamp_type and self._selected_files and not self._processing)
        self._create_btn.configure(state="normal" if ready else "disabled")

    def _start_stamping(self):
        if not self._stamp_type or not self._selected_files:
            return

        cfg = STAMP_CONFIGS[self._stamp_type]
        stamp_path = os.path.join(get_app_dir(), "stamps", cfg["file"])

        if not os.path.exists(stamp_path):
            messagebox.showerror(
                "חותמת לא נמצאה",
                f"קובץ החותמת לא נמצא:\n\n{stamp_path}\n\n"
                f"אנא הכנס קובץ בשם  '{cfg['file']}'\n"
                f"בתיקיית 'stamps'  שליד קובץ ה-EXE.",
            )
            return

        # Capture options from main thread before handing off to worker
        files = list(self._selected_files)
        position = POSITIONS.get(self._position_var.get(), "bottom-right")
        stamp_all = self._all_pages_var.get()
        ts_color = cfg["ts_color"]

        self._processing = True
        self._update_create_btn()

        threading.Thread(
            target=self._worker,
            args=(files, stamp_path, cfg["label"], position, stamp_all, ts_color),
            daemon=True,
        ).start()

    # ══════════════════════════════════════════════════ Worker Thread ══

    def _worker(self, files, stamp_path, label, position, stamp_all, ts_color):
        total = len(files)
        success = 0
        failed = 0

        self.after(0, self._log_clear)
        self.after(0, lambda: self._progress.set(0))
        self.after(0, lambda: self._log(f"מתחיל חתימה '{label}' על {total} קבצים"))
        self.after(0, lambda: self._log("─" * 52))

        for i, path in enumerate(files):
            fname = os.path.basename(path)
            self.after(0, lambda f=fname: self._status_lbl.configure(text=f"מעבד: {f}"))

            try:
                self._stamp_pdf(path, stamp_path, position, stamp_all, ts_color)
                self.after(0, lambda f=fname: self._log(f"{f}  ✓"))
                success += 1
            except PermissionError:
                msg = "הקובץ נעול — סגור אותו בתוכנה אחרת ונסה שוב"
                self.after(0, lambda f=fname, m=msg: self._log(f"{f}  —  {m}  ✗"))
                failed += 1
            except Exception as exc:
                msg = str(exc)
                self.after(0, lambda f=fname, m=msg: self._log(f"{f}  —  {m}  ✗"))
                failed += 1

            prog = (i + 1) / total
            self.after(0, lambda v=prog: self._progress.set(v))

        self.after(0, lambda: self._log("─" * 52))
        summary = f"הושלם: {success} הצליחו" + (f",  {failed} נכשלו" if failed else "")
        self.after(0, lambda s=summary: self._log(s))
        self.after(0, lambda s=summary: self._status_lbl.configure(text=s))
        self.after(0, lambda s=summary: self._on_worker_done(s))

    def _on_worker_done(self, summary):
        self._processing = False
        self._update_create_btn()
        messagebox.showinfo("הסתיים", summary)

    # ══════════════════════════════════════════════════ PDF Stamping ══

    def _stamp_pdf(self, pdf_path, stamp_img_path, position, stamp_all, ts_color):
        """Apply stamp image + timestamp to the PDF and overwrite the original."""
        # Pre-read image dimensions (safe, just reads metadata)
        with Image.open(stamp_img_path) as img:
            orig_w, orig_h = img.size

        tmp = pdf_path + ".__stamp_tmp__"
        try:
            doc = fitz.open(pdf_path)
            pages = range(len(doc)) if stamp_all else [0]
            for pnum in pages:
                self._apply_stamp_to_page(
                    doc[pnum], stamp_img_path, position, orig_w, orig_h, ts_color
                )
            doc.save(tmp, garbage=4, deflate=True)
            doc.close()
            os.replace(tmp, pdf_path)
        except Exception:
            doc_ref = locals().get("doc")
            if doc_ref:
                try:
                    doc_ref.close()
                except Exception:
                    pass
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def _apply_stamp_to_page(self, page, stamp_img_path, position, orig_w, orig_h, ts_color):
        """Insert the stamp image and timestamp text onto a single page."""
        STAMP_W = 135      # width in PDF points (~4.8 cm)
        MARGIN = 20        # distance from page edge
        TS_HEIGHT = 16     # height of timestamp text block
        GAP = 4            # gap between image and timestamp

        stamp_h = int(orig_h * STAMP_W / orig_w)
        total_h = stamp_h + GAP + TS_HEIGHT

        pw = page.rect.width
        ph = page.rect.height

        if position == "bottom-right":
            x1, y1 = pw - STAMP_W - MARGIN, ph - total_h - MARGIN
        elif position == "bottom-left":
            x1, y1 = MARGIN, ph - total_h - MARGIN
        elif position == "top-right":
            x1, y1 = pw - STAMP_W - MARGIN, MARGIN
        else:                                        # top-left
            x1, y1 = MARGIN, MARGIN

        # Insert stamp image
        page.insert_image(
            fitz.Rect(x1, y1, x1 + STAMP_W, y1 + stamp_h),
            filename=stamp_img_path,
        )

        # Insert timestamp below the stamp image
        ts = datetime.now().strftime("%d/%m/%Y  %H:%M")
        page.insert_textbox(
            fitz.Rect(x1, y1 + stamp_h + GAP,
                      x1 + STAMP_W, y1 + stamp_h + GAP + TS_HEIGHT),
            ts,
            fontsize=12,
            color=ts_color,
            align=1,   # centered
        )

    # ══════════════════════════════════════════════════════ Logging ══

    def _log(self, msg):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _log_clear(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")


# ─── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = PDFStamperApp()
    app.mainloop()
