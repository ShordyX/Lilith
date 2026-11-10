from theme_manager import ThemeManager, ThemePalette, get_perla_appdata_dir, enable_win11_effects, detect_windows_system_theme
import os
import sys
import math
import json
import shutil
import hashlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QThread, QRunnable, QThreadPool, QObject, pyqtSignal, pyqtSlot,
    QRect, QRectF, QPoint, QPointF, QSize, QTimer, QUrl, QEvent,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QFont,
    QKeySequence, QAction, QCursor, QImage, QPainterPath,
    QLinearGradient, QShortcut, QImageReader
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QScrollArea, QFrame, QDialog, QSplitter,
    QSlider, QMenu, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QSizePolicy, QInputDialog, QStackedWidget, QProgressBar
)

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import bisect
from PyQt6 import sip
import winreg

from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

def _qt_message_filter(msg_type, context, message):
    if "sBIT: bad length" in message or "iCCP: known incorrect sRGB profile" in message:
        return
    if msg_type in (QtMsgType.QtFatalMsg, QtMsgType.QtCriticalMsg):
        sys.stderr.write(f"{message}\n")

qInstallMessageHandler(_qt_message_filter)

def apply_fade_transition(widget: QWidget, duration_ms: int = 180):
    if not widget:
        return
    try:
        if sip.isdeleted(widget):
            return
    except Exception:
        return

    old_anim = getattr(widget, "_current_fade_anim", None)
    if old_anim:
        try:
            old_anim.stop()
        except Exception:
            pass
        widget._current_fade_anim = None
    try:
        widget.setGraphicsEffect(None)
    except Exception:
        pass

    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.15)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _on_anim_finished():
        try:
            if not sip.isdeleted(widget):
                widget.setGraphicsEffect(None)
                widget._current_fade_anim = None
        except Exception:
            pass

    anim.finished.connect(_on_anim_finished)
    widget._current_fade_anim = anim
    anim.start()

VLC_AVAILABLE = False
VLC_PLUGIN_PATH = None
vlc = None

def get_jade_appdata_dir() -> str:
    appdata = os.path.expanduser(r"~\AppData\Roaming\Jade")
    os.makedirs(appdata, exist_ok=True)
    os.makedirs(os.path.join(appdata, "bin"), exist_ok=True)
    os.makedirs(os.path.join(appdata, "logs"), exist_ok=True)
    os.makedirs(os.path.join(appdata, "cache", "galeria_thumbs"), exist_ok=True)
    os.makedirs(os.path.join(appdata, "cache", "galeria_reels"), exist_ok=True)
    return appdata

def log_message(msg: str):
    try:
        log_dir = os.path.join(get_jade_appdata_dir(), "logs")
        log_file = os.path.join(log_dir, "jade_debug.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except Exception:
        pass

def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))

    candidates = [
        os.path.join(base_path, relative_path),
        os.path.join(base_path, ".py", "resources", "icon.ico"),
        os.path.join(base_path, "resources", "icon.ico"),
        os.path.join(os.getcwd(), ".py", "resources", "icon.ico"),
        os.path.join(os.getcwd(), "resources", "icon.ico")
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]

def detect_windows_system_theme() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "claro" if value == 1 else "oscuro"
    except Exception:
        return "oscuro"

def get_main_config() -> dict:
    for base in [get_jade_appdata_dir(), os.path.expanduser(r"~\AppData\Roaming\Jade")]:
        cfg_file = os.path.join(base, "config.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def find_and_setup_vlc():
    global VLC_AVAILABLE, VLC_PLUGIN_PATH, vlc
    appdata_roaming = get_jade_appdata_dir()
    appdata_local = os.path.expanduser(r"~\AppData\Roaming\Jade")
    vlc_paths = [
        os.path.join(appdata_roaming, "bin", "vlc"),
        os.path.join(appdata_local, "bin", "vlc"),
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC"
    ]
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        vlc_paths.insert(0, exe_dir)
        vlc_paths.insert(1, os.path.join(exe_dir, "vlc"))
    if hasattr(sys, "_MEIPASS"):
        vlc_paths.insert(0, sys._MEIPASS)

    for p in vlc_paths:
        dll_path = os.path.join(p, "libvlc.dll")
        if os.path.exists(dll_path):
            if hasattr(os, "add_dll_directory"):
                try: os.add_dll_directory(p)
                except Exception: pass
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

            plugins_dir = os.path.join(p, "plugins")
            if os.path.exists(plugins_dir):
                VLC_PLUGIN_PATH = plugins_dir
                os.environ["VLC_PLUGIN_PATH"] = plugins_dir

            try:
                import vlc as _vlc_mod
                vlc = _vlc_mod
                VLC_AVAILABLE = True
                return True
            except Exception as e:
                log_message(f"Error importando vlc tras encontrar libvlc.dll en {p}: {e}")
    return False

find_and_setup_vlc()

try:
    from reproductor import HDMediaViewerDialog
except Exception:
    HDMediaViewerDialog = None

class LRUBoundedCache:
    def __init__(self, max_items: int = 1500):
        self.max_items = max_items
        self._data = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key, default=None):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            return default

    def set(self, key, value):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            if len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def __contains__(self, key):
        with self._lock:
            return key in self._data

    def __getitem__(self, key):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            raise KeyError(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def clear(self):
        with self._lock:
            self._data.clear()

os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"

try:
    import cv2
    cv2.setLogLevel(0)
except Exception:
    pass

_RAM_PIXMAP_CACHE = LRUBoundedCache(max_items=250)
_ASPECT_RATIO_CACHE = LRUBoundedCache(max_items=8000)
_VIDEO_PREVIEW_FRAMES_CACHE = LRUBoundedCache(max_items=40)
_THUMB_POOL = QThreadPool()
_THUMB_POOL.setMaxThreadCount(min(4, max(2, (os.cpu_count() or 4) // 2)))

def clear_layout_safely(layout):
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            if hasattr(widget, "cleanup_resources"):
                try:
                    widget.cleanup_resources()
                except Exception:
                    pass
            widget.hide()
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout_safely(child_layout)

VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ts', '.mts', '.m2ts', '.vob', '.ogv', '.asf', '.f4v', '.mpg', '.mpeg', '.mpv')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif', '.ico', '.tiff', '.tif', '.jfif', '.heic', '.heif', '.avif', '.svg')
ALL_MEDIA_EXTS = IMAGE_EXTS + VIDEO_EXTS

def is_video_file(path_str: str) -> bool:
    return path_str.lower().endswith(VIDEO_EXTS)

_MTIME_CACHE = LRUBoundedCache(max_items=8000)

def get_thumbnail_cache_path(media_path: str, size: int) -> str:
    cache_dir = os.path.join(get_jade_appdata_dir(), "cache", "galeria_thumbs")
    mtime = _MTIME_CACHE.get(media_path)
    if mtime is None:
        try:
            mtime = os.path.getmtime(media_path)
            _MTIME_CACHE.set(media_path, mtime)
        except Exception:
            mtime = 0
    key = f"{media_path}_{mtime}_{size}".encode("utf-8")
    h = hashlib.md5(key).hexdigest()
    ext = ".png" if media_path.lower().endswith(('.png', '.webp', '.ico', '.svg')) else ".jpg"
    return os.path.join(cache_dir, f"{h}{ext}")

def get_media_aspect_ratio_fast(media_path: str) -> float:
    cached = _ASPECT_RATIO_CACHE.get(media_path)
    if cached is not None:
        return cached

    if is_video_file(media_path):
        default_ar = 0.5625 if any(k in media_path.lower() for k in ["reel", "tiktok", "short", "story", "status", "snap"]) else 1.77
        _ASPECT_RATIO_CACHE.set(media_path, default_ar)
        return default_ar

    default_ar = 1.33
    _ASPECT_RATIO_CACHE.set(media_path, default_ar)
    return default_ar

import re

def get_gallery_profile_path() -> str:
    return os.path.join(get_jade_appdata_dir(), "gallery_profile.json")

def get_gallery_db_path() -> str:
    return os.path.join(get_jade_appdata_dir(), "galeria.json")

def get_excluded_db_path() -> str:
    return os.path.join(get_jade_appdata_dir(), "excluir.json")

USER_PROTECTED_DIRS = {
    os.path.normpath(os.path.expanduser("~")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Pictures")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Videos")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Desktop")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Documents")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Downloads")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Pictures", "Jade")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Videos", "Jade")).lower(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "Music", "Jade")).lower(),
    os.path.normpath(get_jade_appdata_dir()).lower()
}

def get_album_group_key(name: str) -> str:
    cleaned = name.strip()
    cleaned = re.sub(r'\s*[\(\[\{][^\(\)\[\]\{\}]*[\)\]\}]\s*$', '', cleaned).strip()
    cleaned = re.sub(r'[\-_\s]*(copia|\d+|_files)$', '', cleaned, flags=re.IGNORECASE).strip()
    if not cleaned:
        cleaned = name.strip()
    return cleaned.lower()

def load_excluded_data() -> tuple[set, set]:
    p = get_excluded_db_path()
    folders = set()
    files = set()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, list):
                    folders = {os.path.normpath(x) for x in data if x}
                elif isinstance(data, dict):
                    folders = {os.path.normpath(x) for x in data.get("excluded_folders", []) if x}
                    files = {os.path.normpath(x) for x in data.get("excluded_files", []) if x}
        except Exception:
            pass
    return folders, files

def load_excluded_folders() -> set:
    folders, _ = load_excluded_data()
    cleaned = set()
    for f in folders:
        if not f:
            continue
        item_str = str(f).strip()
        item_lower = item_str.lower()
        if item_lower.startswith("name::") or item_lower.startswith("group::"):
            cleaned.add(item_str)
            continue
        norm = os.path.normpath(item_str).lower()
        bname = os.path.basename(norm).lower()
        if bname == "jade" or norm.endswith(os.sep.lower() + "jade"):
            continue
        if norm not in USER_PROTECTED_DIRS:
            cleaned.add(item_str)
    return cleaned

def load_excluded_files() -> set:
    _, files = load_excluded_data()
    return files

def save_excluded_data(excluded_folders: set, excluded_files: set):
    p = get_excluded_db_path()
    try:
        data = {
            "excluded_folders": sorted(list(excluded_folders)),
            "excluded_files": sorted(list(excluded_files))
        }
        with open(p, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=4, ensure_ascii=False)
    except Exception:
        pass

def save_excluded_folders(excluded_paths: set):
    _, files = load_excluded_data()
    save_excluded_data(excluded_paths, files)

def save_excluded_files(excluded_files_set: set):
    folders, _ = load_excluded_data()
    save_excluded_data(folders, excluded_files_set)

class FastExclusionMatcher:
    def __init__(self, raw_excluded: set):
        self.exact_folders = set()
        self.exact_folder_names = set()
        self.parent_prefixes = []
        self.group_keys = set()

        if not raw_excluded:
            self.parent_prefixes_tuple = ()
            return

        for item in raw_excluded:
            if not item:
                continue
            item_str = str(item).strip()
            item_lower = item_str.lower()
            if not item_str or len(item_str) < 2:
                continue

            if item_lower.startswith("name::"):
                name_key = item_str.split("::", 1)[1].strip().lower()
                if name_key and name_key != "jade":
                    self.exact_folder_names.add(name_key)
                continue

            if item_lower.startswith("group::"):
                g_key = item_str.split("::", 1)[1].strip().lower()
                if g_key != "jade" and len(g_key) >= 2:
                    self.group_keys.add(g_key)
                continue

            if os.sep not in item_str and "/" not in item_str and "\\" not in item_str:
                if item_lower != "jade" and len(item_lower) >= 2:
                    self.exact_folder_names.add(item_lower)
                continue

            norm = os.path.normpath(item_str).lower()
            bname = os.path.basename(norm).lower()
            if bname == "jade" or norm in USER_PROTECTED_DIRS or len(norm) <= 3:
                continue

            self.exact_folders.add(norm)
            self.parent_prefixes.append(norm + os.sep.lower())

        self.parent_prefixes_tuple = tuple(self.parent_prefixes)

    def is_excluded(self, folder_path: str) -> bool:
        if not folder_path:
            return False

        norm = os.path.normpath(folder_path).lower()
        bname = os.path.basename(norm).lower()

        if bname == "jade" or norm.endswith(os.sep.lower() + "jade") or norm in USER_PROTECTED_DIRS:
            return False

        if self.exact_folder_names:
            normalized_parts = norm.replace("/", "\\").split("\\")
            for part in normalized_parts:
                if part and part in self.exact_folder_names:
                    return True

        if norm in self.exact_folders:
            return True

        if self.parent_prefixes_tuple and norm.startswith(self.parent_prefixes_tuple):
            return True

        if self.group_keys:
            target_key = get_album_group_key(bname)
            if target_key != "jade" and target_key in self.group_keys:
                return True

        return False

_MATCHER_CACHE = {}

def get_exclusion_matcher(excluded_set: set) -> FastExclusionMatcher:
    if not excluded_set:
        return FastExclusionMatcher(set())
    try:
        key = frozenset(excluded_set)
    except Exception:
        key = tuple(sorted(list(excluded_set)))
    matcher = _MATCHER_CACHE.get(key)
    if matcher is None:
        matcher = FastExclusionMatcher(excluded_set)
        if len(_MATCHER_CACHE) > 6:
            _MATCHER_CACHE.clear()
        _MATCHER_CACHE[key] = matcher
    return matcher

def is_folder_excluded(folder_path: str, excluded_set: set) -> bool:
    if not folder_path or not excluded_set:
        return False
    return get_exclusion_matcher(excluded_set).is_excluded(folder_path)

def load_gallery_db() -> dict:
    p = get_gallery_db_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                excluded = load_excluded_folders()
                if excluded and "albums" in data:
                    matcher = get_exclusion_matcher(excluded)
                    data["albums"] = [a for a in data["albums"] if not matcher.is_excluded(a.get("folder_path", ""))]
                return data
        except Exception:
            pass
    return {"albums": []}

def save_gallery_db(db_data: dict):
    p = get_gallery_db_path()
    try:
        with open(p, "w", encoding="utf-8") as fp:
            json.dump(db_data, fp, indent=4, ensure_ascii=False)
    except Exception:
        pass

def sync_gallery_db_from_folders(folders: list) -> dict:
    existing_db = load_gallery_db()
    cached_albums_map = {os.path.normpath(a.get("folder_path", "")): a for a in existing_db.get("albums", []) if a.get("folder_path")}
    excluded = load_excluded_folders()
    albums = []
    seen = set()

    for root_fldr in folders:
        if not root_fldr or not os.path.exists(root_fldr) or not os.path.isdir(root_fldr):
            continue

        candidate_dirs = [root_fldr]
        try:
            with os.scandir(root_fldr) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        candidate_dirs.append(entry.path)
        except Exception:
            pass

        for fldr in candidate_dirs:
            norm = os.path.normpath(fldr)
            if norm in seen or is_folder_excluded(norm, excluded):
                continue
            seen.add(norm)

            if norm in cached_albums_map and cached_albums_map[norm].get("cover_path") and cached_albums_map[norm].get("count", 0) > 0:
                albums.append(cached_albums_map[norm])
                continue

            cover_path = ""
            media_files = []
            try:
                with os.scandir(norm) as it:
                    for entry in it:
                        if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(ALL_MEDIA_EXTS):
                            media_files.append(entry.path)
            except (PermissionError, OSError):
                continue

            if media_files:
                media_files.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
                cover_path = media_files[0]
                albums.append({
                    "folder_path": norm,
                    "name": os.path.basename(norm) or norm,
                    "cover_path": cover_path,
                    "count": len(media_files),
                    "media_files": media_files
                })

    # Prioridad: Las carpetas Jade siempre aparecen en primer lugar
    albums.sort(key=lambda x: (0 if any(k in x.get("name", "").lower() for k in ["perla", "jade"]) else 1, x.get("name", "").lower()))
    db = {"albums": albums}
    save_gallery_db(db)
    return db

def load_gallery_profile() -> dict:
    p = get_gallery_profile_path()
    default_user = "Usuario"
    try:
        import getpass
        default_user = getpass.getuser().capitalize()
    except Exception:
        pass

    main_cfg = get_main_config()
    main_avatar = main_cfg.get("user_avatar", "")
    user_home = os.path.expanduser("~")
    pics = os.path.join(user_home, "Pictures")
    jade_pics = main_cfg.get("images_folder") or os.path.join(pics, "Jade")
    jade_vids = main_cfg.get("videos_folder") or os.path.join(user_home, "Videos", "Jade")
    jade_auds = main_cfg.get("audios_folder") or os.path.join(user_home, "Music", "Jade")

    default_folders = []
    for f in [jade_pics, jade_vids, pics, os.path.join(user_home, "Videos"), jade_auds]:
        if f and os.path.exists(f) and f not in default_folders:
            default_folders.append(os.path.normpath(f))
    if not default_folders:
        default_folders.append(user_home)

    data = {
        "username": default_user,
        "avatar_path": main_avatar,
        "allowed_folders": default_folders
    }

    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as fp:
                saved = json.load(fp)
                data.update(saved)

            raw_folders = data.get("allowed_folders", [])
            cleaned_folders = []
            seen_clean = set()

            for fldr in raw_folders:
                if fldr and os.path.exists(fldr) and os.path.isdir(fldr):
                    norm = os.path.normpath(fldr)
                    if norm not in seen_clean:
                        seen_clean.add(norm)
                        cleaned_folders.append(norm)

            if not cleaned_folders:
                cleaned_folders = default_folders

            data["allowed_folders"] = cleaned_folders
        except Exception:
            pass

    if not data.get("avatar_path") or not os.path.exists(data.get("avatar_path", "")):
        if main_avatar and os.path.exists(main_avatar):
            data["avatar_path"] = main_avatar

    return data

def save_gallery_profile(data: dict):
    p = get_gallery_profile_path()
    try:
        with open(p, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=4, ensure_ascii=False)
    except Exception:
        pass

class AllowedFoldersDialog(QDialog):
    folders_updated = pyqtSignal()

    def __init__(self, current_folders: list, parent=None):
        super().__init__(parent)
        self.folders = list(current_folders)
        self.setWindowTitle("Carpetas permitidas para Jade")
        self.resize(520, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_desc = QLabel("Selecciona las carpetas donde Jade buscará fotos y videos:")
        layout.addWidget(lbl_desc)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(8)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Agregar Carpeta")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self.add_folder)

        btn_save = QPushButton("Guardar Cambios")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self.save_and_close)

        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

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
            QLabel {{ color: {p['text_primary']}; font-size: 13px; }}
            QPushButton {{
                background-color: {p['bg_card']};
                color: {p['text_primary']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {p['bg_card_hover']}; }}
            QPushButton#PrimaryBtn {{
                background-color: {p['accent']};
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#PrimaryBtn:hover {{ background-color: #106EBE; }}
            QScrollArea {{ border: none; background: transparent; }}
        """)
        self.refresh_list()

    def refresh_list(self):
        for i in reversed(range(self.list_layout.count())):
            w = self.list_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        is_dark = ThemeManager.get_instance().is_dark
        p = ThemePalette.get(is_dark)
        row_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.04)"
        row_border = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.08)"

        for fpath in self.folders:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: {row_bg};
                    border: 1px solid {row_border};
                    border-radius: 8px;
                    padding: 4px;
                }}
            """)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(10, 6, 10, 6)

            lbl = QLabel(fpath)
            lbl.setStyleSheet(f"color: {p['text_primary']}; font-size: 12px;")
            btn_del = QPushButton("Quitar")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet("background-color: rgba(232, 17, 35, 0.2); color: #FF99A4; border: 1px solid rgba(232, 17, 35, 0.4); padding: 4px 10px;")
            btn_del.clicked.connect(lambda _, p=fpath: self.remove_folder(p))

            r_layout.addWidget(lbl, stretch=1)
            r_layout.addWidget(btn_del)
            self.list_layout.addWidget(row)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta permitida", os.path.expanduser("~"))
        if folder and folder not in self.folders:
            self.folders.append(folder)
            self.refresh_list()

    def remove_folder(self, fpath: str):
        if fpath in self.folders:
            self.folders.remove(fpath)
            self.refresh_list()

    def save_and_close(self):
        profile = load_gallery_profile()
        profile["allowed_folders"] = self.folders
        save_gallery_profile(profile)
        self.folders_updated.emit()
        self.accept()

class TopProfileWidget(QWidget):
    profile_clicked = pyqtSignal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profile_data = load_gallery_profile()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        self.lbl_name = QLabel(self.profile_data.get("username", "Usuario"))
        self.lbl_name.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))

        self.avatar_size = 46
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(self.avatar_size, self.avatar_size)

        layout.addWidget(self.lbl_name)
        layout.addWidget(self.avatar_label)

        ThemeManager.get_instance().register_child(self)
        self.apply_theme(ThemeManager.get_instance().is_dark)
        self.update_avatar_display()

    def apply_theme(self, is_dark: bool):
        p = ThemePalette.get(is_dark)
        self.lbl_name.setStyleSheet(f"color: {p['text_primary']};")

    def update_profile(self):
        self.profile_data = load_gallery_profile()
        self.lbl_name.setText(self.profile_data.get("username", "Usuario"))
        self.update_avatar_display()

    def update_avatar_display(self):
        pix = QPixmap(self.avatar_size, self.avatar_size)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        clip_path = QPainterPath()
        clip_path.addEllipse(0, 0, self.avatar_size, self.avatar_size)
        painter.setClipPath(clip_path)

        av_path = self.profile_data.get("avatar_path", "")
        if not av_path or not os.path.exists(av_path):
            main_cfg = get_main_config()
            av_path = main_cfg.get("user_avatar", "")

        drawn = False
        if av_path and os.path.exists(av_path):
            reader = QImageReader(av_path)
            reader.setAutoTransform(True)
            img = reader.read()
            if not img.isNull():
                src_img = QPixmap.fromImage(img)
                sw = src_img.width()
                sh = src_img.height()
                scale = max(self.avatar_size / float(sw), self.avatar_size / float(sh))
                rw = int(sw * scale)
                rh = int(sh * scale)
                rx = int((self.avatar_size - rw) / 2.0)
                ry = int((self.avatar_size - rh) / 2.0)
                painter.drawPixmap(rx, ry, rw, rh, src_img)
                drawn = True

        if not drawn:
            self._draw_default_avatar(painter)

        painter.end()
        self.avatar_label.setPixmap(pix)

    def _draw_default_avatar(self, painter: QPainter):
        painter.fillRect(0, 0, self.avatar_size, self.avatar_size, QColor(24, 30, 42))
        painter.setPen(QColor(148, 163, 184))
        painter.setFont(QFont("Segoe UI Variable Display", 16, QFont.Weight.Bold))
        uname = self.profile_data.get("username", "Usuario")
        initial = uname[0].upper() if uname else "U"
        painter.drawText(QRect(0, 0, self.avatar_size, self.avatar_size), Qt.AlignmentFlag.AlignCenter, initial)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.profile_clicked.emit(self.mapToGlobal(event.pos()))
        super().mousePressEvent(event)

class FloatingBottomNavBar(QFrame):
    """Barra flotante inferior moderna con esquinas suavemente redondeadas y tipografía escalable."""
    tab_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FloatingNavPill")
        self.active_tab = "fotos"
        self._is_dark = ThemeManager.get_instance().is_dark

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(24)
        self._shadow.setOffset(0, 6)
        self.setGraphicsEffect(self._shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.btn_fotos = QPushButton("Fotos")
        self.btn_fotos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fotos.clicked.connect(lambda: self.set_active_tab("fotos"))

        self.btn_videos = QPushButton("Videos")
        self.btn_videos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_videos.clicked.connect(lambda: self.set_active_tab("videos"))

        self.btn_albumes = QPushButton("Álbumes")
        self.btn_albumes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_albumes.clicked.connect(lambda: self.set_active_tab("albumes"))

        self.btn_memorias = QPushButton("Memorias")
        self.btn_memorias.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_memorias.clicked.connect(lambda: self.set_active_tab("memorias"))

        self.btn_buscador = QPushButton("Buscador")
        self.btn_buscador.setEnabled(False)
        self.btn_buscador.setToolTip("Buscador (Próximamente)")

        self.btn_explorar = QPushButton("Explorar")
        self.btn_explorar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_explorar.clicked.connect(lambda: self.set_active_tab("explorar"))

        layout.addWidget(self.btn_fotos)
        layout.addWidget(self.btn_videos)
        layout.addWidget(self.btn_albumes)
        layout.addWidget(self.btn_memorias)
        layout.addWidget(self.btn_buscador)
        layout.addWidget(self.btn_explorar)

        self.buttons = {
            "fotos": self.btn_fotos,
            "videos": self.btn_videos,
            "albumes": self.btn_albumes,
            "memorias": self.btn_memorias,
            "explorar": self.btn_explorar
        }

        ThemeManager.get_instance().register_child(self)
        self.apply_theme(self._is_dark)

    def apply_theme(self, is_dark: bool):
        self._is_dark = is_dark
        if is_dark:
            bg = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(22, 28, 42, 0.88), stop:1 rgba(12, 16, 26, 0.94))"
            border = "1px solid rgba(255, 255, 255, 0.12)"
            border_top = "1px solid rgba(255, 255, 255, 0.24)"
            inactive_color = "#94A3B8"
            hover_color = "#FFFFFF"
            hover_bg = "rgba(255, 255, 255, 0.08)"
            hover_border = "rgba(255, 255, 255, 0.12)"
            self._shadow.setColor(QColor(0, 0, 0, 180))
        else:
            bg = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.95), stop:1 rgba(240, 244, 248, 0.98))"
            border = "1px solid rgba(0, 0, 0, 0.12)"
            border_top = "1px solid rgba(0, 0, 0, 0.06)"
            inactive_color = "#64748B"
            hover_color = "#0F172A"
            hover_bg = "rgba(0, 0, 0, 0.06)"
            hover_border = "rgba(0, 0, 0, 0.10)"
            self._shadow.setColor(QColor(0, 0, 0, 45))

        self.setStyleSheet(f"""
            QFrame#FloatingNavPill {{
                background: {bg};
                border: {border};
                border-top: {border_top};
                border-radius: 14px;
            }}
            QPushButton {{
                background-color: transparent;
                color: {inactive_color};
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 7px 16px;
                font-size: 10.5pt;
                font-weight: 600;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }}
            QPushButton:hover:enabled {{
                color: {hover_color};
                background-color: {hover_bg};
                border: 1px solid {hover_border};
            }}
            QPushButton:disabled {{
                color: #94A3B8;
                background-color: transparent;
                border: 1px solid transparent;
            }}
        """)
        self.update_buttons_style()

    def set_active_tab(self, tab: str):
        if self.active_tab != tab and tab in self.buttons:
            self.active_tab = tab
            self.update_buttons_style()
            self.tab_changed.emit(tab)

    def update_buttons_style(self):
        active_style = """
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0078D4, stop:1 #005A9E);
            color: #FFFFFF;
            font-weight: bold;
            font-size: 10.5pt;
            border: 1px solid rgba(255, 255, 255, 0.25);
            border-radius: 8px;
            padding: 7px 16px;
            font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
        """
        inactive_color = "#94A3B8" if self._is_dark else "#64748B"
        inactive_style = f"""
            background-color: transparent;
            color: {inactive_color};
            font-weight: 600;
            font-size: 10.5pt;
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 7px 16px;
            font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
        """

        for key, btn in self.buttons.items():
            if key == self.active_tab:
                btn.setStyleSheet(active_style)
            else:
                btn.setStyleSheet(inactive_style)

class FastThumbWorkerSignals(QObject):
    ready = pyqtSignal(str, QImage)

_CACHED_FFMPEG_PATH = None

def locate_ffmpeg_executable() -> str:
    global _CACHED_FFMPEG_PATH
    if _CACHED_FFMPEG_PATH is not None:
        return _CACHED_FFMPEG_PATH

    bin_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    base_dirs = [
        os.path.join(get_jade_appdata_dir(), "bin"),
        os.path.join(os.path.expanduser(r"~\AppData\Roaming\Jade"), "bin"),
        get_jade_appdata_dir(),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "ffmpeg", "bin"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "ffmpeg", "bin")
    ]
    for d in base_dirs:
        cand = os.path.join(d, bin_name)
        if os.path.exists(cand) and os.path.isfile(cand) and os.path.getsize(cand) > 1000000:
            _CACHED_FFMPEG_PATH = cand
            return cand

    f = shutil.which(bin_name) or shutil.which("ffmpeg")
    if f and os.path.exists(f):
        _CACHED_FFMPEG_PATH = f
        return f

    _CACHED_FFMPEG_PATH = ""
    return ""

_FAILED_VIDEO_THUMBS = set()

def extract_robust_video_thumbnail(ffmpeg_bin: str, video_path: str, target_path: str, target_size: int = 320) -> bool:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    flags = 0x08000000
    tmp_path = f"{target_path}.tmp_{os.getpid()}_{threading.get_ident()}.jpg"

    if ffmpeg_bin and os.path.exists(ffmpeg_bin):
        cmd = [
            ffmpeg_bin, "-nostdin", "-hide_banner", "-loglevel", "quiet",
            "-err_detect", "ignore_err", "-y",
            "-ss", "00:00:00.500", "-i", video_path,
            "-vf", f"scale={target_size}:-2",
            "-vframes", "1", "-an", "-sn", "-q:v", "4", tmp_path
        ]
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=flags,
                timeout=3.5
            )
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 200:
                os.replace(tmp_path, target_path)
                return True
        except Exception:
            pass

        cmd_fallback = [
            ffmpeg_bin, "-nostdin", "-hide_banner", "-loglevel", "quiet",
            "-err_detect", "ignore_err", "-y",
            "-i", video_path,
            "-vf", f"scale={target_size}:-2",
            "-vframes", "1", "-an", "-sn", "-q:v", "5", tmp_path
        ]
        try:
            subprocess.run(
                cmd_fallback,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=flags,
                timeout=3.5
            )
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 200:
                os.replace(tmp_path, target_path)
                return True
        except Exception:
            pass

    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return False

class FastThumbnailRunnable(QRunnable):
    def __init__(self, media_path: str, target_size: int = 480):
        super().__init__()
        self.media_path = media_path
        self.target_size = target_size
        self.signals = FastThumbWorkerSignals()
        self.setAutoDelete(True)
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if self._is_cancelled:
            return
        try:
            if not os.path.exists(self.media_path):
                return

            c_path = get_thumbnail_cache_path(self.media_path, self.target_size)
            if os.path.exists(c_path) and os.path.getsize(c_path) > 200:
                if self._is_cancelled:
                    return
                img = QImage(c_path)
                if not img.isNull():
                    if img.height() > 0:
                        _ASPECT_RATIO_CACHE.set(self.media_path, max(0.55, min(2.4, img.width() / float(img.height()))))
                    if not self._is_cancelled:
                        self.signals.ready.emit(self.media_path, img)
                    return
                else:
                    try:
                        os.remove(c_path)
                    except Exception:
                        pass

            if self._is_cancelled:
                return

            tmp_path = f"{c_path}.tmp_{os.getpid()}_{threading.get_ident()}.jpg"
            extracted = False

            if is_video_file(self.media_path):
                if self.media_path in _FAILED_VIDEO_THUMBS:
                    extracted = False
                else:
                    ffmpeg_bin = locate_ffmpeg_executable()
                    if self._is_cancelled:
                        return
                    extracted = extract_robust_video_thumbnail(ffmpeg_bin, self.media_path, c_path, self.target_size)
                    if not extracted:
                        _FAILED_VIDEO_THUMBS.add(self.media_path)
            else:
                if self._is_cancelled:
                    return

                try:
                    from PIL import Image, ImageOps
                    with Image.open(self.media_path) as pil_img:
                        if self._is_cancelled:
                            return
                        orig_w, orig_h = pil_img.size
                        if orig_h > 0:
                            _ASPECT_RATIO_CACHE.set(self.media_path, max(0.55, min(2.4, orig_w / float(orig_h))))

                        if pil_img.format in ("JPEG", "JPG", "MPO"):
                            pil_img.draft("RGB", (self.target_size * 2, self.target_size * 2))

                        if hasattr(ImageOps, "exif_transpose"):
                            try:
                                pil_img = ImageOps.exif_transpose(pil_img)
                            except Exception:
                                pass

                        if pil_img.mode not in ("RGB", "RGBA"):
                            pil_img = pil_img.convert("RGB")

                        pil_img.thumbnail((self.target_size, self.target_size), Image.Resampling.BILINEAR)
                        pil_img.save(tmp_path, "JPEG", quality=78, optimize=False)
                        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 200:
                            os.replace(tmp_path, c_path)
                            extracted = True
                except Exception:
                    pass

                if not extracted and not self._is_cancelled:
                    try:
                        reader = QImageReader(self.media_path)
                        reader.setAllocationLimit(4096)
                        reader.setAutoTransform(True)
                        sz = reader.size()
                        if sz.isValid() and sz.height() > 0:
                            _ASPECT_RATIO_CACHE.set(self.media_path, max(0.55, min(2.4, sz.width() / float(sz.height()))))
                            if sz.width() > self.target_size or sz.height() > self.target_size:
                                target_decode_size = sz.scaled(self.target_size, self.target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
                                reader.setScaledSize(target_decode_size)

                        img = reader.read()
                        if not img.isNull():
                            scaled = img.scaled(
                                self.target_size, self.target_size,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.FastTransformation
                            )
                            scaled.save(tmp_path, "JPG", 78)
                            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 200:
                                os.replace(tmp_path, c_path)
                                extracted = True
                    except Exception:
                        pass

            if not extracted or not (os.path.exists(c_path) and os.path.getsize(c_path) > 200):
                fallback_img = QImage(self.target_size, int(self.target_size * 0.5625), QImage.Format.Format_RGB32)
                fallback_img.fill(QColor(18, 24, 36))
                fallback_img.save(tmp_path, "JPG", 70)
                if os.path.exists(tmp_path):
                    os.replace(tmp_path, c_path)

            if not self._is_cancelled and os.path.exists(c_path) and os.path.getsize(c_path) > 200:
                img = QImage(c_path)
                if not img.isNull():
                    if img.height() > 0:
                        _ASPECT_RATIO_CACHE.set(self.media_path, max(0.55, min(2.4, img.width() / float(img.height()))))
                    if not self._is_cancelled:
                        self.signals.ready.emit(self.media_path, img)
        except Exception:
            pass

class VideoPreviewExtractRunnable(QRunnable):
    """Extrae 5 fotogramas secuenciales en segundo plano garantizando soporte a videos de cualquier duración para Reels en hover."""
    def __init__(self, video_path: str, target_size: int = 320):
        super().__init__()
        self.video_path = video_path
        self.target_size = target_size
        self.signals = FastThumbWorkerSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            if not os.path.exists(self.video_path):
                return

            v_hash = hashlib.md5(f"{self.video_path}_{os.path.getmtime(self.video_path)}".encode("utf-8")).hexdigest()
            cache_dir = os.path.join(get_jade_appdata_dir(), "cache", "galeria_reels", v_hash)
            os.makedirs(cache_dir, exist_ok=True)

            frames = []
            cached_files = [os.path.join(cache_dir, f"frame_{i}.jpg") for i in range(5)]
            all_cached = all(os.path.exists(f) and os.path.getsize(f) > 0 for f in cached_files)

            if all_cached:
                for f in cached_files:
                    p = QPixmap(f)
                    if not p.isNull():
                        frames.append(p)
                if len(frames) == 5:
                    _VIDEO_PREVIEW_FRAMES_CACHE[self.video_path] = frames
                    return

            ffmpeg_bin = locate_ffmpeg_executable()

            if ffmpeg_bin and os.path.exists(ffmpeg_bin):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                flags = 0x08000000

                timestamps = ["00:00:00.200", "00:00:01.000", "00:00:02.500", "00:00:04.000", "00:00:06.000"]
                for i, ts in enumerate(timestamps):
                    out_f = cached_files[i]
                    if not (os.path.exists(out_f) and os.path.getsize(out_f) > 0):
                        cmd = [
                            ffmpeg_bin, "-y", "-ss", ts, "-i", self.video_path,
                            "-vf", f"scale={self.target_size}:-2", "-vframes", "1",
                            "-q:v", "6", out_f
                        ]
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo, creationflags=flags, timeout=3)
                        if not (os.path.exists(out_f) and os.path.getsize(out_f) > 0):
                            fallback_main = get_thumbnail_cache_path(self.video_path, self.target_size)
                            if os.path.exists(fallback_main) and os.path.getsize(fallback_main) > 0:
                                shutil.copy2(fallback_main, out_f)

                    if os.path.exists(out_f) and os.path.getsize(out_f) > 0:
                        p = QPixmap(out_f)
                        if not p.isNull():
                            frames.append(p)

                if frames:
                    _VIDEO_PREVIEW_FRAMES_CACHE[self.video_path] = frames
        except Exception:
            pass

class SmoothScrollArea(QScrollArea):
    """Área de scroll cinético suave basada en física de inercia y acumulación fluida idéntica a navegadores web."""
    near_bottom = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loading_cooldown = False
        self._target_val = 0.0
        self._current_val = 0.0

        p = ThemePalette.get(ThemeManager.get_instance().is_dark)
        self.setStyleSheet(f"background-color: {p['bg_window']}; border: none;")
        if self.viewport():
            self.viewport().setStyleSheet(f"background-color: {p['bg_window']};")

        ThemeManager.get_instance().register_child(self)

    def apply_theme(self, is_dark: bool):
        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"background-color: {p['bg_window']}; border: none;")
        if self.viewport():
            self.viewport().setStyleSheet(f"background-color: {p['bg_window']};")

        self._smooth_timer = QTimer(self)
        self._smooth_timer.setInterval(14)
        self._smooth_timer.timeout.connect(self._step_smooth_scroll)

        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.setSingleShot(True)
        self._cooldown_timer.setInterval(220)
        self._cooldown_timer.timeout.connect(self._reset_cooldown)

        vbar = self.verticalScrollBar()
        if vbar:
            vbar.valueChanged.connect(self._on_scroll_changed)

    def _reset_cooldown(self):
        self._is_loading_cooldown = False

    def _on_scroll_changed(self, value):
        if not self._smooth_timer.isActive():
            self._current_val = float(value)
            self._target_val = float(value)

        vbar = self.verticalScrollBar()
        if vbar and not self._is_loading_cooldown:
            max_v = vbar.maximum()
            if max_v > 0 and value >= max_v - 750:
                self._is_loading_cooldown = True
                self.near_bottom.emit()
                self._cooldown_timer.start()

    def check_and_fill(self):
        vbar = self.verticalScrollBar()
        if vbar and vbar.maximum() <= 150 and not self._is_loading_cooldown:
            self._is_loading_cooldown = True
            self.near_bottom.emit()
            self._cooldown_timer.start()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            vbar = self.verticalScrollBar()
            if not vbar:
                return

            max_v = vbar.maximum()
            if max_v <= 0:
                return

            if not self._smooth_timer.isActive():
                self._current_val = float(vbar.value())
                self._target_val = self._current_val

            step = -float(delta) * 1.20
            self._target_val = max(0.0, min(float(max_v), self._target_val + step))

            if not self._smooth_timer.isActive():
                self._smooth_timer.start()

            event.accept()
        else:
            super().wheelEvent(event)

    def _step_smooth_scroll(self):
        vbar = self.verticalScrollBar()
        if not vbar:
            self._smooth_timer.stop()
            return

        max_v = float(vbar.maximum())
        self._target_val = max(0.0, min(max_v, self._target_val))

        diff = self._target_val - self._current_val
        if abs(diff) < 0.5:
            self._current_val = self._target_val
            vbar.setValue(int(round(self._target_val)))
            self._smooth_timer.stop()
            return

        self._current_val += diff * 0.20
        self._current_val = max(0.0, min(max_v, self._current_val))
        vbar.setValue(int(round(self._current_val)))
class ModernPhotoTile(QFrame):
    clicked = pyqtSignal(str)
    action_requested = pyqtSignal(str, str)

    def __init__(self, media_path: str = "", width: int = 100, height: int = 100, parent=None):
        super().__init__(parent)
        self.media_path = media_path
        self.tile_w = width
        self.tile_h = height
        self.is_video = is_video_file(media_path) if media_path else False
        self.is_hovered = False
        self._is_loading = False
        self._is_cancelled = False
        self._current_runnable = None
        self.pixmap = None

        self.setFixedSize(self.tile_w, self.tile_h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        if self.media_path:
            cached_pix = _RAM_PIXMAP_CACHE.get(self.media_path)
            if cached_pix is not None and not cached_pix.isNull():
                self.pixmap = cached_pix
            else:
                self.request_async_thumbnail()

    def bind_media(self, media_path: str, width: int, height: int):
        self.cleanup_resources()
        self.media_path = media_path
        self.tile_w = width
        self.tile_h = height
        self.is_video = is_video_file(media_path) if media_path else False
        self.setFixedSize(self.tile_w, self.tile_h)
        self.is_hovered = False
        self._is_loading = False
        self._is_cancelled = False
        self._current_runnable = None

        if not self.media_path:
            self.pixmap = None
            self.update()
            return

        cached_pix = _RAM_PIXMAP_CACHE.get(self.media_path)
        if cached_pix is not None and not cached_pix.isNull():
            self.pixmap = cached_pix
            self.update()
        else:
            self.request_async_thumbnail()

    def cleanup_resources(self):
        self._is_cancelled = True
        self._is_loading = False
        if self._current_runnable is not None:
            try:
                self._current_runnable.cancel()
            except Exception:
                pass
            self._current_runnable = None
        self.pixmap = None
        self.update()

    def ensure_loaded(self):
        if self.pixmap is not None or not self.media_path:
            return

        cached_pix = _RAM_PIXMAP_CACHE.get(self.media_path)
        if cached_pix is not None and not cached_pix.isNull():
            self.pixmap = cached_pix
            self.update()
            return

        if not self._is_loading and not self._is_cancelled:
            self.request_async_thumbnail()

    def request_async_thumbnail(self):
        if self._is_loading or not self.media_path or self._is_cancelled:
            return
        self._is_loading = True

        dpr = 1.0
        try:
            screen = self.screen() or QApplication.primaryScreen()
            if screen:
                dpr = float(screen.devicePixelRatio())
        except Exception:
            dpr = 1.0
        dpr = max(1.0, dpr)

        req_dim = int(max(self.tile_w, self.tile_h) * dpr)
        target_size = 480 if req_dim <= 480 else (640 if req_dim <= 640 else 800)

        runnable = FastThumbnailRunnable(self.media_path, target_size)
        self._current_runnable = runnable
        runnable.signals.ready.connect(self.on_thumb_ready)
        _THUMB_POOL.start(runnable, priority=60)

    def on_thumb_ready(self, path: str, img: QImage):
        self._is_loading = False
        self._current_runnable = None
        if self._is_cancelled or path != self.media_path:
            return
        try:
            if sip.isdeleted(self):
                return
        except Exception:
            return
        if not img.isNull():
            pix = QPixmap.fromImage(img)
            _RAM_PIXMAP_CACHE.set(self.media_path, pix)
            self.pixmap = pix
            self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.media_path)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, 10.0, 10.0)

        if self.pixmap and not self.pixmap.isNull():
            painter.setClipPath(path)
            sw = self.pixmap.width()
            sh = self.pixmap.height()
            scale = max(self.width() / float(sw), self.height() / float(sh))
            rw = int(sw * scale)
            rh = int(sh * scale)
            rx = int((self.width() - rw) / 2.0)
            ry = int((self.height() - rh) / 2.0)
            painter.drawPixmap(rx, ry, rw, rh, self.pixmap)
            painter.setClipping(False)
        else:
            is_dark_now = ThemeManager.get_instance().is_dark if 'ThemeManager' in globals() else True
            ph_col = QColor(20, 26, 38) if is_dark_now else QColor(226, 232, 240)
            painter.fillPath(path, ph_col)

        if self.is_video and self.pixmap and not self.pixmap.isNull():
            badge_rect = QRectF(self.width() - 52, self.height() - 24, 46, 16)
            b_path = QPainterPath()
            b_path.addRoundedRect(badge_rect, 4, 4)
            painter.fillPath(b_path, QColor(0, 0, 0, 190))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI Variable Text", 7, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "VIDEO")

        if self.is_hovered:
            painter.fillPath(path, QColor(255, 255, 255, 20))
            painter.setPen(QPen(QColor(0, 120, 212, 220), 2.0))
            painter.drawPath(path)

    def show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet(ThemePalette.get_menu_style(ThemeManager.get_instance().is_dark))

        act_view = menu.addAction("Abrir y Visualizar")
        act_copy = menu.addAction("Copiar Archivo")
        act_folder = menu.addAction("Mostrar en Explorador")
        menu.addSeparator()
        act_exclude = menu.addAction("Excluir de Jade")
        act_rename = menu.addAction("Renombrar")
        act_del = menu.addAction("Eliminar")

        action = menu.exec(self.mapToGlobal(pos))
        if action == act_view:
            self.action_requested.emit("view", self.media_path)
        elif action == act_copy:
            self.action_requested.emit("copy", self.media_path)
        elif action == act_folder:
            self.action_requested.emit("folder", self.media_path)
        elif action == act_exclude:
            self.action_requested.emit("exclude", self.media_path)
        elif action == act_rename:
            self.action_requested.emit("rename", self.media_path)
        elif action == act_del:
            self.action_requested.emit("delete", self.media_path)

def get_responsive_metrics(viewport_width: int):
    """Calcula márgenes, espaciados y alturas adaptativas desde VGA (640x480) hasta 4K (3840x2160)."""
    if viewport_width < 720:
        margin_h = 10
        margin_bottom = 40
        spacing = 6
        base_row_h = 135
        min_row_h = 100
        max_row_h = 180
    elif viewport_width < 1280:
        margin_h = 18
        margin_bottom = 54
        spacing = 8
        base_row_h = 175
        min_row_h = 130
        max_row_h = 220
    elif viewport_width < 1980:
        margin_h = 24
        margin_bottom = 64
        spacing = 10
        base_row_h = 205
        min_row_h = 150
        max_row_h = 270
    elif viewport_width < 2600:
        margin_h = 30
        margin_bottom = 72
        spacing = 12
        base_row_h = 235
        min_row_h = 170
        max_row_h = 310
    else:
        margin_h = 38
        margin_bottom = 84
        spacing = 14
        base_row_h = 265
        min_row_h = 190
        max_row_h = 350
    return margin_h, margin_bottom, spacing, base_row_h, min_row_h, max_row_h

def compute_justified_rows_engine(paths: list, available_width: int, spacing: int = 10,
                                  base_h: int = 205, min_h: int = 150, max_h: int = 270):
    rows = []
    current_row = []
    current_sum_ar = 0.0

    for fpath in paths:
        ar = get_media_aspect_ratio_fast(fpath)
        clamped_ar = max(0.55, min(2.4, ar))
        current_row.append((fpath, clamped_ar))
        current_sum_ar += clamped_ar

        row_w_at_base = (current_sum_ar * base_h) + ((len(current_row) - 1) * spacing)
        if row_w_at_base >= available_width:
            inner_w = available_width - ((len(current_row) - 1) * spacing)
            justified_h = max(min_h, min(max_h, int(inner_w / current_sum_ar)))

            widths = [max(90, int(justified_h * a)) for _, a in current_row]
            diff = inner_w - sum(widths)
            for i in range(abs(diff)):
                idx = i % len(widths)
                widths[idx] += (1 if diff > 0 else -1)

            rows.append(([(current_row[i][0], widths[i], justified_h) for i in range(len(current_row))], False))
            current_row = []
            current_sum_ar = 0.0

    if current_row:
        ideal_w = (current_sum_ar * base_h) + ((len(current_row) - 1) * spacing)
        if ideal_w >= available_width * 0.72:
            inner_w = available_width - ((len(current_row) - 1) * spacing)
            justified_h = max(min_h, min(max_h, int(inner_w / current_sum_ar)))
            widths = [max(90, int(justified_h * a)) for _, a in current_row]
            diff = inner_w - sum(widths)
            for i in range(abs(diff)):
                widths[i % len(widths)] += (1 if diff > 0 else -1)
            rows.append(([(current_row[i][0], widths[i], justified_h) for i in range(len(current_row))], False))
        else:
            rows.append(([(fpath, max(90, int(base_h * a)), base_h) for fpath, a in current_row], True))

    return rows

class VirtualRowWidget(QWidget):
    clicked = pyqtSignal(str)
    action_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        self.r_layout = QHBoxLayout(self)
        self.r_layout.setContentsMargins(0, 0, 0, 0)
        self.r_layout.setSpacing(10)
        self.r_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.tiles = []
        self.stretch_item = None

    def cleanup_resources(self):
        for tile in self.tiles:
            tile.cleanup_resources()

    def bind_data(self, items: list, row_height: int, spacing: int, is_incomplete: bool):
        self.r_layout.setSpacing(spacing)
        self.setFixedHeight(row_height)

        if self.stretch_item is not None:
            self.r_layout.removeItem(self.stretch_item)
            self.stretch_item = None

        needed_count = len(items)
        while len(self.tiles) < needed_count:
            tile = ModernPhotoTile("", 100, row_height, parent=self)
            tile.clicked.connect(self.clicked.emit)
            tile.action_requested.connect(self.action_requested.emit)
            self.r_layout.addWidget(tile)
            self.tiles.append(tile)

        for i in range(needed_count, len(self.tiles)):
            self.tiles[i].cleanup_resources()
            self.tiles[i].hide()

        for i, (path, tw, th) in enumerate(items):
            tile = self.tiles[i]
            tile.show()
            tile.bind_media(path, tw, th)

        if is_incomplete:
            self.stretch_item = self.r_layout.addStretch()

class VirtualMuralContainer(QWidget):
    clicked = pyqtSignal(str)
    action_requested = pyqtSignal(str, str)

    def __init__(self, parent_scroll_area: QScrollArea, empty_text: str = "No hay fotos ni videos.", parent=None):
        super().__init__(parent)
        self.parent_scroll_area = parent_scroll_area
        self._empty_text = empty_text
        self._all_files = []
        self._next_file_idx = 0
        self._batch_size = 90
        self._is_loading_batch = False
        self._row_layouts = []
        self._active_rows = {}
        self._row_pool = []
        self._current_visible_range = (-1, -1)
        self._total_height = 0
        self._spacing = 10
        self._margin_h = 24
        self._margin_bottom = 64
        self._last_width = 0
        self._is_recomputing = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background-color: transparent;")

        self.lbl_empty = QLabel(self._empty_text, self)
        self.lbl_empty.setFont(QFont("Segoe UI Variable Display", 12))
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.hide()

        if self.parent_scroll_area:
            if hasattr(self.parent_scroll_area, "near_bottom"):
                self.parent_scroll_area.near_bottom.connect(self.load_next_batch)
            if self.parent_scroll_area.verticalScrollBar():
                self.parent_scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)

    def set_empty_text(self, text: str):
        self._empty_text = text
        self.lbl_empty.setText(text)

    def clear_active_rows(self):
        for row_w in self._active_rows.values():
            row_w.cleanup_resources()
            row_w.hide()
            if len(self._row_pool) < 25:
                self._row_pool.append(row_w)
            else:
                row_w.setParent(None)
                row_w.deleteLater()
        self._active_rows.clear()
        self._current_visible_range = (-1, -1)

    def set_files(self, file_list: list):
        self._all_files = list(file_list)
        self._next_file_idx = 0
        self._row_layouts = []
        self.clear_active_rows()

        if not self._all_files:
            self._total_height = 300
            self.setFixedHeight(300)
            self._update_empty_label_style()
            self.lbl_empty.setGeometry(0, 40, max(300, self.width()), 100)
            self.lbl_empty.show()
            self.update()
            return

        self.lbl_empty.hide()
        vp_w = 0
        if self.parent_scroll_area and self.parent_scroll_area.viewport():
            vp_w = self.parent_scroll_area.viewport().width()
        if vp_w <= 100:
            vp_w = self.width() if self.width() > 100 else 1000

        self.recompute_layout(vp_w)

    def _update_empty_label_style(self):
        is_dark = ThemeManager.get_instance().is_dark if 'ThemeManager' in globals() else True
        p = ThemePalette.get(is_dark) if 'ThemePalette' in globals() else {'text_secondary': '#60687A'}
        self.lbl_empty.setStyleSheet(f"color: {p.get('text_secondary', '#60687A')}; padding: 40px;")

    def recompute_layout(self, width: int):
        if self._is_recomputing:
            return
        if not self._all_files:
            self.lbl_empty.setGeometry(0, 40, max(300, width), 100)
            return

        self._is_recomputing = True
        try:
            self._last_width = width
            self.clear_active_rows()

            margin_h, margin_bottom, spacing, base_row_h, min_row_h, max_row_h = get_responsive_metrics(width)
            self._margin_h = margin_h
            self._margin_bottom = margin_bottom
            self._spacing = spacing

            initial_count = max(self._batch_size, self._next_file_idx)
            initial_count = min(len(self._all_files), initial_count)
            self._next_file_idx = initial_count

            items_to_render = self._all_files[:self._next_file_idx]
            available_w = max(240, width - (margin_h * 2))

            raw_rows = compute_justified_rows_engine(
                items_to_render,
                available_width=available_w,
                spacing=spacing,
                base_h=base_row_h,
                min_h=min_row_h,
                max_h=max_row_h
            )

            self._row_layouts = []
            cur_y = 10
            for row_items, is_incomplete in raw_rows:
                if not row_items:
                    continue
                row_h = row_items[0][2]
                self._row_layouts.append({
                    "y": cur_y,
                    "height": row_h,
                    "items": row_items,
                    "is_incomplete": is_incomplete
                })
                cur_y += row_h + spacing

            self._total_height = cur_y + margin_bottom
            self.setFixedHeight(self._total_height)
            if self.parent_scroll_area:
                self.parent_scroll_area.updateGeometry()

            self._current_visible_range = (-1, -1)
            self.update_visible_rows()
        finally:
            self._is_recomputing = False

    def load_next_batch(self):
        if self._is_loading_batch or self._is_recomputing:
            return
        total = len(self._all_files)
        if self._next_file_idx >= total:
            return

        self._is_loading_batch = True
        try:
            batch_count = min(total - self._next_file_idx, self._batch_size)
            new_items = self._all_files[self._next_file_idx : self._next_file_idx + batch_count]
            self._next_file_idx += batch_count

            width = self._last_width if self._last_width > 100 else self.width()
            margin_h, margin_bottom, spacing, base_row_h, min_row_h, max_row_h = get_responsive_metrics(width)
            available_w = max(240, width - (margin_h * 2))

            cur_y = 10
            if self._row_layouts:
                last_layout = self._row_layouts[-1]
                cur_y = last_layout["y"] + last_layout["height"] + spacing

            raw_rows = compute_justified_rows_engine(
                new_items,
                available_width=available_w,
                spacing=spacing,
                base_h=base_row_h,
                min_h=min_row_h,
                max_h=max_row_h
            )

            for row_items, is_incomplete in raw_rows:
                if not row_items:
                    continue
                row_h = row_items[0][2]
                self._row_layouts.append({
                    "y": cur_y,
                    "height": row_h,
                    "items": row_items,
                    "is_incomplete": is_incomplete
                })
                cur_y += row_h + spacing

            self._total_height = cur_y + margin_bottom
            self.setFixedHeight(self._total_height)
            if self.parent_scroll_area:
                self.parent_scroll_area.updateGeometry()

            self.update_visible_rows()
        finally:
            self._is_loading_batch = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._is_recomputing:
            return
        new_w = self.width()
        if abs(new_w - self._last_width) > 6:
            self.recompute_layout(new_w)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.setGraphicsEffect(None)
        except Exception:
            pass
        self._current_visible_range = (-1, -1)
        vp_w = 0
        if self.parent_scroll_area and self.parent_scroll_area.viewport():
            vp_w = self.parent_scroll_area.viewport().width()
        if vp_w <= 100:
            vp_w = self.width() if self.width() > 100 else 1000
        if abs(vp_w - self._last_width) > 6 or not self._active_rows:
            self.recompute_layout(vp_w)
        else:
            self.update_visible_rows()

    def on_scroll_changed(self, value: int):
        self.update_visible_rows()

    def update_visible_rows(self):
        if not self._row_layouts or not self.parent_scroll_area:
            return

        vbar = self.parent_scroll_area.verticalScrollBar()
        scroll_y = vbar.value() if vbar else 0
        viewport_h = self.parent_scroll_area.viewport().height() if self.parent_scroll_area.viewport() else 800

        if not self._is_loading_batch and scroll_y + viewport_h >= self._total_height - 900:
            if self._next_file_idx < len(self._all_files):
                QTimer.singleShot(0, self.load_next_batch)

        buffer = max(int(viewport_h * 1.5), 700)
        visible_top = max(0, scroll_y - buffer)
        visible_bottom = scroll_y + viewport_h + buffer

        total_rows = len(self._row_layouts)
        y_list = [r["y"] for r in self._row_layouts]
        first_idx = max(0, bisect.bisect_right(y_list, visible_top) - 1)
        last_idx = min(total_rows - 1, bisect.bisect_right(y_list, visible_bottom))

        new_range = (first_idx, last_idx)
        if new_range == self._current_visible_range and self._active_rows:
            return
        self._current_visible_range = new_range

        needed_indices = set(range(first_idx, last_idx + 1))

        active_indices = list(self._active_rows.keys())
        for idx in active_indices:
            if idx not in needed_indices:
                row_widget = self._active_rows.pop(idx)
                row_widget.cleanup_resources()
                row_widget.hide()
                if len(self._row_pool) < 25:
                    self._row_pool.append(row_widget)
                else:
                    row_widget.setParent(None)
                    row_widget.deleteLater()

        target_w = self._last_width if self._last_width > 100 else self.width()
        available_row_w = max(240, target_w - (self._margin_h * 2))

        for idx in needed_indices:
            row_data = self._row_layouts[idx]
            if idx not in self._active_rows:
                row_widget = self._get_or_create_row(row_data)
                row_widget.setGeometry(self._margin_h, row_data["y"], available_row_w, row_data["height"])
                row_widget.show()
                self._active_rows[idx] = row_widget
            else:
                row_widget = self._active_rows[idx]
                row_widget.setGeometry(self._margin_h, row_data["y"], available_row_w, row_data["height"])
                if not row_widget.isVisible():
                    row_widget.show()

    def _get_or_create_row(self, row_data: dict) -> VirtualRowWidget:
        if self._row_pool:
            row_widget = self._row_pool.pop()
        else:
            row_widget = VirtualRowWidget(self)
            row_widget.clicked.connect(self.clicked.emit)
            row_widget.action_requested.connect(self.action_requested.emit)

        row_widget.bind_data(row_data["items"], row_data["height"], self._spacing, row_data["is_incomplete"])
        return row_widget

    def apply_theme(self, is_dark: bool):
        self._update_empty_label_style()
        for row_w in self._active_rows.values():
            for tile in row_w.tiles:
                if tile.isVisible():
                    tile.update()

class ModernAlbumTile(QFrame):
    """Tarjeta de álbum con soporte para carpetas individuales o grupos de sub-álbumes similares."""
    clicked = pyqtSignal(str)
    selection_toggled = pyqtSignal(str, bool)
    action_requested = pyqtSignal(str, object)

    def __init__(self, folder_path: str, cover_media_path: str, count: int,
                 is_group: bool = False, sub_album_count: int = 0,
                 display_title: str = "", group_data: list = None,
                 width: int = 210, height: int = 265, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.cover_path = cover_media_path
        self.count = count
        self.is_group = is_group
        self.sub_album_count = sub_album_count
        self.display_title = display_title
        self.group_data = group_data or []
        self.is_hovered = False
        self.is_selection_mode = False
        self.is_selected = False
        self.pixmap = None
        self._is_loading = False

        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        if self.cover_path:
            cached_pix = _RAM_PIXMAP_CACHE.get(self.cover_path)
            if cached_pix is not None:
                self.pixmap = cached_pix
            else:
                self.request_thumb()

    def set_selection_mode(self, enabled: bool):
        if self.is_selection_mode != enabled:
            self.is_selection_mode = enabled
            if not enabled:
                self.is_selected = False
            self.update()

    def set_selected(self, selected: bool):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()

    def toggle_selected(self):
        self.is_selected = not self.is_selected
        self.update()
        return self.is_selected

    def cleanup_resources(self):
        self._is_loading = True
        self.pixmap = None

    def ensure_loaded(self):
        if self.pixmap is None and self.cover_path and not self._is_loading:
            cached_pix = _RAM_PIXMAP_CACHE.get(self.cover_path)
            if cached_pix is not None:
                self.pixmap = cached_pix
                self.update()
            else:
                self.request_thumb()

    def request_thumb(self):
        if self.cover_path and not self._is_loading:
            self._is_loading = True
            runnable = FastThumbnailRunnable(self.cover_path, 320)
            runnable.signals.ready.connect(self.on_thumb_ready)
            _THUMB_POOL.start(runnable, priority=80)

    def on_thumb_ready(self, path: str, img: QImage):
        self._is_loading = False
        try:
            if sip.isdeleted(self):
                return
        except Exception:
            return
        if path == self.cover_path and not img.isNull():
            pix = QPixmap.fromImage(img)
            _RAM_PIXMAP_CACHE.set(self.cover_path, pix)
            self.pixmap = pix
            self.update()

    def _apply_brush_action(self):
        if not self.is_selection_mode:
            return
        is_ctrl = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
        if is_ctrl:
            if self.is_selected:
                self.set_selected(False)
                self.selection_toggled.emit(self.folder_path, False)
        else:
            if not self.is_selected:
                self.set_selected(True)
                self.selection_toggled.emit(self.folder_path, True)

    def enterEvent(self, event):
        self.is_hovered = True
        if self.is_selection_mode:
            self._apply_brush_action()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_selection_mode:
            self._apply_brush_action()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_selection_mode:
                is_ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier or QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
                if is_ctrl:
                    if self.is_selected:
                        self.set_selected(False)
                        self.selection_toggled.emit(self.folder_path, False)
                else:
                    state = self.toggle_selected()
                    self.selection_toggled.emit(self.folder_path, state)
            else:
                self.clicked.emit(self.folder_path)
        super().mousePressEvent(event)

    def show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet(ThemePalette.get_menu_style(ThemeManager.get_instance().is_dark))

        act_open = menu.addAction("Abrir Álbum" if not self.is_group else "Explorar Grupo")
        menu.addSeparator()

        if self.is_group:
            act_excl_grp = menu.addAction(f"Excluir todo este Grupo ({self.sub_album_count} álbumes)")
            action = menu.exec(self.mapToGlobal(pos))
            if action == act_open:
                self.clicked.emit(self.folder_path)
            elif action == act_excl_grp:
                self.action_requested.emit("exclude_group", self)
        else:
            act_excl_one = menu.addAction("Excluir este Álbum de Jade")
            bname = os.path.basename(self.folder_path) or self.folder_path
            act_excl_exact = menu.addAction(f"Excluir '{bname}' en TODOS los discos")
            act_excl_sim = menu.addAction("Excluir Álbumes con Nombres Similares")
            menu.addSeparator()
            act_explore = menu.addAction("Mostrar en Explorador")

            action = menu.exec(self.mapToGlobal(pos))
            if action == act_open:
                self.clicked.emit(self.folder_path)
            elif action == act_excl_one:
                self.action_requested.emit("exclude_album", self.folder_path)
            elif action == act_excl_exact:
                self.action_requested.emit("exclude_exact_name", bname)
            elif action == act_excl_sim:
                name = self.display_title or os.path.basename(self.folder_path)
                self.action_requested.emit("exclude_similar", name)
            elif action == act_explore:
                self.action_requested.emit("open_folder", self.folder_path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        is_dark_album = ThemeManager.get_instance().is_dark if 'ThemeManager' in globals() else True
        p_album = ThemePalette.get(is_dark_album)
        painter.fillRect(self.rect(), QColor(p_album['bg_window']))

        w = float(self.width())
        cover_h = float(self.height() - 52)

        if self.is_group:
            back_rect = QRectF(4, 2, w - 8, cover_h - 4)
            b_path = QPainterPath()
            b_path.addRoundedRect(back_rect, 14.0, 14.0)
            painter.fillPath(b_path, QColor(26, 34, 52) if is_dark_album else QColor(225, 232, 240))
            painter.setPen(QPen(QColor(0, 120, 212, 100), 1.5))
            painter.drawPath(b_path)

        cover_rect = QRectF(0, 6 if self.is_group else 0, w, cover_h - (6 if self.is_group else 0))
        path = QPainterPath()
        path.addRoundedRect(cover_rect, 14.0, 14.0)

        if self.pixmap and not self.pixmap.isNull():
            painter.setClipPath(path)
            sw = self.pixmap.width()
            sh = self.pixmap.height()
            tw = cover_rect.width()
            th = cover_rect.height()
            scale = max(tw / float(sw), th / float(sh))
            rw = int(sw * scale)
            rh = int(sh * scale)
            rx = int(cover_rect.x() + (tw - rw) / 2.0)
            ry = int(cover_rect.y() + (th - rh) / 2.0)
            painter.drawPixmap(rx, ry, rw, rh, self.pixmap)
            painter.setClipping(False)
        else:
            painter.fillPath(path, QColor(22, 28, 42) if is_dark_album else QColor(235, 240, 246))
            if not self.cover_path or self.count == 0:
                painter.setPen(QColor(100, 116, 139))
                painter.setFont(QFont("Segoe UI Variable Text", 9))
                painter.drawText(cover_rect, Qt.AlignmentFlag.AlignCenter, "Vacío")

        if self.is_group:
            badge_rect = QRectF(8, 12, 86, 20)
            bg_badge = QPainterPath()
            bg_badge.addRoundedRect(badge_rect, 6.0, 6.0)
            painter.fillPath(bg_badge, QColor(0, 120, 212, 220))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI Variable Text", 8, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"📁 GRUPO ({self.sub_album_count})")

        if self.is_selected:
            painter.fillPath(path, QColor(0, 120, 212, 60))
            painter.setPen(QPen(QColor(0, 150, 255), 3.0))
            painter.drawPath(path)

            badge_sel = QRectF(w - 32, 10 if self.is_group else 8, 24, 24)
            painter.setBrush(QBrush(QColor(0, 120, 212)))
            painter.setPen(QPen(QColor(255, 255, 255), 1.5))
            painter.drawEllipse(badge_sel)
            painter.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
            painter.drawText(badge_sel, Qt.AlignmentFlag.AlignCenter, "✓")
        elif self.is_hovered:
            painter.fillPath(path, QColor(255, 255, 255, 25) if is_dark_album else QColor(0, 0, 0, 15))
            painter.setPen(QPen(QColor(0, 120, 212, 220), 2.5))
            painter.drawPath(path)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 20) if is_dark_album else QColor(0, 0, 0, 20), 1.0))
            painter.drawPath(path)

        folder_name = self.display_title or (os.path.basename(self.folder_path) or self.folder_path)
        painter.setPen(QColor(p_album['text_primary']))
        painter.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
        name_rect = QRectF(4, cover_h + 6, w - 8, 20)
        elided_name = painter.fontMetrics().elidedText(folder_name, Qt.TextElideMode.ElideRight, int(w - 8))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_name)

        painter.setPen(QColor(p_album['text_secondary']))
        painter.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Normal))
        count_rect = QRectF(4, cover_h + 26, w - 8, 18)
        if self.is_group:
            painter.drawText(count_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{self.sub_album_count} álbumes • {self.count} elem.")
        else:
            painter.drawText(count_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{self.count} elementos")

class PresentationCarouselTile(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, media_path: str, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.media_path = media_path
        self.is_active = is_active
        self.is_video = is_video_file(media_path)
        self.pixmap = None
        self._is_loading = False
        self.setFixedSize(92, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        cached_pix = _RAM_PIXMAP_CACHE.get(self.media_path)
        if cached_pix is not None:
            self.pixmap = cached_pix
        else:
            self._req_thumb()

    def cleanup_resources(self):
        self._is_loading = True
        self.pixmap = None

    def _req_thumb(self):
        if self._is_loading:
            return
        self._is_loading = True
        runnable = FastThumbnailRunnable(self.media_path, 320)
        runnable.signals.ready.connect(self._on_thumb)
        _THUMB_POOL.start(runnable, priority=50)

    def _on_thumb(self, path: str, img: QImage):
        self._is_loading = False
        try:
            if sip.isdeleted(self):
                return
        except Exception:
            return
        if path == self.media_path and not img.isNull():
            pix = QPixmap.fromImage(img)
            _RAM_PIXMAP_CACHE.set(self.media_path, pix)
            self.pixmap = pix
            self.update()

    def set_active(self, active: bool):
        if self.is_active != active:
            self.is_active = active
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.media_path)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, 8.0, 8.0)
        painter.setClipPath(path)

        if self.pixmap and not self.pixmap.isNull():
            sw = self.pixmap.width()
            sh = self.pixmap.height()
            tw = self.width()
            th = self.height()
            scale = max(tw / sw, th / sh)
            rw = sw * scale
            rh = sh * scale
            rx = (tw - rw) / 2.0
            ry = (th - rh) / 2.0
            painter.drawPixmap(int(rx), int(ry), int(rw), int(rh), self.pixmap)
        else:
            painter.fillRect(self.rect(), QColor(24, 30, 44))

        if self.is_video:
            badge_rect = QRectF(self.width() - 32, self.height() - 16, 28, 12)
            b_path = QPainterPath()
            b_path.addRoundedRect(badge_rect, 3, 3)
            painter.fillPath(b_path, QColor(0, 0, 0, 190))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI Variable Text", 6, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "VID")

        painter.setClipping(False)
        if self.is_active:
            painter.setPen(QPen(QColor(0, 120, 212), 3.0))
            painter.drawRoundedRect(QRectF(1.5, 1.5, self.width() - 3.0, self.height() - 3.0), 7.0, 7.0)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
            painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0), 8.0, 8.0)

class PresentationImageViewer(QWidget):
    double_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_path = ""
        self.pixmap = None
        self.is_video = False
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self._is_dragging = False
        self._drag_start = QPointF(0, 0)
        self.setMouseTracking(True)

    def set_media(self, path: str):
        self.media_path = path
        self.is_video = is_video_file(path)
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)

        if not path or not os.path.exists(path):
            self.pixmap = None
            self.update()
            return

        if self.is_video:
            c_path = get_thumbnail_cache_path(path, 1280)
            if not os.path.exists(c_path):
                c_path = get_thumbnail_cache_path(path, 320)
            if os.path.exists(c_path):
                self.pixmap = QPixmap(c_path)
            else:
                self.pixmap = None
        else:
            reader = QImageReader(path)
            reader.setAutoTransform(True)
            sz = reader.size()
            if sz.isValid() and (sz.width() > 2880 or sz.height() > 2880):
                target_scale = sz.scaled(2880, 2880, Qt.AspectRatioMode.KeepAspectRatio)
                reader.setScaledSize(target_scale)
            img = reader.read()
            if not img.isNull():
                self.pixmap = QPixmap.fromImage(img)
            else:
                self.pixmap = None

        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            old_zoom = self.zoom_factor
            if delta > 0:
                self.zoom_factor = min(5.0, self.zoom_factor * 1.15)
            else:
                self.zoom_factor = max(1.0, self.zoom_factor / 1.15)

            if self.zoom_factor == 1.0:
                self.pan_offset = QPointF(0, 0)
            self.update()
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.zoom_factor > 1.0:
                self._is_dragging = True
                self._drag_start = event.position()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            delta = event.position() - self._drag_start
            self._drag_start = event.position()
            self.pan_offset += delta
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.zoom_factor > 1.0:
                self.zoom_factor = 1.0
                self.pan_offset = QPointF(0, 0)
                self.update()
            else:
                self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if not self.pixmap or self.pixmap.isNull():
            return

        w = self.width()
        h = self.height()
        pw = self.pixmap.width()
        ph = self.pixmap.height()

        if pw <= 0 or ph <= 0:
            return

        scale = min(w / pw, h / ph) * self.zoom_factor
        draw_w = pw * scale
        draw_h = ph * scale
        dx = (w - draw_w) / 2.0 + self.pan_offset.x()
        dy = (h - draw_h) / 2.0 + self.pan_offset.y()

        painter.drawPixmap(int(dx), int(dy), int(draw_w), int(draw_h), self.pixmap)

        if self.is_video and self.zoom_factor <= 1.0:
            play_sz = 60
            px = int((w - play_sz) / 2.0)
            py = int((h - play_sz) / 2.0)
            p_rect = QRectF(px, py, play_sz, play_sz)
            painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
            painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
            painter.drawEllipse(p_rect)

            tri_path = QPainterPath()
            tri_path.moveTo(px + play_sz * 0.4, py + play_sz * 0.3)
            tri_path.lineTo(px + play_sz * 0.72, py + play_sz * 0.5)
            tri_path.lineTo(px + play_sz * 0.4, py + play_sz * 0.7)
            tri_path.closeSubpath()
            painter.fillPath(tri_path, QColor(255, 255, 255, 240))

class PresentationViewWidget(QWidget):
    media_changed = pyqtSignal(str)
    open_viewer_requested = pyqtSignal(str)

    def apply_theme(self, is_dark: bool):
        p = ThemePalette.get(is_dark)
        if hasattr(self, "lbl_date") and self.lbl_date:
            self.lbl_date.setStyleSheet(f"color: {p['text_primary']}; background: transparent;")
        if hasattr(self, "lbl_count") and self.lbl_count:
            self.lbl_count.setStyleSheet(f"color: {p['text_secondary']}; background: transparent;")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_list = []
        self.current_idx = 0
        self.blurred_bg_pixmap = None
        self._tile_widgets = {}

        self.init_ui()

    def init_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(24, 16, 24, 54)
        main_lay.setSpacing(10)

        # Top Bar: Fecha y contador
        self.top_info_row = QHBoxLayout()
        self.top_info_row.setContentsMargins(8, 0, 8, 0)

        self.lbl_date = QLabel("")
        self.lbl_date.setFont(QFont("Segoe UI Variable Display", 15, QFont.Weight.Bold))

        self.lbl_count = QLabel("")
        self.lbl_count.setFont(QFont("Segoe UI Variable Text", 11, QFont.Weight.DemiBold))

        ThemeManager.get_instance().register_child(self)
        self.apply_theme(ThemeManager.get_instance().is_dark)

        self.top_info_row.addWidget(self.lbl_date)
        self.top_info_row.addStretch()
        self.top_info_row.addWidget(self.lbl_count)
        main_lay.addLayout(self.top_info_row)

        # Centro: Visor de Gran Tamaño
        self.viewer = PresentationImageViewer()
        self.viewer.double_clicked.connect(self._on_viewer_double_clicked)
        main_lay.addWidget(self.viewer, stretch=1)

        # Tira Horizontal Navegable
        self.carousel_scroll = QScrollArea()
        self.carousel_scroll.setFixedHeight(78)
        self.carousel_scroll.setWidgetResizable(True)
        self.carousel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.carousel_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.carousel_scroll.setStyleSheet("background: transparent; border: none;")

        self.carousel_container = QWidget()
        self.carousel_container.setStyleSheet("background: transparent;")
        self.carousel_lay = QHBoxLayout(self.carousel_container)
        self.carousel_lay.setContentsMargins(6, 4, 6, 4)
        self.carousel_lay.setSpacing(8)
        self.carousel_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.carousel_scroll.setWidget(self.carousel_container)
        self.carousel_scroll.wheelEvent = self._carousel_wheel_event
        main_lay.addWidget(self.carousel_scroll)

    def _carousel_wheel_event(self, event):
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta != 0:
            hbar = self.carousel_scroll.horizontalScrollBar()
            hbar.setValue(hbar.value() - int(delta * 1.2))
            event.accept()

    def set_files(self, file_list: list, start_idx: int = 0):
        self.file_list = list(file_list)
        self._tile_widgets.clear()
        clear_layout_safely(self.carousel_lay)

        # Limitar la tira de miniaturas activas a un lote ultrarrápido de 150 elementos
        carousel_batch = self.file_list[:150]

        for idx, fpath in enumerate(carousel_batch):
            tile = PresentationCarouselTile(fpath, is_active=(idx == start_idx))
            tile.clicked.connect(lambda p=fpath: self.select_media_by_path(p))
            self.carousel_lay.addWidget(tile)
            self._tile_widgets[fpath] = tile

        if self.file_list:
            safe_idx = max(0, min(start_idx, len(self.file_list) - 1))
            self.set_current_index(safe_idx)
        else:
            self.lbl_date.setText("")
            self.lbl_count.setText("")
            self.viewer.set_media("")
            self.blurred_bg_pixmap = None
            self.update()

    def select_media_by_path(self, fpath: str):
        if fpath in self.file_list:
            self.set_current_index(self.file_list.index(fpath))

    def set_current_index(self, index: int):
        if not (0 <= index < len(self.file_list)):
            return

        self.current_idx = index
        fpath = self.file_list[index]

        for p, tile in self._tile_widgets.items():
            tile.set_active(p == fpath)

        target_tile = self._tile_widgets.get(fpath)
        if target_tile:
            self.carousel_scroll.ensureWidgetVisible(target_tile, 120, 0)

        # Actualizar Fecha y Contador
        dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            dia_nom = dias_es[mtime.weekday()]
            mes_nom = meses_es[mtime.month - 1]
            self.lbl_date.setText(f"{dia_nom}, {mtime.day} de {mes_nom} de {mtime.year}")
        except Exception:
            self.lbl_date.setText(os.path.basename(fpath))

        self.lbl_count.setText(f"{index + 1} de {len(self.file_list)}")

        self.viewer.set_media(fpath)
        self._generate_blurred_background(fpath)
        self.media_changed.emit(fpath)
        self.update()

    def _generate_blurred_background(self, media_path: str):
        pix = None
        if media_path in _RAM_PIXMAP_CACHE:
            pix = _RAM_PIXMAP_CACHE[media_path]
        else:
            c_path = get_thumbnail_cache_path(media_path, 320)
            if os.path.exists(c_path):
                pix = QPixmap(c_path)

        if not pix or pix.isNull():
            if not is_video_file(media_path):
                reader = QImageReader(media_path)
                reader.setAutoTransform(True)
                reader.setScaledSize(QSize(64, 64))
                img = reader.read()
                if not img.isNull():
                    pix = QPixmap.fromImage(img)

        if pix and not pix.isNull():
            tiny = pix.scaled(48, 48, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.blurred_bg_pixmap = tiny
        else:
            self.blurred_bg_pixmap = None

    def _on_viewer_double_clicked(self):
        if 0 <= self.current_idx < len(self.file_list):
            self.open_viewer_requested.emit(self.file_list[self.current_idx])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self.blurred_bg_pixmap and not self.blurred_bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.blurred_bg_pixmap)
            painter.fillRect(self.rect(), QColor(11, 14, 20, 195))
        else:
            painter.fillRect(self.rect(), QColor(11, 14, 20))

def _optimize_file_worker(fpath: str) -> bool:
    try:
        c_path = get_thumbnail_cache_path(fpath, 320)
        if os.path.exists(c_path) and os.path.getsize(c_path) > 200:
            return True

        if is_video_file(fpath):
            ffmpeg_bin = locate_ffmpeg_executable()
            return extract_robust_video_thumbnail(ffmpeg_bin, fpath, c_path, 320)
        else:
            is_png = fpath.lower().endswith(('.png', '.webp', '.ico', '.svg'))
            save_fmt = "PNG" if is_png else "JPG"
            save_quality = 90 if is_png else 82

            reader = QImageReader(fpath)
            reader.setAllocationLimit(2048)
            reader.setAutoTransform(True)
            sz = reader.size()
            if sz.isValid() and sz.height() > 0:
                _ASPECT_RATIO_CACHE[fpath] = max(0.45, min(2.6, sz.width() / float(sz.height())))

            if sz.isValid() and (sz.width() > 640 or sz.height() > 640):
                target_decode_size = sz.scaled(640, 640, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
                reader.setScaledSize(target_decode_size)

            img = reader.read()
            if not img.isNull():
                scaled = img.scaled(
                    320, 320,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                scaled.save(c_path, save_fmt, save_quality)
                return True
            else:
                try:
                    from PIL import Image
                    with Image.open(fpath) as pil_img:
                        pil_img.thumbnail((640, 640), Image.Resampling.LANCZOS)
                        pil_img.save(c_path, save_fmt, optimize=True)
                        return True
                except Exception:
                    pass
    except Exception:
        pass
    return False

class BatchOptimizerThread(QThread):
    progress_updated = pyqtSignal(int, int, int, int)
    optimization_completed = pyqtSignal()

    def __init__(self, file_list: list, parent=None):
        super().__init__(parent)
        self.file_list = list(file_list)
        self._is_running = True

    def run(self):
        total = len(self.file_list)
        if total == 0:
            self.optimization_completed.emit()
            return

        completed_count = 0
        lock = threading.Lock()
        max_workers = min(4, max(2, (os.cpu_count() or 4) // 2))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_optimize_file_worker, fp) for fp in self.file_list]
            for future in as_completed(futures):
                if not self._is_running:
                    break
                with lock:
                    completed_count += 1
                    current = completed_count
                    remaining = total - current
                    percent = int((current / float(total)) * 100)
                self.progress_updated.emit(current, total, remaining, percent)

        self.optimization_completed.emit()

    def stop(self):
        self._is_running = False

IGNORED_SYSTEM_DIRS = {
    "windows", "program files", "program files (x86)", "programdata",
    "$recycle.bin", "system volume information", "appdata", "node_modules",
    ".git", ".svn", ".vscode", "site-packages", "__pycache__", "temp", "cache",
    "steam", "steamapps", "steamlibrary", "epic games", "riot games", "roblox",
    "unity", "unreal", "blender", "android", ".android", ".gradle", ".cargo",
    ".nuget", "vendor", "dist", "build", "packages"
}

def get_available_drives():
    drives = []
    if sys.platform == "win32":
        import ctypes
        import string
        kernel32 = ctypes.windll.kernel32
        bitmask = kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                root_path = f"{letter}:\\"
                drive_type = kernel32.GetDriveTypeW(root_path)
                # DRIVE_REMOVABLE=2, DRIVE_FIXED=3, DRIVE_REMOTE=4, DRIVE_RAMDISK=6
                if drive_type in (2, 3, 4, 6):
                    drives.append(root_path)
                elif os.path.exists(root_path):
                    drives.append(root_path)
            bitmask >>= 1
    else:
        drives = ["/"]
    return drives

class DeepPcScannerThread(QThread):
    scan_progress = pyqtSignal(str)
    cache_progress = pyqtSignal(int, int, int, int)
    scan_finished = pyqtSignal(list, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True

    def run(self):
        drives = get_available_drives()
        raw_items = []
        folder_media_map = {}

        for drive in drives:
            if not self._is_running:
                break
            self.scan_progress.emit(f"Escaneando unidad completa {drive}...")
            self._fast_scan_dir(drive, raw_items, folder_media_map)

        raw_items.sort(key=lambda item: item[1], reverse=True)
        found_files = [item[0] for item in raw_items]

        albums = []
        cover_files = []

        for fldr, files in folder_media_map.items():
            if len(files) > 0:
                files.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
                cover_path = files[0]
                cover_files.append(cover_path)
                albums.append({
                    "folder_path": fldr,
                    "name": os.path.basename(fldr) or fldr,
                    "cover_path": cover_path,
                    "count": len(files),
                    "media_files": files
                })

        albums.sort(key=lambda x: (0 if any(k in x.get("name", "").lower() for k in ["perla", "jade"]) else 1, x["name"].lower()))
        db = {"albums": albums}
        save_gallery_db(db)

        priority_files = list(set(cover_files + found_files[:200]))
        uncached = [
            fp for fp in priority_files
            if not (os.path.exists(get_thumbnail_cache_path(fp, 320)) and os.path.getsize(get_thumbnail_cache_path(fp, 320)) > 200)
        ]

        total = len(uncached)
        if total > 0:
            completed_count = 0
            lock = threading.Lock()
            max_workers = min(4, max(2, (os.cpu_count() or 4) // 2))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_optimize_file_worker, fp) for fp in uncached]
                for future in as_completed(futures):
                    if not self._is_running:
                        break
                    with lock:
                        completed_count += 1
                        curr = completed_count
                        rem = total - curr
                        pct = int((curr / float(total)) * 100)
                    self.cache_progress.emit(curr, total, rem, pct)

        self.scan_finished.emit(found_files, db)

    def _fast_scan_dir(self, current_dir: str, raw_items: list, folder_media_map: dict):
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if not self._is_running:
                        return
                    try:
                        name_lower = entry.name.lower()
                        if entry.is_dir(follow_symlinks=False):
                            if name_lower in IGNORED_SYSTEM_DIRS or name_lower.startswith(("$", ".")):
                                continue
                            self._fast_scan_dir(entry.path, raw_items, folder_media_map)
                        elif entry.is_file(follow_symlinks=False):
                            if name_lower.endswith(ALL_MEDIA_EXTS):
                                stat_res = entry.stat(follow_symlinks=False)
                                if stat_res.st_size >= 512:
                                    raw_items.append((entry.path, stat_res.st_mtime))
                                    parent_dir = os.path.normpath(os.path.dirname(entry.path))
                                    folder_media_map.setdefault(parent_dir, []).append(entry.path)
                                    if len(raw_items) % 250 == 0:
                                        self.scan_progress.emit(f"Catalogando toda la PC: {len(raw_items):,} fotos y videos encontrados...")
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass

    def stop(self):
        self._is_running = False

class ClearCacheWorkerThread(QThread):
    clearing_finished = pyqtSignal()

    def run(self):
        _RAM_PIXMAP_CACHE.clear()
        _ASPECT_RATIO_CACHE.clear()
        _VIDEO_PREVIEW_FRAMES_CACHE.clear()
        _THUMB_POOL.clear()

        appdata = get_jade_appdata_dir()
        thumbs_cache = os.path.join(appdata, "cache", "galeria_thumbs")
        reels_cache = os.path.join(appdata, "cache", "galeria_reels")
        trash_dir = os.path.join(appdata, "cache", f"trash_{int(datetime.now().timestamp())}")

        try:
            os.makedirs(trash_dir, exist_ok=True)
            if os.path.exists(thumbs_cache):
                temp_thumbs = os.path.join(trash_dir, "galeria_thumbs")
                try:
                    os.rename(thumbs_cache, temp_thumbs)
                except Exception:
                    temp_thumbs = thumbs_cache
                shutil.rmtree(temp_thumbs, ignore_errors=True)

            if os.path.exists(reels_cache):
                temp_reels = os.path.join(trash_dir, "galeria_reels")
                try:
                    os.rename(reels_cache, temp_reels)
                except Exception:
                    temp_reels = reels_cache
                shutil.rmtree(temp_reels, ignore_errors=True)

            shutil.rmtree(trash_dir, ignore_errors=True)
            os.makedirs(thumbs_cache, exist_ok=True)
            os.makedirs(reels_cache, exist_ok=True)
        except Exception:
            pass

        save_gallery_db({"albums": []})
        save_excluded_data(set(), set())

        profile = load_gallery_profile()
        profile["allowed_folders"] = []
        save_gallery_profile(profile)

        self.clearing_finished.emit()

class OptimizationOverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card = QFrame()
        self.card.setFixedSize(540, 240)

        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(32, 28, 32, 28)
        card_lay.setSpacing(12)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_title = QLabel("Optimizando imágenes")
        self.lbl_title.setFont(QFont("Segoe UI Variable Display", 16, QFont.Weight.Bold))
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_subtitle = QLabel("Acelerando biblioteca y preparando caché de alto rendimiento...")
        self.lbl_subtitle.setFont(QFont("Segoe UI Variable Text", 10))
        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078D4, stop:1 #00BCF2);
                border-radius: 4px;
            }
        """)

        self.lbl_status = QLabel("Iniciando procesamiento multi-núcleo...")
        self.lbl_status.setFont(QFont("Segoe UI Variable Text", 10, QFont.Weight.DemiBold))
        self.lbl_status.setStyleSheet("color: #38BDF8; background: transparent; border: none;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_lay.addWidget(self.lbl_title)
        card_lay.addWidget(self.lbl_subtitle)
        card_lay.addSpacing(6)
        card_lay.addWidget(self.progress_bar)
        card_lay.addWidget(self.lbl_status)

        layout.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)
        ThemeManager.get_instance().register_child(self)
        self.apply_theme(ThemeManager.get_instance().is_dark)

    def apply_theme(self, is_dark: bool):
        p = ThemePalette.get(is_dark)
        if hasattr(self, 'card'):
            self.card.setStyleSheet(f"""
                QFrame {{
                    background-color: {p['bg_card']};
                    border: 1px solid {p['border']};
                    border-radius: 20px;
                }}
            """)
        self.lbl_title.setStyleSheet(f"color: {p['text_primary']}; background: transparent; border: none;")
        self.lbl_subtitle.setStyleSheet(f"color: {p['text_secondary']}; background: transparent; border: none;")

    def update_progress(self, current: int, total: int, remaining: int, percent: int):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(f"Procesando archivo {current} de {total}  •  Faltan {remaining} ({percent}%)")

from PyQt6.QtCore import QAbstractNativeEventFilter

class VlcSafeNativeEventFilter(QAbstractNativeEventFilter):
    def __init__(self, page):
        super().__init__()
        self.page = page

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32" and (event_type == "windows_generic_MSG" or event_type == "windows_dispatcher_MSG"):
            try:
                import ctypes
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                m = msg.message
                if m == 0x0100:  # WM_KEYDOWN
                    vk = msg.wParam
                    if vk == 0x1B:  # VK_ESCAPE (27)
                        QTimer.singleShot(0, self.page._handle_escape)
                        return True, 0
                    elif vk == 0x7A:  # VK_F11 (122)
                        QTimer.singleShot(0, self.page.toggle_fullscreen)
                        return True, 0
                    elif vk in (0x25, 0x41):  # VK_LEFT (37), 'A' (65)
                        QTimer.singleShot(0, self.page.navigate_prev)
                        return True, 0
                    elif vk in (0x27, 0x44):  # VK_RIGHT (39), 'D' (68)
                        QTimer.singleShot(0, self.page.navigate_next)
                        return True, 0
                    elif vk == 0x20:  # VK_SPACE (32)
                        QTimer.singleShot(0, self.page.toggle_play_pause)
                        return True, 0
                elif m == 0x0200:  # WM_MOUSEMOVE
                    QTimer.singleShot(0, self.page._handle_fullscreen_mouse_move)
                elif m == 0x0203:  # WM_LBUTTONDBLCLK
                    QTimer.singleShot(0, self.page.toggle_fullscreen)
                    return True, 0
            except Exception:
                pass
        return False, 0

class EmbeddedHDGalleryViewerPage(QWidget):
    back_requested = pyqtSignal()

    def apply_theme(self, is_dark: bool):
        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"background-color: {p['bg_window']};")
        if hasattr(self, "btn_back") and self.btn_back:
            self.btn_back.setStyleSheet(f"""
                QPushButton {{
                    background-color: {p['bg_card']};
                    color: {p['text_primary']};
                    border: 1px solid {p['border']};
                    border-radius: 10px;
                    padding: 7px 16px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {p['accent']};
                    color: #FFFFFF;
                    border-color: transparent;
                }}
            """)
        if hasattr(self, "lbl_title_info") and self.lbl_title_info:
            self.lbl_title_info.setStyleSheet(f"color: {p['text_primary']}; background: transparent;")
        if hasattr(self, "viewer_widget") and self.viewer_widget and hasattr(self.viewer_widget, "apply_theme"):
            self.viewer_widget.apply_theme(is_dark)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_list = []
        self.current_idx = 0
        self.viewer_widget = None
        self._carousel_tiles = {}
        self.blurred_bg_pixmap = None
        self._is_in_fullscreen = False
        self._was_maximized = True
        self._native_filter = None
        self._last_cursor_pos = QPoint(-1, -1)

        self._mouse_idle_timer = QTimer(self)
        self._mouse_idle_timer.setSingleShot(True)
        self._mouse_idle_timer.setInterval(2500)
        self._mouse_idle_timer.timeout.connect(self._on_mouse_idle)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)

        self.main_lay = QVBoxLayout(self)
        self.main_lay.setContentsMargins(20, 10, 20, 14)
        self.main_lay.setSpacing(8)

        self.header_bar = QWidget()
        self.header_bar.setStyleSheet("background: transparent;")
        h_lay = QHBoxLayout(self.header_bar)
        h_lay.setContentsMargins(4, 0, 4, 0)
        h_lay.setSpacing(12)

        self.btn_back = QPushButton("← Volver a la Galería (Esc)")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self._on_back_clicked)

        self.lbl_title_info = QLabel("")
        self.lbl_title_info.setFont(QFont("Segoe UI Variable Display", 12, QFont.Weight.Bold))

        ThemeManager.get_instance().register_child(self)
        self.apply_theme(ThemeManager.get_instance().is_dark)

        h_lay.addWidget(self.btn_back)
        h_lay.addWidget(self.lbl_title_info)
        h_lay.addStretch()

        self.main_lay.addWidget(self.header_bar)

        self.viewer_container = QWidget()
        self.viewer_container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewer_container.setMouseTracking(True)
        self.viewer_container.setStyleSheet("background: transparent;")
        self.viewer_container_lay = QVBoxLayout(self.viewer_container)
        self.viewer_container_lay.setContentsMargins(0, 0, 0, 0)
        self.viewer_container_lay.setSpacing(0)
        self.main_lay.addWidget(self.viewer_container, stretch=1)

        self.carousel_scroll = QScrollArea()
        self.carousel_scroll.setFixedHeight(82)
        self.carousel_scroll.setWidgetResizable(True)
        self.carousel_scroll.setMouseTracking(True)
        self.carousel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.carousel_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.carousel_scroll.setStyleSheet("background: transparent; border: none;")

        self.carousel_container = QWidget()
        self.carousel_container.setMouseTracking(True)
        self.carousel_container.setStyleSheet("background: transparent;")
        self.carousel_lay = QHBoxLayout(self.carousel_container)
        self.carousel_lay.setContentsMargins(4, 2, 4, 2)
        self.carousel_lay.setSpacing(8)
        self.carousel_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.carousel_scroll.setWidget(self.carousel_container)
        self.carousel_scroll.wheelEvent = self._carousel_wheel_event
        self.main_lay.addWidget(self.carousel_scroll)

    def _carousel_wheel_event(self, event):
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta != 0:
            hbar = self.carousel_scroll.horizontalScrollBar()
            if hbar:
                hbar.setValue(hbar.value() - int(delta * 1.2))
            event.accept()

    def _render_carousel(self):
        clear_layout_safely(self.carousel_lay)
        self._carousel_tiles.clear()

        total_files = len(self.file_list)
        if total_files == 0:
            return

        window_radius = 25
        start_idx = max(0, self.current_idx - window_radius)
        end_idx = min(total_files, self.current_idx + window_radius + 1)

        display_batch = self.file_list[start_idx:end_idx]
        for fpath in display_batch:
            tile = PresentationCarouselTile(fpath, is_active=(fpath == self.file_list[self.current_idx]))
            tile.clicked.connect(lambda p=fpath: self.select_media_by_path(p))
            self.carousel_lay.addWidget(tile)
            self._carousel_tiles[fpath] = tile

    def select_media_by_path(self, fpath: str):
        if fpath in self.file_list:
            self.load_index(self.file_list.index(fpath))

    def _update_carousel_active(self):
        if not self.file_list or not (0 <= self.current_idx < len(self.file_list)):
            return
        active_path = self.file_list[self.current_idx]
        if active_path not in self._carousel_tiles:
            self._render_carousel()
        for p, tile in self._carousel_tiles.items():
            tile.set_active(p == active_path)
        target_tile = self._carousel_tiles.get(active_path)
        if target_tile:
            QTimer.singleShot(20, lambda t=target_tile: self._center_carousel_tile(t))

    def _center_carousel_tile(self, target_tile):
        if not target_tile or not self.carousel_scroll:
            return
        hbar = self.carousel_scroll.horizontalScrollBar()
        if not hbar:
            return
        tile_center_x = target_tile.x() + target_tile.width() // 2
        viewport_w = self.carousel_scroll.viewport().width()
        target_val = max(0, min(hbar.maximum(), tile_center_x - viewport_w // 2))
        hbar.setValue(target_val)

    def _show_video_controls(self, visible: bool):
        if not self.viewer_widget:
            return

        targets = []
        for attr in ["bottom_bar", "hud_frame", "controls_bar", "video_controls", "playback_bar", "hud", "bottom_hud", "control_bar"]:
            w = getattr(self.viewer_widget, attr, None)
            if isinstance(w, QWidget):
                targets.append(w)

        for s in self.viewer_widget.findChildren(QSlider):
            p = s.parentWidget()
            while p and p != self.viewer_widget and p != self.viewer_container:
                if isinstance(p, (QFrame, QWidget)) and p.layout() is not None:
                    if p not in targets:
                        targets.append(p)
                    break
                p = p.parentWidget()

        for w in targets:
            if visible:
                w.show()
                w.setMaximumHeight(16777215)
                target_h = w.sizeHint().height()
                w.setFixedHeight(max(50, target_h if target_h > 20 else 54))
                w.raise_()
            else:
                w.hide()

    def _hide_viewer_toolbar(self):
        if not self.viewer_widget:
            return
        is_video = getattr(self.viewer_widget, "is_video", False) or (is_video_file(self.file_list[self.current_idx]) if self.file_list else False)

        if is_video:
            self._show_video_controls(True)
            return

        for btn in self.viewer_widget.findChildren(QPushButton):
            txt = btn.text().strip()
            tt = (btn.toolTip() or "").lower()
            if txt == "OCR" or "ocr" in tt or txt in ("100%", "225%", "131%") or "rotar" in tt:
                p = btn.parentWidget()
                while p and p != self.viewer_widget and p != self.viewer_container:
                    if isinstance(p, (QFrame, QWidget)) and p.layout() is not None:
                        if not p.findChildren(QSlider):
                            p.hide()
                            p.setFixedHeight(0)
                            p.setMaximumHeight(0)
                        break
                    p = p.parentWidget()

        for lbl in self.viewer_widget.findChildren(QLabel):
            if ("px (" in lbl.text() or ("px" in lbl.text() and "/" in lbl.text())) and not is_video:
                p = lbl.parentWidget()
                while p and p != self.viewer_widget and p != self.viewer_container:
                    if isinstance(p, (QFrame, QWidget)) and p.layout() is not None:
                        if not p.findChildren(QSlider):
                            p.hide()
                            p.setFixedHeight(0)
                            p.setMaximumHeight(0)
                        break
                    p = p.parentWidget()

    def toggle_play_pause(self):
        if not self.viewer_widget:
            return
        if getattr(self.viewer_widget, "is_video", False) and getattr(self.viewer_widget, "vlc_player", None):
            try:
                self.viewer_widget.vlc_player.pause()
            except Exception:
                pass
        elif hasattr(self.viewer_widget, "toggle_play"):
            try:
                self.viewer_widget.toggle_play()
            except Exception:
                pass

    def toggle_fullscreen(self):
        main_win = self.window()
        is_fs = main_win.isFullScreen() if main_win else self._is_in_fullscreen
        self.set_fullscreen_mode(not is_fs)

    def set_fullscreen_mode(self, enabled: bool):
        self._is_in_fullscreen = enabled
        main_win = self.window()
        if not main_win:
            return

        if enabled:
            self._was_maximized = main_win.isMaximized()
            self.main_lay.setContentsMargins(0, 0, 0, 0)
            self.main_lay.setSpacing(0)
            if hasattr(self, 'header_bar') and self.header_bar:
                self.header_bar.hide()
            if hasattr(self, 'carousel_scroll') and self.carousel_scroll:
                self.carousel_scroll.hide()
            main_win.showFullScreen()
            self._handle_fullscreen_mouse_move(force=True)
        else:
            if self._mouse_idle_timer.isActive():
                self._mouse_idle_timer.stop()
            self.unsetCursor()
            self.main_lay.setContentsMargins(20, 10, 20, 14)
            self.main_lay.setSpacing(8)
            if hasattr(self, 'header_bar') and self.header_bar:
                self.header_bar.show()
            if hasattr(self, 'carousel_scroll') and self.carousel_scroll:
                self.carousel_scroll.show()
            if getattr(self, '_was_maximized', True):
                main_win.showMaximized()
            else:
                main_win.showNormal()
            self._show_video_controls(True)

    def _handle_fullscreen_mouse_move(self, force: bool = False):
        if not self._is_in_fullscreen:
            return

        cur_pos = QCursor.pos()
        if not force and self._last_cursor_pos == cur_pos:
            return
        self._last_cursor_pos = cur_pos

        self.unsetCursor()
        is_video = getattr(self.viewer_widget, "is_video", False) if self.viewer_widget else False
        if is_video:
            self._show_video_controls(True)
        self._mouse_idle_timer.start(2500)

    def _on_mouse_idle(self):
        if not self._is_in_fullscreen:
            return
        self.setCursor(Qt.CursorShape.BlankCursor)
        is_video = getattr(self.viewer_widget, "is_video", False) if self.viewer_widget else False
        if is_video:
            self._show_video_controls(False)

    def _handle_escape(self):
        main_win = self.window()
        is_fs = (main_win and main_win.isFullScreen()) or self._is_in_fullscreen
        if is_fs:
            self.set_fullscreen_mode(False)
            return
        if self.viewer_widget and hasattr(self.viewer_widget, 'isFullScreen') and self.viewer_widget.isFullScreen():
            self.viewer_widget.showNormal()
            return
        self._on_back_clicked()

    def navigate_prev(self):
        if not self.file_list:
            return
        new_idx = self.current_idx - 1
        if new_idx < 0:
            new_idx = len(self.file_list) - 1
        self.load_index(new_idx)

    def navigate_next(self):
        if not self.file_list:
            return
        new_idx = self.current_idx + 1
        if new_idx >= len(self.file_list):
            new_idx = 0
        self.load_index(new_idx)

    def load_index(self, index: int):
        if not self.file_list or not (0 <= index < len(self.file_list)):
            return
        self.current_idx = index
        if self.viewer_widget and hasattr(self.viewer_widget, "load_media_at_index"):
            self.viewer_widget.load_media_at_index(index)
        else:
            target_path = self.file_list[self.current_idx]
            self._generate_blurred_background(target_path)
            self._update_header_info()
            self._update_carousel_active()
        self._hide_viewer_toolbar()

    def eventFilter(self, watched, event):
        evt_type = event.type()
        if evt_type == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self._handle_escape()
                return True
            elif key == Qt.Key.Key_F11:
                self.toggle_fullscreen()
                return True
            elif key in (Qt.Key.Key_Left, Qt.Key.Key_A):
                self.navigate_prev()
                return True
            elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
                self.navigate_next()
                return True
            elif key == Qt.Key.Key_Space:
                self.toggle_play_pause()
                return True
        elif evt_type == QEvent.Type.MouseMove:
            if self._is_in_fullscreen:
                self._handle_fullscreen_mouse_move()
        elif evt_type == QEvent.Type.MouseButtonDblClick:
            if event.button() == Qt.MouseButton.LeftButton:
                self.toggle_fullscreen()
                return True
        return super().eventFilter(watched, event)

    def load_media_view(self, file_list: list, start_idx: int = 0):
        self.cleanup_current_viewer()
        self.file_list = list(file_list)
        self.current_idx = max(0, min(start_idx, len(self.file_list) - 1)) if self.file_list else 0

        self._render_carousel()

        if not self.file_list or not HDMediaViewerDialog:
            return

        target_path = self.file_list[self.current_idx]
        self._generate_blurred_background(target_path)

        self.viewer_widget = HDMediaViewerDialog(
            target_path,
            parent=self.viewer_container,
            file_list=self.file_list,
            current_index=self.current_idx
        )
        self.viewer_widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.viewer_widget.setWindowFlags(Qt.WindowType.Widget)
        self.viewer_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewer_widget.setMouseTracking(True)
        self.viewer_widget.setStyleSheet(self.viewer_widget.styleSheet() + "\nQDialog { background: transparent; border: none; }")

        self.viewer_widget.reject = self._handle_escape
        self.viewer_widget.toggle_fullscreen = self.toggle_fullscreen

        def _hook_fs_btn(btn):
            try: btn.clicked.disconnect()
            except Exception: pass
            btn.clicked.connect(self.toggle_fullscreen)

        for b in self.viewer_widget.findChildren(QPushButton):
            tt = (b.toolTip() or "").lower()
            obj_name = (b.objectName() or "").lower()
            if "pantalla" in tt or "fullscreen" in tt or "fs" in obj_name or "fullscreen" in obj_name:
                _hook_fs_btn(b)

        for attr in ["btn_fullscreen", "fullscreen_btn", "btn_fs", "btn_pantalla_completa", "btn_expand"]:
            b = getattr(self.viewer_widget, attr, None)
            if isinstance(b, QPushButton):
                _hook_fs_btn(b)

        orig_load_media = self.viewer_widget.load_media_at_index
        def _wrapped_load_media(index: int):
            orig_load_media(index)
            self.current_idx = getattr(self.viewer_widget, "current_index", index)
            if 0 <= self.current_idx < len(self.file_list):
                self._generate_blurred_background(self.file_list[self.current_idx])
            self._update_carousel_active()
            self._update_header_info()
            self._hide_viewer_toolbar()

        self.viewer_widget.load_media_at_index = _wrapped_load_media

        self.viewer_container_lay.addWidget(self.viewer_widget)
        self.viewer_widget.show()
        self.viewer_widget.setFocus()

        self._hide_viewer_toolbar()
        QTimer.singleShot(0, self._hide_viewer_toolbar)
        QTimer.singleShot(60, self._hide_viewer_toolbar)
        QTimer.singleShot(180, self._hide_viewer_toolbar)

        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        QApplication.instance().installEventFilter(self)

        if not self._native_filter:
            self._native_filter = VlcSafeNativeEventFilter(self)
            try:
                QApplication.instance().installNativeEventFilter(self._native_filter)
            except Exception:
                pass

        if self.viewer_widget.is_video:
            if hasattr(self.viewer_widget, 'video_widget') and sys.platform == "win32" and self.viewer_widget.vlc_player:
                self.viewer_widget.vlc_player.set_hwnd(int(self.viewer_widget.video_widget.winId()))
                try:
                    self.viewer_widget.vlc_player.video_set_key_input(False)
                    self.viewer_widget.vlc_player.video_set_mouse_input(False)
                except Exception:
                    pass
            QTimer.singleShot(60, self.viewer_widget._start_vlc_playback)
            QTimer.singleShot(120, lambda: self._show_video_controls(True))

        if hasattr(self, 'header_bar') and self.header_bar:
            self.header_bar.show()
        if hasattr(self, 'carousel_scroll') and self.carousel_scroll:
            self.carousel_scroll.show()

        self._update_carousel_active()
        self._update_header_info()
        self.update()

    def _generate_blurred_background(self, media_path: str):
        pix = None
        if media_path in _RAM_PIXMAP_CACHE:
            pix = _RAM_PIXMAP_CACHE[media_path]
        else:
            c_path = get_thumbnail_cache_path(media_path, 320)
            if os.path.exists(c_path) and os.path.getsize(c_path) > 200:
                pix = QPixmap(c_path)
            else:
                if is_video_file(media_path):
                    ffmpeg_bin = locate_ffmpeg_executable()
                    if extract_robust_video_thumbnail(ffmpeg_bin, media_path, c_path, 320):
                        pix = QPixmap(c_path)
                else:
                    reader = QImageReader(media_path)
                    reader.setAutoTransform(True)
                    reader.setScaledSize(QSize(64, 64))
                    img = reader.read()
                    if not img.isNull():
                        pix = QPixmap.fromImage(img)

        if pix and not pix.isNull():
            self.blurred_bg_pixmap = pix.scaled(48, 48, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            self.blurred_bg_pixmap = None

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.fillRect(self.rect(), QColor(11, 14, 20))

        if self.blurred_bg_pixmap and not self.blurred_bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.blurred_bg_pixmap)
            painter.fillRect(self.rect(), QColor(10, 13, 20, 200))

    def _update_header_info(self):
        if not self.file_list or not (0 <= self.current_idx < len(self.file_list)):
            self.lbl_title_info.setText("")
            return
        cur_p = self.file_list[self.current_idx]
        fname = os.path.basename(cur_p)
        self.lbl_title_info.setText(f"{fname}   •   ({self.current_idx + 1} de {len(self.file_list)})")

    def _on_back_clicked(self):
        self.cleanup_current_viewer()
        self.back_requested.emit()

    def cleanup_current_viewer(self):
        if self._native_filter:
            try:
                QApplication.instance().removeNativeEventFilter(self._native_filter)
            except Exception:
                pass
            self._native_filter = None

        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass

        if self._is_in_fullscreen or (self.window() and self.window().isFullScreen()):
            self.set_fullscreen_mode(False)

        if hasattr(self, '_mouse_idle_timer') and self._mouse_idle_timer.isActive():
            self._mouse_idle_timer.stop()

        self.unsetCursor()
        self._is_in_fullscreen = False
        self.main_lay.setContentsMargins(20, 10, 20, 14)
        self.main_lay.setSpacing(8)

        if hasattr(self, 'header_bar') and self.header_bar:
            self.header_bar.show()
        if hasattr(self, 'carousel_scroll') and self.carousel_scroll:
            self.carousel_scroll.show()

        if self.viewer_widget:
            try:
                if hasattr(self.viewer_widget, "_cleanup_vlc"):
                    self.viewer_widget._cleanup_vlc()
                self.viewer_widget.hide()
                self.viewer_widget.setParent(None)
                self.viewer_widget.deleteLater()
            except Exception:
                pass
            self.viewer_widget = None
        self.blurred_bg_pixmap = None

class JadePhotosGalleryWindow(QMainWindow):
    def __init__(self, config=None, initial_folder: str = None, initial_file: str = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.all_media_files = []
        self.current_filtered_files = []
        self.initial_file = os.path.abspath(initial_file) if initial_file and os.path.exists(initial_file) else None

        if self.initial_file:
            self.active_folder = os.path.dirname(self.initial_file)
        else:
            self.active_folder = initial_folder or self._get_default_folder()

        self._last_rendered_width = 1180
        self._cached_albums_data = []
        self._albums_rendered = False
        self._album_loader_thread = None
        self._rendered_album_tiles = []
        self._rendered_group_sub_tiles = []
        self._current_album_cols = 4
        self._current_group_cols = 4
        self._resize_debounce_timer = QTimer(self)
        self._resize_debounce_timer.setSingleShot(True)
        self._resize_debounce_timer.timeout.connect(self._recalc_grid_debounced)

        self.setWindowTitle("Fotos")
        self.resize(1180, 780)
        self.setMinimumSize(640, 440)

        icon_path = os.path.join(get_jade_appdata_dir(), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._initial_render_done = False
        self.is_dark = ThemeManager.get_instance().is_dark
        self.init_ui()
        ThemeManager.get_instance().register_child(self)
        ThemeManager.get_instance().theme_changed.connect(lambda mode, dark: self.apply_theme(dark))

        if self.initial_file:
            self.open_media_viewer(self.initial_file, explicit_file_list=[self.initial_file])
            QTimer.singleShot(60, lambda: self.filter_and_switch_to_folder(self.active_folder))


    def apply_theme(self, is_dark: bool):
        self.is_dark = is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass

        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"""
            QMainWindow, QWidget#CentralWidget {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }}
            QScrollArea {{
                border: none;
                background-color: {p['bg_window']};
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: transparent;
                width: 0px;
                height: 0px;
                margin: 0px;
            }}
        """)

        for cont_name in [
            "container_widget", "container_videos", "container_albumes",
            "container_album_detail", "container_album_group",
            "container_memorias", "container_explorar"
        ]:
            if hasattr(self, cont_name):
                w = getattr(self, cont_name)
                if w:
                    w.setStyleSheet(f"background-color: {p['bg_window']};")
                    if hasattr(w, "apply_theme"):
                        w.apply_theme(is_dark)

        if hasattr(self, "nav_bar") and hasattr(self.nav_bar, "apply_theme"):
            self.nav_bar.apply_theme(is_dark)
        if hasattr(self, "page_visor_hd") and hasattr(self.page_visor_hd, "apply_theme"):
            self.page_visor_hd.apply_theme(is_dark)
        if hasattr(self, "top_profile") and hasattr(self.top_profile, "apply_theme"):
            self.top_profile.apply_theme(is_dark)

        hud_bg = "rgba(15, 20, 32, 0.96)" if is_dark else "rgba(255, 255, 255, 0.96)"
        hud_border = "rgba(0, 150, 255, 0.4)" if is_dark else "rgba(0, 120, 212, 0.3)"
        if hasattr(self, "selection_action_bar") and self.selection_action_bar:
            self.selection_action_bar.setStyleSheet(f"""
                QFrame#SelectionHUD {{
                    background-color: {hud_bg};
                    border: 1px solid {hud_border};
                    border-radius: 22px;
                }}
                QLabel#SelectionCountLabel {{
                    color: {p['text_primary']};
                    font-weight: bold;
                    font-size: 12px;
                    background: transparent;
                    border: none;
                }}
                QFrame#HelperPill {{
                    background-color: rgba(0, 120, 212, 0.18);
                    border: 1px solid rgba(0, 150, 255, 0.3);
                    border-radius: 12px;
                }}
                QLabel#HelperText {{
                    color: {p['accent']};
                    font-size: 11px;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                }}
                QPushButton {{
                    background-color: {p['bg_card']};
                    color: {p['text_primary']};
                    border: 1px solid {p['border']};
                    border-radius: 12px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {p['bg_card_hover']};
                }}
                QPushButton#BtnExcluir {{
                    background-color: #E81123;
                    border: 1px solid rgba(255, 120, 120, 0.45);
                    color: #FFFFFF;
                }}
                QPushButton#BtnExcluir:hover {{
                    background-color: #F02030;
                }}
            """)

        btn_style = f"""
            QPushButton {{
                background-color: {p['bg_card']};
                color: {p['text_primary']};
                border: 1px solid {p['border_strong']};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {p['bg_card_hover']};
                border: 1px solid {p['accent']};
            }}
        """
        if hasattr(self, "btn_back_to_albums") and self.btn_back_to_albums:
            self.btn_back_to_albums.setStyleSheet(btn_style)
        if hasattr(self, "btn_back_from_group") and self.btn_back_from_group:
            self.btn_back_from_group.setStyleSheet(btn_style)
        if hasattr(self, "lbl_album_detail_title") and self.lbl_album_detail_title:
            self.lbl_album_detail_title.setStyleSheet(f"color: {p['text_secondary']}; font-size: 14px; font-weight: 600;")
        if hasattr(self, "lbl_album_group_title") and self.lbl_album_group_title:
            self.lbl_album_group_title.setStyleSheet(f"color: {p['text_primary']}; font-size: 16px; font-weight: bold;")

    def _get_default_folder(self) -> str:
        if self.config is not None and hasattr(self.config, "get"):
            try:
                cfg_folder = self.config.get("images_folder")
                if cfg_folder and os.path.exists(cfg_folder):
                    return cfg_folder
            except Exception:
                pass

        profile = load_gallery_profile()
        folders = profile.get("allowed_folders", [])
        if folders and os.path.exists(folders[0]):
            return folders[0]

        user_pics = os.path.join(os.path.expanduser("~"), "Pictures")
        if os.path.exists(user_pics):
            return user_pics
        return os.path.expanduser("~")

    def init_ui(self):
        p = ThemePalette.get(self.is_dark)
        self.setStyleSheet(f"""
            QMainWindow, QWidget#CentralWidget {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            }}
            QScrollArea {{
                border: none;
                background-color: {p['bg_window']};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 0px;
                height: 0px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: transparent;
                min-height: 0px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0px;
                width: 0px;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 0px;
            }}
        """)

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.top_bar = QWidget(central)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(24, 14, 24, 0)
        top_layout.addStretch()

        self.profile_widget = TopProfileWidget()
        self.profile_widget.profile_clicked.connect(self.show_profile_menu)
        top_layout.addWidget(self.profile_widget)

        main_layout.addWidget(self.top_bar)

        self.stack = QStackedWidget()

        # Página 0: Fotos (Sub-HUD Todas / Presentación)
        self.page_fotos = QWidget()
        p_fotos_layout = QVBoxLayout(self.page_fotos)
        p_fotos_layout.setContentsMargins(0, 0, 0, 0)
        p_fotos_layout.setSpacing(0)

        # Sub-HUD selector superior exclusivo de Fotos
        self.fotos_sub_hud = QWidget()
        self.fotos_sub_hud.setStyleSheet("background-color: transparent;")
        fsh_lay = QHBoxLayout(self.fotos_sub_hud)
        fsh_lay.setContentsMargins(32, 4, 32, 10)
        fsh_lay.setSpacing(8)
        fsh_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.btn_sub_todas = QPushButton("Todas")
        self.btn_sub_todas.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sub_todas.clicked.connect(lambda: self.set_fotos_sub_mode("todas"))

        self.btn_sub_presentacion = QPushButton("Presentación")
        self.btn_sub_presentacion.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sub_presentacion.clicked.connect(lambda: self.set_fotos_sub_mode("presentacion"))

        fsh_lay.addWidget(self.btn_sub_todas)
        fsh_lay.addWidget(self.btn_sub_presentacion)
        p_fotos_layout.addWidget(self.fotos_sub_hud)

        self.fotos_views_stack = QStackedWidget()

        # Vista 0: Todas (Mural Dinámico Virtualizado)
        self.view_todas_container = QWidget()
        vt_layout = QVBoxLayout(self.view_todas_container)
        vt_layout.setContentsMargins(0, 0, 0, 0)
        vt_layout.setSpacing(0)

        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container_widget = VirtualMuralContainer(self.scroll_area, empty_text="No hay fotos ni videos.")
        self.container_widget.clicked.connect(self.open_media_viewer)
        self.container_widget.action_requested.connect(self.handle_tile_action)
        self.mural_layout = None

        self.scroll_area.setWidget(self.container_widget)
        vt_layout.addWidget(self.scroll_area)

        # Vista 1: Presentación (Fondo Blur + Canvas Zoom + Tira Navegable)
        self.presentation_view = PresentationViewWidget()
        self.presentation_view.open_viewer_requested.connect(self.open_media_viewer)

        self.fotos_views_stack.addWidget(self.view_todas_container)
        self.fotos_views_stack.addWidget(self.presentation_view)
        p_fotos_layout.addWidget(self.fotos_views_stack, stretch=1)

        self.set_fotos_sub_mode("todas")

        # Página 1: Solo Videos (Mural Virtualizado)
        self.page_videos = QWidget()
        p_videos_layout = QVBoxLayout(self.page_videos)
        p_videos_layout.setContentsMargins(0, 0, 0, 0)
        p_videos_layout.setSpacing(0)

        self.scroll_videos = SmoothScrollArea()
        self.scroll_videos.setWidgetResizable(True)
        self.scroll_videos.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_videos.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container_videos = VirtualMuralContainer(self.scroll_videos, empty_text="No hay videos guardados en las carpetas permitidas.")
        self.container_videos.clicked.connect(self.open_media_viewer)
        self.container_videos.action_requested.connect(self.handle_tile_action)
        self.videos_layout = None

        self.scroll_videos.setWidget(self.container_videos)
        p_videos_layout.addWidget(self.scroll_videos)

        # Página 2: Álbumes (Mosaico de Álbumes con portadas + Vista Detalle con botón Volver)
        self.page_albumes = QWidget()
        p_albumes_layout = QVBoxLayout(self.page_albumes)
        p_albumes_layout.setContentsMargins(0, 0, 0, 0)
        p_albumes_layout.setSpacing(0)

        self.albumes_stack = QStackedWidget()

        self.view_albumes_grid = QWidget()
        v_ag_layout = QVBoxLayout(self.view_albumes_grid)
        v_ag_layout.setContentsMargins(18, 0, 18, 64)
        v_ag_layout.setSpacing(0)

        self.scroll_albumes = SmoothScrollArea()
        self.scroll_albumes.setWidgetResizable(True)
        self.scroll_albumes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_albumes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_albumes.near_bottom.connect(self.load_next_albumes_batch)

        self.container_albumes = QWidget()
        self.container_albumes.setStyleSheet(f"background-color: {p['bg_window']};")
        self.container_albumes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.albumes_layout = QVBoxLayout(self.container_albumes)
        self.albumes_layout.setContentsMargins(0, 10, 0, 20)
        self.albumes_layout.setSpacing(16)
        self.albumes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_albumes.setWidget(self.container_albumes)
        v_ag_layout.addWidget(self.scroll_albumes)

        self.view_album_detail = QWidget()
        v_ad_layout = QVBoxLayout(self.view_album_detail)
        v_ad_layout.setContentsMargins(16, 8, 16, 0)
        v_ad_layout.setSpacing(10)

        self.album_detail_header = QWidget()
        adh_layout = QHBoxLayout(self.album_detail_header)
        adh_layout.setContentsMargins(0, 0, 0, 0)
        adh_layout.setSpacing(12)

        self.btn_back_to_albums = QPushButton("← Volver a Álbumes")
        self.btn_back_to_albums.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back_to_albums.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 10px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0078D4;
                border-color: transparent;
            }
        """)
        self.btn_back_to_albums.clicked.connect(self.back_to_albums_overview)

        self.lbl_album_detail_title = QLabel("")
        self.lbl_album_detail_title.setFont(QFont("Segoe UI Variable Display", 13, QFont.Weight.Bold))
        self.lbl_album_detail_title.setStyleSheet("color: #94A3B8;")

        adh_layout.addWidget(self.btn_back_to_albums)
        adh_layout.addWidget(self.lbl_album_detail_title)
        adh_layout.addStretch()

        v_ad_layout.addWidget(self.album_detail_header)

        self.scroll_album_detail = SmoothScrollArea()
        self.scroll_album_detail.setWidgetResizable(True)
        self.scroll_album_detail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_album_detail.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container_album_detail = VirtualMuralContainer(self.scroll_album_detail, empty_text="Este álbum no contiene fotos ni videos.")
        self.container_album_detail.clicked.connect(self.open_media_viewer)
        self.container_album_detail.action_requested.connect(self.handle_tile_action)
        self.album_detail_layout = None

        self.scroll_album_detail.setWidget(self.container_album_detail)
        v_ad_layout.addWidget(self.scroll_album_detail)

        self.view_album_group = QWidget()
        v_gp_layout = QVBoxLayout(self.view_album_group)
        v_gp_layout.setContentsMargins(28, 10, 28, 64)
        v_gp_layout.setSpacing(10)

        self.album_group_header = QWidget()
        agh_layout = QHBoxLayout(self.album_group_header)
        agh_layout.setContentsMargins(0, 0, 0, 0)
        agh_layout.setSpacing(12)

        self.btn_back_from_group = QPushButton("← Volver a Álbumes")
        self.btn_back_from_group.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back_from_group.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 10px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0078D4; border-color: transparent; }
        """)
        self.btn_back_from_group.clicked.connect(self.back_to_albums_overview)

        self.lbl_album_group_title = QLabel("")
        self.lbl_album_group_title.setFont(QFont("Segoe UI Variable Display", 13, QFont.Weight.Bold))
        self.lbl_album_group_title.setStyleSheet("color: #E2E8F0;")

        self.btn_exclude_current_group = QPushButton("Excluir Todo este Grupo")
        self.btn_exclude_current_group.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exclude_current_group.setStyleSheet("""
            QPushButton {
                background-color: rgba(232, 17, 35, 0.25);
                color: #FFA4A4;
                border: 1px solid rgba(232, 17, 35, 0.45);
                border-radius: 10px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #E81123; color: #FFFFFF; }
        """)
        self.btn_exclude_current_group.clicked.connect(self.exclude_currently_viewed_group)

        agh_layout.addWidget(self.btn_back_from_group)
        agh_layout.addWidget(self.lbl_album_group_title)
        agh_layout.addStretch()
        agh_layout.addWidget(self.btn_exclude_current_group)

        v_gp_layout.addWidget(self.album_group_header)

        self.scroll_album_group = SmoothScrollArea()
        self.scroll_album_group.setWidgetResizable(True)
        self.scroll_album_group.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_album_group.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container_album_group = QWidget()
        self.container_album_group.setStyleSheet(f"background-color: {p['bg_window']};")
        self.container_album_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.album_group_layout = QVBoxLayout(self.container_album_group)
        self.album_group_layout.setContentsMargins(0, 10, 0, 20)
        self.album_group_layout.setSpacing(16)
        self.album_group_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_album_group.setWidget(self.container_album_group)
        v_gp_layout.addWidget(self.scroll_album_group)

        self.albumes_stack.addWidget(self.view_albumes_grid)    # Index 0
        self.albumes_stack.addWidget(self.view_album_detail)   # Index 1
        self.albumes_stack.addWidget(self.view_album_group)    # Index 2
        p_albumes_layout.addWidget(self.albumes_stack)

        # Página 3: Memorias (Recuerdos destacados)
        self.page_memorias = QWidget()
        p_memorias_layout = QVBoxLayout(self.page_memorias)
        p_memorias_layout.setContentsMargins(36, 16, 36, 64)
        p_memorias_layout.setSpacing(16)

        self.scroll_memorias = SmoothScrollArea()
        self.scroll_memorias.setWidgetResizable(True)
        self.scroll_memorias.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_memorias.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container_memorias = QWidget()
        self.container_memorias.setStyleSheet(f"background-color: {p['bg_window']};")
        self.memorias_layout = QVBoxLayout(self.container_memorias)
        self.memorias_layout.setContentsMargins(0, 0, 0, 0)
        self.memorias_layout.setSpacing(20)
        self.memorias_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_memorias.setWidget(self.container_memorias)
        p_memorias_layout.addWidget(self.scroll_memorias)

        # Página 4: Explorar (Gestión de carpetas y categorías)
        self.page_explorar = QWidget()
        p_explorar_layout = QVBoxLayout(self.page_explorar)
        p_explorar_layout.setContentsMargins(36, 16, 36, 64)
        p_explorar_layout.setSpacing(16)

        self.scroll_explorar = SmoothScrollArea()
        self.scroll_explorar.setWidgetResizable(True)
        self.scroll_explorar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_explorar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container_explorar = QWidget()
        self.container_explorar.setStyleSheet(f"background-color: {p['bg_window']};")
        self.explorar_layout = QVBoxLayout(self.container_explorar)
        self.explorar_layout.setContentsMargins(0, 0, 0, 0)
        self.explorar_layout.setSpacing(20)
        self.explorar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_explorar.setWidget(self.container_explorar)
        p_explorar_layout.addWidget(self.scroll_explorar)

        self.page_visor_hd = EmbeddedHDGalleryViewerPage(self)
        self.page_visor_hd.back_requested.connect(self.exit_embedded_viewer)

        self.stack.addWidget(self.page_fotos)     # Index 0
        self.stack.addWidget(self.page_videos)    # Index 1
        self.stack.addWidget(self.page_albumes)   # Index 2
        self.stack.addWidget(self.page_memorias)  # Index 3
        self.stack.addWidget(self.page_explorar)  # Index 4
        self.stack.addWidget(self.page_visor_hd)  # Index 5

        self._previous_stack_tab = 0

        main_layout.addWidget(self.stack, stretch=1)

        self.nav_bar = FloatingBottomNavBar(self)
        self.nav_bar.tab_changed.connect(self.on_nav_tab_changed)

        # Barra Flotante de Acción para Modo Selección con Globito de Ayuda Integrado
        self.selection_action_bar = QFrame(self)
        self.selection_action_bar.setObjectName("SelectionHUD")
        self.selection_action_bar.setStyleSheet("""
            QFrame#SelectionHUD {
                background-color: rgba(15, 20, 32, 0.96);
                border: 1px solid rgba(0, 150, 255, 0.4);
                border-top: 1px solid rgba(0, 190, 255, 0.7);
                border-radius: 22px;
            }
            QLabel#SelectionCountLabel {
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                background: transparent;
                border: none;
            }
            QFrame#HelperPill {
                background-color: rgba(0, 120, 212, 0.18);
                border: 1px solid rgba(0, 150, 255, 0.3);
                border-radius: 12px;
            }
            QLabel#HelperText {
                color: #7DD3FC;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 12px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QPushButton#BtnExcluir {
                background-color: #E81123;
                border: 1px solid rgba(255, 120, 120, 0.45);
                color: #FFFFFF;
            }
            QPushButton#BtnExcluir:hover {
                background-color: #F02030;
            }
        """)
        sab_lay = QHBoxLayout(self.selection_action_bar)
        sab_lay.setContentsMargins(14, 6, 14, 6)
        sab_lay.setSpacing(10)

        self.lbl_selection_count = QLabel("0 seleccionados")
        self.lbl_selection_count.setObjectName("SelectionCountLabel")

        # Globito / Pill de Ayuda Flotante
        self.helper_pill = QFrame()
        self.helper_pill.setObjectName("HelperPill")
        hp_lay = QHBoxLayout(self.helper_pill)
        hp_lay.setContentsMargins(10, 3, 10, 3)
        hp_lay.setSpacing(6)

        self.lbl_helper_text = QLabel("💡 Pasa el ratón para seleccionar  •  Mantén Ctrl para deseleccionar")
        self.lbl_helper_text.setObjectName("HelperText")
        hp_lay.addWidget(self.lbl_helper_text)

        self.btn_exclude_selected = QPushButton("Excluir")
        self.btn_exclude_selected.setObjectName("BtnExcluir")
        self.btn_exclude_selected.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exclude_selected.clicked.connect(self.exclude_selected_folders)

        self.btn_cancel_selection = QPushButton("Cancelar (Esc)")
        self.btn_cancel_selection.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel_selection.clicked.connect(self.cancel_selection_mode)

        sab_lay.addWidget(self.lbl_selection_count)
        sab_lay.addWidget(self.helper_pill)
        sab_lay.addStretch()
        sab_lay.addWidget(self.btn_exclude_selected)
        sab_lay.addWidget(self.btn_cancel_selection)
        self.selection_action_bar.hide()

        # Atajos Universales: Shift+Tab y Escape
        self.shortcut_shift_tab = QShortcut(QKeySequence("Shift+Tab"), self)
        self.shortcut_shift_tab.activated.connect(self.toggle_selection_mode)

        self.shortcut_shift_backtab = QShortcut(QKeySequence("Shift+Backtab"), self)
        self.shortcut_shift_backtab.activated.connect(self.toggle_selection_mode)

        self.shortcut_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_esc.activated.connect(self.cancel_selection_mode)

        self.is_multi_select_mode = False
        self.selected_album_paths = set()
        self._last_hover_x = 0
        self.apply_theme(ThemeManager.get_instance().is_dark)

    def on_nav_tab_changed(self, tab: str):
        target_idx = 0
        if tab == "fotos":
            target_idx = 0
        elif tab == "videos":
            target_idx = 1
        elif tab == "albumes":
            target_idx = 2
        elif tab == "memorias":
            target_idx = 3
        elif tab == "explorar":
            target_idx = 4

        if self.stack.currentIndex() != target_idx:
            cur_w = self.stack.currentWidget()
            if cur_w:
                try:
                    cur_w.setGraphicsEffect(None)
                except Exception:
                    pass
            self.stack.setCurrentIndex(target_idx)
            apply_fade_transition(self.stack.currentWidget(), duration_ms=180)

        QApplication.processEvents()

        if target_idx == 0:
            target_files = self.current_filtered_files if self.current_filtered_files else self.all_media_files
            if target_files:
                if getattr(self.container_widget, '_files', None) != target_files or not getattr(self.container_widget, '_active_rows', None):
                    self.render_mural(target_files)
                else:
                    self.container_widget.show()
                    self.container_widget.update_visible_rows()
            elif hasattr(self, "load_all_allowed_folders"):
                self.load_all_allowed_folders()
        elif target_idx == 1:
            self.render_videos_view()
        elif target_idx == 2:
            self.render_albumes_view(force_reload=False)
        elif target_idx == 3:
            self.render_memorias_view()
        elif target_idx == 4:
            self.render_explorar_view()

    def set_fotos_sub_mode(self, mode: str):
        active_css = "background-color: #0078D4; color: #FFFFFF; font-weight: bold; border-radius: 14px; padding: 6px 18px; border: none; font-size: 12px;"
        inactive_css = "background-color: rgba(255, 255, 255, 0.08); color: #94A3B8; font-weight: 600; border-radius: 14px; padding: 6px 18px; border: 1px solid rgba(255, 255, 255, 0.08); font-size: 12px;"

        if mode == "todas":
            self.btn_sub_todas.setStyleSheet(active_css)
            self.btn_sub_presentacion.setStyleSheet(inactive_css)
            if self.fotos_views_stack.currentIndex() != 0:
                self.fotos_views_stack.setCurrentIndex(0)
                apply_fade_transition(self.view_todas_container, duration_ms=180)
            if hasattr(self, "container_widget") and self.container_widget:
                self.container_widget.show()
                self.container_widget.update_visible_rows()
        elif mode == "presentacion":
            self.btn_sub_todas.setStyleSheet(inactive_css)
            self.btn_sub_presentacion.setStyleSheet(active_css)
            target_files = self.current_filtered_files if self.current_filtered_files else self.all_media_files
            self.presentation_view.set_files(target_files)
            if self.fotos_views_stack.currentIndex() != 1:
                self.fotos_views_stack.setCurrentIndex(1)
                apply_fade_transition(self.presentation_view, duration_ms=180)

    def render_videos_view(self):
        """Inicializa la vista de videos mediante el contenedor virtualizado."""
        videos_only = [f for f in self.all_media_files if is_video_file(f)]
        self._videos_queue = list(videos_only)
        self.container_videos.set_files(videos_only)

    def load_next_videos_batch(self, initial: bool = False):
        pass

    def _check_videos_fill(self):
        pass

    def render_albumes_view(self, force_reload: bool = False):
        """Renderiza los álbumes individuales y grupos reutilizando el sistema fluido de filas de la galería."""
        if getattr(self, "_albums_rendered", False) and not force_reload:
            self.albumes_stack.setCurrentIndex(0)
            return

        self.albumes_stack.setCurrentIndex(0)
        clear_layout_safely(self.albumes_layout)

        db = load_gallery_db()
        raw_albums = db.get("albums", [])

        if not raw_albums and self.all_media_files:
            folder_map = OrderedDict()
            for fp in self.all_media_files:
                fldr = os.path.normpath(os.path.dirname(fp))
                if fldr not in folder_map:
                    folder_map[fldr] = []
                folder_map[fldr].append(fp)

            built_albums = []
            for fldr, files in folder_map.items():
                built_albums.append({
                    "folder_path": fldr,
                    "name": os.path.basename(fldr) or fldr,
                    "cover_path": files[0] if files else "",
                    "count": len(files),
                    "media_files": files
                })
            built_albums.sort(key=lambda x: (0 if any(k in x.get("name", "").lower() for k in ["perla", "jade"]) else 1, x.get("name", "").lower()))
            raw_albums = built_albums
            save_gallery_db({"albums": raw_albums})

        self._cached_albums_data = raw_albums
        self._albums_rendered = True

        lbl_title = QLabel("Tus Álbumes y Carpetas")
        lbl_title.setFont(QFont("Segoe UI Variable Display", 13, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #94A3B8; padding-top: 4px; padding-bottom: 8px; letter-spacing: 0.5px;")
        self.albumes_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignLeft)

        if not raw_albums:
            lbl_empty = QLabel("No hay álbumes registrados. Haz clic en 'Explorar' para examinar tus carpetas.")
            lbl_empty.setFont(QFont("Segoe UI Variable Display", 12))
            lbl_empty.setStyleSheet("color: #60687A; padding: 60px;")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.albumes_layout.addWidget(lbl_empty)
            return

        grouped_map = OrderedDict()
        for alb in raw_albums:
            name = alb.get("name") or os.path.basename(alb.get("folder_path", ""))
            group_key = get_album_group_key(name)
            if group_key not in grouped_map:
                grouped_map[group_key] = []
            grouped_map[group_key].append(alb)

        display_entries = []
        for g_key, alb_list in grouped_map.items():
            if len(alb_list) == 1:
                item = dict(alb_list[0])
                item["is_group"] = False
                item["sub_album_count"] = 1
                item["display_title"] = item.get("name") or os.path.basename(item.get("folder_path", ""))
                display_entries.append(item)
            else:
                total_cnt = sum(a.get("count", 0) for a in alb_list)
                cover = next((a.get("cover_path") for a in alb_list if a.get("cover_path")), "")
                candidate_names = [a.get("name", "") for a in alb_list if a.get("name")]
                g_title = min(candidate_names, key=len) if candidate_names else g_key
                display_entries.append({
                    "is_group": True,
                    "group_key": g_key,
                    "folder_path": f"group::{g_key}",
                    "display_title": g_title,
                    "name": g_title,
                    "cover_path": cover,
                    "count": total_cnt,
                    "sub_album_count": len(alb_list),
                    "group_data": alb_list
                })

        self._albumes_queue = display_entries
        self._rendered_albumes_count = 0
        self._is_albumes_loading = False

        self.load_next_albumes_batch(initial=True)

    def load_next_albumes_batch(self, initial: bool = False):
        if getattr(self, "_is_albumes_loading", False):
            return
        if not hasattr(self, "_albumes_queue") or not self._albumes_queue:
            return

        total = len(self._albumes_queue)
        if self._rendered_albumes_count >= total:
            return

        self._is_albumes_loading = True
        batch_size = 28
        start_idx = self._rendered_albumes_count
        end_idx = min(total, start_idx + batch_size)

        vp_w = self.scroll_albumes.viewport().width() if hasattr(self, "scroll_albumes") and self.scroll_albumes.viewport() else 0
        real_window_w = self.centralWidget().width() if self.centralWidget() else self.width()
        available_w = max(420, (vp_w - 10) if vp_w > 300 else (real_window_w - 76))
        spacing = 16
        min_card_w = 205
        cols = max(1, int((available_w + spacing) / (min_card_w + spacing)))
        card_w = int((available_w - (spacing * (cols - 1))) / float(cols))
        card_h = int(card_w + 52)

        batch = self._albumes_queue[start_idx:end_idx]

        for i in range(0, len(batch), cols):
            row_slice = batch[i:i + cols]
            row_widget = QWidget()
            row_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row_widget.setStyleSheet("background-color: transparent;")
            r_lay = QHBoxLayout(row_widget)
            r_lay.setContentsMargins(0, 0, 0, 0)
            r_lay.setSpacing(spacing)
            r_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

            for alb in row_slice:
                fpath = alb.get("folder_path", "")
                cover_path = alb.get("cover_path", "")
                count = alb.get("count", 0)
                is_group = alb.get("is_group", False)
                sub_count = alb.get("sub_album_count", 0)
                disp_title = alb.get("display_title", "")
                g_data = alb.get("group_data", [])

                album_tile = ModernAlbumTile(
                    fpath, cover_path, count,
                    is_group=is_group, sub_album_count=sub_count,
                    display_title=disp_title, group_data=g_data,
                    width=card_w, height=card_h
                )
                album_tile.selection_toggled.connect(self.handle_album_selection_toggled)
                album_tile.action_requested.connect(self.handle_album_tile_action)

                if is_group:
                    album_tile.clicked.connect(lambda _, a=alb: self.open_album_group(a))
                else:
                    album_tile.clicked.connect(lambda p=fpath: self.open_album_detail(p, from_group=False))

                if getattr(self, "is_multi_select_mode", False):
                    album_tile.set_selection_mode(True)
                    album_tile.set_selected(os.path.normpath(fpath) in self.selected_album_paths)

                r_lay.addWidget(album_tile)

            if len(row_slice) < cols:
                r_lay.addStretch()

            self.albumes_layout.addWidget(row_widget)

        self._rendered_albumes_count = end_idx
        self._is_albumes_loading = False

        prefetch_end = min(total, end_idx + 28)
        for ahead_alb in self._albumes_queue[end_idx:prefetch_end]:
            ahead_cover = ahead_alb.get("cover_path")
            if ahead_cover and ahead_cover not in _RAM_PIXMAP_CACHE:
                c_p = get_thumbnail_cache_path(ahead_cover, 320)
                if not (os.path.exists(c_p) and os.path.getsize(c_p) > 200):
                    r = FastThumbnailRunnable(ahead_cover, 320)
                    _THUMB_POOL.start(r, priority=10)

        QTimer.singleShot(30, self._check_albumes_fill)

    def _check_albumes_fill(self):
        if hasattr(self, "_albumes_queue") and self._rendered_albumes_count < len(self._albumes_queue):
            vbar = self.scroll_albumes.verticalScrollBar()
            if vbar and vbar.maximum() <= 120:
                self.load_next_albumes_batch()

    def open_album_group(self, group_entry: dict):
        """Abre la vista intermedia con todos los sub-álbumes pertenecientes a este grupo expandiéndose por completo."""
        clear_layout_safely(self.album_group_layout)
        sub_albums = group_entry.get("group_data", [])
        group_name = group_entry.get("display_title") or group_entry.get("name") or "Grupo"
        self._currently_viewed_group_data = sub_albums

        self.lbl_album_group_title.setText(f"{group_name}   •   ({len(sub_albums)} sub-álbumes)")

        vp_w = self.scroll_album_group.viewport().width() if hasattr(self, "scroll_album_group") and self.scroll_album_group.viewport() else 0
        real_window_w = self.centralWidget().width() if self.centralWidget() else self.width()
        available_w = max(420, (vp_w - 10) if vp_w > 300 else (real_window_w - 76))
        spacing = 16
        min_card_w = 205
        cols = max(1, int((available_w + spacing) / (min_card_w + spacing)))
        card_w = int((available_w - (spacing * (cols - 1))) / float(cols))
        card_h = int(card_w + 52)

        self.container_album_group.setUpdatesEnabled(False)
        for i in range(0, len(sub_albums), cols):
            row_slice = sub_albums[i:i + cols]
            row_widget = QWidget()
            row_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row_widget.setStyleSheet("background-color: transparent;")
            r_lay = QHBoxLayout(row_widget)
            r_lay.setContentsMargins(0, 0, 0, 0)
            r_lay.setSpacing(spacing)
            r_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

            for sub_alb in row_slice:
                fpath = sub_alb.get("folder_path", "")
                cover = sub_alb.get("cover_path", "")
                cnt = sub_alb.get("count", 0)
                sub_name = sub_alb.get("name") or os.path.basename(fpath)

                tile = ModernAlbumTile(
                    fpath, cover, cnt,
                    is_group=False, sub_album_count=1,
                    display_title=sub_name,
                    width=card_w, height=card_h
                )
                tile.clicked.connect(lambda p=fpath: self.open_album_detail(p, from_group=True))
                tile.action_requested.connect(self.handle_album_tile_action)
                r_lay.addWidget(tile)

            if len(row_slice) < cols:
                r_lay.addStretch()

            self.album_group_layout.addWidget(row_widget)

        self.container_album_group.setUpdatesEnabled(True)
        self.albumes_stack.setCurrentIndex(2)
        self.scroll_album_group.verticalScrollBar().setValue(0)
        apply_fade_transition(self.view_album_group, duration_ms=200)

    def exclude_currently_viewed_group(self):
        sub_albums = getattr(self, "_currently_viewed_group_data", [])
        if not sub_albums:
            return
        rep = QMessageBox.question(
            self,
            "Excluir Grupo de Álbumes",
            f"¿Deseas excluir todos los {len(sub_albums)} sub-álbumes de este grupo de Jade?\n\n"
            f"• Se registrarán en 'excluir.json'.\n"
            f"(Las carpetas y archivos originales en tu PC NO se borrarán)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if rep != QMessageBox.StandardButton.Yes:
            return

        excluded = load_excluded_folders()
        ref_title = self.lbl_album_group_title.text()
        clean_key = get_album_group_key(ref_title)
        if clean_key:
            excluded.add(f"group::{clean_key}")

        for a in sub_albums:
            fp = a.get("folder_path")
            if fp:
                excluded.add(os.path.normpath(fp))
        save_excluded_folders(excluded)

        db = load_gallery_db()
        db["albums"] = [a for a in db.get("albums", []) if not is_folder_excluded(a.get("folder_path", ""), excluded)]
        save_gallery_db(db)

        self.load_all_allowed_folders()
        self.render_albumes_view(force_reload=True)

    def open_album_detail(self, target_folder: str, from_group: bool = False):
        """Abre el detalle del álbum al instante desde la RAM con cero lecturas a disco."""
        self._current_album_from_group = from_group
        if from_group:
            self.btn_back_to_albums.setText("← Volver al Grupo")
        else:
            self.btn_back_to_albums.setText("← Volver a Álbumes")

        norm_target = os.path.normpath(target_folder)
        excluded_files_set = load_excluded_files()
        found = []

        if hasattr(self, "all_media_files") and self.all_media_files:
            for f in self.all_media_files:
                if os.path.normpath(os.path.dirname(f)) == norm_target:
                    if os.path.normpath(f) not in excluded_files_set:
                        found.append(f)

        if not found:
            db = load_gallery_db()
            album_entry = next((a for a in db.get("albums", []) if os.path.normpath(a.get("folder_path", "")) == norm_target), None)
            if album_entry and "media_files" in album_entry:
                found = [f for f in album_entry["media_files"] if os.path.normpath(f) not in excluded_files_set and os.path.exists(f)]

        folder_name = os.path.basename(target_folder) or target_folder
        self.lbl_album_detail_title.setText(f"{folder_name} ({len(found)} elementos)")

        clear_layout_safely(self.album_detail_layout)

        if not found:
            lbl_empty = QLabel("Este álbum no contiene fotos ni videos.")
            lbl_empty.setFont(QFont("Segoe UI Variable Display", 12))
            lbl_empty.setStyleSheet("color: #60687A; padding: 60px;")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.album_detail_layout.addWidget(lbl_empty)
            self.albumes_stack.setCurrentIndex(1)
            self.scroll_album_detail.verticalScrollBar().setValue(0)
            apply_fade_transition(self.view_album_detail, duration_ms=180)
            return

        self._render_album_detail_grid(found)
        self.albumes_stack.setCurrentIndex(1)
        self.scroll_album_detail.verticalScrollBar().setValue(0)
        apply_fade_transition(self.view_album_detail, duration_ms=180)

    def _render_album_detail_grid(self, file_list: list):
        self._album_detail_queue = list(file_list)
        self.container_album_detail.set_files(file_list)

    def load_next_album_detail_batch(self, initial: bool = False):
        pass

    def _check_album_detail_fill(self):
        pass

    def start_full_pc_scan(self):
        clear_layout_safely(self.explorar_layout)

        overlay = OptimizationOverlayWidget()
        overlay.lbl_title.setText("Examinando toda la PC")
        overlay.lbl_subtitle.setText("Escaneando unidades de almacenamiento y guardando galeria.json...")
        self.explorar_layout.addWidget(overlay)

        self._pc_scanner_thread = DeepPcScannerThread(self)
        self._pc_scanner_thread.scan_progress.connect(lambda msg: overlay.lbl_status.setText(msg))
        self._pc_scanner_thread.cache_progress.connect(overlay.update_progress)

        def _on_scan_completed(found_files, db):
            profile = load_gallery_profile()
            discovered_folders = [alb["folder_path"] for alb in db.get("albums", [])]
            profile["allowed_folders"] = discovered_folders
            save_gallery_profile(profile)

            self.all_media_files = found_files
            self.current_filtered_files = found_files
            self.render_mural(found_files)
            self.nav_bar.set_active_tab("fotos")
            apply_fade_transition(self.view_todas_container, duration_ms=220)

        self._pc_scanner_thread.scan_finished.connect(_on_scan_completed)
        self._pc_scanner_thread.start()

    def back_to_albums_overview(self):
        """Regresa al grupo o a la vista principal de álbumes de forma instantánea liberando la CPU."""
        self._album_detail_queue = []
        self._rendered_album_detail_count = 0
        clear_layout_safely(self.album_detail_layout)

        curr_idx = self.albumes_stack.currentIndex()
        if curr_idx == 1 and getattr(self, "_current_album_from_group", False):
            self.albumes_stack.setCurrentIndex(2)
            apply_fade_transition(self.view_album_group, duration_ms=190)
        else:
            self._current_album_from_group = False
            self.albumes_stack.setCurrentIndex(0)
            apply_fade_transition(self.view_albumes_grid, duration_ms=190)

    def handle_album_tile_action(self, action: str, data: object):
        if action == "exclude_album":
            folder_path = str(data)
            rep = QMessageBox.question(
                self, "Excluir Álbum",
                f"¿Deseas excluir este álbum de Jade?\n\n{os.path.basename(folder_path)}\n\n(No se borrará ningún archivo del disco)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if rep == QMessageBox.StandardButton.Yes:
                excluded = load_excluded_folders()
                excluded.add(os.path.normpath(folder_path))
                save_excluded_folders(excluded)

                db = load_gallery_db()
                db["albums"] = [a for a in db.get("albums", []) if os.path.normpath(a.get("folder_path", "")) not in excluded]
                save_gallery_db(db)

                self.load_all_allowed_folders()
                self.render_albumes_view(force_reload=True)

        elif action == "exclude_exact_name":
            folder_name = str(data).strip()
            self.exclude_folders_by_exact_name(folder_name)

        elif action == "exclude_similar":
            name = str(data)
            self.exclude_similar_albums(name)

        elif action == "exclude_group":
            tile = data
            if hasattr(tile, "group_data") and tile.group_data:
                self._currently_viewed_group_data = tile.group_data
                self.exclude_currently_viewed_group()

        elif action == "open_folder":
            try:
                norm_path = os.path.normpath(str(data))
                subprocess.Popen(f'explorer /select,"{norm_path}"', creationflags=0x08000000)
            except Exception:
                pass

    def _apply_exclusion_cleanup(self, excluded: set):
        matcher = get_exclusion_matcher(excluded)

        profile = load_gallery_profile()
        profile["allowed_folders"] = [f for f in profile.get("allowed_folders", []) if not matcher.is_excluded(f)]
        save_gallery_profile(profile)

        db = load_gallery_db()
        db["albums"] = [a for a in db.get("albums", []) if not matcher.is_excluded(a.get("folder_path", ""))]
        save_gallery_db(db)

        self.all_media_files = [f for f in self.all_media_files if not matcher.is_excluded(os.path.dirname(f))]
        self.current_filtered_files = [f for f in self.current_filtered_files if not matcher.is_excluded(os.path.dirname(f))]

        self._albums_rendered = False
        self._cached_albums_data = []

        curr_idx = self.stack.currentIndex()
        if curr_idx == 4:
            self.render_explorar_view()
        elif curr_idx == 2:
            self.render_albumes_view(force_reload=True)
        elif curr_idx == 0:
            self.render_mural(self.current_filtered_files)
        elif curr_idx == 1:
            self.render_videos_view()

    def show_path_exclusion_menu(self, folder_path: str, global_pos: QPoint):
        norm = os.path.normpath(folder_path)
        parts = norm.replace("/", "\\").split("\\")
        segments = []
        for p in reversed(parts):
            p_clean = p.strip()
            if not p_clean or ":" in p_clean or p_clean.lower() == "jade":
                continue
            if p_clean not in segments:
                segments.append(p_clean)

        menu = QMenu(self)
        menu.setStyleSheet(ThemePalette.get_menu_style(self.is_dark))

        title_act = menu.addAction("🚫 Excluir del árbol de rutas (Todos los discos):")
        title_act.setEnabled(False)

        actions_map = {}
        for seg in segments:
            act = menu.addAction(f"Excluir carpeta '{seg}'")
            actions_map[act] = ("segment", seg)

        menu.addSeparator()
        act_exact_path = menu.addAction("Excluir solo esta ruta específica")
        actions_map[act_exact_path] = ("path", norm)

        act_manual = menu.addAction("Escribir otro nombre de carpeta...")
        actions_map[act_manual] = ("manual", "")

        selected = menu.exec(global_pos)
        if selected in actions_map:
            kind, val = actions_map[selected]
            if kind == "segment":
                self.exclude_folders_by_exact_name(val)
            elif kind == "path":
                excluded = load_excluded_folders()
                excluded.add(norm)
                save_excluded_folders(excluded)
                self._apply_exclusion_cleanup(excluded)
            elif kind == "manual":
                self.prompt_exclude_folder_by_name()

    def exclude_folders_by_exact_name(self, folder_name: str):
        folder_name = folder_name.strip()
        if not folder_name or folder_name.lower() == "jade":
            return

        rep = QMessageBox.question(
            self,
            "Excluir por nombre en todos los discos",
            f"¿Deseas excluir todas las carpetas llamadas exactamente '{folder_name}' en TODOS tus discos duros?\n\n"
            f"• Cualquier carpeta que coincida con '{folder_name}' y sus subcarpetas ya no aparecerán en Jade.\n"
            f"(Tus archivos en el disco NO serán eliminados ni modificados)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if rep != QMessageBox.StandardButton.Yes:
            return

        excluded = load_excluded_folders()
        excluded.add(f"name::{folder_name.lower()}")
        save_excluded_folders(excluded)

        self._apply_exclusion_cleanup(excluded)

        QMessageBox.information(
            self,
            "Carpetas Excluidas",
            f"Se han excluido todas las carpetas llamadas '{folder_name}' en todos los discos duros correctamente."
        )

    def prompt_exclude_folder_by_name(self):
        name, ok = QInputDialog.getText(
            self,
            "Excluir carpetas en todos los discos",
            "Escribe el nombre exacto de la carpeta que deseas excluir en todos tus discos:\n(Ejemplo: dota2, node_modules, recursos, assets)"
        )
        if ok and name.strip():
            self.exclude_folders_by_exact_name(name.strip())

    def exclude_similar_albums(self, reference_name: str):
        target_key = get_album_group_key(reference_name)
        db = load_gallery_db()
        matching_albums = []

        for a in db.get("albums", []):
            a_name = a.get("name") or os.path.basename(a.get("folder_path", ""))
            if get_album_group_key(a_name) == target_key:
                matching_albums.append(a)

        if not matching_albums:
            QMessageBox.information(self, "Sin coincidencias", f"No se encontraron álbumes similares a '{reference_name}'.")
            return

        rep = QMessageBox.question(
            self,
            "Excluir Álbumes Similares",
            f"Se encontraron {len(matching_albums)} álbum(es) similares a '{reference_name}'.\n\n"
            f"¿Deseas excluirlos todos de Jade simultáneamente?\n"
            f"(Tus carpetas y archivos en el disco NO se borrarán)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if rep != QMessageBox.StandardButton.Yes:
            return

        excluded = load_excluded_folders()
        for a in matching_albums:
            fp = a.get("folder_path")
            if fp:
                excluded.add(os.path.normpath(fp))
        save_excluded_folders(excluded)

        db["albums"] = [a for a in db.get("albums", []) if os.path.normpath(a.get("folder_path", "")) not in excluded]
        save_gallery_db(db)

        self.load_all_allowed_folders()
        self.render_albumes_view(force_reload=True)

        QMessageBox.information(self, "Álbumes Excluidos", f"Se han excluido {len(matching_albums)} álbum(es) similares correctamente.")

    def exclude_single_file(self, filepath: str):
        norm = os.path.normpath(filepath)
        excluded_files = load_excluded_files()
        excluded_files.add(norm)
        save_excluded_files(excluded_files)

        self.all_media_files = [f for f in self.all_media_files if os.path.normpath(f) != norm]
        self.current_filtered_files = [f for f in self.current_filtered_files if os.path.normpath(f) != norm]

        idx = self.stack.currentIndex()
        if idx == 0:
            self.render_mural(self.current_filtered_files)
        elif idx == 1:
            self.render_videos_view()
        elif idx == 2 and hasattr(self, "albumes_stack") and self.albumes_stack.currentIndex() == 1:
            if hasattr(self, "_album_detail_queue"):
                self._album_detail_queue = [f for f in self._album_detail_queue if os.path.normpath(f) != norm]
                self._render_album_detail_grid(self._album_detail_queue)




    class MemoriasWorkerThread(QThread):
        analysis_completed = pyqtSignal(dict)

        def __init__(self, file_list: list, parent=None):
            super().__init__(parent)
            self.file_list = list(file_list)
            self._is_running = True

        def run(self):
            cascade_face = None
            cascade_cat = None
            try:
                import cv2
                hdir = getattr(getattr(cv2, "data", None), "haarcascades", "")
                if hdir and os.path.isdir(hdir):
                    face_xml = os.path.join(hdir, "haarcascade_frontalface_default.xml")
                    cat_xml = os.path.join(hdir, "haarcascade_frontalcatface.xml")
                    if os.path.exists(face_xml):
                        cascade_face = cv2.CascadeClassifier(face_xml)
                    if os.path.exists(cat_xml):
                        cascade_cat = cv2.CascadeClassifier(cat_xml)
            except Exception:
                pass

            today = datetime.now()
            un_dia_como_hoy = []
            personas_list = []
            animales_list = []
            gps_groups = OrderedDict()
            name_groups = OrderedDict()
            hashes = []

            sample_set = self.file_list[:min(160, len(self.file_list))]

            for fp in sample_set:
                if not self._is_running:
                    return

                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                    if mtime.month == today.month and abs(mtime.day - today.day) <= 3 and mtime.year < today.year:
                        un_dia_como_hoy.append(fp)
                except Exception:
                    pass

                coords = self._extract_gps(fp)
                if coords:
                    gps_groups.setdefault(coords, []).append(fp)

                folder_name = os.path.basename(os.path.dirname(fp)) or "Colección"
                clean_name = get_album_group_key(folder_name)
                if clean_name and len(clean_name) > 1:
                    name_groups.setdefault(folder_name, []).append(fp)

                if is_video_file(fp):
                    continue

                try:
                    import cv2
                    c_path = get_thumbnail_cache_path(fp, 320)
                    read_path = c_path if (os.path.exists(c_path) and os.path.getsize(c_path) > 200) else fp
                    img_cv = cv2.imread(read_path)

                    if img_cv is not None and img_cv.size > 0:
                        ih, iw = img_cv.shape[:2]
                        target_w = 260
                        if iw > target_w:
                            scale = target_w / float(iw)
                            small_cv = cv2.resize(img_cv, (target_w, max(20, int(ih * scale))), interpolation=cv2.INTER_AREA)
                        else:
                            small_cv = img_cv

                        gray = cv2.cvtColor(small_cv, cv2.COLOR_BGR2GRAY)

                        has_human = False
                        if cascade_face is not None and not cascade_face.empty():
                            faces = cascade_face.detectMultiScale(gray, scaleFactor=1.18, minNeighbors=4, minSize=(28, 28))
                            if len(faces) > 0:
                                personas_list.append(fp)
                                has_human = True

                        if not has_human and cascade_cat is not None and not cascade_cat.empty():
                            cats = cascade_cat.detectMultiScale(gray, scaleFactor=1.18, minNeighbors=4, minSize=(28, 28))
                            if len(cats) > 0:
                                animales_list.append(fp)

                        hash_small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
                        diff = hash_small[:, 1:] > hash_small[:, :-1]
                        h_val = 0
                        for bit in diff.flatten():
                            h_val = (h_val << 1) | (1 if bit else 0)
                        hashes.append((fp, h_val))
                except Exception:
                    pass

            similar_clusters = []
            assigned = set()
            for i in range(len(hashes)):
                fpath_a, hash_a = hashes[i]
                if fpath_a in assigned:
                    continue
                current_cluster = [fpath_a]
                for j in range(i + 1, len(hashes)):
                    fpath_b, hash_b = hashes[j]
                    if fpath_b in assigned:
                        continue
                    diff_bits = bin(hash_a ^ hash_b).count('1')
                    if diff_bits <= 4:
                        current_cluster.append(fpath_b)
                        assigned.add(fpath_b)
                if len(current_cluster) > 1:
                    assigned.add(fpath_a)
                    similar_clusters.extend(current_cluster)

            result_data = {
                "personas": personas_list,
                "animales": animales_list,
                "un_dia_como_hoy": un_dia_como_hoy,
                "similares": similar_clusters,
                "gps_groups": gps_groups,
                "name_groups": name_groups,
                "fallback": self.file_list[:12]
            }

            if self._is_running:
                self.analysis_completed.emit(result_data)

        def stop(self):
            self._is_running = False

        def _extract_gps(self, path: str):
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS, GPSTAGS
                with Image.open(path) as im:
                    exif = im._getexif()
                    if not exif:
                        return None
                    gps_info = {}
                    for tag, value in exif.items():
                        decoded = TAGS.get(tag, tag)
                        if decoded == "GPSInfo":
                            for t in value:
                                sub_decoded = GPSTAGS.get(t, t)
                                gps_info[sub_decoded] = value[t]
                            break
                    if not gps_info or "GPSLatitude" not in gps_info or "GPSLongitude" not in gps_info:
                        return None

                    def _dms_to_dd(val):
                        return float(val[0]) + (float(val[1]) / 60.0) + (float(val[2]) / 3600.0)

                    lat = _dms_to_dd(gps_info["GPSLatitude"])
                    if str(gps_info.get("GPSLatitudeRef", "N")).upper() != "N":
                        lat = -lat
                    lon = _dms_to_dd(gps_info["GPSLongitude"])
                    if str(gps_info.get("GPSLongitudeRef", "E")).upper() != "E":
                        lon = -lon
                    return (round(lat, 2), round(lon, 2))
            except Exception:
                return None

    def _add_memorias_section(self, title: str, subtitle: str, files: list):
        if not files:
            return

        sec_header = QWidget()
        sec_header.setStyleSheet("background-color: transparent;")
        sh_lay = QVBoxLayout(sec_header)
        sh_lay.setContentsMargins(0, 10, 0, 6)
        sh_lay.setSpacing(2)

        lbl_sec_title = QLabel(title)
        lbl_sec_title.setFont(QFont("Segoe UI Variable Display", 13, QFont.Weight.Bold))
        lbl_sec_title.setStyleSheet("color: #FFFFFF; background: transparent;")

        lbl_sec_sub = QLabel(subtitle)
        lbl_sec_sub.setFont(QFont("Segoe UI Variable Text", 9))
        lbl_sec_sub.setStyleSheet("color: #94A3B8; background: transparent;")

        sh_lay.addWidget(lbl_sec_title)
        sh_lay.addWidget(lbl_sec_sub)
        self.memorias_layout.addWidget(sec_header)

        available_w = max(480, self.width() - 96)
        calculated_rows = self._compute_justified_rows(files[:8], available_w, spacing=10)

        for row_items, is_incomplete in calculated_rows:
            row_widget = QWidget()
            row_widget.setStyleSheet("background-color: transparent;")
            r_layout = QHBoxLayout(row_widget)
            r_layout.setContentsMargins(0, 0, 0, 0)
            r_layout.setSpacing(10)
            r_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            for p, tw, th in row_items:
                tile = ModernPhotoTile(p, width=tw, height=th)
                tile.clicked.connect(self.open_media_viewer)
                tile.action_requested.connect(self.handle_tile_action)
                r_layout.addWidget(tile)

            if is_incomplete:
                r_layout.addStretch()

            self.memorias_layout.addWidget(row_widget)

    def _display_cached_memorias(self, data: dict):
        clear_layout_safely(self.memorias_layout)

        lbl_title = QLabel("Memorias y Colecciones Inteligentes")
        lbl_title.setFont(QFont("Segoe UI Variable Display", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #FFFFFF; padding-top: 6px; padding-bottom: 2px;")
        self.memorias_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        sections_added = 0

        personas = data.get("personas", [])
        if personas:
            self._add_memorias_section(
                "👤 Personas y Retratos",
                "Fotografías donde se reconocieron rostros humanos",
                personas
            )
            sections_added += 1

        animales = data.get("animales", [])
        if animales:
            self._add_memorias_section(
                "🐾 Mascotas y Animales",
                "Capturas identificadas con animales y mascotas",
                animales
            )
            sections_added += 1

        similares = data.get("similares", [])
        if similares:
            self._add_memorias_section(
                "👥 Tomas idénticas y fotos similares",
                "Ráfagas continuas y fotos duplicadas detectadas",
                similares
            )
            sections_added += 1

        gps_groups = data.get("gps_groups", {})
        for coords, g_files in gps_groups.items():
            if len(g_files) >= 1:
                self._add_memorias_section(
                    f"📍 Lugares y Viajes ({coords[0]}°, {coords[1]}°)",
                    "Fotografías tomadas en esta ubicación geográfica registrada",
                    g_files
                )
                sections_added += 1
                if sections_added >= 5:
                    break

        un_dia = data.get("un_dia_como_hoy", [])
        if un_dia:
            self._add_memorias_section(
                "📅 Un día como hoy en años anteriores",
                "Momentos capturados en estas fechas en años pasados",
                un_dia
            )
            sections_added += 1

        name_groups = data.get("name_groups", {})
        for group_label, files_in_group in name_groups.items():
            if len(files_in_group) >= 3 and sections_added < 6:
                self._add_memorias_section(
                    f"📁 Álbum: {group_label}",
                    f"Colección agrupada en {group_label}",
                    files_in_group
                )
                sections_added += 1

        if sections_added == 0:
            self._add_memorias_section(
                "✨ Momentos Destacados",
                "Tus fotos recientes destacadas",
                data.get("fallback", self.all_media_files[:12])
            )

        self.memorias_layout.addStretch()

    def _on_memorias_ready(self, data: dict):
        self._cached_memorias_data = data
        if self.stack.currentIndex() == 3:
            self._display_cached_memorias(data)

    def render_memorias_view(self):
        """Renderiza las memorias agrupadas por rostros, animales, lugares y similitud en segundo plano."""
        if hasattr(self, "_cached_memorias_data") and self._cached_memorias_data:
            self._display_cached_memorias(self._cached_memorias_data)
            return

        clear_layout_safely(self.memorias_layout)

        lbl_title = QLabel("Memorias y Colecciones Inteligentes")
        lbl_title.setFont(QFont("Segoe UI Variable Display", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #FFFFFF; padding-top: 6px; padding-bottom: 2px;")
        self.memorias_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        if len(self.all_media_files) < 2:
            lbl_empty = QLabel("Agrega más fotos o videos para que Jade organice tus memorias automáticamente.")
            lbl_empty.setFont(QFont("Segoe UI Variable Display", 11))
            lbl_empty.setStyleSheet("color: #64748B; padding: 40px;")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.memorias_layout.addWidget(lbl_empty)
            return

        lbl_loading = QLabel("🔍 Analizando rostros, mascotas, lugares y fotos similares...\n(Procesando en segundo plano sin congelar la app)")
        lbl_loading.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.DemiBold))
        lbl_loading.setStyleSheet("color: #38BDF8; padding: 50px;")
        lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.memorias_layout.addWidget(lbl_loading)
        self.memorias_layout.addStretch()

        if hasattr(self, "_memorias_thread") and self._memorias_thread and self._memorias_thread.isRunning():
            return

        self._memorias_thread = self.MemoriasWorkerThread(self.all_media_files, self)
        self._memorias_thread.analysis_completed.connect(self._on_memorias_ready)
        self._memorias_thread.start()

    def show_profile_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet(ThemePalette.get_menu_style(self.is_dark))

        act_name = menu.addAction("Cambiar nombre")
        act_photo = menu.addAction("Cambiar foto de perfil")
        menu.addSeparator()
        act_folders = menu.addAction("Carpetas permitidas para Jade")
        act_name_excl = menu.addAction("Excluir carpetas por nombre (Todos los discos)")

        action = menu.exec(pos)
        if action == act_name:
            self.change_username()
        elif action == act_photo:
            self.change_avatar_photo()
        elif action == act_folders:
            self.manage_allowed_folders()
        elif action == act_name_excl:
            self.prompt_exclude_folder_by_name()

    def change_username(self):
        profile = load_gallery_profile()
        curr_name = profile.get("username", "Usuario")
        new_name, ok = QInputDialog.getText(self, "Nombre de usuario", "Escribe tu nombre:", text=curr_name)
        if ok and new_name.strip():
            profile["username"] = new_name.strip()
            save_gallery_profile(profile)
            self.profile_widget.update_profile()

    def change_avatar_photo(self):
        img_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar foto de perfil", os.path.expanduser("~"),
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if img_path and os.path.exists(img_path):
            norm_img = os.path.abspath(img_path)
            profile = load_gallery_profile()
            profile["avatar_path"] = norm_img
            save_gallery_profile(profile)

            cfg_file = os.path.join(get_jade_appdata_dir(), "config.json")
            try:
                cfg_data = {}
                if os.path.exists(cfg_file):
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                cfg_data["user_avatar"] = norm_img
                with open(cfg_file, "w", encoding="utf-8") as f:
                    json.dump(cfg_data, f, indent=4, ensure_ascii=False)
            except Exception:
                pass

            if self.config and hasattr(self.config, "set"):
                try:
                    self.config.set("user_avatar", norm_img)
                except Exception:
                    pass

            self.profile_widget.update_profile()

    def manage_allowed_folders(self):
        profile = load_gallery_profile()
        dialog = AllowedFoldersDialog(profile.get("allowed_folders", []), self)
        dialog.folders_updated.connect(self.load_all_allowed_folders)
        dialog.exec()

    def toggle_selection_mode(self):
        self.is_multi_select_mode = not self.is_multi_select_mode
        self.selected_album_paths.clear()
        self._update_all_album_tiles_selection_state()

        if self.is_multi_select_mode:
            self.lbl_selection_count.setText("0 seleccionados")
            self.selection_action_bar.show()
            self.selection_action_bar.raise_()
            self._reposition_hud_elements()
            apply_fade_transition(self.selection_action_bar, duration_ms=160)
        else:
            self.selection_action_bar.hide()

    def cancel_selection_mode(self):
        if self.is_multi_select_mode:
            self.is_multi_select_mode = False
            self.selected_album_paths.clear()
            self._update_all_album_tiles_selection_state()
            self.selection_action_bar.hide()

    def _update_all_album_tiles_selection_state(self):
        if hasattr(self, "scroll_albumes") and self.scroll_albumes:
            for tile in self.scroll_albumes.findChildren(ModernAlbumTile):
                tile.set_selection_mode(self.is_multi_select_mode)
                tile.set_selected(os.path.normpath(tile.folder_path) in self.selected_album_paths)

    def handle_album_selection_toggled(self, folder_path: str, is_selected: bool):
        norm = os.path.normpath(folder_path)
        if is_selected:
            self.selected_album_paths.add(norm)
        else:
            self.selected_album_paths.discard(norm)
        count = len(self.selected_album_paths)
        self.lbl_selection_count.setText(f"{count} seleccionado{'s' if count != 1 else ''}")

    def exclude_selected_folders(self):
        if not self.selected_album_paths:
            QMessageBox.information(self, "Excluir Álbumes", "No has seleccionado ningún álbum para excluir.")
            return

        db = load_gallery_db()
        all_albums = db.get("albums", [])
        excluded = load_excluded_folders()

        expanded_folders = set()
        for p in self.selected_album_paths:
            p_str = str(p)
            if p_str.startswith("group::"):
                g_key = p_str.split("group::", 1)[1].strip().lower()
                excluded.add(p_str)
                for alb in all_albums:
                    alb_name = alb.get("name") or os.path.basename(alb.get("folder_path", ""))
                    if get_album_group_key(alb_name) == g_key:
                        fp = alb.get("folder_path")
                        if fp:
                            expanded_folders.add(os.path.normpath(fp))
                            excluded.add(os.path.normpath(fp))
            else:
                norm_p = os.path.normpath(p_str)
                expanded_folders.add(norm_p)
                excluded.add(norm_p)
                for alb in all_albums:
                    alb_fp = os.path.normpath(alb.get("folder_path", ""))
                    if alb_fp.lower().startswith(norm_p.lower() + os.sep.lower()):
                        expanded_folders.add(alb_fp)
                        excluded.add(alb_fp)

        count = len(expanded_folders) or len(self.selected_album_paths)
        rep = QMessageBox.question(
            self,
            "Confirmar Exclusión",
            f"¿Deseas excluir {count} álbum(es) seleccionados (incluyendo subcarpetas y grupos)?\n\n"
            f"• Se guardarán en 'excluir.json'.\n"
            f"• Ya no se mostrarán ni se cargarán en la galería.\n"
            f"(Tus fotos y carpetas originales en el disco NO se borrarán)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if rep != QMessageBox.StandardButton.Yes:
            return

        save_excluded_folders(excluded)

        db["albums"] = [a for a in all_albums if not is_folder_excluded(a.get("folder_path", ""), excluded)]
        save_gallery_db(db)

        self.cancel_selection_mode()
        self.load_all_allowed_folders()
        self.render_albumes_view(force_reload=True)

        QMessageBox.information(
            self,
            "Álbumes Excluidos",
            f"Se han excluido {count} álbum(es) y sus grupos correctamente."
        )

    def _reposition_hud_elements(self):
        if hasattr(self, "nav_bar") and self.nav_bar:
            pill_w = min(self.width() - 40, 560)
            pill_h = 48
            x = (self.width() - pill_w) // 2
            y = self.height() - pill_h - 18
            self.nav_bar.setGeometry(x, y, pill_w, pill_h)
            self.nav_bar.raise_()

        if hasattr(self, "selection_action_bar") and self.selection_action_bar and self.selection_action_bar.isVisible():
            bar_w = min(self.width() - 40, 720)
            bar_h = 48
            bx = (self.width() - bar_w) // 2
            by = self.height() - bar_h - 74
            self.selection_action_bar.setGeometry(bx, by, bar_w, bar_h)
            self.selection_action_bar.raise_()

    def load_all_allowed_folders(self):
        db = load_gallery_db()
        excluded = load_excluded_folders()
        excluded_files_set = load_excluded_files()
        cached_media = []
        seen = set()

        for alb in db.get("albums", []):
            alb_folder = alb.get("folder_path", "")
            if alb_folder and is_folder_excluded(os.path.normpath(alb_folder), excluded):
                continue
            for fp in alb.get("media_files", []):
                norm = os.path.normpath(fp)
                if norm not in seen and norm not in excluded_files_set:
                    seen.add(norm)
                    cached_media.append(norm)

        def _sort_key(p):
            p_lower = p.lower()
            return 0 if any(k in p_lower for k in ["perla", "jade"]) else 1

        cached_media.sort(key=_sort_key)

        if cached_media:
            self.all_media_files = cached_media
            self.current_filtered_files = cached_media
            self._albums_rendered = False
            self._cached_albums_data = []
            self.render_mural(cached_media)
            return

        profile = load_gallery_profile()
        folders = profile.get("allowed_folders", [])
        candidate_folders = []
        for f in folders:
            if f and os.path.exists(f) and os.path.isdir(f):
                candidate_folders.append(f)
                try:
                    with os.scandir(f) as it:
                        for entry in it:
                            if entry.is_dir(follow_symlinks=False):
                                candidate_folders.append(entry.path)
                except Exception:
                    pass

        raw_items = []
        seen_paths = set()
        for folder in candidate_folders:
            norm_folder = os.path.normpath(folder)
            if is_folder_excluded(norm_folder, excluded):
                continue
            try:
                with os.scandir(folder) as it:
                    for entry in it:
                        try:
                            if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(ALL_MEDIA_EXTS):
                                norm_p = os.path.normpath(entry.path)
                                if norm_p not in seen_paths and norm_p not in excluded_files_set:
                                    seen_paths.add(norm_p)
                                    stat_res = entry.stat(follow_symlinks=False)
                                    raw_items.append((entry.path, stat_res.st_mtime))
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                pass

        def _raw_sort_key(item):
            p = item[0].lower()
            is_jade = 0 if any(k in p.lower() for k in ["perla", "jade"]) else 1
            return (is_jade, -item[1])

        raw_items.sort(key=_raw_sort_key)
        all_found = [item[0] for item in raw_items]

        self.all_media_files = all_found
        self.current_filtered_files = all_found
        self._albums_rendered = False
        self._cached_albums_data = []

        sync_gallery_db_from_folders(folders)
        self.render_mural(all_found)

    def render_explorar_view(self):
        clear_layout_safely(self.explorar_layout)

        profile = load_gallery_profile()
        folders = profile.get("allowed_folders", [])
        excluded = load_excluded_folders()
        matcher = get_exclusion_matcher(excluded)

        db = load_gallery_db()
        albums = db.get("albums", [])

        counts_map = {}
        for alb in albums:
            fp = alb.get("folder_path")
            if fp and not matcher.is_excluded(fp):
                counts_map[os.path.normpath(fp)] = alb.get("count", 0)

        # Panel de Control Superior (Acciones Rápidas)
        top_cards_row = QHBoxLayout()
        top_cards_row.setSpacing(16)

        # Tarjeta 1: Escanear PC
        card_scan = QFrame()
        card_scan.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111726, stop:1 #0C101A);
                border: 1px solid rgba(0, 120, 212, 0.4);
                border-radius: 14px;
            }
        """)
        cs_lay = QVBoxLayout(card_scan)
        cs_lay.setContentsMargins(18, 16, 18, 16)
        cs_lay.setSpacing(10)

        lbl_cs_title = QLabel("Examinar Toda la PC")
        lbl_cs_title.setFont(QFont("Segoe UI Variable Display", 13, QFont.Weight.Bold))
        lbl_cs_title.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")

        lbl_cs_desc = QLabel("Indexa automáticamente discos locales y descubre tus fotos.")
        lbl_cs_desc.setFont(QFont("Segoe UI Variable Text", 9))
        lbl_cs_desc.setStyleSheet("color: #94A3B8; background: transparent; border: none;")

        btn_scan_all = QPushButton("Iniciar Búsqueda")
        btn_scan_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_scan_all.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #106EBE; }
        """)
        btn_scan_all.clicked.connect(self.start_full_pc_scan)

        cs_lay.addWidget(lbl_cs_title)
        cs_lay.addWidget(lbl_cs_desc)
        cs_lay.addWidget(btn_scan_all, alignment=Qt.AlignmentFlag.AlignLeft)

        # Tarjeta 2: Limpieza y Mantenimiento (Eliminar Caché)
        card_clean = QFrame()
        card_clean.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1A1218, stop:1 #120C10);
                border: 1px solid rgba(232, 17, 35, 0.35);
                border-radius: 14px;
            }
        """)
        cc_lay = QVBoxLayout(card_clean)
        cc_lay.setContentsMargins(18, 16, 18, 16)
        cc_lay.setSpacing(10)

        lbl_cc_title = QLabel("Limpieza y Rendimiento")
        lbl_cc_title.setFont(QFont("Segoe UI Variable Display", 13, QFont.Weight.Bold))
        lbl_cc_title.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")

        lbl_cc_desc = QLabel("Libera memoria RAM, borra miniaturas y vacía la galería.")
        lbl_cc_desc.setFont(QFont("Segoe UI Variable Text", 9))
        lbl_cc_desc.setStyleSheet("color: #94A3B8; background: transparent; border: none;")

        btn_clear_cache = QPushButton("Eliminar Caché y Vaciar Galería")
        btn_clear_cache.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_cache.setStyleSheet("""
            QPushButton {
                background-color: rgba(232, 17, 35, 0.25);
                color: #FFA4A4;
                border: 1px solid rgba(232, 17, 35, 0.5);
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #E81123;
                color: #FFFFFF;
                border: none;
            }
        """)
        btn_clear_cache.clicked.connect(self.clear_all_gallery_cache)

        cc_lay.addWidget(lbl_cc_title)
        cc_lay.addWidget(lbl_cc_desc)
        cc_lay.addWidget(btn_clear_cache, alignment=Qt.AlignmentFlag.AlignLeft)

        top_cards_row.addWidget(card_scan)
        top_cards_row.addWidget(card_clean)
        self.explorar_layout.addLayout(top_cards_row)

        valid_folders = [f for f in folders if f and not matcher.is_excluded(f)]

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 10, 0, 0)
        lbl_folders_title = QLabel(f"Carpetas y Ubicaciones Registradas ({len(valid_folders)})")
        lbl_folders_title.setFont(QFont("Segoe UI Variable Display", 13, QFont.Weight.Bold))
        lbl_folders_title.setStyleSheet("color: #E2E8F0;")

        btn_manage = QPushButton("Administrar Carpetas")
        btn_manage.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_manage.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.16); }
        """)
        btn_manage.clicked.connect(self.manage_allowed_folders)

        header_row.addWidget(lbl_folders_title)
        header_row.addStretch()
        header_row.addWidget(btn_manage)
        self.explorar_layout.addLayout(header_row)

        if not valid_folders:
            lbl_empty = QLabel("No hay carpetas activas registradas (o todas han sido excluidas).")
            lbl_empty.setFont(QFont("Segoe UI Variable Text", 11))
            lbl_empty.setStyleSheet("color: #64748B; padding: 40px;")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.explorar_layout.addWidget(lbl_empty)
            self.explorar_layout.addStretch()
            return

        list_container = QWidget()
        list_container.setStyleSheet("background: transparent;")
        list_lay = QVBoxLayout(list_container)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(8)

        displayed_folders = valid_folders[:80]

        for fpath in displayed_folders:
            if not fpath:
                continue

            norm_path = os.path.normpath(fpath)
            count = counts_map.get(norm_path, 0)

            row_frame = QFrame()
            row_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            row_frame.setStyleSheet("""
                QFrame#ExplorarRowFrame {
                    background-color: #121722;
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 8px;
                }
                QFrame#ExplorarRowFrame:hover {
                    background-color: #182030;
                    border: 1px solid #0078D4;
                }
            """)
            row_frame.setObjectName("ExplorarRowFrame")

            r_lay = QHBoxLayout(row_frame)
            r_lay.setContentsMargins(14, 8, 14, 8)
            r_lay.setSpacing(12)

            fname = os.path.basename(fpath) or fpath
            lbl_name = QLabel(fname)
            lbl_name.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
            lbl_name.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
            lbl_name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            lbl_path = QLabel(fpath)
            lbl_path.setFont(QFont("Segoe UI Variable Text", 9))
            lbl_path.setStyleSheet("color: #64748B; background: transparent; border: none;")
            lbl_path.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            lbl_cnt = QLabel(f"{count} elem." if count > 0 else "")
            lbl_cnt.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))
            lbl_cnt.setStyleSheet("color: #0078D4; background: transparent; border: none;")
            lbl_cnt.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            btn_exclude_tree = QPushButton("Excluir...")
            btn_exclude_tree.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_exclude_tree.setStyleSheet("""
                QPushButton {
                    background-color: rgba(232, 17, 35, 0.18);
                    color: #FF99A4;
                    border: 1px solid rgba(232, 17, 35, 0.35);
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #E81123;
                    color: #FFFFFF;
                }
            """)

            r_lay.addWidget(lbl_name)
            r_lay.addWidget(lbl_path, stretch=1)
            r_lay.addWidget(lbl_cnt)
            r_lay.addWidget(btn_exclude_tree)

            def _make_row_press(target_folder):
                def _handler(event):
                    if event.button() == Qt.MouseButton.LeftButton:
                        self.filter_and_switch_to_folder(target_folder)
                    elif event.button() == Qt.MouseButton.RightButton:
                        event.accept()
                return _handler

            def _make_row_context(target_folder):
                def _handler(event):
                    self.show_path_exclusion_menu(target_folder, event.globalPos())
                    event.accept()
                return _handler

            row_frame.mousePressEvent = _make_row_press(fpath)
            row_frame.contextMenuEvent = _make_row_context(fpath)

            btn_exclude_tree.clicked.connect(lambda _, p=fpath, b=btn_exclude_tree: self.show_path_exclusion_menu(p, b.mapToGlobal(QPoint(0, b.height()))))

            list_lay.addWidget(row_frame)

        self.explorar_layout.addWidget(list_container)
        self.explorar_layout.addStretch()

    def clear_all_gallery_cache(self):
        rep = QMessageBox.question(
            self,
            "Eliminar todo el caché",
            "¿Estás seguro de que deseas eliminar todo el caché y vaciar la galería?\n\n"
            "• Se borrarán todas las miniaturas y fotogramas guardados en disco.\n"
            "• Se liberará toda la memoria RAM consumida.\n"
            "• Se vaciarán los álbumes y carpetas registradas en Jade.\n\n"
            "(Tus fotos y videos originales no se modificarán)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if rep != QMessageBox.StandardButton.Yes:
            return

        clear_layout_safely(self.explorar_layout)

        overlay = OptimizationOverlayWidget()
        overlay.lbl_title.setText("Vaciando Galería y Caché")
        overlay.lbl_subtitle.setText("Liberando memoria RAM y eliminando registros en disco...")
        overlay.progress_bar.setRange(0, 0)
        overlay.lbl_status.setText("Eliminando datos en segundo plano sin congelar la aplicación...")
        self.explorar_layout.addWidget(overlay)

        self._clear_cache_thread = ClearCacheWorkerThread(self)

        def _on_clearing_done():
            self.all_media_files = []
            self.current_filtered_files = []
            self._cached_albums_data = []
            self._albums_rendered = False

            self.render_mural([])
            self.render_explorar_view()

            QMessageBox.information(
                self,
                "Caché Eliminado",
                "El caché ha sido eliminado por completo y la galería se ha restablecido a su estado vacío."
            )

        self._clear_cache_thread.clearing_finished.connect(_on_clearing_done)
        self._clear_cache_thread.start()

    def filter_and_switch_to_folder(self, target_folder: str):
        found = []
        if os.path.exists(target_folder):
            try:
                for fname in os.listdir(target_folder):
                    if fname.lower().endswith(ALL_MEDIA_EXTS):
                        p = os.path.join(target_folder, fname)
                        if os.path.isfile(p):
                            found.append(p)
            except Exception:
                pass

        found.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        self.current_filtered_files = found
        self.render_mural(found)
        self.nav_bar.set_active_tab("fotos")

    def _compute_justified_rows(self, paths: list, available_width: int, spacing: int = 10):
        return compute_justified_rows_engine(paths, available_width, spacing)

    def render_mural(self, file_list: list):
        self.current_filtered_files = list(file_list)
        if hasattr(self, "presentation_view"):
            self.presentation_view.set_files(file_list[:150])
        self.container_widget.set_files(file_list)

    def load_next_sections_batch(self, initial: bool = False):
        pass

    def _check_mural_fill(self):
        pass

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_initial_render_done", False):
            self._initial_render_done = True
            if not self.initial_file:
                QTimer.singleShot(0, self.load_all_allowed_folders)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_hud_elements()
        self.apply_theme(ThemeManager.get_instance().is_dark)

        if self.isMinimized() or not self.isVisible():
            return

        idx = self.stack.currentIndex()
        if idx == 0:
            self._check_mural_fill()
        elif idx == 1:
            self._check_videos_fill()
        elif idx == 2:
            if hasattr(self, "albumes_stack"):
                sub_idx = self.albumes_stack.currentIndex()
                if sub_idx == 0:
                    self._check_albumes_fill()
                elif sub_idx == 1:
                    self._check_album_detail_fill()

        if hasattr(self, "_resize_debounce_timer"):
            self._resize_debounce_timer.start(60)

    def _recalc_grid_debounced(self):
        if self.isMinimized() or not self.isVisible():
            return

        self._last_rendered_width = self.width()
        idx = self.stack.currentIndex()

        if idx == 0:
            if hasattr(self, "fotos_views_stack") and self.fotos_views_stack.currentIndex() == 0:
                if hasattr(self, "container_widget") and self.container_widget:
                    vp_w = self.scroll_area.viewport().width() if (self.scroll_area and self.scroll_area.viewport()) else self.width()
                    self.container_widget.recompute_layout(vp_w)
        elif idx == 1:
            if hasattr(self, "container_videos") and self.container_videos:
                vp_w = self.scroll_videos.viewport().width() if (self.scroll_videos and self.scroll_videos.viewport()) else self.width()
                self.container_videos.recompute_layout(vp_w)
        elif idx == 2 and hasattr(self, "albumes_stack"):
            sub_idx = self.albumes_stack.currentIndex()
            if sub_idx == 0:
                self.render_albumes_view(force_reload=True)
            elif sub_idx == 1 and hasattr(self, "container_album_detail") and self.container_album_detail:
                vp_w = self.scroll_album_detail.viewport().width() if (self.scroll_album_detail and self.scroll_album_detail.viewport()) else self.width()
                self.container_album_detail.recompute_layout(vp_w)
            elif sub_idx == 2 and hasattr(self, "_currently_viewed_group_data") and self._currently_viewed_group_data:
                g_entry = {
                    "group_data": self._currently_viewed_group_data,
                    "display_title": self.lbl_album_group_title.text().split("•")[0].strip()
                }
                self.open_album_group(g_entry)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if hasattr(self, "stack") and self.stack.currentIndex() == 5:
                if hasattr(self, "page_visor_hd"):
                    self.page_visor_hd._handle_escape()
                else:
                    self.exit_embedded_viewer()
                event.accept()
                return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            if hasattr(self, "stack") and self.stack.currentIndex() == 5:
                if hasattr(self, "page_visor_hd"):
                    self.page_visor_hd._handle_escape()
                else:
                    self.exit_embedded_viewer()
                return True
        return super().eventFilter(watched, event)

    def open_media_viewer(self, filepath: str, explicit_file_list: list = None):
        if HDMediaViewerDialog:
            current_tab = self.stack.currentIndex()
            if current_tab != 5:
                self._previous_stack_tab = current_tab

            if explicit_file_list and isinstance(explicit_file_list, list) and filepath in explicit_file_list:
                target_list = list(explicit_file_list)
            else:
                if current_tab == 1:
                    target_list = [f for f in self.all_media_files if is_video_file(f)]
                elif current_tab == 2:
                    if hasattr(self, "albumes_stack") and self.albumes_stack.currentIndex() == 1 and hasattr(self, "_album_detail_queue") and self._album_detail_queue:
                        target_list = list(self._album_detail_queue)
                    else:
                        target_list = self.current_filtered_files if self.current_filtered_files else self.all_media_files
                elif current_tab == 3:
                    target_list = self.all_media_files[:min(9, len(self.all_media_files))]
                else:
                    target_list = self.current_filtered_files if self.current_filtered_files else self.all_media_files

            if filepath not in target_list:
                target_list = [filepath] + target_list

            curr_idx = target_list.index(filepath) if filepath in target_list else 0

            self.top_bar.hide()
            self.nav_bar.hide()
            if hasattr(self, "selection_action_bar"):
                self.selection_action_bar.hide()

            self.page_visor_hd.load_media_view(target_list, curr_idx)
            self.stack.setCurrentIndex(5)
            apply_fade_transition(self.page_visor_hd, duration_ms=180)
        else:
            try:
                os.startfile(filepath)
            except Exception:
                pass

    def exit_embedded_viewer(self):
        last_viewed_path = ""
        if hasattr(self, "page_visor_hd") and self.page_visor_hd.file_list and (0 <= self.page_visor_hd.current_idx < len(self.page_visor_hd.file_list)):
            last_viewed_path = self.page_visor_hd.file_list[self.page_visor_hd.current_idx]

        if self.isFullScreen():
            prev_state = getattr(self.page_visor_hd.viewer_widget, "_prev_window_state", None) if self.page_visor_hd and self.page_visor_hd.viewer_widget else None
            if prev_state is not None and (prev_state & Qt.WindowState.WindowMaximized):
                self.showMaximized()
            else:
                self.showNormal()

        self.page_visor_hd.set_fullscreen_mode(False)
        self.page_visor_hd.cleanup_current_viewer()
        self.top_bar.show()
        self.nav_bar.show()

        target_idx = getattr(self, "_previous_stack_tab", 0)
        if target_idx >= 5:
            target_idx = 0

        self.stack.setCurrentIndex(target_idx)
        apply_fade_transition(self.stack.currentWidget(), duration_ms=180)

        if target_idx == 0:
            if hasattr(self, 'container_widget') and self.container_widget:
                self.container_widget.show()
                self.container_widget.update_visible_rows()
        elif target_idx == 1:
            if hasattr(self, 'container_videos') and self.container_videos:
                self.container_videos.show()
                self.container_videos.update_visible_rows()
        elif target_idx == 2:
            if hasattr(self, "albumes_stack") and self.albumes_stack.currentIndex() == 1 and hasattr(self, 'container_album_detail') and self.container_album_detail:
                self.container_album_detail.show()
                self.container_album_detail.update_visible_rows()

        if last_viewed_path:
            QTimer.singleShot(120, lambda p=last_viewed_path, tidx=target_idx: self._scroll_and_highlight_media(p, tidx))

    def _scroll_and_highlight_media(self, media_path: str, tab_idx: int):
        target_scroll = None
        if tab_idx == 0:
            target_scroll = self.scroll_area
        elif tab_idx == 1:
            target_scroll = self.scroll_videos
        elif tab_idx == 2:
            if hasattr(self, "albumes_stack") and self.albumes_stack.currentIndex() == 1:
                target_scroll = self.scroll_album_detail

        if not target_scroll:
            return

        norm_target = os.path.normpath(media_path)
        for tile in target_scroll.findChildren(ModernPhotoTile):
            try:
                if sip.isdeleted(tile):
                    continue
            except Exception:
                continue

            if os.path.normpath(tile.media_path) == norm_target:
                target_scroll.ensureWidgetVisible(tile, 50, 100)
                tile.is_hovered = True
                tile.update()
                QTimer.singleShot(1400, lambda t=tile: self._clear_tile_focus(t))
                break

    def _clear_tile_focus(self, tile):
        if not tile:
            return
        try:
            if sip.isdeleted(tile):
                return
            tile.is_hovered = False
            tile.update()
        except Exception:
            pass

    def handle_tile_action(self, action: str, filepath: str):
        if action == "view":
            self.open_media_viewer(filepath)
        elif action == "copy":
            from PyQt6.QtCore import QMimeData, QUrl
            cb = QApplication.clipboard()
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(os.path.abspath(filepath))])
            cb.setMimeData(mime)
        elif action == "folder":
            try:
                norm_path = os.path.normpath(filepath)
                subprocess.Popen(f'explorer /select,"{norm_path}"', creationflags=0x08000000)
            except Exception:
                pass
        elif action == "exclude":
            rep = QMessageBox.question(
                self, "Excluir Imagen",
                f"¿Deseas excluir esta imagen de Jade?\n\n{os.path.basename(filepath)}\n\n(El archivo NO se borrará de tu disco duro)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if rep == QMessageBox.StandardButton.Yes:
                self.exclude_single_file(filepath)
        elif action == "rename":
            d_name, o_name = os.path.split(filepath)
            b_name, ext = os.path.splitext(o_name)
            new_n, ok = QInputDialog.getText(self, "Renombrar", "Nuevo nombre:", text=b_name)
            if ok and new_n.strip():
                dest = os.path.join(d_name, new_n.strip() + ext)
                try:
                    os.rename(filepath, dest)
                    self.load_all_allowed_folders()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo renombrar: {e}")
        elif action == "delete":
            rep = QMessageBox.question(
                self, "Eliminar", f"¿Eliminar este archivo permanentemente?\n\n{os.path.basename(filepath)}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if rep == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(filepath)
                    self.load_all_allowed_folders()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo eliminar: {e}")

__all__ = ["JadePhotosGalleryWindow", "ModernPhotoTile", "ModernAlbumTile"]

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = JadePhotosGalleryWindow()
    win.show()
    sys.exit(app.exec())

# Alias de compatibilidad retroactiva
PerlaPhotosGalleryWindow = JadePhotosGalleryWindow
