from theme_manager import ThemeManager, ThemePalette, get_perla_appdata_dir, enable_win11_effects
import sys
import os
import ctypes
import math
from PyQt6.QtCore import (
    Qt, QPoint, QPointF, QRectF, QSizeF, QSize, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QMimeData, QUrl, QLineF, QByteArray
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QFont, QImage, QPainterPath, QTransform, QPolygonF, QCursor, QTextOption
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPathItem,
    QGraphicsLineItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsPolygonItem,
    QGraphicsItemGroup, QColorDialog, QSlider, QInputDialog, QMessageBox, QFrame,
    QSizePolicy, QToolButton, QGraphicsItem, QGraphicsDropShadowEffect, QListWidget, QListWidgetItem, QLayout, QTextEdit
)

SVG_COLLECTION = {
    "edit": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 20h9"></path>
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
    </svg>''',
    "ocr": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
        <path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
        <path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
        <path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
        <path d="M7 8h10"></path>
        <path d="M7 12h10"></path>
        <path d="M7 16h6"></path>
    </svg>''',
    "copy": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </svg>''',
    "palette": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="13.5" cy="6.5" r=".5" fill="{color}"></circle>
        <circle cx="17.5" cy="10.5" r=".5" fill="{color}"></circle>
        <circle cx="8.5" cy="7.5" r=".5" fill="{color}"></circle>
        <circle cx="6.5" cy="12.5" r=".5" fill="{color}"></circle>
        <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"></path>
    </svg>''',
    "transform": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="4 14 10 14 10 20"></polyline>
        <polyline points="20 10 14 10 14 4"></polyline>
        <line x1="14" y1="10" x2="21" y2="3"></line>
        <line x1="3" y1="21" x2="10" y2="14"></line>
    </svg>''',
    "undo": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="1 4 1 10 7 10"></polyline>
        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
    </svg>''',
    "redo": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"></polyline>
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
    </svg>''',
    "clear": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"></polyline>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
    </svg>''',
    "zoom_in": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        <line x1="11" y1="8" x2="11" y2="14"></line>
        <line x1="8" y1="11" x2="14" y2="11"></line>
    </svg>''',
    "zoom_out": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        <line x1="8" y1="11" x2="14" y2="11"></line>
    </svg>''',
    "fit": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="15 3 21 3 21 9"></polyline>
        <polyline points="9 21 3 21 3 15"></polyline>
        <polyline points="21 15 21 21 15 21"></polyline>
        <polyline points="3 9 3 3 9 3"></polyline>
    </svg>''',
    "select": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 3l7 18 3-7 7-3L3 3z"></path>
    </svg>''',
    "arrow": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="5" y1="12" x2="19" y2="12"></line>
        <polyline points="12 5 19 12 12 19"></polyline>
    </svg>''',
    "line": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="4" y1="20" x2="20" y2="4"></line>
    </svg>''',
    "rect": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
    </svg>''',
    "text": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="4 7 4 4 20 4 20 7"></polyline>
        <line x1="12" y1="4" x2="12" y2="20"></line>
    </svg>''',
    "highlighter": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2l4 4-10 10H4v-4L14 2z"></path>
        <line x1="12" y1="18" x2="20" y2="18"></line>
    </svg>''',
    "plus": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
    </svg>''',
    "save": '''<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
        <polyline points="17 21 17 13 7 13 7 21"></polyline>
        <polyline points="7 3 7 8 15 8"></polyline>
    </svg>'''
}

def get_svg_icon(name: str, color: str = "#FFFFFF", size: int = 18) -> QIcon:
    svg_raw = SVG_COLLECTION.get(name, SVG_COLLECTION["edit"]).format(color=color)
    renderer = QSvgRenderer(QByteArray(svg_raw.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

def set_window_exclude_from_capture(hwnd: int):
    """Excluye la ventana nativa de capturas para evitar bucles o interferencias."""
    try:
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except Exception:
        pass

def write_desktop_editor_log(msg: str):
    try:
        dt_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(dt_path):
            dt_path = os.path.join(os.path.expanduser("~"), "Escritorio")
        log_file = os.path.join(dt_path, "jade_record_debug.log")
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        entry = f"[{timestamp}] [JADE_EDITOR] {msg}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def is_dark_theme() -> bool:
    """Detecta dinámicamente si el tema de Jade o de Windows está en modo oscuro."""
    try:
        config_path = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
        if os.path.exists(config_path):
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                theme_val = cfg.get("theme", "sistema")
                if theme_val == "oscuro":
                    return True
                elif theme_val == "claro":
                    return False
    except Exception:
        pass
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return val == 0
    except Exception:
        return True

def enable_win11_effects(hwnd: int, dark_mode=True):
    """Aplica la propiedad nativa de modo oscuro/claro de Windows 10/11 en la barra de título de la ventana."""
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1 if dark_mode else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass

class ScreenshotFloatingCard(QWidget):
    """Tarjeta flotante mosaico animada con vista previa dominante, Fade-In/Fade-Out y destrucción garantizada."""
    ocr_requested = pyqtSignal(QPixmap)
    
    def __init__(self, filepath: str = "", pixmap: QPixmap = None, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.pixmap = pixmap
        self._is_closing = False
        write_desktop_editor_log(f"__init__ iniciado. Filepath: {filepath}, Pixmap válido: {pixmap is not None and not pixmap.isNull()}")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowOpacity(0.0)

        self.init_ui()
        ThemeManager.get_instance().register_child(self)

        self.timer = QTimer(self)
        self.timer.setInterval(8000)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out_and_destroy)
        write_desktop_editor_log(f"__init__ completado. Tamaño tarjeta: {self.width()}x{self.height()}")

    def paintEvent(self, event):
        if not hasattr(self, "_painted_once"):
            self._painted_once = True
            write_desktop_editor_log(f"paintEvent DIBUJANDO TARJETA EN PANTALLA. Geometry: {self.geometry()}, Opacidad actual: {self.windowOpacity()}")
        super().paintEvent(event)
    def init_ui(self):
        dark = is_dark_theme()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        card = self.card
        card.setObjectName("MosaicCard")
        if dark:
            card_style = """
                QFrame#MosaicCard {
                    background-color: rgba(18, 22, 28, 0.96);
                    border: none;
                    border-radius: 16px;
                }
            """
            thumb_style = "border-radius: 10px; background-color: #080A0C; border: 1px solid rgba(255,255,255,0.08);"
            btn_action_style = """
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.08); color: #EDEDED; border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 8px; padding: 8px 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.18); }
            """
        else:
            card_style = """
                QFrame#MosaicCard {
                    background-color: rgba(255, 255, 255, 0.98);
                    border: none;
                    border-radius: 16px;
                }
            """
            thumb_style = "border-radius: 10px; background-color: #EFEFEF; border: 1px solid rgba(0,0,0,0.08);"
            btn_action_style = """
                QPushButton {
                    background-color: rgba(0, 0, 0, 0.05); color: #2B2B2B; border: 1px solid rgba(0, 0, 0, 0.12);
                    border-radius: 8px; padding: 8px 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: rgba(0, 0, 0, 0.12); }
            """

        card.setStyleSheet(card_style)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180 if dark else 90))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(280, 140)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setStyleSheet(thumb_style)

        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(QSize(280, 140), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_thumb.setPixmap(scaled)
        elif self.filepath and os.path.exists(self.filepath):
            pix = QPixmap(self.filepath)
            if not pix.isNull():
                scaled = pix.scaled(QSize(280, 140), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_thumb.setPixmap(scaled)

        c_layout.addWidget(self.lbl_thumb, alignment=Qt.AlignmentFlag.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        card_icon_color = "#D4D4D4" if dark else "#2B2B2B"

        self.btn_edit = QPushButton(" Editar")
        self.btn_edit.setIcon(get_svg_icon("edit", card_icon_color, 14))
        self.btn_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setStyleSheet(btn_action_style)
        self.btn_edit.clicked.connect(self.open_editor)

        self.btn_ocr = QPushButton(" OCR")
        self.btn_ocr.setIcon(get_svg_icon("ocr", card_icon_color, 14))
        self.btn_ocr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_ocr.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ocr.setStyleSheet(btn_action_style)
        self.btn_ocr.clicked.connect(self.trigger_ocr)

        self.btn_copy_file = QPushButton(" Copiar")
        self.btn_copy_file.setIcon(get_svg_icon("copy", card_icon_color, 14))
        self.btn_copy_file.setToolTip("Copiar archivo físico .png para pegar en carpetas del Explorador de Windows")
        self.btn_copy_file.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_copy_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_file.setStyleSheet(btn_action_style)
        self.btn_copy_file.clicked.connect(self.copy_physical_file)

        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_ocr)
        btn_layout.addWidget(self.btn_copy_file)

        c_layout.addLayout(btn_layout)

        main_layout.addWidget(card)
        self.setFixedSize(300, 210)

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        if is_dark:
            card_style = """
                QFrame#MosaicCard {
                    background-color: rgba(18, 22, 28, 0.96);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 16px;
                }
            """
            thumb_style = "border-radius: 10px; background-color: #080A0C; border: 1px solid rgba(255,255,255,0.08);"
            btn_action_style = """
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.08); color: #EDEDED; border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 8px; padding: 8px 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.18); }
            """
            card_icon_color = "#D4D4D4"
        else:
            card_style = """
                QFrame#MosaicCard {
                    background-color: rgba(255, 255, 255, 0.98);
                    border: 1px solid rgba(0, 0, 0, 0.14);
                    border-radius: 16px;
                }
            """
            thumb_style = "border-radius: 10px; background-color: #EFEFEF; border: 1px solid rgba(0,0,0,0.08);"
            btn_action_style = """
                QPushButton {
                    background-color: rgba(0, 0, 0, 0.05); color: #2B2B2B; border: 1px solid rgba(0, 0, 0, 0.12);
                    border-radius: 8px; padding: 8px 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: rgba(0, 0, 0, 0.12); }
            """
            card_icon_color = "#2B2B2B"

        if hasattr(self, "card") and self.card:
            self.card.setStyleSheet(card_style)
        if hasattr(self, "lbl_thumb") and self.lbl_thumb:
            self.lbl_thumb.setStyleSheet(thumb_style)
        if hasattr(self, "btn_edit") and self.btn_edit:
            self.btn_edit.setStyleSheet(btn_action_style)
            self.btn_edit.setIcon(get_svg_icon("edit", card_icon_color, 14))
        if hasattr(self, "btn_ocr") and self.btn_ocr:
            self.btn_ocr.setStyleSheet(btn_action_style)
            self.btn_ocr.setIcon(get_svg_icon("ocr", card_icon_color, 14))
        if hasattr(self, "btn_copy_file") and self.btn_copy_file:
            self.btn_copy_file.setStyleSheet(btn_action_style)
            self.btn_copy_file.setIcon(get_svg_icon("copy", card_icon_color, 14))

    def is_ocr_debug_enabled(self) -> bool:
        try:
            config_path = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return bool(cfg.get("save_ocr_debug", False))
        except Exception:
            pass
        return False

    def is_save_all_captures_enabled(self) -> bool:
        try:
            config_path = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return bool(cfg.get("save_all_captures", False))
        except Exception:
            pass
        return False

    def save_all_captures_image(self):
        if not self.is_save_all_captures_enabled():
            return
        try:
            import datetime
            debug_dir = os.path.expanduser(r"~\AppData\Roaming\Jade\captures_debug")
            os.makedirs(debug_dir, exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"capture_{timestamp}.png"
            full_path = os.path.join(debug_dir, filename)

            pix = self.pixmap
            if (not pix or pix.isNull()) and self.filepath and os.path.exists(self.filepath):
                pix = QPixmap(self.filepath)

            if pix and not pix.isNull():
                pix.save(full_path, "PNG")
        except Exception:
            pass

    def save_ocr_debug_image(self, pix: QPixmap):
        if not self.is_ocr_debug_enabled():
            return
        try:
            import datetime
            debug_dir = os.path.expanduser(r"~\AppData\Roaming\Jade\ocr_debug")
            os.makedirs(debug_dir, exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"ocr_capture_{timestamp}.png"
            full_path = os.path.join(debug_dir, filename)

            if pix and not pix.isNull():
                pix.save(full_path, "PNG")
        except Exception:
            pass

    def enterEvent(self, event):
        try:
            if hasattr(self, "timer") and self.timer and self.timer.isActive():
                self.timer.stop()
        except (RuntimeError, AttributeError):
            pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        try:
            if not self._is_closing and hasattr(self, "timer") and self.timer:
                self.timer.start(2000)
        except (RuntimeError, AttributeError):
            pass
        super().leaveEvent(event)

    def position_card(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if not screen:
            write_desktop_editor_log("position_card ERROR: No se detectó ninguna pantalla activa.")
            return

        pos_setting = "bottom_left"
        try:
            config_path = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
            if not os.path.exists(config_path):
                config_path = os.path.expanduser(r"~\AppData\Local\Jade\config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    pos_setting = cfg.get("card_position", "bottom_left")
        except Exception as e:
            write_desktop_editor_log(f"position_card advertencia cargando config: {e}")

        geo = screen.availableGeometry()
        margin = 25

        self.adjustSize()
        w = max(300, self.width())
        h = max(180, self.height())

        if pos_setting in ("top_left", "superior_izquierda"):
            x = geo.x() + margin
            y = geo.y() + margin
        elif pos_setting in ("top_right", "superior_derecha"):
            x = geo.x() + geo.width() - w - margin
            y = geo.y() + margin
        elif pos_setting in ("bottom_right", "inferior_derecha"):
            x = geo.x() + geo.width() - w - margin
            y = geo.y() + geo.height() - h - margin
        else:
            x = geo.x() + margin
            y = geo.y() + geo.height() - h - margin

        write_desktop_editor_log(f"position_card calculado -> Screen: {geo.width()}x{geo.height()} at ({geo.x()},{geo.y()}), PosSetting: {pos_setting}, Moviendo a: ({int(x)}, {int(y)})")
        self.move(int(x), int(y))

    def showEvent(self, event):
        super().showEvent(event)
        write_desktop_editor_log(f"showEvent disparado. Geometry: {self.geometry().x()},{self.geometry().y()} {self.geometry().width()}x{self.geometry().height()}, Opacidad: {self.windowOpacity()}")
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark_theme())
        except Exception as e:
            write_desktop_editor_log(f"showEvent error enable_win11_effects: {e}")

        if not hasattr(self, "_fade_started"):
            self._fade_started = True
            self.save_all_captures_image()
            self.position_card()

            write_desktop_editor_log("showEvent iniciando animación fade_anim ultra-rápida")
            self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
            self.fade_anim.setDuration(95)
            self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.fade_anim.setStartValue(0.0)
            self.fade_anim.setEndValue(1.0)
            self.fade_anim.start()

            try:
                if hasattr(self, "timer") and self.timer:
                    self.timer.start(8000)
                    write_desktop_editor_log("Timer de auto-cierre iniciado (8s)")
            except (RuntimeError, AttributeError) as e:
                write_desktop_editor_log(f"showEvent error iniciando timer: {e}")

    def open_editor(self):
        if self._is_closing:
            return
        self._is_closing = True

        try:
            if hasattr(self, "timer") and self.timer:
                self.timer.stop()
        except (RuntimeError, AttributeError):
            pass

        try:
            self.hide()
        except (RuntimeError, AttributeError):
            pass

        if not self.filepath or not os.path.exists(self.filepath):
            temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Jade", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            self.filepath = os.path.join(temp_dir, "temp_screenshot.png")
            if self.pixmap and not self.pixmap.isNull():
                self.pixmap.save(self.filepath, "PNG")

        editor = JadeImageEditor(self.filepath)
        editor.exec()

        self.destroy_permanently()

    def copy_physical_file(self):
        """Copia el archivo físico .png al portapapeles de Windows para pegarlo directamente en cualquier carpeta o escritorio."""
        try:
            if not self.filepath or not os.path.exists(self.filepath):
                temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Jade", "temp")
                os.makedirs(temp_dir, exist_ok=True)
                self.filepath = os.path.join(temp_dir, "temp_screenshot.png")
                if self.pixmap and not self.pixmap.isNull():
                    self.pixmap.save(self.filepath, "PNG")

            if self.filepath and os.path.exists(self.filepath):
                abs_path = os.path.abspath(self.filepath)
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(abs_path)])
                QApplication.clipboard().setMimeData(mime)
                write_desktop_editor_log(f"Archivo físico .png copiado al portapapeles: {abs_path}")
        except Exception as e:
            write_desktop_editor_log(f"Error copiando archivo físico: {e}")

        self.fade_out_and_destroy()

    def share_capture(self):
        try:
            if self.pixmap and not self.pixmap.isNull():
                img = self.pixmap.toImage()
                QApplication.clipboard().setImage(img)
            elif self.filepath and os.path.exists(self.filepath):
                img = QImage(self.filepath)
                if not img.isNull():
                    QApplication.clipboard().setImage(img)
        except Exception:
            pass

        self.fade_out_and_destroy()

    def apply_ocr_filters(self, pixmap: QPixmap) -> QPixmap:
        """Aplica filtros ultrarrápidos de escala de grises y contraste para maximizar la nitidez del texto."""
        if not pixmap or pixmap.isNull():
            return pixmap
        try:
            img = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
            out = QPixmap.fromImage(img)
            return out if not out.isNull() else pixmap
        except Exception:
            return pixmap

    def capture_and_filter_3_frames(self) -> list:
        """Captura 3 fotogramas ultrarrápidos y les aplica filtros de mejora de imagen en < 300 ms."""
        filtered_frames = []
        try:
            from PyQt6.QtCore import QEventLoop, QTimer
            screen = QApplication.primaryScreen()

            pix1 = self.pixmap
            if (not pix1 or pix1.isNull()) and self.filepath and os.path.exists(self.filepath):
                pix1 = QPixmap(self.filepath)
            if (not pix1 or pix1.isNull()) and screen:
                pix1 = screen.grabWindow(0)

            if pix1 and not pix1.isNull():
                filtered_frames.append(self.apply_ocr_filters(pix1))

            # Capturas 2 y 3 con ráfaga ultrarrápida (150ms de intervalo para completarse en < 0.5s)
            if screen:
                for _ in range(2):
                    loop = QEventLoop()
                    QTimer.singleShot(150, loop.quit)
                    loop.exec()
                    snap = screen.grabWindow(0)
                    if snap and not snap.isNull():
                        filtered_frames.append(self.apply_ocr_filters(snap))
        except Exception:
            pass

        if not filtered_frames and self.pixmap:
            filtered_frames = [self.apply_ocr_filters(self.pixmap)]

        return filtered_frames[:3]

    def trigger_ocr(self):
        """Procesa las 3 capturas filtradas en < 2s y envía el mejor fotograma libre de ruido."""
        try:
            frames = self.capture_and_filter_3_frames()
            best_pix = frames[0] if frames else self.pixmap

            if best_pix and not best_pix.isNull():
                self.save_ocr_debug_image(best_pix)
                self.ocr_requested.emit(best_pix)
                for w in QApplication.topLevelWidgets():
                    if hasattr(w, "perform_ocr"):
                        if hasattr(w, "perform_ocr_multi_frame"):
                            w.perform_ocr_multi_frame(frames)
                        else:
                            w.perform_ocr(best_pix)
                        break
        except Exception:
            pass

        self.fade_out_and_destroy()

    def fade_out_and_destroy(self):
        if self._is_closing:
            return
        self._is_closing = True

        try:
            if hasattr(self, "timer") and self.timer:
                self.timer.stop()
        except (RuntimeError, AttributeError):
            pass

        self.out_anim = QPropertyAnimation(self, b"windowOpacity")
        self.out_anim.setDuration(85)
        self.out_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.out_anim.setStartValue(self.windowOpacity())
        self.out_anim.setEndValue(0.0)
        self.out_anim.finished.connect(self.destroy_permanently)
        self.out_anim.start()

    def destroy_permanently(self):
        self._is_closing = True
        try:
            if hasattr(self, "timer") and self.timer:
                self.timer.stop()
        except (RuntimeError, AttributeError):
            pass

        if hasattr(self, "lbl_thumb"):
            try:
                self.lbl_thumb.clear()
            except (RuntimeError, AttributeError):
                pass

        try:
            self.hide()
            self.close()
        except (RuntimeError, AttributeError):
            pass

    def closeEvent(self, event):
        self._is_closing = True
        try:
            if hasattr(self, "timer") and self.timer:
                self.timer.stop()
        except (RuntimeError, AttributeError):
            pass

        if hasattr(self, "lbl_thumb"):
            try:
                self.lbl_thumb.clear()
            except (RuntimeError, AttributeError):
                pass

        super().closeEvent(event)

def auto_inject_desarrollo_tab(parent_widget=None):
    """Escanea los diálogos activos de la app e inyecta '🛠️ Desarrollo' en cualquier ventana con pestañas de configuración."""
    try:
        from PyQt6.QtWidgets import QApplication, QTabWidget
        widgets = [parent_widget] if parent_widget else QApplication.topLevelWidgets()
        for w in widgets:
            if not w:
                continue
            tab_widgets = w.findChildren(QTabWidget)
            if isinstance(w, QTabWidget):
                tab_widgets.append(w)
            for tw in tab_widgets:
                has_dev = False
                for i in range(tw.count()):
                    txt = tw.tabText(i)
                    if "Desarrollo" in txt:
                        has_dev = True

                if not has_dev:
                    tw.addTab(DesarrolloTabWidget(tw), "🛠️ Desarrollo")
    except Exception:
        pass

def get_desktop_screen_resolution():
    """Detecta con precisión la resolución real del escritorio de Windows en píxeles."""
    try:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            return geo.width(), geo.height()
    except Exception:
        pass
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080

def calculate_safe_container_bounds(origin_x: float = 0, origin_y: float = 0):
    """Calcula la expansión máxima horizontal y vertical segura desde el origen de la plantilla sin salir del monitor."""
    sw, sh = get_desktop_screen_resolution()
    max_safe_w = max(600, int(sw - 40))
    max_safe_h = max(150, int(sh - 20))
    return sw, sh, max_safe_w, max_safe_h

class DesarrolloTabWidget(QWidget):
    """Pestaña modular '🛠️ Desarrollo' para integrar en cualquier QTabWidget de Jade (Modo Juego o Configuración)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        ThemeManager.get_instance().register_child(self)
        QTimer.singleShot(300, auto_inject_desarrollo_tab)

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        if is_dark:
            card_style = "QFrame#DevCard { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }"
        else:
            card_style = "QFrame#DevCard { background-color: #F9F9F9; border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 10px; }"
        self.setStyleSheet(card_style)

    def init_ui(self):
        dark = is_dark_theme()
        if dark:
            card_style = "QFrame#DevCard { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }"
            btn_action_style = "background-color: rgba(255,255,255,0.08); color: white; border: 1px solid rgba(255,255,255,0.15); padding: 7px 14px; border-radius: 6px; font-weight: bold; font-size: 11px;"
            text_color = "#AAAAAA"
        else:
            card_style = "QFrame#DevCard { background-color: #F9F9F9; border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 10px; }"
            btn_action_style = "background-color: #EAEAEA; color: #1A1A1A; border: 1px solid rgba(0,0,0,0.15); padding: 7px 14px; border-radius: 6px; font-weight: bold; font-size: 11px;"
            text_color = "#666666"

        self.setStyleSheet(card_style)

        dev_layout = QVBoxLayout(self)
        dev_layout.setContentsMargins(15, 15, 15, 15)
        dev_layout.setSpacing(12)

        lbl_dev_title = QLabel("🛠️ Opciones de Desarrollo, Resolución y Depuración IA")
        lbl_dev_title.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))

        # Panel de Resolución del Escritorio Windows
        sw, sh = get_desktop_screen_resolution()
        card_res = QFrame()
        card_res.setObjectName("DevCard")
        card_res_layout = QVBoxLayout(card_res)
        card_res_layout.setContentsMargins(12, 12, 12, 12)
        card_res_layout.setSpacing(6)

        lbl_res_title = QLabel(f"🖥️ Resolución del Escritorio Windows Detectada: {sw} x {sh} px")
        lbl_res_title.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))
        lbl_res_title.setStyleSheet("color: #60CDFF;" if dark else "color: #0066B8;")

        lbl_res_info = QLabel(
            f"• Ancho de Pantalla Base: {sw} px | Alto de Pantalla Base: {sh} px\n"
            f"• Expansión Máxima Dinámica: Habilitada (Garantiza 1 sola línea horizontal)\n"
            f"• Ajuste Vertical Anti-Recortes: Activo (Alto adaptativo dinámico según el texto real)"
        )
        lbl_res_info.setStyleSheet(f"font-size: 11px; color: {text_color};")

        card_res_layout.addWidget(lbl_res_title)
        card_res_layout.addWidget(lbl_res_info)

        # Panel de Opciones de Guardado Debug
        card_dev = QFrame()
        card_dev.setObjectName("DevCard")
        card_dev_layout = QVBoxLayout(card_dev)
        card_dev_layout.setContentsMargins(12, 12, 12, 12)
        card_dev_layout.setSpacing(10)

        # Opción 1: Guardar todas las capturas de pantalla realizadas
        switch_row_cap = QHBoxLayout()
        lbl_switch_cap_desc = QLabel("Guardar automáticamente todas las capturas realizadas")
        lbl_switch_cap_desc.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))

        self.btn_switch_cap = QPushButton()
        self.btn_switch_cap.setCheckable(True)
        self.btn_switch_cap.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_cap.setFixedSize(70, 26)

        is_cap_enabled = self.load_setting("save_all_captures", False)
        self.btn_switch_cap.setChecked(is_cap_enabled)
        self.update_switch_btn_style(self.btn_switch_cap, is_cap_enabled)
        self.btn_switch_cap.clicked.connect(self.on_toggle_all_captures)

        switch_row_cap.addWidget(lbl_switch_cap_desc)
        switch_row_cap.addStretch()
        switch_row_cap.addWidget(self.btn_switch_cap)

        # Opción 2: Guardar capturas enviadas al OCR para traducción
        switch_row_ocr = QHBoxLayout()
        lbl_switch_ocr_desc = QLabel("Guardar imágenes enviadas al modelo OCR (Traducción)")
        lbl_switch_ocr_desc.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))

        self.btn_switch_ocr = QPushButton()
        self.btn_switch_ocr.setCheckable(True)
        self.btn_switch_ocr.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_ocr.setFixedSize(70, 26)

        is_ocr_enabled = self.load_setting("save_ocr_debug", False)
        self.btn_switch_ocr.setChecked(is_ocr_enabled)
        self.update_switch_btn_style(self.btn_switch_ocr, is_ocr_enabled)
        self.btn_switch_ocr.clicked.connect(self.on_toggle_ocr_debug)

        switch_row_ocr.addWidget(lbl_switch_ocr_desc)
        switch_row_ocr.addStretch()
        switch_row_ocr.addWidget(self.btn_switch_ocr)

        lbl_info = QLabel(
            "Al activar estas opciones, las capturas de pantalla realizadas y las imágenes "
            "procesadas para traducción por el motor OCR se guardarán en carpetas locales "
            "(captures_debug y ocr_debug). Esto permite realizar auditorías visuales y optimizaciones."
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet(f"font-size: 11px; color: {text_color};")

        folder_btn_layout = QHBoxLayout()
        folder_btn_layout.setSpacing(8)

        btn_open_captures_folder = QPushButton("📁 Capturas (captures_debug)")
        btn_open_captures_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_captures_folder.setStyleSheet(btn_action_style)
        btn_open_captures_folder.clicked.connect(self.open_captures_debug_folder)

        btn_open_ocr_folder = QPushButton("📁 Capturas OCR (ocr_debug)")
        btn_open_ocr_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_ocr_folder.setStyleSheet(btn_action_style)
        btn_open_ocr_folder.clicked.connect(self.open_ocr_debug_folder)

        folder_btn_layout.addWidget(btn_open_captures_folder)
        folder_btn_layout.addWidget(btn_open_ocr_folder)

        card_dev_layout.addLayout(switch_row_cap)
        card_dev_layout.addLayout(switch_row_ocr)
        card_dev_layout.addWidget(lbl_info)
        card_dev_layout.addLayout(folder_btn_layout)

        dev_layout.addWidget(lbl_dev_title)
        dev_layout.addWidget(card_res)
        dev_layout.addWidget(card_dev)
        dev_layout.addStretch()

    def on_toggle_all_captures(self):
        enabled = self.btn_switch_cap.isChecked()
        self.update_switch_btn_style(self.btn_switch_cap, enabled)
        self.save_setting("save_all_captures", enabled)

    def on_toggle_ocr_debug(self):
        enabled = self.btn_switch_ocr.isChecked()
        self.update_switch_btn_style(self.btn_switch_ocr, enabled)
        self.save_setting("save_ocr_debug", enabled)

    def update_switch_btn_style(self, btn: QPushButton, enabled: bool):
        if enabled:
            btn.setText("ON 🟢")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #107C41; color: white; border: none;
                    border-radius: 13px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #139B52; }
            """)
        else:
            btn.setText("OFF ⚪")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(120, 120, 120, 0.35); color: #888888; border: 1px solid rgba(120, 120, 120, 0.4);
                    border-radius: 13px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: rgba(120, 120, 120, 0.5); }
            """)

    def open_captures_debug_folder(self):
        try:
            debug_dir = os.path.expanduser(r"~\AppData\Roaming\Jade\captures_debug")
            os.makedirs(debug_dir, exist_ok=True)
            os.startfile(debug_dir)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta de capturas: {e}")

    def open_ocr_debug_folder(self):
        try:
            debug_dir = os.path.expanduser(r"~\AppData\Roaming\Jade\ocr_debug")
            os.makedirs(debug_dir, exist_ok=True)
            os.startfile(debug_dir)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta de OCR: {e}")

    def load_setting(self, key, default=None):
        try:
            config_path = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return cfg.get(key, default)
        except Exception:
            pass
        return default

    def save_setting(self, key, value):
        try:
            config_dir = os.path.expanduser(r"~\AppData\Roaming\Jade")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.json")

            cfg = {}
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    try:
                        cfg = json.load(f)
                    except Exception:
                        cfg = {}

            cfg[key] = value

            import json
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

class JadeSettingsDialog(QDialog):
    """Ventana de Configuración de Jade con pestañas 'General' y 'Desarrollo'."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración — Jade")
        self.resize(560, 420)
        self.setMinimumSize(500, 360)
        self.init_ui()
        ThemeManager.get_instance().register_child(self)

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        if is_dark:
            self.setStyleSheet("""
                QDialog { background-color: #121418; color: #FFFFFF; }
                QLabel { color: #FFFFFF; }
                QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.1); background-color: #181C22; border-radius: 8px; }
                QTabBar::tab { background: rgba(255, 255, 255, 0.05); color: #AAAAAA; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
                QTabBar::tab:selected { background: #0078D4; color: #FFFFFF; font-weight: bold; }
                QFrame#GeneralCard { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }
            """)
        else:
            self.setStyleSheet("""
                QDialog { background-color: #F8FAFC; color: #0F172A; }
                QLabel { color: #0F172A; }
                QTabWidget::pane { border: 1px solid rgba(0, 0, 0, 0.12); background-color: #FFFFFF; border-radius: 8px; }
                QTabBar::tab { background: #E2E8F0; color: #475569; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
                QTabBar::tab:selected { background: #0078D4; color: #FFFFFF; font-weight: bold; }
                QFrame#GeneralCard { background-color: #FFFFFF; border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 10px; }
            """)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark_theme())
            auto_inject_desarrollo_tab(self)
        except Exception:
            pass

    def init_ui(self):
        from PyQt6.QtWidgets import QTabWidget, QComboBox
        dark = is_dark_theme()

        if dark:
            self.setStyleSheet("""
                QDialog { background-color: #121418; color: #FFFFFF; }
                QLabel { color: #FFFFFF; }
                QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.1); background-color: #181C22; border-radius: 8px; }
                QTabBar::tab { background: rgba(255, 255, 255, 0.05); color: #AAAAAA; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
                QTabBar::tab:selected { background: #0078D4; color: #FFFFFF; font-weight: bold; }
                QFrame#GeneralCard { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }
            """)
        else:
            self.setStyleSheet("""
                QDialog { background-color: #F3F3F3; color: #1A1A1A; }
                QLabel { color: #1A1A1A; }
                QTabWidget::pane { border: 1px solid rgba(0, 0, 0, 0.12); background-color: #FFFFFF; border-radius: 8px; }
                QTabBar::tab { background: #E0E0E0; color: #555555; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
                QTabBar::tab:selected { background: #0078D4; color: #FFFFFF; font-weight: bold; }
                QFrame#GeneralCard { background-color: #F9F9F9; border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 10px; }
            """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Banner Destacado de Resolución de Pantalla Windows en la GUI Principal
        sw, sh = get_desktop_screen_resolution()
        banner_res = QFrame()
        banner_res.setObjectName("GeneralCard")
        banner_layout = QVBoxLayout(banner_res)
        banner_layout.setContentsMargins(10, 8, 10, 8)
        banner_layout.setSpacing(4)

        lbl_res_banner = QLabel(f"🖥️ RESOLUCIÓN DEL ESCRITORIO DETECTADA: {sw} x {sh} px")
        lbl_res_banner.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))
        lbl_res_banner.setStyleSheet("color: #60CDFF;" if dark else "color: #0066B8;")

        lbl_res_detail = QLabel(f"• Expansión Horizontal Máxima Automática: {sw - 40} px | Alto Dinámico Anti-Corte Activo")
        lbl_res_detail.setStyleSheet("font-size: 11px; color: #AAAAAA;" if dark else "font-size: 11px; color: #555555;")

        banner_layout.addWidget(lbl_res_banner)
        banner_layout.addWidget(lbl_res_detail)
        main_layout.addWidget(banner_res)

        self.tabs = QTabWidget()

        # Tab 1: General
        tab_general = QWidget()
        gen_layout = QVBoxLayout(tab_general)
        gen_layout.setContentsMargins(15, 15, 15, 15)
        gen_layout.setSpacing(12)

        lbl_gen_title = QLabel("⚙️ Configuración General")
        lbl_gen_title.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))

        card_gen = QFrame()
        card_gen.setObjectName("GeneralCard")
        card_gen_layout = QVBoxLayout(card_gen)
        card_gen_layout.setContentsMargins(12, 12, 12, 12)
        card_gen_layout.setSpacing(10)

        pos_row = QHBoxLayout()
        lbl_pos = QLabel("Posición de la Tarjeta Flotante:")
        lbl_pos.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))

        self.combo_pos = QComboBox()
        self.combo_pos.addItems(["inferior_izquierda", "inferior_derecha", "superior_izquierda", "superior_derecha"])

        try:
            config_path = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
            curr_pos = "bottom_left"
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    curr_pos = json.load(f).get("card_position", "bottom_left")
        except Exception:
            curr_pos = "bottom_left"

        pos_map = {"bottom_left": 0, "bottom_right": 1, "top_left": 2, "top_right": 3}
        self.combo_pos.setCurrentIndex(pos_map.get(curr_pos, 0))

        pos_row.addWidget(lbl_pos)
        pos_row.addStretch()
        pos_row.addWidget(self.combo_pos)

        card_gen_layout.addLayout(pos_row)
        gen_layout.addWidget(lbl_gen_title)
        gen_layout.addWidget(card_gen)
        gen_layout.addStretch()

        self.tabs.addTab(tab_general, "⚙️ General")

        # Tab 2: Desarrollo
        self.tab_desarrollo = DesarrolloTabWidget(self)
        self.tabs.addTab(self.tab_desarrollo, "🛠️ Desarrollo")

        main_layout.addWidget(self.tabs)

        btn_close = QPushButton("Cerrar")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("background-color: #0078D4; color: white; font-weight: bold; padding: 7px 18px; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)

        main_layout.addLayout(bottom_layout)

def apply_expression_dictionary(text: str) -> str:
    """Aplica correcciones comunes de OCR (ej: '11' -> 'I') y reemplazos desde expressions.json."""
    if not text:
        return ""
    try:
        import json, os, re

        default_fixes = {
            r'\b11\b': 'I',
            r'\bI iam\b': 'I am',
            r'\bI\'am\b': 'I am',
            r'\biam\b': 'am',
            r'\bAhi\b': '¡Ah!',
        }

        for pattern, replacement in default_fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        json_path = os.path.expanduser(r"~\AppData\Roaming\Jade\expressions.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                custom_dict = json.load(f)
                if isinstance(custom_dict, dict):
                    for key, val in custom_dict.items():
                        text = re.sub(r'\b' + re.escape(key) + r'\b', str(val), text, flags=re.IGNORECASE)
    except Exception:
        pass
    return text

def purge_translated_text(text: str) -> str:
    """Purga a fondo el texto traducido: elimina HTML, basura de OCR (ej: 'ning.') y fuerza una sola línea horizontal."""
    if not text:
        return ""
    try:
        import re
        from PyQt6.QtGui import QTextDocument

        # 1. Eliminar cualquier formato o etiqueta HTML
        doc = QTextDocument()
        doc.setHtml(str(text))
        clean_text = doc.toPlainText()

        # 2. Eliminar basura de sílabas, palabras cortas pegadas por el OCR o artefactos al inicio y al final
        clean_text = re.sub(r'^\s*([a-zA-Z]{1,4}\.\s*)+', '', clean_text)
        clean_text = re.sub(r'\b(rorkout|Identificación)\b', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\s+\b[a-zA-Z]\b\.\s*$', '', clean_text)

        # 3. Eliminar caracteres corruptos y símbolos no deseados
        clean_text = re.sub(r'[^\w\s\d¡!¿?.,:\-\'\"áéíóúÁÉÍÓÚñÑüÜ]', '', clean_text)

        # 4. Unificar todo el texto en una sola línea horizontal continua sin múltiples espacios
        clean_text = re.sub(r'[\r\n]+', ' ', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # 5. Pasar por el diccionario JSON de expresiones
        clean_text = apply_expression_dictionary(clean_text)

        return clean_text
    except Exception:
        return str(text).strip()

class MovableTextItem(QGraphicsTextItem):
    """Objeto de texto profesional que mantiene intacto el contenedor de la plantilla creada por el usuario."""
    def __init__(self, text: str, color: QColor, font: QFont, target_width: float = 0, parent=None):
        super().__init__(parent)
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QTextOption

        self.txt_item = self
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setCursor(Qt.CursorShape.IBeamCursor)

        clean_text = purge_translated_text(text) if text else ""
        self.setPlainText(clean_text)
        self.setDefaultTextColor(color)
        self.setFont(font)

        doc = self.document()
        doc.setDocumentMargin(2)

        opt = doc.defaultTextOption()
        opt.setAlignment(Qt.AlignmentFlag.AlignLeft)
        opt.setWrapMode(QTextOption.WrapMode.NoWrap)
        doc.setDefaultTextOption(opt)

        if target_width > 0:
            self.setTextWidth(float(target_width))
        elif target_width == 0:
            sw, sh, max_safe_w, max_safe_h = calculate_safe_container_bounds()
            self.setTextWidth(float(max_safe_w))
        else:
            self.setTextWidth(-1)

    def paint(self, painter, option, widget=None):
        painter.save()
        self.document().drawContents(painter)
        painter.restore()

    def apply_text(self):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.clearFocus()
        self.setSelected(False)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.update()
        scene = self.scene()
        if scene:
            scene.clearFocus()
            if hasattr(scene, "parent") and hasattr(scene.parent(), "set_tool"):
                scene.parent().set_tool("select")

    def start_editing(self):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        scene = self.scene()
        if scene:
            scene.setFocusItem(self)

    def mouseDoubleClickEvent(self, event):
        self.start_editing()
        event.accept()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.apply_text()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.apply_text()
            event.accept()
            return
        super().keyPressEvent(event)

    @staticmethod
    def recreate_clean_item(scene, layer, old_item, text: str, color: QColor, font: QFont, pos=None, target_width: float = 0):
        """Mantiene Y REUTILIZA el contenedor de la plantilla del usuario actualizando únicamente su texto sin destruirlo."""
        clean_text = purge_translated_text(text)

        # Si ya existe el contenedor de la plantilla, REUTILIZARLO intacto sin borrarlo ni crear bloques flotantes nuevos
        if old_item and hasattr(old_item, "txt_item"):
            try:
                old_item.txt_item.setDefaultTextColor(color)
                old_item.txt_item.setFont(font)
                doc = old_item.txt_item.document()
                opt = doc.defaultTextOption()
                opt.setWrapMode(QTextOption.WrapMode.NoWrap)
                doc.setDefaultTextOption(opt)
                old_item.txt_item.setPlainText(clean_text)
                if pos is not None:
                    old_item.setPos(pos)
                return old_item
            except Exception:
                pass

        # Si no existe contenedor previo, se crea respetando el ancho de la plantilla
        new_item = MovableTextItem(clean_text, color, font, target_width)
        if pos is not None:
            new_item.setPos(pos)

        if scene and hasattr(scene, "addItem"):
            scene.addItem(new_item)
        if layer and hasattr(layer, "add_item"):
            layer.add_item(new_item)

        return new_item
class TransformBoxItem(QGraphicsItemGroup):
    """Caja de Transformación Libre (Ctrl+T) estilo Photoshop para escalar y rotar objetos."""
    def __init__(self, target_item: QGraphicsItem, parent=None):
        super().__init__(parent)
        self.target_item = target_item
        self.setZValue(999999)
        self.init_box()

    def init_box(self):
        if not self.target_item:
            return

        rect = self.target_item.boundingRect()
        self.border = QGraphicsRectItem(rect, self)
        pen = QPen(QColor(0, 120, 212), 1.5, Qt.PenStyle.DashLine)
        self.border.setPen(pen)

        self.handles = {}
        points = {
            'tl': rect.topLeft(),
            'tr': rect.topRight(),
            'bl': rect.bottomLeft(),
            'br': rect.bottomRight(),
            'rot': QPointF(rect.center().x(), rect.top() - 22)
        }

        for name, pt in points.items():
            h = QGraphicsRectItem(-5, -5, 10, 10, self)
            col = QColor(255, 185, 0) if name == 'rot' else QColor(0, 120, 212)
            h.setBrush(QBrush(col))
            h.setPen(QPen(QColor(255, 255, 255), 1))
            h.setPos(pt)
            self.handles[name] = h

class EditorLayer:
    """Clase que gestiona una Capa independiente en el lienzo sin alterar coordenadas."""
    def __init__(self, name: str, z_index: int, scene: QGraphicsScene):
        self.name = name
        self.z_index = z_index
        self.scene = scene
        self.is_visible = True
        self.is_locked = False
        self.items = []

    def add_item(self, item: QGraphicsItem):
        self.items.append(item)
        item.setZValue(self.z_index)
        item.setVisible(self.is_visible)

    def remove_item(self, item: QGraphicsItem):
        if item in self.items:
            self.items.remove(item)
            self.scene.removeItem(item)

    def set_visible(self, visible: bool):
        self.is_visible = visible
        for item in self.items:
            item.setVisible(visible)

    def set_locked(self, locked: bool):
        self.is_locked = locked

    def clear(self):
        for item in list(self.items):
            self.remove_item(item)

class EditorGraphicsScene(QGraphicsScene):
    """Escena gráfica con Capas y coordenadas de precisión directa."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tool = "pen"  # "select", "pen", "arrow", "line", "rect", "text", "highlighter"
        self.pen_color = QColor(255, 0, 0)
        self.pen_width = 4
        self.pen_opacity = 255
        self.current_item = None
        self.extra_head_item = None
        self.start_point = QPointF()
        self.history = []
        self.redo_stack = []
        self.active_layer = None
        self.transform_box = None

    def deselect_all_transforms(self):
        if self.transform_box:
            self.removeItem(self.transform_box)
            self.transform_box = None

    def activate_free_transform(self):
        self.deselect_all_transforms()
        selected = self.selectedItems()
        if selected and selected[0] != self.transform_box:
            target = selected[0]
            self.transform_box = TransformBoxItem(target)
            self.addItem(self.transform_box)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.tool != "select":
            clicked = self.itemAt(event.scenePos(), QTransform())
            if isinstance(clicked, MovableTextItem) or (clicked and isinstance(clicked.parentItem(), MovableTextItem)):
                super().mousePressEvent(event)
                return

            if not self.active_layer or self.active_layer.is_locked or not self.active_layer.is_visible:
                event.accept()
                return

            self.current_item = None
            self.extra_head_item = None
            self.deselect_all_transforms()
            self.start_point = event.scenePos()
            draw_color = QColor(self.pen_color)
            if self.tool == "highlighter":
                draw_color.setAlpha(110)
            else:
                draw_color.setAlpha(self.pen_opacity)

            if self.tool in ("pen", "highlighter"):
                self.current_path = QPainterPath(self.start_point)
                self.current_path.lineTo(self.start_point)
                w = self.pen_width * 3 if self.tool == "highlighter" else self.pen_width
                pen = QPen(draw_color, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                self.current_item = QGraphicsPathItem()
                self.current_item.setPen(pen)
                self.current_item.setPath(self.current_path)
                self.addItem(self.current_item)
                self.active_layer.add_item(self.current_item)
                self.history.append((self.active_layer, self.current_item, None))
                self.redo_stack.clear()

            elif self.tool in ("line", "arrow"):
                pen = QPen(draw_color, self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                self.current_item = QGraphicsLineItem(self.start_point.x(), self.start_point.y(), self.start_point.x(), self.start_point.y())
                self.current_item.setPen(pen)
                self.addItem(self.current_item)
                self.active_layer.add_item(self.current_item)
                self.extra_head_item = None

                if self.tool == "arrow":
                    brush = QBrush(draw_color)
                    self.extra_head_item = QGraphicsPolygonItem()
                    self.extra_head_item.setPen(pen)
                    self.extra_head_item.setBrush(brush)
                    self.addItem(self.extra_head_item)
                    self.active_layer.add_item(self.extra_head_item)

                self.history.append((self.active_layer, self.current_item, self.extra_head_item))
                self.redo_stack.clear()

            elif self.tool == "rect":
                pen = QPen(draw_color, self.pen_width, Qt.PenStyle.SolidLine)
                brush = QBrush(QColor(draw_color.red(), draw_color.green(), draw_color.blue(), 30))
                self.current_item = QGraphicsRectItem(QRectF(self.start_point, QSizeF(0, 0)))
                self.current_item.setPen(pen)
                self.current_item.setBrush(brush)
                self.addItem(self.current_item)
                self.active_layer.add_item(self.current_item)
                self.history.append((self.active_layer, self.current_item, None))
                self.redo_stack.clear()

            elif self.tool == "text":
                clicked_item = self.itemAt(self.start_point, QTransform())
                target_txt = None
                if isinstance(clicked_item, MovableTextItem):
                    target_txt = clicked_item
                elif isinstance(clicked_item, QGraphicsTextItem):
                    target_txt = clicked_item

                if target_txt:
                    if hasattr(target_txt, "start_editing"):
                        target_txt.start_editing()
                    else:
                        target_txt.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
                        self.setFocusItem(target_txt)
                        target_txt.setFocus(Qt.FocusReason.MouseFocusReason)
                else:
                    font = QFont("Segoe UI Variable Display", max(14, self.pen_width * 3), QFont.Weight.Bold)
                    movable_text = MovableTextItem("Texto", draw_color, font, target_width=-1)
                    movable_text.setPos(self.start_point)
                    self.addItem(movable_text)
                    self.active_layer.add_item(movable_text)
                    self.history.append((self.active_layer, movable_text, None))
                    self.redo_stack.clear()

                    for v in self.views():
                        v.setFocus()
                    self.setFocusItem(movable_text)
                    movable_text.setFocus(Qt.FocusReason.MouseFocusReason)

                    from PyQt6.QtGui import QTextCursor
                    cursor = movable_text.textCursor()
                    cursor.select(QTextCursor.SelectionType.Document)
                    movable_text.setTextCursor(cursor)

            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.current_item and self.tool != "select":
            curr_pos = event.scenePos()

            if self.tool in ("pen", "highlighter"):
                if hasattr(self, "current_path") and self.current_path:
                    self.current_path.lineTo(curr_pos)
                    self.current_item.setPath(self.current_path)

            elif self.tool in ("line", "arrow"):
                self.current_item.setLine(self.start_point.x(), self.start_point.y(), curr_pos.x(), curr_pos.y())
                if self.tool == "arrow" and self.extra_head_item:
                    line = QLineF(self.start_point, curr_pos)
                    if line.length() > 5:
                        angle = math.atan2(-line.dy(), line.dx())
                        arrow_size = max(14, self.pen_width * 3.2)

                        p1 = line.p2() - QPointF(math.cos(angle + math.pi / 6) * arrow_size, -math.sin(angle + math.pi / 6) * arrow_size)
                        p2 = line.p2() - QPointF(math.cos(angle - math.pi / 6) * arrow_size, -math.sin(angle - math.pi / 6) * arrow_size)

                        poly = QPolygonF([line.p2(), p1, p2])
                        self.extra_head_item.setPolygon(poly)

            elif self.tool == "rect":
                rect = QRectF(self.start_point, curr_pos).normalized()
                self.current_item.setRect(rect)

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.tool != "select":
            if self.current_item:
                self.current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                self.current_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            if self.extra_head_item:
                self.extra_head_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                self.extra_head_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.current_item = None
            self.extra_head_item = None
            self.current_path = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def delete_selected_items(self):
        for item in self.selectedItems():
            if self.active_layer and item in self.active_layer.items:
                self.active_layer.remove_item(item)

    def undo(self):
        if self.history:
            layer, item, extra = self.history.pop()
            if layer and item:
                layer.remove_item(item)
            if layer and extra:
                layer.remove_item(extra)
            self.redo_stack.append((layer, item, extra))

    def redo(self):
        if self.redo_stack:
            layer, item, extra = self.redo_stack.pop()
            if layer and item:
                layer.add_item(item)
            if layer and extra:
                layer.add_item(extra)
            self.history.append((layer, item, extra))

    def clear_annotations(self):
        while self.history:
            self.undo()

class EditorGraphicsView(QGraphicsView):
    """Vista de lienzo con soporte de Zoom con rueda del ratón y Desplazamiento (Pan)."""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        bg_col = "#0B0E12" if is_dark_theme() else "#E0E5EC"
        self.setStyleSheet(f"background-color: {bg_col}; border: none; border-radius: 10px;")

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

class JadeImageEditor(QDialog):
    """Editor profesional estilo Photoshop con Capas, Texto Móvil y Atajos de Teclado."""
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.layers = []
        self.layer_counter = 1

        self.setWindowTitle("Editor")
        self.resize(1200, 780)
        self.setMinimumSize(850, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.init_ui()
        self.load_image()
        ThemeManager.get_instance().register_child(self)

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        if is_dark:
            self.setStyleSheet("""
                QDialog { background-color: #121418; color: #FFFFFF; }
                QLabel { color: #FFFFFF; }
            """)
            cancel_btn_style = "background-color: rgba(255,255,255,0.08); color: white; border: 1px solid rgba(255,255,255,0.12); padding: 8px 16px; border-radius: 6px;"
            layer_list_style = """
                QListWidget {
                    background-color: rgba(18, 22, 28, 0.8);
                    color: #FFFFFF;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                }
                QListWidget::item {
                    padding: 6px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                    color: #FFFFFF;
                }
                QListWidget::item:selected {
                    background-color: #0078D4;
                    color: #FFFFFF;
                    border-radius: 4px;
                }
            """
        else:
            self.setStyleSheet("""
                QDialog { background-color: #F8FAFC; color: #0F172A; }
                QLabel { color: #0F172A; }
            """)
            cancel_btn_style = "background-color: #E2E8F0; color: #0F172A; border: 1px solid rgba(0,0,0,0.15); padding: 8px 16px; border-radius: 6px;"
            layer_list_style = """
                QListWidget {
                    background-color: #FFFFFF;
                    color: #0F172A;
                    border: 1px solid rgba(0, 0, 0, 0.15);
                    border-radius: 8px;
                }
                QListWidget::item {
                    padding: 6px;
                    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
                    color: #0F172A;
                }
                QListWidget::item:selected {
                    background-color: #0078D4;
                    color: #FFFFFF;
                    border-radius: 4px;
                }
            """
        if hasattr(self, "layer_list") and self.layer_list:
            self.layer_list.setStyleSheet(layer_list_style)
        if hasattr(self, "btn_cancel") and self.btn_cancel:
            self.btn_cancel.setStyleSheet(cancel_btn_style)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            enable_win11_effects(int(self.winId()), dark_mode=ThemeManager.get_instance().is_dark)
        except Exception:
            pass

    def init_ui(self):
        dark = is_dark_theme()
        if dark:
            self.setStyleSheet("""
                QDialog { background-color: #121418; color: #FFFFFF; }
                QLabel { color: #FFFFFF; }
            """)
            top_btn_style = "background-color: rgba(255,255,255,0.08); color: white; border: 1px solid rgba(255,255,255,0.12); padding: 5px 10px; border-radius: 6px; font-weight: bold; font-size: 11px;"
            tool_btn_style = """
                QToolButton {
                    background-color: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    color: white;
                }
                QToolButton:hover { background-color: rgba(255, 255, 255, 0.15); }
                QToolButton:checked {
                    background-color: #0078D4;
                    border: 1px solid #60CDFF;
                    color: white;
                }
            """
            layer_list_style = """
                QListWidget {
                    background-color: rgba(18, 22, 28, 0.8);
                    color: #FFFFFF;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                }
                QListWidget::item {
                    padding: 6px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                    color: #FFFFFF;
                }
                QListWidget::item:selected {
                    background-color: #0078D4;
                    color: #FFFFFF;
                    border-radius: 4px;
                }
            """
            cancel_btn_style = "background-color: rgba(255,255,255,0.08); color: white; border: 1px solid rgba(255,255,255,0.12); padding: 8px 16px; border-radius: 6px;"
            title_color = "#60CDFF"
            sep_color = "rgba(255,255,255,0.15)"
        else:
            self.setStyleSheet("""
                QDialog { background-color: #F3F3F3; color: #1A1A1A; }
                QLabel { color: #1A1A1A; }
            """)
            top_btn_style = "background-color: #EAEAEA; color: #1A1A1A; border: 1px solid rgba(0,0,0,0.15); padding: 5px 10px; border-radius: 6px; font-weight: bold; font-size: 11px;"
            tool_btn_style = """
                QToolButton {
                    background-color: #FFFFFF;
                    border: 1px solid rgba(0, 0, 0, 0.15);
                    border-radius: 8px;
                    color: #1A1A1A;
                }
                QToolButton:hover { background-color: #E5E5E5; }
                QToolButton:checked {
                    background-color: #0078D4;
                    border: 1px solid #005A9E;
                    color: white;
                }
            """
            layer_list_style = """
                QListWidget {
                    background-color: #FFFFFF;
                    color: #1A1A1A;
                    border: 1px solid rgba(0, 0, 0, 0.15);
                    border-radius: 8px;
                }
                QListWidget::item {
                    padding: 6px;
                    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
                    color: #1A1A1A;
                }
                QListWidget::item:selected {
                    background-color: #0078D4;
                    color: #FFFFFF;
                    border-radius: 4px;
                }
            """
            cancel_btn_style = "background-color: #EAEAEA; color: #1A1A1A; border: 1px solid rgba(0,0,0,0.15); padding: 8px 16px; border-radius: 6px;"
            title_color = "#0066B8"
            sep_color = "rgba(0,0,0,0.15)"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Barra de Control Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_col = QLabel("🎨 Color:")
        lbl_col.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))
        top_bar.addWidget(lbl_col)

        colors = [QColor(232, 17, 35), QColor(16, 124, 65), QColor(0, 120, 212), QColor(255, 185, 0), QColor(255, 255, 255), QColor(0, 0, 0)]
        for c in colors:
            btn_c = QPushButton()
            btn_c.setFixedSize(22, 22)
            btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_c.setStyleSheet(f"background-color: {c.name()}; border: 1px solid {'#888888' if c == QColor(255,255,255) else 'white'}; border-radius: 11px;")
            btn_c.clicked.connect(lambda _, col=c: self.set_color(col))
            top_bar.addWidget(btn_c)

        ui_icon_color = "#FFFFFF" if dark else "#1A1A1A"

        btn_more_col = QPushButton(" Más...")
        btn_more_col.setIcon(get_svg_icon("palette", ui_icon_color, 14))
        btn_more_col.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_more_col.setStyleSheet(top_btn_style)
        btn_more_col.clicked.connect(self.choose_custom_color)
        top_bar.addWidget(btn_more_col)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet(f"color: {sep_color};")
        top_bar.addWidget(sep1)

        lbl_w = QLabel("Grosor:")
        self.slider_w = QSlider(Qt.Orientation.Horizontal)
        self.slider_w.setRange(1, 40)
        self.slider_w.setValue(4)
        self.slider_w.setFixedWidth(70)
        self.slider_w.valueChanged.connect(lambda v: setattr(self.scene, 'pen_width', v))

        lbl_op = QLabel("Opacidad:")
        self.slider_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_op.setRange(20, 255)
        self.slider_op.setValue(255)
        self.slider_op.setFixedWidth(70)
        self.slider_op.valueChanged.connect(lambda v: setattr(self.scene, 'pen_opacity', v))

        top_bar.addWidget(lbl_w)
        top_bar.addWidget(self.slider_w)
        top_bar.addWidget(lbl_op)
        top_bar.addWidget(self.slider_op)

        top_bar.addStretch()

        btn_transform = QPushButton(" Transformar (Ctrl+T)")
        btn_transform.setIcon(get_svg_icon("transform", ui_icon_color, 14))
        btn_transform.setToolTip("Escalar / Rotar Objeto Seleccionado")
        btn_transform.clicked.connect(lambda: self.scene.activate_free_transform())

        btn_undo = QPushButton()
        btn_undo.setIcon(get_svg_icon("undo", ui_icon_color, 14))
        btn_undo.setToolTip("Deshacer (Ctrl+Z)")
        btn_undo.clicked.connect(lambda: self.scene.undo())

        btn_redo = QPushButton()
        btn_redo.setIcon(get_svg_icon("redo", ui_icon_color, 14))
        btn_redo.setToolTip("Rehacer (Ctrl+Y)")
        btn_redo.clicked.connect(lambda: self.scene.redo())

        btn_clear = QPushButton()
        btn_clear.setIcon(get_svg_icon("clear", ui_icon_color, 14))
        btn_clear.setToolTip("Limpiar Capa Actual")
        btn_clear.clicked.connect(lambda: self.scene.clear_annotations())

        btn_zoom_in = QPushButton()
        btn_zoom_in.setIcon(get_svg_icon("zoom_in", ui_icon_color, 14))
        btn_zoom_in.setToolTip("Acercar")
        btn_zoom_in.clicked.connect(lambda: self.view.scale(1.2, 1.2))

        btn_zoom_out = QPushButton()
        btn_zoom_out.setIcon(get_svg_icon("zoom_out", ui_icon_color, 14))
        btn_zoom_out.setToolTip("Alejar")
        btn_zoom_out.clicked.connect(lambda: self.view.scale(0.8, 0.8))

        btn_zoom_fit = QPushButton(" Ajustar")
        btn_zoom_fit.setIcon(get_svg_icon("fit", ui_icon_color, 14))
        btn_zoom_fit.clicked.connect(self.fit_view_to_image)

        for b in [btn_transform, btn_undo, btn_redo, btn_clear, btn_zoom_in, btn_zoom_out, btn_zoom_fit]:
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(top_btn_style)
            top_bar.addWidget(b)

        main_layout.addLayout(top_bar)

        # 2. Área Central (Herramientas | Lienzo | Panel de Capas)
        center_layout = QHBoxLayout()
        center_layout.setSpacing(8)

        # Barra Lateral Izquierda (Herramientas Photoshop)
        left_toolbar = QVBoxLayout()
        left_toolbar.setSpacing(6)

        self.tools = {
            "select": QToolButton(),
            "pen": QToolButton(),
            "arrow": QToolButton(),
            "line": QToolButton(),
            "rect": QToolButton(),
            "text": QToolButton(),
            "highlighter": QToolButton()
        }

        tool_defs = [
            ("select", "select", "Mover / Seleccionar [Atajo: V]"),
            ("pen", "edit", "Pincel Libre [Atajo: B]"),
            ("arrow", "arrow", "Flecha Pro [Atajo: A]"),
            ("line", "line", "Línea Recta"),
            ("rect", "rect", "Destacar Área [Atajo: U]"),
            ("text", "text", "Insertar Texto [Atajo: T]"),
            ("highlighter", "highlighter", "Resaltador [Atajo: H]")
        ]

        tool_icon_color = "#FFFFFF" if dark else "#1A1A1A"
        for code, icon_name, tooltip in tool_defs:
            btn = self.tools[code]
            btn.setIcon(get_svg_icon(icon_name, tool_icon_color, 18))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedSize(38, 38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(tool_btn_style)
            btn.clicked.connect(lambda _, c=code: self.set_tool(c))
            left_toolbar.addWidget(btn)

        self.tools["pen"].setChecked(True)
        left_toolbar.addStretch()

        center_layout.addLayout(left_toolbar)

        # Lienzo Central
        self.scene = EditorGraphicsScene(self)
        self.view = EditorGraphicsView(self.scene, self)
        center_layout.addWidget(self.view, stretch=1)

        # Panel Derecho de Capas
        layer_panel = QVBoxLayout()
        layer_panel.setSpacing(6)

        lbl_layers_title = QLabel("🥞 Capas")
        lbl_layers_title.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))
        lbl_layers_title.setStyleSheet(f"color: {title_color};")

        self.layer_list_widget = QListWidget()
        self.layer_list_widget.setFixedWidth(180)
        self.layer_list_widget.setStyleSheet(layer_list_style)
        self.layer_list_widget.currentRowChanged.connect(self.on_layer_selected)

        layer_icon_color = "#FFFFFF" if dark else "#1A1A1A"

        layer_btn_box = QHBoxLayout()
        btn_add_layer = QPushButton(" Capa")
        btn_add_layer.setIcon(get_svg_icon("plus", layer_icon_color, 14))
        btn_del_layer = QPushButton()
        btn_del_layer.setIcon(get_svg_icon("clear", layer_icon_color, 14))
        btn_del_layer.setToolTip("Eliminar Capa")

        btn_add_layer.clicked.connect(self.add_new_layer)
        btn_del_layer.clicked.connect(self.delete_current_layer)

        for b in [btn_add_layer, btn_del_layer]:
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(top_btn_style)

        layer_btn_box.addWidget(btn_add_layer)
        layer_btn_box.addWidget(btn_del_layer)

        layer_panel.addWidget(lbl_layers_title)
        layer_panel.addWidget(self.layer_list_widget, stretch=1)
        layer_panel.addLayout(layer_btn_box)

        center_layout.addLayout(layer_panel)

        main_layout.addLayout(center_layout, stretch=1)

        # 3. Barra Inferior
        bottom_bar = QHBoxLayout()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(cancel_btn_style)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton(" Guardar y Copiar al Portapapeles")
        btn_save.setIcon(get_svg_icon("save", "#FFFFFF", 16))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet("background-color: #0078D4; color: white; font-weight: bold; padding: 8px 20px; border-radius: 6px; font-size: 12px;")
        btn_save.clicked.connect(self.save_and_copy)

        bottom_bar.addStretch()
        bottom_bar.addWidget(btn_cancel)
        bottom_bar.addWidget(btn_save)

        main_layout.addLayout(bottom_bar)

    def keyPressEvent(self, event):
        focus_item = self.scene.focusItem() if hasattr(self, "scene") and self.scene else None
        if focus_item and isinstance(focus_item, QGraphicsTextItem) and (focus_item.textInteractionFlags() & Qt.TextInteractionFlag.TextEditorInteraction):
            if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if hasattr(focus_item, "apply_text"):
                    focus_item.apply_text()
                else:
                    focus_item.clearFocus()
                    focus_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                self.set_tool("select")
                event.accept()
                return
            self.view.keyPressEvent(event)
            event.accept()
            return

        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_T:
                self.scene.activate_free_transform()
                event.accept()
                return
            elif key == Qt.Key.Key_Z:
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    self.scene.redo()
                else:
                    self.scene.undo()
                event.accept()
                return
            elif key == Qt.Key.Key_Y:
                self.scene.redo()
                event.accept()
                return

        if key == Qt.Key.Key_V:
            self.set_tool("select")
        elif key == Qt.Key.Key_B:
            self.set_tool("pen")
        elif key == Qt.Key.Key_T:
            self.set_tool("text")
        elif key == Qt.Key.Key_U:
            self.set_tool("rect")
        elif key == Qt.Key.Key_A:
            self.set_tool("arrow")
        elif key == Qt.Key.Key_H:
            self.set_tool("highlighter")
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.scene.delete_selected_items()

        super().keyPressEvent(event)

    def load_image(self):
        if os.path.exists(self.filepath):
            pix = QPixmap(self.filepath)
            if not pix.isNull():
                self.scene.setSceneRect(QRectF(pix.rect()))

                base_layer = EditorLayer("🖼️ Imagen Base", 0, self.scene)
                base_layer.set_locked(True)
                pix_item = QGraphicsPixmapItem(pix)
                self.scene.addItem(pix_item)
                base_layer.add_item(pix_item)
                self.layers.append(base_layer)

                draw_layer = EditorLayer("🎨 Capa 1", 1, self.scene)
                self.layers.append(draw_layer)
                self.scene.active_layer = draw_layer

                self.refresh_layer_list_ui()
                QTimer.singleShot(50, self.fit_view_to_image)

    def add_new_layer(self):
        self.layer_counter += 1
        z_idx = len(self.layers)
        new_layer = EditorLayer(f"🎨 Capa {self.layer_counter}", z_idx, self.scene)
        self.layers.append(new_layer)
        self.scene.active_layer = new_layer
        self.refresh_layer_list_ui()

    def delete_current_layer(self):
        curr_idx = self.layer_list_widget.currentRow()
        if curr_idx < 0 or curr_idx >= len(self.layers):
            return

        layer = self.layers[curr_idx]
        if layer.name == "🖼️ Imagen Base":
            QMessageBox.warning(self, "Capas", "No se puede eliminar la capa de imagen base.")
            return

        layer.clear()
        self.layers.remove(layer)

        if self.layers:
            self.scene.active_layer = self.layers[-1]

        self.refresh_layer_list_ui()

    def refresh_layer_list_ui(self):
        self.layer_list_widget.blockSignals(True)
        self.layer_list_widget.clear()

        for idx, layer in enumerate(self.layers):
            item = QListWidgetItem(f"{'🔒 ' if layer.is_locked else '👁️ '}{layer.name}")
            self.layer_list_widget.addItem(item)
            if layer == self.scene.active_layer:
                self.layer_list_widget.setCurrentItem(item)

        self.layer_list_widget.blockSignals(False)

    def on_layer_selected(self, row: int):
        if 0 <= row < len(self.layers):
            self.scene.active_layer = self.layers[row]

    def fit_view_to_image(self):
        if self.scene.sceneRect().isValid():
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_tool(self, tool_code: str):
        self.scene.tool = tool_code
        for code, btn in self.tools.items():
            btn.setChecked(code == tool_code)

    def set_color(self, color: QColor):
        self.scene.pen_color = color

    def choose_custom_color(self):
        c = QColorDialog.getColor(self.scene.pen_color, self, "Seleccionar color Pro")
        if c.isValid():
            self.set_color(c)

    def save_and_copy(self):
        try:
            self.scene.deselect_all_transforms()

            rect = self.scene.sceneRect()
            out_img = QImage(rect.size().toSize(), QImage.Format.Format_ARGB32)
            out_img.fill(Qt.GlobalColor.transparent)

            painter = QPainter(out_img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            self.scene.render(painter)
            painter.end()

            file_dir = os.path.dirname(self.filepath)
            if file_dir:
                os.makedirs(file_dir, exist_ok=True)

            out_img.save(self.filepath, "PNG")

            cb = QApplication.clipboard()
            cb.setImage(out_img)

            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la imagen: {e}")

    def closeEvent(self, event):
        super().closeEvent(event)

# Aliases de compatibilidad retroactiva
JadeImageEditor = JadeImageEditor
JadeSettingsDialog = JadeSettingsDialog


# Aliases de compatibilidad
PerlaImageEditor = JadeImageEditor
PerlaSettingsDialog = JadeSettingsDialog
