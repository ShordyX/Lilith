from theme_manager import ThemeManager, ThemePalette, get_perla_appdata_dir, enable_win11_effects
import sys
import os
import json
import threading
import subprocess

from PyQt6.QtCore import (
    Qt, QSize, QTimer, QUrl, QMimeData, pyqtSignal, QByteArray, QPointF, QRectF, QEvent
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage, QFont, QKeySequence, QShortcut, QPainter, QTransform, QWheelEvent, QMouseEvent, QColor, QBrush
)
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSlider, QMessageBox, QProgressDialog, QApplication,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PyQt6.QtSvg import QSvgRenderer

def _get_main_attr(attr_name, default=None):
    main_mod = sys.modules.get('__main__')
    if main_mod and hasattr(main_mod, attr_name):
        return getattr(main_mod, attr_name)
    return default

def get_resource_path(relative_path: str) -> str:
    fn = _get_main_attr('get_resource_path')
    if fn:
        return fn(relative_path)
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)

def detect_windows_system_theme() -> str:
    fn = _get_main_attr('detect_windows_system_theme')
    if fn:
        return fn()
    return "oscuro"

def find_and_setup_vlc():
    fn = _get_main_attr('find_and_setup_vlc')
    if fn:
        return fn()
    return False

def log_message(msg: str):
    fn = _get_main_attr('log_message')
    if fn:
        fn(msg)

SVG_DATA_MAP = {
    "zoom_in": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>',
    "zoom_out": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>',
    "zoom_fit": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg>',
    "zoom_100": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 7v10M9 9.5l3-2.5 3 2.5"></path></svg>',
    "rotate_left": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38L2.5 8"></path></svg>',
    "rotate_right": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38L21.5 8"></path></svg>',
    "flip_horizontal": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 7 5 5-5 5V7zm18 0-5 5 5 5V7zM12 2v20"></path></svg>',
    "fullscreen": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"></path></svg>',
    "fullscreen_exit": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"></path></svg>',
    "copy": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
    "ocr": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V4h3m10 0h3v3M4 17v3h3m10 0h3v-3M9 12h6M12 9v6"></path></svg>',
    "prev": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>',
    "next": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>',
    "play": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>',
    "pause": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>',
    "volume_high": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>',
    "volume_mute": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>',
    "seek_forward": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 19 22 12 13 5 13 19"></polygon><polygon points="2 19 11 12 2 5 2 19"></polygon></svg>',
    "seek_backward": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 19 2 12 11 5 11 19"></polygon><polygon points="22 19 13 12 22 5 22 19"></polygon></svg>',
    "open_ext": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>'
}

def get_minimalist_svg_icon(icon_type: str, color_hex: str = "#FFFFFF", size_px: int = 20) -> QIcon:
    svg_template = SVG_DATA_MAP.get(icon_type)
    if svg_template:
        svg_xml = svg_template.format(c=color_hex)
        renderer = QSvgRenderer(QByteArray(svg_xml.encode('utf-8')))
        pixmap = QPixmap(size_px, size_px)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    fn = _get_main_attr('get_minimalist_svg_icon')
    if fn:
        res = fn(icon_type, color_hex, size_px)
        if res and not res.isNull():
            return res
        
    return QIcon()

def create_audio_thumbnail_pixmap(width: int = 170, height: int = 130) -> QPixmap:
    fn = _get_main_attr('create_audio_thumbnail_pixmap')
    if fn:
        return fn(width, height)
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    return pixmap

def get_vlc_module():
    return _get_main_attr('vlc', None)

def is_vlc_available():
    return _get_main_attr('VLC_AVAILABLE', False)

def get_vlc_installer_thread_class():
    return _get_main_attr('VLCInstallerThread', None)


class ProfessionalInteractiveGraphicsView(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    double_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self.pixmap_item)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QColor("#0B0C0E"))
        self.viewport().setAutoFillBackground(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._zoom_factor = 1.0
        self._rotation_angle = 0
        self._is_flipped_h = False
        self._original_pixmap = QPixmap()
        self._is_user_zoomed = False
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_graphics_context_menu)

    def _show_graphics_context_menu(self, pos):
        viewer_dialog = None
        curr = self.parent()
        while curr:
            if hasattr(curr, "set_wallpaper_action"):
                viewer_dialog = curr
                break
            curr = curr.parent()

        if not viewer_dialog:
            return

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(ThemePalette.get_menu_style(ThemeManager.get_instance().is_dark))

        act_copy_img = menu.addAction("📋 Copiar Imagen")
        act_copy_file = menu.addAction("📄 Copiar Archivo")
        act_folder = menu.addAction("📂 Mostrar en Carpeta")
        menu.addSeparator()
        act_wallpaper = menu.addAction("🖼️ Establecer como Fondo de Pantalla")
        act_lockscreen = menu.addAction("🔒 Establecer como Pantalla de Bloqueo")
        menu.addSeparator()
        act_rot_r = menu.addAction("↻ Rotar 90° Derecha (R)")
        act_rot_l = menu.addAction("↺ Rotar 90° Izquierda")
        act_flip = menu.addAction("⇄ Voltear Horizontalmente (H)")
        act_fit = menu.addAction("⛶ Ajustar a Pantalla (0)")
        act_actual = menu.addAction("🔍 Tamaño Original 100% (1)")
        menu.addSeparator()
        act_ocr = menu.addAction("✨ Extraer Texto (OCR)")

        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_copy_img:
            viewer_dialog.copy_image()
        elif chosen == act_copy_file:
            viewer_dialog.copy_file_native()
        elif chosen == act_folder:
            viewer_dialog.open_in_explorer()
        elif chosen == act_wallpaper:
            viewer_dialog.set_wallpaper_action()
        elif chosen == act_lockscreen:
            viewer_dialog.set_lockscreen_action()
        elif chosen == act_rot_r:
            self.rotate_right()
        elif chosen == act_rot_l:
            self.rotate_left()
        elif chosen == act_flip:
            self.flip_horizontal()
        elif chosen == act_fit:
            self.fit_in_view_smooth()
        elif chosen == act_actual:
            self.set_actual_size()
        elif chosen == act_ocr:
            viewer_dialog.run_ocr()

    def keyPressEvent(self, event):
        event.ignore()

    def set_image(self, pixmap: QPixmap):
        self._original_pixmap = pixmap
        self.pixmap_item.setPixmap(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.pixmap_item.setPos(0, 0)
        self.reset_transformations()
        QTimer.singleShot(10, self.fit_in_view_smooth)

    def reset_transformations(self):
        self._rotation_angle = 0
        self._is_flipped_h = False
        self._is_user_zoomed = False
        self.pixmap_item.setTransform(QTransform())
        self.resetTransform()

    def _apply_item_transform(self):
        tr = QTransform()
        bounds = self.pixmap_item.boundingRect()
        cx = bounds.width() / 2.0
        cy = bounds.height() / 2.0
        tr.translate(cx, cy)
        tr.rotate(self._rotation_angle)
        if self._is_flipped_h:
            tr.scale(-1, 1)
        tr.translate(-cx, -cy)
        self.pixmap_item.setTransform(tr)
        self._scene.setSceneRect(self.pixmap_item.mapToScene(self.pixmap_item.boundingRect()).boundingRect())

    def fit_in_view_smooth(self):
        if self._original_pixmap.isNull():
            return
        rect = self._scene.itemsBoundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        vp = self.viewport().size()
        if vp.width() <= 10 or vp.height() <= 10:
            QTimer.singleShot(20, self.fit_in_view_smooth)
            return
        self.resetTransform()
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.centerOn(rect.center())
        self._zoom_factor = self.transform().m11()
        self._is_user_zoomed = False
        self.zoom_changed.emit(self._zoom_factor)

    def set_actual_size(self):
        if self._original_pixmap.isNull():
            return
        self.resetTransform()
        self.centerOn(self.pixmap_item)
        self._zoom_factor = 1.0
        self._is_user_zoomed = True
        self.zoom_changed.emit(self._zoom_factor)

    def zoom_in(self):
        self.zoom_by_factor(1.20)

    def zoom_out(self):
        self.zoom_by_factor(0.83)

    def zoom_by_factor(self, factor: float):
        if self._original_pixmap.isNull():
            return
        current_scale = self.transform().m11()
        if (current_scale * factor < 0.02) or (current_scale * factor > 40.0):
            return
        self.scale(factor, factor)
        self._zoom_factor = self.transform().m11()
        self._is_user_zoomed = True
        self.zoom_changed.emit(self._zoom_factor)

    def rotate_left(self):
        self._rotation_angle = (self._rotation_angle - 90) % 360
        self._apply_item_transform()
        self.fit_in_view_smooth()

    def rotate_right(self):
        self._rotation_angle = (self._rotation_angle + 90) % 360
        self._apply_item_transform()
        self.fit_in_view_smooth()

    def flip_horizontal(self):
        self._is_flipped_h = not self._is_flipped_h
        self._apply_item_transform()

    def wheelEvent(self, event: QWheelEvent):
        angle = event.angleDelta().y()
        if angle > 0:
            self.zoom_by_factor(1.15)
        elif angle < 0:
            self.zoom_by_factor(0.87)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._is_user_zoomed:
            self.fit_in_view_smooth()

class VideoContainerWidget(QWidget):
    double_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_ar = 16.0 / 9.0
        self.is_fullscreen = False
        self.video_widget = QWidget(self)
        self.video_widget.setStyleSheet("background-color: #000000; border: none;")
        self.setStyleSheet("background-color: transparent; border: none;")

    def set_aspect_ratio(self, ar: float):
        if ar > 0.1 and abs(self.video_ar - ar) > 0.01:
            self.video_ar = ar
            self.update_layout()

    def set_fullscreen_layout(self, enabled: bool):
        self.is_fullscreen = enabled
        self.update_layout()

    def update_layout(self):
        cw = self.width()
        ch = self.height()
        if cw <= 10 or ch <= 10:
            return

        if self.is_fullscreen:
            container_ar = cw / float(ch)
            if container_ar > self.video_ar:
                vw = int(ch * self.video_ar)
                vh = ch
            else:
                vw = cw
                vh = int(cw / self.video_ar)
            vx = (cw - vw) // 2
            vy = (ch - vh) // 2
            self.video_widget.setGeometry(vx, vy, vw, vh)
        else:
            container_ar = cw / float(ch)
            if container_ar > self.video_ar:
                vw = int(ch * self.video_ar)
                vh = ch
            else:
                vw = cw
                vh = int(cw / self.video_ar)
            vx = (cw - vw) // 2
            vy = (ch - vh) // 2
            self.video_widget.setGeometry(vx, vy, vw, vh)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

class HDMediaViewerDialog(QDialog):
    """Visualizador HD profesional ultra-minimalista, con zoom de alta precisión, atajos de teclado y motor gráfico avanzado."""
    ocr_requested = pyqtSignal(QPixmap)

    def __init__(self, item_path: str, parent=None, file_list: list = None, current_index: int = 0):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)

        self.item_path = os.path.abspath(item_path)
        
        if isinstance(file_list, list) and file_list:
            self.file_list = [os.path.abspath(p) for p in file_list]
            self.current_index = current_index if (0 <= current_index < len(self.file_list)) else 0
        else:
            self.file_list = [self.item_path]
            self.current_index = 0

        ALL_VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ts', '.mts', '.m2ts', '.vob', '.ogv', '.asf', '.f4v', '.mpg', '.mpeg', '.mpv')
        ALL_AUDIO_EXTS = ('.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma', '.opus', '.aiff', '.alac')
        self.item_path = self.file_list[self.current_index]
        self.is_video = self.item_path.lower().endswith(ALL_VIDEO_EXTS)
        self.is_audio = self.item_path.lower().endswith(ALL_AUDIO_EXTS)
        self.vlc_player = None
        self.vlc_instance = None
        self.is_user_seeking = False
        self._is_fullscreen = False
        self.control_bar_widget = None
        self._prev_window_state = None

        self.setMouseTracking(True)
        self._autohide_timer = QTimer(self)
        self._autohide_timer.setInterval(2400)
        self._autohide_timer.setSingleShot(True)
        self._autohide_timer.timeout.connect(self._on_autohide_timeout)

        self.resize(1180, 800)
        self.setMinimumSize(750, 520)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        self._init_shortcuts()
        self.init_ui()

    def _init_shortcuts(self):
        sc_map = [
            (Qt.Key.Key_Left, self.show_previous_media),
            (Qt.Key.Key_Right, self.show_next_media),
            (Qt.Key.Key_A, self.show_previous_media),
            (Qt.Key.Key_D, self.show_next_media),
            (Qt.Key.Key_F11, self.toggle_fullscreen),
            (Qt.Key.Key_F, self.toggle_fullscreen),
            (Qt.Key.Key_Plus, self._action_zoom_in),
            (Qt.Key.Key_Minus, self._action_zoom_out),
            (Qt.Key.Key_0, self._action_zoom_fit),
            (Qt.Key.Key_1, self._action_zoom_100),
            (Qt.Key.Key_R, self._action_rotate_right),
            (Qt.Key.Key_H, self._action_flip_h),
            (Qt.Key.Key_Space, self._action_space_key),
            (Qt.Key.Key_M, self.toggle_vlc_mute),
            (Qt.Key.Key_Escape, self._action_escape_key)
        ]
        for key, callback in sc_map:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(callback)

    def _action_escape_key(self):
        if getattr(self, '_is_fullscreen', False):
            self.toggle_fullscreen()
        else:
            curr = self.parent()
            while curr:
                if hasattr(curr, "back_requested"):
                    curr.back_requested.emit()
                    break
                curr = curr.parent()
            else:
                self.close()

    def _action_space_key(self):
        if self.is_video or self.is_audio:
            self.toggle_vlc_play()

    def _action_zoom_in(self):
        if hasattr(self, 'graphics_viewer') and self.graphics_viewer:
            self.graphics_viewer.zoom_in()

    def _action_zoom_out(self):
        if hasattr(self, 'graphics_viewer') and self.graphics_viewer:
            self.graphics_viewer.zoom_out()

    def _action_zoom_fit(self):
        if hasattr(self, 'graphics_viewer') and self.graphics_viewer:
            self.graphics_viewer.fit_in_view_smooth()

    def _action_zoom_100(self):
        if hasattr(self, 'graphics_viewer') and self.graphics_viewer:
            self.graphics_viewer.set_actual_size()

    def _action_rotate_right(self):
        if hasattr(self, 'graphics_viewer') and self.graphics_viewer:
            self.graphics_viewer.rotate_right()

    def _action_flip_h(self):
        if hasattr(self, 'graphics_viewer') and self.graphics_viewer:
            self.graphics_viewer.flip_horizontal()

    def mouseMoveEvent(self, event):
        self._show_controls_temporarily()
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.HoverMove, QEvent.Type.MouseButtonPress):
            self._show_controls_temporarily()
        return super().eventFilter(obj, event)

    def _show_controls_temporarily(self):
        if hasattr(self, 'control_bar_widget') and self.control_bar_widget:
            self.control_bar_widget.show()
        self.unsetCursor()

        curr = self.parent()
        while curr:
            if hasattr(curr, '_show_hud_temporarily'):
                curr._show_hud_temporarily()
                break
            curr = curr.parent()

        self._autohide_timer.start()

    def _on_autohide_timeout(self):
        if getattr(self, '_is_fullscreen', False):
            if hasattr(self, 'control_bar_widget') and self.control_bar_widget:
                self.control_bar_widget.hide()
            self.setCursor(Qt.CursorShape.BlankCursor)
        else:
            self.unsetCursor()
            if hasattr(self, 'control_bar_widget') and self.control_bar_widget:
                self.control_bar_widget.show()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self.show_previous_media()
            event.accept()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self.show_next_media()
            event.accept()
        elif key == Qt.Key.Key_Escape:
            self._action_escape_key()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_fullscreen()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def toggle_fullscreen(self):
        top_win = self.window()
        curr = self.parent()
        embed_page = None
        while curr:
            if hasattr(curr, "set_fullscreen_mode"):
                embed_page = curr
                break
            curr = curr.parent()

        if self._is_fullscreen:
            prev_state = getattr(self, "_prev_window_state", None)
            if prev_state is not None and (prev_state & Qt.WindowState.WindowMaximized):
                top_win.showMaximized()
            else:
                top_win.showNormal()

            self._is_fullscreen = False
            self.main_layout.setContentsMargins(16, 16, 16, 16)
            self.main_layout.setSpacing(12)

            if hasattr(self, 'video_container') and self.video_container:
                self.video_container.set_fullscreen_layout(False)

            if embed_page:
                embed_page.set_fullscreen_mode(False)

            if hasattr(self, 'btn_fs'):
                col = "#FFFFFF" if getattr(self, '_is_dark_theme', True) else "#1A1A1A"
                self.btn_fs.setIcon(get_minimalist_svg_icon("fullscreen", col, 18))
                self.btn_fs.setToolTip("Pantalla completa (F11)")
        else:
            self._prev_window_state = top_win.windowState()
            top_win.showFullScreen()
            self._is_fullscreen = True

            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)

            if hasattr(self, 'video_container') and self.video_container:
                self.video_container.set_fullscreen_layout(True)

            if embed_page:
                embed_page.set_fullscreen_mode(True)

            if hasattr(self, 'btn_fs'):
                col = "#FFFFFF" if getattr(self, '_is_dark_theme', True) else "#1A1A1A"
                self.btn_fs.setIcon(get_minimalist_svg_icon("fullscreen_exit", col, 18))
                self.btn_fs.setToolTip("Salir de pantalla completa (Esc / F11)")

    def copy_file_native(self):
        if hasattr(self, 'item_path') and os.path.exists(self.item_path):
            abs_p = os.path.abspath(self.item_path)
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(abs_p)])
            QApplication.clipboard().setMimeData(mime_data)
            QMessageBox.information(self, "Jade", "¡Archivo copiado al portapapeles!")

    def open_in_explorer(self):
        if hasattr(self, 'item_path') and os.path.exists(self.item_path):
            norm_path = os.path.normpath(self.item_path)
            subprocess.Popen(f'explorer /select,"{norm_path}"', creationflags=0x08000000)

    def set_wallpaper_action(self):
        if hasattr(self, 'item_path') and os.path.exists(self.item_path):
            try:
                import ctypes
                abs_path = os.path.abspath(self.item_path)
                SPI_SETDESKWALLPAPER = 20
                SPIF_UPDATEINIFILE = 0x01
                SPIF_SENDCHANGE = 0x02
                ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, abs_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)
                QMessageBox.information(self, "Fondo de Pantalla", "¡Fondo de escritorio cambiado exitosamente!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo establecer el fondo de pantalla: {e}")

    def set_lockscreen_action(self):
        if hasattr(self, 'item_path') and os.path.exists(self.item_path):
            try:
                abs_path = os.path.abspath(self.item_path).replace("'", "''")
                ps_script = f'''
[Windows.System.UserProfile.LockScreen, Windows.System.UserProfile, ContentType = WindowsRuntime] | Out-Null
$file = [Windows.Storage.StorageFile]::GetFileFromPathAsync('{abs_path}').GetAwaiter().GetResult()
[Windows.System.UserProfile.LockScreen]::SetImageFileAsync($file).GetAwaiter().GetResult()
'''
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                    startupinfo=startupinfo,
                    creationflags=0x08000000,
                    timeout=6
                )
                QMessageBox.information(self, "Pantalla de Bloqueo", "¡Pantalla de bloqueo cambiada exitosamente!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo establecer la pantalla de bloqueo: {e}")

    def show_previous_media(self):
        if len(self.file_list) > 1 and self.current_index > 0:
            self.load_media_at_index(self.current_index - 1)

    def show_next_media(self):
        if len(self.file_list) > 1 and self.current_index < len(self.file_list) - 1:
            self.load_media_at_index(self.current_index + 1)

    def load_media_at_index(self, index: int):
        ALL_VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ts', '.mts', '.m2ts', '.vob', '.ogv', '.asf', '.f4v', '.mpg', '.mpeg', '.mpv')
        ALL_AUDIO_EXTS = ('.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma', '.opus', '.aiff', '.alac')
        self._cleanup_vlc()
        self.current_index = index
        self.item_path = self.file_list[self.current_index]
        self.is_video = self.item_path.lower().endswith(ALL_VIDEO_EXTS)
        self.is_audio = self.item_path.lower().endswith(ALL_AUDIO_EXTS)
        self.init_ui()
        self.setFocus()
        if self.isVisible():
            if self.is_video and hasattr(self, 'video_widget') and sys.platform == "win32":
                if self.vlc_player:
                    self.vlc_player.set_hwnd(int(self.video_widget.winId()))
            QTimer.singleShot(50, self._start_vlc_playback)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        if not self.is_video and not self.is_audio and hasattr(self, 'graphics_viewer') and self.graphics_viewer:
            QTimer.singleShot(30, self.graphics_viewer.fit_in_view_smooth)
        if hasattr(self, 'vlc_player') and self.vlc_player and not getattr(self, '_vlc_started', False):
            self._vlc_started = True
            if self.is_video and hasattr(self, 'video_widget') and sys.platform == "win32":
                self.vlc_player.set_hwnd(int(self.video_widget.winId()))
            QTimer.singleShot(50, self._start_vlc_playback)

    def _start_vlc_playback(self):
        if hasattr(self, 'vlc_player') and self.vlc_player:
            self.vlc_player.play()
            if hasattr(self, 'timer') and self.timer:
                self.timer.start()

    def init_ui(self):
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        is_dark = True
        is_dark = ThemeManager.get_instance().is_dark
        self._is_dark_theme = is_dark
        ThemeManager.get_instance().register_child(self)
        dialog_bg = "transparent"
        panel_bg = "rgba(18, 22, 32, 0.94)" if is_dark else "rgba(255, 255, 255, 0.95)"
        border_col = "rgba(255, 255, 255, 0.14)" if is_dark else "#DDE2E8"
        text_col = "#F0F3F6" if is_dark else "#1A202C"
        subtext_col = "#94A3B8" if is_dark else "#64748B"
        icon_col = "#F0F3F6" if is_dark else "#2D3748"
        btn_hover_bg = "rgba(255, 255, 255, 0.12)" if is_dark else "#EAEEF3"

        self.setStyleSheet(f"""
            QDialog {{ 
                background-color: {dialog_bg}; 
            }}
            QFrame#ControlBar, QFrame#VideoControlBar {{
                background-color: {panel_bg};
                border: 1px solid {border_col};
                border-radius: 12px;
            }}
            QPushButton[is_tool="true"] {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px;
                min-width: 32px;
                min-height: 32px;
            }}
            QPushButton[is_tool="true"]:hover {{
                background-color: {btn_hover_bg};
            }}
            QPushButton[is_tool="true"]:pressed {{
                background-color: {border_col};
            }}
            QPushButton[is_tool="true"]:disabled {{
                opacity: 0.3;
            }}
            QPushButton#PlayPauseBtn {{
                background-color: #3B82F6;
                border: none;
                border-radius: 18px;
                min-width: 36px;
                min-height: 36px;
                max-width: 36px;
                max-height: 36px;
            }}
            QPushButton#PlayPauseBtn:hover {{
                background-color: #2563EB;
            }}
            QPushButton#PlayPauseBtn:pressed {{
                background-color: #1D4ED8;
            }}
            QLabel#SubInfoLabel {{
                color: {subtext_col};
                font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
            }}
            QLabel#ZoomBadge, QLabel#MediaTimeBadge {{
                color: {text_col};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', monospace;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 6px;
                background-color: {btn_hover_bg};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background-color: {border_col};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: #3B82F6;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background-color: #FFFFFF;
                border: 2px solid #3B82F6;
                width: 14px;
                height: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: #3B82F6;
                border: 2px solid #FFFFFF;
            }}
            QSlider#VolumeSlider {{
                max-width: 85px;
            }}
            QSlider#VolumeSlider::groove:horizontal {{
                height: 4px;
            }}
            QSlider#VolumeSlider::handle:horizontal {{
                width: 10px;
                height: 10px;
                margin-top: -3px;
                margin-bottom: -3px;
                border-radius: 5px;
            }}
        """)

        self.setWindowTitle(f"Visor HD ({self.current_index + 1} de {len(self.file_list)}) — {os.path.basename(self.item_path)}")

        if not self.is_video and not self.is_audio:
            self.graphics_viewer = ProfessionalInteractiveGraphicsView(self)
            self.graphics_viewer.setStyleSheet("background-color: transparent; border: none; border-radius: 10px;")
            self.graphics_viewer.setBackgroundBrush(QBrush(Qt.GlobalColor.transparent))
            self.graphics_viewer.viewport().setAutoFillBackground(False)
            self.pixmap = QPixmap(self.item_path)
            self.graphics_viewer.set_image(self.pixmap)
            self.graphics_viewer.double_clicked.connect(self.toggle_fullscreen)

            self.main_layout.addWidget(self.graphics_viewer, stretch=1)

            control_bar = QFrame()
            control_bar.setObjectName("ControlBar")
            control_bar.setFixedHeight(54)
            c_layout = QHBoxLayout(control_bar)
            c_layout.setContentsMargins(14, 4, 14, 4)
            c_layout.setSpacing(6)

            info_text = f"{os.path.basename(self.item_path)}   •   {self.pixmap.width()} × {self.pixmap.height()} px   ({self.current_index + 1}/{len(self.file_list)})"
            lbl_info = QLabel(info_text)
            lbl_info.setObjectName("SubInfoLabel")

            self.lbl_zoom = QLabel("100%")
            self.lbl_zoom.setObjectName("ZoomBadge")
            self.graphics_viewer.zoom_changed.connect(lambda z: self.lbl_zoom.setText(f"{int(round(z * 100))}%"))

            btn_prev = QPushButton()
            btn_prev.setProperty("is_tool", "true")
            btn_prev.setIcon(get_minimalist_svg_icon("prev", icon_col, 18))
            btn_prev.setToolTip("Anterior (← / A)")
            btn_prev.setEnabled(self.current_index > 0)
            btn_prev.clicked.connect(self.show_previous_media)

            btn_next = QPushButton()
            btn_next.setProperty("is_tool", "true")
            btn_next.setIcon(get_minimalist_svg_icon("next", icon_col, 18))
            btn_next.setToolTip("Siguiente (→ / D)")
            btn_next.setEnabled(self.current_index < len(self.file_list) - 1)
            btn_next.clicked.connect(self.show_next_media)

            sep1 = QFrame()
            sep1.setFrameShape(QFrame.Shape.VLine)
            sep1.setStyleSheet(f"background-color: {border_col}; max-width: 1px;")

            btn_zin = QPushButton()
            btn_zin.setProperty("is_tool", "true")
            btn_zin.setIcon(get_minimalist_svg_icon("zoom_in", icon_col, 18))
            btn_zin.setToolTip("Acercar (+ / Rueda arriba)")
            btn_zin.clicked.connect(self.graphics_viewer.zoom_in)

            btn_zout = QPushButton()
            btn_zout.setProperty("is_tool", "true")
            btn_zout.setIcon(get_minimalist_svg_icon("zoom_out", icon_col, 18))
            btn_zout.setToolTip("Alejar (- / Rueda abajo)")
            btn_zout.clicked.connect(self.graphics_viewer.zoom_out)

            btn_zfit = QPushButton()
            btn_zfit.setProperty("is_tool", "true")
            btn_zfit.setIcon(get_minimalist_svg_icon("zoom_fit", icon_col, 18))
            btn_zfit.setToolTip("Ajustar a pantalla (0)")
            btn_zfit.clicked.connect(self.graphics_viewer.fit_in_view_smooth)

            btn_z100 = QPushButton()
            btn_z100.setProperty("is_tool", "true")
            btn_z100.setIcon(get_minimalist_svg_icon("zoom_100", icon_col, 18))
            btn_z100.setToolTip("Tamaño original 100% (1)")
            btn_z100.clicked.connect(self.graphics_viewer.set_actual_size)

            sep2 = QFrame()
            sep2.setFrameShape(QFrame.Shape.VLine)
            sep2.setStyleSheet(f"background-color: {border_col}; max-width: 1px;")

            btn_rotl = QPushButton()
            btn_rotl.setProperty("is_tool", "true")
            btn_rotl.setIcon(get_minimalist_svg_icon("rotate_left", icon_col, 18))
            btn_rotl.setToolTip("Rotar 90° izquierda")
            btn_rotl.clicked.connect(self.graphics_viewer.rotate_left)

            btn_rotr = QPushButton()
            btn_rotr.setProperty("is_tool", "true")
            btn_rotr.setIcon(get_minimalist_svg_icon("rotate_right", icon_col, 18))
            btn_rotr.setToolTip("Rotar 90° derecha (R)")
            btn_rotr.clicked.connect(self.graphics_viewer.rotate_right)

            btn_fliph = QPushButton()
            btn_fliph.setProperty("is_tool", "true")
            btn_fliph.setIcon(get_minimalist_svg_icon("flip_horizontal", icon_col, 18))
            btn_fliph.setToolTip("Voltear horizontalmente (H)")
            btn_fliph.clicked.connect(self.graphics_viewer.flip_horizontal)

            self.btn_fs = QPushButton()
            self.btn_fs.setProperty("is_tool", "true")
            fs_icon = "fullscreen_exit" if self.isFullScreen() else "fullscreen"
            self.btn_fs.setIcon(get_minimalist_svg_icon(fs_icon, icon_col, 18))
            self.btn_fs.setToolTip("Pantalla completa (Doble clic / F11)")
            self.btn_fs.clicked.connect(self.toggle_fullscreen)

            sep3 = QFrame()
            sep3.setFrameShape(QFrame.Shape.VLine)
            sep3.setStyleSheet(f"background-color: {border_col}; max-width: 1px;")

            btn_copy = QPushButton()
            btn_copy.setProperty("is_tool", "true")
            btn_copy.setIcon(get_minimalist_svg_icon("copy", icon_col, 18))
            btn_copy.setToolTip("Copiar imagen al portapapeles")
            btn_copy.clicked.connect(self.copy_image)

            btn_ocr = QPushButton(" OCR")
            btn_ocr.setIcon(get_minimalist_svg_icon("ocr", "#FFFFFF", 16))
            btn_ocr.setObjectName("PrimaryBtn")
            btn_ocr.setFixedHeight(34)
            btn_ocr.setStyleSheet("QPushButton { font-weight: bold; padding: 0 16px; border-radius: 6px; }")
            btn_ocr.clicked.connect(self.run_ocr)

            c_layout.addWidget(lbl_info)
            c_layout.addStretch()
            c_layout.addWidget(btn_prev)
            c_layout.addWidget(btn_next)
            c_layout.addWidget(sep1)
            c_layout.addWidget(btn_zin)
            c_layout.addWidget(btn_zout)
            c_layout.addWidget(btn_zfit)
            c_layout.addWidget(btn_z100)
            c_layout.addWidget(self.lbl_zoom)
            c_layout.addWidget(sep2)
            c_layout.addWidget(btn_rotl)
            c_layout.addWidget(btn_rotr)
            c_layout.addWidget(btn_fliph)
            c_layout.addWidget(self.btn_fs)
            c_layout.addWidget(sep3)
            c_layout.addWidget(btn_copy)
            c_layout.addWidget(btn_ocr)

            self.control_bar_widget = control_bar
            self.graphics_viewer.installEventFilter(self)
            self.main_layout.addWidget(control_bar)

        else:
            vlc_success = False
            find_and_setup_vlc()
            vlc_mod = get_vlc_module()

            if is_vlc_available() and vlc_mod is not None:
                try:
                    vlc_args = ["--quiet", "--no-xlib", "--no-video-title-show", "--no-mouse-events"]
                    self.vlc_instance = vlc_mod.Instance(*vlc_args)
                    self.vlc_player = self.vlc_instance.media_player_new()
                    media = self.vlc_instance.media_new(self.item_path)
                    self.vlc_player.set_media(media)
                    media.release()

                    if self.is_video:
                        self.video_container = VideoContainerWidget(self)
                        self.video_container.setMouseTracking(True)
                        self.video_container.installEventFilter(self)
                        self.video_container.double_clicked.connect(self.toggle_fullscreen)
                        self.video_widget = self.video_container.video_widget
                        self.video_widget.setMouseTracking(True)
                        self.video_widget.installEventFilter(self)
                        self.main_layout.addWidget(self.video_container, stretch=1)
                        if sys.platform == "win32":
                            self.vlc_player.set_hwnd(int(self.video_widget.winId()))
                    else:
                        audio_card = QFrame()
                        audio_card.setObjectName("GalleryCard")
                        a_layout = QVBoxLayout(audio_card)
                        a_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        a_layout.setSpacing(12)

                        icon_lbl = QLabel()
                        icon_lbl.setPixmap(create_audio_thumbnail_pixmap(220, 150))
                        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

                        title_lbl = QLabel(os.path.basename(self.item_path))
                        title_lbl.setObjectName("PrimaryTextLabel")
                        title_lbl.setFont(QFont("Segoe UI Variable Display", 14, QFont.Weight.Bold))

                        subtitle_lbl = QLabel(f"Reproductor Audio HD — ({self.current_index + 1}/{len(self.file_list)})")
                        subtitle_lbl.setObjectName("SubTextLabel")

                        a_layout.addWidget(icon_lbl)
                        a_layout.addWidget(title_lbl)
                        a_layout.addWidget(subtitle_lbl)

                        self.main_layout.addWidget(audio_card, stretch=1)

                    video_control_bar = QFrame()
                    video_control_bar.setObjectName("VideoControlBar")
                    self.control_bar_widget = video_control_bar
                    vcb_layout = QVBoxLayout(video_control_bar)
                    vcb_layout.setContentsMargins(14, 10, 14, 10)
                    vcb_layout.setSpacing(8)

                    self.slider_progress = QSlider(Qt.Orientation.Horizontal)
                    self.slider_progress.setRange(0, 1000)
                    self.slider_progress.sliderPressed.connect(self.on_slider_pressed)
                    self.slider_progress.sliderReleased.connect(self.on_slider_released)
                    vcb_layout.addWidget(self.slider_progress)

                    controls_row = QHBoxLayout()
                    controls_row.setSpacing(8)

                    btn_prev = QPushButton()
                    btn_prev.setProperty("is_tool", "true")
                    btn_prev.setIcon(get_minimalist_svg_icon("prev", icon_col, 18))
                    btn_prev.setToolTip("Anterior (← / A)")
                    btn_prev.setEnabled(self.current_index > 0)
                    btn_prev.clicked.connect(self.show_previous_media)

                    btn_seek_bwd = QPushButton()
                    btn_seek_bwd.setProperty("is_tool", "true")
                    btn_seek_bwd.setIcon(get_minimalist_svg_icon("seek_backward", icon_col, 18))
                    btn_seek_bwd.setToolTip("Retroceder 10 segundos")
                    btn_seek_bwd.clicked.connect(lambda: self.seek_by_ms(-10000))

                    self.btn_play_pause = QPushButton()
                    self.btn_play_pause.setObjectName("PlayPauseBtn")
                    self.btn_play_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 20))
                    self.btn_play_pause.setToolTip("Reproducir / Pausar (Espacio)")
                    self.btn_play_pause.clicked.connect(self.toggle_vlc_play)

                    btn_seek_fwd = QPushButton()
                    btn_seek_fwd.setProperty("is_tool", "true")
                    btn_seek_fwd.setIcon(get_minimalist_svg_icon("seek_forward", icon_col, 18))
                    btn_seek_fwd.setToolTip("Adelantar 10 segundos")
                    btn_seek_fwd.clicked.connect(lambda: self.seek_by_ms(10000))

                    btn_next = QPushButton()
                    btn_next.setProperty("is_tool", "true")
                    btn_next.setIcon(get_minimalist_svg_icon("next", icon_col, 18))
                    btn_next.setToolTip("Siguiente (→ / D)")
                    btn_next.setEnabled(self.current_index < len(self.file_list) - 1)
                    btn_next.clicked.connect(self.show_next_media)

                    sep_v1 = QFrame()
                    sep_v1.setFrameShape(QFrame.Shape.VLine)
                    sep_v1.setStyleSheet(f"background-color: {border_col}; max-width: 1px;")

                    self.lbl_time = QLabel("00:00 / 00:00")
                    self.lbl_time.setObjectName("MediaTimeBadge")

                    controls_row.addWidget(btn_prev)
                    controls_row.addWidget(btn_seek_bwd)
                    controls_row.addWidget(self.btn_play_pause)
                    controls_row.addWidget(btn_seek_fwd)
                    controls_row.addWidget(btn_next)
                    controls_row.addWidget(sep_v1)
                    controls_row.addWidget(self.lbl_time)
                    controls_row.addStretch()

                    self.btn_mute = QPushButton()
                    self.btn_mute.setProperty("is_tool", "true")
                    self.btn_mute.setIcon(get_minimalist_svg_icon("volume_high", icon_col, 18))
                    self.btn_mute.setToolTip("Silenciar / Reactivar audio (M)")
                    self.btn_mute.clicked.connect(self.toggle_vlc_mute)

                    self.slider_volume = QSlider(Qt.Orientation.Horizontal)
                    self.slider_volume.setObjectName("VolumeSlider")
                    self.slider_volume.setRange(0, 100)
                    self.slider_volume.setValue(100)
                    self.slider_volume.setToolTip("Volumen")
                    self.slider_volume.valueChanged.connect(self.on_volume_changed)

                    sep_v2 = QFrame()
                    sep_v2.setFrameShape(QFrame.Shape.VLine)
                    sep_v2.setStyleSheet(f"background-color: {border_col}; max-width: 1px;")

                    self.btn_fs = QPushButton()
                    self.btn_fs.setProperty("is_tool", "true")
                    fs_icon = "fullscreen_exit" if self.isFullScreen() else "fullscreen"
                    self.btn_fs.setIcon(get_minimalist_svg_icon(fs_icon, icon_col, 18))
                    self.btn_fs.setToolTip("Pantalla completa (Doble clic / F11)")
                    self.btn_fs.clicked.connect(self.toggle_fullscreen)

                    btn_open_ext = QPushButton()
                    btn_open_ext.setProperty("is_tool", "true")
                    btn_open_ext.setIcon(get_minimalist_svg_icon("open_ext", icon_col, 18))
                    btn_open_ext.setToolTip("Abrir en reproductor externo")
                    btn_open_ext.clicked.connect(lambda: os.startfile(self.item_path))

                    controls_row.addWidget(self.btn_mute)
                    controls_row.addWidget(self.slider_volume)
                    controls_row.addWidget(sep_v2)
                    controls_row.addWidget(self.btn_fs)
                    controls_row.addWidget(btn_open_ext)

                    vcb_layout.addLayout(controls_row)
                    self.main_layout.addWidget(video_control_bar)

                    self.timer = QTimer(self)
                    self.timer.setInterval(100)
                    self.timer.timeout.connect(self.update_vlc_ui)

                    self._vlc_started = False
                    vlc_success = True
                except Exception as e:
                    log_message(f"Error inicializando VLC embebido: {e}")
                    vlc_success = False

            if not vlc_success:
                fallback_card = QFrame()
                fallback_card.setObjectName("GalleryCard")
                fb_layout = QVBoxLayout(fallback_card)
                fb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                fb_layout.setSpacing(12)

                lbl_fallback = QLabel("🎬 Reproductor Multimedia Jade\n\nNo se detectó el motor portátil LibVLC.")
                lbl_fallback.setObjectName("PrimaryTextLabel")
                lbl_fallback.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.DemiBold))
                lbl_fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)

                btn_download_vlc = QPushButton("⚡ Descargar Motor VLC")
                btn_download_vlc.setObjectName("PrimaryBtn")
                btn_download_vlc.clicked.connect(self.download_and_setup_vlc_engine)

                btn_open_external = QPushButton("▶️ Abrir Externo")
                btn_open_external.setObjectName("SecondaryBtn")
                btn_open_external.clicked.connect(lambda: os.startfile(self.item_path))

                fb_layout.addWidget(lbl_fallback)
                fb_layout.addWidget(btn_download_vlc)
                fb_layout.addWidget(btn_open_external)

                self.main_layout.addWidget(fallback_card, stretch=1)

        for w in self.findChildren(QWidget):
            w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()


    def apply_theme(self, is_dark: bool):
        self._is_dark_theme = is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass

        panel_bg = "rgba(18, 22, 32, 0.94)" if is_dark else "rgba(255, 255, 255, 0.95)"
        border_col = "rgba(255, 255, 255, 0.14)" if is_dark else "#DDE2E8"
        text_col = "#F0F3F6" if is_dark else "#1A202C"
        subtext_col = "#94A3B8" if is_dark else "#64748B"
        icon_col = "#F0F3F6" if is_dark else "#2D3748"
        btn_hover_bg = "rgba(255, 255, 255, 0.12)" if is_dark else "#EAEEF3"

        self.setStyleSheet(f"""
            QDialog {{ background-color: transparent; }}
            QFrame#ControlBar, QFrame#VideoControlBar {{
                background-color: {panel_bg};
                border: 1px solid {border_col};
                border-radius: 12px;
            }}
            QPushButton[is_tool="true"] {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px;
                min-width: 32px;
                min-height: 32px;
            }}
            QPushButton[is_tool="true"]:hover {{
                background-color: {btn_hover_bg};
            }}
            QPushButton[is_tool="true"]:pressed {{
                background-color: {border_col};
            }}
            QPushButton[is_tool="true"]:disabled {{
                opacity: 0.3;
            }}
            QPushButton#PlayPauseBtn {{
                background-color: #3B82F6;
                border: none;
                border-radius: 18px;
                min-width: 36px;
                min-height: 36px;
                max-width: 36px;
                max-height: 36px;
            }}
            QPushButton#PlayPauseBtn:hover {{ background-color: #2563EB; }}
            QPushButton#PlayPauseBtn:pressed {{ background-color: #1D4ED8; }}
            QLabel#SubInfoLabel {{
                color: {subtext_col};
                font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
            }}
            QLabel#ZoomBadge, QLabel#MediaTimeBadge {{
                color: {text_col};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', monospace;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 6px;
                background-color: {btn_hover_bg};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background-color: {border_col};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: #3B82F6;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background-color: #FFFFFF;
                border: 2px solid #3B82F6;
                width: 14px;
                height: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: #3B82F6;
                border: 2px solid #FFFFFF;
            }}
            QSlider#VolumeSlider {{ max-width: 85px; }}
            QSlider#VolumeSlider::groove:horizontal {{ height: 4px; }}
            QSlider#VolumeSlider::handle:horizontal {{
                width: 10px; height: 10px; margin-top: -3px; margin-bottom: -3px; border-radius: 5px;
            }}
        """)

        # Actualizar iconos de herramientas si existen
        btn_map = {
            'btn_prev': 'prev', 'btn_next': 'next', 'btn_rotate_left': 'rotate_left',
            'btn_rotate_right': 'rotate_right', 'btn_flip_h': 'flip_horizontal',
            'btn_zoom_100': 'zoom_100', 'btn_copy': 'copy', 'btn_ocr': 'ocr',
            'btn_open_ext': 'open_ext', 'btn_backward': 'seek_backward',
            'btn_forward': 'seek_forward'
        }
        for attr, icon_name in btn_map.items():
            if hasattr(self, attr):
                btn = getattr(self, attr)
                if btn:
                    btn.setIcon(get_minimalist_svg_icon(icon_name, icon_col, 18))

        if hasattr(self, 'btn_fs'):
            fs_icon = "fullscreen_exit" if getattr(self, '_is_fullscreen', False) else "fullscreen"
            self.btn_fs.setIcon(get_minimalist_svg_icon(fs_icon, icon_col, 18))

    def download_and_setup_vlc_engine(self):
        self.progress_dialog = QProgressDialog("Configurando el motor portátil VLC...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Configuración de Reproductor")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        vlc_installer_cls = get_vlc_installer_thread_class()
        if vlc_installer_cls:
            self.vlc_installer = vlc_installer_cls(self)
            self.vlc_installer.status_updated.connect(self.progress_dialog.setLabelText)
            self.vlc_installer.finished.connect(self.on_vlc_installed)
            self.vlc_installer.start()

    def on_vlc_installed(self, success: bool, message: str):
        self.progress_dialog.close()
        if success:
            find_and_setup_vlc()
            QMessageBox.information(self, "Jade", message)
            self.init_ui()
        else:
            QMessageBox.warning(self, "Jade", message)

    def toggle_vlc_play(self):
        if self.vlc_player:
            vlc_mod = get_vlc_module()
            state = self.vlc_player.get_state() if vlc_mod else None

            if vlc_mod and state == vlc_mod.State.Ended:
                self.vlc_player.stop()
                self.vlc_player.play()
                if hasattr(self, 'btn_play_pause'):
                    self.btn_play_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 20))
            elif self.vlc_player.is_playing():
                self.vlc_player.pause()
                if hasattr(self, 'btn_play_pause'):
                    self.btn_play_pause.setIcon(get_minimalist_svg_icon("play", "#FFFFFF", 20))
            else:
                self.vlc_player.play()
                if hasattr(self, 'btn_play_pause'):
                    self.btn_play_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 20))
        else:
            os.startfile(self.item_path)

    def toggle_vlc_mute(self):
        if hasattr(self, 'vlc_player') and self.vlc_player:
            is_muted = bool(self.vlc_player.audio_get_mute())
            new_mute = not is_muted
            self.vlc_player.audio_set_mute(new_mute)
            icon_col = "#F0F3F6" if getattr(self, '_is_dark_theme', True) else "#2D3748"
            if hasattr(self, 'btn_mute'):
                icon_name = "volume_mute" if new_mute else "volume_high"
                self.btn_mute.setIcon(get_minimalist_svg_icon(icon_name, icon_col, 18))

    def on_volume_changed(self, value: int):
        if hasattr(self, 'vlc_player') and self.vlc_player:
            self.vlc_player.audio_set_volume(value)
            if hasattr(self, 'btn_mute'):
                icon_col = "#F0F3F6" if getattr(self, '_is_dark_theme', True) else "#2D3748"
                icon_name = "volume_mute" if value == 0 else "volume_high"
                self.btn_mute.setIcon(get_minimalist_svg_icon(icon_name, icon_col, 18))

    def seek_by_ms(self, offset_ms: int):
        if hasattr(self, 'vlc_player') and self.vlc_player:
            vlc_mod = get_vlc_module()
            state = self.vlc_player.get_state() if vlc_mod else None
            length = self.vlc_player.get_length()
            if length > 0:
                cur = self.vlc_player.get_time()
                if vlc_mod and state == vlc_mod.State.Ended:
                    cur = length
                target = max(0, min(length, cur + offset_ms))
                if vlc_mod and state in (vlc_mod.State.Ended, vlc_mod.State.Stopped):
                    self.vlc_player.stop()
                    self.vlc_player.play()
                    if hasattr(self, 'btn_play_pause'):
                        self.btn_play_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 20))
                self.vlc_player.set_time(target)
                self.update_vlc_ui()

    def on_slider_pressed(self):
        self.is_user_seeking = True

    def on_slider_released(self):
        if self.vlc_player:
            vlc_mod = get_vlc_module()
            state = self.vlc_player.get_state() if vlc_mod else None
            length = self.vlc_player.get_length()
            if length > 0:
                pos_percent = self.slider_progress.value() / 1000.0
                target_time = int(length * pos_percent)
                if vlc_mod and state in (vlc_mod.State.Ended, vlc_mod.State.Stopped):
                    self.vlc_player.stop()
                    self.vlc_player.play()
                    self.vlc_player.set_time(target_time)
                    if hasattr(self, 'btn_play_pause'):
                        self.btn_play_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 20))
                else:
                    self.vlc_player.set_time(target_time)
        self.is_user_seeking = False

    def _format_time_str(self, ms: int) -> str:
        sec = max(0, ms // 1000)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def update_vlc_ui(self):
        if not hasattr(self, "vlc_player") or not self.vlc_player or self.is_user_seeking:
            return

        try:
            if hasattr(self, "video_container") and self.video_container:
                vw, vh = self.vlc_player.video_get_size(0)
                if vw > 0 and vh > 0:
                    self.video_container.set_aspect_ratio(vw / float(vh))

            vlc_mod = get_vlc_module()
            state = self.vlc_player.get_state()
            if vlc_mod and state in (vlc_mod.State.Playing, vlc_mod.State.Paused):
                time_ms = self.vlc_player.get_time()
                length_ms = self.vlc_player.get_length()

                if length_ms > 0 and time_ms >= 0:
                    val = int((time_ms / float(length_ms)) * 1000)
                    self.slider_progress.setValue(val)
                    self._update_time_label(time_ms, length_ms)
            elif vlc_mod and state == vlc_mod.State.Ended:
                if hasattr(self, 'btn_play_pause'):
                    self.btn_play_pause.setIcon(get_minimalist_svg_icon("play", "#FFFFFF", 20))
                self.slider_progress.setValue(1000)
                length_ms = self.vlc_player.get_length()
                if length_ms > 0:
                    self._update_time_label(length_ms, length_ms)
        except Exception:
            pass

    def copy_image(self):
        if hasattr(self, 'item_path') and os.path.exists(self.item_path):
            abs_path = os.path.abspath(self.item_path)
            img = QImage(abs_path)
            if not img.isNull():
                mime_data = QMimeData()
                mime_data.setImageData(img)
                mime_data.setUrls([QUrl.fromLocalFile(abs_path)])
                QApplication.clipboard().setMimeData(mime_data)
                QMessageBox.information(self, "Jade", "¡Imagen HD copiada al portapapeles!")

    def run_ocr(self):
        if hasattr(self, 'pixmap') and not self.pixmap.isNull():
            self.ocr_requested.emit(self.pixmap)

    def _update_time_label(self, pos_ms: int, dur_ms: int):
        pos_sec = max(0, pos_ms // 1000)
        dur_sec = max(0, dur_ms // 1000)
        if hasattr(self, "lbl_time"):
            self.lbl_time.setText(f"{pos_sec//60:02d}:{pos_sec%60:02d} / {dur_sec//60:02d}:{dur_sec%60:02d}")

    def _cleanup_vlc(self):
        if hasattr(self, 'timer') and self.timer:
            try:
                self.timer.stop()
                self.timer.deleteLater()
            except Exception: pass
            self.timer = None

        player = getattr(self, 'vlc_player', None)
        instance = getattr(self, 'vlc_instance', None)
        self.vlc_player = None
        self.vlc_instance = None

        if player or instance:
            def _async_release(p, inst):
                try:
                    if p:
                        p.pause()
                        p.stop()
                        p.release()
                    if inst:
                        inst.release()
                except Exception:
                    pass

            t = threading.Thread(target=_async_release, args=(player, instance), daemon=True)
            t.start()

    def closeEvent(self, event):
        self._cleanup_vlc()
        super().closeEvent(event)
        import gc
        gc.collect()