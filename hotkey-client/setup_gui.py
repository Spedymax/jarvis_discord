"""GUI setup wizard (customtkinter). All decisions live in setup_core."""
from __future__ import annotations

import threading

import customtkinter as ctk
from pynput import keyboard

import setup_core
import soundlist

# Палитра Discord (выбрана в visual companion, спека 2026-06-12)
BG = "#313338"
CARD = "#2b2d31"
INPUT = "#1e1f22"
BTN = "#4e5058"
BTN_HOVER = "#6d6f78"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
GREEN = "#23a559"
GREEN_BG = "#1e3329"
YELLOW = "#f0b232"
YELLOW_BG = "#3a3225"
RED = "#da373c"
RED_BG = "#42252a"
KBD = "#949cf7"
TEXT = "#dbdee1"
MUTED = "#949ba4"
ROW = "#35373c"
ROW_HOVER = "#3f4248"


class SetupWindow(ctk.CTk):
    def __init__(self, initial: dict | None = None) -> None:
        super().__init__()
        self.configure(fg_color=BG)
        self._mono = ctk.CTkFont(family="Consolas", size=12)

        self.title("Jarvis Hotkeys — настройка")
        self.geometry("720x680")
        self.minsize(640, 560)

        self.result: dict | None = None
        self._token: str | None = None
        self._webhook: str | None = None
        self._sounds: list[str] = []
        self._bindings: dict[str, str] = {}
        self._listener: keyboard.Listener | None = None
        self._mods: set[str] = set()
        self._pending_combo: str | None = None
        self._fetching = False
        self._hide_job = None

        self._build_code_section()
        self._build_constructor_section()
        self._build_bindings_list_section()
        self._build_footer()
        self._refresh_rows()  # счётчик и пустое состояние с первого кадра

        if initial:
            self._token = initial.get("token")
            self._webhook = initial.get("webhook_url")
            self._bindings = dict(initial.get("bindings") or {})
            self.code_hint.configure(
                text="Конфиг найден — setup-код нужен только для замены токена.",
                text_color=MUTED,
            )
            self._refresh_rows()
            self._refresh_save_state()
            if self._token and self._webhook:
                self.refresh_btn.configure(state="normal")
                self._refresh_sounds()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI construction ----------

    def _build_code_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        frame.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(frame, text="SETUP-КОД", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 2))
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 4))
        self.code_entry = ctk.CTkEntry(row, placeholder_text="JHK1.…",
                                       fg_color=INPUT, border_color=INPUT,
                                       text_color=TEXT)
        self.code_entry.pack(side="left", fill="x", expand=True)
        self.code_entry.bind("<KeyRelease>", lambda _e: self._on_code_change())
        self.status_badge = ctk.CTkLabel(row, text=" — ", text_color=MUTED,
                                         fg_color=INPUT, corner_radius=10,
                                         font=ctk.CTkFont(size=11))
        self.status_badge.pack(side="left", padx=(8, 0))
        self.code_hint = ctk.CTkLabel(frame, text="Вставь код целиком.",
                                      text_color=MUTED)
        self.code_hint.pack(anchor="w", padx=12, pady=(0, 10))

    def _set_badge(self, text: str, kind: str) -> None:
        """kind: 'muted' | 'ok' | 'warn'."""
        fg, tc = {
            "muted": (INPUT, MUTED),
            "ok": (GREEN_BG, GREEN),
            "warn": (YELLOW_BG, YELLOW),
        }[kind]
        self.status_badge.configure(text=f" {text} ", fg_color=fg, text_color=tc)

    def _build_constructor_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(frame, text="НОВЫЙ БИНДИНГ", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 2))
        add_row = ctk.CTkFrame(frame, fg_color="transparent")
        add_row.pack(fill="x", padx=12, pady=4)
        self.capture_btn = ctk.CTkButton(add_row, text="⌨ Захват", width=110,
                                         fg_color=BTN, hover_color=BTN_HOVER,
                                         command=self._start_capture)
        self.capture_btn.pack(side="left")
        self.combo_label = ctk.CTkLabel(add_row, text="—", width=160,
                                        font=self._mono, text_color=KBD,
                                        fg_color=INPUT, corner_radius=4)
        self.combo_label.pack(side="left", padx=8)
        self.sound_entry = ctk.CTkEntry(add_row, placeholder_text="🔍 звук…",
                                        fg_color=INPUT, border_color=INPUT,
                                        text_color=TEXT)
        self.sound_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.sound_entry.bind("<KeyRelease>", lambda _e: self._update_suggestions())
        self.sound_entry.bind("<FocusIn>", lambda _e: self._update_suggestions())
        # отложенно: клик по подсказке должен успеть сработать до сворачивания
        self.sound_entry.bind("<FocusOut>", lambda _e: self._schedule_hide())
        self.sound_entry.bind("<Escape>", lambda _e: self._hide_suggestions())
        self.refresh_btn = ctk.CTkButton(add_row, text="⟳", width=32,
                                         fg_color=BTN, hover_color=BTN_HOVER,
                                         command=self._refresh_sounds,
                                         state="disabled")
        self.refresh_btn.pack(side="left", padx=(0, 8))
        self.add_btn = ctk.CTkButton(add_row, text="Добавить", width=90,
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     command=self._add_binding, state="disabled")
        self.add_btn.pack(side="left")

        self.suggest_frame = ctk.CTkFrame(frame, fg_color=INPUT, corner_radius=6)
        # pack по требованию в _update_suggestions (before=warn_label)

        self.warn_label = ctk.CTkLabel(frame, text="", text_color=YELLOW)
        self.warn_label.pack(anchor="w", padx=12, pady=(0, 8))

    def _build_bindings_list_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=16, pady=8)
        self.bindings_header = ctk.CTkLabel(
            frame, text="БИНДИНГИ · 0", text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold"))
        self.bindings_header.pack(anchor="w", padx=12, pady=(10, 2))
        self.rows_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.rows_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    # ---------- sound search ----------

    def _update_suggestions(self) -> None:
        query = self.sound_entry.get().strip()
        items: list[str] = []
        if not query:
            items.append(setup_core.STOP_LABEL)
        items += setup_core.filter_sounds(query, self._sounds)
        for child in self.suggest_frame.winfo_children():
            child.destroy()
        if not items:
            self._hide_suggestions()
            return
        for name in items:
            ctk.CTkButton(
                self.suggest_frame, text=name, anchor="w", height=26,
                fg_color="transparent", hover_color=ROW_HOVER, text_color=TEXT,
                command=lambda n=name: self._pick_suggestion(n),
            ).pack(fill="x", padx=4, pady=1)
        if not self.suggest_frame.winfo_ismapped():
            self.suggest_frame.pack(fill="x", padx=12, pady=(0, 4),
                                    before=self.warn_label)

    def _schedule_hide(self) -> None:
        self._cancel_hide()
        self._hide_job = self.after(350, self._hide_suggestions)

    def _cancel_hide(self) -> None:
        if self._hide_job is not None:
            self.after_cancel(self._hide_job)
            self._hide_job = None

    def _hide_suggestions(self) -> None:
        self._hide_job = None
        self.suggest_frame.pack_forget()

    def _pick_suggestion(self, name: str) -> None:
        self._cancel_hide()
        self.sound_entry.delete(0, "end")
        self.sound_entry.insert(0, name)
        self._hide_suggestions()

    # ---------- setup code ----------

    def _on_code_change(self) -> None:
        code = self.code_entry.get().strip()
        if not code:
            self.code_hint.configure(text="Вставь код целиком.", text_color=MUTED)
            return
        try:
            data = setup_core.decode_setup_code(code)
        except setup_core.SetupCodeError as exc:
            self.code_hint.configure(text=str(exc), text_color=RED)
            return
        self._token = data["token"]
        self._webhook = data["webhook_url"]
        self._sounds = data["sounds"]
        self._refresh_save_state()
        self.refresh_btn.configure(state="normal")
        self._refresh_sounds()

    # ---------- live sound list ----------

    def _refresh_sounds(self) -> None:
        if self._fetching or not (self._token and self._webhook):
            return
        self._fetching = True
        self.refresh_btn.configure(state="disabled")
        self._set_badge("…", "muted")
        self.code_hint.configure(text="Загружаю список звуков…", text_color=MUTED)
        token, webhook = self._token, self._webhook

        def worker() -> None:
            try:
                names = soundlist.fetch_sounds(webhook, token)
                self.after(0, self._apply_fetched_sounds, names, token)
            except Exception:
                pass  # окно закрыто или fetch неожиданно упал

        threading.Thread(target=worker, daemon=True).start()

    def _apply_fetched_sounds(self, names: list | None, fetch_token: str) -> None:
        self._fetching = False
        if fetch_token != self._token:
            # результат устаревшего запроса (код сменили во время fetch'а) —
            # отбрасываем и перезапрашиваем уже с актуальным токеном
            self._refresh_sounds()
            return
        self.refresh_btn.configure(state="normal")
        if names is None:
            self._set_badge(f"⚠ {len(self._sounds)} из кода", "warn")
            self.code_hint.configure(
                text="Бот не ответил — использую список из setup-кода.",
                text_color=YELLOW,
            )
            return
        self._sounds = names
        self._set_badge(f"✓ Звуков: {len(names)}", "ok")
        self.code_hint.configure(text="", text_color=MUTED)

    # ---------- combo capture ----------

    def _start_capture(self) -> None:
        if self._listener is not None:
            return
        self._mods = set()
        self.capture_btn.configure(text="Esc — отмена")
        self.combo_label.configure(text="…")

        def on_press(key) -> None:
            name = getattr(key, "name", None)
            char = getattr(key, "char", None)
            if name == "esc":
                self.after(0, self._finish_capture, None)
                return
            got = setup_core.classify_key(name, char)
            if got is None:
                return
            kind, value = got
            if kind == "modifier":
                self._mods.add(value)
                self.after(0, self._show_capture_progress, frozenset(self._mods))
                return
            combo = setup_core.combo_to_string(frozenset(self._mods), value)
            self.after(0, self._finish_capture, combo)

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def _show_capture_progress(self, mods: frozenset) -> None:
        if self._listener is None:
            return  # захват уже завершён
        shown = " + ".join(m for m in setup_core.MODIFIER_ORDER if m in mods)
        self.combo_label.configure(text=(shown + " + …") if shown else "…")

    def _finish_capture(self, combo: str | None) -> None:
        if self._listener is None:
            return  # второй queued-колбэк после уже обработанного захвата
        self._listener.stop()
        self._listener = None
        self.capture_btn.configure(text="⌨ Захват")
        if combo is None:
            self.combo_label.configure(text="—")
            return
        try:
            keyboard.HotKey.parse(combo)
        except ValueError:
            self.combo_label.configure(text="—")
            self.warn_label.configure(
                text="⚠ Эта клавиша не подходит для глобального хоткея — попробуй другую.")
            return
        self._pending_combo = combo
        self.combo_label.configure(text=combo)
        self.add_btn.configure(state="normal")
        if setup_core.needs_modifier_warning(combo):
            self.warn_label.configure(
                text="⚠ Без модификаторов — будет срабатывать при обычном вводе.")
        else:
            self.warn_label.configure(text="")

    # ---------- bindings list ----------

    def _add_binding(self) -> None:
        sound = self.sound_entry.get().strip()
        if sound == setup_core.STOP_LABEL:
            sound = setup_core.STOP_COMMAND  # команда содержит пробел — guard ниже не для неё
        else:
            if not sound:
                self.warn_label.configure(text="⚠ Выбери звук.")
                return
            if " " in sound:
                # протокол вебхука разделяет токен и имя первым пробелом —
                # имя с пробелом бот не зарезолвит
                self.warn_label.configure(text="⚠ В имени звука не может быть пробелов.")
                return
        if not self._pending_combo:
            self.warn_label.configure(text="⚠ Сначала нажми комбинацию.")
            return
        self._bindings[self._pending_combo] = sound
        self._pending_combo = None
        self.combo_label.configure(text="—")
        self.add_btn.configure(state="disabled")
        self.warn_label.configure(text="")
        self.sound_entry.delete(0, "end")
        self._hide_suggestions()
        self._refresh_rows()
        self._refresh_save_state()

    def _remove_binding(self, combo: str) -> None:
        self._bindings.pop(combo, None)
        self._refresh_rows()
        self._refresh_save_state()

    def _refresh_rows(self) -> None:
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self.bindings_header.configure(text=f"БИНДИНГИ · {len(self._bindings)}")
        if not self._bindings:
            ctk.CTkLabel(self.rows_frame,
                         text="Пока пусто — захвати комбинацию и выбери звук",
                         text_color=MUTED).pack(pady=18)
            return
        for combo, sound in self._bindings.items():
            shown = setup_core.STOP_LABEL if sound == setup_core.STOP_COMMAND else sound
            row = ctk.CTkFrame(self.rows_frame, fg_color=ROW, corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)
            kbd = ctk.CTkLabel(row, text=f" {combo} ", font=self._mono,
                               text_color=KBD, fg_color=INPUT, corner_radius=4)
            kbd.pack(side="left", padx=(8, 6), pady=5)
            name = ctk.CTkLabel(row, text=shown, anchor="w", text_color=TEXT)
            name.pack(side="left", fill="x", expand=True, pady=5)
            x_btn = ctk.CTkButton(row, text="✕", width=28, fg_color="transparent",
                                  hover_color=RED_BG, text_color=MUTED,
                                  command=lambda c=combo: self._remove_binding(c))
            x_btn.pack(side="right", padx=6)

            def _on_enter(_e, r=row, b=x_btn):
                r.configure(fg_color=ROW_HOVER)
                b.configure(text_color=RED)

            def _on_leave(_e, r=row, b=x_btn):
                r.configure(fg_color=ROW)
                b.configure(text_color=MUTED)

            for w in (row, kbd, name, x_btn):
                w.bind("<Enter>", _on_enter)
                w.bind("<Leave>", _on_leave)

    # ---------- footer ----------

    def _build_footer(self) -> None:
        self.save_btn = ctk.CTkButton(
            self, text="Сохранить и запустить",
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="white",
            state="disabled", command=self._save)
        self.save_btn.pack(fill="x", padx=16, pady=(4, 16))

    # ---------- save / close ----------

    def _refresh_save_state(self) -> None:
        ready = bool(self._token and self._webhook and self._bindings)
        self.save_btn.configure(state="normal" if ready else "disabled")

    def _save(self) -> None:
        self.result = setup_core.make_config(
            self._token, self._webhook, self._bindings)
        self._on_close()

    def _on_close(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self.destroy()


def run_setup_gui(initial: dict | None = None) -> dict | None:
    """Open the wizard; return a config dict or None if cancelled."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    win = SetupWindow(initial)
    win.mainloop()
    return win.result
