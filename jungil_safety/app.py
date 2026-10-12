"""정일건설 안전관리 도우미 (HPMS 부적합보고서 / TBM 보고서 자체 관리용)."""
import datetime as dt
import os
import shutil
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

import core
import sample_data

APP_TITLE = "정일건설 안전관리 도우미"

NCR_FORM = [
    ("report_no", "보고서 번호", "entry", None),
    ("issue_date", "발행일", "date", None),
    ("due_date", "조치요구일", "date", None),
    ("done_date", "조치완료", "date", None),
    ("dept", "발행부서", "combo", core.DEPTS),
    ("source", "출처", "combo", core.SOURCES),
    ("author", "작성자", "entry", None),
    ("receiver", "수신처", "entry", None),
    ("issue_type", "발행구분", "combo", core.ISSUE_TYPES),
    ("result", "결과확인", "combo", core.RESULTS),
    ("title", "제목", "entry", None),
    ("location", "위치/작업", "entry", None),
    ("action", "조치내용", "text", None),
    ("memo", "비고", "text", None),
]
TBM_FORM = [
    ("site_code", "현장코드", "entry", None),
    ("ptw_no", "PTW 관리번호", "combo", None),
    ("company", "협력업체명", "entry", None),
    ("reg_date", "등록일", "date", None),
    ("exec_date", "실시일", "date", None),
    ("kind", "실시구분", "combo", core.TBM_KINDS),
    ("leader", "작업반장", "entry", None),
    ("attendees", "참석인원", "entry", None),
    ("work", "작업내용", "text", None),
    ("hazards", "위험요인", "text", None),
    ("measures", "안전대책", "text", None),
    ("memo", "비고", "text", None),
]


class FormDialog(tk.Toplevel):
    """등록/수정 공통 입력창. on_save(dict) 가 ValueError 를 내면 메시지 표시 후 유지."""

    def __init__(self, master, title, form, values, on_save, combo_values=None):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.on_save = on_save
        self.widgets = {}
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        for row, (key, label, kind, options) in enumerate(form):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="ne", padx=(0, 8), pady=3)
            val = values.get(key, "") or ""
            if kind == "text":
                w = tk.Text(body, width=48, height=3, wrap="word")
                w.insert("1.0", val)
                w.grid(row=row, column=1, columnspan=2, sticky="we", pady=3)
            elif kind == "combo":
                w = ttk.Combobox(body, width=46, values=options or (combo_values or {}).get(key, []))
                w.set(val)
                w.grid(row=row, column=1, columnspan=2, sticky="we", pady=3)
            else:
                w = ttk.Entry(body, width=34 if kind == "date" else 48)
                w.insert(0, val)
                w.grid(row=row, column=1, columnspan=1 if kind == "date" else 2, sticky="w", pady=3)
                if kind == "date":
                    ttk.Button(body, text="오늘", width=6,
                               command=lambda e=w: (e.delete(0, "end"), e.insert(0, core.today()))
                               ).grid(row=row, column=2, sticky="w", padx=4)
            self.widgets[key] = w
        btns = ttk.Frame(body)
        btns.grid(row=len(form), column=0, columnspan=3, pady=(10, 0))
        ttk.Button(btns, text="저장", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="left", padx=4)
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        first = next(iter(self.widgets.values()))
        first.focus_set()

    def values(self):
        out = {}
        for k, w in self.widgets.items():
            out[k] = w.get("1.0", "end").strip() if isinstance(w, tk.Text) else w.get().strip()
        return out

    def save(self):
        try:
            self.on_save(self.values())
        except ValueError as e:
            messagebox.showwarning("입력 확인", str(e), parent=self)
            return
        self.destroy()


class ListTab(ttk.Frame):
    """조회조건 + 목록(Treeview) + 버튼으로 이루어진 탭의 공통 부분."""

    table = ""
    fields = []
    lead_cols = []  # [(키, 머리글, 폭)] - 목록 앞에 붙는 계산 열

    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.store = app.store
        self.filters = ttk.Frame(self)
        self.filters.pack(fill="x")
        self.buttons = ttk.Frame(self)
        self.buttons.pack(fill="x", pady=(6, 4))
        self.info = ttk.Label(self.buttons, text="", foreground="#C00000")
        self.info.pack(side="left")
        cols = [("_no", "No", 45)] + self.lead_cols + list(self.fields)
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings", selectmode="extended")
        for key, head, width in cols:
            self.tree.heading(key, text=head)
            self.tree.column(key, width=width, anchor="w" if width >= 120 else "center", stretch=False)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.tag_configure("overdue", background="#FFD6D6")
        self.tree.tag_configure("open", background="#FFF7CC")
        self.tree.bind("<Double-1>", lambda e: self.edit())
        self.tree.bind("<Delete>", lambda e: self.delete())
        self.rows = []

    # 하위 클래스에서 구현
    def query(self):
        raise NotImplementedError

    def row_tag(self, r):
        return ()

    def add_filter(self, label, widget_factory, col):
        ttk.Label(self.filters, text="· " + label).grid(row=col // 4, column=(col % 4) * 2, sticky="e", padx=(10, 4), pady=2)
        w = widget_factory(self.filters)
        w.grid(row=col // 4, column=(col % 4) * 2 + 1, sticky="w", pady=2)
        return w

    def add_button(self, text, cmd):
        ttk.Button(self.buttons, text=text, command=cmd).pack(side="right", padx=2)

    def refresh(self):
        try:
            self.rows = self.query()
        except ValueError as e:
            messagebox.showwarning("조회 조건", str(e))
            return
        self.tree.delete(*self.tree.get_children())
        cols = self.tree["columns"]
        for i, r in enumerate(self.rows, 1):
            vals = [len(self.rows) - i + 1] + [str(r.get(c, "")).replace("\n", " ") for c in cols[1:]]
            self.tree.insert("", "end", iid=str(r["id"]), values=vals, tags=self.row_tag(r))
        self.after_refresh()

    def after_refresh(self):
        pass

    def selected_ids(self):
        return [int(i) for i in self.tree.selection()]

    def delete(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo("삭제", "삭제할 항목을 선택하세요.")
            return
        if messagebox.askyesno("삭제", f"선택한 {len(ids)}건을 삭제할까요?"):
            self.store.delete(self.table, ids)
            self.refresh()

    def export(self, title, extra=()):
        if not self.rows:
            messagebox.showinfo("엑셀파일", "저장할 자료가 없습니다.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"{title}_{core.today()}.xlsx",
        )
        if not path:
            return
        try:
            core.export_xlsx(path, title, self.fields, self.rows, extra)
        except PermissionError:
            messagebox.showerror("엑셀파일", "파일이 열려 있어 저장할 수 없습니다. 엑셀을 닫고 다시 시도하세요.")
            return
        if messagebox.askyesno("엑셀파일", f"저장했습니다.\n{path}\n\n지금 열까요?"):
            open_file(path)

    def import_file(self, aliases, importer, label):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm")])
        if not path:
            return
        try:
            rows = core.import_xlsx(path, aliases)
        except Exception as e:  # noqa: BLE001 - 사용자에게 그대로 보여줌
            messagebox.showerror("엑셀 불러오기", f"읽지 못했습니다.\n{e}")
            return
        a, b, errors = importer(rows)
        msg = f"추가 {a}건, {label} {b}건"
        if errors:
            msg += f"\n\n오류 {len(errors)}건:\n" + "\n".join(errors[:15])
        messagebox.showinfo("엑셀 불러오기", msg)
        self.refresh()
        self.app.summary.refresh()


def date_entry(value):
    def make(parent):
        e = ttk.Entry(parent, width=12)
        e.insert(0, value)
        return e
    return make


def combo(values, width=14, default="전체"):
    def make(parent):
        c = ttk.Combobox(parent, values=values, width=width, state="readonly")
        c.set(default)
        return c
    return make


def entry(width=16):
    return lambda parent: ttk.Entry(parent, width=width)


class NcrTab(ListTab):
    table = "ncr"
    fields = core.NCR_FIELDS
    lead_cols = [("status", "상태", 70)]

    def __init__(self, master, app):
        super().__init__(master, app)
        start = (dt.date.today() - dt.timedelta(days=92)).isoformat()
        self.f_start = self.add_filter("기간(발행일) 시작", date_entry(start), 0)
        self.f_end = self.add_filter("~ 종료", date_entry(core.today()), 1)
        self.f_status = self.add_filter("상태", combo(["전체", "진행중", "기한초과", "완료"]), 2)
        self.f_receiver = self.add_filter("수신처", entry(), 3)
        self.f_receiver.insert(0, "정일건설")
        self.f_kw = self.add_filter("검색어(제목/번호/작성자)", entry(24), 4)
        self.f_kw.bind("<Return>", lambda e: self.refresh())
        ttk.Button(self.filters, text="조회", command=self.refresh).grid(row=1, column=7, sticky="e")
        for text, cmd in [
            ("엑셀 불러오기", lambda: self.import_file(core.NCR_ALIASES, self.store.import_ncr, "갱신")),
            ("엑셀파일", lambda: self.export("부적합보고서", [("status", "상태")])),
            ("삭제", self.delete),
            ("조치완료 처리", self.complete),
            ("수정", self.edit),
            ("등록", self.add),
        ]:
            self.add_button(text, cmd)

    def query(self):
        return self.store.list_ncr(
            self.f_start.get(), self.f_end.get(), self.f_status.get(),
            self.f_receiver.get().strip(), self.f_kw.get().strip(),
        )

    def row_tag(self, r):
        return {"기한초과": ("overdue",), "진행중": ("open",)}.get(r["status"], ())

    def after_refresh(self):
        rate = core.on_time_rate(self.rows)
        n_open = sum(1 for r in self.rows if r["status"] != "완료")
        n_over = sum(1 for r in self.rows if r["status"] == "기한초과")
        txt = f"조회 {len(self.rows)}건 · 미조치 {n_open}건 · 기한초과 {n_over}건 · 기한 내 조치율 "
        txt += "-" if rate is None else f"{rate:.2f}%"
        self.info.configure(text=txt)

    def add(self):
        values = {
            "issue_date": core.today(),
            "due_date": core.today(),
            "receiver": self.store.setting("company"),
            "source": "일반",
            "issue_type": core.ISSUE_TYPES[0],
            "result": "미완료",
        }
        FormDialog(self, "부적합 보고서 등록 (보고서 번호는 비우면 자동)", NCR_FORM, values, self._saver(None))

    def edit(self):
        ids = self.selected_ids()
        if not ids:
            return
        FormDialog(self, "부적합 보고서 수정", NCR_FORM, self.store.get("ncr", ids[0]), self._saver(ids[0]))

    def _saver(self, rid):
        def save(values):
            self.store.save_ncr(values, rid)
            self.refresh()
            self.app.summary.refresh()
        return save

    def complete(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo("조치완료", "조치완료 처리할 항목을 선택하세요.")
            return
        if not messagebox.askyesno("조치완료", f"선택한 {len(ids)}건을 오늘({core.today()}) 조치완료로 처리할까요?"):
            return
        for rid in ids:
            r = self.store.get("ncr", rid)
            if not r["done_date"]:
                r.update(done_date=core.today(), result="완료")
                self.store.save_ncr(r, rid)
        self.refresh()
        self.app.summary.refresh()


class TbmTab(ListTab):
    table = "tbm"
    fields = core.TBM_FIELDS

    def __init__(self, master, app):
        super().__init__(master, app)
        start = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        self.f_start = self.add_filter("실시일 시작", date_entry(start), 0)
        self.f_end = self.add_filter("~ 종료", date_entry(core.today()), 1)
        self.f_kind = self.add_filter("구분", combo(["전체"] + core.TBM_KINDS), 2)
        self.f_kw = self.add_filter("검색어(PTW/작업/반장)", entry(24), 3)
        self.f_kw.bind("<Return>", lambda e: self.refresh())
        ttk.Button(self.filters, text="조회", command=self.refresh).grid(row=1, column=7, sticky="e")
        for text, cmd in [
            ("엑셀 불러오기", lambda: self.import_file(core.TBM_ALIASES, self.store.import_tbm, "중복 건너뜀")),
            ("엑셀파일", lambda: self.export("TBM보고서")),
            ("미실시일 확인", self.check_missing),
            ("삭제", self.delete),
            ("수정", self.edit),
            ("복사 등록(오늘)", self.copy_today),
            ("등록", self.add),
        ]:
            self.add_button(text, cmd)

    def query(self):
        return self.store.list_tbm(self.f_start.get(), self.f_end.get(), self.f_kind.get(), self.f_kw.get().strip())

    def after_refresh(self):
        days = len({r["exec_date"] for r in self.rows})
        people = sum(int(r["attendees"]) for r in self.rows if r["attendees"].isdigit())
        self.info.configure(text=f"조회 {len(self.rows)}건 · 실시일수 {days}일 · 참석 연인원 {people}명")

    def _dialog(self, title, values, rid):
        def save(v):
            self.store.save_tbm(v, rid)
            self.refresh()
            self.app.summary.refresh()
        FormDialog(self, title, TBM_FORM, values, save, {"ptw_no": self.store.ptw_numbers()})

    def add(self):
        ptws = self.store.ptw_numbers()
        values = {
            "site_code": self.store.setting("site_code"),
            "company": self.store.setting("company"),
            "reg_date": core.today(),
            "exec_date": core.today(),
            "kind": core.TBM_KINDS[0],
            "ptw_no": ptws[0] if ptws else "",
        }
        self._dialog("TBM 보고서 등록", values, None)

    def copy_today(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo("복사 등록", "복사할 TBM 을 선택하세요. (어제 내용을 오늘 날짜로 불러옵니다)")
            return
        r = self.store.get("tbm", ids[0])
        r.update(reg_date=core.today(), exec_date=core.today(), attendees="")
        self._dialog("TBM 보고서 복사 등록", r, None)

    def edit(self):
        ids = self.selected_ids()
        if ids:
            self._dialog("TBM 보고서 수정", self.store.get("tbm", ids[0]), ids[0])

    def check_missing(self):
        try:
            days = self.store.missing_tbm_days(self.f_start.get(), self.f_end.get())
        except ValueError as e:
            messagebox.showwarning("미실시일 확인", str(e))
            return
        if not days:
            messagebox.showinfo("미실시일 확인", "조회 기간 중 TBM 누락일이 없습니다. (일요일 제외)")
            return
        wd = "월화수목금토일"
        lines = [f"{d} ({wd[dt.date.fromisoformat(d).weekday()]})" for d in days]
        messagebox.showwarning(
            "미실시일 확인",
            f"TBM 기록이 없는 날 {len(days)}일 (일요일 제외)\n휴무일이 아니면 HPMS 등록 여부를 확인하세요.\n\n"
            + "\n".join(lines[:40]) + ("\n..." if len(lines) > 40 else ""),
        )


class SummaryTab(ttk.Frame):
    COLS = [
        ("month", "월", 80), ("ncr", "부적합 발행", 90), ("done", "조치완료", 80),
        ("open", "미조치", 70), ("overdue", "기한초과", 80), ("rate", "기한 내 조치율", 110),
        ("tbm_days", "TBM 실시일수", 100), ("tbm_count", "TBM 건수", 80),
    ]

    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.store = app.store
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="· 연도").pack(side="left")
        self.year = ttk.Spinbox(top, from_=2020, to=2100, width=6, command=self.refresh)
        self.year.set(dt.date.today().year)
        self.year.pack(side="left", padx=4)
        ttk.Button(top, text="조회", command=self.refresh).pack(side="left")
        ttk.Button(top, text="엑셀파일", command=self.export).pack(side="right")
        self.tree = ttk.Treeview(self, columns=[c[0] for c in self.COLS], show="headings", height=14)
        for k, h, w in self.COLS:
            self.tree.heading(k, text=h)
            self.tree.column(k, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=6)
        self.tree.tag_configure("total", background="#DCE6F1")
        self.rows = []

    def refresh(self):
        try:
            year = int(self.year.get())
        except ValueError:
            return
        self.rows = self.store.monthly_summary(year)
        self.tree.delete(*self.tree.get_children())
        for r in self.rows:
            self.tree.insert("", "end", values=[r[k] for k, _, _ in self.COLS])
        tot = {k: sum(r[k] for r in self.rows) for k in ("ncr", "done", "open", "overdue", "tbm_days", "tbm_count")}
        ncr = self.store.list_ncr(f"{year}-01-01", f"{year}-12-31")
        rate = core.on_time_rate(ncr)
        tot.update(month="합계", rate="" if rate is None else f"{rate:.2f}%")
        self.tree.insert("", "end", values=[tot[k] for k, _, _ in self.COLS], tags=("total",))

    def export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"월별현황_{self.year.get()}.xlsx",
        )
        if path:
            core.export_xlsx(path, f"{self.year.get()}년 월별 안전관리 현황", self.COLS, self.rows)
            open_file(path)


def open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
    except OSError:
        pass


class App(tk.Tk):
    def __init__(self, db_path=None):
        super().__init__()
        self.store = core.Store(db_path)
        self.geometry("1360x760")
        self.minsize(1000, 560)
        family = "맑은 고딕" if sys.platform.startswith("win") else tkfont.nametofont("TkDefaultFont").actual("family")
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
            tkfont.nametofont(name).configure(family=family, size=10)
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=(family, 10, "bold"))

        self.header = ttk.Label(self, padding=(10, 8), font=(family, 13, "bold"))
        self.header.pack(fill="x")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.ncr = NcrTab(nb, self)
        self.tbm = TbmTab(nb, self)
        self.summary = SummaryTab(nb, self)
        nb.add(self.ncr, text="  안전·보건 부적합 보고서  ")
        nb.add(self.tbm, text="  TBM 보고서  ")
        nb.add(self.summary, text="  월별 현황  ")
        self._menu()
        self.update_header()
        self.refresh_all()

    def _menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="자료 백업...", command=self.backup)
        f.add_command(label="HPMS 화면 예시 자료 불러오기", command=self.load_sample)
        f.add_separator()
        f.add_command(label="종료", command=self.destroy)
        m.add_cascade(label="파일", menu=f)
        s = tk.Menu(m, tearoff=0)
        s.add_command(label="현장/업체 정보...", command=self.edit_settings)
        m.add_cascade(label="설정", menu=s)
        h = tk.Menu(m, tearoff=0)
        h.add_command(label="사용법", command=self.help)
        m.add_cascade(label="도움말", menu=h)
        self.config(menu=m)

    def update_header(self):
        st = self.store.setting
        self.title(f"{APP_TITLE} - [{st('site_code')}] {st('site_name')}")
        self.header.configure(text=f"[{st('site_code')}] {st('site_name')}   |   {st('company')}")

    def refresh_all(self):
        self.ncr.refresh()
        self.tbm.refresh()
        self.summary.refresh()

    def edit_settings(self):
        form = [("site_code", "현장코드", "entry", None), ("site_name", "현장명", "entry", None),
                ("company", "협력업체명", "entry", None)]
        values = {k: self.store.setting(k) for k, *_ in form}

        def save(v):
            if not all(v.values()):
                raise ValueError("모든 항목을 입력하세요.")
            for k, val in v.items():
                self.store.set_setting(k, val)
            self.update_header()

        FormDialog(self, "현장/업체 정보", form, values, save)

    def backup(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".db", filetypes=[("DB", "*.db")],
            initialfile=f"jungil_safety_backup_{core.today()}.db",
        )
        if path:
            self.store.db.commit()
            shutil.copyfile(self.store.path, path)
            messagebox.showinfo("백업", f"백업했습니다.\n{path}")

    def load_sample(self):
        if not messagebox.askyesno("예시 자료", "HPMS 화면에 보이던 부적합보고서 19건, TBM 18건을 불러올까요?\n(이미 있는 번호는 갱신/건너뜀)"):
            return
        a1, b1, _ = self.store.import_ncr(sample_data.ncr_rows())
        a2, b2, _ = self.store.import_tbm(sample_data.tbm_rows())
        messagebox.showinfo("예시 자료", f"부적합보고서 추가 {a1} / 갱신 {b1}\nTBM 추가 {a2} / 중복 {b2}")
        self.ncr.f_start.delete(0, "end")
        self.ncr.f_start.insert(0, "2026-07-01")
        self.refresh_all()

    def help(self):
        messagebox.showinfo("사용법", (
            "■ 부적합 보고서\n"
            " - 등록: 보고서 번호를 비우면 [현장코드]-HSE-NCR-YYYYMM-순번 으로 자동 부여\n"
            " - 조치완료 처리: 선택한 건을 오늘 날짜로 완료 처리\n"
            " - 노란색 = 진행중, 빨간색 = 조치요구일 경과(기한초과)\n"
            " - 기한 내 조치율 = 기한 도래/완료 건 중 기한 내 조치 비율\n\n"
            "■ TBM 보고서\n"
            " - 복사 등록(오늘): 선택한 TBM 내용을 오늘 날짜로 복사\n"
            " - 미실시일 확인: 조회 기간 중 TBM 기록이 없는 날(일요일 제외)\n\n"
            "■ 엑셀 불러오기\n"
            " - HPMS 에서 [엑셀파일]로 받은 목록을 그대로 불러올 수 있습니다\n"
            "   (머리글 이름으로 열을 자동 인식)\n\n"
            f"■ 자료 파일: {self.store.path}\n"
            "   프로그램과 같은 폴더에 저장됩니다. 주기적으로 [파일 > 자료 백업] 하세요."
        ))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
