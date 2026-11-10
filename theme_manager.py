# -*- coding: utf-8 -*-
"""
theme_manager.py - Gestor centralizado de temas y UX para Jade.
Permite detección reactiva en tiempo real del modo Oscuro / Claro de Windows 10 y 11,
sincronización instantánea con todas las ventanas hijas de la aplicación,
y paletas de diseño con alto contraste y máxima legibilidad en ambos modos.
"""

import sys
import os
import json
import ctypes
import winreg
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QColor

# API de Windows DWM para modo oscuro en barra de título
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19


import shutil

_MIGRATED = False

def migrate_from_jade_if_needed(perla_appdata: str):
    """Migra configuraciones, plantillas y binarios de Jade hacia Perla automáticamente."""
    global _MIGRATED
    if _MIGRATED:
        return
    _MIGRATED = True
    jade_appdata = os.path.expanduser(r"~\AppData\Roaming\Jade")
    if not os.path.exists(jade_appdata):
        return
    try:
        for fn in ["config.json", "game_templates.json", "galeria.json", "gallery_profile.json", "excluir.json", "ocr_corrections.json", "expressions.json"]:
            src = os.path.join(jade_appdata, fn)
            dst = os.path.join(perla_appdata, fn)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    if fn == "config.json":
                        with open(src, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        for key in ["images_folder", "videos_folder", "audios_folder"]:
                            if key in cfg and isinstance(cfg[key], str) and "Jade" in cfg[key]:
                                cfg[key] = cfg[key].replace("Jade", "Perla")
                        with open(dst, "w", encoding="utf-8") as f:
                            json.dump(cfg, f, indent=4, ensure_ascii=False)
                    else:
                        shutil.copy2(src, dst)
                except Exception:
                    pass

        src_bin = os.path.join(jade_appdata, "bin")
        dst_bin = os.path.join(perla_appdata, "bin")
        if os.path.exists(src_bin):
            for item in os.listdir(src_bin):
                s_item = os.path.join(src_bin, item)
                d_item = os.path.join(dst_bin, item)
                if not os.path.exists(d_item):
                    try:
                        if os.path.isfile(s_item):
                            shutil.copy2(s_item, d_item)
                        elif os.path.isdir(s_item):
                            shutil.copytree(s_item, d_item)
                    except Exception:
                        pass
    except Exception:
        pass


def get_jade_appdata_dir() -> str:
    """Retorna la ruta centralizada de AppData/Roaming/Jade."""
    appdata = os.path.expanduser(r"~\AppData\Roaming\Jade")
    os.makedirs(appdata, exist_ok=True)
    os.makedirs(os.path.join(appdata, "bin"), exist_ok=True)
    os.makedirs(os.path.join(appdata, "logs"), exist_ok=True)
    os.makedirs(os.path.join(appdata, "cache", "galeria_thumbs"), exist_ok=True)
    os.makedirs(os.path.join(appdata, "cache", "galeria_reels"), exist_ok=True)
    
    # Sincronizar desde Perla si existen datos ahí
    perla_appdata = os.path.expanduser(r"~\AppData\Roaming\Perla")
    if os.path.exists(perla_appdata):
        for fn in ["config.json", "game_templates.json", "galeria.json", "gallery_profile.json", "excluir.json", "ocr_corrections.json", "expressions.json"]:
            src = os.path.join(perla_appdata, fn)
            dst = os.path.join(appdata, fn)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass
    return appdata

# Alias de compatibilidad
get_perla_appdata_dir = get_jade_appdata_dir


def detect_windows_system_theme() -> str:
    """Detecta de forma instantánea si Windows está en modo claro u oscuro."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "claro" if val == 1 else "oscuro"
    except Exception:
        return "oscuro"


def enable_win11_effects(hwnd: int, dark_mode: bool = True):
    """Aplica el tema oscuro o claro nativo de Windows 10/11 en la barra de título."""
    if not hwnd or sys.platform != "win32":
        return
    try:
        val = ctypes.c_int(1 if dark_mode else 0)
        # Intentar atributo moderno (Win 11 y Win 10 20H1+)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val)
        )
        if res != 0:
            # Fallback para compilaciones anteriores de Win 10
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(val), ctypes.sizeof(val)
            )
    except Exception:
        pass


class ThemePalette:
    """Definición de paleta de colores semántica de alta legibilidad para Jade."""

    @staticmethod
    def get(is_dark: bool) -> dict:
        if is_dark:
            return {
                "is_dark": True,
                # Fondos
                "bg_window": "#0F1218",
                "bg_card": "#181C24",
                "bg_card_hover": "#222734",
                "bg_input": "#141720",
                "bg_panel": "rgba(18, 22, 32, 0.94)",
                "bg_floating": "rgba(15, 18, 26, 0.96)",
                # Textos
                "text_primary": "#F8FAFC",
                "text_secondary": "#94A3B8",
                "text_muted": "#64748B",
                # Acento y estados
                "accent": "#0078D4",
                "accent_hover": "#106EBE",
                "accent_pressed": "#005A9E",
                "accent_light": "#60CDFF",
                "danger": "#EF4444",
                "danger_hover": "#DC2626",
                "danger_bg": "rgba(239, 68, 68, 0.16)",
                "danger_text": "#FCA5A5",
                "success": "#10B981",
                "success_bg": "rgba(16, 185, 129, 0.16)",
                "warning": "#F59E0B",
                # Bordes
                "border": "rgba(255, 255, 255, 0.10)",
                "border_strong": "rgba(255, 255, 255, 0.20)",
                "border_focus": "#0078D4",
                # Elementos específicos
                "scroll_handle": "#374151",
                "scroll_handle_hover": "#4B5563",
                "tooltip_bg": "#1E222D",
                "tooltip_text": "#F8FAFC",
                "tooltip_border": "rgba(255, 255, 255, 0.15)",
                "menu_bg": "#181C24",
                "menu_hover": "#0078D4",
                "tab_inactive_bg": "#141720",
                "tab_inactive_text": "#94A3B8",
                "tab_active_bg": "#0078D4",
                "tab_active_text": "#FFFFFF",
                "placeholder_thumb": "#161B26",
                "icon_color": "#F8FAFC",
                "nav_pill_bg": "rgba(18, 22, 32, 0.88)",
                "nav_pill_border": "rgba(255, 255, 255, 0.16)",
                "sidebar_bg": "#141720",
                "sidebar_border": "rgba(255, 255, 255, 0.08)",
                "nav_btn_hover": "rgba(255, 255, 255, 0.08)",
                "nav_btn_checked_bg": "rgba(255, 255, 255, 0.14)",
                "nav_btn_accent": "#60CDFF",
            }
        else:
            return {
                "is_dark": False,
                # Fondos
                "bg_window": "#F8FAFC",
                "bg_card": "#FFFFFF",
                "bg_card_hover": "#F1F5F9",
                "bg_input": "#FFFFFF",
                "bg_panel": "rgba(255, 255, 255, 0.96)",
                "bg_floating": "rgba(255, 255, 255, 0.97)",
                # Textos de alto contraste (totalmente legibles sobre blanco)
                "text_primary": "#0F172A",
                "text_secondary": "#334155",
                "text_muted": "#64748B",
                # Acento y estados
                "accent": "#0078D4",
                "accent_hover": "#106EBE",
                "accent_pressed": "#005A9E",
                "accent_light": "#005A9E",
                "danger": "#DC2626",
                "danger_hover": "#B91C1C",
                "danger_bg": "#FEE2E2",
                "danger_text": "#991B1B",
                "success": "#059669",
                "success_bg": "#D1FAE5",
                "warning": "#D97706",
                # Bordes
                "border": "rgba(0, 0, 0, 0.12)",
                "border_strong": "rgba(0, 0, 0, 0.24)",
                "border_focus": "#0078D4",
                # Elementos específicos
                "scroll_handle": "#CBD5E1",
                "scroll_handle_hover": "#94A3B8",
                "tooltip_bg": "#FFFFFF",
                "tooltip_text": "#0F172A",
                "tooltip_border": "#CBD5E1",
                "menu_bg": "#FFFFFF",
                "menu_hover": "#0078D4",
                "tab_inactive_bg": "#E2E8F0",
                "tab_inactive_text": "#475569",
                "tab_active_bg": "#0078D4",
                "tab_active_text": "#FFFFFF",
                "placeholder_thumb": "#E2E8F0",
                "icon_color": "#1E293B",
                "nav_pill_bg": "rgba(255, 255, 255, 0.94)",
                "nav_pill_border": "rgba(0, 0, 0, 0.14)",
                "sidebar_bg": "#FFFFFF",
                "sidebar_border": "rgba(0, 0, 0, 0.10)",
                "nav_btn_hover": "rgba(0, 0, 0, 0.06)",
                "nav_btn_checked_bg": "rgba(0, 120, 212, 0.12)",
                "nav_btn_accent": "#0078D4",
            }

    @staticmethod
    def get_menu_style(is_dark: bool) -> str:
        """Retorna una hoja de estilo QMenu 100% reactiva y dinámica para menús contextuales."""
        p = ThemePalette.get(is_dark)
        return f"""
            QMenu {{
                background-color: {p['menu_bg']};
                color: {p['text_primary']};
                border: 1px solid {p['border_strong']};
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }}
            QMenu::item {{
                background-color: transparent;
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: {p['text_primary']};
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {p['accent']};
                color: #FFFFFF;
            }}
            QMenu::item:disabled {{
                color: {p['text_muted']};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {p['border']};
                margin: 4px 6px;
            }}
        """


class ThemeManager(QObject):
    """
    Gestor maestro de temas de Jade.
    Controla el tema activo ('sistema', 'oscuro', 'claro'),
    escucha cambios en Windows y notifica a todas las ventanas suscritas.
    """
    theme_changed = pyqtSignal(str, bool)  # (effective_theme_str, is_dark_bool)

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.config_theme = "sistema"
        self._last_detected_system_theme = detect_windows_system_theme()
        self._effective_theme = self._calc_effective_theme()
        self._is_dark = (self._effective_theme == "oscuro")
        self._registered_children = set()

        # Timer de verificación reactiva de Windows (cada 1s, ultraligero <0.05ms)
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(1000)
        self._watch_timer.timeout.connect(self._check_system_change)
        self._watch_timer.start()

    def set_config_theme(self, theme_mode: str):
        """Establece el tema desde la configuración ('sistema', 'oscuro', 'claro')."""
        if theme_mode not in ("sistema", "oscuro", "claro"):
            theme_mode = "sistema"
        if self.config_theme != theme_mode:
            self.config_theme = theme_mode
            self._update_and_emit(force=True)

    def set_theme(self, theme_mode: str):
        self.set_config_theme(theme_mode)

    def _calc_effective_theme(self) -> str:
        if self.config_theme in ("oscuro", "claro"):
            return self.config_theme
        return detect_windows_system_theme()

    def _check_system_change(self):
        if self.config_theme == "sistema":
            current_sys = detect_windows_system_theme()
            if current_sys != self._last_detected_system_theme:
                self._last_detected_system_theme = current_sys
                self._update_and_emit()

    def _update_and_emit(self, force: bool = False):
        new_effective = self._calc_effective_theme()
        new_is_dark = (new_effective == "oscuro")

        if force or (new_effective != self._effective_theme):
            self._effective_theme = new_effective
            self._is_dark = new_is_dark
            # Aplicar a la aplicación global
            self.apply_global_styles()
            # Notificar a todas las ventanas suscritas
            self.theme_changed.emit(self._effective_theme, self._is_dark)

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    @property
    def effective_theme(self) -> str:
        return self._effective_theme

    def get_palette(self) -> dict:
        return ThemePalette.get(self._is_dark)

    def register_child(self, child_widget: QWidget):
        """Registra un widget/ventana hija para que reciba cambios de tema de forma garantizada."""
        if child_widget and child_widget not in self._registered_children:
            self._registered_children.add(child_widget)
            try:
                child_widget.destroyed.connect(lambda: self._registered_children.discard(child_widget))
            except Exception:
                pass
            # Aplicar inmediatamente el tema actual
            try:
                if hasattr(child_widget, "winId") and callable(getattr(child_widget, "isWindow", None)) and child_widget.isWindow():
                    enable_win11_effects(int(child_widget.winId()), dark_mode=self._is_dark)
                if hasattr(child_widget, "apply_theme") and callable(child_widget.apply_theme):
                    try:
                        child_widget.apply_theme(self._is_dark)
                    except TypeError:
                        child_widget.apply_theme()
            except Exception:
                pass

    def apply_global_styles(self):
        """Aplica la hoja de estilo global a QApplication y barras de título a topLevelWidgets."""
        app = QApplication.instance()
        if not app:
            return

        p = self.get_palette()
        style = f"""
            QMainWindow, QDialog, QWidget#CentralWidget {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
            }}
            QWidget {{
                font-family: 'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif;
                color: {p['text_primary']};
            }}
            QToolTip {{
                background-color: {p['tooltip_bg']};
                color: {p['tooltip_text']};
                border: 1px solid {p['tooltip_border']};
                border-radius: 6px;
                padding: 5px 9px;
                font-size: 11px;
            }}
            QScrollArea, QScrollArea > QWidget > QWidget {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 9px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {p['scroll_handle']};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {p['scroll_handle_hover']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 9px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {p['scroll_handle']};
                border-radius: 4px;
                min-width: 24px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {p['scroll_handle_hover']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
                width: 0px;
            }}
            QMenu {{
                background-color: {p['menu_bg']};
                color: {p['text_primary']};
                border: 1px solid {p['border_strong']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: {p['text_primary']};
            }}
            QMenu::item:selected {{
                background-color: {p['accent']};
                color: #FFFFFF;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {p['border']};
                margin: 4px 0px;
            }}
            QTabWidget::pane {{
                border: 1px solid {p['border']};
                background-color: {p['bg_card']};
                border-radius: 12px;
            }}
            QTabBar::tab {{
                background: {p['tab_inactive_bg']};
                color: {p['tab_inactive_text']};
                padding: 9px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                margin-right: 4px;
            }}
            QTabBar::tab:hover {{
                background: {p['bg_card_hover']};
                color: {p['text_primary']};
            }}
            QTabBar::tab:selected {{
                background: {p['tab_active_bg']};
                color: {p['tab_active_text']};
                font-weight: bold;
            }}
            QLineEdit, QTextEdit, QListWidget, QComboBox {{
                background-color: {p['bg_input']};
                color: {p['text_primary']};
                border: 1px solid {p['border_strong']};
                border-radius: 8px;
                padding: 6px 10px;
                selection-background-color: {p['accent']};
                selection-color: #FFFFFF;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border: 1px solid {p['border_focus']};
                background-color: {p['bg_input']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {p['menu_bg']};
                color: {p['text_primary']};
                border: 1px solid {p['border_strong']};
                selection-background-color: {p['accent']};
                selection-color: #FFFFFF;
                border-radius: 6px;
                padding: 4px;
            }}
            QFrame#GalleryCard, QFrame#TextNoteCard, QFrame#ModernCard {{
                background-color: {p['bg_card']};
                border: 1px solid {p['border']};
                border-radius: 12px;
            }}
            QFrame#GalleryCard:hover, QFrame#TextNoteCard:hover, QFrame#ModernCard:hover {{
                background-color: {p['bg_card_hover']};
                border: 1px solid {p['border_focus']};
            }}
            QPushButton {{
                background-color: {p['bg_card']};
                border: 1px solid {p['border_strong']};
                border-radius: 8px;
                padding: 7px 15px;
                color: {p['text_primary']};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {p['bg_card_hover']};
                border: 1px solid {p['accent']};
            }}
            QPushButton:pressed {{
                background-color: {p['bg_input']};
            }}
            QPushButton#PrimaryBtn {{
                background-color: {p['accent']};
                color: #FFFFFF;
                border: none;
                font-weight: bold;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {p['accent_hover']};
            }}
            QPushButton#SecondaryBtn {{
                background-color: {p['bg_card']};
                color: {p['text_primary']};
                border: 1px solid {p['border_strong']};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: {p['bg_card_hover']};
            }}
            QPushButton#DangerBtn {{
                background-color: {p['danger_bg']};
                color: {p['danger_text']};
                border: 1px solid {p['danger']};
            }}
            QPushButton#DangerBtn:hover {{
                background-color: {p['danger']};
                color: #FFFFFF;
            }}
            QLabel#SubTextLabel {{
                color: {p['text_secondary']};
            }}
            QLabel#PrimaryTextLabel {{
                color: {p['text_primary']};
            }}
            QLabel#HighlightTimeLabel {{
                color: {p['accent_light']};
            }}
            QLabel#HighlightNoteLabel {{
                color: {p['warning']};
            }}
            QCheckBox {{
                color: {p['text_primary']};
                spacing: 8px;
            }}
            QProgressBar {{
                background-color: {p['bg_input']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                text-align: center;
                color: {p['text_primary']};
            }}
            QProgressBar::chunk {{
                background-color: {p['accent']};
                border-radius: 5px;
            }}
        """
        app.setStyleSheet(style)

        # Actualizar efectos nativos y tema en todas las ventanas abiertas y widgets registrados
        all_targets = set(app.topLevelWidgets()) | set(self._registered_children)
        for w in list(all_targets):
            try:
                if hasattr(w, "winId") and callable(getattr(w, "isWindow", None)) and w.isWindow():
                    enable_win11_effects(int(w.winId()), dark_mode=self._is_dark)
                if hasattr(w, "apply_theme") and callable(w.apply_theme):
                    try:
                        w.apply_theme(self._is_dark)
                    except TypeError:
                        w.apply_theme()
            except Exception:
                pass
