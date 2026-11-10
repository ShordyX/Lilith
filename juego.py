from theme_manager import ThemeManager, ThemePalette, get_perla_appdata_dir, enable_win11_effects
import sys
import os

# Forzar codificación UTF-8 global en ejecutable congelado (.exe) antes de cargar librerías
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

import shutil
import time
import ctypes
import ctypes.wintypes
import asyncio
import json
import re
import io
import urllib.request
import urllib.parse
from difflib import SequenceMatcher
import shutil
import time
import ctypes
import asyncio
from PyQt6.QtCore import (
    Qt, QTimer, QRect, QRectF, QPoint, QSize, pyqtSignal, QThread, QBuffer, QIODevice,
    QMutex, QMutexLocker, QWaitCondition
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QPen, QBrush, QIcon, QPixmap, QImage
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QGraphicsDropShadowEffect, QMessageBox
)

# RESOLUCIÓN INTELIGENTE DE IMPORTACIONES DESDE JADE (`__main__`)
try:
    from main import (
        detect_windows_system_theme, set_window_exclude_from_capture, log_message
    )
except (ImportError, ModuleNotFoundError):
    import __main__ as main_mod
    detect_windows_system_theme = getattr(main_mod, "detect_windows_system_theme", lambda: "oscuro")
    set_window_exclude_from_capture = getattr(main_mod, "set_window_exclude_from_capture", lambda hwnd: None)
    log_message = getattr(main_mod, "log_message", print)

def check_is_dark_theme(config_manager=None) -> bool:
    """Detecta con precisión si el tema activo de Jade es oscuro o claro leyendo la configuración o el sistema."""
    if config_manager and hasattr(config_manager, "get"):
        theme_cfg = config_manager.get("theme")
        if theme_cfg == "oscuro":
            return True
        elif theme_cfg == "claro":
            return False

    try:
        import __main__ as main_mod
        if hasattr(main_mod, "detect_windows_system_theme"):
            return main_mod.detect_windows_system_theme() == "oscuro"
    except Exception:
        pass

    if callable(detect_windows_system_theme):
        return detect_windows_system_theme() == "oscuro"

    return True

def make_window_click_through(hwnd: int):
    """Aplica la API nativa WS_EX_TRANSPARENT para que los clics del juego atraviesen la ventana."""
    try:
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_LAYERED = 0x00080000
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
    except Exception as e:
        if callable(log_message):
            log_message(f"Error asignando click-through nativo en juego: {e}")

def capture_screen_region_under_overlay(x: int, y: int, w: int, h: int, overlay_hwnd: int = 0) -> QPixmap:
    """Captura de pantalla ultra-rápida en RAM DEBAJO del cuadro superpuesto con ajuste DPI y soporte DirectX/GDI."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    screen = app.primaryScreen() if app else None
    if not screen:
        print("[JUEGO LOG ERROR] No se detectó pantalla primaria en QApplication.", flush=True)
        return QPixmap()

    dpr = screen.devicePixelRatio()
    px = int(x * dpr)
    py = int(y * dpr)
    pw = int(w * dpr)
    ph = int(h * dpr)

    if pw <= 0 or ph <= 0:
        print(f"[JUEGO LOG ERROR] Dimensiones inválidas de recuadro: {pw}x{ph} px", flush=True)
        return QPixmap()

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # Excluir la ventana únicamente durante la fracción de milisegundo de BitBlt para capturar el juego limpio debajo
    if overlay_hwnd:
        try:
            user32.SetWindowDisplayAffinity(overlay_hwnd, 0x00000011)
        except Exception:
            pass

    hdc_screen = user32.GetDC(0)
    if hdc_screen:
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, pw, ph)
        old_bitmap = gdi32.SelectObject(hdc_mem, hbitmap)

        # 0x40CC0020 = SRCCOPY | CAPTUREBLT (captura directamente el framebuffer acelerado de juegos DirectX/Vulkan)
        gdi32.BitBlt(hdc_mem, 0, 0, pw, ph, hdc_screen, px, py, 0x40CC0020)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', ctypes.c_uint32),
                ('biWidth', ctypes.c_int32),
                ('biHeight', ctypes.c_int32),
                ('biPlanes', ctypes.c_uint16),
                ('biBitCount', ctypes.c_uint16),
                ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32),
                ('biXPelsPerMeter', ctypes.c_int32),
                ('biYPelsPerMeter', ctypes.c_int32),
                ('biClrUsed', ctypes.c_uint32),
                ('biClrImportant', ctypes.c_uint32)
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = pw
        bmi.biHeight = -ph
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buffer_len = pw * ph * 4
        raw_data = bytearray(buffer_len)
        c_buffer = (ctypes.c_char * buffer_len).from_buffer(raw_data)

        gdi32.GetDIBits(hdc_mem, hbitmap, 0, ph, c_buffer, ctypes.byref(bmi), 0)

        gdi32.SelectObject(hdc_mem, old_bitmap)
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        # Restaurar la visibilidad para la grabación de pantalla inmediatamente después de BitBlt (0.05 ms)
        if overlay_hwnd:
            try:
                user32.SetWindowDisplayAffinity(overlay_hwnd, 0x00000000)
            except Exception:
                pass

        qimage = QImage(raw_data, pw, ph, QImage.Format.Format_RGB32).copy()
        if not qimage.isNull() and qimage.width() > 0:
            return QPixmap.fromImage(qimage)

    if overlay_hwnd:
        try:
            user32.SetWindowDisplayAffinity(overlay_hwnd, 0x00000000)
        except Exception:
            pass

    # Fallback si GDI nativo falla
    pixmap = screen.grabWindow(0, px, py, pw, ph)
    return pixmap

def compute_image_fingerprint(qimage: QImage) -> list:
    """Calcula una huella binarizada de alto contraste para aislar texto e ignorar sombras y movimientos del entorno."""
    if qimage.isNull():
        return []

    small = qimage.scaled(
        32, 16,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation
    ).convertToFormat(QImage.Format.Format_Grayscale8)

    ptr = small.bits()
    if ptr is None:
        return []

    ptr.setsize(32 * 16)
    raw_bytes = bytes(ptr)

    # Binarización: se aísla el texto brillante (>150) convirtiendo el entorno y movimiento de fondo en 0
    return [255 if b > 150 else 0 for b in raw_bytes]

def calculate_frame_difference(fp1: list, fp2: list) -> float:
    """Calcula el porcentaje de variación entre dos huellas binarizadas de pantalla."""
    if not fp1 or not fp2 or len(fp1) != len(fp2):
        return 100.0
    diff_sum = sum(abs(a - b) for a, b in zip(fp1, fp2))
    max_possible = len(fp1) * 255.0
    return (diff_sum / max_possible) * 100.0

from difflib import SequenceMatcher

def compute_text_similarity(text1: str, text2: str) -> float:
    """Calcula el porcentaje de similitud entre dos cadenas de texto (0.0 a 1.0)."""
    if not text1 or not text2:
        return 0.0
    t1 = text1.strip().lower()
    t2 = text2.strip().lower()
    if t1 == t2:
        return 1.0
    return SequenceMatcher(None, t1, t2).ratio()

import json

_CURRENT_ACTIVE_PROFILE_NAME = None

def get_game_templates_filepath() -> str:
    """Obtiene la ruta centralizada de almacenamiento de plantillas del modo juego en AppData."""
    try:
        import __main__ as main_mod
        get_jade_appdata_dir = getattr(main_mod, "get_jade_appdata_dir", None)
        if callable(get_jade_appdata_dir):
            return os.path.join(get_jade_appdata_dir(), "game_templates.json")
    except Exception:
        pass
    appdata = os.path.expanduser(r"~\AppData\Roaming\Jade")
    os.makedirs(appdata, exist_ok=True)
    return os.path.join(appdata, "game_templates.json")

_DYNAMIC_GAME_OVERLAYS = []

def load_all_game_profiles() -> dict:
    """Carga el diccionario completo de perfiles de juego desde el archivo JSON."""
    filepath = get_game_templates_filepath()
    default_structure = {
        "active_profile": "Predeterminado",
        "global_hotkey": "Ctrl+Shift+Enter",
        "hotkey_quick_add": "Ctrl+Alt+S",
        "hotkey_quick_clear": "Ctrl+Alt+C",
        "profiles": {
            "Predeterminado": []
        }
    }
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {
                        "active_profile": "Predeterminado",
                        "global_hotkey": "Ctrl+Shift+Enter",
                        "hotkey_quick_add": "Ctrl+Alt+S",
                        "hotkey_quick_clear": "Ctrl+Alt+C",
                        "profiles": {
                            "Predeterminado": data
                        }
                    }
                elif isinstance(data, dict) and "profiles" in data:
                    if "global_hotkey" not in data: data["global_hotkey"] = "Ctrl+Shift+Enter"
                    if "hotkey_quick_add" not in data: data["hotkey_quick_add"] = "Ctrl+Alt+S"
                    if "hotkey_quick_clear" not in data: data["hotkey_quick_clear"] = "Ctrl+Alt+C"
                    return data
        except Exception as e:
            print(f"[JUEGO LOG ERROR CARGAR PERFILES]: {e}", flush=True)
    return default_structure

def save_all_game_profiles(profiles_data: dict):
    """Guarda la estructura completa de perfiles por juego en disco."""
    filepath = get_game_templates_filepath()
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profiles_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[JUEGO LOG ERROR GUARDAR PERFILES]: {e}", flush=True)

def get_game_launch_hotkey() -> str:
    """Obtiene el atajo global para iniciar la traducción en vivo del juego."""
    try:
        appdata_cfg = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
        if os.path.exists(appdata_cfg):
            with open(appdata_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("hotkey_game_mode"):
                    return cfg.get("hotkey_game_mode")
    except Exception:
        pass
    data = load_all_game_profiles()
    return data.get("global_hotkey", "Ctrl+Shift+Enter")

def set_game_launch_hotkey(hotkey_str: str):
    """Guarda el atajo global personalizado para la traducción en vivo."""
    clean_hk = hotkey_str.strip() if hotkey_str and hotkey_str.strip() else "Ctrl+Shift+Enter"
    try:
        appdata_cfg = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
        if os.path.exists(appdata_cfg):
            with open(appdata_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["hotkey_game_mode"] = clean_hk
            with open(appdata_cfg, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[JUEGO LOG ERROR GUARDAR CONFIG HK]: {e}", flush=True)

    data = load_all_game_profiles()
    data["global_hotkey"] = clean_hk
    save_all_game_profiles(data)

def get_game_quick_add_hotkey() -> str:
    """Obtiene el atajo para recortar al vuelo un área de juego sin congelar la imagen."""
    try:
        appdata_cfg = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
        if os.path.exists(appdata_cfg):
            with open(appdata_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("hotkey_game_quick_add"):
                    return cfg.get("hotkey_game_quick_add")
    except Exception:
        pass
    data = load_all_game_profiles()
    return data.get("hotkey_quick_add", "Ctrl+Alt+S")

def set_game_quick_add_hotkey(hotkey_str: str):
    """Guarda el atajo para recortar al vuelo un área de juego."""
    clean_hk = hotkey_str.strip() if hotkey_str and hotkey_str.strip() else "Ctrl+Alt+S"
    try:
        appdata_cfg = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
        if os.path.exists(appdata_cfg):
            with open(appdata_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["hotkey_game_quick_add"] = clean_hk
            with open(appdata_cfg, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
    data = load_all_game_profiles()
    data["hotkey_quick_add"] = clean_hk
    save_all_game_profiles(data)

def get_game_quick_clear_hotkey() -> str:
    """Obtiene el atajo para borrar todos los bloques creados al vuelo."""
    try:
        appdata_cfg = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
        if os.path.exists(appdata_cfg):
            with open(appdata_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("hotkey_game_quick_clear"):
                    return cfg.get("hotkey_game_quick_clear")
    except Exception:
        pass
    data = load_all_game_profiles()
    return data.get("hotkey_quick_clear", "Ctrl+Alt+C")

def set_game_quick_clear_hotkey(hotkey_str: str):
    """Guarda el atajo para borrar todos los bloques creados al vuelo."""
    clean_hk = hotkey_str.strip() if hotkey_str and hotkey_str.strip() else "Ctrl+Alt+C"
    try:
        appdata_cfg = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
        if os.path.exists(appdata_cfg):
            with open(appdata_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["hotkey_game_quick_clear"] = clean_hk
            with open(appdata_cfg, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
    data = load_all_game_profiles()
    data["hotkey_quick_clear"] = clean_hk
    save_all_game_profiles(data)

def get_current_profile_name() -> str:
    """Obtiene el nombre de la plantilla/perfil de juego activa."""
    global _CURRENT_ACTIVE_PROFILE_NAME
    if _CURRENT_ACTIVE_PROFILE_NAME:
        return _CURRENT_ACTIVE_PROFILE_NAME
    data = load_all_game_profiles()
    _CURRENT_ACTIVE_PROFILE_NAME = data.get("active_profile", "Predeterminado")
    return _CURRENT_ACTIVE_PROFILE_NAME

def set_current_profile_name(name: str):
    """Establece la plantilla/perfil de juego activa."""
    global _CURRENT_ACTIVE_PROFILE_NAME
    _CURRENT_ACTIVE_PROFILE_NAME = name
    data = load_all_game_profiles()
    data["active_profile"] = name
    if "profiles" not in data or not isinstance(data["profiles"], dict):
        data["profiles"] = {}
    if name not in data["profiles"]:
        data["profiles"][name] = []
    save_all_game_profiles(data)

def load_saved_game_templates(profile_name: str = None) -> list:
    """Carga los bloques configurados para un perfil de juego específico."""
    data = load_all_game_profiles()
    target_prof = profile_name if profile_name else get_current_profile_name()
    return data.get("profiles", {}).get(target_prof, [])

def save_game_templates_data(templates_list: list, profile_name: str = None):
    """Guarda los bloques para el perfil de juego activo o especificado."""
    data = load_all_game_profiles()
    target_prof = profile_name if profile_name else get_current_profile_name()
    data["active_profile"] = target_prof
    if "profiles" not in data or not isinstance(data["profiles"], dict):
        data["profiles"] = {}
    data["profiles"][target_prof] = templates_list
    save_all_game_profiles(data)

def get_main_capture_tools():
    """Obtiene de forma robusta las herramientas de captura de la app principal (main.py)."""
    try:
        import main
        return getattr(main, "capture_full_desktop", None), getattr(main, "SnippingOverlay", None)
    except Exception:
        pass
    try:
        import __main__ as main_mod
        return getattr(main_mod, "capture_full_desktop", None), getattr(main_mod, "SnippingOverlay", None)
    except Exception:
        pass
    return None, None

def spawn_dynamic_game_block(rect: QRect, from_lang: str = "en", to_lang: str = "es") -> "GameTranslationOverlay":
    """Crea e instancia un bloque de traducción en vivo en tiempo real sin pausar la imagen del juego."""
    global _DYNAMIC_GAME_OVERLAYS
    style = get_default_block_style()
    slot_num = len(_DYNAMIC_GAME_OVERLAYS) + 1
    ov = GameTranslationOverlay(rect, from_lang, to_lang, slot_num, style)
    ov.show()
    _DYNAMIC_GAME_OVERLAYS.append(ov)
    print(f"[LOG JUEGO DINÁMICO] Bloque al vuelo [{slot_num}] creado en ({rect.x()}, {rect.y()}) {rect.width()}x{rect.height()}px", flush=True)
    return ov

def clear_all_dynamic_game_blocks():
    """Elimina y destruye de pantalla todos los bloques de traducción creados al vuelo."""
    global _DYNAMIC_GAME_OVERLAYS
    for ov in _DYNAMIC_GAME_OVERLAYS:
        try:
            if ov is not None:
                ov.close()
                ov.deleteLater()
        except Exception:
            pass
    _DYNAMIC_GAME_OVERLAYS.clear()
    print("[LOG JUEGO DINÁMICO] Todos los bloques al vuelo han sido eliminados de pantalla.", flush=True)

class GameCountdownToast(QWidget):
    """Superposición de conteo regresivo de 3 segundos no bloqueante para cambiar al juego."""
    countdown_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.count = 3
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            w, h = 360, 110
            self.setGeometry(geo.x() + (geo.width() - w) // 2, geo.y() + 40, w, h)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._step_countdown)

    def start_countdown(self):
        self.count = 3
        self.show()
        try:
            hwnd = int(self.winId())
            set_window_exclude_from_capture(hwnd)
        except Exception:
            pass
        self.update()
        self.timer.start()

    def _step_countdown(self):
        self.count -= 1
        if self.count > 0:
            self.update()
        else:
            self.timer.stop()
            self.close()
            self.countdown_finished.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 16.0, 16.0)

        painter.fillPath(path, QColor(15, 18, 24, 235))
        painter.setPen(QPen(QColor(0, 120, 212), 2))
        painter.drawPath(path)

        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
        text_top = "🎮 Enfoca la ventana de tu juego ahora..."
        painter.drawText(QRectF(0, 12, self.width(), 30), Qt.AlignmentFlag.AlignCenter, text_top)

        painter.setFont(QFont("Segoe UI Variable Display", 28, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(96, 205, 255)))
        painter.drawText(QRectF(0, 45, self.width(), 50), Qt.AlignmentFlag.AlignCenter, str(self.count))

_OCR_CORRECTIONS_CACHE = None

def get_ocr_corrections_filepath() -> str:
    """Obtiene la ruta del archivo JSON de corrección de abreviaturas OCR en AppData."""
    try:
        import __main__ as main_mod
        get_jade_appdata_dir = getattr(main_mod, "get_jade_appdata_dir", None)
        if callable(get_jade_appdata_dir):
            return os.path.join(get_jade_appdata_dir(), "ocr_corrections.json")
    except Exception:
        pass
    appdata = os.path.expanduser(r"~\AppData\Roaming\Jade")
    os.makedirs(appdata, exist_ok=True)
    return os.path.join(appdata, "ocr_corrections.json")

def load_ocr_corrections_dict() -> dict:
    """Carga o genera el diccionario JSON de corrección de contracciones y glitcheos OCR en RAM (0ms)."""
    global _OCR_CORRECTIONS_CACHE
    if _OCR_CORRECTIONS_CACHE is not None:
        return _OCR_CORRECTIONS_CACHE

    filepath = get_ocr_corrections_filepath()
    default_rules = {
        "1'11": "I'll", "1'll": "I'll", "I'11": "I'll", "1'1l": "I'll", "1'l1": "I'll", "1 11": "I'll", "1 1l": "I'll",
        "I´Iam": "I'm", "I'Iam": "I'm", "I`Iam": "I'm",
        "I´Il": "I'll", "I´ll": "I'll", "I'Il": "I'll", "I`ll": "I'll", "I`Il": "I'll", "I 1l": "I'll", "I1l": "I'll", "I I": "I'll", "I Il": "I'll", "I ' Il": "I'll",
        "I´m": "I'm", "I`m": "I'm", "I’m": "I'm", "I m": "I'm", "1'm": "I'm", "l'm": "I'm",
        "I´ve": "I've", "I`ve": "I've", "I’ve": "I've", "1've": "I've", "l've": "I've",
        "I´d": "I'd", "I`d": "I'd", "I’d": "I'd", "1'd": "I'd", "l'd": "I'd",
        "you´re": "you're", "you`re": "you're", "you’re": "you're", "you re": "you're",
        "you´ll": "you'll", "you`ll": "you'll", "you’ll": "you'll",
        "you´ve": "you've", "you`ve": "you've", "you’ve": "you've",
        "it´s": "it's", "it`s": "it's", "it’s": "it's", "it s": "it's",
        "he´s": "he's", "he`s": "he's", "he’s": "he's",
        "she´s": "she's", "she`s": "she's", "she’s": "she's",
        "we´re": "we're", "we`re": "we're", "we’re": "we're",
        "we´ll": "we'll", "we`ll": "we'll", "we’ll": "we'll",
        "they´re": "they're", "they`re": "they're", "they’re": "they're",
        "they´ll": "they'll", "they`ll": "they'll", "they’ll": "they'll",
        "don´t": "don't", "don`t": "don't", "don’t": "don't", "don t": "don't",
        "can´t": "can't", "can`t": "can't", "can’t": "can't", "can t": "can't",
        "won´t": "won't", "won`t": "won't", "won’t": "won't",
        "couldn´t": "couldn't", "couldn`t": "couldn't", "couldn’t": "couldn't",
        "wouldn´t": "wouldn't", "wouldn`t": "wouldn't", "wouldn’t": "wouldn't",
        "shouldn´t": "shouldn't", "shouldn`t": "shouldn't", "shouldn’t": "shouldn't",
        "isn´t": "isn't", "isn`t": "isn't", "isn’t": "isn't",
        "aren´t": "aren't", "aren`t": "aren't", "aren’t": "aren't",
        "wasn´t": "wasn't", "wasn`t": "wasn't", "wasn’t": "wasn't",
        "weren´t": "weren't", "weren`t": "weren't", "weren’t": "weren't",
        "hasn´t": "hasn't", "hasn`t": "hasn't", "hasn’t": "hasn't",
        "haven´t": "haven't", "haven`t": "haven't", "haven’t": "haven't",
        "hadn´t": "hadn't", "hadn`t": "hadn't", "hadn’t": "hadn't",
        "that´s": "that's", "that`s": "that's", "that’s": "that's",
        "what´s": "what's", "what`s": "what's", "what’s": "what's",
        "there´s": "there's", "there`s": "there's", "there’s": "there's",
        "who´s": "who's", "who`s": "who's", "who’s": "who's",
        "let´s": "let's", "let`s": "let's", "let’s": "let's"
    }

    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                user_rules = json.load(f)
                if isinstance(user_rules, dict):
                    default_rules.update(user_rules)
        except Exception as e:
            print(f"[LOG OCR CORRECTIONS ERROR CARGAR]: {e}", flush=True)

    # Actualizar archivo JSON en disco con las reglas sincronizadas
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_rules, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[LOG OCR CORRECTIONS GUARDAR ERROR]: {e}", flush=True)

    _OCR_CORRECTIONS_CACHE = default_rules
    return _OCR_CORRECTIONS_CACHE

import re

def clean_exe_mojibake_encoding(text: str) -> str:
    """Corrige automáticamente distorsiones de codificación ANSI/Mojibake producidas por binarios congelados (.exe)."""
    if not text:
        return text
    try:
        bytes_raw = text.encode("latin-1")
        fixed_utf8 = bytes_raw.decode("utf-8")
        if fixed_utf8:
            text = fixed_utf8
    except Exception:
        pass

    replacements = {
        "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú",
        "Ã": "Á", "Ã‰": "É", "Ã": "Í", "Ã“": "Ó", "Ãš": "Ú",
        "Ã±": "ñ", "Ã": "Ñ", "Â¿": "¿", "Â¡": "¡",
        "â€™": "'", "â€“": "-", "â€”": "-", "â€œ": '"', "â€": '"'
    }
    for wrong, right in replacements.items():
        if wrong in text:
            text = text.replace(wrong, right)
    return text

def preprocess_and_fix_english_ocr(text: str) -> str:
    """Preprocesa y corrige de forma limpia comillas, contracciones y glitcheos de OCR en inglés."""
    if not text:
        return text

    fixed = clean_exe_mojibake_encoding(text)

    # 1. Normalizar comillas y acentos ruidosos a comilla simple estándar
    fixed = fixed.replace("´", "'").replace("`", "'").replace("’", "'").replace("‘", "'").replace("“", "'").replace("”", "'")

    # 2. Corregir cualquier variación de I'll donde I/l se lean como 1 (ej. "1'11", "1'll", "I'11", "1 11")
    fixed = re.sub(r"\b[I1l]['\s|]*[1lI]{2}\b", "I'll", fixed)
    fixed = re.sub(r"\b[I1l]['\s|]*am\b", "I'm", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\b[I1l]['\s|]*m\b", "I'm", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\b[I1l]['\s|]*ve\b", "I've", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\b[I1l]['\s|]*d\b", "I'd", fixed, flags=re.IGNORECASE)

    # 3. Normalizar apóstrofes separados por kerning/espaciado ancho en juegos (ej. "there ' s" -> "there's")
    fixed = re.sub(r"\b([a-zA-Z]+)\s*'\s*s\b", r"\1's", fixed)
    fixed = re.sub(r"\b([a-zA-Z]+)\s*'\s*re\b", r"\1're", fixed)
    fixed = re.sub(r"\b([a-zA-Z]+)\s*'\s*ve\b", r"\1've", fixed)
    fixed = re.sub(r"\b([a-zA-Z]+)\s*'\s*ll\b", r"\1'll", fixed)

    # 4. Autocorrección de confusiones de OCR por fuentes delgadas con kerning ancho
    fixed = re.sub(r"\b(v[a4]rnished|f[i1la|]{1,2}rnished|farnished|flnished|finlshed)\b", "finished", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\ba[I1l|]ready\b", "already", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\ba[I1l|]so\b", "also", fixed, flags=re.IGNORECASE)

    # 5. Mapeo discreto por diccionario dinámico JSON (ocr_corrections.json)
    rules = load_ocr_corrections_dict()
    for wrong, correct in rules.items():
        if wrong in fixed:
            fixed = fixed.replace(wrong, correct)

    return fixed

def enhance_game_subtitle_image(crop_image: QImage) -> QImage:
    """Normaliza y limpia cualquier tipo de subtítulo de juego de forma nítida sin deformar fuentes delgadas."""
    if crop_image.isNull():
        return crop_image

    try:
        # 1. Escalado a 3x manteniendo bordes vectoriales nítidos
        w = crop_image.width()
        h = crop_image.height()
        if w < 1000 or h < 300:
            crop_image = crop_image.scaled(
                w * 3,
                h * 3,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

        # 2. Convertir a Escala de Grises 8-bit
        gray = crop_image.convertToFormat(QImage.Format.Format_Grayscale8)
        gw = gray.width()
        gh = gray.height()
        stride = gray.bytesPerLine()

        ptr = gray.bits()
        if ptr is None:
            return crop_image

        ptr.setsize(stride * gh)
        buf = bytearray(ptr)

        if not buf or len(buf) < stride * gh:
            return crop_image

        # 3. Determinar el brillo promedio del fondo muestreando los bordes
        sample_rows = max(1, gh // 10)
        sample_bytes = stride * sample_rows
        top_bg = buf[:sample_bytes]
        bottom_bg = buf[-sample_bytes:]
        avg_bg = (sum(top_bg) + sum(bottom_bg)) / (len(top_bg) + len(bottom_bg)) if (top_bg and bottom_bg) else 128.0

        is_dark_bg = avg_bg < 128.0

        # 4. Invertir si el fondo es oscuro para que el texto quede siempre oscuro sobre fondo claro
        if is_dark_bg:
            for y in range(gh):
                row_start = y * stride
                for x in range(gw):
                    idx = row_start + x
                    buf[idx] = 255 - buf[idx]

        # 5. Estiramiento de contraste suave
        min_v = 255
        max_v = 0
        for y in range(gh):
            row_start = y * stride
            for x in range(gw):
                v = buf[row_start + x]
                if v < min_v: min_v = v
                if v > max_v: max_v = v

        diff = max_v - min_v
        if diff > 10:
            for y in range(gh):
                row_start = y * stride
                for x in range(gw):
                    idx = row_start + x
                    buf[idx] = int(((buf[idx] - min_v) / diff) * 255)

        res_img = QImage(bytes(buf), gw, gh, stride, QImage.Format.Format_Grayscale8).copy()
        return res_img if not res_img.isNull() else crop_image

    except Exception as e:
        print(f"[LOG ENHANCE ERROR]: {e}", flush=True)
        return crop_image

class GameOcrTransWorker(QThread):
    """Hilo trabajador persistente único con watchdog anti-cuelgues y tiempos límites rígidos."""
    result_ready = pyqtSignal(str, str)

    def __init__(self, from_lang: str = "en", to_lang: str = "es", parent=None):
        super().__init__(parent)
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.running = True
        self.busy = False
        self.request_time = 0.0
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.pending_image = None

    def request_ocr(self, crop_image: QImage):
        """Recibe un nuevo fotograma y despierta al hilo único en segundo plano."""
        with QMutexLocker(self.mutex):
            self.pending_image = crop_image
            self.busy = True
            self.request_time = time.time()
            self.condition.wakeOne()

    def is_busy(self) -> bool:
        with QMutexLocker(self.mutex):
            if self.busy and (time.time() - self.request_time) > 3.0:
                print("[LOG WORKER WARN] Hilo ocupado por más de 3.0s. Desbloqueando por watchdog anti-cuelgue.", flush=True)
                self.busy = False
            return self.busy

    def stop(self):
        with QMutexLocker(self.mutex):
            self.running = False
            self.condition.wakeOne()
        self.quit()
        self.wait(1000)

    def run(self):
        print(f"[LOG HILO PERSISTENTE-{id(self)}] Hilo iniciado y listo para procesar en segundo plano.", flush=True)
        com_inited = False
        try:
            ctypes.windll.ole32.CoInitializeEx(None, 0)
            com_inited = True
        except Exception:
            pass

        while True:
            target_image = None
            with QMutexLocker(self.mutex):
                while self.running and self.pending_image is None:
                    self.condition.wait(self.mutex)
                if not self.running:
                    break
                target_image = self.pending_image
                self.pending_image = None

            if target_image and not target_image.isNull():
                try:
                    ocr_txt, trans_txt = self._process_image_frame(target_image)
                    if self.running:
                        self.result_ready.emit(ocr_txt, trans_txt)
                except Exception as e_run:
                    print(f"[LOG WORKER ERROR EN PROCESO]: {e_run}", flush=True)
                finally:
                    with QMutexLocker(self.mutex):
                        self.busy = False
            else:
                with QMutexLocker(self.mutex):
                    self.busy = False

        if com_inited:
            try:
                ctypes.windll.ole32.CoUninitialize()
            except Exception:
                pass
        print(f"[LOG HILO PERSISTENTE-{id(self)}] Hilo detenido de forma segura.", flush=True)

    def _process_image_frame(self, crop_image: QImage) -> tuple:
        try:
            # Aumentar contraste y binarizar suavemente para aislar texto
            enhanced_img = enhance_game_subtitle_image(crop_image)

            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            enhanced_img.save(buffer, "BMP")
            bytes_data = bytes(buffer.data())
            buffer.close()

            ocr_text = ""

            # 1. PRIORIDAD #1: WinRT OCR (Fuerza el modelo de idioma exacto, ej. 'en-US', en vez de usar el español del PC)
            try:
                import winrt.windows.media.ocr as ocr
                import winrt.windows.graphics.imaging as imaging
                import winrt.windows.storage.streams as streams

                async def _fast_winrt():
                    stream = streams.InMemoryRandomAccessStream()
                    writer = streams.DataWriter(stream)
                    writer.write_bytes(bytes_data)
                    await writer.store_async()
                    stream.seek(0)

                    decoder = await imaging.BitmapDecoder.create_async(stream)
                    software_bitmap = await decoder.get_software_bitmap_async()

                    # Forzar idioma explícito (en-US para inglés) desactivando el modelo en español de Windows
                    win_lang_map = {
                        "en": "en-US", "es": "es-ES", "fr": "fr-FR", "de": "de-DE",
                        "it": "it-IT", "pt": "pt-BR", "ja": "ja-JP", "zh": "zh-Hans-CN",
                        "ru": "ru-RU", "ko": "ko-KR"
                    }
                    target_tag = win_lang_map.get(self.from_lang, "en-US")

                    engine = None
                    try:
                        import winrt.windows.globalization as glob  # type: ignore
                        lang_obj = glob.Language(target_tag)
                        if ocr.OcrEngine.is_language_supported(lang_obj):
                            engine = ocr.OcrEngine.try_create_from_language(lang_obj)
                    except Exception:
                        pass

                    if not engine:
                        engine = ocr.OcrEngine.try_create_from_user_profile_languages()

                    if not engine:
                        return ""

                    ocr_res = await engine.recognize_async(software_bitmap)
                    res_lines = []
                    try:
                        for line in ocr_res.lines:
                            res_lines.append(line.text)
                        txt_res = "\n".join(res_lines)
                    except Exception:
                        txt_res = getattr(ocr_res, "text", "")

                    del ocr_res, software_bitmap, decoder, writer, stream, engine
                    return txt_res

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    ocr_text = loop.run_until_complete(asyncio.wait_for(_fast_winrt(), timeout=2.5))
                except asyncio.TimeoutError:
                    ocr_text = ""
                except Exception:
                    ocr_text = ""
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass
                    del loop

                if ocr_text.strip():
                    print("[LOG OCR] WinRT OK", flush=True)
            except Exception as e_winrt_gen:
                print(f"[LOG OCR ERROR] WinRT general: {e_winrt_gen}", flush=True)

            # 2. PRIORIDAD #2: Fallback a Tesseract OCR si WinRT no devolvió texto
            if not ocr_text or not ocr_text.strip():
                tess_exe = None
                tess_dir = None
                try:
                    import __main__ as main_mod
                    get_jade_appdata_dir = getattr(main_mod, "get_jade_appdata_dir", None)
                    if callable(get_jade_appdata_dir):
                        appdata_bin = os.path.normpath(os.path.join(get_jade_appdata_dir(), "bin", "tesseract.exe"))
                        if os.path.exists(appdata_bin):
                            tess_exe = appdata_bin
                            tess_dir = os.path.normpath(os.path.join(get_jade_appdata_dir(), "bin", "tessdata"))
                except Exception:
                    pass

                if not tess_exe:
                    candidate_paths = [
                        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                        shutil.which("tesseract")
                    ]
                    for cand in candidate_paths:
                        if cand and os.path.exists(cand):
                            tess_exe = os.path.normpath(cand)
                            tess_dir = os.path.normpath(os.path.join(os.path.dirname(cand), "tessdata"))
                            break

                if tess_exe:
                    try:
                        import pytesseract
                        import io
                        from PIL import Image
                        pytesseract.pytesseract.tesseract_cmd = tess_exe

                        tess_lang_map = {
                            "en": "eng", "es": "spa", "fr": "fra", "de": "deu",
                            "it": "ita", "pt": "por", "ja": "jpn", "zh": "chi_sim",
                            "ru": "rus", "ko": "kor"
                        }
                        tess_lang = tess_lang_map.get(self.from_lang, self.from_lang)

                        if tess_dir and os.path.exists(tess_dir):
                            os.environ["TESSDATA_PREFIX"] = tess_dir

                        pil_img = Image.open(io.BytesIO(bytes_data))
                        ocr_text = pytesseract.image_to_string(
                            pil_img,
                            lang=tess_lang,
                            config="--psm 6",
                            timeout=2.5
                        )
                        if ocr_text.strip():
                            print("[LOG OCR] Tesseract Fallback OK", flush=True)
                    except Exception as e_tess:
                        print(f"[LOG OCR WARN] Tesseract: {e_tess}", flush=True)

            clean_ocr = ocr_text.strip() if ocr_text else ""
            if not clean_ocr:
                return ("", "")

            # Limpieza de símbolos basura y bordes de cuadros de diálogo
            lines = [line.strip() for line in clean_ocr.splitlines() if line.strip()]
            cleaned_lines = []
            for line in lines:
                # Quitar líneas de ruido extremadamente cortas o compuestas de bordes/símbolos
                letters_only = re.sub(r"[^a-zA-Z]", "", line)
                if len(letters_only) < 2 and len(line) < 5:
                    continue
                # Descartar símbolos extraños en bordes (como TM», =, c), , 7 tl)
                c_line = re.sub(r"^[^\w\"']+", "", line)
                c_line = re.sub(r"[^\w\"'.!?]+$", "", c_line)
                if c_line.strip():
                    cleaned_lines.append(c_line.strip())

            clean_ocr = "\n".join(cleaned_lines) if cleaned_lines else clean_ocr

            # Normalización de contracciones y glitcheos OCR en inglés
            if self.from_lang == "en":
                clean_ocr = preprocess_and_fix_english_ocr(clean_ocr)

            translated_text = clean_ocr

            # 3. MOTOR DE TRADUCCIÓN HÍBRIDO
            # Intento #1: Motor Neuronal Profesional en línea (Google GTX - Natural y fluida)
            online_success = False
            try:
                import urllib.request
                import urllib.parse
                import json

                url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={self.from_lang}&tl={self.to_lang}&dt=t&q=" + urllib.parse.quote(clean_ocr)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=0.8) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    chunks = [item[0] for item in res_data[0] if item[0]]
                    online_text = "".join(chunks).strip()
                    if online_text:
                        translated_text = online_text
                        online_success = True
                        print(f"[LOG TRADUCCION PROFESIONAL ONLINE] Éxito: '{translated_text}'", flush=True)
            except Exception as e_online:
                print(f"[LOG TRADUCCION ONLINE WARN]: {e_online}. Recurriendo a Argos offline...", flush=True)

            # Intento #2: Fallback Offline (Argos Translate) si no hay conexión
            if not online_success:
                try:
                    import __main__ as main_mod
                    cache = getattr(main_mod, "_ARGOS_TRANSLATION_CACHE", {})
                    cache_key = f"{self.from_lang}_{self.to_lang}"
                    translation_model = cache.get(cache_key)

                    if not translation_model:
                        import argostranslate.translate
                        installed_langs = argostranslate.translate.get_installed_languages()
                        f_obj = next((l for l in installed_langs if l.code == self.from_lang), None)
                        t_obj = next((l for l in installed_langs if l.code == self.to_lang), None)

                        if not (f_obj and t_obj):
                            import argostranslate.package
                            argostranslate.package.update_package_index()
                            available_packages = argostranslate.package.get_available_packages()
                            target_package = next((p for p in available_packages if p.from_code == self.from_lang and p.to_code == self.to_lang), None)
                            if target_package:
                                download_path = target_package.download()
                                argostranslate.package.install_from_path(download_path)
                                installed_langs = argostranslate.translate.get_installed_languages()
                                f_obj = next((l for l in installed_langs if l.code == self.from_lang), None)
                                t_obj = next((l for l in installed_langs if l.code == self.to_lang), None)

                        if f_obj and t_obj:
                            translation_model = f_obj.get_translation(t_obj)
                            if translation_model:
                                cache[cache_key] = translation_model

                    if translation_model:
                        translated_text = translation_model.translate(clean_ocr)
                        print(f"[LOG TRADUCCION OFFLINE ARGOS] Éxito: '{translated_text}'", flush=True)
                except Exception as e_tr:
                    print(f"[LOG TRADUCCION ERROR]: {e_tr}", flush=True)

            return (clean_ocr, translated_text)

        except Exception as e:
            print(f"[LOG TRADUCCION EXCEPCION]: {e}", flush=True)
            return ("", "")

from PyQt6.QtWidgets import (
    QTabWidget, QColorDialog, QSlider, QSpinBox, QCheckBox, QComboBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout
)
import ctypes.wintypes

def get_default_block_style() -> dict:
    """Retorna los valores de estilo predeterminados para los recuadros de traducción."""
    return {
        "font_color": "#60CDFF",
        "font_size": 13,
        "font_bold": True,
        "text_border": True,
        "text_border_color": "#000000",
        "bg_color": "#000000",
        "bg_opacity": 60,
        "box_border_color": "#0078D4",
        "box_border_width": 2
    }

class GameTranslationOverlay(QWidget):
    """Cuadro superpuesto pasivo con transiciones de Fade In/Out y estabilidad continua sin cierres ni cuelgues."""
    def __init__(self, target_rect: QRect, from_lang: str = "en", to_lang: str = "es", slot_num: int = 1, style_config: dict = None, parent=None):
        super().__init__(parent)
        self.target_rect = target_rect
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.slot_num = slot_num
        self.style_config = style_config or get_default_block_style()
        self.last_fingerprint = None
        self.last_ocr_text = ""
        self.last_trans_text = ""
        self.empty_frames_count = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setGeometry(target_rect)

        self.init_ui()
        ThemeManager.get_instance().theme_changed.connect(lambda mode, dark: self.apply_theme(dark))
        self.apply_style_config(self.style_config)

        # Hilo trabajador persistente 100% seguro (sin auto-destrucción interna durante eventos)
        self.worker = GameOcrTransWorker(self.from_lang, self.to_lang)
        self.worker.result_ready.connect(self._on_trans_complete)
        self.worker.start()

        self.loop_timer = QTimer(self)
        self.loop_timer.setInterval(450)
        self.loop_timer.timeout.connect(self.process_live_frame)
        self.loop_timer.start()

        print(f"[LOG OVERLAY BLOQUE {slot_num}] Recuadro con Fade & Estabilidad Continua iniciado en ({target_rect.x()}, {target_rect.y()})", flush=True)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            make_window_click_through(hwnd)
            # Asegurar visibilidad total para que la grabación de video (FFmpeg) capture el recuadro
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000000)
        except Exception as e:
            print(f"[JUEGO LOG EXCEPCION SHOWEVENT]: {e}", flush=True)


    def apply_theme(self, is_dark: bool):
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }}
            QLabel {{
                color: {p['text_primary']};
            }}
        """)
        if hasattr(self, "title_lbl") and self.title_lbl:
            self.title_lbl.setStyleSheet("color: #60CDFF;" if is_dark else "color: #005A9E;")
        if hasattr(self, "tabs") and self.tabs:
            if is_dark:
                self.tabs.setStyleSheet("""
                    QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; background: rgba(20, 24, 32, 0.6); }
                    QTabBar::tab { background: rgba(255, 255, 255, 0.08); color: #CCCCCC; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
                    QTabBar::tab:selected { background: #0078D4; color: white; }
                """)
            else:
                self.tabs.setStyleSheet("""
                    QTabWidget::pane { border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 8px; background: #FFFFFF; }
                    QTabBar::tab { background: rgba(0, 0, 0, 0.06); color: #444444; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
                    QTabBar::tab:selected { background: #0078D4; color: white; }
                """)
        if hasattr(self, "btn_cancel") and self.btn_cancel:
            if is_dark:
                self.btn_cancel.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 8px 16px; font-weight: bold;")
            else:
                self.btn_cancel.setStyleSheet("background-color: rgba(0, 0, 0, 0.06); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 8px; padding: 8px 16px; font-weight: bold;")

        style_edit = "background: rgba(255, 255, 255, 0.1); color: white; border-radius: 6px; padding: 4px; font-weight: bold;" if is_dark else "background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 6px; padding: 4px; font-weight: bold;"
        for ed in ("edit_global_launch", "edit_quick_add", "edit_quick_clear"):
            if hasattr(self, ed) and getattr(self, ed):
                getattr(self, ed).setStyleSheet(style_edit)

        color_lbl = "color: #60CDFF; font-weight: bold;" if is_dark else "color: #005A9E; font-weight: bold;"
        for lbl_name in ("lbl_c1", "lbl_c2", "lbl_c3"):
            if hasattr(self, lbl_name) and getattr(self, lbl_name):
                getattr(self, lbl_name).setStyleSheet(color_lbl)

        if hasattr(self, "lbl_desc") and self.lbl_desc:
            self.lbl_desc.setStyleSheet("color: #A0AAB4;" if is_dark else "color: #595959;")

        if hasattr(self, "table_blocks") and self.table_blocks:
            if is_dark:
                self.table_blocks.setStyleSheet("background-color: rgba(0, 0, 0, 0.3); color: white; gridline-color: rgba(255, 255, 255, 0.1);")
            else:
                self.table_blocks.setStyleSheet("background-color: #FFFFFF; color: #1A1A1A; gridline-color: rgba(0, 0, 0, 0.1);")

            cell_edit_style = "background: rgba(255, 255, 255, 0.1); color: white; border-radius: 4px; padding: 4px;" if is_dark else "background: rgba(0, 0, 0, 0.05); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 4px; padding: 4px;"
            for row in range(self.table_blocks.rowCount()):
                for col in (1, 2):
                    w = self.table_blocks.cellWidget(row, col)
                    if w:
                        w.setStyleSheet(cell_edit_style)

        spin_style = "background: rgba(255, 255, 255, 0.1); color: white; padding: 4px; border-radius: 4px;" if is_dark else "background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); padding: 4px; border-radius: 4px;"
        if hasattr(self, "spin_font_size") and self.spin_font_size:
            self.spin_font_size.setStyleSheet(spin_style)
        if hasattr(self, "spin_border_width") and self.spin_border_width:
            self.spin_border_width.setStyleSheet(spin_style)
        chk_style = "color: white;" if is_dark else "color: #1A1A1A;"
        if hasattr(self, "chk_font_bold") and self.chk_font_bold:
            self.chk_font_bold.setStyleSheet(chk_style)
        if hasattr(self, "chk_text_border") and self.chk_text_border:
            self.chk_text_border.setStyleSheet(chk_style)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.box = QFrame()
        self.box.setObjectName("GameSubBox")

        b_layout = QVBoxLayout(self.box)
        b_layout.setContentsMargins(12, 8, 12, 8)

        self.lbl_subtitle = QLabel(f"🎮 Esperando texto Bloque [{self.slot_num}]...")
        self.lbl_subtitle.setWordWrap(True)
        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        b_layout.addWidget(self.lbl_subtitle, stretch=1)
        layout.addWidget(self.box)

        # Configuración de efecto de opacidad para animación de Fade In / Fade Out
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        self.box_opacity = QGraphicsOpacityEffect(self.box)
        self.box.setGraphicsEffect(self.box_opacity)
        self.box_opacity.setOpacity(1.0)

    def _animate_text_transition(self, new_text: str, font_color: str):
        """Realiza una transición elegante Fade Out (120ms) -> Cambiar Texto -> Fade In (180ms)."""
        try:
            from PyQt6.QtCore import QPropertyAnimation

            self.anim_out = QPropertyAnimation(self.box_opacity, b"opacity")
            self.anim_out.setDuration(120)
            self.anim_out.setStartValue(self.box_opacity.opacity())
            self.anim_out.setEndValue(0.0)

            def _on_fade_out_complete():
                self.lbl_subtitle.setText(new_text)
                self.lbl_subtitle.setStyleSheet(f"color: {font_color}; background: transparent;")

                self.anim_in = QPropertyAnimation(self.box_opacity, b"opacity")
                self.anim_in.setDuration(180)
                self.anim_in.setStartValue(0.0)
                self.anim_in.setEndValue(1.0)
                self.anim_in.start()

            self.anim_out.finished.connect(_on_fade_out_complete)
            self.anim_out.start()
        except Exception:
            self.lbl_subtitle.setText(new_text)
            self.lbl_subtitle.setStyleSheet(f"color: {font_color}; background: transparent;")
            self.box_opacity.setOpacity(1.0)

    def reset_state_ram(self):
        """Reinicia los estados de memoria en RAM de forma instantánea sin tocar ni destruir hilos de C++."""
        self.last_ocr_text = ""
        self.last_trans_text = ""
        self.last_fingerprint = None
        self.empty_frames_count = 0

    def apply_style_config(self, style: dict):
        """Aplica la configuración personalizada de fuente, colores, opacidad y bordes."""
        self.style_config = style
        bg_hex = style.get("bg_color", "#000000")
        opacity_val = float(style.get("bg_opacity", 60)) / 100.0
        border_hex = style.get("box_border_color", "#0078D4")
        border_w = style.get("box_border_width", 2)

        qcol = QColor(bg_hex)
        r, g, b = qcol.red(), qcol.green(), qcol.blue()

        self.box.setStyleSheet(f"""
            QFrame#GameSubBox {{
                background-color: rgba({r}, {g}, {b}, {opacity_val:.2f});
                border: {border_w}px solid {border_hex};
                border-radius: 12px;
            }}
        """)

        font_color = style.get("font_color", "#60CDFF")
        font_size = style.get("font_size", 13)
        font_bold = style.get("font_bold", True)
        weight = QFont.Weight.Bold if font_bold else QFont.Weight.Normal

        self.lbl_subtitle.setFont(QFont("Segoe UI Variable Text", font_size, weight))
        self.lbl_subtitle.setStyleSheet(f"color: {font_color}; background: transparent;")

    def toggle_active_visibility(self) -> bool:
        """Alterna el estado encendido/apagado del bloque reiniciando el estado de memoria."""
        if self.isVisible():
            self.loop_timer.stop()
            self.hide()
            print(f"[LOG OVERLAY BLOQUE {self.slot_num}] Ocultado/Desactivado mediante atajo.", flush=True)
            return False
        else:
            self.reset_state_ram()
            self.show()
            self.loop_timer.start()
            print(f"[LOG OVERLAY BLOQUE {self.slot_num}] Reactivado mediante atajo.", flush=True)
            return True

    def process_live_frame(self):
        if not self.isVisible() or (hasattr(self, "worker") and self.worker and self.worker.is_busy()):
            return

        try:
            hwnd = int(self.winId()) if hasattr(self, "winId") else 0
            crop_pixmap = capture_screen_region_under_overlay(
                self.target_rect.x(), self.target_rect.y(),
                self.target_rect.width(), self.target_rect.height(),
                overlay_hwnd=hwnd
            )

            if crop_pixmap.isNull():
                return

            current_img = crop_pixmap.toImage()
            if current_img.isNull():
                return

            curr_fp = compute_image_fingerprint(current_img)

            # Umbral de 2.2%: absorbe vibraciones de cámara, vegetación y viento sin re-disparar el OCR
            if self.last_fingerprint is not None and self.last_ocr_text:
                delta = calculate_frame_difference(self.last_fingerprint, curr_fp)
                if delta < 2.2:
                    return

            self.pending_fp = curr_fp
            self.worker.request_ocr(current_img)

        except Exception as e:
            print(f"[JUEGO OVERLAY ERROR EN FRAME]: {e}", flush=True)

    def _on_trans_complete(self, ocr_text: str, trans_text: str):
        try:
            clean_ocr = ocr_text.strip() if ocr_text else ""
            clean_trans = trans_text.strip() if trans_text else ""
            font_color = self.style_config.get("font_color", "#60CDFF")

            if clean_trans or clean_ocr:
                display_text = clean_trans if clean_trans else clean_ocr

                # 1. Subtítulo Inicial
                if not self.last_ocr_text:
                    print(f"[LOG OVERLAY BLOQUE {self.slot_num}] Subtítulo inicial: '{display_text}'", flush=True)
                    self._animate_text_transition(display_text, font_color)
                    self.last_ocr_text = clean_ocr
                    self.last_trans_text = display_text
                    if hasattr(self, "pending_fp"):
                        self.last_fingerprint = self.pending_fp
                    self.empty_frames_count = 0
                    return

                # 2. Filtro Anti-Parpadeo (Si la frase es la misma, no se redibuja la UI)
                similarity = compute_text_similarity(clean_ocr, self.last_ocr_text)
                if similarity >= 0.85:
                    self.empty_frames_count = 0
                    return

                # 3. Transición de Frase Suave con Animación Fade In/Out
                print(f"[LOG OVERLAY BLOQUE {self.slot_num}] Transición de frase detectada: '{display_text}'", flush=True)
                self._animate_text_transition(display_text, font_color)
                self.last_ocr_text = clean_ocr
                self.last_trans_text = display_text
                if hasattr(self, "pending_fp"):
                    self.last_fingerprint = self.pending_fp
                self.empty_frames_count = 0

            else:
                self.empty_frames_count += 1
                if self.empty_frames_count >= 4:
                    self._animate_text_transition(f"🎮 Esperando texto Bloque [{self.slot_num}]...", "#888888")
                    self.reset_state_ram()

        except Exception as e_ui:
            print(f"[LOG OVERLAY ERROR UI]: {e_ui}", flush=True)

    def closeEvent(self, event):
        if hasattr(self, "loop_timer") and self.loop_timer:
            self.loop_timer.stop()
        if hasattr(self, "worker") and self.worker:
            self.worker.stop()
        super().closeEvent(event)

def parse_hotkey_to_vk(hotkey_str: str) -> tuple:
    """Convierte cadenas como 'Ctrl+1' o 'Ctrl+Shift+F1' a modificadores Win32 y Código de Tecla Virtual (VK)."""
    parts = [p.strip().upper() for p in hotkey_str.split("+") if p.strip()]
    mods = 0x4000  # MOD_NOREPEAT
    vk = 0
    for part in parts:
        if part in ("CTRL", "CONTROL"):
            mods |= 0x0002
        elif part == "SHIFT":
            mods |= 0x0004
        elif part in ("ALT", "MENU"):
            mods |= 0x0001
        elif part in ("WIN", "WINDOWS", "META"):
            mods |= 0x0008
        elif len(part) == 1 and ("0" <= part <= "9" or "A" <= part <= "Z"):
            vk = ord(part)
        elif part.startswith("F") and part[1:].isdigit():
            f_num = int(part[1:])
            if 1 <= f_num <= 24:
                vk = 0x70 + (f_num - 1)
        elif part in ("ENTER", "RETURN"):
            vk = 0x0D
        elif part in ("SPACE", "ESPACIO"):
            vk = 0x20
        elif part == "TAB":
            vk = 0x09
        elif part in ("ESC", "ESCAPE"):
            vk = 0x1B
    return mods, vk

class GameGlobalHotkeyThread(QThread):
    """Escuchador global dinámico Win32 configurable para combinaciones de teclado personalizadas."""
    toggle_slot_triggered = pyqtSignal(int)
    define_slot_triggered = pyqtSignal(int)
    confirm_triggered = pyqtSignal()
    quick_add_triggered = pyqtSignal()
    quick_clear_triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.win_thread_id = 0

    def run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.win_thread_id = kernel32.GetCurrentThreadId()

        registered_ids = []
        saved_templates = load_saved_game_templates()

        # Registrar atajos para los 9 bloques
        for idx in range(1, 10):
            item = saved_templates[idx - 1] if idx <= len(saved_templates) else {}
            str_toggle = item.get("hotkey_toggle", f"Ctrl+{idx}")
            str_define = item.get("hotkey_define", f"Ctrl+Shift+{idx}")

            m_tog, vk_tog = parse_hotkey_to_vk(str_toggle)
            m_def, vk_def = parse_hotkey_to_vk(str_define)

            hid_tog = 300 + idx
            hid_def = 200 + idx

            if vk_tog:
                if user32.RegisterHotKey(None, hid_tog, m_tog, vk_tog):
                    registered_ids.append(hid_tog)
                if 0x31 <= vk_tog <= 0x39:
                    vk_num = vk_tog + 0x30
                    if user32.RegisterHotKey(None, hid_tog + 50, m_tog, vk_num):
                        registered_ids.append(hid_tog + 50)

            if vk_def:
                if user32.RegisterHotKey(None, hid_def, m_def, vk_def):
                    registered_ids.append(hid_def)
                if 0x31 <= vk_def <= 0x39:
                    vk_num = vk_def + 0x30
                    if user32.RegisterHotKey(None, hid_def + 50, m_def, vk_num):
                        registered_ids.append(hid_def + 50)

        # Atajo global configurable de inicio (ID 210)
        str_global_launch = get_game_launch_hotkey()
        m_launch, vk_launch = parse_hotkey_to_vk(str_global_launch)
        if vk_launch:
            if user32.RegisterHotKey(None, 210, m_launch, vk_launch):
                registered_ids.append(210)

        # Atajo global para recortar al vuelo sin congelar imagen (ID 211)
        str_quick_add = get_game_quick_add_hotkey()
        m_add, vk_add = parse_hotkey_to_vk(str_quick_add)
        if vk_add:
            if user32.RegisterHotKey(None, 211, m_add, vk_add):
                registered_ids.append(211)

        # Atajo global para borrar todos los bloques al vuelo (ID 212)
        str_quick_clear = get_game_quick_clear_hotkey()
        m_clr, vk_clr = parse_hotkey_to_vk(str_quick_clear)
        if vk_clr:
            if user32.RegisterHotKey(None, 212, m_clr, vk_clr):
                registered_ids.append(212)

        print(f"[LOG ATAJOS JUEGO] Escuchador activo con {len(registered_ids)} atajos dinámicos registrados.", flush=True)

        msg = ctypes.wintypes.MSG()
        while self.running:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break
            if msg.message == 0x0312:  # WM_HOTKEY
                hid = msg.wParam
                if 301 <= hid <= 309:
                    self.toggle_slot_triggered.emit(hid - 300)
                elif 351 <= hid <= 359:
                    self.toggle_slot_triggered.emit(hid - 350)
                elif 201 <= hid <= 209:
                    self.define_slot_triggered.emit(hid - 200)
                elif 251 <= hid <= 259:
                    self.define_slot_triggered.emit(hid - 250)
                elif hid == 210:
                    self.confirm_triggered.emit()
                elif hid == 211:
                    self.quick_add_triggered.emit()
                elif hid == 212:
                    self.quick_clear_triggered.emit()

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        for hid in registered_ids:
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass

    def stop(self):
        self.running = False
        if hasattr(self, "win_thread_id") and self.win_thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(self.win_thread_id, 0x0012, 0, 0)
            except Exception:
                pass
        self.quit()
        self.wait(1500)

from PyQt6.QtWidgets import (
    QTabWidget, QColorDialog, QSlider, QSpinBox, QCheckBox, QComboBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout,
    QInputDialog, QMessageBox
)
from PyQt6.QtGui import QKeySequence

class HotkeyLineEdit(QLineEdit):
    """Campo de entrada interactivo que detecta automáticamente cualquier combinación de teclas presionada."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setPlaceholderText("Haz clic y presiona las teclas...")
        self.setReadOnly(True)
        self.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold))

    def keyPressEvent(self, event):
        key = event.key()

        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        modifiers = event.modifiers()
        parts = []

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Win")

        native_vk = event.nativeVirtualKey()
        if native_vk == 0x2C or key in (Qt.Key.Key_Print, Qt.Key.Key_SysReq, 0x01000009, 0x0100000a):
            parts.append("PrtScn")
        elif key == Qt.Key.Key_Escape:
            self.clear()
            return
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            f_num = key - Qt.Key.Key_F1 + 1
            parts.append(f"F{f_num}")
        elif key == Qt.Key.Key_Space:
            parts.append("Space")
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            parts.append("Enter")
        elif key == Qt.Key.Key_Tab:
            parts.append("Tab")
        elif key == Qt.Key.Key_Backspace:
            self.clear()
            return
        else:
            key_text = event.text().upper()
            if not key_text or len(key_text) != 1 or not key_text.isprintable():
                key_text = QKeySequence(key).toString().upper()
            if key_text:
                parts.append(key_text)

        if parts:
            self.setText("+".join(parts))

class GameSettingsDialog(QDialog):
    """Panel de configuración amigable con pestañas para Bloques/Atajos, Fuentes y Apariencia del Recuadro."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = get_current_profile_name()
        self.setWindowTitle(f"Configuración del Modo Juego — Plantilla [{self.current_profile}]")
        self.resize(680, 520)

        self.templates_data = load_saved_game_templates(self.current_profile)
        if not self.templates_data:
            self.templates_data = []

        self.init_ui()
        ThemeManager.get_instance().register_child(self)
        self.apply_theme(ThemeManager.get_instance().is_dark)

    def apply_theme(self, is_dark: bool):
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }}
            QLabel {{
                color: {p['text_primary']};
            }}
        """)
        if hasattr(self, "title_lbl") and self.title_lbl:
            self.title_lbl.setStyleSheet("color: #60CDFF;" if is_dark else "color: #005A9E;")
        if hasattr(self, "tabs") and self.tabs:
            if is_dark:
                self.tabs.setStyleSheet("""
                    QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; background: rgba(20, 24, 32, 0.6); }
                    QTabBar::tab { background: rgba(255, 255, 255, 0.08); color: #CCCCCC; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
                    QTabBar::tab:selected { background: #0078D4; color: white; }
                """)
            else:
                self.tabs.setStyleSheet("""
                    QTabWidget::pane { border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 8px; background: #FFFFFF; }
                    QTabBar::tab { background: rgba(0, 0, 0, 0.06); color: #444444; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
                    QTabBar::tab:selected { background: #0078D4; color: white; }
                """)
        if hasattr(self, "btn_cancel") and self.btn_cancel:
            if is_dark:
                self.btn_cancel.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 8px 16px; font-weight: bold;")
            else:
                self.btn_cancel.setStyleSheet("background-color: rgba(0, 0, 0, 0.06); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 8px; padding: 8px 16px; font-weight: bold;")

        style_edit = "background: rgba(255, 255, 255, 0.1); color: white; border-radius: 6px; padding: 4px; font-weight: bold;" if is_dark else "background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 6px; padding: 4px; font-weight: bold;"
        for ed in ("edit_global_launch", "edit_quick_add", "edit_quick_clear"):
            if hasattr(self, ed) and getattr(self, ed):
                getattr(self, ed).setStyleSheet(style_edit)

        color_lbl = "color: #60CDFF; font-weight: bold;" if is_dark else "color: #005A9E; font-weight: bold;"
        for lbl_name in ("lbl_c1", "lbl_c2", "lbl_c3"):
            if hasattr(self, lbl_name) and getattr(self, lbl_name):
                getattr(self, lbl_name).setStyleSheet(color_lbl)

        if hasattr(self, "lbl_desc") and self.lbl_desc:
            self.lbl_desc.setStyleSheet("color: #A0AAB4;" if is_dark else "color: #595959;")

        if hasattr(self, "table_blocks") and self.table_blocks:
            if is_dark:
                self.table_blocks.setStyleSheet("background-color: rgba(0, 0, 0, 0.3); color: white; gridline-color: rgba(255, 255, 255, 0.1);")
            else:
                self.table_blocks.setStyleSheet("background-color: #FFFFFF; color: #1A1A1A; gridline-color: rgba(0, 0, 0, 0.1);")

            cell_edit_style = "background: rgba(255, 255, 255, 0.1); color: white; border-radius: 4px; padding: 4px;" if is_dark else "background: rgba(0, 0, 0, 0.05); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 4px; padding: 4px;"
            for row in range(self.table_blocks.rowCount()):
                for col in (1, 2):
                    w = self.table_blocks.cellWidget(row, col)
                    if w:
                        w.setStyleSheet(cell_edit_style)

        spin_style = "background: rgba(255, 255, 255, 0.1); color: white; padding: 4px; border-radius: 4px;" if is_dark else "background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); padding: 4px; border-radius: 4px;"
        if hasattr(self, "spin_font_size") and self.spin_font_size:
            self.spin_font_size.setStyleSheet(spin_style)
        if hasattr(self, "spin_border_width") and self.spin_border_width:
            self.spin_border_width.setStyleSheet(spin_style)
        chk_style = "color: white;" if is_dark else "color: #1A1A1A;"
        if hasattr(self, "chk_font_bold") and self.chk_font_bold:
            self.chk_font_bold.setStyleSheet(chk_style)
        if hasattr(self, "chk_text_border") and self.chk_text_border:
            self.chk_text_border.setStyleSheet(chk_style)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            parent_obj = self.parent()
            cfg = getattr(parent_obj, "config_manager", None) or getattr(parent_obj, "config", None)
            dark = check_is_dark_theme(cfg)
            hwnd = int(self.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            val = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

    def init_ui(self):
        parent_obj = self.parent()
        cfg = getattr(parent_obj, "config_manager", None) or getattr(parent_obj, "config", None)
        dark = check_is_dark_theme(cfg)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        self.title_lbl = QLabel(f"⚙️ Configurando Plantilla de Juego: '{self.current_profile}'"); title_lbl = self.title_lbl
        title_lbl.setFont(QFont("Segoe UI Variable Display", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #60CDFF;" if dark else "color: #005A9E;")
        main_layout.addWidget(title_lbl)

        self.tabs = QTabWidget()
        if dark:
            self.tabs.setStyleSheet("""
                QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; background: rgba(20, 24, 32, 0.6); }
                QTabBar::tab { background: rgba(255, 255, 255, 0.08); color: #CCCCCC; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
                QTabBar::tab:selected { background: #0078D4; color: white; }
            """)
        else:
            self.tabs.setStyleSheet("""
                QTabWidget::pane { border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 8px; background: #FFFFFF; }
                QTabBar::tab { background: rgba(0, 0, 0, 0.06); color: #444444; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: bold; }
                QTabBar::tab:selected { background: #0078D4; color: white; }
            """)

        # Pestañas
        self.tab_blocks = QWidget()
        self.tab_font = QWidget()
        self.tab_style = QWidget()

        self._setup_blocks_tab()
        self._setup_font_tab()
        self._setup_style_tab()

        self.tabs.addTab(self.tab_blocks, "🎮 Bloques y Atajos")
        self.tabs.addTab(self.tab_font, "🔤 Fuente y Texto")
        self.tabs.addTab(self.tab_style, "🎨 Fondo y Recuadro")

        main_layout.addWidget(self.tabs, stretch=1)

        # Botones inferiores
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Guardar y Aplicar Ajustes")
        btn_save.setStyleSheet("background-color: #107C41; color: white; border: none; border-radius: 8px; padding: 8px 20px; font-weight: bold;")
        btn_save.clicked.connect(self.save_and_close)

        self.btn_cancel = QPushButton("Cancelar"); btn_cancel = self.btn_cancel
        if dark:
            btn_cancel.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 8px 16px; font-weight: bold;")
        else:
            btn_cancel.setStyleSheet("background-color: rgba(0, 0, 0, 0.06); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 8px; padding: 8px 16px; font-weight: bold;")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)

        main_layout.addLayout(btn_layout)

    def _setup_blocks_tab(self):
        parent_obj = self.parent()
        cfg = getattr(parent_obj, "config_manager", None) or getattr(parent_obj, "config", None)
        dark = check_is_dark_theme(cfg)
        layout = QVBoxLayout(self.tab_blocks)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Atajos Globales de Lanzamiento y Recorte al Vuelo interactivos (Auto-detectan teclas)
        form_hk = QFormLayout()
        form_hk.setSpacing(6)

        self.edit_global_launch = HotkeyLineEdit(get_game_launch_hotkey())
        self.edit_quick_add = HotkeyLineEdit(get_game_quick_add_hotkey())
        self.edit_quick_clear = HotkeyLineEdit(get_game_quick_clear_hotkey())

        style_edit = "background: rgba(255, 255, 255, 0.1); color: white; border-radius: 6px; padding: 4px; font-weight: bold;" if dark else "background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 6px; padding: 4px; font-weight: bold;"
        self.edit_global_launch.setStyleSheet(style_edit)
        self.edit_quick_add.setStyleSheet(style_edit)
        self.edit_quick_clear.setStyleSheet(style_edit)

        self.lbl_c1 = QLabel("Atajo Iniciar/Apagar Traducción:"); lbl_c1 = self.lbl_c1
        self.lbl_c2 = QLabel("Atajo Recortar al Vuelo (Sin congelar):"); lbl_c2 = self.lbl_c2
        self.lbl_c3 = QLabel("Atajo Borrar Bloques al Vuelo:"); lbl_c3 = self.lbl_c3
        color_lbl = "color: #60CDFF; font-weight: bold;" if dark else "color: #005A9E; font-weight: bold;"
        lbl_c1.setStyleSheet(color_lbl)
        lbl_c2.setStyleSheet(color_lbl)
        lbl_c3.setStyleSheet(color_lbl)

        form_hk.addRow(lbl_c1, self.edit_global_launch)
        form_hk.addRow(lbl_c2, self.edit_quick_add)
        form_hk.addRow(lbl_c3, self.edit_quick_clear)

        layout.addLayout(form_hk)

        self.lbl_desc = QLabel("Haz clic en una casilla y presiona tus teclas para configurar los 9 bloques plantilla:"); lbl_desc = self.lbl_desc
        lbl_desc.setStyleSheet("color: #A0AAB4;" if dark else "color: #595959;")
        layout.addWidget(lbl_desc)

        self.table_blocks = QTableWidget(9, 4)
        self.table_blocks.setHorizontalHeaderLabels(["Bloque", "Atajo On/Off", "Atajo Recortar", "Estado del Área"])
        self.table_blocks.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_blocks.verticalHeader().setVisible(False)
        if dark:
            self.table_blocks.setStyleSheet("background-color: rgba(0, 0, 0, 0.3); color: white; gridline-color: rgba(255, 255, 255, 0.1);")
        else:
            self.table_blocks.setStyleSheet("background-color: #FFFFFF; color: #1A1A1A; gridline-color: rgba(0, 0, 0, 0.1);")

        for idx in range(1, 10):
            item_info = self.templates_data[idx - 1] if idx <= len(self.templates_data) else {}
            r = item_info.get("rect")

            lbl_item = QTableWidgetItem(f"Bloque [{idx}]")
            lbl_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            lbl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_blocks.setItem(idx - 1, 0, lbl_item)

            edit_toggle = HotkeyLineEdit(item_info.get("hotkey_toggle", f"Ctrl+{idx}"))
            edit_toggle.setStyleSheet("background: rgba(255, 255, 255, 0.1); color: white; border-radius: 4px; padding: 4px;" if dark else "background: rgba(0, 0, 0, 0.05); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 4px; padding: 4px;")
            self.table_blocks.setCellWidget(idx - 1, 1, edit_toggle)

            edit_define = HotkeyLineEdit(item_info.get("hotkey_define", f"Ctrl+Shift+{idx}"))
            edit_define.setStyleSheet("background: rgba(255, 255, 255, 0.1); color: white; border-radius: 4px; padding: 4px;" if dark else "background: rgba(0, 0, 0, 0.05); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 4px; padding: 4px;")
            self.table_blocks.setCellWidget(idx - 1, 2, edit_define)

            status_txt = f"{r['w']}x{r['h']} px" if r else "Sin Configurar"
            st_item = QTableWidgetItem(status_txt)
            st_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_blocks.setItem(idx - 1, 3, st_item)

        layout.addWidget(self.table_blocks)

    def _setup_font_tab(self):
        parent_obj = self.parent()
        cfg = getattr(parent_obj, "config_manager", None) or getattr(parent_obj, "config", None)
        dark = check_is_dark_theme(cfg)
        layout = QVBoxLayout(self.tab_font)
        layout.setContentsMargins(16, 16, 16, 16)

        first_cfg = self.templates_data[0] if self.templates_data else get_default_block_style()

        form = QFormLayout()
        form.setSpacing(14)

        # Color de Fuente
        self.btn_font_color = QPushButton()
        self.current_font_color = first_cfg.get("font_color", "#60CDFF")
        self._update_color_button_style(self.btn_font_color, self.current_font_color)
        self.btn_font_color.clicked.connect(self._choose_font_color)
        form.addRow("Color del Texto:", self.btn_font_color)

        # Tamaño de Fuente
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(9, 36)
        self.spin_font_size.setValue(first_cfg.get("font_size", 13))
        if dark:
            self.spin_font_size.setStyleSheet("background: rgba(255, 255, 255, 0.1); color: white; padding: 4px; border-radius: 4px;")
        else:
            self.spin_font_size.setStyleSheet("background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); padding: 4px; border-radius: 4px;")
        form.addRow("Tamaño del Texto (pt):", self.spin_font_size)

        # Negritas
        self.chk_font_bold = QCheckBox("Activar Texto en Negrita (Bold)")
        self.chk_font_bold.setChecked(first_cfg.get("font_bold", True))
        self.chk_font_bold.setStyleSheet("color: white;" if dark else "color: #1A1A1A;")
        form.addRow("Estilo de Fuente:", self.chk_font_bold)

        # Borde/Sombra de Texto
        self.chk_text_border = QCheckBox("Activar Sombra / Borde de Alto Contraste")
        self.chk_text_border.setChecked(first_cfg.get("text_border", True))
        self.chk_text_border.setStyleSheet("color: white;" if dark else "color: #1A1A1A;")
        form.addRow("Contraste de Texto:", self.chk_text_border)

        # Color del Borde de Texto
        self.btn_text_border_color = QPushButton()
        self.current_text_border_color = first_cfg.get("text_border_color", "#000000")
        self._update_color_button_style(self.btn_text_border_color, self.current_text_border_color)
        self.btn_text_border_color.clicked.connect(self._choose_text_border_color)
        form.addRow("Color Sombra/Borde:", self.btn_text_border_color)

        layout.addLayout(form)
        layout.addStretch()

    def _setup_style_tab(self):
        parent_obj = self.parent()
        cfg = getattr(parent_obj, "config_manager", None) or getattr(parent_obj, "config", None)
        dark = check_is_dark_theme(cfg)
        layout = QVBoxLayout(self.tab_style)
        layout.setContentsMargins(16, 16, 16, 16)

        first_cfg = self.templates_data[0] if self.templates_data else get_default_block_style()

        form = QFormLayout()
        form.setSpacing(14)

        # Opacidad
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(first_cfg.get("bg_opacity", 60))
        self.lbl_opacity_val = QLabel(f"{self.slider_opacity.value()}%")
        self.lbl_opacity_val.setStyleSheet("color: #60CDFF; font-weight: bold;" if dark else "color: #005A9E; font-weight: bold;")
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity_val.setText(f"{v}%"))

        op_layout = QHBoxLayout()
        op_layout.addWidget(self.slider_opacity)
        op_layout.addWidget(self.lbl_opacity_val)
        form.addRow("Opacidad del Fondo:", op_layout)

        # Color Fondo
        self.btn_bg_color = QPushButton()
        self.current_bg_color = first_cfg.get("bg_color", "#000000")
        self._update_color_button_style(self.btn_bg_color, self.current_bg_color)
        self.btn_bg_color.clicked.connect(self._choose_bg_color)
        form.addRow("Color de Fondo:", self.btn_bg_color)

        # Color Borde Marco
        self.btn_box_border_color = QPushButton()
        self.current_box_border_color = first_cfg.get("box_border_color", "#0078D4")
        self._update_color_button_style(self.btn_box_border_color, self.current_box_border_color)
        self.btn_box_border_color.clicked.connect(self._choose_box_border_color)
        form.addRow("Color de Borde Marco:", self.btn_box_border_color)

        # Grosor Borde Marco
        self.spin_border_width = QSpinBox()
        self.spin_border_width.setRange(0, 6)
        self.spin_border_width.setValue(first_cfg.get("box_border_width", 2))
        if dark:
            self.spin_border_width.setStyleSheet("background: rgba(255, 255, 255, 0.1); color: white; padding: 4px; border-radius: 4px;")
        else:
            self.spin_border_width.setStyleSheet("background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); padding: 4px; border-radius: 4px;")
        form.addRow("Grosor de Borde (px):", self.spin_border_width)

        layout.addLayout(form)
        layout.addStretch()

    def _update_color_button_style(self, btn: QPushButton, hex_code: str):
        btn.setText(hex_code.upper())
        btn.setStyleSheet(f"background-color: {hex_code}; color: {'#000000' if QColor(hex_code).lightness() > 128 else '#FFFFFF'}; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; padding: 6px; font-weight: bold;")

    def _choose_font_color(self):
        color = QColorDialog.getColor(QColor(self.current_font_color), self, "Seleccionar Color de Texto")
        if color.isValid():
            self.current_font_color = color.name()
            self._update_color_button_style(self.btn_font_color, self.current_font_color)

    def _choose_text_border_color(self):
        color = QColorDialog.getColor(QColor(self.current_text_border_color), self, "Seleccionar Color de Sombra/Borde")
        if color.isValid():
            self.current_text_border_color = color.name()
            self._update_color_button_style(self.btn_text_border_color, self.current_text_border_color)

    def _choose_bg_color(self):
        color = QColorDialog.getColor(QColor(self.current_bg_color), self, "Seleccionar Color de Fondo")
        if color.isValid():
            self.current_bg_color = color.name()
            self._update_color_button_style(self.btn_bg_color, self.current_bg_color)

    def _choose_box_border_color(self):
        color = QColorDialog.getColor(QColor(self.current_box_border_color), self, "Seleccionar Color de Borde de Marco")
        if color.isValid():
            self.current_box_border_color = color.name()
            self._update_color_button_style(self.btn_box_border_color, self.current_box_border_color)

    def save_and_close(self):
        if hasattr(self, "edit_global_launch") and self.edit_global_launch:
            set_game_launch_hotkey(self.edit_global_launch.text().strip())
        if hasattr(self, "edit_quick_add") and self.edit_quick_add:
            set_game_quick_add_hotkey(self.edit_quick_add.text().strip())
        if hasattr(self, "edit_quick_clear") and self.edit_quick_clear:
            set_game_quick_clear_hotkey(self.edit_quick_clear.text().strip())

        style_shared = {
            "font_color": self.current_font_color,
            "font_size": self.spin_font_size.value(),
            "font_bold": self.chk_font_bold.isChecked(),
            "text_border": self.chk_text_border.isChecked(),
            "text_border_color": self.current_text_border_color,
            "bg_color": self.current_bg_color,
            "bg_opacity": self.slider_opacity.value(),
            "box_border_color": self.current_box_border_color,
            "box_border_width": self.spin_border_width.value()
        }

        updated_templates = []
        for idx in range(1, 10):
            item_existing = self.templates_data[idx - 1] if idx <= len(self.templates_data) else {}
            
            w_tog = self.table_blocks.cellWidget(idx - 1, 1)
            w_def = self.table_blocks.cellWidget(idx - 1, 2)

            str_tog = w_tog.text().strip() if w_tog else f"Ctrl+{idx}"
            str_def = w_def.text().strip() if w_def else f"Ctrl+Shift+{idx}"

            item_combined = {
                "rect": item_existing.get("rect", {"x": 100, "y": 100, "w": 300, "h": 100}),
                "from_lang": item_existing.get("from_lang", "en"),
                "to_lang": item_existing.get("to_lang", "es"),
                "hotkey_toggle": str_tog,
                "hotkey_define": str_def,
                **style_shared
            }
            if item_existing.get("rect"):
                updated_templates.append(item_combined)

        save_game_templates_data(updated_templates, self.current_profile)
        self.accept()

class GameTranslatorWindow(QDialog):
    """Ventana independiente de gestión de traducción en vivo con sistema de perfiles por juego."""
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.active_overlays = {}
        self.pending_slot = None

        self.setWindowTitle("Jade — Traductor de Juegos en Tiempo Real")
        self.resize(660, 560)
        self.setMinimumSize(420, 360)

        self.init_ui()
        self.populate_profiles_combo()
        self.load_saved_templates_ui()
        ThemeManager.get_instance().register_child(self)
        self.apply_theme(ThemeManager.get_instance().is_dark)

        # Iniciar escuchador global de atajos en juego
        self.start_hotkey_listener()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            dark = check_is_dark_theme(self.config_manager)
            hwnd = int(self.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            val = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

    def start_hotkey_listener(self):
        if hasattr(self, "hk_thread") and self.hk_thread:
            self.hk_thread.stop()
        self.hk_thread = GameGlobalHotkeyThread(self)
        self.hk_thread.toggle_slot_triggered.connect(self.on_toggle_slot_hotkey)
        self.hk_thread.define_slot_triggered.connect(self.on_define_slot_hotkey)
        self.hk_thread.confirm_triggered.connect(self.on_confirm_hotkey_triggered)
        self.hk_thread.quick_add_triggered.connect(self.trigger_live_quick_selection)
        self.hk_thread.quick_clear_triggered.connect(self.clear_all_dynamic_blocks)
        self.hk_thread.start()

    def trigger_live_quick_selection(self):
        """Abre la herramienta de selección de pantalla nativa de la app principal (SnippingOverlay) para capturar el área."""
        capture_func, overlay_class = get_main_capture_tools()
        if callable(capture_func) and overlay_class:
            try:
                full_desktop = capture_func()
                self.overlay_selector = overlay_class(full_desktop)
                self.overlay_selector.area_captured.connect(self._on_live_area_cropped)
                self.overlay_selector.show()
            except Exception as e:
                print(f"[LOG ERROR RECORTE JUEGO]: {e}", flush=True)
        else:
            print("[LOG ERROR RECORTE JUEGO] Herramientas de captura no disponibles en main.", flush=True)

    def _on_live_area_cropped(self, pixmap, rect: QRect):
        if rect and rect.isValid() and rect.width() > 10 and rect.height() > 10:
            from_lang = "en"
            to_lang = "es"
            if self.config_manager:
                from_lang = self.config_manager.get("translate_from_lang") or "en"
                to_lang = self.config_manager.get("translate_to_lang") or "es"
            spawn_dynamic_game_block(rect, from_lang, to_lang)

    def clear_all_dynamic_blocks(self):
        """Elimina todos los contenedores recortados al vuelo en vivo."""
        clear_all_dynamic_game_blocks()


    def apply_theme(self, is_dark: bool):
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }}
        """)
        if hasattr(self, "title_lbl") and self.title_lbl:
            self.title_lbl.setStyleSheet("color: #60CDFF;" if is_dark else "color: #005A9E;")
        if hasattr(self, "btn_settings") and self.btn_settings:
            if is_dark:
                self.btn_settings.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 120, 212, 0.25);
                        color: #60CDFF; border: 1px solid rgba(0, 120, 212, 0.5);
                        border-radius: 8px; padding: 6px 14px; font-weight: bold; font-size: 11px;
                    }
                    QPushButton:hover { background-color: #0078D4; color: white; }
                """)
            else:
                self.btn_settings.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 120, 212, 0.12);
                        color: #005A9E; border: 1px solid rgba(0, 120, 212, 0.4);
                        border-radius: 8px; padding: 6px 14px; font-weight: bold; font-size: 11px;
                    }
                    QPushButton:hover { background-color: #0078D4; color: white; }
                """)
        if hasattr(self, "prof_box") and self.prof_box:
            if is_dark:
                self.prof_box.setStyleSheet("QGroupBox { color: #60CDFF; font-weight: bold; border: 1px solid rgba(0, 120, 212, 0.4); border-radius: 8px; margin-top: 6px; padding-top: 12px; }")
            else:
                self.prof_box.setStyleSheet("QGroupBox { color: #005A9E; font-weight: bold; border: 1px solid rgba(0, 120, 212, 0.3); border-radius: 8px; margin-top: 6px; padding-top: 12px; }")
        if hasattr(self, "combo_profiles") and self.combo_profiles:
            if is_dark:
                self.combo_profiles.setStyleSheet("QComboBox { background: rgba(255, 255, 255, 0.1); color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold; } QComboBox QAbstractItemView { background-color: #141820; color: white; selection-background-color: #0078D4; }")
            else:
                self.combo_profiles.setStyleSheet("QComboBox { background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 6px; padding: 6px 12px; font-weight: bold; } QComboBox QAbstractItemView { background-color: #FFFFFF; color: #1A1A1A; selection-background-color: #0078D4; selection-color: white; }")
        if hasattr(self, "btn_ren_prof") and self.btn_ren_prof:
            if is_dark:
                self.btn_ren_prof.setStyleSheet("background-color: rgba(255, 255, 255, 0.15); color: white; border-radius: 6px; padding: 6px 10px; font-weight: bold;")
            else:
                self.btn_ren_prof.setStyleSheet("background-color: rgba(0, 0, 0, 0.08); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 6px; padding: 6px 10px; font-weight: bold;")
        if hasattr(self, "sub_lbl_shortcuts") and self.sub_lbl_shortcuts:
            if is_dark:
                self.sub_lbl_shortcuts.setStyleSheet("color: #60CDFF; background-color: rgba(0, 120, 212, 0.15); border-left: 3px solid #0078D4; padding: 8px; border-radius: 6px;")
            else:
                self.sub_lbl_shortcuts.setStyleSheet("color: #005A9E; background-color: rgba(0, 120, 212, 0.08); border-left: 3px solid #0078D4; padding: 8px; border-radius: 6px;")
        if hasattr(self, "list_templates") and self.list_templates:
            if is_dark:
                self.list_templates.setStyleSheet("""
                    QListWidget {
                        background-color: rgba(20, 24, 32, 0.8);
                        color: white;
                        border: 1px solid rgba(255, 255, 255, 0.12);
                        border-radius: 8px;
                        padding: 4px;
                    }
                """)
            else:
                self.list_templates.setStyleSheet("""
                    QListWidget {
                        background-color: #FFFFFF;
                        color: #1A1A1A;
                        border: 1px solid rgba(0, 0, 0, 0.15);
                        border-radius: 8px;
                        padding: 4px;
                    }
                """)
        if hasattr(self, "btn_close_all") and self.btn_close_all:
            if is_dark:
                self.btn_close_all.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(232, 17, 35, 0.2); color: #FF99A4; border: 1px solid rgba(232, 17, 35, 0.4);
                        border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 11px;
                    }
                    QPushButton:hover { background-color: #E81123; color: white; }
                """)
            else:
                self.btn_close_all.setStyleSheet("""
                    QPushButton {
                        background-color: #FDE8E8; color: #E81123; border: 1px solid rgba(232, 17, 35, 0.3);
                        border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 11px;
                    }
                    QPushButton:hover { background-color: #E81123; color: white; }
                """)

    def init_ui(self):
        dark = check_is_dark_theme(self.config_manager)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Encabezado
        top_header = QHBoxLayout()
        self.title_lbl = QLabel("🎮 Traducción de Pantalla & Juegos"); title_lbl = self.title_lbl
        title_lbl.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #60CDFF;" if dark else "color: #005A9E;")

        self.btn_settings = QPushButton("⚙️ Atajos & Fuentes"); btn_settings = self.btn_settings
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        if dark:
            btn_settings.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 120, 212, 0.25);
                    color: #60CDFF; border: 1px solid rgba(0, 120, 212, 0.5);
                    border-radius: 8px; padding: 6px 14px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #0078D4; color: white; }
            """)
        else:
            btn_settings.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 120, 212, 0.12);
                    color: #005A9E; border: 1px solid rgba(0, 120, 212, 0.4);
                    border-radius: 8px; padding: 6px 14px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #0078D4; color: white; }
            """)
        btn_settings.clicked.connect(self.open_game_settings)

        top_header.addWidget(title_lbl)
        top_header.addStretch()
        top_header.addWidget(btn_settings)

        layout.addLayout(top_header)

        # Barra de Selección de Plantilla de Juego
        self.prof_box = QGroupBox("🎮 Seleccionar Plantilla de Juego Activa"); prof_box = self.prof_box
        if dark:
            prof_box.setStyleSheet("QGroupBox { color: #60CDFF; font-weight: bold; border: 1px solid rgba(0, 120, 212, 0.4); border-radius: 8px; margin-top: 6px; padding-top: 12px; }")
        else:
            prof_box.setStyleSheet("QGroupBox { color: #005A9E; font-weight: bold; border: 1px solid rgba(0, 120, 212, 0.3); border-radius: 8px; margin-top: 6px; padding-top: 12px; }")
        prof_layout = QHBoxLayout(prof_box)
        prof_layout.setContentsMargins(10, 8, 10, 8)
        prof_layout.setSpacing(8)

        self.combo_profiles = QComboBox()
        if dark:
            self.combo_profiles.setStyleSheet("QComboBox { background: rgba(255, 255, 255, 0.1); color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold; } QComboBox QAbstractItemView { background-color: #141820; color: white; selection-background-color: #0078D4; }")
        else:
            self.combo_profiles.setStyleSheet("QComboBox { background: #FFFFFF; color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.15); border-radius: 6px; padding: 6px 12px; font-weight: bold; } QComboBox QAbstractItemView { background-color: #FFFFFF; color: #1A1A1A; selection-background-color: #0078D4; selection-color: white; }")
        self.combo_profiles.currentTextChanged.connect(self.on_profile_changed)

        btn_new_prof = QPushButton("➕ Nueva")
        btn_new_prof.setStyleSheet("background-color: #107C41; color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        btn_new_prof.clicked.connect(self.create_new_profile)

        self.btn_ren_prof = QPushButton("✏️ Renombrar"); btn_ren_prof = self.btn_ren_prof
        if dark:
            btn_ren_prof.setStyleSheet("background-color: rgba(255, 255, 255, 0.15); color: white; border-radius: 6px; padding: 6px 10px; font-weight: bold;")
        else:
            btn_ren_prof.setStyleSheet("background-color: rgba(0, 0, 0, 0.08); color: #1A1A1A; border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 6px; padding: 6px 10px; font-weight: bold;")
        btn_ren_prof.clicked.connect(self.rename_current_profile)

        btn_del_prof = QPushButton("🗑️")
        btn_del_prof.setToolTip("Eliminar Plantilla Seleccionada")
        btn_del_prof.setStyleSheet("background-color: rgba(232, 17, 35, 0.25); color: #FF99A4; border: 1px solid rgba(232, 17, 35, 0.4); border-radius: 6px; padding: 6px 10px; font-weight: bold;")
        btn_del_prof.clicked.connect(self.delete_current_profile)

        prof_layout.addWidget(self.combo_profiles, stretch=1)
        prof_layout.addWidget(btn_new_prof)
        prof_layout.addWidget(btn_ren_prof)
        prof_layout.addWidget(btn_del_prof)

        layout.addWidget(prof_box)

        # Atajos Rápidos
        str_launch_hk = get_game_launch_hotkey()
        self.sub_lbl_shortcuts = QLabel(f"💡 Atajos directos:\n• Alternar/Destruir Bloques: [Ctrl+1] a [Ctrl+9]\n• Recortar/Redefinir Área: [Ctrl+Shift+1] a [Ctrl+Shift+9]\n• Iniciar Traducción en Vivo: [{str_launch_hk}]")
        self.sub_lbl_shortcuts.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))
        if dark:
            self.sub_lbl_shortcuts.setStyleSheet("color: #60CDFF; background-color: rgba(0, 120, 212, 0.15); border-left: 3px solid #0078D4; padding: 8px; border-radius: 6px;")
        else:
            self.sub_lbl_shortcuts.setStyleSheet("color: #005A9E; background-color: rgba(0, 120, 212, 0.08); border-left: 3px solid #0078D4; padding: 8px; border-radius: 6px;")
        self.sub_lbl_shortcuts.setWordWrap(True)
        layout.addWidget(self.sub_lbl_shortcuts)

        # Lista de Bloques
        self.list_templates = QListWidget()
        self.list_templates.setStyleSheet("""
            QListWidget {
                background-color: rgba(20, 24, 32, 0.8);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 4px;
            }
        """ if dark else """
            QListWidget {
                background-color: #FFFFFF;
                color: #1A1A1A;
                border: 1px solid rgba(0, 0, 0, 0.15);
                border-radius: 8px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.list_templates, stretch=1)

        # Acciones inferiores
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_add = QPushButton("➕ Recortar Área Bloque")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; color: white; border: none;
                border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 11px;
            }
            QPushButton:hover { background-color: #106EBE; }
        """)
        btn_add.clicked.connect(self.add_template_area)

        btn_launch = QPushButton("▶️ Iniciar Traducción en Vivo")
        btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_launch.setStyleSheet("""
            QPushButton {
                background-color: #107C41; color: white; border: none;
                border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 11px;
            }
            QPushButton:hover { background-color: #0F6CBD; }
        """)
        btn_launch.clicked.connect(self.launch_saved_templates)

        self.btn_close_all = QPushButton("🛑 Detener Todo"); btn_close_all = self.btn_close_all
        btn_close_all.setCursor(Qt.CursorShape.PointingHandCursor)
        if dark:
            btn_close_all.setStyleSheet("""
                QPushButton {
                    background-color: rgba(232, 17, 35, 0.2); color: #FF99A4; border: 1px solid rgba(232, 17, 35, 0.4);
                    border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #E81123; color: white; }
            """)
        else:
            btn_close_all.setStyleSheet("""
                QPushButton {
                    background-color: #FDE8E8; color: #E81123; border: 1px solid rgba(232, 17, 35, 0.3);
                    border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #E81123; color: white; }
            """)
        btn_close_all.clicked.connect(self.stop_all_overlays)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_launch)
        btn_layout.addWidget(btn_close_all)

        layout.addLayout(btn_layout)

    def populate_profiles_combo(self):
        """Puebla el desplegable de plantillas de juego."""
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        data = load_all_game_profiles()
        profiles = list(data.get("profiles", {}).keys())
        if not profiles:
            profiles = ["Predeterminado"]

        self.combo_profiles.addItems(profiles)
        active = get_current_profile_name()
        if active in profiles:
            self.combo_profiles.setCurrentText(active)
        self.combo_profiles.blockSignals(False)

    def on_profile_changed(self, profile_name: str):
        """Cambia la plantilla activa al seleccionar otra en el desplegable."""
        if profile_name and profile_name != get_current_profile_name():
            set_current_profile_name(profile_name)
            self.stop_all_overlays()
            self.load_saved_templates_ui()
            self.start_hotkey_listener()

    def create_new_profile(self):
        """Crea una nueva plantilla para otro juego."""
        name, ok = QInputDialog.getText(self, "Nueva Plantilla de Juego", "Nombre de la plantilla de juego (ej. Genshin Impact):")
        if ok and name.strip():
            prof_name = name.strip()
            set_current_profile_name(prof_name)
            self.stop_all_overlays()
            self.populate_profiles_combo()
            self.load_saved_templates_ui()
            self.start_hotkey_listener()

    def rename_current_profile(self):
        """Renombra la plantilla de juego activa."""
        curr = get_current_profile_name()
        name, ok = QInputDialog.getText(self, "Renombrar Plantilla", "Nuevo nombre para la plantilla:", text=curr)
        if ok and name.strip() and name.strip() != curr:
            new_name = name.strip()
            data = load_all_game_profiles()
            if curr in data.get("profiles", {}):
                templates = data["profiles"].pop(curr)
                data["profiles"][new_name] = templates
                data["active_profile"] = new_name
                save_all_game_profiles(data)
                set_current_profile_name(new_name)
                self.populate_profiles_combo()
                self.load_saved_templates_ui()

    def delete_current_profile(self):
        """Elimina la plantilla de juego activa tras confirmación."""
        curr = get_current_profile_name()
        data = load_all_game_profiles()
        profiles = data.get("profiles", {})
        if len(profiles) <= 1:
            QMessageBox.warning(self, "Aviso", "No puedes eliminar la única plantilla existente.")
            return

        reply = QMessageBox.question(
            self, "Confirmar Eliminación",
            f"¿Estás seguro de que deseas eliminar la plantilla de juego '{curr}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            profiles.pop(curr, None)
            new_active = next(iter(profiles.keys()))
            data["active_profile"] = new_active
            save_all_game_profiles(data)
            set_current_profile_name(new_active)
            self.stop_all_overlays()
            self.populate_profiles_combo()
            self.load_saved_templates_ui()
            self.start_hotkey_listener()

    def open_game_settings(self):
        dialog = GameSettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.start_hotkey_listener()
            self.reload_active_overlay_styles()
            self.load_saved_templates_ui()

    def reload_active_overlay_styles(self):
        saved = load_saved_game_templates()
        for idx, item in enumerate(saved):
            slot_n = idx + 1
            if slot_n in self.active_overlays and self.active_overlays[slot_n] is not None:
                self.active_overlays[slot_n].apply_style_config(item)

    def on_toggle_slot_hotkey(self, slot_num: int):
        """Alterna o destruye el bloque instanciando en vivo con el estilo configurado."""
        print(f"[LOG TRADUCCION] Atajo accionado para Bloque [{slot_num}]", flush=True)
        if slot_num in self.active_overlays and self.active_overlays[slot_num] is not None:
            try:
                ov = self.active_overlays[slot_num]
                ov.close()
                ov.deleteLater()
            except Exception as e:
                print(f"[LOG ERROR DESTRUIR OVERLAY]: {e}", flush=True)
            self.active_overlays[slot_num] = None
            print(f"[LOG OVERLAY BLOQUE {slot_num}] Destruido completamente de la memoria.", flush=True)
        else:
            saved = load_saved_game_templates()
            if slot_num <= len(saved):
                item = saved[slot_num - 1]
                r = item["rect"]
                rect = QRect(r["x"], r["y"], r["w"], r["h"])
                ov = GameTranslationOverlay(rect, item.get("from_lang", "en"), item.get("to_lang", "es"), slot_num, item)
                ov.show()
                self.active_overlays[slot_num] = ov
                print(f"[LOG OVERLAY BLOQUE {slot_num}] Creado e instanciado desde cero.", flush=True)
            else:
                self.pending_slot = slot_num
                self._start_area_selection()
        self.load_saved_templates_ui()

    def on_define_slot_hotkey(self, slot_num: int):
        self.pending_slot = slot_num
        self._start_area_selection()

    def on_confirm_hotkey_triggered(self):
        self.toggle_saved_templates()

    def toggle_saved_templates(self):
        """Alterna el estado de los bloques: si hay alguno activo lo apaga; si están apagados los enciende."""
        if any(ov is not None and ov.isVisible() for ov in self.active_overlays.values()):
            print("[LOG TRADUCCION] Apagando contenedores de Modo Juego mediante atajo...", flush=True)
            self.stop_all_overlays()
        else:
            print("[LOG TRADUCCION] Encendiendo contenedores de Modo Juego mediante atajo...", flush=True)
            self.launch_saved_templates()

    def add_template_area(self):
        saved = load_saved_game_templates()
        self.pending_slot = min(9, len(saved) + 1)
        self.countdown_toast = GameCountdownToast()
        self.countdown_toast.countdown_finished.connect(self._start_area_selection)
        self.countdown_toast.start_countdown()

    def _start_area_selection(self):
        try:
            import __main__ as main_mod
            capture_full_desktop = getattr(main_mod, "capture_full_desktop", None)
            SnippingOverlay = getattr(main_mod, "SnippingOverlay", None)

            if callable(capture_full_desktop) and SnippingOverlay:
                full_screen = capture_full_desktop()
                self.overlay_selector = SnippingOverlay(full_screen)
                self.overlay_selector.area_captured.connect(self._on_area_selected)
                self.overlay_selector.canceled.connect(self.show)
                self.overlay_selector.show()
        except Exception as e:
            if callable(log_message):
                log_message(f"Error abriendo selector de área para juego: {e}")

    def _on_area_selected(self, pixmap, rect: QRect):
        if rect.isValid() and rect.width() > 30 and rect.height() > 20:
            from_lang = "en"
            to_lang = "es"
            if self.config_manager:
                from_lang = self.config_manager.get("translate_from_lang") or "en"
                to_lang = self.config_manager.get("translate_to_lang") or "es"

            saved = load_saved_game_templates()
            slot_index = self.pending_slot if self.pending_slot else (len(saved) + 1)
            slot_index = max(1, min(9, slot_index))

            default_style = saved[0] if saved else get_default_block_style()

            slot_item = {
                "rect": {"x": rect.x(), "y": rect.y(), "w": rect.width(), "h": rect.height()},
                "from_lang": from_lang,
                "to_lang": to_lang,
                "hotkey_toggle": f"Ctrl+{slot_index}",
                "hotkey_define": f"Ctrl+Shift+{slot_index}",
                "font_color": default_style.get("font_color", "#60CDFF"),
                "font_size": default_style.get("font_size", 13),
                "font_bold": default_style.get("font_bold", True),
                "text_border": default_style.get("text_border", True),
                "text_border_color": default_style.get("text_border_color", "#000000"),
                "bg_color": default_style.get("bg_color", "#000000"),
                "bg_opacity": default_style.get("bg_opacity", 60),
                "box_border_color": default_style.get("box_border_color", "#0078D4"),
                "box_border_width": default_style.get("box_border_width", 2)
            }

            if slot_index <= len(saved):
                saved[slot_index - 1] = slot_item
            else:
                saved.append(slot_item)

            save_game_templates_data(saved)

            if slot_index in self.active_overlays and self.active_overlays[slot_index] is not None:
                try:
                    self.active_overlays[slot_index].close()
                    self.active_overlays[slot_index].deleteLater()
                except Exception:
                    pass

            ov = GameTranslationOverlay(rect, from_lang, to_lang, slot_index, slot_item)
            ov.show()
            self.active_overlays[slot_index] = ov

            self.load_saved_templates_ui()

    def load_saved_templates_ui(self):
        if hasattr(self, "sub_lbl_shortcuts") and self.sub_lbl_shortcuts:
            str_launch_hk = get_game_launch_hotkey()
            self.sub_lbl_shortcuts.setText(f"💡 Atajos directos:\n• Alternar/Destruir Bloques: [Ctrl+1] a [Ctrl+9]\n• Recortar/Redefinir Área: [Ctrl+Shift+1] a [Ctrl+Shift+9]\n• Iniciar Traducción en Vivo: [{str_launch_hk}]")

        self.list_templates.clear()
        saved = load_saved_game_templates()
        if not saved:
            self.list_templates.addItem("No hay bloques configurados en esta plantilla. Usa '➕ Recortar Área Bloque' o presiona el atajo de recorte.")
            return

        for idx, item in enumerate(saved[:9]):
            slot_n = idx + 1
            is_active = (slot_n in self.active_overlays and self.active_overlays[slot_n] is not None and self.active_overlays[slot_n].isVisible())
            status_tag = "🟢 ACTIVO" if is_active else "🔴 INACTIVO"
            r = item["rect"]
            str_tog = item.get("hotkey_toggle", f"Ctrl+{slot_n}")
            str_def = item.get("hotkey_define", f"Ctrl+Shift+{slot_n}")
            txt = f"Bloque [{slot_n}] ({status_tag}) ➔ On/Off: [{str_tog}] | Recortar: [{str_def}] | {r['w']}x{r['h']} px"
            self.list_templates.addItem(QListWidgetItem(txt))

    def launch_saved_templates(self):
        self.stop_all_overlays()
        saved = load_saved_game_templates()
        if not saved:
            print("[LOG TRADUCCION] No hay bloques configurados en la plantilla activa. Iniciando recortador para el Bloque [1]...", flush=True)
            self.pending_slot = 1
            self._start_area_selection()
            return

        for idx, item in enumerate(saved):
            slot_n = idx + 1
            r = item.get("rect")
            if r:
                rect = QRect(r["x"], r["y"], r["w"], r["h"])
                ov = GameTranslationOverlay(rect, item.get("from_lang", "en"), item.get("to_lang", "es"), slot_n, item)
                ov.show()
                self.active_overlays[slot_n] = ov
        self.load_saved_templates_ui()

    def stop_all_overlays(self):
        for ov in self.active_overlays.values():
            if ov is not None:
                try:
                    ov.close()
                    ov.deleteLater()
                except Exception:
                    pass
        self.active_overlays.clear()
        self.load_saved_templates_ui()

    def closeEvent(self, event):
        if hasattr(self, "hk_thread") and self.hk_thread:
            self.hk_thread.stop()
        super().closeEvent(event)