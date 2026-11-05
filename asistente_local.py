import base64
import io
import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
import keyboard
from groq import Groq
import pystray
from PIL import Image, ImageDraw, ImageGrab
from winotify import Notification


APP_NAME = "AURA"
MODEL = "qwen/qwen3.8-27b"
DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "AuraAsistente"
HISTORY_FILE = DATA_DIR / "historial.txt"
BG = "#090D18"
SURFACE = "#101727"
CARD = "#141E31"
CARD_ALT = "#19253B"
ACCENT = "#8978FF"
ACCENT_HOVER = "#7564EF"
TEXT = "#F3F5FC"
MUTED = "#8B98B3"
GREEN = "#52D6A1"
RED = "#F17E91"

PROMPT = """Eres AURA, asistente experto principalmente en matemáticas y física. Responde en español y analiza cuidadosamente la captura antes de concluir.

LEE primero el enunciado, los datos, símbolos, unidades, diagramas y opciones tal como aparecen. Conserva signos, exponentes, decimales y unidades; si algo no se distingue, dilo y no lo inventes. Determina qué se pide y qué información es relevante.

MATEMÁTICAS: elige la definición, regla o método apropiado; muestra los pasos algebraicos sin saltos que cambien el resultado; cuida signos, paréntesis, exponentes, dominio y unidades; sustituye o deriva/integraliza de nuevo como comprobación cuando aplique.

FÍSICA, con prioridad en mecánica: identifica sistema, modelo físico, incógnita y datos con unidades. Distingue escalares de vectores y conceptos cercanos (posición/desplazamiento/distancia, rapidez/velocidad, masa/peso). Declara eje, marco de referencia y convención de signos. Selecciona la ley correcta y sus condiciones (cinemática, leyes de Newton y diagrama de fuerzas, trabajo/energía, cantidad de movimiento/impulso, movimiento circular, estática o rotación); descompón vectores en componentes cuando corresponda. Convierte unidades de forma explícita, resuelve primero simbólicamente y después sustituye valores. Comprueba consistencia dimensional, dirección/signo y si la magnitud es físicamente razonable. No mezcles fórmulas de modelos incompatibles.

En otras materias, adapta el razonamiento al tema y usa evidencia visible. Si hay alternativas, evalúa cada una frente a la pregunta, descarta las falsas y elige solo la que responde exactamente; detecta negaciones como NO, EXCEPTO o FALSO y si pide una o varias. No elijas por palabras parecidas. Si ninguna opción es correcta, indícalo. Ejemplo de control conceptual: el abecedario está compuesto por letras; los números no pertenecen a él; las letras se clasifican en vocales y consonantes.

Si falta un dato imprescindible, explica qué supuesto usas o qué dato falta. Entrega una respuesta final directa y una explicación verificable, concisa pero suficiente para revisar el procedimiento. Devuelve únicamente JSON válido con estas cuatro claves: enunciado, respuesta, explicacion y procedimiento. No repitas innecesariamente la explicación en procedimiento."""


def api_key():
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg:
            return winreg.QueryValueEx(reg, "GROQ_API_KEY")[0]
    except (OSError, ImportError):
        return ""


def save_key(key):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as reg:
        winreg.SetValueEx(reg, "GROQ_API_KEY", 0, winreg.REG_SZ, key)
    os.environ["GROQ_API_KEY"] = key


def parse_json(raw):
    raw = (raw or "").strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.I | re.S)
    if match:
        raw = match.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    return json.loads(raw)


def request_is_output_token_limit(error):
    message = str(error).lower()
    return "429" in message and (
        "output tokens per minute" in message
        or "otpm" in message
        or ("request too large" in message and "output" in message)
    )


def request_completion(client, messages):
    # El límite solicitado cuenta para la cuota OTPM aunque la respuesta real sea menor.
    # Si la cuota disponible no admite el primer tamaño, vuelve a probar más corto.
    for token_budget in (1400, 1000, 700, 480):
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=token_budget,
                response_format={"type": "json_object"},
            )
        except Exception as error:
            if not request_is_output_token_limit(error):
                raise
    raise RuntimeError(
        "Groq sigue rechazando la consulta por su límite de tokens de salida, incluso con una respuesta breve. "
        "Espera un minuto y vuelve a intentarlo; la cuota depende de tu plan y del uso reciente de la API."
    )


def analyze():
    key = api_key()
    if not key:
        raise RuntimeError("Agrega tu clave de Groq en Ajustes para empezar.")
    shot = ImageGrab.grab().convert("RGB")
    stream = io.BytesIO()
    shot.save(stream, format="JPEG", quality=88, optimize=True)
    encoded = base64.b64encode(stream.getvalue()).decode("ascii")
    client = Groq(api_key=key)
    messages = [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
        ]}]
    response = request_completion(client, messages)
    data = parse_json(response.choices[0].message.content)
    answer = str(data.get("respuesta") or "No se identificó una respuesta clara.").strip()
    explanation = str(data.get("explicacion") or data.get("procedimiento") or "Sin explicación.").strip()
    question = str(data.get("enunciado") or "No identificado").strip()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n{'─' * 48}\n{datetime.now():%Y-%m-%d %H:%M}\n{question}\nRespuesta: {answer}\n{explanation}\n")
    return question, answer, explanation


class AuraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title("AURA — Asistente visual")
        self.geometry("1120x760")
        self.minsize(960, 660)
        self.configure(fg_color=BG)
        self.busy = False
        self.active = False
        self.hotkey_id = None
        self.tray_icon = None
        self.last_result = None
        self.current_page = "home"
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self._build_shell()
        self.show_page("home")
        if not api_key():
            self.after(500, lambda: self.show_page("settings"))

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=236, corner_radius=0, fg_color=SURFACE)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=22, pady=(28, 34))
        logo = ctk.CTkCanvas(brand, width=44, height=44, bg=SURFACE, highlightthickness=0)
        logo.pack(side="left", padx=(0, 12))
        logo.create_oval(2, 2, 42, 42, fill=ACCENT, outline="")
        logo.create_text(22, 21, text="A", fill="white", font=("Segoe UI", 22, "bold"))
        ctk.CTkLabel(brand, text="AURA", font=ctk.CTkFont("Segoe UI", 19, "bold"), text_color=TEXT).pack(anchor="w", pady=(1, 0))
        ctk.CTkLabel(brand, text="ASISTENTE VISUAL", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=MUTED).pack(anchor="w")

        ctk.CTkLabel(self.sidebar, text="ESPACIO DE TRABAJO", font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color="#66738C", anchor="w").pack(fill="x", padx=22, pady=(0, 10))
        self.home_nav = self._nav_button(self.sidebar, "⌂", "Inicio", lambda: self.show_page("home"))
        self.home_nav.pack(fill="x", padx=12, pady=3)
        self.settings_nav = self._nav_button(self.sidebar, "⚙", "Ajustes", lambda: self.show_page("settings"))
        self.settings_nav.pack(fill="x", padx=12, pady=3)

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=18, pady=20)
        ctk.CTkFrame(bottom, height=1, fg_color="#243049").pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(bottom, text="AURA  ·  PERSONAL", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=MUTED).pack(anchor="w")
        ctk.CTkLabel(bottom, text="Tu pantalla, a un atajo.", font=ctk.CTkFont("Segoe UI", 10), text_color="#697792").pack(anchor="w", pady=(4, 0))

        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

    def _nav_button(self, parent, icon, text, command):
        return ctk.CTkButton(parent, text=f"   {icon}     {text}", command=command, anchor="w",
                             height=44, corner_radius=10, fg_color="transparent", hover_color=CARD_ALT,
                             text_color=MUTED, font=ctk.CTkFont("Segoe UI", 12))

    def _clear_main(self):
        for child in self.main.winfo_children():
            child.destroy()

    def show_page(self, page):
        self.current_page = page
        self.home_nav.configure(fg_color=CARD_ALT if page == "home" else "transparent",
                                text_color=TEXT if page == "home" else MUTED)
        self.settings_nav.configure(fg_color=CARD_ALT if page == "settings" else "transparent",
                                    text_color=TEXT if page == "settings" else MUTED)
        self._clear_main()
        if page == "home":
            self._build_home()
        else:
            self._build_settings()

    def _page_header(self, title, subtitle):
        head = ctk.CTkFrame(self.main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=42, pady=(34, 20))
        ctk.CTkLabel(head, text=title, font=ctk.CTkFont("Segoe UI", 25, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(head, text=subtitle, font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED).pack(anchor="w", pady=(5, 0))

    def _build_home(self):
        self._page_header("Tu escritorio, entendido.", "Activa AURA y analiza cualquier contenido con un solo atajo.")
        content = ctk.CTkFrame(self.main, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=42, pady=(0, 32))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        control = ctk.CTkFrame(content, fg_color=CARD, corner_radius=18, border_width=1, border_color="#202D45")
        control.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        row = ctk.CTkFrame(control, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=22)
        statebox = ctk.CTkFrame(row, fg_color="transparent")
        statebox.pack(side="left", fill="x", expand=True)
        self.state_title = ctk.CTkLabel(statebox, text="AURA está desactivada", font=ctk.CTkFont("Segoe UI", 15, "bold"), text_color=TEXT)
        self.state_title.pack(anchor="w")
        self.state_detail = ctk.CTkLabel(statebox, text="Actívala para habilitar Ctrl + Q. Cierra esta ventana para dejar AURA en segundo plano.", font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED)
        self.state_detail.pack(anchor="w", pady=(5, 0))
        self.toggle = ctk.CTkSwitch(row, text="", width=48, command=self.toggle_active,
                                   progress_color=ACCENT, button_color="#F3F5FC", button_hover_color="white")
        self.toggle.pack(side="right", padx=(16, 3))
        if self.active:
            self.toggle.select()
        self._update_active_ui()

        result_card = ctk.CTkFrame(content, fg_color=CARD, corner_radius=18, border_width=1, border_color="#202D45")
        result_card.grid(row=1, column=0, sticky="nsew")
        result_card.grid_columnconfigure(0, weight=1)
        result_card.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(result_card, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(21, 0))
        ctk.CTkLabel(bar, text="ÚLTIMO ANÁLISIS", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color="#A99CFF").pack(side="left")
        self.result_status = ctk.CTkLabel(bar, text="EN ESPERA", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=MUTED)
        self.result_status.pack(side="right")
        self.question_label = ctk.CTkLabel(result_card, text="Cuando analices tu pantalla, verás aquí el resultado.",
                                            font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=TEXT,
                                            anchor="w", justify="left", wraplength=740)
        self.question_label.grid(row=1, column=0, sticky="ew", padx=24, pady=(22, 12))
        self.answer_box = ctk.CTkTextbox(result_card, height=100, fg_color=CARD_ALT, text_color="#C7BEFF",
                                         border_width=0, corner_radius=12, font=ctk.CTkFont("Segoe UI", 15, "bold"), wrap="word")
        self.answer_box.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 13))
        self.answer_box.insert("1.0", "Tu respuesta aparecerá aquí")
        self.answer_box.configure(state="disabled")
        ctk.CTkLabel(result_card, text="EXPLICACIÓN", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=MUTED).grid(row=3, column=0, sticky="w", padx=24, pady=(5, 7))
        self.explanation_box = ctk.CTkTextbox(result_card, height=125, fg_color="transparent", text_color="#C6CDDC",
                                              border_width=0, corner_radius=8, font=ctk.CTkFont("Segoe UI", 11), wrap="word")
        self.explanation_box.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 15))
        self.explanation_box.insert("1.0", "La explicación detallada se mostrará aquí.")
        self.explanation_box.configure(state="disabled")
        footer = ctk.CTkFrame(result_card, fg_color="transparent")
        footer.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 20))
        self.status_label = ctk.CTkLabel(footer, text="Listo cuando tú lo estés.", font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED)
        self.status_label.pack(side="left")
        self.copy_btn = ctk.CTkButton(footer, text="Copiar respuesta", width=130, height=32, corner_radius=8,
                                      fg_color=CARD_ALT, hover_color="#263653", text_color=TEXT,
                                      font=ctk.CTkFont("Segoe UI", 10), command=self.copy_answer)
        self.copy_btn.pack(side="right")
        if self.last_result:
            question, answer, explanation = self.last_result
            self.question_label.configure(text=question)
            self._set_text(self.answer_box, answer)
            self._set_text(self.explanation_box, explanation)

    def _build_settings(self):
        self._page_header("Ajustes", "Conecta tu cuenta y personaliza cómo usas AURA.")
        panel = ctk.CTkFrame(self.main, fg_color=CARD, corner_radius=18, border_width=1, border_color="#202D45")
        panel.grid(row=1, column=0, sticky="new", padx=42, pady=(0, 25))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Conexión con Groq", font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=24, pady=(24, 5))
        ctk.CTkLabel(panel, text="Tu clave se guarda en tu perfil de Windows y no se muestra en Inicio.",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 20))
        ctk.CTkLabel(panel, text="CLAVE API", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color="#A99CFF").grid(row=2, column=0, sticky="w", padx=24, pady=(0, 8))
        keyrow = ctk.CTkFrame(panel, fg_color="transparent")
        keyrow.grid(row=3, column=0, sticky="ew", padx=24)
        keyrow.grid_columnconfigure(0, weight=1)
        self.key_entry = ctk.CTkEntry(keyrow, placeholder_text="Pega aquí tu clave de Groq", show="•", height=42,
                                      fg_color="#0C1321", border_color="#293750", corner_radius=10,
                                      font=ctk.CTkFont("Segoe UI", 11))
        self.key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        if api_key():
            self.key_entry.insert(0, api_key())
        self.reveal_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(keyrow, text="Mostrar", variable=self.reveal_var, command=self.toggle_key_visibility,
                        checkbox_width=17, checkbox_height=17, font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED,
                        fg_color=ACCENT, hover_color=ACCENT_HOVER).grid(row=0, column=1, padx=(0, 12))
        ctk.CTkButton(keyrow, text="Guardar clave", command=self.store_key, width=135, height=42, corner_radius=10,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, font=ctk.CTkFont("Segoe UI", 11, "bold")).grid(row=0, column=2)
        self.key_status = ctk.CTkLabel(panel, text="Clave guardada" if api_key() else "Aún no has agregado una clave.",
                                       font=ctk.CTkFont("Segoe UI", 10), text_color=GREEN if api_key() else MUTED)
        self.key_status.grid(row=4, column=0, sticky="w", padx=24, pady=(12, 24))

        hotkey = ctk.CTkFrame(self.main, fg_color=CARD, corner_radius=18, border_width=1, border_color="#202D45")
        hotkey.grid(row=2, column=0, sticky="ew", padx=42, pady=(0, 24))
        ctk.CTkLabel(hotkey, text="Atajo de análisis", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=TEXT).pack(anchor="w", padx=24, pady=(19, 3))
        ctk.CTkLabel(hotkey, text="Ctrl + Q   ·   Se habilita o deshabilita desde Inicio.",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).pack(anchor="w", padx=24, pady=(0, 19))

    def toggle_key_visibility(self):
        self.key_entry.configure(show="" if self.reveal_var.get() else "•")

    def store_key(self):
        key = self.key_entry.get().strip()
        if not key:
            self.key_status.configure(text="Pega una clave antes de guardar.", text_color=RED)
            return
        try:
            save_key(key)
            self.key_status.configure(text="Clave guardada en este perfil de Windows.", text_color=GREEN)
        except Exception as exc:
            self.key_status.configure(text=f"No se pudo guardar: {exc}", text_color=RED)

    def toggle_active(self):
        if self.active:
            self.deactivate()
        else:
            if not api_key():
                if self.current_page == "home":
                    self.toggle.deselect()
                self.show_window()
                self.show_page("settings")
                self.key_status.configure(text="Primero agrega tu clave de Groq.", text_color=RED)
                return
            try:
                self.hotkey_id = keyboard.add_hotkey("ctrl+q", lambda: self.after(0, self.start_analysis), suppress=False)
                self.active = True
                if hasattr(self, "toggle"):
                    self.toggle.select()
                self._update_active_ui()
                self.notify("AURA está activa", "Pulsa Ctrl + Q para analizar la pantalla.")
                self._update_tray_menu()
            except Exception as exc:
                if hasattr(self, "toggle"):
                    self.toggle.deselect()
                messagebox.showerror("No se pudo activar", f"No se pudo registrar Ctrl + Q.\n\n{exc}", parent=self)

    def deactivate(self):
        if self.hotkey_id is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_id)
            except (KeyError, ValueError):
                pass
            self.hotkey_id = None
        self.active = False
        if self.current_page == "home" and hasattr(self, "toggle"):
            self.toggle.deselect()
        self._update_active_ui()
        self._update_tray_menu()

    def _update_active_ui(self):
        if self.current_page != "home" or not hasattr(self, "state_title"):
            return
        if self.active:
            self.state_title.configure(text="AURA está activa", text_color=GREEN)
            self.state_detail.configure(text="Atajo global activo. Puedes cerrar esta ventana; AURA seguirá en segundo plano.")
        else:
            self.state_title.configure(text="AURA está desactivada", text_color=TEXT)
            self.state_detail.configure(text="Actívala para habilitar Ctrl + Q. Cierra esta ventana para dejar AURA en segundo plano.")

    def start_analysis(self):
        if self.busy:
            return
        if not api_key():
            self.show_window()
            self.show_page("settings")
            self.key_status.configure(text="Agrega tu clave de Groq para analizar.", text_color=RED)
            return
        if self.current_page != "home":
            self.show_page("home")
        self.busy = True
        self.status_label.configure(text="Capturando pantalla…", text_color="#F2C879")
        self.result_status.configure(text="ANALIZANDO", text_color="#F2C879")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            result = analyze()
            self.after(0, lambda: self._show_result(result))
        except Exception as exc:
            self.after(0, lambda err=str(exc): self._show_error(err))

    def _set_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _show_result(self, result):
        question, answer, explanation = result
        self.last_result = result
        if self.current_page != "home":
            self.show_page("home")
        self.question_label.configure(text=question)
        self._set_text(self.answer_box, answer)
        self._set_text(self.explanation_box, explanation)
        self.status_label.configure(text="Respuesta lista · Guardada en el historial.", text_color=GREEN)
        self.result_status.configure(text="COMPLETADO", text_color=GREEN)
        self.notify("AURA · Respuesta lista", answer)
        self.busy = False

    def _show_error(self, error):
        if self.current_page != "home":
            self.show_page("home")
        self.status_label.configure(text="No se pudo completar el análisis.", text_color=RED)
        self.result_status.configure(text="ERROR", text_color=RED)
        self.notify("AURA · Error de análisis", error[:220])
        self.busy = False

    def notify(self, title, text):
        try:
            Notification(app_id="AURA — Asistente visual", title=title, msg=text[:500]).show()
        except Exception:
            pass

    def copy_answer(self):
        answer = self.answer_box.get("1.0", "end").strip()
        if answer and answer != "Tu respuesta aparecerá aquí":
            self.clipboard_clear()
            self.clipboard_append(answer)
            self.status_label.configure(text="Respuesta copiada al portapapeles.", text_color=GREEN)

    def _make_tray_image(self):
        image = Image.new("RGBA", (64, 64), "#090D18")
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, 60, 60), fill="#8978FF")
        draw.polygon([(32, 13), (49, 51), (40, 51), (36, 42), (28, 42), (24, 51), (15, 51)], fill="white")
        return image

    def _ensure_tray(self):
        if self.tray_icon is not None:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Abrir AURA", self._tray_open, default=True),
            pystray.MenuItem(lambda _item: "Desactivar Ctrl + Q" if self.active else "Activar Ctrl + Q",
                             self._tray_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir de AURA", self._tray_exit),
        )
        self.tray_icon = pystray.Icon("AURA", self._make_tray_image(), "AURA — Asistente visual", menu)
        self.tray_icon.run_detached()

    def _update_tray_menu(self):
        if self.tray_icon is not None:
            self.tray_icon.update_menu()

    def _tray_open(self, _icon=None, _item=None):
        self.after(0, self.show_window)

    def _tray_toggle(self, _icon=None, _item=None):
        self.after(0, self.toggle_active)

    def _tray_exit(self, _icon=None, _item=None):
        self.after(0, self.exit_app)

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide_to_tray(self):
        self._ensure_tray()
        self.withdraw()

    def exit_app(self):
        self.deactivate()
        if self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None
        self.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    AuraApp().mainloop()
