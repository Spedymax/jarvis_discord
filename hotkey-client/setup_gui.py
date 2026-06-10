"""GUI setup wizard (customtkinter). All decisions live in setup_core."""
from __future__ import annotations

import customtkinter as ctk
from pynput import keyboard

import setup_core

ACCENT = "#ff9933"  # цвет карточки now-playing


class SetupWindow(ctk.CTk):
    def __init__(self, initial: dict | None = None) -> None:
        super().__init__()
        self.title("Jarvis Hotkeys — настройка")
        self.geometry("600x680")
        self.minsize(520, 560)

        self.result: dict | None = None
        self._token: str | None = None
        self._webhook: str | None = None
        self._sounds: list[str] = []
        self._bindings: dict[str, str] = {}
        self._listener: keyboard.Listener | None = None
        self._mods: set[str] = set()
        self._pending_combo: str | None = None

        self._build_code_section()
        self._build_bindings_section()
        self._build_footer()

        if initial:
            self._token = initial.get("token")
            self._webhook = initial.get("webhook_url")
            self._bindings = dict(initial.get("bindings") or {})
            self.code_hint.configure(
                text="Конфиг найден — setup-код нужен только для замены токена."
            )
            self._refresh_rows()
            self._refresh_save_state()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI construction ----------

    def _build_code_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(frame, text="Setup-код из /hotkey setup",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 2))
        self.code_entry = ctk.CTkEntry(frame, placeholder_text="JHK1.…")
        self.code_entry.pack(fill="x", padx=12, pady=4)
        self.code_entry.bind("<KeyRelease>", lambda _e: self._on_code_change())
        self.code_hint = ctk.CTkLabel(frame, text="Вставь код целиком.",
                                      text_color="gray")
        self.code_hint.pack(anchor="w", padx=12, pady=(0, 10))

    def _build_bindings_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=16, pady=8)
        ctk.CTkLabel(frame, text="Биндинги",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 2))

        add_row = ctk.CTkFrame(frame, fg_color="transparent")
        add_row.pack(fill="x", padx=12, pady=4)
        self.capture_btn = ctk.CTkButton(add_row, text="⌨ Нажми комбинацию",
                                         command=self._start_capture, width=190)
        self.capture_btn.pack(side="left")
        self.combo_label = ctk.CTkLabel(add_row, text="—", width=140)
        self.combo_label.pack(side="left", padx=8)
        self.sound_box = ctk.CTkComboBox(add_row, values=[""], width=150)
        self.sound_box.set("")
        self.sound_box.pack(side="left", padx=8)
        self.add_btn = ctk.CTkButton(add_row, text="Добавить", width=90,
                                     command=self._add_binding, state="disabled")
        self.add_btn.pack(side="left")

        self.warn_label = ctk.CTkLabel(frame, text="", text_color="#e0c341")
        self.warn_label.pack(anchor="w", padx=12)

        self.rows_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.rows_frame.pack(fill="both", expand=True, padx=8, pady=(4, 10))

    def _build_footer(self) -> None:
        self.save_btn = ctk.CTkButton(
            self, text="Сохранить и запустить", fg_color=ACCENT,
            text_color="black", state="disabled", command=self._save)
        self.save_btn.pack(fill="x", padx=16, pady=(4, 16))

    # ---------- setup code ----------

    def _on_code_change(self) -> None:
        code = self.code_entry.get().strip()
        if not code:
            self.code_hint.configure(text="Вставь код целиком.", text_color="gray")
            return
        try:
            data = setup_core.decode_setup_code(code)
        except setup_core.SetupCodeError as exc:
            self.code_hint.configure(text=str(exc), text_color="#e05341")
            return
        self._token = data["token"]
        self._webhook = data["webhook_url"]
        self._sounds = data["sounds"]
        self.sound_box.configure(values=self._sounds or ["(звуков нет — впиши имя)"])
        self.code_hint.configure(text=f"✓ Код принят. Звуков: {len(self._sounds)}",
                                 text_color="#41e07a")
        self._refresh_save_state()

    # ---------- combo capture ----------

    def _start_capture(self) -> None:
        if self._listener is not None:
            return
        self._mods = set()
        self.capture_btn.configure(text="Жми клавиши… (Esc — отмена)")

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
                return
            combo = setup_core.combo_to_string(frozenset(self._mods), value)
            self.after(0, self._finish_capture, combo)

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def _finish_capture(self, combo: str | None) -> None:
        if self._listener is None:
            return  # второй queued-колбэк после уже обработанного захвата
        self._listener.stop()
        self._listener = None
        self.capture_btn.configure(text="⌨ Нажми комбинацию")
        if combo is None:
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
        sound = self.sound_box.get().strip()
        if not self._pending_combo or not sound or sound.startswith("("):
            self.warn_label.configure(text="⚠ Выбери звук.")
            return
        if " " in sound:
            # протокол вебхука разделяет токен и имя первым пробелом —
            # имя с пробелом бот не зарезолвит
            self.warn_label.configure(text="⚠ В имени звука не может быть пробелов.")
            return
        self._bindings[self._pending_combo] = sound
        self._pending_combo = None
        self.combo_label.configure(text="—")
        self.add_btn.configure(state="disabled")
        self.warn_label.configure(text="")
        self._refresh_rows()
        self._refresh_save_state()

    def _remove_binding(self, combo: str) -> None:
        self._bindings.pop(combo, None)
        self._refresh_rows()
        self._refresh_save_state()

    def _refresh_rows(self) -> None:
        for child in self.rows_frame.winfo_children():
            child.destroy()
        for combo, sound in self._bindings.items():
            row = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{combo}  →  {sound}", anchor="w").pack(
                side="left", padx=4, fill="x", expand=True)
            ctk.CTkButton(row, text="✕", width=30, fg_color="transparent",
                          hover_color="#7a2020",
                          command=lambda c=combo: self._remove_binding(c)).pack(
                side="right", padx=4)

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
