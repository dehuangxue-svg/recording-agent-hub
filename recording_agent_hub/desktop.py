"""Native desktop entry point for Recording Agent Hub."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.request import Request, urlopen

from recording_agent_hub import __version__, app
from recording_agent_hub.i18n import LANGUAGE_NAMES, translate

PORT = 8787
BG = "#0d1214"
SURFACE = "#151c1f"
SURFACE_2 = "#1d262a"
BORDER = "#2b373c"
TEXT = "#edf3f2"
MUTED = "#91a09f"
ACCENT = "#43c590"
ACCENT_DARK = "#092319"
DANGER = "#d96b70"
UI_FONT = "Segoe UI" if sys.platform == "win32" else "SF Pro Text"
DISPLAY_FONT = "Segoe UI" if sys.platform == "win32" else "SF Pro Display"
MONO_FONT = "Consolas" if sys.platform == "win32" else "SF Mono"

AGENT_LABELS = {
    "codex": "Codex CLI",
    "claude-code": "Claude Code CLI",
    "qoder": "Qoder SDK",
    "qoder-cn": "Qoder CN CLI",
    "kimi": "Kimi Code CLI",
    "hermes": "Hermes",
}

AGENT_NOTE_KEYS = {
    "dry-run": "note_dry_run",
    "codex": "note_codex",
    "claude-code": "note_claude",
    "hermes": "note_hermes",
    "qoder": "note_qoder",
    "qoder-cn": "note_qoder_cn",
    "kimi": "note_kimi",
}


def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def _run_runner(module: str, argv: list[str]) -> int:
    from recording_agent_hub import (
        claude_runner,
        codex_runner,
        kimi_runner,
        qoder_cn_runner,
        qoder_runner,
        streamcap_hook,
    )

    runners: dict[str, Callable[[list[str]], int]] = {
        "recording_agent_hub.claude_runner": claude_runner.main,
        "recording_agent_hub.codex_runner": codex_runner.main,
        "recording_agent_hub.kimi_runner": kimi_runner.main,
        "recording_agent_hub.qoder_runner": qoder_runner.main,
        "recording_agent_hub.qoder_cn_runner": qoder_cn_runner.main,
        "recording_agent_hub.streamcap_hook": streamcap_hook.main,
    }
    target = runners.get(module)
    if not target:
        raise SystemExit(f"Unsupported bundled runner: {module}")
    return target(argv)


def _ensure_config() -> Path:
    if not app.DEFAULT_CONFIG.exists():
        app.write_json(app.DEFAULT_CONFIG, app.default_config())
    return app.DEFAULT_CONFIG


class NativeHubWindow:
    def __init__(self, root: tk.Tk, hub: app.Hub, server: app.ThreadingHTTPServer) -> None:
        self.root, self.hub, self.server = root, hub, server
        self.profile = hub.config["profiles"]["default"]
        self.language = hub.config.get("ui_language", "zh_CN")
        if self.language not in LANGUAGE_NAMES:
            self.language = "en"
        self._refresh_after_id: str | None = None
        root.title("Recording Agent Hub")
        root.minsize(980, 700)
        root.geometry("1120x800")
        root.configure(background=BG)
        root.protocol("WM_DELETE_WINDOW", self.stop_and_exit)
        hub.activation_callback = lambda: root.after(0, self.activate_window)
        self.configure_style()
        self.build()
        self.refresh_now()
        self.schedule_refresh()

    def t(self, key: str, **values: object) -> str:
        return translate(self.language, key, **values)

    def agent_label(self, name: str) -> str:
        return self.t("dry_run") if name == "dry-run" else AGENT_LABELS.get(name, name)

    def agent_note(self, name: str) -> str:
        key = AGENT_NOTE_KEYS.get(name)
        return self.t(key) if key else ""

    def job_status_label(self, status: object) -> str:
        name = str(status)
        return self.t(f"job_{name}") if name in {"queued", "running", "completed", "failed", "cancelled"} else name

    def configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT, font=(UI_FONT, 12))
        style.configure("Surface.TLabel", background=SURFACE, foreground=TEXT)
        style.configure("Title.TLabel", font=(DISPLAY_FONT, 27, "bold"), foreground=TEXT)
        style.configure("Subtitle.TLabel", font=(UI_FONT, 12), foreground=MUTED)
        style.configure("Section.TLabel", font=(UI_FONT, 17, "bold"), foreground=TEXT)
        style.configure("Muted.TLabel", font=(UI_FONT, 11), foreground=MUTED)
        style.configure("Status.TLabel", background=SURFACE, foreground=ACCENT, font=(UI_FONT, 12, "bold"))
        style.configure(
            "TButton",
            background=SURFACE_2,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=SURFACE_2,
            darkcolor=SURFACE_2,
            padding=(13, 8),
            font=(UI_FONT, 11, "bold"),
        )
        style.map("TButton", background=[("active", "#273338"), ("pressed", "#111719")])
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground=ACCENT_DARK,
            bordercolor=ACCENT,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        style.map("Accent.TButton", background=[("active", "#59d6a2"), ("pressed", "#35ad7d")])
        style.configure("Danger.TButton", foreground="#f4b6b9")
        style.configure(
            "TCheckbutton",
            background=BG,
            foreground=TEXT,
            indicatorcolor=SURFACE_2,
            indicatorrelief="flat",
            padding=(4, 4),
        )
        style.map("TCheckbutton", indicatorcolor=[("selected", ACCENT)], foreground=[("active", TEXT)])
        style.configure(
            "TCombobox",
            fieldbackground=SURFACE_2,
            background=SURFACE_2,
            foreground=TEXT,
            arrowcolor=MUTED,
            bordercolor=BORDER,
            padding=(9, 7),
        )
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE_2)], foreground=[("readonly", TEXT)])
        style.configure(
            "TEntry",
            fieldbackground=SURFACE_2,
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor=BORDER,
            padding=(10, 8),
        )
        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 12))
        style.configure(
            "TNotebook.Tab",
            background=SURFACE,
            foreground=MUTED,
            padding=(18, 10),
            borderwidth=0,
            font=(UI_FONT, 11, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", SURFACE_2), ("active", "#202b2f")],
            foreground=[("selected", TEXT), ("active", TEXT)],
        )
        style.configure(
            "Treeview",
            background=SURFACE,
            fieldbackground=SURFACE,
            foreground=TEXT,
            bordercolor=BORDER,
            rowheight=34,
            font=(UI_FONT, 11),
        )
        style.map("Treeview", background=[("selected", "#245342")], foreground=[("selected", TEXT)])
        style.configure(
            "Treeview.Heading",
            background=SURFACE_2,
            foreground=MUTED,
            bordercolor=BORDER,
            relief="flat",
            padding=(8, 9),
            font=(UI_FONT, 10, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", "#263237")])
        style.configure("TSeparator", background=BORDER)
        style.configure(
            "TLabelframe",
            background=BG,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure("TLabelframe.Label", background=BG, foreground=MUTED, font=(UI_FONT, 10, "bold"))

    def build(self) -> None:
        selected_tab = self.notebook.index(self.notebook.select()) if hasattr(self, "notebook") else 0
        draft = None
        if hasattr(self, "agent_var"):
            draft = (self.agent_var.get(), self.workspace_var.get(), self.enabled_var.get())
        for child in self.root.winfo_children():
            child.destroy()

        outer = ttk.Frame(self.root, padding=(26, 22, 26, 24))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        title_area = ttk.Frame(header)
        title_area.pack(side="left", fill="x", expand=True)
        ttk.Label(title_area, text=self.t("app_name"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_area, text=self.t("subtitle"), style="Subtitle.TLabel").pack(anchor="w", pady=(3, 0))

        language_area = ttk.Frame(header)
        language_area.pack(side="right", anchor="ne")
        ttk.Label(language_area, text=f"v{__version__}", style="Muted.TLabel").pack(anchor="e", pady=(0, 5))
        ttk.Label(language_area, text=self.t("language"), style="Muted.TLabel").pack(anchor="e", pady=(0, 4))
        self.language_var = tk.StringVar(value=LANGUAGE_NAMES[self.language])
        self.language_combo = ttk.Combobox(
            language_area,
            state="readonly",
            width=16,
            textvariable=self.language_var,
            values=list(LANGUAGE_NAMES.values()),
        )
        self.language_combo.pack(anchor="e")
        self.language_combo.bind("<<ComboboxSelected>>", self.change_language)

        status_bar = ttk.Frame(outer, style="Surface.TFrame", padding=(16, 12))
        status_bar.pack(fill="x", pady=(20, 18))
        self.state = ttk.Label(status_bar, style="Status.TLabel")
        self.state.pack(side="left", fill="x", expand=True)
        self.pause_button = ttk.Button(status_bar, command=self.toggle_pause)
        self.pause_button.pack(side="right")
        ttk.Button(status_bar, text=self.t("stop"), command=self.stop_and_exit, style="Danger.TButton").pack(side="right", padx=(0, 8))

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        self.setup_tab = ttk.Frame(self.notebook, padding=(4, 18, 4, 0))
        self.jobs_tab = ttk.Frame(self.notebook, padding=(4, 18, 4, 0))
        self.test_tab = ttk.Frame(self.notebook, padding=(4, 18, 4, 0))
        self.memory_tab = ttk.Frame(self.notebook, padding=(4, 18, 4, 0))
        self.agent_tab = ttk.Frame(self.notebook, padding=(4, 18, 4, 0))
        self.notebook.add(self.setup_tab, text=self.t("tab_setup"))
        self.notebook.add(self.jobs_tab, text=self.t("tab_jobs"))
        self.notebook.add(self.test_tab, text=self.t("tab_test"))
        self.notebook.add(self.memory_tab, text=self.t("tab_memory"))
        self.notebook.add(self.agent_tab, text=self.t("tab_agents"))
        self.build_setup(draft)
        self.build_jobs()
        self.build_test()
        self.build_memories()
        self.build_agents()
        self.notebook.select(min(selected_tab, 4))

    def section_intro(self, parent: ttk.Frame, title: str, description: str) -> None:
        ttk.Label(parent, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(parent, text=description, style="Muted.TLabel", wraplength=860).pack(anchor="w", pady=(4, 16))

    def build_setup(self, draft: tuple[str, str, bool] | None = None) -> None:
        tab = self.setup_tab
        self.section_intro(tab, self.t("setup_title"), self.t("setup_desc"))
        form = ttk.Frame(tab)
        form.pack(fill="x")
        ttk.Label(form, text=self.t("use_agent"), style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        agent_name = draft[0] if draft else self.profile["agent"]
        workspace = draft[1] if draft else self.profile.get("agent_workspace", "")
        enabled = draft[2] if draft else bool(self.hub.config["agents"][agent_name].get("enabled"))
        self.agent_var = tk.StringVar(value=agent_name)
        self.agent_combo = ttk.Combobox(
            form,
            state="readonly",
            textvariable=self.agent_var,
            values=list(self.hub.config["agents"]),
            width=31,
        )
        self.agent_combo.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.agent_combo.bind("<<ComboboxSelected>>", self.agent_changed)
        self.enabled_var = tk.BooleanVar(value=enabled)
        ttk.Checkbutton(form, text=self.t("enable_agent"), variable=self.enabled_var).grid(row=1, column=1, sticky="w", padx=(14, 0))

        ttk.Label(form, text=self.t("workspace"), style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(18, 0))
        self.workspace_var = tk.StringVar(value=workspace)
        self.workspace_combo = ttk.Combobox(form, textvariable=self.workspace_var)
        self.workspace_combo.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        ttk.Button(form, text=self.t("auto_detect"), command=self.scan_workspaces).grid(row=3, column=1, padx=(10, 0), pady=(5, 0))
        ttk.Button(form, text=self.t("choose_folder"), command=self.choose_workspace).grid(row=3, column=2, padx=(8, 0), pady=(5, 0))
        ttk.Button(form, text=self.t("save_settings"), command=self.save_settings, style="Accent.TButton").grid(row=4, column=0, sticky="w", pady=(15, 0))
        form.columnconfigure(0, weight=1)

        ttk.Separator(tab).pack(fill="x", pady=24)
        ttk.Label(tab, text=self.t("streamcap_title"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(tab, text=self.t("streamcap_desc"), style="Muted.TLabel", wraplength=860).pack(anchor="w", pady=(4, 12))
        command_row = ttk.Frame(tab)
        command_row.pack(fill="x")
        self.command_var = tk.StringVar(value=self.streamcap_command())
        ttk.Entry(command_row, textvariable=self.command_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(command_row, text=self.t("copy_command"), command=self.copy_command).pack(side="left", padx=(10, 0))
        self.setup_message = ttk.Label(tab, style="Muted.TLabel")
        self.setup_message.pack(anchor="w", pady=(12, 0))

    def build_jobs(self) -> None:
        self.section_intro(self.jobs_tab, self.t("jobs_title"), self.t("jobs_desc"))
        columns = ("status", "agent", "source", "created", "result")
        table = ttk.Frame(self.jobs_tab)
        table.pack(fill="both", expand=True)
        self.jobs_tree = ttk.Treeview(table, columns=columns, show="headings", height=9)
        headings = (
            ("status", self.t("status"), 120),
            ("agent", "Agent", 120),
            ("source", self.t("source"), 420),
            ("created", self.t("created"), 170),
            ("result", self.t("result"), 160),
        )
        for name, label, width in headings:
            self.jobs_tree.heading(name, text=label)
            self.jobs_tree.column(name, width=width, anchor="w")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.jobs_tree.yview)
        self.jobs_tree.configure(yscrollcommand=scrollbar.set)
        self.jobs_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.jobs_tree.bind("<<TreeviewSelect>>", lambda _event: self.show_selected_job())

        toolbar = ttk.Frame(self.jobs_tab)
        toolbar.pack(fill="x", pady=(12, 0))
        actions = (
            ("refresh", self.refresh_jobs, None),
            ("retry", self.retry_selected, "Accent.TButton"),
            ("cancel", self.cancel_selected, "Danger.TButton"),
            ("open_source", lambda: self.open_selected("source_path"), None),
            ("open_output", lambda: self.open_selected("output_path"), None),
            ("open_log", lambda: self.open_selected("log_path"), None),
        )
        for index, (key, command, style) in enumerate(actions):
            ttk.Button(toolbar, text=self.t(key), command=command, style=style or "TButton").pack(side="left", padx=(0 if index == 0 else 7, 0))

        details = ttk.LabelFrame(self.jobs_tab, text=self.t("job_details"), padding=10)
        details.pack(fill="both", expand=True, pady=(12, 0))
        self.job_details = tk.Text(
            details,
            height=7,
            wrap="word",
            state="disabled",
            background=SURFACE,
            foreground=TEXT,
            insertbackground=TEXT,
            selectbackground="#245342",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=8,
            font=(MONO_FONT, 10),
        )
        self.job_details.pack(fill="both", expand=True)

    def build_test(self) -> None:
        self.section_intro(self.test_tab, self.t("test_title"), self.t("test_desc"))
        row = ttk.Frame(self.test_tab)
        row.pack(fill="x")
        self.sample_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.sample_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=self.t("choose_video"), command=self.choose_sample).pack(side="left", padx=(10, 0))
        ttk.Button(self.test_tab, text=self.t("run_test"), command=self.test_trigger, style="Accent.TButton").pack(anchor="w", pady=(14, 0))
        self.test_message = ttk.Label(self.test_tab, style="Muted.TLabel")
        self.test_message.pack(anchor="w", pady=(12, 0))

    def build_agents(self) -> None:
        self.section_intro(self.agent_tab, self.t("agents_title"), self.t("agents_desc"))
        columns = ("agent", "available", "enabled", "details")
        self.agents_tree = ttk.Treeview(self.agent_tab, columns=columns, show="headings", height=12)
        headings = (
            ("agent", "Agent", 190),
            ("available", self.t("local_status"), 180),
            ("enabled", self.t("enabled"), 100),
            ("details", self.t("details"), 500),
        )
        for name, label, width in headings:
            self.agents_tree.heading(name, text=label)
            self.agents_tree.column(name, width=width, anchor="w")
        self.agents_tree.pack(fill="both", expand=True)

    def build_memories(self) -> None:
        self.section_intro(self.memory_tab, self.t("memory_title"), self.t("memory_desc"))
        columns = ("name", "agent", "workspace", "saved")
        self.memory_tree = ttk.Treeview(self.memory_tab, columns=columns, show="headings", height=13)
        headings = (
            ("name", self.t("memory_name"), 220),
            ("agent", "Agent", 150),
            ("workspace", self.t("workspace"), 480),
            ("saved", self.t("saved"), 170),
        )
        for name, label, width in headings:
            self.memory_tree.heading(name, text=label)
            self.memory_tree.column(name, width=width, anchor="w")
        self.memory_tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(self.memory_tab)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text=self.t("use_memory"), command=self.use_selected_memory, style="Accent.TButton").pack(side="left")
        ttk.Button(buttons, text=self.t("refresh"), command=self.refresh_memories).pack(side="left", padx=(8, 0))

    def change_language(self, _event: object = None) -> None:
        reverse = {label: code for code, label in LANGUAGE_NAMES.items()}
        language = reverse.get(self.language_var.get(), "en")
        if language == self.language:
            return
        self.language = language
        self.hub.config["ui_language"] = language
        self.hub.save_config()
        self.build()
        self.refresh_now()

    def choose_workspace(self) -> None:
        selected = filedialog.askdirectory(title=self.t("dialog_workspace"))
        if selected:
            self.workspace_var.set(selected)

    def agent_changed(self, _event: object = None) -> None:
        definition = self.hub.config["agents"].get(self.agent_var.get(), {})
        self.enabled_var.set(bool(definition.get("enabled")))
        self.scan_workspaces()

    def scan_workspaces(self) -> None:
        candidates = app.discover_workspace_candidates(self.agent_var.get(), self.hub.config)
        self.workspace_combo.configure(values=candidates)
        if candidates and self.workspace_var.get() not in candidates:
            self.workspace_var.set(candidates[0])
        self.setup_message.configure(text=self.t("msg_scan", count=len(candidates)), foreground=ACCENT)

    def choose_sample(self) -> None:
        selected = filedialog.askopenfilename(
            title=self.t("dialog_video"),
            filetypes=[(self.t("video_files"), "*.mp4 *.mov *.mkv *.flv *.m4v"), (self.t("all_files"), "*.*")],
        )
        if selected:
            self.sample_var.set(selected)

    def streamcap_command(self) -> str:
        return app.streamcap_hook_command(server=f"http://127.0.0.1:{PORT}", profile="default")

    def copy_command(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.command_var.get())
        self.setup_message.configure(text=self.t("msg_copy"), foreground=ACCENT)

    def save_settings(self) -> None:
        workspace = Path(self.workspace_var.get()).expanduser()
        agent_name = self.agent_var.get()
        if not workspace.is_dir():
            self.setup_message.configure(text=self.t("msg_workspace_invalid"), foreground=DANGER)
            return
        self.profile["agent"] = agent_name
        self.profile["agent_workspace"] = str(workspace.resolve())
        self.hub.config["agents"][agent_name]["enabled"] = self.enabled_var.get()
        self.hub.save_config()
        memory = app.save_workspace_memory("", agent_name, workspace, self.enabled_var.get())
        self.setup_message.configure(text=self.t("msg_saved", name=memory.name), foreground=ACCENT)
        self.refresh_agents()
        self.refresh_memories()

    def toggle_pause(self) -> None:
        self.hub.set_paused(not self.hub.paused)
        self.refresh_state()

    def test_trigger(self) -> None:
        try:
            job = self.hub.submit(Path(self.sample_var.get()).expanduser(), "default", connection_test=True)
        except Exception as exc:
            self.test_message.configure(text=str(exc), foreground=DANGER)
            return
        self.test_message.configure(text=self.t("msg_test", job_id=job["id"]), foreground=ACCENT)
        self.refresh_jobs()

    def retry_selected(self) -> None:
        selection = self.jobs_tree.selection()
        if selection and self.hub.store.retry(selection[0]):
            self.hub._wake.set()
        self.refresh_jobs()

    def selected_job(self) -> dict[str, object] | None:
        selection = self.jobs_tree.selection()
        return self.hub.store.get(selection[0]) if selection else None

    def cancel_selected(self) -> None:
        job = self.selected_job()
        if job and self.hub.cancel(str(job["id"])):
            self.refresh_jobs()

    def open_selected(self, field: str) -> None:
        job = self.selected_job()
        if not job:
            return
        path = Path(str(job.get(field, "")))
        if field == "output_path" and not path.exists():
            path = path.parent
        if path.exists():
            open_path(path)

    def show_selected_job(self) -> None:
        job = self.selected_job()
        lines: list[str] = []
        if job:
            status = self.job_status_label(job["status"])
            lines.extend(
                [
                    f"{self.t('detail_status')}: {status}    {self.t('detail_attempts')}: {job.get('attempt_count', 0)}",
                    f"{self.t('detail_source')}: {job['source_path']}",
                    f"{self.t('detail_output')}: {job['output_path']}",
                    f"{self.t('detail_error')}: {job.get('error') or '-'}",
                    "",
                ]
            )
            log_path = Path(str(job.get("log_path", "")))
            if log_path.is_file():
                try:
                    lines.extend(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-120:])
                except OSError as exc:
                    lines.append(self.t("log_error", error=exc))
        self.job_details.configure(state="normal")
        self.job_details.delete("1.0", "end")
        self.job_details.insert("1.0", "\n".join(lines))
        self.job_details.configure(state="disabled")

    def refresh_state(self) -> None:
        if self.hub.paused:
            self.state.configure(text="●  " + self.t("status_paused"), foreground="#e5b95e")
            self.pause_button.configure(text=self.t("resume"))
        else:
            recovered = self.t("status_recovered", count=self.hub.recovered_jobs) if self.hub.recovered_jobs else ""
            self.state.configure(text="●  " + self.t("status_running") + recovered, foreground=ACCENT)
            self.pause_button.configure(text=self.t("pause"))

    def refresh_jobs(self) -> None:
        selection = self.jobs_tree.selection()
        for item in self.jobs_tree.get_children():
            self.jobs_tree.delete(item)
        for job in self.hub.store.list():
            result = job.get("error") or (self.t("job_completed") if job["status"] == "completed" else "")
            self.jobs_tree.insert(
                "",
                "end",
                iid=job["id"],
                values=(
                    self.job_status_label(job["status"]),
                    self.agent_label(job["agent"]),
                    job["source_path"],
                    job["created_at"].replace("T", " "),
                    result,
                ),
            )
        if selection and self.jobs_tree.exists(selection[0]):
            self.jobs_tree.selection_set(selection[0])
        self.show_selected_job()

    def refresh_agents(self) -> None:
        diagnostics = app.agent_diagnostics()
        for item in self.agents_tree.get_children():
            self.agents_tree.delete(item)
        for name, definition in self.hub.config["agents"].items():
            available = self.t("ready") if diagnostics.get(name) or name in {"dry-run", "hermes"} else self.t("missing")
            self.agents_tree.insert(
                "",
                "end",
                values=(
                    self.agent_label(name),
                    available,
                    self.t("yes") if definition.get("enabled") else self.t("no"),
                    self.agent_note(name),
                ),
            )

    def refresh_memories(self) -> None:
        self.memories_by_path = {memory["path"]: memory for memory in app.list_workspace_memories()}
        for item in self.memory_tree.get_children():
            self.memory_tree.delete(item)
        for path, memory in self.memories_by_path.items():
            self.memory_tree.insert(
                "",
                "end",
                iid=path,
                values=(
                    memory["name"],
                    self.agent_label(memory["agent"]),
                    memory["agent_workspace"],
                    memory.get("saved_at", "").replace("T", " "),
                ),
            )

    def use_selected_memory(self) -> None:
        selection = self.memory_tree.selection()
        if not selection:
            return
        memory = self.memories_by_path.get(selection[0])
        if not memory:
            return
        self.agent_var.set(memory["agent"])
        self.workspace_var.set(memory["agent_workspace"])
        self.enabled_var.set(bool(memory.get("enabled")))
        self.profile["agent"] = memory["agent"]
        self.profile["agent_workspace"] = memory["agent_workspace"]
        self.hub.config["agents"][memory["agent"]]["enabled"] = bool(memory.get("enabled"))
        self.hub.save_config()
        self.setup_message.configure(text=self.t("msg_memory", name=memory["name"]), foreground=ACCENT)
        self.refresh_agents()

    def refresh_now(self) -> None:
        self.refresh_state()
        self.refresh_jobs()
        self.refresh_agents()
        self.refresh_memories()

    def schedule_refresh(self) -> None:
        if self.root.winfo_exists():
            self.refresh_now()
            self._refresh_after_id = self.root.after(2500, self.schedule_refresh)

    def stop_and_exit(self) -> None:
        if not messagebox.askyesno(self.t("stop_title"), self.t("stop_confirm")):
            return
        if self._refresh_after_id:
            self.root.after_cancel(self._refresh_after_id)
        self.hub.shutdown()
        self.server.shutdown()
        self.server.server_close()
        self.root.destroy()

    def activate_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()


def _activate_running_app() -> bool:
    try:
        request = Request(
            f"http://127.0.0.1:{PORT}/api/activate",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def open_path(path: Path) -> None:
    """Open a file or directory with the platform's default application."""
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["/usr/bin/open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _run_desktop() -> int:
    root = tk.Tk()
    config_path = _ensure_config()
    config = app.load_config(config_path)
    language = config.get("ui_language", "zh_CN")
    if _port_in_use():
        root.withdraw()
        if not _activate_running_app():
            messagebox.showerror(
                translate(language, "port_error_title"),
                translate(language, "port_error", port=PORT),
            )
        root.destroy()
        return 0
    hub = app.Hub(config, config_path)
    server = app.ThreadingHTTPServer(("127.0.0.1", PORT), app.web_handler(hub))
    threading.Thread(target=server.serve_forever, daemon=True, name="recording-agent-web").start()
    NativeHubWindow(root, hub, server)
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) >= 2 and arguments[0] == "--runner":
        return _run_runner(arguments[1], arguments[2:])
    return _run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
