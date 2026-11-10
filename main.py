from theme_manager import (
    ThemeManager, ThemePalette, get_jade_appdata_dir,
    enable_win11_effects, detect_windows_system_theme
)
import sys
import os
import json
import time
import math
import ctypes
import ctypes.wintypes
import winreg
import asyncio
import subprocess
import shutil
import re
import webbrowser
import threading
from datetime import datetime
from pathlib import Path


try:
    from jade_editor import ScreenshotFloatingCard
    JADE_EDITOR_AVAILABLE = True
except Exception:
    JADE_EDITOR_AVAILABLE = False

import faulthandler

def get_desktop_path() -> str:
    """Obtiene dinámicamente la ruta del escritorio del usuario."""
    desktop_path = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            raw_path, _ = winreg.QueryValueEx(key, "Desktop")
            desktop_path = os.path.expandvars(raw_path)
    except Exception:
        pass

    if desktop_path and os.path.exists(desktop_path):
        return desktop_path

    user_home = os.path.expanduser("~")
    candidates = [
        os.path.join(user_home, "OneDrive", "Escritorio"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "Escritorio"),
        os.path.join(user_home, "Desktop"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return user_home

# Activación inmediata del monitor nativo de excepciones de hardware C/C++ en el Escritorio
try:
    _dt_crash_dir = get_desktop_path()
    _dt_crash_file_path = os.path.join(_dt_crash_dir, "jade_crash_diagnostic.log")
    _crash_log_file = open(_dt_crash_file_path, "w", encoding="utf-8", buffering=1)
    faulthandler.enable(file=_crash_log_file, all_threads=True)
    
    _crash_log_file.write("====================================================================\n")
    _crash_log_file.write(f"JADE SISTEMA DIAGNÓSTICO EN TIEMPO REAL - INICIADO: {datetime.now()}\n")
    _crash_log_file.write(f"SO: Windows {sys.getwindowsversion().major}.{sys.getwindowsversion().minor} (Build {sys.getwindowsversion().build})\n")
    _crash_log_file.write(f"Python: {sys.version} ({'64 bits' if sys.maxsize > 2**32 else '32 bits'})\n")
    _crash_log_file.write("====================================================================\n\n")

    # Inspección preventiva del código fuente en las líneas marcadas por el traceback
    try:
        _src_path = os.path.abspath(__file__)
        if os.path.exists(_src_path):
            with open(_src_path, "r", encoding="utf-8", errors="ignore") as _f_src:
                _all_src_lines = _f_src.readlines()

            _crash_log_file.write("--- INSPECCIÓN DE LÍNEAS REPORTADAS EN MAIN.PY ---\n")
            for _target in [2770, 4588, 9986, 9989]:
                _crash_log_file.write(f"\n[Contexto alrededor de la Línea {_target}]:\n")
                _start_idx = max(0, _target - 6)
                _end_idx = min(len(_all_src_lines), _target + 5)
                for _idx in range(_start_idx, _end_idx):
                    _pfx = " >>> " if (_idx + 1) == _target else "     "
                    _crash_log_file.write(f"{_pfx}L{_idx + 1}: {_all_src_lines[_idx]}")
            _crash_log_file.write("\n----------------------------------------------------\n\n")
            _crash_log_file.flush()
    except Exception as _e_inspect:
        _crash_log_file.write(f"Aviso inspeccionando líneas de main.py: {_e_inspect}\n")
        _crash_log_file.flush()
except Exception as _e_init_diag:
    pass

# Redirección de salida estándar y ocultación de consola nativa en Windows con HWND validado
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

try:
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    kernel32.GetConsoleWindow.restype = ctypes.wintypes.HWND
    user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
    hwnd_console = kernel32.GetConsoleWindow()
    if hwnd_console:
        user32.ShowWindow(hwnd_console, 0)
except Exception:
    pass

from PyQt6.QtCore import (
    Qt, QThread, QRunnable, QThreadPool, QObject, pyqtSignal, pyqtSlot, QRect, QRectF, QPoint, QPointF, QLineF, QSize, QSettings,
    QBuffer, QIODevice, QStandardPaths, QEvent, QTimer, QUrl, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QFont,
    QKeySequence, QAction, QClipboard, QCursor, QScreen, QImage,
    QPainterPath, QTransform, QShortcut, QPolygonF
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox, QSystemTrayIcon, QMenu, QScrollArea,
    QFrame, QDialog, QTextEdit, QComboBox, QSplitter, QGraphicsDropShadowEffect,
    QProgressDialog, QSizePolicy, QTabWidget, QTabBar, QListWidget, QListWidgetItem,
    QInputDialog, QSlider, QColorDialog
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

def find_and_setup_vlc():
    """Detecta la ubicación de libvlc.dll en Windows e importa el módulo vlc globalmente de forma no bloqueante y ultra-rápida."""
    global VLC_AVAILABLE, VLC_PLUGIN_PATH, vlc

    if VLC_AVAILABLE and "vlc" in sys.modules:
        return True

    candidates = [
        os.path.join(get_jade_appdata_dir(), "bin", "vlc"),
        os.path.expanduser(r"~\AppData\Roaming\Jade\bin\vlc"),
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC"
    ]

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.insert(0, exe_dir)
        candidates.insert(1, os.path.join(exe_dir, "vlc"))
        candidates.insert(2, os.path.join(exe_dir, "bin", "vlc"))

    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, sys._MEIPASS)
        candidates.insert(1, os.path.join(sys._MEIPASS, "vlc"))
        candidates.insert(2, os.path.join(sys._MEIPASS, "bin", "vlc"))

    for p in candidates:
        if not p or not os.path.exists(p):
            continue

        dll_path = os.path.join(p, "libvlc.dll")
        if os.path.exists(dll_path):
            try:
                ctypes.windll.kernel32.SetDllDirectoryW(p)
            except Exception:
                pass

            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(p)
                except Exception:
                    pass

            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
            os.environ["PYTHON_VLC_LIB_PATH"] = dll_path
            os.environ["PYTHON_VLC_MODULE_PATH"] = p

            plugins_dir = os.path.join(p, "plugins")
            if os.path.exists(plugins_dir):
                VLC_PLUGIN_PATH = plugins_dir
                os.environ["VLC_PLUGIN_PATH"] = plugins_dir

            try:
                import vlc
                VLC_AVAILABLE = True
                log_message(f"Motor LibVLC vinculado e identificado con éxito en: {p}")
                return True
            except Exception as e:
                log_message(f"Error vinculando biblioteca LibVLC en {p}: {e}")

    VLC_AVAILABLE = False
    return False

VLC_AVAILABLE = False
VLC_PLUGIN_PATH = None

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False

def get_resource_path(relative_path: str) -> str:
    """Obtiene la ruta absoluta para recursos (como .py/resources/icon.ico),
    compatible con ejecución normal, entorno empaquetado y Nuitka."""
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

def get_jade_appdata_dir() -> str:
    """Retorna la ruta centralizada de almacenamiento de caché y configuración en AppData/Roaming/Jade."""
    appdata = os.path.expanduser(r"~\AppData\Roaming\Jade")
    os.makedirs(appdata, exist_ok=True)
    os.makedirs(os.path.join(appdata, "bin"), exist_ok=True)
    os.makedirs(os.path.join(appdata, "logs"), exist_ok=True)
    return appdata

def write_desktop_record_debug_log(msg: str):
    """Escribe un diagnóstico exhaustivo de grabación en tiempo real directamente en el Escritorio del usuario."""
    try:
        dt_path = get_desktop_path()
        log_file = os.path.join(dt_path, "jade_record_debug.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        entry = f"[{timestamp}] {msg}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"Error escribiendo en log de escritorio: {e}")

def log_message(msg: str):
    """Escribe eventos detallados y diagnósticos en el log oficial de Jade en AppData."""
    try:
        log_dir = os.path.join(get_jade_appdata_dir(), "logs")
        log_file = os.path.join(log_dir, "jade_debug.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {msg}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"Error escribiendo en log: {e}")

def set_window_exclude_from_capture(hwnd: int):
    """Aplica la API nativa WDA_EXCLUDEFROMCAPTURE (0x00000011) para que ventanas
    de la app sean totalmente invisibles en videos grabados y screenshots con firmas x64 verificadas."""
    try:
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        user32.SetWindowDisplayAffinity(ctypes.wintypes.HWND(int(hwnd)), WDA_EXCLUDEFROMCAPTURE)
    except Exception as e:
        log_message(f"Error asignando exclusión de captura a la ventana HWND {hwnd}: {e}")

def set_window_click_through(hwnd: int, enable: bool):
    """Activa o desactiva la transparencia de clics (WS_EX_TRANSPARENT) usando SetWindowLongPtrW nativo de 64 bits."""
    try:
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_LAYERED = 0x00080000

        # Resolución binaria compatible con 32 y 64 bits para Windows 10 y Windows 11
        if hasattr(user32, "GetWindowLongPtrW"):
            user32.GetWindowLongPtrW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            get_long = user32.GetWindowLongPtrW
            set_long = user32.SetWindowLongPtrW
        else:
            user32.GetWindowLongW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongW.restype = ctypes.c_long
            user32.SetWindowLongW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_long]
            user32.SetWindowLongW.restype = ctypes.c_long
            get_long = user32.GetWindowLongW
            set_long = user32.SetWindowLongW

        h = ctypes.wintypes.HWND(int(hwnd))
        style = get_long(h, GWL_EXSTYLE)
        if enable:
            set_long(h, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
        else:
            set_long(h, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
    except Exception as e:
        log_message(f"Error ajustando click-through nativo: {e}")

def apply_hdr_tonemap(pixmap: QPixmap) -> QPixmap:
    """Aplica corrección de exposición y mapeo de tonos en RAM con clonación de memoria segura sin desbordamiento de búfer."""
    if not pixmap or pixmap.isNull():
        return pixmap
    try:
        img = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB32)
        w = img.width()
        h = img.height()
        bpl = img.bytesPerLine()
        
        # Extracción segura de bytes sin manipular punteros voidptr sin tamaño fijo
        raw_bytes = img.constBits().asstring(h * bpl)
        if not raw_bytes:
            return pixmap

        lut = bytearray(256)
        for i in range(256):
            norm = i / 255.0
            s_curve = norm * norm * (3.0 - 2.0 * norm)
            val_norm = 0.65 * norm + 0.35 * s_curve
            val_norm = math.pow(val_norm, 0.98)
            val = int(round(val_norm * 255.0))
            lut[i] = max(0, min(255, val))
        lut[255] = 255

        processed_bytes = raw_bytes.translate(lut)
        # Deep copy obligatoria para que QImage adquiera propiedad de memoria propia e independiente
        res_img = QImage(processed_bytes, w, h, bpl, QImage.Format.Format_RGB32).copy()
        return QPixmap.fromImage(res_img)
    except Exception as e:
        log_message(f"Aviso en mapeo de tonos HDR: {e}")
        return pixmap

def is_hdr_fix_enabled() -> bool:
    """Verifica de forma ultrarrápida si el parche HDR está habilitado en la configuración."""
    try:
        cfg_file = os.path.join(get_jade_appdata_dir(), "config.json")
        if os.path.exists(cfg_file):
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("hdr_fix", False))
    except Exception:
        pass
    return False

def capture_full_desktop() -> QPixmap:
    """Captura instantánea de pantalla completa 100% nativa y estable para Windows 10 y Windows 11 (todas las Builds)."""
    screen = QApplication.primaryScreen()
    if not screen:
        return QPixmap()

    # Captura nativa C++ mediante el pipeline oficial de Qt (DirectX/DXGI Desktop Duplication seguro)
    result_pixmap = screen.grabWindow(0)

    # Si la captura primaria tuvo éxito y está en modo HDR, aplicar corrección segura
    if result_pixmap and not result_pixmap.isNull():
        if is_hdr_fix_enabled():
            return apply_hdr_tonemap(result_pixmap)
        return result_pixmap

    # Respaldo de emergencia con firmas nativas x64 estrictas para Windows 11 Build 26300+
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.GetDC.argtypes = [ctypes.wintypes.HWND]
        user32.GetDC.restype = ctypes.wintypes.HDC
        user32.ReleaseDC.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HDC]
        user32.ReleaseDC.restype = ctypes.c_int

        gdi32.CreateCompatibleDC.argtypes = [ctypes.wintypes.HDC]
        gdi32.CreateCompatibleDC.restype = ctypes.wintypes.HDC
        gdi32.CreateCompatibleBitmap.argtypes = [ctypes.wintypes.HDC, ctypes.c_int, ctypes.c_int]
        gdi32.CreateCompatibleBitmap.restype = ctypes.wintypes.HBITMAP
        gdi32.SelectObject.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.HGDIOBJ]
        gdi32.SelectObject.restype = ctypes.wintypes.HGDIOBJ
        gdi32.BitBlt.argtypes = [ctypes.wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.wintypes.DWORD]
        gdi32.BitBlt.restype = ctypes.wintypes.BOOL
        gdi32.GetDIBits.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.HBITMAP, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        gdi32.GetDIBits.restype = ctypes.c_int
        gdi32.DeleteObject.argtypes = [ctypes.wintypes.HGDIOBJ]
        gdi32.DeleteObject.restype = ctypes.wintypes.BOOL
        gdi32.DeleteDC.argtypes = [ctypes.wintypes.HDC]
        gdi32.DeleteDC.restype = ctypes.wintypes.BOOL

        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)

        hdc_screen = user32.GetDC(None)
        if hdc_screen:
            try:
                hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                if hdc_mem:
                    try:
                        hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
                        if hbitmap:
                            try:
                                old_bitmap = gdi32.SelectObject(hdc_mem, hbitmap)
                                raster_op = 0x00CC0020 | 0x40000000  # SRCCOPY | CAPTUREBLT
                                gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, 0, 0, raster_op)
                                gdi32.SelectObject(hdc_mem, old_bitmap)

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
                                bmi.biWidth = width
                                bmi.biHeight = -height
                                bmi.biPlanes = 1
                                bmi.biBitCount = 32
                                bmi.biCompression = 0

                                buffer_length = width * height * 4
                                raw_data = bytearray(buffer_length)
                                c_buffer = (ctypes.c_char * buffer_length).from_buffer(raw_data)

                                if gdi32.GetDIBits(hdc_mem, hbitmap, 0, height, c_buffer, ctypes.byref(bmi), 0):
                                    # Se crea copia profunda (.copy()) para que no quede memoria atada al bytearray local
                                    qimage = QImage(raw_data, width, height, QImage.Format.Format_RGB32).copy()
                                    if not qimage.isNull():
                                        result_pixmap = QPixmap.fromImage(qimage)
                            finally:
                                gdi32.DeleteObject(hbitmap)
                    finally:
                        gdi32.DeleteDC(hdc_mem)
            finally:
                user32.ReleaseDC(None, hdc_screen)
    except Exception as e:
        log_message(f"Fallo en GDI de respaldo: {e}")

    if result_pixmap is None or result_pixmap.isNull():
        result_pixmap = screen.grabWindow(0) if screen else QPixmap()

    if is_hdr_fix_enabled() and result_pixmap and not result_pixmap.isNull():
        result_pixmap = apply_hdr_tonemap(result_pixmap)

    return result_pixmap

def suspend_process(pid: int):
    """Suspende temporalmente la ejecución de un proceso de Windows."""
    try:
        PROCESS_ALL_ACCESS = 0x1F0FFF
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if handle:
            ctypes.windll.ntdll.NtSuspendProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception as e:
        log_message(f"Error suspendiendo proceso PID {pid}: {e}")

def resume_process(pid: int):
    """Reanuda la ejecución de un proceso previamente suspendido en Windows."""
    try:
        PROCESS_ALL_ACCESS = 0x1F0FFF
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if handle:
            ctypes.windll.ntdll.NtResumeProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception as e:
        log_message(f"Error reanudando proceso PID {pid}: {e}")

def ensure_wasapi_script_exists():
    """Crea el script WASAPI dual en C# dentro del directorio de caché de Jade para capturar Sistema (Loopback) o Micrófono nativo."""
    try:
        bin_dir = os.path.join(get_jade_appdata_dir(), "bin")
        ps_script_path = os.path.join(bin_dir, "wasapi_recorder.ps1")

        ps_content = r'''param(
    [string]$OutputFile = "temp_audio.wav",
    [string]$StopFile = "stop_audio.txt",
    [string]$ReadyFile = "ready_audio.txt",
    [string]$GoFile = "go_audio.txt",
    [int]$DataFlow = 0
)

$code = @"
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace WasapiLoopback {
    public class AudioRecorder {
        [Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
        [ComImport]
        private class MMDeviceEnumerator { }

        [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        [ComImport]
        private interface IMMDeviceEnumerator {
            [PreserveSig]
            int EnumAudioEndpoints(int dataFlow, int stateMask, out object devices);

            [PreserveSig]
            int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
        }

        [Guid("D666063F-1587-4E43-81F1-B948E807363F")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        [ComImport]
        private interface IMMDevice {
            [PreserveSig]
            int Activate(ref Guid iid, uint dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
        }

        [Guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        [ComImport]
        private interface IAudioClient {
            [PreserveSig]
            int Initialize(int shareMode, uint streamFlags, long hnsBufferDuration, long hnsPeriodicity, IntPtr pWaveFormat, ref Guid AudioSessionGuid);

            [PreserveSig]
            int GetBufferSize(out uint pNumBufferFrames);

            [PreserveSig]
            int GetStreamLatency(out long phnsLatency);

            [PreserveSig]
            int GetCurrentPadding(out uint pNumPaddingFrames);

            [PreserveSig]
            int IsFormatSupported(int shareMode, IntPtr pWaveFormat, out IntPtr ppClosestMatch);

            [PreserveSig]
            int GetMixFormat(out IntPtr ppDeviceFormat);

            [PreserveSig]
            int GetDevicePeriod(out long phnsDefaultDevicePeriod, out long phnsMinimumDevicePeriod);

            [PreserveSig]
            int Start();

            [PreserveSig]
            int Stop();

            [PreserveSig]
            int Reset();

            [PreserveSig]
            int SetEventHandle(IntPtr eventHandle);

            [PreserveSig]
            int GetService(ref Guid riid, [MarshalAs(UnmanagedType.IUnknown)] out object ppv);
        }

        [Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        [ComImport]
        private interface IAudioCaptureClient {
            [PreserveSig]
            int GetBuffer(out IntPtr pData, out uint pNumFramesToRead, out uint pdwFlags, out ulong pu64DevicePosition, out ulong pu64QPCPosition);

            [PreserveSig]
            int ReleaseBuffer(uint NumFramesRead);

            [PreserveSig]
            int GetNextPacketSize(out uint pNumFramesInNextPacket);
        }

        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        private struct WAVEFORMATEX {
            public ushort wFormatTag;
            public ushort nChannels;
            public uint nSamplesPerSec;
            public uint nAvgBytesPerSec;
            public ushort nBlockAlign;
            public ushort wBitsPerSample;
            public ushort cbSize;
        }

        public static void Record(string wavPath, string stopFilePath, string readyFilePath, string goFilePath, int dataFlow) {
            try {
                var enumerator = (IMMDeviceEnumerator)new MMDeviceEnumerator();
                IMMDevice device = null;
                int hr = enumerator.GetDefaultAudioEndpoint(dataFlow, 1, out device);
                if (hr != 0 || device == null) {
                    hr = enumerator.GetDefaultAudioEndpoint(dataFlow, 0, out device);
                }
                if ((hr != 0 || device == null) && dataFlow == 1) {
                    hr = enumerator.GetDefaultAudioEndpoint(dataFlow, 2, out device);
                }
                if (hr != 0 || device == null) return;

                Guid iidIAudioClient = new Guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2");
                object audioClientObj = null;

                uint[] clsContexts = new uint[] { 23, 1, 4, 7 };
                foreach (uint ctx in clsContexts) {
                    hr = device.Activate(ref iidIAudioClient, ctx, IntPtr.Zero, out audioClientObj);
                    if (hr == 0 && audioClientObj != null) break;
                }

                if (audioClientObj == null) return;
                var audioClient = (IAudioClient)audioClientObj;

                IntPtr pWaveFormat;
                hr = audioClient.GetMixFormat(out pWaveFormat);
                if (hr != 0 || pWaveFormat == IntPtr.Zero) return;

                WAVEFORMATEX wf = (WAVEFORMATEX)Marshal.PtrToStructure(pWaveFormat, typeof(WAVEFORMATEX));
                Guid sessionGuid = Guid.Empty;
                uint streamFlags = (dataFlow == 0) ? 0x00020000u : 0u;
                hr = audioClient.Initialize(0, streamFlags, 10000000, 0, pWaveFormat, ref sessionGuid);
                if (hr != 0) return;

                Guid iidIAudioCaptureClient = new Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317");
                object captureClientObj = null;
                hr = audioClient.GetService(ref iidIAudioCaptureClient, out captureClientObj);
                if (hr != 0 || captureClientObj == null) return;
                var captureClient = (IAudioCaptureClient)captureClientObj;

                hr = audioClient.Start();
                if (hr != 0) return;

                try { File.WriteAllText(readyFilePath, "ready"); } catch {}

                while (!File.Exists(goFilePath) && !File.Exists(stopFilePath)) {
                    Thread.Sleep(5);
                    uint pSize;
                    captureClient.GetNextPacketSize(out pSize);
                    while (pSize > 0) {
                        IntPtr pD; uint nF; uint fl; ulong dp, qp;
                        captureClient.GetBuffer(out pD, out nF, out fl, out dp, out qp);
                        captureClient.ReleaseBuffer(nF);
                        captureClient.GetNextPacketSize(out pSize);
                    }
                }

                if (File.Exists(stopFilePath)) {
                    audioClient.Stop();
                    return;
                }

                using (var fs = new FileStream(wavPath, FileMode.Create, FileAccess.Write))
                using (var bw = new BinaryWriter(fs)) {
                    bw.Write(new char[] { 'R', 'I', 'F', 'F' });
                    bw.Write((int)0);
                    bw.Write(new char[] { 'W', 'A', 'V', 'E' });
                    bw.Write(new char[] { 'f', 'm', 't', ' ' });

                    if (wf.wFormatTag == 0xFFFE) {
                        bw.Write((int)40);
                        byte[] formatBytes = new byte[40];
                        Marshal.Copy(pWaveFormat, formatBytes, 0, 40);
                        bw.Write(formatBytes);
                    } else {
                        bw.Write((int)16);
                        bw.Write((short)wf.wFormatTag);
                        bw.Write((short)wf.nChannels);
                        bw.Write((int)wf.nSamplesPerSec);
                        bw.Write((int)wf.nAvgBytesPerSec);
                        bw.Write((short)wf.nBlockAlign);
                        bw.Write((short)wf.wBitsPerSample);
                    }

                    bw.Write(new char[] { 'd', 'a', 't', 'a' });
                    bw.Write((int)0);

                    uint totalBytesWritten = 0;
                    var sw = System.Diagnostics.Stopwatch.StartNew();

                    while (!File.Exists(stopFilePath)) {
                        Thread.Sleep(5);
                        uint packetSize;
                        captureClient.GetNextPacketSize(out packetSize);

                        if (packetSize > 0) {
                            while (packetSize > 0) {
                                IntPtr pData; uint numFrames; uint flags; ulong devPos, qpcPos;
                                captureClient.GetBuffer(out pData, out numFrames, out flags, out devPos, out qpcPos);

                                if (numFrames > 0) {
                                    int bytesToRead = (int)(numFrames * wf.nBlockAlign);
                                    byte[] pcmBuffer = new byte[bytesToRead];

                                    bool isSilent = ((flags & 2) != 0) || (pData == IntPtr.Zero);
                                    if (!isSilent) {
                                        try {
                                            Marshal.Copy(pData, pcmBuffer, 0, bytesToRead);
                                        } catch {
                                            isSilent = true;
                                        }
                                    }

                                    if (isSilent) {
                                        Array.Clear(pcmBuffer, 0, pcmBuffer.Length);
                                    }

                                    bw.Write(pcmBuffer, 0, pcmBuffer.Length);
                                    totalBytesWritten += (uint)pcmBuffer.Length;
                                }

                                captureClient.ReleaseBuffer(numFrames);
                                captureClient.GetNextPacketSize(out packetSize);
                            }
                        } else {
                            long expectedBytes = (long)(sw.Elapsed.TotalSeconds * wf.nAvgBytesPerSec);
                            long missingBytes = expectedBytes - totalBytesWritten;
                            missingBytes = (missingBytes / wf.nBlockAlign) * wf.nBlockAlign;
                            if (missingBytes > 0) {
                                int chunkSize = (int)Math.Min(missingBytes, 192000);
                                chunkSize = (chunkSize / wf.nBlockAlign) * wf.nBlockAlign;
                                if (chunkSize > 0) {
                                    byte[] silenceBuffer = new byte[chunkSize];
                                    bw.Write(silenceBuffer, 0, silenceBuffer.Length);
                                    totalBytesWritten += (uint)silenceBuffer.Length;
                                }
                            }
                        }
                    }

                    int headerOffset = (wf.wFormatTag == 0xFFFE) ? 40 + 8 : 16 + 8;
                    fs.Seek(4, SeekOrigin.Begin);
                    bw.Write((int)(totalBytesWritten + headerOffset + 12));
                    fs.Seek(headerOffset + 12 + 4, SeekOrigin.Begin);
                    bw.Write((int)totalBytesWritten);
                }

                audioClient.Stop();
            } catch (Exception ex) {
                Console.WriteLine("[WASAPI C#] EXCEPCIÓN: " + ex.ToString());
            }
        }
    }
}
"@

Add-Type -TypeDefinition $code -Language CSharp
[WasapiLoopback.AudioRecorder]::Record($OutputFile, $StopFile, $ReadyFile, $GoFile, $DataFlow)
[Environment]::Exit(0)
'''
        with open(ps_script_path, "w", encoding="utf-8") as f:
            f.write(ps_content)
        log_message("Script WASAPI dual (Sistema/Mic) guardado correctamente en AppData/Jade.")
    except Exception as e:
        log_message(f"Error asegurando script WASAPI: {e}")

def is_valid_ffmpeg_binary(bin_path: str) -> bool:
    """Verifica físicamente si el ejecutable de FFmpeg es un binario Win32/64 válido y funcional."""
    if not bin_path or not os.path.exists(bin_path):
        return False
    try:
        if os.path.getsize(bin_path) < 1000000:
            return False
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        res = subprocess.run(
            [bin_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            creationflags=0x08000000,
            timeout=3
        )
        return res.returncode == 0
    except Exception as e:
        log_message(f"Ejecutable FFmpeg no válido o corrupto en {bin_path}: {e}")
        return False

def get_ffmpeg_path() -> str:
    """Busca el ejecutable de FFmpeg priorizando binarios válidos. Purga automáticamente archivos corruptos (WinError 193)."""
    local_bin = os.path.join(get_jade_appdata_dir(), "bin", "ffmpeg.exe")
    if os.path.exists(local_bin):
        if is_valid_ffmpeg_binary(local_bin):
            return local_bin
        else:
            log_message("Se detectó un ejecutable de FFmpeg corrupto en AppData. Eliminando para reparación...")
            try:
                os.remove(local_bin)
            except Exception:
                pass

    if hasattr(sys, "_MEIPASS"):
        meipass_bin = os.path.join(sys._MEIPASS, "ffmpeg.exe")
        if is_valid_ffmpeg_binary(meipass_bin):
            return meipass_bin

    if getattr(sys, "frozen", False):
        exe_dir_bin = os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe")
        if is_valid_ffmpeg_binary(exe_dir_bin):
            return exe_dir_bin

    res_bin = get_resource_path("ffmpeg.exe")
    if res_bin and is_valid_ffmpeg_binary(res_bin):
        return res_bin

    winget_link = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe")
    if is_valid_ffmpeg_binary(winget_link):
        return winget_link

    winget_packages = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages")
    if os.path.exists(winget_packages):
        try:
            for root, dirs, files in os.walk(winget_packages):
                if "ffmpeg.exe" in files:
                    candidate = os.path.join(root, "ffmpeg.exe")
                    if is_valid_ffmpeg_binary(candidate):
                        return candidate
        except Exception:
            pass

    path = shutil.which("ffmpeg")
    if path and is_valid_ffmpeg_binary(path):
        return path

    return None

def get_system_audio_drivers_and_devices(ffmpeg_executable: str):
    """Detecta micrófonos DirectShow para narración de voz si están activos."""
    dshow_mic_devices = []
    alt_names_dshow = {}

    if ffmpeg_executable and os.path.exists(ffmpeg_executable):
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creation_flags = 0x08000000

            cmd_dshow = [ffmpeg_executable, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            res_dshow = subprocess.run(
                cmd_dshow,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creation_flags
            )

            raw_dshow = ""
            for enc in ["utf-8", "cp1252", "cp850", "latin1"]:
                try:
                    raw_dshow = res_dshow.stderr.decode(enc)
                    if "audio" in raw_dshow.lower():
                        break
                except Exception:
                    continue

            lines = raw_dshow.splitlines()
            in_audio_section = False
            last_dev = None

            for line in lines:
                line_str = line.strip()

                if "DirectShow audio devices" in line_str:
                    in_audio_section = True
                    continue
                if "DirectShow video devices" in line_str:
                    in_audio_section = False
                    continue

                if in_audio_section:
                    if "Alternative name" in line_str:
                        matches = re.findall(r'"([^"]+)"', line_str)
                        if last_dev and matches:
                            alt_names_dshow[last_dev] = matches[0]
                        continue

                    matches = re.findall(r'"([^"]+)"', line_str)
                    if matches:
                        dev_name = matches[0]
                        dev_lower = dev_name.lower()

                        if not dev_name.startswith("@") and not any(bad in dev_lower for bad in ["spdif", "widi", "midi"]):
                            if any(k in dev_lower for k in ["mic", "micrófono", "microphone", "headset", "entrada", "input"]):
                                if dev_name not in dshow_mic_devices:
                                    dshow_mic_devices.append(dev_name)
                                    last_dev = dev_name

        except Exception as e:
            log_message(f"Error en escaneo DirectShow: {e}")

    return dshow_mic_devices, alt_names_dshow

def check_nvenc_support(ffmpeg_executable: str):
    """Comprueba si NVENC responde correctamente en el hardware."""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creation_flags = 0x08000000

        cmd = [
            ffmpeg_executable, "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
            "-c:v", "h264_nvenc",
            "-f", "null", "-"
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            startupinfo=startupinfo,
            creationflags=creation_flags
        )
        if res.returncode == 0:
            return True, "NVENC por hardware verificado y completamente funcional."
        else:
            err_text = res.stderr
            if "Driver does not support the required nvenc API version" in err_text or "minimum required Nvidia driver" in err_text:
                return False, "REQUIERE_FFMPEG_COMPATIBLE"
            return False, f"Prueba NVENC falló: {err_text[:200]}"
    except Exception as e:
        return False, f"Excepción comprobando NVENC: {e}"

from PyQt6.QtGui import QImageReader

_ACTIVE_WORKER_SIGNALS = set()

class WorkerSignals(QObject):
    finished = pyqtSignal(str, QPixmap)
    _image_ready = pyqtSignal(str, QImage)

    def __init__(self):
        super().__init__()
        self._image_ready.connect(self._deliver_pixmap)
        _ACTIVE_WORKER_SIGNALS.add(self)

    def _deliver_pixmap(self, media_path: str, img: QImage):
        try:
            if not img.isNull():
                pix = QPixmap.fromImage(img)
                if len(_RAM_THUMB_CACHE) >= _MAX_RAM_THUMB_CACHE:
                    _RAM_THUMB_CACHE.popitem(last=False)
                _RAM_THUMB_CACHE[media_path] = pix
                self.finished.emit(media_path, pix)
            else:
                self.finished.emit(media_path, QPixmap())
        except Exception as e:
            log_message(f"Error procesando miniatura en hilo UI: {e}")
            self.finished.emit(media_path, QPixmap())
        finally:
            _ACTIVE_WORKER_SIGNALS.discard(self)

class ThumbnailRunnable(QRunnable):
    """Tarea ejecutable en QThreadPool para generar miniaturas asíncronas en alta definición con consumo mínimo de RAM."""
    def __init__(self, media_path: str):
        super().__init__()
        self.media_path = media_path
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            import hashlib
            cache_dir = os.path.join(get_jade_appdata_dir(), "cache", "thumbs_hd")
            os.makedirs(cache_dir, exist_ok=True)

            media_hash = hashlib.md5(self.media_path.encode("utf-8")).hexdigest()
            thumb_path = os.path.join(cache_dir, f"{media_hash}.jpg")

            if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                img = QImage(thumb_path)
                if not img.isNull():
                    self.signals._image_ready.emit(self.media_path, img)
                    return

            is_video = self.media_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'))
            if is_video:
                ffmpeg_bin = get_ffmpeg_path()
                if ffmpeg_bin and os.path.exists(ffmpeg_bin):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                    cmd = [
                        ffmpeg_bin, "-threads", "1", "-ss", "00:00:00.000", "-i", self.media_path,
                        "-vf", "scale=420:-1", "-vframes", "1", "-q:v", "3", thumb_path, "-y"
                    ]
                    subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        startupinfo=startupinfo,
                        creationflags=0x08000000 | 0x00000040,
                        timeout=4
                    )
            else:
                reader = QImageReader(self.media_path)
                reader.setAutoTransform(True)
                orig_size = reader.size()
                img = None
                if orig_size.isValid() and orig_size.width() > 0 and orig_size.height() > 0:
                    scaled_size = orig_size.scaled(420, 300, Qt.AspectRatioMode.KeepAspectRatio)
                    reader.setScaledSize(scaled_size)
                    img = reader.read()

                if img is None or img.isNull():
                    img = QImage(self.media_path)
                    if not img.isNull():
                        img = img.scaled(420, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

                if img is not None and not img.isNull():
                    img.save(thumb_path, "JPG", 88)
                    del img

            if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                img = QImage(thumb_path)
                if not img.isNull():
                    self.signals._image_ready.emit(self.media_path, img)
                    return
        except Exception as e:
            log_message(f"Error generando miniatura asíncrona: {e}")

        self.signals._image_ready.emit(self.media_path, QImage())

from collections import OrderedDict
_RAM_THUMB_CACHE = OrderedDict()
_MAX_RAM_THUMB_CACHE = 120

def get_cached_media_thumbnail(media_path: str) -> QPixmap:
    """Obtiene ultra-rápidamente la miniatura desde RAM o disco evitando bloqueos y fugas de memoria con LRU."""
    if media_path in _RAM_THUMB_CACHE:
        _RAM_THUMB_CACHE.move_to_end(media_path)
        return _RAM_THUMB_CACHE[media_path]
    try:
        import hashlib
        cache_dir = os.path.join(get_jade_appdata_dir(), "cache", "thumbs_hd")
        media_hash = hashlib.md5(media_path.encode("utf-8")).hexdigest()
        thumb_path = os.path.join(cache_dir, f"{media_hash}.jpg")

        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            img = QImage(thumb_path)
            if not img.isNull():
                pix = QPixmap.fromImage(img)
                if len(_RAM_THUMB_CACHE) >= _MAX_RAM_THUMB_CACHE:
                    _RAM_THUMB_CACHE.popitem(last=False)
                _RAM_THUMB_CACHE[media_path] = pix
                return pix
    except Exception:
        pass
    return QPixmap()

def overlay_play_icon(pixmap: QPixmap) -> QPixmap:
    """Añade un botón de reproducción flotante semi-transparente sobre la miniatura del video."""
    if pixmap.isNull():
        return pixmap
    result = pixmap.copy()
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx, cy = result.width() // 2, result.height() // 2
    r = min(result.width(), result.height()) // 6
    r = max(18, min(34, r))

    painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
    painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
    painter.drawEllipse(QPoint(cx, cy), r, r)

    path = QPainterPath()
    tri_w = r * 0.7
    tri_h = r * 0.8
    path.moveTo(cx - tri_w * 0.35, cy - tri_h * 0.5)
    path.lineTo(cx + tri_w * 0.65, cy)
    path.lineTo(cx - tri_w * 0.35, cy + tri_h * 0.5)
    path.closeSubpath()

    painter.setBrush(QBrush(QColor(255, 255, 255)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(path)
    painter.end()

    return result

class FFmpegInstallerThread(QThread):
    """Descarga e instala automáticamente el motor FFmpeg optimizado para Jade en AppData/Local/Jade/bin."""
    status_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            import urllib.request
            import zipfile
            import ssl

            self.status_updated.emit("Iniciando descarga del motor gráfico FFmpeg 7.0.2...")
            log_message("Descargando compilado de FFmpeg 7.0.2 para Jade...")

            local_dir = os.path.join(get_jade_appdata_dir(), "bin")
            zip_path = os.path.join(local_dir, "ffmpeg.zip")
            url = "https://github.com/GyanD/codexffmpeg/releases/download/7.0.2/ffmpeg-7.0.2-essentials_build.zip"

            try:
                ssl_context = ssl._create_unverified_context()
                opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))
                urllib.request.install_opener(opener)
            except Exception:
                pass

            def report_progress(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int(block_num * block_size * 100 / total_size)
                    percent = min(100, percent)
                    descargado_mb = (block_num * block_size) / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    self.status_updated.emit(f"Descargando Motor GPU... {percent}% ({descargado_mb:.1f} MB / {total_mb:.1f} MB)")

            urllib.request.urlretrieve(url, zip_path, reporthook=report_progress)
            self.status_updated.emit("Descarga completada. Descomprimiendo e instalando...")

            extracted_ffmpeg = None
            extracted_subpath = None

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    if member.endswith("ffmpeg.exe"):
                        zip_ref.extract(member, local_dir)
                        extracted_ffmpeg = os.path.join(local_dir, member)
                        extracted_subpath = member
                        break

            if extracted_ffmpeg and os.path.exists(extracted_ffmpeg):
                target_path = os.path.join(local_dir, "ffmpeg.exe")
                if os.path.exists(target_path):
                    try: os.remove(target_path)
                    except Exception: pass

                shutil.move(extracted_ffmpeg, target_path)

                try:
                    os.remove(zip_path)
                    if extracted_subpath:
                        top_subfolder = extracted_subpath.split('/')[0]
                        shutil.rmtree(os.path.join(local_dir, top_subfolder), ignore_errors=True)
                except Exception:
                    pass

                log_message("FFmpeg 7.0.2 configurado con éxito en Jade.")
                self.finished.emit(True, "¡Módulo GPU configurado exitosamente para Jade!")
            else:
                self.finished.emit(False, "No se encontró el ejecutable ffmpeg.exe en el archivo Zip.")

        except Exception as e:
            log_message(f"Excepción instalando FFmpeg: {e}")
            self.finished.emit(False, f"Error al configurar motor de GPU: {str(e)}")


class VLCInstallerThread(QThread):
    """Descarga e instala automáticamente el motor portátil LibVLC para Jade en AppData/Roaming/Jade/bin/vlc con validación estricta de binarios."""
    status_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            import urllib.request
            import zipfile
            import ssl

            self.status_updated.emit("Iniciando descarga de componentes portátiles LibVLC...")
            log_message("Descargando componentes portátiles LibVLC para Jade...")

            vlc_dir = os.path.join(get_jade_appdata_dir(), "bin", "vlc")
            os.makedirs(vlc_dir, exist_ok=True)
            zip_path = os.path.join(get_jade_appdata_dir(), "bin", "vlc.zip")

            download_urls = [
                "https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.zip",
                "https://download.videolan.org/pub/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip",
                "https://ftp.osuosl.org/pub/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip"
            ]

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }

            try:
                ssl_ctx = ssl._create_unverified_context()
            except Exception:
                ssl_ctx = None

            def report_progress(downloaded, total):
                if total > 0:
                    percent = int(downloaded * 100 / total)
                    percent = min(100, percent)
                    d_mb = downloaded / (1024 * 1024)
                    t_mb = total / (1024 * 1024)
                    self.status_updated.emit(f"Descargando Motor VLC... {percent}% ({d_mb:.1f} MB / {t_mb:.1f} MB)")

            downloaded_ok = False
            for url in download_urls:
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, context=ssl_ctx, timeout=120) as resp, open(zip_path, "wb") as out_f:
                        total_size = int(resp.headers.get("Content-Length", 0))
                        chunk_size = 65536
                        downloaded_bytes = 0
                        while True:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded_bytes += len(chunk)
                            report_progress(downloaded_bytes, total_size)

                    if os.path.exists(zip_path) and os.path.getsize(zip_path) > 10000000:
                        downloaded_ok = True
                        break
                except Exception as e_dl:
                    log_message(f"Fallo descargando LibVLC desde {url}: {e_dl}")
                    if os.path.exists(zip_path):
                        try: os.remove(zip_path)
                        except Exception: pass

            if not downloaded_ok:
                self.finished.emit(False, "No se pudo descargar el archivo comprimido de LibVLC desde los servidores oficiales.")
                return

            self.status_updated.emit("Descarga completada. Extrayendo archivos portátiles de LibVLC...")

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    parts = member.split('/')
                    if len(parts) > 1 and parts[0].startswith("vlc-"):
                        rel_path = "/".join(parts[1:])
                        if not rel_path:
                            continue
                        target_file = os.path.join(vlc_dir, rel_path)
                        if member.endswith('/'):
                            os.makedirs(target_file, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_file), exist_ok=True)
                            with zip_ref.open(member) as source, open(target_file, "wb") as target:
                                shutil.copyfileobj(source, target)

            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception:
                pass

            target_dll = os.path.join(vlc_dir, "libvlc.dll")
            if not os.path.exists(target_dll):
                self.finished.emit(False, "Extracción fallida: no se encontró libvlc.dll en el directorio de instalación.")
                return

            setup_ok = find_and_setup_vlc()
            if setup_ok:
                log_message("LibVLC configurado y verificado con éxito en Jade.")
                self.finished.emit(True, "¡Motor VLC configurado y verificado exitosamente para Jade!")
            else:
                self.finished.emit(False, "Se extrajeron los archivos, pero el sistema no pudo vincular la biblioteca DLL de VLC.")

        except Exception as e:
            log_message(f"Excepción instalando LibVLC: {e}")
            self.finished.emit(False, f"Error al configurar motor VLC: {str(e)}")

DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_MICA_EFFECT = 1029
DWMWA_SYSTEMBACKDROP_TYPE = 38

def enable_win11_effects(hwnd: int, dark_mode=True, backdrop_type=2):
    """Aplica dinámicamente modo oscuro y efectos Mica adaptados a cada versión de Windows 10 y Windows 11 (21H2 a 26H2)."""
    try:
        if not hwnd:
            return

        dwmapi = ctypes.windll.dwmapi
        dwmapi.DwmSetWindowAttribute.argtypes = [
            ctypes.wintypes.HWND, ctypes.wintypes.DWORD, ctypes.c_void_p, ctypes.wintypes.DWORD
        ]
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

        h = ctypes.wintypes.HWND(int(hwnd))
        build_number = sys.getwindowsversion().build
        val_dark = ctypes.c_int(1 if dark_mode else 0)

        # 1. Modo Oscuro en barra de título según la versión de Windows
        if build_number >= 19041:
            # Windows 10 (2004, 20H2, 21H1, 21H2, 22H2) y todo Windows 11
            dwmapi.DwmSetWindowAttribute(
                h, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val_dark), ctypes.sizeof(val_dark)
            )
        elif build_number >= 17763:
            # Windows 10 (1809, 1903, 1909)
            dwmapi.DwmSetWindowAttribute(
                h, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(val_dark), ctypes.sizeof(val_dark)
            )

        # 2. Efectos de translucidez (Mica / Acrylic) adaptados por generación de Windows 11
        if build_number >= 22621:
            # Windows 11 (22H2, 23H2, 24H2, 25H2, 26H2) - API oficial SystemBackdropType
            val_backdrop = ctypes.c_int(int(backdrop_type) if dark_mode else 1)
            dwmapi.DwmSetWindowAttribute(
                h, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(val_backdrop), ctypes.sizeof(val_backdrop)
            )
        elif build_number >= 22000:
            # Windows 11 21H2 (Build inicial 22000) - API MicaEffect
            val_mica = ctypes.c_int(1 if dark_mode else 0)
            dwmapi.DwmSetWindowAttribute(
                h, DWMWA_MICA_EFFECT, ctypes.byref(val_mica), ctypes.sizeof(val_mica)
            )
        # En Windows 10 no se aplican llamadas a atributos de Mica inexistentes
    except Exception as e:
        log_message(f"Aviso aplicando efectos DWM compatibles: {e}")

def get_documents_path() -> str:
    """Obtiene dinámicamente la ruta de la carpeta Documentos del usuario para guardar archivos de texto."""
    docs_path = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            raw_path, _ = winreg.QueryValueEx(key, "Personal")
            docs_path = os.path.expandvars(raw_path)
    except Exception:
        pass

    if not docs_path or not os.path.exists(docs_path):
        user_home = os.path.expanduser("~")
        candidates = [
            os.path.join(user_home, "OneDrive", "Documentos"),
            os.path.join(user_home, "OneDrive", "Documents"),
            os.path.join(user_home, "Documentos"),
            os.path.join(user_home, "Documents"),
        ]
        docs_path = user_home
        for candidate in candidates:
            if os.path.exists(candidate):
                docs_path = candidate
                break

    jade_docs = os.path.join(docs_path, "Jade_Historial_Texto")
    os.makedirs(jade_docs, exist_ok=True)
    return jade_docs

class TextHistoryManager:
    """Gestiona el almacenamiento de textos copiados guardando directamente archivos .txt en la carpeta Documentos/Jade_Historial_Texto."""
    def __init__(self):
        self.docs_dir = get_documents_path()
        self._cache = None

    @property
    def entries(self):
        return self.load_entries()

    def load_entries(self):
        if self._cache is not None:
            return self._cache

        entries_list = []
        if not os.path.exists(self.docs_dir):
            self._cache = entries_list
            return entries_list

        try:
            files = [f for f in os.listdir(self.docs_dir) if f.lower().endswith(".txt")]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.docs_dir, x)), reverse=True)

            for fname in files[:300]:
                fpath = os.path.join(self.docs_dir, fname)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                
                note_val = ""
                note_file = fpath + ".meta"
                if os.path.exists(note_file):
                    try:
                        with open(note_file, "r", encoding="utf-8") as nf:
                            note_val = nf.read().strip()
                    except Exception:
                        pass

                is_pinned = os.path.exists(fpath + ".pinned")
                pinned_time = 0.0
                if is_pinned:
                    try:
                        pinned_time = os.path.getmtime(fpath + ".pinned")
                    except Exception:
                        pinned_time = mtime.timestamp()

                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
                except Exception:
                    text_content = ""

                entries_list.append({
                    "id": fname,
                    "filepath": fpath,
                    "timestamp": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    "date": mtime.strftime("%Y-%m-%d"),
                    "display_time": mtime.strftime("%I:%M %p"),
                    "text": text_content,
                    "note": note_val,
                    "pinned": is_pinned,
                    "pinned_time": pinned_time
                })
        except Exception as e:
            log_message(f"Error cargando archivos de texto desde Documentos: {e}")

        self._cache = entries_list
        return entries_list

    def add_entry(self, text: str, note: str = ""):
        if not text or not text.strip():
            return

        MAX_TEXT_LEN = 25000
        clean_text = text.strip()
        if len(clean_text) > MAX_TEXT_LEN:
            clean_text = clean_text[:MAX_TEXT_LEN] + "\n\n... [Texto truncado por Jade por superar el límite de 25,000 caracteres]"

        current_entries = self.load_entries()
        if current_entries and current_entries[0].get("text") == clean_text:
            return

        now = datetime.now()
        fname = f"Texto_{now.strftime('%Y%m%d_%H%M%S_%f')}.txt"
        fpath = os.path.join(self.docs_dir, fname)

        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(clean_text)

            if note.strip():
                with open(fpath + ".meta", "w", encoding="utf-8") as nf:
                    nf.write(note.strip())
            self._cache = None
        except Exception as e:
            log_message(f"Error guardando archivo .txt en Documentos: {e}")

    def update_note(self, entry_id: str, new_note: str):
        fpath = os.path.join(self.docs_dir, entry_id)
        meta_path = fpath + ".meta"
        try:
            if new_note.strip():
                with open(meta_path, "w", encoding="utf-8") as nf:
                    nf.write(new_note.strip())
            else:
                if os.path.exists(meta_path):
                    os.remove(meta_path)
            self._cache = None
        except Exception as e:
            log_message(f"Error actualizando nota de texto: {e}")

    def toggle_pinned(self, entry_id: str):
        fpath = os.path.join(self.docs_dir, entry_id)
        pinned_path = fpath + ".pinned"
        try:
            if os.path.exists(pinned_path):
                os.remove(pinned_path)
            else:
                with open(pinned_path, "w", encoding="utf-8") as pf:
                    pf.write("pinned")
            self._cache = None
        except Exception as e:
            log_message(f"Error alternando estado fijado de la nota: {e}")

    def delete_entry(self, entry_id: str):
        fpath = os.path.join(self.docs_dir, entry_id)
        meta_path = fpath + ".meta"
        pinned_path = fpath + ".pinned"
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
            if os.path.exists(meta_path):
                os.remove(meta_path)
            if os.path.exists(pinned_path):
                os.remove(pinned_path)
            self._cache = None
        except Exception as e:
            log_message(f"Error eliminando archivo .txt: {e}")

    def clear_cache(self):
        try:
            if os.path.exists(self.docs_dir):
                for fname in os.listdir(self.docs_dir):
                    if fname.lower().endswith(".txt") or fname.lower().endswith(".txt.meta") or fname.lower().endswith(".txt.pinned"):
                        try:
                            os.remove(os.path.join(self.docs_dir, fname))
                        except Exception:
                            pass
            self._cache = None
        except Exception as e:
            log_message(f"Error limpiando carpeta de textos en Documentos: {e}")

    def add_pinned_entry(self, text: str, note: str = "Nota anclada"):
        if not text or not text.strip():
            return None
        MAX_TEXT_LEN = 25000
        clean_text = text.strip()
        if len(clean_text) > MAX_TEXT_LEN:
            clean_text = clean_text[:MAX_TEXT_LEN] + "\n\n... [Texto truncado por Jade por superar el límite de 25,000 caracteres]"
        now = datetime.now()
        fname = f"Texto_{now.strftime('%Y%m%d_%H%M%S_%f')}.txt"
        fpath = os.path.join(self.docs_dir, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(clean_text)
            if note.strip():
                with open(fpath + ".meta", "w", encoding="utf-8") as nf:
                    nf.write(note.strip())
            with open(fpath + ".pinned", "w", encoding="utf-8") as pf:
                pf.write("pinned")
            self._cache = None
            return fname
        except Exception as e:
            log_message(f"Error guardando nota anclada en Documentos: {e}")
            return None

    def touch_pinned_entry(self, entry_id: str):
        fpath = os.path.join(self.docs_dir, entry_id)
        pinned_path = fpath + ".pinned"
        try:
            if os.path.exists(pinned_path):
                os.utime(pinned_path, None)
                self._cache = None
        except Exception as e:
            log_message(f"Error actualizando prioridad de nota anclada: {e}")

def detect_windows_system_theme() -> str:
    """Detecta dinámicamente si el sistema Windows está en modo claro u oscuro."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "claro" if value == 1 else "oscuro"
    except Exception:
        return "oscuro"

class ConfigManager:
    """Gestiona la configuración persistente en AppData/Local/Jade/config.json."""
    DEFAULT_CONFIG = {
        "images_folder": os.path.join(os.path.expanduser("~"), "Pictures", "Jade"),
        "videos_folder": os.path.join(os.path.expanduser("~"), "Videos", "Jade"),
        "audios_folder": os.path.join(os.path.expanduser("~"), "Music", "Jade"),
        "hotkey": "PrtScn",
        "hotkey_capture": "PrtScn",
        "hotkey_record": "Ctrl+Shift+R",
        "hotkey_record_audio": "Ctrl+Shift+A",
        "hotkey_pause": "Ctrl+Shift+P",
        "hotkey_text_history": "Ctrl+Shift+H",
        "hotkey_media_gallery": "Ctrl+Shift+G",
        "hotkey_toggle_hotkeys": "Ctrl+Shift+X",
        "hotkey_draw_arrow": "Ctrl+Shift+D",
        "hotkey_clear_draw": "Ctrl+Shift+E",
        "hotkey_translate": "Ctrl+Shift+T",
        "hotkey_quick_translator": "Ctrl+Shift+Z",
        "hotkey_game_mode": "Ctrl+Shift+Enter",
        "hotkey_pin_note": "Ctrl+Shift+C",
        "translate_from_lang": "en",
        "translate_to_lang": "es",
        "draw_color": "#E81123",
        "override_printscreen": True,
        "card_position": "bottom_left",
        "last_gallery_tab": 0,
        "autostart": False,
        "theme": "sistema",
        "mica_effect": True,
        "auto_copy_clipboard": True,
        "play_sound": True,
        "hide_on_capture": False,
        "hdr_fix": False,
        "use_nvenc": True,
        "record_system_audio": True,
        "record_mic_audio": False,
        "fps": "auto"
    }

    def __init__(self):
        self.config_dir = get_jade_appdata_dir()
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.data = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    for k, v in self.DEFAULT_CONFIG.items():
                        config.setdefault(k, v)
                    if config.get("override_printscreen", True) and config.get("hotkey_capture") in ("F11", "Ctrl+Shift+S"):
                        config["hotkey_capture"] = "PrtScn"
                    if config.get("hotkey_clear_draw") == "Ctrl+Shift+C":
                        config["hotkey_clear_draw"] = "Ctrl+Shift+E"
                    return config
            except Exception:
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando configuración: {e}")

    def get(self, key, default=None):
        fallback = default if default is not None else self.DEFAULT_CONFIG.get(key)
        return self.data.get(key, fallback)

    def set(self, key, value):
        self.data[key] = value
        self.save_config()

def override_windows_printscreen_key(enable: bool = True):
    """Desactiva la herramienta de recortes nativa de Windows (ms-screenclip) en Win 10/11 para que Jade tome control de la tecla Impr Pant (PrtScn)."""
    try:
        key_path = r"Control Panel\Keyboard"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            value = 0 if enable else 1
            winreg.SetValueEx(key, "PrintScreenKeyForSnippingEnabled", 0, winreg.REG_DWORD, value)
        log_message(f"Registro de Windows ajustado: PrintScreenKeyForSnippingEnabled = {value}")
    except Exception as e:
        log_message(f"Error ajustando registro de la tecla Impr Pant: {e}")

class AutostartManager:
    """Administra el inicio automático con Windows 10/11 para Jade garantizando compatibilidad con StartupApproved."""
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APPROVED_PATH = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
    APP_NAME = "Jade"

    @classmethod
    def set_autostart(cls, enable: bool):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cls.REG_PATH, 0, winreg.KEY_SET_VALUE
            )
            if enable:
                if getattr(sys, 'frozen', False):
                    target_exe = os.path.abspath(sys.executable)
                    exe_path = f'"{target_exe}" --minimized'
                else:
                    target_script = os.path.abspath(sys.argv[0])
                    exe_path = f'"{sys.executable}" "{target_script}" --minimized'
                winreg.SetValueEx(key, cls.APP_NAME, 0, winreg.REG_SZ, exe_path)

                # Habilitar en StartupApproved para Windows 10 y Windows 11
                try:
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cls.APPROVED_PATH) as app_key:
                        winreg.SetValueEx(app_key, cls.APP_NAME, 0, winreg.REG_BINARY, b'\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                except Exception:
                    pass
            else:
                try:
                    winreg.DeleteValue(key, cls.APP_NAME)
                except FileNotFoundError:
                    pass
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.APPROVED_PATH, 0, winreg.KEY_SET_VALUE) as app_key:
                        winreg.DeleteValue(app_key, cls.APP_NAME)
                except Exception:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            log_message(f"Error en configuración de inicio automático: {e}")
            return False

class CountdownOverlay(QWidget):
    """Superposición transparente no bloqueante para cuenta regresiva (3, 2, 1, ¡ACCIÓN!)."""
    finished = pyqtSignal()

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

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_countdown)

    def start(self):
        self.count = 3
        self.show()

        try:
            hwnd = int(self.winId())
            set_window_exclude_from_capture(hwnd)
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, -20)
            user32.SetWindowLongW(hwnd, -20, style | 0x00000020 | 0x00080000)
            SWP_NOACTIVATE = 0x0010
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception as e:
            print(f"Error asignando estilo transparente nativo: {e}")

        self.update()
        self.timer.start()

    def _update_countdown(self):
        self.count -= 1
        if self.count > 0:
            self.update()
        elif self.count == 0:
            self.update()
        else:
            self.timer.stop()
            self.close()
            self.finished.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.count > 0:
            text = str(self.count)
            color = QColor(0, 120, 212)
        else:
            text = "¡ACCIÓN!"
            color = QColor(16, 124, 65)

        cx, cy = self.width() // 2, self.height() // 2
        card_w, card_h = 220, 140
        card_rect = QRectF(cx - card_w / 2.0, cy - card_h / 2.0, float(card_w), float(card_h))

        path = QPainterPath()
        path.addRoundedRect(card_rect, 24.0, 24.0)

        painter.fillPath(path, QColor(18, 18, 18, 220))

        pen = QPen(color, 3)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.setPen(QPen(QColor(255, 255, 255)))
        if self.count > 0:
            painter.setFont(QFont("Segoe UI Variable Display", 54, QFont.Weight.Bold))
        else:
            painter.setFont(QFont("Segoe UI Variable Display", 24, QFont.Weight.Bold))

        painter.drawText(card_rect, Qt.AlignmentFlag.AlignCenter, text)

try:
    from PyQt6.QtSvg import QSvgRenderer
    HAS_SVG_SUPPORT = True
except ImportError:
    HAS_SVG_SUPPORT = False

def get_adaptive_theme_color(override_hex: str = None) -> str:
    """Calcula el color hexadecimal contrastante idóneo según el tema oscuro o claro activo."""
    if override_hex and override_hex not in ("adaptive", "auto", ""):
        return override_hex
    try:
        tm = ThemeManager.get_instance()
        return "#FFFFFF" if tm.is_dark else "#1A1A1A"
    except Exception:
        try:
            return "#1A1A1A" if detect_windows_system_theme() == "claro" else "#FFFFFF"
        except Exception:
            return "#FFFFFF"

def get_minimalist_svg_icon(icon_type: str, color_hex: str = None, size_px: int = 18) -> QIcon:
    """Genera dinámicamente un QIcon SVG vectorial de alta resolución totalmente adaptativo al tema."""
    final_color = get_adaptive_theme_color(color_hex)
    svgs = {
        "copy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
        "ocr": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V4h3"></path><path d="M17 4h3v3"></path><path d="M20 17v3h-3"></path><path d="M7 20H4v-3"></path><line x1="7" y1="8" x2="17" y2="8"></line><line x1="7" y1="12" x2="17" y2="12"></line><line x1="7" y1="16" x2="13" y2="16"></line></svg>',
        "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>',
        "folder": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
        "move": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 9 2 12 5 15"></polyline><polyline points="9 5 12 2 15 5"></polyline><polyline points="15 19 12 22 9 19"></polyline><polyline points="19 9 22 12 19 15"></polyline><line x1="2" y1="12" x2="22" y2="12"></line><line x1="12" y1="2" x2="12" y2="22"></line></svg>',
        "rename": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>',
        "delete": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>',
        "trash": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>',
        "play": '<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"></polygon></svg>',
        "pause": '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"></rect><rect x="14" y="4" width="4" height="16" rx="1"></rect></svg>',
        "stop": '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2"></rect></svg>',
        "record": '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"></circle></svg>',
        "audio": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>',
        "video": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>',
        "image": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
        "gallery_pro": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="14.31" y1="8" x2="20.05" y2="17.94"></line><line x1="9.69" y1="8" x2="21.17" y2="8"></line><line x1="7.38" y1="12" x2="13.12" y2="2.06"></line><line x1="9.69" y1="16" x2="3.95" y2="6.06"></line><line x1="14.31" y1="16" x2="2.83" y2="16"></line><line x1="16.62" y1="12" x2="10.88" y2="21.94"></line></svg>',
        "settings": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>',
        "game": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="12" x2="10" y2="12"></line><line x1="8" y1="10" x2="8" y2="14"></line><line x1="15" y1="13" x2="15.01" y2="13"></line><line x1="18" y1="11" x2="18.01" y2="11"></line><rect x="2" y="6" width="20" height="12" rx="6"></rect></svg>',
        "globe": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>',
        "swap": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 5h18"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 19H3"></path></svg>',
        "close": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
        "pin": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"></line><path d="M5 17h14v-2l-2-3V5a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7l-2 3v2z"></path></svg>',
        "unpin": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="2" y1="2" x2="22" y2="22"></line><line x1="12" y1="17" x2="12" y2="22"></line><path d="M9 9v3l-2 3v2h10m-3-7V5a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1"></path></svg>',
        "plus": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
        "clock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
        "calendar": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>',
        "detail": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>',
        "mosaic": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>',
        "check": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        "warning": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        "lightning": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
        "gpu": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="15" x2="23" y2="15"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="15" x2="4" y2="15"></line></svg>',
        "chevron_down": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
        "tag": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>',
        "note": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>',
        "keyboard": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"></rect><line x1="6" y1="8" x2="6" y2="8"></line><line x1="10" y1="8" x2="10" y2="8"></line><line x1="14" y1="8" x2="14" y2="8"></line><line x1="18" y1="8" x2="18" y2="8"></line><line x1="6" y1="12" x2="6" y2="12"></line><line x1="10" y1="12" x2="10" y2="12"></line><line x1="14" y1="12" x2="14" y2="12"></line><line x1="18" y1="12" x2="18" y2="12"></line><line x1="7" y1="16" x2="17" y2="16"></line></svg>',
        "star": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>',
        "sparkle": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 14.5 9.5 22 12 14.5 14.5 12 22 9.5 14.5 2 12 9.5 9.5 12 2"></polygon></svg>',
        "edit_pen": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>',
        "tools": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>'
    }

    raw_xml = svgs.get(icon_type, svgs["copy"]).replace("currentColor", final_color)
    if HAS_SVG_SUPPORT:
        try:
            renderer = QSvgRenderer(raw_xml.encode("utf-8"))
            pixmap = QPixmap(size_px, size_px)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
        except Exception:
            pass
    return QIcon()

def get_minimalist_svg_pixmap(icon_type: str, color_hex: str = None, width: int = 18, height: int = 18) -> QPixmap:
    """Genera dinámicamente un QPixmap a partir de un ícono SVG vectorial adaptativo."""
    icon = get_minimalist_svg_icon(icon_type, color_hex, max(width, height))
    return icon.pixmap(width, height)

class FloatingControlBar(QWidget):
    """Barra flotante compacta durante la grabación, totalmente invisible en videos grabados y sin robo de foco."""
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_paused = False
        self.seconds_elapsed = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.init_ui()
        ThemeManager.get_instance().register_child(self)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_timer)

        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            self.move(sg.x() + (sg.width() - self.width()) // 2, sg.y() + 20)

        self._drag_pos = None

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        p = ThemePalette.get(is_dark)
        if hasattr(self, "container") and self.container:
            bg = "rgba(22, 22, 22, 0.94)" if is_dark else "rgba(255, 255, 255, 0.96)"
            border = "rgba(255, 255, 255, 0.18)" if is_dark else "rgba(0, 0, 0, 0.15)"
            self.container.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 20px;
                }}
            """)
        if hasattr(self, "lbl_time") and self.lbl_time:
            self.lbl_time.setStyleSheet(f"color: {p['text_primary']};")
        if hasattr(self, "btn_pause") and self.btn_pause:
            icon_color = "#FFFFFF" if is_dark else "#0F172A"
            btn_bg = "rgba(255, 255, 255, 0.12)" if is_dark else "rgba(0, 0, 0, 0.08)"
            self.btn_pause.setStyleSheet(f"background-color: {btn_bg}; border: none; border-radius: 12px;")
            current_icon = "play" if getattr(self, "is_paused", False) else "pause"
            self.btn_pause.setIcon(get_minimalist_svg_icon(current_icon, icon_color, 16))
        if hasattr(self, "btn_settings") and self.btn_settings:
            icon_color = "#FFFFFF" if is_dark else "#0F172A"
            btn_bg = "rgba(255, 255, 255, 0.12)" if is_dark else "rgba(0, 0, 0, 0.08)"
            self.btn_settings.setStyleSheet(f"background-color: {btn_bg}; border: none; border-radius: 12px;")
            self.btn_settings.setIcon(get_minimalist_svg_icon("settings", icon_color, 16))

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            set_window_exclude_from_capture(hwnd)
            SWP_NOACTIVATE = 0x0010
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass
        self.apply_theme()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame()
        container = self.container
        container.setStyleSheet("""
            QFrame {
                background-color: rgba(22, 22, 22, 0.94);
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 20px;
            }
        """)
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(14, 6, 14, 6)
        c_layout.setSpacing(10)

        self.rec_icon_label = QLabel()
        self.rec_icon_label.setPixmap(get_minimalist_svg_pixmap("record", "#FF3B30", 12, 12))

        self.rec_dot = QLabel("REC")
        self.rec_dot.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))
        self.rec_dot.setStyleSheet("color: #FF3B30;")

        self.lbl_time = QLabel("00:00")
        self.lbl_time.setFont(QFont("Segoe UI Variable Text", 10, QFont.Weight.Bold))
        self.lbl_time.setStyleSheet("color: white;")

        self.btn_pause = QPushButton()
        self.btn_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 16))
        self.btn_pause.setToolTip("Pausar Grabación (Ctrl+Shift+P)")
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.setFixedSize(30, 26)
        self.btn_pause.setStyleSheet("background-color: rgba(255, 255, 255, 0.12); border: none; border-radius: 12px;")
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(get_minimalist_svg_icon("stop", "#FFFFFF", 14))
        self.btn_stop.setToolTip("Detener Grabación (Ctrl+Shift+R)")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setFixedSize(32, 26)
        self.btn_stop.setStyleSheet("background-color: #E81123; border: none; border-radius: 12px;")
        self.btn_stop.clicked.connect(self.stop_requested.emit)

        self.btn_settings = QPushButton()
        self.btn_settings.setIcon(get_minimalist_svg_icon("settings", "#FFFFFF", 16))
        self.btn_settings.setToolTip("Ajustes de Jade")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setFixedSize(30, 26)
        self.btn_settings.setStyleSheet("background-color: rgba(255, 255, 255, 0.12); border: none; border-radius: 12px;")
        self.btn_settings.clicked.connect(self.settings_requested.emit)

        c_layout.addWidget(self.rec_icon_label)
        c_layout.addWidget(self.rec_dot)
        c_layout.addWidget(self.lbl_time)
        c_layout.addWidget(self.btn_pause)
        c_layout.addWidget(self.btn_stop)
        c_layout.addWidget(self.btn_settings)

        layout.addWidget(container)
        self.adjustSize()

    def start_timer(self):
        self.seconds_elapsed = 0
        self.is_paused = False
        self.btn_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 16))
        self.rec_icon_label.setPixmap(get_minimalist_svg_pixmap("record", "#FF3B30", 12, 12))
        self.rec_dot.setText("REC")
        self.rec_dot.setStyleSheet("color: #FF3B30; font-weight: bold;")
        self.lbl_time.setText("00:00")
        self.show()
        try:
            set_window_exclude_from_capture(int(self.winId()))
        except Exception:
            pass
        self.timer.start()

    def stop_timer(self):
        self.timer.stop()
        self.hide()

    def toggle_pause(self):
        if not self.is_paused:
            self.is_paused = True
            self.btn_pause.setIcon(get_minimalist_svg_icon("play", "#FFFFFF", 16))
            self.rec_icon_label.setPixmap(get_minimalist_svg_pixmap("record", "#FFB900", 12, 12))
            self.rec_dot.setStyleSheet("color: #FFB900; font-weight: bold;")
            self.pause_requested.emit()
        else:
            self.is_paused = False
            self.btn_pause.setIcon(get_minimalist_svg_icon("pause", "#FFFFFF", 16))
            self.rec_icon_label.setPixmap(get_minimalist_svg_pixmap("record", "#FF3B30", 12, 12))
            self.rec_dot.setStyleSheet("color: #FF3B30; font-weight: bold;")
            self.resume_requested.emit()

    def _update_timer(self):
        if not self.is_paused:
            self.seconds_elapsed += 1
            mins = self.seconds_elapsed // 60
            secs = self.seconds_elapsed % 60
            self.lbl_time.setText(f"{mins:02d}:{secs:02d}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

class ScreenRecorder(QThread):
    """Hilo de grabación de pantalla con DDAGRAB GPU, captura dual de audio nativo sincronizado (Sistema + Micrófono) por WASAPI y parada asíncrona a 0 ms."""
    recording_started = pyqtSignal()
    recording_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, output_filepath: str, fps: int = 60, use_nvenc: bool = True,
                 record_system: bool = True, record_mic: bool = False, rect: QRect = None,
                 hdr_fix: bool = None, parent=None):
        super().__init__(parent)
        self.output_filepath = output_filepath
        self.fps = fps
        self.use_nvenc = use_nvenc
        self.record_system = record_system
        self.record_mic = record_mic
        self.rect = rect
        self.hdr_fix = hdr_fix if hdr_fix is not None else is_hdr_fix_enabled()
        self.process = None
        self.audio_process = None
        self.mic_process = None
        self.ffmpeg_log_file = None
        self.go_event = threading.Event()
        self.user_stopped = False

    def trigger_go(self):
        self.go_event.set()

    def pause_recording(self):
        log_message("Pausando grabación...")
        if self.process and self.process.poll() is None:
            suspend_process(self.process.pid)
        if self.audio_process and self.audio_process.poll() is None:
            suspend_process(self.audio_process.pid)
        if hasattr(self, 'mic_process') and self.mic_process and self.mic_process.poll() is None:
            suspend_process(self.mic_process.pid)

    def resume_recording(self):
        log_message("Reanudando grabación...")
        if self.process and self.process.poll() is None:
            resume_process(self.process.pid)
        if self.audio_process and self.audio_process.poll() is None:
            resume_process(self.audio_process.pid)
        if hasattr(self, 'mic_process') and self.mic_process and self.mic_process.poll() is None:
            resume_process(self.mic_process.pid)

    def _build_ffmpeg_cmd(self, ffmpeg_executable: str, use_nvenc: bool, use_ddagrab: bool, is_partial: bool,
                          x: int, y: int, w: int, h: int):
        cmd = [ffmpeg_executable, "-y"]

        is_hdr = bool(self.hdr_fix or is_hdr_fix_enabled())

        if self.fps >= 180:
            target_bitrate = "28M"
            max_bitrate = "38M"
            nvenc_preset = "p2"
        elif self.fps >= 120:
            target_bitrate = "20M"
            max_bitrate = "28M"
            nvenc_preset = "p3"
        else:
            target_bitrate = "10M"
            max_bitrate = "15M"
            nvenc_preset = "p4"

        video_filters = []
        video_filters.append(f"fps=fps={self.fps}:round=near:start_time=0")

        if is_hdr:
            video_filters.append("lutrgb=r=clip(255*pow(val/255\\,1.38)*0.90\\,0\\,255):g=clip(255*pow(val/255\\,1.38)*0.90\\,0\\,255):b=clip(255*pow(val/255\\,1.38)*0.90\\,0\\,255)")

        vf_chain = ",".join(video_filters)

        if use_ddagrab and not is_hdr:
            if is_partial:
                dda_filter = f"ddagrab=framerate={self.fps}:draw_mouse=1:offset_x={x}:offset_y={y}:video_size={w}x{h},hwdownload,format=bgra,{vf_chain}"
            else:
                dda_filter = f"ddagrab=framerate={self.fps}:draw_mouse=1,hwdownload,format=bgra,{vf_chain}"
            cmd.extend([
                "-thread_queue_size", "2048",
                "-f", "lavfi",
                "-i", dda_filter
            ])
        else:
            cmd.extend([
                "-thread_queue_size", "2048",
                "-f", "gdigrab",
                "-framerate", str(self.fps),
                "-draw_mouse", "1",
                "-use_wallclock_as_timestamps", "1",
                "-rtbufsize", "2048M"
            ])
            if is_partial:
                cmd.extend(["-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}"])
            cmd.extend(["-i", "desktop"])
            cmd.extend(["-vf", vf_chain])

        cmd.extend([
            "-r", str(self.fps),
            "-fps_mode", "cfr",
            "-map", "0:v"
        ])

        gop_size = str(self.fps * 2)
        if use_nvenc:
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", nvenc_preset,
                "-rc", "vbr",
                "-cq", "20",
                "-b:v", target_bitrate,
                "-maxrate", max_bitrate,
                "-bufsize", "48M",
                "-g", gop_size,
                "-forced-idr", "1",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-crf", "20",
                "-g", gop_size,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"
            ])

        cmd.append(self.temp_video_path)
        return cmd

    def run(self):
        msg_header = "--- NUEVA SESIÓN DE GRABACIÓN DE PANTALLA EN JADE ---"
        log_message(msg_header)
        write_desktop_record_debug_log(msg_header)
        self.user_stopped = False
        try:
            ffmpeg_executable = get_ffmpeg_path()
            if not ffmpeg_executable:
                err_msg = "No se encontró el ejecutable de FFmpeg."
                write_desktop_record_debug_log(f"ERROR CRÍTICO: {err_msg}")
                self.error_occurred.emit(err_msg)
                return

            write_desktop_record_debug_log(f"FFmpeg localizado en: {ffmpeg_executable}")
            ensure_wasapi_script_exists()

            import uuid
            session_id = uuid.uuid4().hex[:8]
            temp_dir = get_jade_appdata_dir()
            self.temp_video_path = os.path.join(temp_dir, f"temp_video_{session_id}.mp4")
            self.temp_audio_path = os.path.join(temp_dir, f"temp_audio_{session_id}.wav")
            self.temp_mic_path = os.path.join(temp_dir, f"temp_mic_{session_id}.wav")
            self.stop_signal_path = os.path.join(temp_dir, f"stop_audio_{session_id}.txt")
            self.ready_signal_path = os.path.join(temp_dir, f"ready_audio_{session_id}.txt")
            self.go_signal_path = os.path.join(temp_dir, f"go_audio_{session_id}.txt")
            self.stop_mic_signal_path = os.path.join(temp_dir, f"stop_mic_{session_id}.txt")
            self.ready_mic_signal_path = os.path.join(temp_dir, f"ready_mic_{session_id}.txt")
            self.go_mic_signal_path = os.path.join(temp_dir, f"go_mic_{session_id}.txt")
            self.ffmpeg_log_path = os.path.join(temp_dir, "logs", f"ffmpeg_video_{session_id}.log")

            for fpath in [self.temp_video_path, self.temp_audio_path, self.temp_mic_path,
                          self.stop_signal_path, self.ready_signal_path, self.go_signal_path,
                          self.stop_mic_signal_path, self.ready_mic_signal_path, self.go_mic_signal_path,
                          self.ffmpeg_log_path]:
                if os.path.exists(fpath):
                    try: os.remove(fpath)
                    except Exception: pass

            screen = QApplication.primaryScreen()
            screen_width = screen.geometry().width() if screen else 1920
            screen_height = screen.geometry().height() if screen else 1080

            if self.rect:
                x = (self.rect.x() // 2) * 2
                y = (self.rect.y() // 2) * 2
                w = (self.rect.width() // 2) * 2
                h = (self.rect.height() // 2) * 2
            else:
                x, y, w, h = 0, 0, screen_width, screen_height

            is_partial = (self.rect is not None) and (w < screen_width or h < screen_height)
            write_desktop_record_debug_log(f"Dimensiones de grabación: {w}x{h} en Offset ({x},{y}). Parcial={is_partial} | Micrófono={self.record_mic}")

            if self.use_nvenc:
                nvenc_ok, nvenc_msg = check_nvenc_support(ffmpeg_executable)
                if not nvenc_ok:
                    write_desktop_record_debug_log(f"NVENC no disponible: {nvenc_msg}. Conmutando a x264 CPU.")
                    self.use_nvenc = False
                else:
                    write_desktop_record_debug_log("NVENC verificado e integrado correctamente.")

            ps_script = os.path.join(temp_dir, "bin", "wasapi_recorder.ps1")
            ps_exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
            if not os.path.exists(ps_exe):
                ps_exe = "powershell"

            startupinfo_audio = subprocess.STARTUPINFO()
            startupinfo_audio.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo_audio.wShowWindow = subprocess.SW_HIDE

            # 1. Precargar captura WASAPI del audio del sistema (DataFlow 0)
            if self.record_system:
                cmd_ps_sys = [
                    ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", ps_script,
                    "-OutputFile", self.temp_audio_path,
                    "-StopFile", self.stop_signal_path,
                    "-ReadyFile", self.ready_signal_path,
                    "-GoFile", self.go_signal_path,
                    "-DataFlow", "0"
                ]
                self.audio_log_path = os.path.join(temp_dir, "logs", f"powershell_audio_{session_id}.log")
                self.audio_log_file = open(self.audio_log_path, "w", encoding="utf-8", errors="ignore")
                self.audio_process = subprocess.Popen(
                    cmd_ps_sys,
                    stdout=self.audio_log_file,
                    stderr=self.audio_log_file,
                    startupinfo=startupinfo_audio,
                    creationflags=0x08000000
                )

            # 2. Precargar captura WASAPI del micrófono nativo en pista separada (DataFlow 1)
            if self.record_mic:
                cmd_ps_mic = [
                    ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", ps_script,
                    "-OutputFile", self.temp_mic_path,
                    "-StopFile", self.stop_mic_signal_path,
                    "-ReadyFile", self.ready_mic_signal_path,
                    "-GoFile", self.go_mic_signal_path,
                    "-DataFlow", "1"
                ]
                self.mic_log_path = os.path.join(temp_dir, "logs", f"powershell_mic_{session_id}.log")
                self.mic_log_file = open(self.mic_log_path, "w", encoding="utf-8", errors="ignore")
                self.mic_process = subprocess.Popen(
                    cmd_ps_mic,
                    stdout=self.mic_log_file,
                    stderr=self.mic_log_file,
                    startupinfo=startupinfo_audio,
                    creationflags=0x08000000
                )

            self.go_event.wait(timeout=10)

            ready_wait_ticks = 0
            while ready_wait_ticks < 150:
                sys_ready = (not self.record_system) or os.path.exists(self.ready_signal_path)
                mic_ready = (not self.record_mic) or os.path.exists(self.ready_mic_signal_path)
                if sys_ready and mic_ready:
                    break
                time.sleep(0.02)
                ready_wait_ticks += 1

            startupinfo_video = subprocess.STARTUPINFO()
            startupinfo_video.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo_video.wShowWindow = subprocess.SW_HIDE

            is_hdr = bool(self.hdr_fix or is_hdr_fix_enabled())
            attempts = [(True, self.use_nvenc), (True, False), (False, self.use_nvenc), (False, False)]

            process_started = False
            for dda_flag, nv_flag in attempts:
                cmd_video = self._build_ffmpeg_cmd(
                    ffmpeg_executable, nv_flag, dda_flag, is_partial,
                    x, y, w, h
                )

                write_desktop_record_debug_log(f"Iniciando FFmpeg GPU (DDAGRAB={dda_flag}, NVENC={nv_flag}).")

                if self.ffmpeg_log_file and not self.ffmpeg_log_file.closed:
                    self.ffmpeg_log_file.close()

                self.ffmpeg_log_file = open(self.ffmpeg_log_path, "w", encoding="utf-8", errors="ignore")
                self.process = subprocess.Popen(
                    cmd_video,
                    stdin=subprocess.PIPE,
                    stdout=self.ffmpeg_log_file,
                    stderr=self.ffmpeg_log_file,
                    startupinfo=startupinfo_video,
                    creationflags=0x08000000 | subprocess.CREATE_NEW_PROCESS_GROUP
                )

                time.sleep(0.08)

                if self.process.poll() is None:
                    self.use_nvenc = nv_flag
                    process_started = True

                    if self.record_system:
                        try:
                            with open(self.go_signal_path, "w", encoding="utf-8") as f: f.write("go")
                        except Exception: pass

                    if self.record_mic:
                        try:
                            with open(self.go_mic_signal_path, "w", encoding="utf-8") as f: f.write("go")
                        except Exception: pass

                    write_desktop_record_debug_log("Audio de Sistema y Micrófono sincronizados e iniciados con FFmpeg.")
                    break

            if not process_started:
                err_msg = "No se pudo iniciar el proceso de grabación de FFmpeg con ninguna combinación gráfica."
                write_desktop_record_debug_log(f"ERROR CRÍTICO: {err_msg}")
                self.error_occurred.emit(err_msg)
                return

            self.recording_started.emit()

            unexpected_exit = False
            while not self.user_stopped:
                if self.process.poll() is not None:
                    unexpected_exit = True
                    break
                time.sleep(0.2)

            write_desktop_record_debug_log("Grabación detenida en background. Finalizando procesos y pistas...")

            if self.process:
                try: self.process.wait(timeout=4)
                except Exception:
                    try: self.process.kill()
                    except Exception: pass

            if self.record_system and self.audio_process:
                try:
                    self.audio_process.wait(timeout=2)
                except Exception:
                    try: self.audio_process.kill()
                    except Exception: pass

            if self.record_mic and self.mic_process:
                try:
                    self.mic_process.wait(timeout=2)
                except Exception:
                    try: self.mic_process.kill()
                    except Exception: pass

            if hasattr(self, 'audio_log_file') and self.audio_log_file and not self.audio_log_file.closed:
                try: self.audio_log_file.close()
                except Exception: pass

            if hasattr(self, 'mic_log_file') and self.mic_log_file and not self.mic_log_file.closed:
                try: self.mic_log_file.close()
                except Exception: pass

            if self.ffmpeg_log_file and not self.ffmpeg_log_file.closed:
                try: self.ffmpeg_log_file.close()
                except Exception: pass

            time.sleep(0.1)

            video_size = os.path.getsize(self.temp_video_path) if os.path.exists(self.temp_video_path) else 0
            audio_size = os.path.getsize(self.temp_audio_path) if os.path.exists(self.temp_audio_path) else 0
            mic_size = os.path.getsize(self.temp_mic_path) if os.path.exists(self.temp_mic_path) else 0

            video_ok = video_size > 1000
            audio_ok = audio_size > 1000
            mic_ok = mic_size > 1000

            write_desktop_record_debug_log(f"Pistas grabadas -> Video: {video_size}B | Audio Sistema: {audio_size}B | Micrófono: {mic_size}B")

            if video_ok:
                if audio_ok and mic_ok:
                    write_desktop_record_debug_log("Mezclando Audio de Sistema y Micrófono al video final...")
                    cmd_mux = [
                        ffmpeg_executable, "-y",
                        "-i", self.temp_video_path,
                        "-i", self.temp_audio_path,
                        "-i", self.temp_mic_path,
                        "-filter_complex", "[1:a]aresample=async=1000[a1];[2:a]aresample=async=1000,volume=1.35[a2];[a1][a2]amix=inputs=2:duration=longest:dropout_transition=0[aout]",
                        "-map", "0:v:0",
                        "-map", "[aout]",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        "-movflags", "+faststart",
                        self.output_filepath
                    ]
                    mux_res = subprocess.run(cmd_mux, startupinfo=startupinfo_video, creationflags=0x08000000)
                    write_desktop_record_debug_log(f"Resultado multiplexación dual: {mux_res.returncode}")

                elif audio_ok:
                    write_desktop_record_debug_log("Uniendo Audio de Sistema con Video...")
                    cmd_mux = [
                        ffmpeg_executable, "-y",
                        "-i", self.temp_video_path,
                        "-i", self.temp_audio_path,
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-af", "aresample=async=1000",
                        "-shortest",
                        "-movflags", "+faststart",
                        self.output_filepath
                    ]
                    subprocess.run(cmd_mux, startupinfo=startupinfo_video, creationflags=0x08000000)

                elif mic_ok:
                    write_desktop_record_debug_log("Uniendo Micrófono con Video...")
                    cmd_mux = [
                        ffmpeg_executable, "-y",
                        "-i", self.temp_video_path,
                        "-i", self.temp_mic_path,
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-af", "aresample=async=1000,volume=1.35",
                        "-shortest",
                        "-movflags", "+faststart",
                        self.output_filepath
                    ]
                    subprocess.run(cmd_mux, startupinfo=startupinfo_video, creationflags=0x08000000)

            if not (os.path.exists(self.output_filepath) and os.path.getsize(self.output_filepath) > 1024):
                if video_ok:
                    for _ in range(5):
                        try:
                            shutil.move(self.temp_video_path, self.output_filepath)
                            break
                        except OSError:
                            time.sleep(0.1)

            # Limpieza no bloqueante de archivos temporales
            audio_log_p = getattr(self, 'audio_log_path', None)
            mic_log_p = getattr(self, 'mic_log_path', None)
            for fpath in [self.temp_video_path, self.temp_audio_path, self.temp_mic_path,
                          self.stop_signal_path, self.ready_signal_path, self.go_signal_path,
                          self.stop_mic_signal_path, self.ready_mic_signal_path, self.go_mic_signal_path,
                          self.ffmpeg_log_path, audio_log_p, mic_log_p]:
                if fpath and os.path.exists(fpath):
                    try: os.remove(fpath)
                    except Exception: pass

            if unexpected_exit:
                self.error_occurred.emit("Grabación interrumpida inesperadamente.")
            elif os.path.exists(self.output_filepath) and os.path.getsize(self.output_filepath) > 1024:
                write_desktop_record_debug_log("¡GRABACIÓN FINALIZADA CON ÉXITO! VIDEO, SISTEMA Y MICRÓFONO SINCRONIZADOS.")
                self.recording_finished.emit(self.output_filepath)
            else:
                self.error_occurred.emit("No se generó el video final.")

        except Exception as e:
            log_message(f"Excepción en grabación: {e}")
            self.error_occurred.emit(f"Error: {str(e)}")

    def stop_recording(self):
        """Envía las señales de parada de forma no bloqueante a 0 ms sin congelar el hilo principal de la UI ni los atajos."""
        log_message("Deteniendo grabación de forma asíncrona inmediata...")
        self.user_stopped = True

        try:
            if hasattr(self, 'stop_signal_path') and self.stop_signal_path:
                with open(self.stop_signal_path, "w") as f: f.write("stop")
        except Exception: pass

        try:
            if hasattr(self, 'stop_mic_signal_path') and self.stop_mic_signal_path:
                with open(self.stop_mic_signal_path, "w") as f: f.write("stop")
        except Exception: pass

        if self.process and self.process.poll() is None:
            try:
                if self.process.stdin and not self.process.stdin.closed:
                    self.process.stdin.write(b'q\n')
                    self.process.stdin.flush()
                    self.process.stdin.close()
            except Exception: pass

class AudioOnlyRecorder(QThread):
    """Hilo exclusivo de grabación de audio interno de la PC en alta calidad nativa MP3 (320 kbps)."""
    recording_started = pyqtSignal()
    recording_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, output_filepath: str, parent=None):
        super().__init__(parent)
        self.output_filepath = output_filepath
        self.audio_process = None
        self.go_event = threading.Event()
        self.user_stopped = False

    def trigger_go(self):
        self.go_event.set()

    def pause_recording(self):
        log_message("Pausando grabación de audio...")
        if self.audio_process and self.audio_process.poll() is None:
            suspend_process(self.audio_process.pid)

    def resume_recording(self):
        log_message("Reanudando grabación de audio...")
        if self.audio_process and self.audio_process.poll() is None:
            resume_process(self.audio_process.pid)

    def run(self):
        log_message("--- NUEVA SESIÓN DE GRABACIÓN DE SOLO AUDIO EN JADE ---")
        self.user_stopped = False
        try:
            ffmpeg_executable = get_ffmpeg_path()
            if not ffmpeg_executable:
                self.error_occurred.emit("No se encontró el ejecutable de FFmpeg para codificar MP3.")
                return

            ensure_wasapi_script_exists()

            import uuid
            session_id = uuid.uuid4().hex[:8]
            temp_dir = get_jade_appdata_dir()
            self.temp_audio_path = os.path.join(temp_dir, f"temp_audio_only_{session_id}.wav")
            self.stop_signal_path = os.path.join(temp_dir, f"stop_audio_only_{session_id}.txt")
            self.ready_signal_path = os.path.join(temp_dir, f"ready_audio_only_{session_id}.txt")
            self.go_signal_path = os.path.join(temp_dir, f"go_audio_only_{session_id}.txt")

            for fpath in [self.temp_audio_path, self.stop_signal_path, self.ready_signal_path, self.go_signal_path]:
                if os.path.exists(fpath):
                    try: os.remove(fpath)
                    except Exception: pass

            ps_script = os.path.join(temp_dir, "bin", "wasapi_recorder.ps1")
            ps_exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
            if not os.path.exists(ps_exe):
                ps_exe = "powershell"

            startupinfo_audio = subprocess.STARTUPINFO()
            startupinfo_audio.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo_audio.wShowWindow = subprocess.SW_HIDE

            cmd_ps = [
                ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", ps_script,
                "-OutputFile", self.temp_audio_path,
                "-StopFile", self.stop_signal_path,
                "-ReadyFile", self.ready_signal_path,
                "-GoFile", self.go_signal_path
            ]

            self.audio_log_path = os.path.join(temp_dir, "logs", f"powershell_audio_only_{session_id}.log")
            self.audio_log_file = open(self.audio_log_path, "w", encoding="utf-8", errors="ignore")
            self.audio_process = subprocess.Popen(
                cmd_ps,
                stdout=self.audio_log_file,
                stderr=self.audio_log_file,
                startupinfo=startupinfo_audio,
                creationflags=0x08000000
            )

            self.go_event.wait(timeout=10)

            ready_ticks = 0
            while not os.path.exists(self.ready_signal_path) and ready_ticks < 100:
                time.sleep(0.02)
                ready_ticks += 1

            try:
                with open(self.go_signal_path, "w") as f:
                    f.write("go")
            except Exception as e:
                log_message(f"Error escribiendo archivo go audio: {e}")

            self.recording_started.emit()

            while not self.user_stopped and self.audio_process and self.audio_process.poll() is None:
                time.sleep(0.1)

            audio_ok = os.path.exists(self.temp_audio_path) and os.path.getsize(self.temp_audio_path) > 1000

            if audio_ok:
                cmd_convert = [
                    ffmpeg_executable, "-y",
                    "-i", self.temp_audio_path,
                    "-c:a", "libmp3lame",
                    "-b:a", "320k",
                    "-ac", "2",
                    "-ar", "44100",
                    self.output_filepath
                ]
                subprocess.run(cmd_convert, startupinfo=startupinfo_audio, creationflags=0x08000000)

            if hasattr(self, 'audio_log_file') and self.audio_log_file and not self.audio_log_file.closed:
                try:
                    self.audio_log_file.close()
                except Exception:
                    pass

            audio_log_p = getattr(self, 'audio_log_path', None)
            for fpath in [self.temp_audio_path, self.stop_signal_path, self.ready_signal_path, self.go_signal_path, audio_log_p]:
                if fpath and os.path.exists(fpath):
                    try: os.remove(fpath)
                    except Exception: pass

            if os.path.exists(self.output_filepath) and os.path.getsize(self.output_filepath) > 500:
                self.recording_finished.emit(self.output_filepath)
            else:
                self.error_occurred.emit("No se generó el archivo de audio MP3.")

        except Exception as e:
            log_message(f"Excepción en grabación de solo audio: {e}")
            self.error_occurred.emit(f"Error en audio: {str(e)}")

    def stop_recording(self):
        log_message("Deteniendo grabación de audio únicamente...")
        self.user_stopped = True

        try:
            if hasattr(self, 'stop_signal_path') and self.stop_signal_path:
                with open(self.stop_signal_path, "w") as f:
                    f.write("stop")
        except Exception as e:
            log_message(f"Error enviando señal stop audio: {e}")

        if hasattr(self, 'audio_process') and self.audio_process and self.audio_process.poll() is None:
            try:
                self.audio_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    self.audio_process.kill()
                except Exception:
                    pass

        self.audio_process = None
        log_message("Recursos de grabación de audio liberados exitosamente.")
def parse_hotkey_string(hotkey_str: str):
    """Convierte cadenas de texto como 'Ctrl+Shift+S', 'PrtScn' o 'F9' en modificadores y virtual key codes Win32."""
    if not hotkey_str or not isinstance(hotkey_str, str) or not hotkey_str.strip():
        return None, None

    mods = 0
    vk = 0
    parts = [p.strip().upper() for p in hotkey_str.split("+") if p.strip()]

    for part in parts:
        if part in ("CTRL", "CONTROL"):
            mods |= 0x0002  # MOD_CONTROL
        elif part == "SHIFT":
            mods |= 0x0004  # MOD_SHIFT
        elif part in ("ALT", "MENU"):
            mods |= 0x0001  # MOD_ALT
        elif part in ("WIN", "WINDOWS"):
            mods |= 0x0008  # MOD_WIN
        else:
            if len(part) == 1:
                vk = ord(part[0])
            elif part.startswith("F") and part[1:].isdigit():
                f_num = int(part[1:])
                if 1 <= f_num <= 24:
                    vk = 0x6F + f_num
            elif part in ("PRTSCN", "PRTSCR", "PRINTSCREEN", "SNAPSHOT"):
                vk = 0x2C
            elif part in ("SPACE", "ESPACIO"):
                vk = 0x20
            elif part == "TAB":
                vk = 0x09
            elif part in ("ESC", "ESCAPE"):
                vk = 0x1B
            elif part in ("ENTER", "RETURN"):
                vk = 0x0D
            elif part in ("DEL", "DELETE"):
                vk = 0x2E
            elif part in ("BACKSPACE", "BKSP"):
                vk = 0x08
            elif part == "HOME":
                vk = 0x24
            elif part == "END":
                vk = 0x23
            elif part in ("PGUP", "PAGEUP"):
                vk = 0x21
            elif part in ("PGDN", "PAGEDOWN"):
                vk = 0x22
            elif part in ("INS", "INSERT"):
                vk = 0x2D

    if vk != 0:
        return mods, vk
    return None, None

class GlobalHotkeyThread(QThread):
    """Escuchador global Win32 híbrido con registro de kernel y sondeo de hardware para garantizar que funcionen todos los atajos."""
    capture_triggered = pyqtSignal()
    record_triggered = pyqtSignal()
    record_audio_triggered = pyqtSignal()
    pause_triggered = pyqtSignal()
    history_triggered = pyqtSignal()
    gallery_triggered = pyqtSignal()
    toggle_hotkeys_triggered = pyqtSignal(bool)
    draw_arrow_triggered = pyqtSignal()
    clear_draw_triggered = pyqtSignal()
    translate_triggered = pyqtSignal()
    quick_translator_triggered = pyqtSignal()
    game_mode_triggered = pyqtSignal()
    pin_note_triggered = pyqtSignal()

    def __init__(self, hk_cap: str, hk_rec: str, hk_rec_audio: str, hk_pause: str, hk_hist: str, hk_gal: str, hk_tog: str, hk_draw: str = "Ctrl+Shift+D", hk_clr: str = "Ctrl+Shift+E", hk_trans: str = "Ctrl+Shift+T", hk_qtrans: str = "Ctrl+Shift+Z", hk_game: str = "Ctrl+Shift+Enter", hk_pin: str = "Ctrl+Shift+C", parent=None):
        super().__init__(parent)
        self.running = True
        self.hk_cap = hk_cap
        self.hk_rec = hk_rec
        self.hk_rec_audio = hk_rec_audio
        self.hk_pause = hk_pause
        self.hk_hist = hk_hist
        self.hk_gal = hk_gal
        self.hk_tog = hk_tog
        self.hk_draw = hk_draw
        self.hk_clr = hk_clr
        self.hk_trans = hk_trans
        self.hk_qtrans = hk_qtrans
        self.hk_game = hk_game
        self.hk_pin = hk_pin
        self.win_thread_id = 0
        self.hotkeys_muted = False
        self._last_trigger_times = {}

    def _dispatch_hotkey(self, hotkey_id: int):
        if hotkey_id == 7:
            self.hotkeys_muted = not self.hotkeys_muted
            self.toggle_hotkeys_triggered.emit(not self.hotkeys_muted)
            return

        if self.hotkeys_muted:
            return

        signals = {
            1: self.capture_triggered,
            2: self.record_triggered,
            3: self.record_audio_triggered,
            4: self.pause_triggered,
            5: self.history_triggered,
            6: self.gallery_triggered,
            8: self.draw_arrow_triggered,
            9: self.clear_draw_triggered,
            10: self.translate_triggered,
            11: self.game_mode_triggered,
            12: self.quick_translator_triggered,
            13: self.pin_note_triggered,
        }
        sig = signals.get(hotkey_id)
        if sig:
            sig.emit()

    def run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.win_thread_id = kernel32.GetCurrentThreadId()

        user32.RegisterHotKey.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
        user32.RegisterHotKey.restype = ctypes.c_int
        user32.UnregisterHotKey.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = ctypes.c_int
        user32.PeekMessageW.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG), ctypes.wintypes.HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
        user32.PeekMessageW.restype = ctypes.c_int
        user32.PostThreadMessageW.argtypes = [ctypes.wintypes.DWORD, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
        user32.PostThreadMessageW.restype = ctypes.c_int
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short

        msg = ctypes.wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        raw_keys = {
            1: self.hk_cap,
            2: self.hk_rec,
            3: self.hk_rec_audio,
            4: self.hk_pause,
            5: self.hk_hist,
            6: self.hk_gal,
            7: self.hk_tog,
            8: self.hk_draw,
            9: self.hk_clr,
            10: self.hk_trans,
            11: self.hk_game,
            12: self.hk_qtrans,
            13: self.hk_pin,
        }

        registered_ids = set()
        active_mappings = {}
        MOD_NOREPEAT = 0x4000

        for hid, hstr in raw_keys.items():
            parsed = parse_hotkey_string(hstr)
            if not parsed or not parsed[1]:
                continue
            m, k = parsed
            active_mappings[hid] = (m, k)
            if k != 0x2C:
                if user32.RegisterHotKey(None, hid, m | MOD_NOREPEAT, k):
                    registered_ids.add(hid)
                elif user32.RegisterHotKey(None, hid, m, k):
                    registered_ids.add(hid)

        PM_REMOVE = 1

        while self.running:
            # 1. Procesar mensajes WM_HOTKEY del sistema
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == 0x0012:
                    self.running = False
                    break
                elif msg.message == 0x0312:
                    hotkey_id = msg.wParam
                    now = time.time()
                    if now - self._last_trigger_times.get(hotkey_id, 0.0) >= 0.25:
                        self._last_trigger_times[hotkey_id] = now
                        self._dispatch_hotkey(hotkey_id)

            if not self.running:
                break

            # 2. Respaldo directo por hardware: detecta PrtScn y combinaciones aunque otro programa las bloquee
            ctrl_down = bool((user32.GetAsyncKeyState(0x11) & 0x8000) or (user32.GetAsyncKeyState(0xA2) & 0x8000) or (user32.GetAsyncKeyState(0xA3) & 0x8000))
            shift_down = bool((user32.GetAsyncKeyState(0x10) & 0x8000) or (user32.GetAsyncKeyState(0xA0) & 0x8000) or (user32.GetAsyncKeyState(0xA1) & 0x8000))
            alt_down = bool((user32.GetAsyncKeyState(0x12) & 0x8000) or (user32.GetAsyncKeyState(0xA4) & 0x8000) or (user32.GetAsyncKeyState(0xA5) & 0x8000))
            win_down = bool((user32.GetAsyncKeyState(0x5B) & 0x8000) or (user32.GetAsyncKeyState(0x5C) & 0x8000))

            current_mods = 0
            if alt_down: current_mods |= 0x0001
            if ctrl_down: current_mods |= 0x0002
            if shift_down: current_mods |= 0x0004
            if win_down: current_mods |= 0x0008

            now = time.time()
            for hid, (req_mods, req_vk) in active_mappings.items():
                if current_mods == req_mods:
                    if user32.GetAsyncKeyState(req_vk) & 0x8000:
                        if now - self._last_trigger_times.get(hid, 0.0) >= 0.35:
                            self._last_trigger_times[hid] = now
                            self._dispatch_hotkey(hid)

            self.msleep(15)

        for hid in list(registered_ids):
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass

    def stop(self):
        self.running = False
        user32 = ctypes.windll.user32
        if hasattr(self, "win_thread_id") and self.win_thread_id:
            try:
                user32.PostThreadMessageW(self.win_thread_id, 0x0012, 0, 0)
            except Exception:
                pass
        self.quit()
        self.wait(500)

class OcrProgressOverlay(QWidget):
    """Superposición transparente con tarjeta flotante animada durante la extracción de texto OCR."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.dot_count = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(80)
        self.anim_timer.timeout.connect(self._on_anim_step)

    def start_animation(self):
        self.angle = 0
        self.dot_count = 0
        self.show()
        try:
            hwnd = int(self.winId())
            set_window_exclude_from_capture(hwnd)
        except Exception:
            pass
        self.anim_timer.start()

    def stop_animation(self):
        self.anim_timer.stop()
        self.close()

    def _on_anim_step(self):
        self.angle = (self.angle + 12) % 360
        self.dot_count = (self.dot_count + 1) % 4
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() // 2, self.height() // 2
        card_w, card_h = 280, 130
        card_rect = QRectF(cx - card_w / 2.0, cy - card_h / 2.0, float(card_w), float(card_h))

        path = QPainterPath()
        path.addRoundedRect(card_rect, 20.0, 20.0)

        painter.fillPath(path, QColor(18, 20, 26, 235))
        painter.setPen(QPen(QColor(0, 120, 212, 180), 2))
        painter.drawPath(path)

        spinner_r = 18
        sp_cx, sp_cy = cx, cy - 18
        painter.save()
        painter.translate(sp_cx, sp_cy)
        painter.rotate(self.angle)
        pen = QPen(QColor(0, 120, 212), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(-spinner_r, -spinner_r, spinner_r * 2, spinner_r * 2, 0, 270 * 16)
        painter.restore()

        dots = "." * self.dot_count
        text = f"Extrayendo texto{dots}"
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
        text_rect = QRectF(card_rect.x(), cy + 12, card_w, 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)


class OcrInstallerThread(QThread):
    """Descarga e instala de forma automatizada y silenciosa el ejecutable (.exe) de Tesseract OCR."""
    status_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            import urllib.request
            import ssl
            import traceback

            print("\n==================================================")
            print("[OCR DIAGNÓSTICO] INICIANDO VERIFICACIÓN E INSTALACIÓN SILENCIOSA DE TESSERACT")
            print("==================================================")

            bin_dir = os.path.join(get_jade_appdata_dir(), "bin")
            os.makedirs(bin_dir, exist_ok=True)
            tess_exe = os.path.join(bin_dir, "tesseract.exe")

            urls_exe = [
                "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe",
                "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.0.20241111.exe",
                "https://github.com/tesseract-ocr/tesseract/releases/download/v5.3.3/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
            ]
            url_spa = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/spa.traineddata"
            url_eng = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata"

            def download_safe(url_src, target_p, reporthook=None):
                print(f"[OCR DESCARGA] Descargando desde: {url_src}")
                ua_str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

                class SmartRedirectHandler(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, req, fp, code, msg, headers, newurl):
                        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
                        if new_req:
                            new_req.add_header("User-Agent", ua_str)
                        return new_req

                try:
                    ctx = ssl._create_unverified_context()
                except Exception:
                    ctx = None

                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    SmartRedirectHandler()
                )

                req = urllib.request.Request(url_src, headers={"User-Agent": ua_str})
                with opener.open(req, timeout=120) as resp, open(target_p, "wb") as out_f:
                    total_s = int(resp.headers.get("content-length", 0))
                    b_size = 65536
                    b_num = 0
                    while True:
                        buf = resp.read(b_size)
                        if not buf:
                            break
                        out_f.write(buf)
                        b_num += 1
                        if reporthook:
                            reporthook(b_num, b_size, total_s)

            # 1. Comprobar si Tesseract ya está instalado en el sistema (C:\Program Files\Tesseract-OCR, PATH, etc.)
            existing_tess = None
            candidate_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                shutil.which("tesseract")
            ]
            for candidate in candidate_paths:
                if candidate and os.path.exists(candidate):
                    existing_tess = candidate
                    break

            if existing_tess:
                self.status_updated.emit("Tesseract detectado en el sistema. Copiando archivos...")
                log_message(f"Tesseract ya instalado en {existing_tess}. Vinculando directamente...")
                source_dir = os.path.dirname(existing_tess)
                if os.path.normpath(source_dir) != os.path.normpath(bin_dir):
                    for item in os.listdir(source_dir):
                        s_item = os.path.join(source_dir, item)
                        d_item = os.path.join(bin_dir, item)
                        if os.path.isfile(s_item) and (item.lower().endswith(".exe") or item.lower().endswith(".dll")):
                            try:
                                shutil.copy2(s_item, d_item)
                            except Exception:
                                pass
            elif not os.path.exists(tess_exe):
                installer_path = os.path.join(bin_dir, "tesseract_setup.exe")

                def report_progress(block_num, block_size, total_size):
                    if total_size > 0:
                        percent = int(block_num * block_size * 100 / total_size)
                        percent = min(100, percent)
                        desc_mb = (block_num * block_size) / (1024 * 1024)
                        tot_mb = total_size / (1024 * 1024)
                        self.status_updated.emit(f"Descargando Instalador Tesseract .exe... {percent}% ({desc_mb:.1f} MB / {tot_mb:.1f} MB)")

                download_success = False
                for exe_url in urls_exe:
                    try:
                        self.status_updated.emit("Descargando ejecutable de instalación de Tesseract OCR desde GitHub...")
                        download_safe(exe_url, installer_path, report_progress)
                        if os.path.exists(installer_path) and os.path.getsize(installer_path) > 5000000:
                            download_success = True
                            log_message(f"Descarga de instalador .exe exitosa desde {exe_url}")
                            break
                    except Exception as e_dl:
                        print(f"[OCR DESCARGA ERROR] Falló descarga desde {exe_url}: {e_dl}")
                        log_message(f"Error descargando instalador Tesseract: {e_dl}")

                if not download_success:
                    self.finished.emit(False, "No se pudo descargar el instalador .exe de Tesseract.")
                    return

                self.status_updated.emit("Instalando Tesseract de forma automatizada y silenciosa...")
                log_message("Ejecutando instalación automatizada de Tesseract OCR...")

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                install_cmd = [installer_path, "/S", f"/D={bin_dir}"]
                res = subprocess.run(
                    install_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    creationflags=0x08000000,
                    timeout=180
                )

                try:
                    if os.path.exists(installer_path):
                        os.remove(installer_path)
                except Exception:
                    pass

            tessdata_dir = os.path.join(bin_dir, "tessdata")
            os.makedirs(tessdata_dir, exist_ok=True)
            spa_data_path = os.path.join(tessdata_dir, "spa.traineddata")
            eng_data_path = os.path.join(tessdata_dir, "eng.traineddata")

            # También verificar si existen en la ruta estándar de Program Files
            prog_tessdata = r"C:\Program Files\Tesseract-OCR\tessdata"
            if os.path.exists(prog_tessdata):
                if not os.path.exists(spa_data_path) and os.path.exists(os.path.join(prog_tessdata, "spa.traineddata")):
                    try: shutil.copy2(os.path.join(prog_tessdata, "spa.traineddata"), spa_data_path)
                    except Exception: pass
                if not os.path.exists(eng_data_path) and os.path.exists(os.path.join(prog_tessdata, "eng.traineddata")):
                    try: shutil.copy2(os.path.join(prog_tessdata, "eng.traineddata"), eng_data_path)
                    except Exception: pass

            if not os.path.exists(spa_data_path):
                self.status_updated.emit("Descargando paquete de idioma Español (spa.traineddata)...")
                try: download_safe(url_spa, spa_data_path)
                except Exception as e_spa:
                    log_message(f"Error descargando spa.traineddata: {e_spa}")

            if not os.path.exists(eng_data_path):
                self.status_updated.emit("Descargando paquete de idioma Inglés (eng.traineddata)...")
                try: download_safe(url_eng, eng_data_path)
                except Exception as e_eng:
                    log_message(f"Error descargando eng.traineddata: {e_eng}")

            final_exe_check = os.path.exists(os.path.join(bin_dir, "tesseract.exe"))
            if not final_exe_check:
                for root, dirs, files in os.walk(bin_dir):
                    if "tesseract.exe" in files:
                        final_exe_check = True
                        break

            if not final_exe_check:
                prog_files_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                if os.path.exists(prog_files_tess):
                    final_exe_check = True

            if final_exe_check:
                log_message("Instalación de Tesseract OCR completada e identificada con éxito.")
                self.finished.emit(True, "¡Motor Tesseract OCR instalado y validado exitosamente!")
            else:
                self.finished.emit(False, "No se encontró tesseract.exe tras la instalación.")

        except Exception as e:
            print(f"[OCR EXCEPCIÓN CRÍTICA GENERAL] {e}")
            traceback.print_exc()
            log_message(f"Excepción instalando Tesseract OCR: {e}")
            self.finished.emit(False, f"Error al instalar motor OCR: {str(e)}")


class ArgosInstallerThread(QThread):
    """Descarga e instala de forma autónoma los paquetes de traducción con redirección total de permisos para Windows Home, Pro y Enterprise."""
    status_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, from_code: str = "en", to_code: str = "es", parent=None):
        super().__init__(parent)
        self.from_code = from_code
        self.to_code = to_code

    def run(self):
        try:
            import urllib.request
            import zipfile
            import ssl
            import json

            base_dir = get_jade_appdata_dir()
            models_dir = os.path.join(base_dir, "argos_models")
            packages_dir = os.path.join(base_dir, "argos_packages")
            argos_data = os.path.join(base_dir, "argos_data")
            argos_cache = os.path.join(base_dir, "cache", "argos")

            for folder in [models_dir, packages_dir, argos_data, argos_cache]:
                os.makedirs(folder, exist_ok=True)

            os.environ["ARGOS_PACKAGES_DIR"] = packages_dir
            os.environ["ARGOS_PACKAGE_DIR"] = packages_dir
            os.environ["ARGOS_TRANSLATE_PACKAGE_DIR"] = packages_dir
            os.environ["XDG_DATA_HOME"] = argos_data
            os.environ["XDG_CONFIG_HOME"] = argos_data
            os.environ["XDG_CACHE_HOME"] = argos_cache

            self.status_updated.emit("Iniciando descarga del paquete de idioma (.argosmodel)...")
            log_message(f"Descargando paquete de idioma {self.from_code}->{self.to_code} en AppData protegida...")

            urls = [
                f"https://pub-dbae765fb25a4114aac1c88b90e94178.r2.dev/v1/translate-{self.from_code}_{self.to_code}-1_0.argosmodel",
                f"https://pub-dbae765fb25a4114aac1c88b90e94178.r2.dev/v1/translate-{self.from_code}_{self.to_code}-1_7.argosmodel",
            ]

            try:
                idx_url = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
                req = urllib.request.Request(idx_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    for pkg in data:
                        if pkg.get("from_code") == self.from_code and pkg.get("to_code") == self.to_code:
                            for l in pkg.get("links", []):
                                if l.startswith("http") and l not in urls:
                                    urls.insert(0, l)
            except Exception as e_idx:
                log_message(f"No se pudo consultar index.json remoto de Argos: {e_idx}")

            target_zip = os.path.join(models_dir, f"translate-{self.from_code}_{self.to_code}-1_0.argosmodel")

            def report_progress(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int(block_num * block_size * 100 / total_size)
                    percent = min(100, percent)
                    desc_mb = (block_num * block_size) / (1024 * 1024)
                    tot_mb = total_size / (1024 * 1024)
                    self.status_updated.emit(f"Descargando Modelo ({self.from_code.upper()}➔{self.to_code.upper()})... {percent}% ({desc_mb:.1f} MB / {tot_mb:.1f} MB)")

            download_ok = False
            ua_str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

            for url in urls:
                try:
                    log_message(f"Probando descarga de modelo desde: {url}")
                    req = urllib.request.Request(url, headers={"User-Agent": ua_str})
                    ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, context=ctx, timeout=120) as resp, open(target_zip, "wb") as out_f:
                        total_s = int(resp.headers.get("content-length", 0))
                        b_size = 65536
                        b_num = 0
                        while True:
                            buf = resp.read(b_size)
                            if not buf:
                                break
                            out_f.write(buf)
                            b_num += 1
                            report_progress(b_num, b_size, total_s)

                    if os.path.exists(target_zip) and os.path.getsize(target_zip) > 500000:
                        download_ok = True
                        log_message(f"Descarga exitosa de modelo desde {url}")
                        break
                except Exception as e_dl:
                    log_message(f"Error descargando modelo desde {url}: {e_dl}")

            if not download_ok:
                try:
                    import argostranslate.package
                    self.status_updated.emit("Consultando repositorio de Argos...")
                    argostranslate.package.update_package_index()
                    pkgs = argostranslate.package.get_available_packages()
                    target_pkg = next((p for p in pkgs if p.from_code == self.from_code and p.to_code == self.to_code), None)
                    if target_pkg:
                        self.status_updated.emit("Descargando vía API de Argos...")
                        dl_path = target_pkg.download()
                        if dl_path and os.path.exists(dl_path):
                            shutil.copy2(dl_path, target_zip)
                            download_ok = True
                except Exception as e_api:
                    log_message(f"Error vía API de Argos: {e_api}")

            if not download_ok:
                self.finished.emit(False, "No se pudo descargar el modelo de traducción desde los servidores oficiales.")
                return

            self.status_updated.emit("Instalando modelo de traducción en AppData de Jade...")
            target_extract_dir = os.path.join(packages_dir, f"{self.from_code}_{self.to_code}")
            os.makedirs(target_extract_dir, exist_ok=True)

            with zipfile.ZipFile(target_zip, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    extracted_path = os.path.join(target_extract_dir, member)
                    if member.endswith('/'):
                        os.makedirs(extracted_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(extracted_path), exist_ok=True)
                        if os.path.exists(extracted_path):
                            try:
                                os.chmod(extracted_path, 0o777)
                                os.remove(extracted_path)
                            except Exception:
                                pass
                        with zip_ref.open(member) as source, open(extracted_path, "wb") as target:
                            shutil.copyfileobj(source, target)

            try:
                import argostranslate.package
                argostranslate.package.install_from_path(target_zip)
            except Exception as e_reg:
                log_message(f"Registro en cache de argos completado localmente: {e_reg}")

            log_message(f"Modelo {self.from_code}->{self.to_code} instalado y validado con éxito.")
            self.finished.emit(True, "¡Modelo de traducción instalado y validado exitosamente!")

        except Exception as e:
            log_message(f"Excepción instalando modelo de traducción: {e}")
            self.finished.emit(False, f"Error al instalar paquete de traducción: {str(e)}")


def get_tesseract_binary_path() -> str:
    """Detecta la ubicación de tesseract.exe en todas las rutas del sistema y entorno compilado."""
    candidates = [
        os.path.join(get_jade_appdata_dir(), "bin", "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        shutil.which("tesseract")
    ]
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.insert(0, os.path.join(exe_dir, "bin", "tesseract.exe"))
        candidates.insert(1, os.path.join(exe_dir, "tesseract.exe"))
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, os.path.join(sys._MEIPASS, "bin", "tesseract.exe"))
        candidates.insert(1, os.path.join(sys._MEIPASS, "tesseract.exe"))

    for c in candidates:
        if c and os.path.exists(c):
            return c
    return ""

def perform_direct_ocr(image: QImage) -> str:
    """Función de OCR 100% en RAM, segura entre hilos (Thread-Safe) y con validación previa de dependencias WinRT."""
    if image is None or image.isNull():
        return ""

    raw_img = image.copy()
    if raw_img.width() < 300 or raw_img.height() < 200:
        raw_img = raw_img.scaled(
            raw_img.width() * 2,
            raw_img.height() * 2,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )

    text_result = ""

    # Intento 1: WinRT nativo de Windows (con verificación previa de Foundation)
    try:
        import winrt.windows.foundation
        import winrt.windows.media.ocr as ocr
        import winrt.windows.graphics.imaging as imaging
        import winrt.windows.storage.streams as streams

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        raw_img.save(buffer, "BMP")
        bytes_data = buffer.data().data()
        buffer.close()

        async def _run_winrt():
            stream = streams.InMemoryRandomAccessStream()
            writer = streams.DataWriter(stream)
            writer.write_bytes(bytes_data)
            await writer.store_async()
            stream.seek(0)

            decoder = await imaging.BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async()

            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
            if not engine:
                langs = ocr.OcrEngine.all_possible_languages
                if langs and len(langs) > 0:
                    engine = ocr.OcrEngine.try_create_from_language(langs[0])
            if not engine:
                return ""

            ocr_result = await engine.recognize_async(software_bitmap)
            return "\n".join([line.text for line in ocr_result.lines])

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            text_result = loop.run_until_complete(_run_winrt())
        finally:
            loop.close()
    except (Exception, BaseException) as e_winrt:
        log_message(f"[OCR WinRT Exception]: {e_winrt}")

    # Intento 2: Tesseract OCR (por pipe directo en RAM sin archivos temporales)
    if not text_result or not text_result.strip():
        tess_bin = get_tesseract_binary_path()
        if tess_bin:
            try:
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                raw_img.save(buffer, "PNG")
                img_bytes = buffer.data().data()
                buffer.close()

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                tess_dir = os.path.dirname(tess_bin)
                tessdata_dir = os.path.join(tess_dir, "tessdata")
                cmd_tess = [tess_bin, "stdin", "stdout", "--psm", "6", "-l", "eng+spa"]
                if os.path.exists(tessdata_dir):
                    cmd_tess.extend(["--tessdata-dir", tessdata_dir])

                proc = subprocess.Popen(
                    cmd_tess,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    creationflags=0x08000000
                )
                out_bytes, _ = proc.communicate(input=img_bytes, timeout=4)
                text_result = out_bytes.decode("utf-8", errors="ignore").strip()
            except Exception as e_tess:
                log_message(f"[OCR Tesseract Exception]: {e_tess}")

    return text_result.strip() if text_result else ""

class OCRWorker(QThread):
    """Hilo secundario ultra-optimizado para OCR en RAM con conversión segura de pixmap a QImage en inicialización."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.image = pixmap.toImage()
        elif isinstance(pixmap, QImage):
            self.image = pixmap
        else:
            self.image = None

    def run(self):
        log_message("=== INICIANDO EXTRAER TEXTO ULTRA-RÁPIDO (100% RAM) ===")
        try:
            if self.image is None or self.image.isNull():
                self.finished.emit("No se pudo cargar la imagen para OCR.")
                return

            clean_res = perform_direct_ocr(self.image)
            if clean_res:
                log_message(f"=== OCR COMPLETADO: {len(clean_res)} caracteres ===")
                self.finished.emit(clean_res)
            else:
                log_message("=== OCR SIN MOTOR DISPONIBLE (SISTEMA LITE) ===")
                self.finished.emit("REQUIRES_LITE_OCR_INSTALL")
        except Exception as e:
            log_message(f"=== EXCEPCIÓN EN OCRWORKER: {e} ===")
            self.finished.emit(f"No se pudo completar el OCR: {str(e)}")
        finally:
            self.image = None
            import gc
            gc.collect()

_ARGOS_TRANSLATION_CACHE = {}
_ARGOS_MODULE_READY = False
_LAST_TRANSLATION_CARD_POS = None

class TranslationFloatingCard(QWidget):
    """Tarjeta flotante de OCR / Traducción instantánea con memoria de posición persistente y arrastre fluido."""
    def __init__(self, pos: QPoint, from_lang: str = "en", to_lang: str = "es", mode: str = "trans", parent=None):
        super().__init__(parent)
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.mode = mode
        self.translated_text = ""
        self.original_text = ""
        self._is_closing = False
        self._initialized = False
        self.dot_count = 0
        self._drag_pos = None
        self.is_dark_theme = True

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
        self.position_near(pos)
        self._initialized = True

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(250)
        self.anim_timer.timeout.connect(self._step_anim)
        self.anim_timer.start()

    def moveEvent(self, event):
        super().moveEvent(event)
        if getattr(self, "_initialized", False):
            global _LAST_TRANSLATION_CARD_POS
            _LAST_TRANSLATION_CARD_POS = self.pos()
            self._save_position_to_disk(self.pos())

    def _save_position_to_disk(self, pos: QPoint):
        global _LAST_TRANSLATION_CARD_POS
        _LAST_TRANSLATION_CARD_POS = pos
        try:
            cfg_file = os.path.join(get_jade_appdata_dir(), "config.json")
            data = {}
            if os.path.exists(cfg_file):
                with open(cfg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["last_translation_card_pos"] = [int(pos.x()), int(pos.y())]
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos") and self._drag_pos:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            if getattr(self, "_initialized", False):
                self._save_position_to_disk(self.pos())
            event.accept()
        super().mouseReleaseEvent(event)

    def init_ui(self):
        dark = True
        try:
            config_path = os.path.join(get_jade_appdata_dir(), "config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    theme_cfg = cfg.get("theme", "sistema")
                    if theme_cfg == "oscuro":
                        dark = True
                    elif theme_cfg == "claro":
                        dark = False
                    else:
                        dark = (detect_windows_system_theme() == "oscuro")
            else:
                dark = (detect_windows_system_theme() == "oscuro")
        except Exception:
            dark = (detect_windows_system_theme() == "oscuro")

        self.is_dark_theme = dark

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        self.card.setObjectName("TranslationCard")
        if dark:
            self.card.setStyleSheet("""
                QFrame#TranslationCard {
                    background-color: rgba(20, 24, 32, 0.96);
                    border: 1px solid rgba(0, 120, 212, 0.7);
                    border-radius: 16px;
                }
            """)
            title_color = "#60CDFF"
            close_btn_style = """
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.12);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 11px;
                }
                QPushButton:hover {
                    background-color: #E81123;
                    border: none;
                }
            """
            txt_edit_style = """
                QTextEdit {
                    background-color: rgba(0, 0, 0, 0.35);
                    color: #FFFFFF;
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 8px;
                    padding: 6px;
                    font-size: 12px;
                }
            """
            copy_btn_disabled = "background-color: rgba(255, 255, 255, 0.1); color: #777777;"
            status_pending_color = "#FFB900"
        else:
            self.card.setStyleSheet("""
                QFrame#TranslationCard {
                    background-color: rgba(255, 255, 255, 0.98);
                    border: 1px solid rgba(0, 120, 212, 0.4);
                    border-radius: 16px;
                }
            """)
            title_color = "#005A9E"
            close_btn_style = """
                QPushButton {
                    background-color: rgba(0, 0, 0, 0.06);
                    border: 1px solid rgba(0, 0, 0, 0.12);
                    border-radius: 11px;
                }
                QPushButton:hover {
                    background-color: #E81123;
                    border: none;
                }
            """
            txt_edit_style = """
                QTextEdit {
                    background-color: rgba(242, 244, 247, 0.95);
                    color: #1A1A1A;
                    border: 1px solid rgba(0, 0, 0, 0.15);
                    border-radius: 8px;
                    padding: 6px;
                    font-size: 12px;
                }
            """
            copy_btn_disabled = "background-color: rgba(0, 0, 0, 0.08); color: #999999;"
            status_pending_color = "#B27B00"

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180 if dark else 45))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(self.card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_icon = QLabel()
        if self.mode == "ocr":
            header_icon.setPixmap(get_minimalist_svg_pixmap("ocr", title_color, 16, 16))
            title_text = "OCR (Texto Extraído)"
            copy_btn_text = " Copiar Texto"
        else:
            header_icon.setPixmap(get_minimalist_svg_pixmap("globe", title_color, 16, 16))
            title_text = f"Traductor ({self.from_lang.upper()} ➔ {self.to_lang.upper()})"
            copy_btn_text = " Copiar Traducción"

        self.lbl_title = QLabel(title_text)
        self.lbl_title.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet(f"color: {title_color};")

        btn_close = QPushButton()
        btn_close.setIcon(get_minimalist_svg_icon("close", "#FFFFFF" if dark else "#1A1A1A", 12))
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(close_btn_style)
        btn_close.clicked.connect(self.fade_out_and_destroy)

        header_layout.addWidget(header_icon)
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(btn_close)

        status_row = QHBoxLayout()
        self.status_icon = QLabel()
        self.status_icon.setPixmap(get_minimalist_svg_pixmap("lightning", status_pending_color, 14, 14))

        self.lbl_status = QLabel("Analizando imagen...")
        self.lbl_status.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet(f"color: {status_pending_color};")

        status_row.addWidget(self.status_icon)
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()

        self.txt_display = QTextEdit()
        self.txt_display.setReadOnly(True)
        self.txt_display.setFixedHeight(100)
        self.txt_display.setPlaceholderText("Procesando...")
        self.txt_display.setStyleSheet(txt_edit_style)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(8)

        self.btn_copy = QPushButton(copy_btn_text)
        self.btn_copy.setIcon(get_minimalist_svg_icon("copy", "#FFFFFF", 14))
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setEnabled(False)
        self.btn_copy.setStyleSheet(f"""
            QPushButton {{
                background-color: #0078D4; color: white; border: none;
                border-radius: 8px; padding: 6px 14px; font-weight: bold; font-size: 11px;
            }}
            QPushButton:disabled {{ {copy_btn_disabled} }}
            QPushButton:hover:enabled {{ background-color: #106EBE; }}
        """)
        self.btn_copy.clicked.connect(self.copy_translation)

        self.actions_layout.addWidget(self.btn_copy)
        self.actions_layout.addStretch()

        c_layout.addLayout(header_layout)
        c_layout.addLayout(status_row)
        c_layout.addWidget(self.txt_display)
        c_layout.addLayout(self.actions_layout)

        layout.addWidget(self.card)
        self.setMinimumSize(280, 210)
        self.resize(330, 230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def position_near(self, pos: QPoint):
        global _LAST_TRANSLATION_CARD_POS
        screen = QApplication.primaryScreen()
        if not screen:
            return

        geo = screen.availableGeometry()

        if _LAST_TRANSLATION_CARD_POS is None:
            try:
                cfg_file = os.path.join(get_jade_appdata_dir(), "config.json")
                if os.path.exists(cfg_file):
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        saved = data.get("last_translation_card_pos")
                        if saved and isinstance(saved, (list, tuple)) and len(saved) == 2:
                            _LAST_TRANSLATION_CARD_POS = QPoint(int(saved[0]), int(saved[1]))
            except Exception:
                pass

        if _LAST_TRANSLATION_CARD_POS is not None:
            target_x = _LAST_TRANSLATION_CARD_POS.x()
            target_y = _LAST_TRANSLATION_CARD_POS.y()

            clamped_x = max(geo.left() + 10, min(target_x, geo.right() - 330 - 10))
            clamped_y = max(geo.top() + 10, min(target_y, geo.bottom() - 230 - 10))
            self.move(clamped_x, clamped_y)
            return

        x = pos.x() + 15
        y = pos.y() + 15
        if x + 330 > geo.right():
            x = pos.x() - 330 - 15
        if y + 230 > geo.bottom():
            y = pos.y() - 230 - 15
        self.move(max(geo.left() + 10, x), max(geo.top() + 10, y))

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            set_window_exclude_from_capture(hwnd)
            enable_win11_effects(hwnd, dark_mode=getattr(self, "is_dark_theme", True))
        except Exception:
            pass

        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(95)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

    def _step_anim(self):
        if not self.btn_copy.isEnabled():
            self.dot_count = (self.dot_count + 1) % 4
            dots = "." * self.dot_count
            base_txt = self.lbl_status.text().rstrip(".")
            if not base_txt: base_txt = "Procesando"
            self.lbl_status.setText(f"{base_txt}{dots}")

    def update_status(self, msg: str):
        self.lbl_status.setText(msg)

    def set_result(self, original: str, translation: str):
        if hasattr(self, "anim_timer") and self.anim_timer:
            self.anim_timer.stop()

        self.original_text = original
        self.translated_text = translation
        self.txt_display.setPlainText(translation)

        status_color = "#107C41" if getattr(self, "is_dark_theme", True) else "#0E703C"
        self.status_icon.setPixmap(get_minimalist_svg_pixmap("check", status_color, 14, 14))

        if self.mode == "ocr":
            self.lbl_status.setText("Texto Extraído")
        else:
            self.lbl_status.setText("Traducción Lista")

        self.lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        self.btn_copy.setEnabled(True)

    def set_error(self, err_msg: str):
        if hasattr(self, "anim_timer") and self.anim_timer:
            self.anim_timer.stop()

        status_color = "#E81123" if getattr(self, "is_dark_theme", True) else "#C42B1C"
        self.status_icon.setPixmap(get_minimalist_svg_pixmap("warning", status_color, 14, 14))

        if self.mode == "ocr":
            self.lbl_status.setText("Error al extraer texto")
        else:
            self.lbl_status.setText("Error en traducción")

        self.lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        self.txt_display.setPlainText(err_msg)

    def copy_translation(self):
        if self.translated_text:
            QApplication.clipboard().setText(self.translated_text)
            self.status_icon.setPixmap(get_minimalist_svg_pixmap("check", "#107C41", 14, 14))
            self.lbl_status.setText("¡Copiado!")
            QTimer.singleShot(350, self.fade_out_and_destroy)

    def fade_out_and_destroy(self):
        if self._is_closing:
            return
        self._is_closing = True

        if getattr(self, "_initialized", False):
            self._save_position_to_disk(self.pos())

        if hasattr(self, "anim_timer") and self.anim_timer:
            self.anim_timer.stop()

        self.out_anim = QPropertyAnimation(self, b"windowOpacity")
        self.out_anim.setDuration(85)
        self.out_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.out_anim.setStartValue(self.windowOpacity())
        self.out_anim.setEndValue(0.0)
        self.out_anim.finished.connect(self.close)
        self.out_anim.start()

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        self.is_dark_theme = is_dark
        if is_dark:
            if hasattr(self, "card") and self.card:
                self.card.setStyleSheet("""
                    QFrame#TranslationCard {
                        background-color: rgba(20, 24, 32, 0.96);
                        border: 1px solid rgba(0, 120, 212, 0.7);
                        border-radius: 16px;
                    }
                """)
            if hasattr(self, "lbl_title") and self.lbl_title:
                self.lbl_title.setStyleSheet("color: #60CDFF;")
            if hasattr(self, "txt_display") and self.txt_display:
                self.txt_display.setStyleSheet("""
                    QTextEdit {
                        background-color: rgba(0, 0, 0, 0.35);
                        color: #FFFFFF;
                        border: 1px solid rgba(255, 255, 255, 0.15);
                        border-radius: 8px;
                        padding: 6px;
                        font-size: 12px;
                    }
                """)
        else:
            if hasattr(self, "card") and self.card:
                self.card.setStyleSheet("""
                    QFrame#TranslationCard {
                        background-color: rgba(255, 255, 255, 0.98);
                        border: 1px solid rgba(0, 120, 212, 0.4);
                        border-radius: 16px;
                    }
                """)
            if hasattr(self, "lbl_title") and self.lbl_title:
                self.lbl_title.setStyleSheet("color: #0078D4;")
            if hasattr(self, "txt_display") and self.txt_display:
                self.txt_display.setStyleSheet("""
                    QTextEdit {
                        background-color: #FFFFFF;
                        color: #0F172A;
                        border: 1px solid rgba(0, 0, 0, 0.15);
                        border-radius: 8px;
                        padding: 6px;
                        font-size: 12px;
                    }
                """)

    def closeEvent(self, event):
        self._is_closing = True
        if getattr(self, "_initialized", False):
            self._save_position_to_disk(self.pos())
        if hasattr(self, "anim_timer") and self.anim_timer:
            self.anim_timer.stop()
        super().closeEvent(event)

class QuickTranslatorWindow(QDialog):
    """Ventana flotante de traducción instantánea en vivo (Español ➔ Inglés), con soporte de pegado y copia directa."""
    def __init__(self, from_lang: str = "es", to_lang: str = "en", parent=None):
        super().__init__(parent)
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.current_worker = None
        self._drag_pos = None
        self._request_id = 0
        self._is_destroyed = False

        self.setWindowTitle("Jade — Traductor Instantáneo")
        self.resize(440, 360)
        self.setMinimumSize(360, 300)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.init_ui()
        ThemeManager.get_instance().register_child(self)
        self.center_on_screen()

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(320)
        self.debounce_timer.timeout.connect(self._do_translate)

        self.reset_copy_btn_timer = QTimer(self)
        self.reset_copy_btn_timer.setSingleShot(True)
        self.reset_copy_btn_timer.setInterval(1400)
        self.reset_copy_btn_timer.timeout.connect(self._reset_copy_button_text)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos") and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def init_ui(self):
        dark = True
        try:
            config_path = os.path.join(get_jade_appdata_dir(), "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    theme_cfg = cfg.get("theme", "sistema")
                    if theme_cfg == "oscuro": dark = True
                    elif theme_cfg == "claro": dark = False
                    else: dark = (detect_windows_system_theme() == "oscuro")
        except Exception:
            dark = (detect_windows_system_theme() == "oscuro")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("QuickTranslatorCard")
        bg_col = "rgba(20, 24, 32, 0.97)" if dark else "rgba(255, 255, 255, 0.98)"
        border_col = "rgba(0, 120, 212, 0.7)" if dark else "rgba(0, 120, 212, 0.4)"
        card.setStyleSheet(f"""
            QFrame#QuickTranslatorCard {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 16px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180 if dark else 50))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(8)

        # Header con selectores de idioma y botón cerrar
        header = QHBoxLayout()
        icon_title = QLabel()
        icon_title.setPixmap(get_minimalist_svg_pixmap("globe", "#0078D4" if not dark else "#60CDFF", 16, 16))

        lbl_title = QLabel("Traductor")
        lbl_title.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #0078D4;" if not dark else "color: #60CDFF;")

        self.combo_from = QComboBox()
        self.combo_from.addItem("Español (ES)", "es")
        self.combo_from.addItem("Inglés (EN)", "en")
        self.combo_from.addItem("Francés (FR)", "fr")
        self.combo_from.addItem("Alemán (DE)", "de")
        self.combo_from.addItem("Italiano (IT)", "it")
        self.combo_from.addItem("Portugués (PT)", "pt")
        idx_from = self.combo_from.findData(self.from_lang)
        if idx_from >= 0: self.combo_from.setCurrentIndex(idx_from)
        self.combo_from.currentIndexChanged.connect(self._on_lang_changed)

        btn_swap = QPushButton()
        btn_swap.setIcon(get_minimalist_svg_icon("swap", "adaptive", 14))
        btn_swap.setToolTip("Intercambiar idiomas")
        btn_swap.setFixedSize(26, 24)
        btn_swap.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_swap.setStyleSheet("QPushButton { border-radius: 4px; padding: 2px; }")
        btn_swap.clicked.connect(self._swap_languages)

        self.combo_to = QComboBox()
        self.combo_to.addItem("Inglés (EN)", "en")
        self.combo_to.addItem("Español (ES)", "es")
        self.combo_to.addItem("Francés (FR)", "fr")
        self.combo_to.addItem("Alemán (DE)", "de")
        self.combo_to.addItem("Italiano (IT)", "it")
        self.combo_to.addItem("Portugués (PT)", "pt")
        idx_to = self.combo_to.findData(self.to_lang)
        if idx_to >= 0: self.combo_to.setCurrentIndex(idx_to)
        self.combo_to.currentIndexChanged.connect(self._on_lang_changed)

        btn_close = QPushButton()
        btn_close.setIcon(get_minimalist_svg_icon("close", "#FFFFFF" if dark else "#1A1A1A", 12))
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 11px;
            }
            QPushButton:hover {
                background-color: #E81123;
                border: none;
            }
        """ if dark else """
            QPushButton {
                background-color: rgba(0, 0, 0, 0.06);
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 11px;
            }
            QPushButton:hover {
                background-color: #E81123;
                border: none;
            }
        """)
        btn_close.clicked.connect(self.close)

        header.addWidget(icon_title)
        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(self.combo_from)
        header.addWidget(btn_swap)
        header.addWidget(self.combo_to)
        header.addWidget(btn_close)

        # Entrada de texto origen
        self.txt_source = QTextEdit()
        self.txt_source.setPlaceholderText("Escribe o pega texto aquí en español...")
        self.txt_source.setFixedHeight(95)
        self.txt_source.textChanged.connect(self._on_source_text_changed)

        # Salida de texto traducido
        self.txt_target = QTextEdit()
        self.txt_target.setPlaceholderText("La traducción aparecerá aquí...")
        self.txt_target.setReadOnly(True)
        self.txt_target.setFixedHeight(95)

        # Barra de estado y acciones
        actions = QHBoxLayout()
        self.lbl_status = QLabel("Listo")
        self.lbl_status.setFont(QFont("Segoe UI Variable Text", 9))
        self.lbl_status.setStyleSheet("color: #8A8A8A;")

        self.btn_clear = QPushButton(" Limpiar")
        self.btn_clear.setIcon(get_minimalist_svg_icon("trash", "adaptive", 14))
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet("padding: 5px 10px; font-size: 11px;")
        self.btn_clear.clicked.connect(self._clear_all)

        self.btn_copy = QPushButton(" Copiar Traducción")
        self.btn_copy.setIcon(get_minimalist_svg_icon("copy", "#FFFFFF", 14))
        self.btn_copy.setObjectName("PrimaryBtn")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setStyleSheet("background-color: #0078D4; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px;")
        self.btn_copy.clicked.connect(self._copy_result)

        actions.addWidget(self.lbl_status)
        actions.addStretch()
        actions.addWidget(self.btn_clear)
        actions.addWidget(self.btn_copy)

        c_layout.addLayout(header)
        c_layout.addWidget(self.txt_source)
        c_layout.addWidget(self.txt_target)
        c_layout.addLayout(actions)

        main_layout.addWidget(card)

    def _swap_languages(self):
        f_idx = self.combo_from.currentIndex()
        t_idx = self.combo_to.currentIndex()
        self.combo_from.blockSignals(True)
        self.combo_to.blockSignals(True)
        self.combo_from.setCurrentIndex(t_idx)
        self.combo_to.setCurrentIndex(f_idx)
        self.combo_from.blockSignals(False)
        self.combo_to.blockSignals(False)
        self._on_lang_changed()

    def _on_lang_changed(self):
        self.from_lang = self.combo_from.currentData() or "es"
        self.to_lang = self.combo_to.currentData() or "en"
        self._on_source_text_changed()

    def _on_source_text_changed(self):
        text = self.txt_source.toPlainText().strip()
        if not text:
            self.txt_target.clear()
            self.lbl_status.setText("Listo")
            return
        self.lbl_status.setText("Traduciendo...")
        self.debounce_timer.start()

    def _do_translate(self):
        text = self.txt_source.toPlainText().strip()
        if not text:
            return

        self._request_id += 1
        current_req = self._request_id

        worker = ArgosTranslatorWorker(direct_text=text, from_code=self.from_lang, to_code=self.to_lang, parent=self)
        self.current_worker = worker

        def _success(orig, trans):
            if not self._is_destroyed and current_req == self._request_id:
                self.txt_target.setPlainText(trans)
                self.lbl_status.setText("Traducido")

        def _fail(err):
            if not self._is_destroyed and current_req == self._request_id:
                self.txt_target.setPlainText(err)
                self.lbl_status.setText("Error")

        worker.finished.connect(_success)
        worker.error.connect(_fail)
        worker.start()

    def _clear_all(self):
        self._request_id += 1
        self.txt_source.clear()
        self.txt_target.clear()
        self.lbl_status.setText("Listo")
        self.txt_source.setFocus()

    def _reset_copy_button_text(self):
        if not self._is_destroyed and hasattr(self, "btn_copy") and self.btn_copy:
            try:
                self.btn_copy.setIcon(get_minimalist_svg_icon("copy", "#FFFFFF", 14))
                self.btn_copy.setText(" Copiar Traducción")
            except Exception:
                pass

    def _copy_result(self):
        text = self.txt_target.toPlainText().strip()
        if text:
            cb = QApplication.clipboard()
            cb.setText(text)
            self.btn_copy.setIcon(get_minimalist_svg_icon("check", "#FFFFFF", 14))
            self.btn_copy.setText(" ¡Copiado!")
            self.reset_copy_btn_timer.start()

    def closeEvent(self, event):
        self._is_destroyed = True
        if hasattr(self, "debounce_timer") and self.debounce_timer.isActive():
            self.debounce_timer.stop()
        if hasattr(self, "reset_copy_btn_timer") and self.reset_copy_btn_timer.isActive():
            self.reset_copy_btn_timer.stop()
        super().closeEvent(event)

class ArgosPrewarmerThread(QThread):
    """Verificación pasiva sin precarga en memoria para mantener el consumo de RAM en niveles mínimos."""
    def run(self):
        global _ARGOS_MODULE_READY
        _ARGOS_MODULE_READY = False
        log_message("[ARGOS LITE] Motor configurado para carga bajo demanda (On-Demand) para optimizar memoria RAM.")

class ArgosTranslatorWorker(QThread):
    """Hilo ultra-optimizado para procesar OCR + Traducción instantánea híbrida (Online / Offline con recursos descargados)."""
    finished = pyqtSignal(str, str)
    status_updated = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pixmap=None, direct_text: str = None, from_code: str = "en", to_code: str = "es", parent=None):
        super().__init__(parent)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.image = pixmap.toImage()
        elif isinstance(pixmap, QImage):
            self.image = pixmap
        else:
            self.image = None

        if pixmap is not None and direct_text in ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh"]:
            self.from_code = direct_text
            self.to_code = from_code if from_code not in ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh"] or from_code != "en" else to_code
            self.direct_text = None
        else:
            self.direct_text = direct_text
            self.from_code = from_code or "en"
            self.to_code = to_code or "es"

    def run(self):
        global _ARGOS_TRANSLATION_CACHE, _ARGOS_MODULE_READY
        log_message("=== INICIANDO TRADUCCIÓN RÁPIDA JADE ===")
        t_start = time.time()
        try:
            if self.direct_text and self.direct_text.strip():
                ocr_text = self.direct_text.strip()
            else:
                self.status_updated.emit("⚡ Extrayendo texto (OCR)...")
                ocr_text = perform_direct_ocr(self.image)

            if not ocr_text or ocr_text == "REQUIRES_LITE_OCR_INSTALL" or ocr_text.startswith("No se"):
                self.error.emit("No se detectó texto reconocible.")
                return

            self.status_updated.emit("🚀 Traduciendo...")
            translated_text = ""

            # Capa 1: Google Translate API vía POST (soporta textos largos y caracteres especiales sin límite)
            try:
                import urllib.request
                import urllib.parse
                import ssl

                ctx = ssl._create_unverified_context()
                post_payload = urllib.parse.urlencode({
                    "client": "gtx",
                    "sl": self.from_code,
                    "tl": self.to_code,
                    "dt": "t",
                    "q": ocr_text
                }).encode("utf-8")

                req_post = urllib.request.Request(
                    "https://translate.googleapis.com/translate_a/single",
                    data=post_payload,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
                    }
                )
                with urllib.request.urlopen(req_post, context=ctx, timeout=6.0) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    if res_data and isinstance(res_data, list) and len(res_data) > 0 and isinstance(res_data[0], list):
                        chunks = [item[0] for item in res_data[0] if isinstance(item, list) and len(item) > 0 and item[0]]
                        translated_text = "".join(chunks).strip()
            except Exception as e_post:
                log_message(f"Capa 1 (Google POST) falló: {e_post}")

            # Capa 2: Google Chrome Client API Espejo
            if not translated_text:
                try:
                    import urllib.request
                    import urllib.parse
                    import ssl

                    ctx = ssl._create_unverified_context()
                    url_c5 = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={self.from_code}&tl={self.to_code}&q=" + urllib.parse.quote(ocr_text)
                    req_c5 = urllib.request.Request(url_c5, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    with urllib.request.urlopen(req_c5, context=ctx, timeout=5.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        if isinstance(data, list) and len(data) > 0:
                            if isinstance(data[0], str):
                                translated_text = " ".join(data).strip()
                            elif isinstance(data[0], list) and len(data[0]) > 0:
                                translated_text = "".join([str(x[0]) for x in data[0] if isinstance(x, list) and x]).strip()
                except Exception as e_c5:
                    log_message(f"Capa 2 (Google Chrome API) falló: {e_c5}")

            # Capa 3: MyMemory Translation API
            if not translated_text:
                try:
                    import urllib.request
                    import urllib.parse
                    import ssl

                    ctx = ssl._create_unverified_context()
                    url_mm = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(ocr_text[:1200])}&langpair={self.from_code}|{self.to_code}"
                    req_mm = urllib.request.Request(url_mm, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    with urllib.request.urlopen(req_mm, context=ctx, timeout=5.0) as resp:
                        mm_data = json.loads(resp.read().decode("utf-8"))
                        res_match = mm_data.get("responseData", {}).get("translatedText", "")
                        if res_match and not res_match.startswith("MYMEMORY WARNING"):
                            translated_text = res_match.strip()
                except Exception as e_mm:
                    log_message(f"Capa 3 (MyMemory) falló: {e_mm}")

            # Capa 4: Paquetes locales Argos Translate Offline
            if not translated_text:
                try:
                    import importlib
                    argostranslate_tr = importlib.import_module("argostranslate.translate")
                    argostranslate_pkg = importlib.import_module("argostranslate.package")

                    cache_key = f"{self.from_code}_{self.to_code}"
                    translation = _ARGOS_TRANSLATION_CACHE.get(cache_key)

                    if not translation:
                        appdata_dir = get_jade_appdata_dir()
                        models_dir = os.path.join(appdata_dir, "argos_models")
                        if os.path.exists(models_dir):
                            for fname in os.listdir(models_dir):
                                if fname.endswith(".argosmodel") and f"{self.from_code}_{self.to_code}" in fname:
                                    pkg_file = os.path.join(models_dir, fname)
                                    try:
                                        argostranslate_pkg.install_from_path(pkg_file)
                                    except Exception:
                                        pass
                                    break

                        installed_langs = argostranslate_tr.get_installed_languages()
                        from_lang_obj = next((l for l in installed_langs if l.code == self.from_code), None)
                        to_lang_obj = next((l for l in installed_langs if l.code == self.to_code), None)

                        if from_lang_obj and to_lang_obj:
                            translation = from_lang_obj.get_translation(to_lang_obj)
                            if translation:
                                _ARGOS_TRANSLATION_CACHE[cache_key] = translation

                    if translation:
                        translated_text = translation.translate(ocr_text)
                except Exception as e_argos:
                    log_message(f"Capa 4 (Argos Offline) falló: {e_argos}")

            if translated_text:
                elapsed = time.time() - t_start
                log_message(f"=== TRADUCCIÓN COMPLETA EN {elapsed:.2f} SEGUNDOS ({len(translated_text)} chars) ===")
                self.finished.emit(ocr_text, translated_text)
            else:
                self.error.emit("No se pudo conectar al servicio de traducción ni cargar el paquete descargado.")

        except Exception as e:
            log_message(f"=== EXCEPCIÓN TRADUCTOR: {e} ===")
            self.error.emit(f"Error: {str(e)}")
        finally:
            self.image = None
            import gc
            gc.collect()

class VideoAnnotationHUD(QWidget):
    """Mini barra indicadora flotante no grabable (excluida de capturas en video)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.border_color = QColor(232, 17, 35, 200)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(620, 42)

    def set_color(self, color: QColor):
        self.border_color = QColor(color.red(), color.green(), color.blue(), 220)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            set_window_exclude_from_capture(hwnd)
            SWP_NOACTIVATE = 0x0010
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass

    def position_at_top(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + 15
            self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        path = QPainterPath()
        path.addRoundedRect(rect, 12.0, 12.0)

        painter.fillPath(path, QColor(20, 22, 28, 230))
        painter.setPen(QPen(self.border_color, 2.0))
        painter.drawPath(path)

        icon_pix = get_minimalist_svg_pixmap("edit_pen", "#FFFFFF", 16, 16)
        painter.drawPixmap(int(rect.x() + 14), int(rect.y() + (rect.height() - 16) / 2), icon_pix)

        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold))
        text_rect = QRectF(rect.x() + 36, rect.y(), rect.width() - 40, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "DIBUJO EN VIVO - Arrastra para señalar | [Ctrl+Shift+D] Salir | [Ctrl+Shift+E] Borrar")

class VideoAnnotationOverlay(QWidget):
    """Superposición transparente de anotaciones en vivo (flechas/líneas) grabables para video."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

        self.start_pt = QPointF()
        self.end_pt = QPointF()
        self.is_drawing = False
        self.click_through = False
        self.annotations = []
        self.current_color = QColor(232, 17, 35)
        self.line_width = 5
        self.hud = VideoAnnotationHUD()
        self._fade_anim = None

        self.reload_config_color()

        QShortcut(QKeySequence("Ctrl+Shift+E"), self, self.clear_annotations)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.clear_annotations)

    def reload_config_color(self):
        try:
            config_path = os.path.expanduser(r"~\AppData\Roaming\Jade\config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    hex_col = cfg.get("draw_color", "#E81123")
                    self.current_color = QColor(hex_col)
        except Exception:
            self.current_color = QColor(232, 17, 35)

        if hasattr(self, "hud") and self.hud:
            self.hud.set_color(self.current_color)

    def set_click_through_mode(self, enable: bool):
        self.click_through = enable
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enable)
        try:
            hwnd = int(self.winId())
            set_window_click_through(hwnd, enable)
        except Exception:
            pass

        if enable:
            self.unsetCursor()
            if hasattr(self, "hud") and self.hud:
                self.hud.hide()
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)
            if hasattr(self, "hud") and self.hud:
                self.hud.position_at_top()
                self.hud.show()

    def showEvent(self, event):
        super().showEvent(event)
        self.reload_config_color()
        self.setWindowOpacity(1.0)
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        except Exception:
            pass

    def draw_arrow_head(self, p1: QPointF, p2: QPointF, width: float) -> QPolygonF:
        line = QLineF(p1, p2)
        if line.length() < 5:
            return QPolygonF()
        angle = math.atan2(-line.dy(), line.dx())
        arrow_size = max(18, width * 3.8)

        pt1 = line.p2() - QPointF(math.cos(angle + math.pi / 6) * arrow_size, -math.sin(angle + math.pi / 6) * arrow_size)
        pt2 = line.p2() - QPointF(math.cos(angle - math.pi / 6) * arrow_size, -math.sin(angle - math.pi / 6) * arrow_size)

        return QPolygonF([line.p2(), pt1, pt2])

    def clear_annotations(self):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        if hasattr(self, "_fade_anim") and self._fade_anim and self._fade_anim.state() == QPropertyAnimation.State.Running:
            return

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(220)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _on_fade_finished():
            self.annotations.clear()
            self.is_drawing = False
            self.setWindowOpacity(1.0)
            if hasattr(self, "hud") and self.hud:
                self.hud.hide()
            self.hide()

        self._fade_anim.finished.connect(_on_fade_finished)
        self._fade_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.click_through:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        for line, poly, col, w in self.annotations:
            pen = QPen(col, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(line)
            if not poly.isEmpty():
                painter.setBrush(QBrush(col))
                painter.drawPolygon(poly)

        if self.is_drawing:
            pen = QPen(self.current_color, self.line_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            line = QLineF(self.start_pt, self.end_pt)
            painter.drawLine(line)

            poly = self.draw_arrow_head(self.start_pt, self.end_pt, self.line_width)
            if not poly.isEmpty():
                painter.setBrush(QBrush(self.current_color))
                painter.drawPolygon(poly)

    def mousePressEvent(self, event):
        if not self.click_through:
            if event.button() == Qt.MouseButton.RightButton:
                self.clear_annotations()
                event.accept()
                return
            elif event.button() == Qt.MouseButton.LeftButton:
                self.start_pt = event.position()
                self.end_pt = self.start_pt
                self.is_drawing = True
                self.update()

    def mouseMoveEvent(self, event):
        if not self.click_through and self.is_drawing:
            self.end_pt = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if not self.click_through and event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            self.end_pt = event.position()
            line = QLineF(self.start_pt, self.end_pt)
            if line.length() > 8:
                poly = self.draw_arrow_head(self.start_pt, self.end_pt, self.line_width)
                self.annotations.append((line, poly, QColor(self.current_color), self.line_width))
            self.update()
            self.set_click_through_mode(True)

    def closeEvent(self, event):
        if hasattr(self, "hud") and self.hud:
            try:
                self.hud.close()
                self.hud.deleteLater()
            except Exception:
                pass
            self.hud = None
        super().closeEvent(event)

class SnippingOverlay(QWidget):
    """Superposición de selección de recorte de pantalla con respuesta instantánea a 0 ms."""
    area_captured = pyqtSignal(QPixmap, QRect)
    canceled = pyqtSignal()

    def __init__(self, full_desktop_pixmap: QPixmap):
        super().__init__()
        self.full_pixmap = full_desktop_pixmap
        self.begin_point = QPoint()
        self.end_point = QPoint()
        self.is_selecting = False
        self.selected_rect = QRect()
        self._is_closing = False
        self._fade_anim = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(0.0)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.cancel)

    def _fade_in(self):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        if self._fade_anim and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(80)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def _fade_out_and_finish(self, on_finished_callback):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        if self._is_closing:
            return
        self._is_closing = True
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        if self._fade_anim and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(70)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_anim.finished.connect(lambda: (on_finished_callback(), self.close()))
        self._fade_anim.start()

    def cancel(self):
        if self._is_closing:
            return
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self._fade_out_and_finish(self.canceled.emit)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
        except Exception:
            pass
        self.raise_()
        self.activateWindow()
        self.setFocus()
        try:
            self.grabKeyboard()
        except Exception:
            pass
        if not self._is_closing:
            self._fade_in()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.full_pixmap)

        overlay_color = QColor(0, 0, 0, 140)

        if self.selected_rect.isValid() and not self.selected_rect.isEmpty():
            rx = self.selected_rect.x()
            ry = self.selected_rect.y()
            rw = self.selected_rect.width()
            rh = self.selected_rect.height()
            w = self.width()
            h = self.height()

            # Cuatro rectángulos rápidos sin cálculo de regiones booleanas
            painter.fillRect(0, 0, w, ry, overlay_color)
            painter.fillRect(0, ry + rh, w, h - (ry + rh), overlay_color)
            painter.fillRect(0, ry, rx, rh, overlay_color)
            painter.fillRect(rx + rw, ry, w - (rx + rw), rh, overlay_color)

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(0, 120, 212), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.selected_rect)

            dim_text = f" {rw} × {rh} px "
            painter.setFont(QFont("Segoe UI Variable Text", 10, QFont.Weight.Bold))
            text_rect = painter.fontMetrics().boundingRect(dim_text)

            tx = rx
            ty = ry - text_rect.height() - 8
            if ty < 10:
                ty = ry + 10

            bg_rect = QRect(tx, ty, text_rect.width() + 10, text_rect.height() + 6)
            painter.setBrush(QColor(20, 20, 20, 230))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bg_rect, 6, 6)

            painter.setPen(QColor(255, 255, 255))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, dim_text)
        else:
            painter.fillRect(self.rect(), overlay_color)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI Variable Display", 14, QFont.Weight.DemiBold))
            guide_text = "Arrastra para seleccionar un área  •  [ESC] para cancelar"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, guide_text)

    def mousePressEvent(self, event):
        if self._is_closing:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_point = event.pos()
            self.end_point = self.begin_point
            self.is_selecting = True
            self.selected_rect = QRect()
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_closing:
            return
        if self.is_selecting:
            self.end_point = event.pos()
            self.selected_rect = QRect(self.begin_point, self.end_point).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if self._is_closing:
            return
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end_point = event.pos()
            self.selected_rect = QRect(self.begin_point, self.end_point).normalized()

            if self.selected_rect.width() > 10 and self.selected_rect.height() > 10:
                scale_x = self.full_pixmap.width() / max(self.width(), 1)
                scale_y = self.full_pixmap.height() / max(self.height(), 1)

                crop_rect = QRect(
                    int(self.selected_rect.x() * scale_x),
                    int(self.selected_rect.y() * scale_y),
                    int(self.selected_rect.width() * scale_x),
                    int(self.selected_rect.height() * scale_y)
                )
                cropped = self.full_pixmap.copy(crop_rect)

                def emit_area():
                    self.area_captured.emit(cropped, self.selected_rect)

                self._fade_out_and_finish(emit_area)
            else:
                self.selected_rect = QRect()
                self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
        else:
            super().keyPressEvent(event)
class AreaSelectionOverlay(QWidget):
    """Superposición dedicada para arrastrar y seleccionar área de grabación."""
    area_selected = pyqtSignal(QRect)
    canceled = pyqtSignal()

    def __init__(self, full_desktop_pixmap: QPixmap):
        super().__init__()
        self.full_pixmap = full_desktop_pixmap
        self.begin_point = QPoint()
        self.end_point = QPoint()
        self.is_selecting = False
        self.selected_rect = QRect()
        self._is_closing = False
        self._fade_anim = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(0.0)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.cancel)

    def _fade_in(self):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        if self._fade_anim and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(140)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def _fade_out_and_finish(self, on_finished_callback):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        if self._is_closing:
            return
        self._is_closing = True
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        if self._fade_anim and self._fade_anim.state() == QPropertyAnimation.State.Running:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(120)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(lambda: (on_finished_callback(), self.close()))
        self._fade_anim.start()

    def cancel(self):
        if self._is_closing:
            return
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self._fade_out_and_finish(self.canceled.emit)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
        except Exception:
            pass
        self.raise_()
        self.activateWindow()
        self.setFocus()
        try:
            self.grabKeyboard()
        except Exception:
            pass
        if not self._is_closing:
            self._fade_in()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(self.rect(), self.full_pixmap)

        overlay_color = QColor(0, 0, 0, 140)

        if self.selected_rect.isValid() and not self.selected_rect.isEmpty():
            from PyQt6.QtGui import QRegion
            full_region = QRegion(self.rect())
            select_region = QRegion(self.selected_rect)
            dark_region = full_region.subtracted(select_region)

            painter.setClipRegion(dark_region)
            painter.fillRect(self.rect(), overlay_color)
            painter.setClipping(False)

            pen = QPen(QColor(16, 124, 65), 3, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.selected_rect)

            dim_text = f" Área de Grabación Jade: {self.selected_rect.width()} × {self.selected_rect.height()} px  (Presiona ENTER para confirmar) "
            painter.setFont(QFont("Segoe UI Variable Text", 10, QFont.Weight.Bold))
            text_rect = painter.fontMetrics().boundingRect(dim_text)

            tx = self.selected_rect.x()
            ty = self.selected_rect.y() - text_rect.height() - 8
            if ty < 10:
                ty = self.selected_rect.y() + 10

            bg_rect = QRect(tx, ty, text_rect.width() + 10, text_rect.height() + 6)
            painter.setBrush(QColor(20, 20, 20, 230))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bg_rect, 6, 6)

            painter.setPen(QColor(255, 255, 255))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, dim_text)
        else:
            painter.fillRect(self.rect(), overlay_color)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI Variable Display", 14, QFont.Weight.DemiBold))
            guide_text = "Arrastra para seleccionar el área de GRABACIÓN  •  [ENTER] Pantalla Completa  •  [ESC] Cancelar"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, guide_text)

    def mousePressEvent(self, event):
        if self._is_closing:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_point = event.pos()
            self.end_point = self.begin_point
            self.is_selecting = True
            self.selected_rect = QRect()
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_closing:
            return
        if self.is_selecting:
            self.end_point = event.pos()
            self.selected_rect = QRect(self.begin_point, self.end_point).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if self._is_closing:
            return
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end_point = event.pos()
            self.selected_rect = QRect(self.begin_point, self.end_point).normalized()
            self.update()

    def keyPressEvent(self, event):
        if self._is_closing:
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.selected_rect.isValid() and self.selected_rect.width() > 10 and self.selected_rect.height() > 10:
                target_rect = self.selected_rect
            else:
                target_rect = QRect(0, 0, self.full_pixmap.width(), self.full_pixmap.height())

            def emit_selected():
                self.area_selected.emit(target_rect)

            self._fade_out_and_finish(emit_selected)
            event.accept()
        else:
            super().keyPressEvent(event)

from reproductor import HDMediaViewerDialog

def clear_thumb_cache():
    pass

def create_audio_thumbnail_pixmap(width: int = 170, height: int = 130) -> QPixmap:
    """Genera una miniatura gráfica elegante con un icono SVG vectorial de audio y degradado."""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    from PyQt6.QtGui import QLinearGradient
    grad = QLinearGradient(0, 0, float(width), float(height))
    grad.setColorAt(0.0, QColor(24, 28, 38))
    grad.setColorAt(1.0, QColor(12, 14, 22))

    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, float(width), float(height)), 10.0, 10.0)
    painter.fillPath(path, QBrush(grad))

    painter.setPen(QPen(QColor(255, 185, 0, 90), 1.5))
    painter.drawPath(path)

    svg_audio_xml = """<svg viewBox="0 0 24 24" fill="none" stroke="#FFB900" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 18V5l12-2v13"></path>
        <circle cx="6" cy="18" r="3"></circle>
        <circle cx="18" cy="16" r="3"></circle>
    </svg>"""

    icon_size = float(min(width, height) * 0.46)
    if HAS_SVG_SUPPORT:
        try:
            renderer = QSvgRenderer(svg_audio_xml.encode("utf-8"))
            icon_x = (width - icon_size) / 2.0
            icon_y = (height - icon_size) / 2.0
            renderer.render(painter, QRectF(icon_x, icon_y, icon_size, icon_size))
        except Exception:
            pass

    painter.end()
    return pixmap

class GalleryCard(QFrame):
    """Elemento de galería 100% responsivo y adaptativo que ajusta dinámicamente sus botones al tamaño de cualquier ventana."""
    delete_requested = pyqtSignal(str)
    ocr_requested = pyqtSignal(QPixmap)
    preview_requested = pyqtSignal(str)
    copy_requested = pyqtSignal()
    rename_requested = pyqtSignal(str)

    def __init__(self, item_path: str, parent=None):
        super().__init__(parent)
        self.item_path = item_path
        self.is_video = item_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))
        self.is_audio = item_path.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))

        cached_pix = get_cached_media_thumbnail(item_path)
        if self.is_audio:
            self.thumb_pixmap = create_audio_thumbnail_pixmap(120, 70)
            self.needs_worker = False
        elif not cached_pix.isNull():
            self.thumb_pixmap = overlay_play_icon(cached_pix) if self.is_video else cached_pix
            self.needs_worker = False
        else:
            self.thumb_pixmap = QPixmap()
            self.needs_worker = True

        self.setObjectName("GalleryCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(80)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.init_ui()

        if self.needs_worker:
            runnable = ThumbnailRunnable(self.item_path)
            runnable.signals.finished.connect(self._on_thumbnail_ready)
            QThreadPool.globalInstance().start(runnable)

    def _on_thumbnail_ready(self, vpath: str, raw_pixmap: QPixmap):
        if not raw_pixmap.isNull():
            self.thumb_pixmap = overlay_play_icon(raw_pixmap) if self.is_video else raw_pixmap
            scaled = self.thumb_pixmap.scaled(
                120, 70,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setText("")
            self.preview_label.setPixmap(scaled)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(70, 48)
        self.preview_label.setMaximumSize(120, 70)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border-radius: 8px; background-color: rgba(0,0,0,0.2); border: 1px solid rgba(128,128,128,0.2);")

        if not self.thumb_pixmap.isNull():
            scaled = self.thumb_pixmap.scaled(
                120, 70,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
        else:
            if self.is_audio:
                self.preview_label.setText("Audio")
            elif self.is_video:
                self.preview_label.setText("Video")
            else:
                self.preview_label.setText("Imagen")
            self.preview_label.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold))

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        info_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        file_name = os.path.basename(self.item_path)
        lbl_filename = QLabel(file_name)
        lbl_filename.setObjectName("PrimaryTextLabel")
        lbl_filename.setWordWrap(True)
        lbl_filename.setMinimumWidth(0)
        lbl_filename.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_filename.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.DemiBold))

        file_info = Path(self.item_path)
        try:
            modified_time = datetime.fromtimestamp(file_info.stat().st_mtime).strftime("%d/%m/%Y • %I:%M %p")
        except Exception:
            modified_time = "--/--/----"

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

        if self.is_audio:
            tag_text = "MP3 320K"
            badge_style = "background-color: rgba(255,185,0,0.2); color: #FFB900; border: 1px solid rgba(255,185,0,0.4); border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: bold;"
        elif self.is_video:
            tag_text = "MP4 60FPS"
            badge_style = "background-color: rgba(16,124,65,0.2); color: #107C41; border: 1px solid rgba(16,124,65,0.4); border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: bold;"
        else:
            tag_text = "PNG HD"
            badge_style = "background-color: rgba(0,120,212,0.2); color: #0078D4; border: 1px solid rgba(0,120,212,0.4); border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: bold;"

        lbl_badge = QLabel(tag_text)
        lbl_badge.setStyleSheet(badge_style)

        cal_icon = QLabel()
        cal_icon.setPixmap(get_minimalist_svg_pixmap("calendar", "adaptive", 12, 12))

        lbl_meta = QLabel(modified_time)
        lbl_meta.setObjectName("SubTextLabel")
        lbl_meta.setStyleSheet("font-size: 11px;")

        meta_row.addWidget(lbl_badge)
        meta_row.addWidget(cal_icon)
        meta_row.addWidget(lbl_meta)
        meta_row.addStretch()

        info_box.addWidget(lbl_filename)
        info_box.addLayout(meta_row)

        top_row.addWidget(self.preview_label)
        top_row.addLayout(info_box, stretch=1)

        self.actions_box = QHBoxLayout()
        self.actions_box.setSpacing(4)
        self.actions_box.setContentsMargins(0, 0, 0, 0)

        icon_copy = get_minimalist_svg_icon("copy", "#FFFFFF", 15)
        icon_ocr = get_minimalist_svg_icon("ocr", "adaptive", 15)
        icon_play = get_minimalist_svg_icon("play", "adaptive", 15)
        icon_folder = get_minimalist_svg_icon("folder", "adaptive", 15)
        icon_move = get_minimalist_svg_icon("move", "adaptive", 15)
        icon_rename = get_minimalist_svg_icon("rename", "adaptive", 15)
        is_dark_now = ThemeManager.get_instance().is_dark
        icon_delete = get_minimalist_svg_icon("delete", "#FF99A4" if is_dark_now else "#C42B1C", 15)

        self.btn_copy = QPushButton(" Copiar")
        self.btn_copy.setIcon(icon_copy)
        self.btn_copy.setToolTip("Copiar archivo al portapapeles")
        self.btn_copy.setObjectName("PrimaryBtn")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setMinimumWidth(0)
        self.btn_copy.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)

        if self.is_audio or self.is_video:
            self.btn_action = QPushButton(" Reproducir")
            self.btn_action.setIcon(icon_play)
            self.btn_action.setToolTip("Reproducir archivo")
            self.btn_action.setObjectName("SecondaryBtn")
            self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_action.setMinimumWidth(0)
            self.btn_action.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.btn_action.clicked.connect(lambda: self.preview_requested.emit(self.item_path))
        else:
            self.btn_action = QPushButton(" OCR")
            self.btn_action.setIcon(icon_ocr)
            self.btn_action.setToolTip("Extraer texto mediante OCR")
            self.btn_action.setObjectName("SecondaryBtn")
            self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_action.setMinimumWidth(0)
            self.btn_action.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.btn_action.clicked.connect(self.request_ocr_on_demand)

        self.btn_folder = QPushButton(" Ubicación")
        self.btn_folder.setIcon(icon_folder)
        self.btn_folder.setToolTip("Abrir carpeta contenedora")
        self.btn_folder.setObjectName("SecondaryBtn")
        self.btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_folder.setMinimumWidth(0)
        self.btn_folder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_folder.clicked.connect(self.open_file_folder)

        self.btn_move = QPushButton(" Mover")
        self.btn_move.setIcon(icon_move)
        self.btn_move.setObjectName("SecondaryBtn")
        self.btn_move.setToolTip("Copiar o mover archivo físico a otro directorio")
        self.btn_move.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_move.setMinimumWidth(0)
        self.btn_move.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_move.clicked.connect(self.move_to_directory)

        self.btn_rename = QPushButton()
        self.btn_rename.setIcon(icon_rename)
        self.btn_rename.setObjectName("SecondaryBtn")
        self.btn_rename.setToolTip("Renombrar archivo")
        self.btn_rename.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rename.setMinimumWidth(28)
        self.btn_rename.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_rename.clicked.connect(lambda: self.rename_requested.emit(self.item_path))

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(icon_delete)
        self.btn_delete.setObjectName("DangerBtn")
        self.btn_delete.setToolTip("Eliminar elemento")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setMinimumWidth(28)
        self.btn_delete.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.item_path))

        self.actions_box.addWidget(self.btn_copy)
        self.actions_box.addWidget(self.btn_action)
        self.actions_box.addWidget(self.btn_folder)
        self.actions_box.addWidget(self.btn_move)
        self.actions_box.addWidget(self.btn_rename)
        self.actions_box.addWidget(self.btn_delete)

        main_layout.addLayout(top_row)
        main_layout.addLayout(self.actions_box)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        is_media = (self.is_audio or self.is_video)

        if w < 380:
            self.btn_copy.setText("")
            self.btn_action.setText("")
            self.btn_folder.setText("")
            self.btn_move.setText("")
            self.actions_box.setSpacing(3)
        elif w < 480:
            self.btn_copy.setText(" Copiar")
            self.btn_action.setText("")
            self.btn_folder.setText("")
            self.btn_move.setText("")
            self.actions_box.setSpacing(4)
        elif w < 560:
            self.btn_copy.setText(" Copiar")
            self.btn_action.setText(" Reproducir" if is_media else " OCR")
            self.btn_folder.setText(" Ubicación")
            self.btn_move.setText("")
            self.actions_box.setSpacing(4)
        else:
            self.btn_copy.setText(" Copiar")
            self.btn_action.setText(" Reproducir" if is_media else " OCR")
            self.btn_folder.setText(" Ubicación")
            self.btn_move.setText(" Mover")
            self.actions_box.setSpacing(6)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.preview_requested.emit(self.item_path)
        super().mousePressEvent(event)

    def copy_to_clipboard(self):
        if self.is_video or self.is_audio:
            from PyQt6.QtCore import QMimeData, QUrl
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(os.path.abspath(self.item_path))])
            QApplication.clipboard().setMimeData(mime_data)
        else:
            if os.path.exists(self.item_path):
                abs_path = os.path.abspath(self.item_path)
                img = QImage(abs_path)
                if not img.isNull():
                    from PyQt6.QtCore import QMimeData, QUrl
                    mime_data = QMimeData()
                    mime_data.setImageData(img)
                    mime_data.setUrls([QUrl.fromLocalFile(abs_path)])
                    QApplication.clipboard().setMimeData(mime_data)
        self.copy_requested.emit()

    def request_ocr_on_demand(self):
        if os.path.exists(self.item_path):
            full_pix = QPixmap(self.item_path)
            if not full_pix.isNull():
                self.ocr_requested.emit(full_pix)

    def open_file_folder(self):
        try:
            norm_path = os.path.normpath(self.item_path)
            subprocess.Popen(f'explorer /select,"{norm_path}"', creationflags=0x08000000)
        except Exception as e:
            log_message(f"Error abriendo ubicación de archivo: {e}")

    def move_to_directory(self):
        if not os.path.exists(self.item_path):
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino", os.path.expanduser("~"))
        if dest_dir:
            try:
                dest_file = os.path.join(dest_dir, os.path.basename(self.item_path))
                if os.path.exists(dest_file):
                    reply = QMessageBox.question(
                        self,
                        "Archivo ya existente",
                        "Ya existe un archivo con ese nombre en la carpeta de destino. ¿Deseas reemplazarlo?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                shutil.copy2(self.item_path, dest_file)
                QMessageBox.information(self, "Jade", f"¡Archivo copiado con éxito en:\n{dest_file}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo copiar el archivo: {e}")

class TileActionOverlay(QWidget):
    def paintEvent(self, event):
        from PyQt6.QtGui import QLinearGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.4, QColor(0, 0, 0, 140))
        grad.setColorAt(1.0, QColor(0, 0, 0, 235))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 12.0, 12.0)
        painter.fillPath(path, QBrush(grad))

class GalleryTileCard(QFrame):
    """Tarjeta responsiva de mosaico con controles dinámicos y animación suave en hover."""
    delete_requested = pyqtSignal(str)
    ocr_requested = pyqtSignal(QPixmap)
    preview_requested = pyqtSignal(str)
    copy_requested = pyqtSignal()
    rename_requested = pyqtSignal(str)

    def __init__(self, item_path: str, parent=None):
        super().__init__(parent)
        self.item_path = item_path
        self.is_video = item_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))
        self.is_audio = item_path.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))

        self.setObjectName("GalleryCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(175)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.thumb_pixmap = QPixmap()
        cached_pix = get_cached_media_thumbnail(item_path)
        if self.is_audio:
            self.thumb_pixmap = create_audio_thumbnail_pixmap(240, 180)
        elif not cached_pix.isNull():
            self.thumb_pixmap = overlay_play_icon(cached_pix) if self.is_video else cached_pix
        else:
            runnable = ThumbnailRunnable(self.item_path)
            runnable.signals.finished.connect(self._on_thumbnail_ready)
            QThreadPool.globalInstance().start(runnable)

        self.init_ui()

    def _on_thumbnail_ready(self, vpath: str, raw_pixmap: QPixmap):
        if not raw_pixmap.isNull():
            self.thumb_pixmap = overlay_play_icon(raw_pixmap) if self.is_video else raw_pixmap
            self.update()

    def init_ui(self):
        self.btn_container = TileActionOverlay(self)
        self.btn_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        self.opacity_effect = QGraphicsOpacityEffect(self.btn_container)
        self.opacity_effect.setOpacity(0.0)
        self.btn_container.setGraphicsEffect(self.opacity_effect)
        self.btn_container.hide()

        container_layout = QVBoxLayout(self.btn_container)
        container_layout.setContentsMargins(6, 8, 6, 6)
        container_layout.setSpacing(0)
        container_layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_copy = QPushButton()
        btn_copy.setIcon(get_minimalist_svg_icon("copy", "#FFFFFF", 15))
        btn_copy.setToolTip("Copiar al portapapeles")
        btn_copy.setFixedSize(26, 26)
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet("QPushButton { background-color: #0078D4; border: none; border-radius: 6px; } QPushButton:hover { background-color: #106EBE; }")
        btn_copy.clicked.connect(self.copy_to_clipboard)
        btn_row.addWidget(btn_copy)

        if not self.is_video and not self.is_audio:
            btn_ocr = QPushButton()
            btn_ocr.setIcon(get_minimalist_svg_icon("ocr", "#FFFFFF", 15))
            btn_ocr.setToolTip("Extraer texto (OCR)")
            btn_ocr.setFixedSize(26, 26)
            btn_ocr.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ocr.setStyleSheet("QPushButton { background-color: rgba(255,255,255,0.22); border: none; border-radius: 6px; } QPushButton:hover { background-color: rgba(255,255,255,0.4); }")
            btn_ocr.clicked.connect(self.request_ocr_on_demand)
            btn_row.addWidget(btn_ocr)

        btn_folder = QPushButton()
        btn_folder.setIcon(get_minimalist_svg_icon("folder", "#FFFFFF", 15))
        btn_folder.setToolTip("Abrir ubicación")
        btn_folder.setFixedSize(26, 26)
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.setStyleSheet("QPushButton { background-color: rgba(255,255,255,0.22); border: none; border-radius: 6px; } QPushButton:hover { background-color: rgba(255,255,255,0.4); }")
        btn_folder.clicked.connect(self.open_file_folder)
        btn_row.addWidget(btn_folder)

        btn_move = QPushButton()
        btn_move.setIcon(get_minimalist_svg_icon("move", "#FFFFFF", 15))
        btn_move.setToolTip("Mover o copiar a otra carpeta")
        btn_move.setFixedSize(26, 26)
        btn_move.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_move.setStyleSheet("QPushButton { background-color: rgba(255,255,255,0.22); border: none; border-radius: 6px; } QPushButton:hover { background-color: rgba(255,255,255,0.4); }")
        btn_move.clicked.connect(self.move_to_directory)
        btn_row.addWidget(btn_move)

        btn_rename = QPushButton()
        btn_rename.setIcon(get_minimalist_svg_icon("rename", "#FFFFFF", 15))
        btn_rename.setToolTip("Renombrar archivo")
        btn_rename.setFixedSize(26, 26)
        btn_rename.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rename.setStyleSheet("QPushButton { background-color: rgba(255,255,255,0.22); border: none; border-radius: 6px; } QPushButton:hover { background-color: rgba(255,255,255,0.4); }")
        btn_rename.clicked.connect(lambda: self.rename_requested.emit(self.item_path))
        btn_row.addWidget(btn_rename)

        btn_delete = QPushButton()
        btn_delete.setIcon(get_minimalist_svg_icon("delete", "#FFFFFF", 15))
        btn_delete.setToolTip("Eliminar elemento")
        btn_delete.setFixedSize(26, 26)
        btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete.setStyleSheet("QPushButton { background-color: rgba(232, 17, 35, 0.88); border: none; border-radius: 6px; } QPushButton:hover { background-color: #E81123; }")
        btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.item_path))
        btn_row.addWidget(btn_delete)

        container_layout.addLayout(btn_row)

        file_name = os.path.basename(self.item_path)
        self.setToolTip(file_name)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.btn_container.setGeometry(0, self.height() - 56, self.width(), 56)
        self.btn_container.raise_()

    def enterEvent(self, event):
        self.btn_container.show()
        if hasattr(self, "_anim_fade") and self._anim_fade:
            self._anim_fade.stop()
        self._anim_fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        self._anim_fade.setDuration(160)
        self._anim_fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_fade.setStartValue(self.opacity_effect.opacity())
        self._anim_fade.setEndValue(1.0)
        self._anim_fade.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self, "_anim_fade") and self._anim_fade:
            self._anim_fade.stop()
        self._anim_fade = QPropertyAnimation(self.opacity_effect, b"opacity")
        self._anim_fade.setDuration(150)
        self._anim_fade.setEasingCurve(QEasingCurve.Type.InQuad)
        self._anim_fade.setStartValue(self.opacity_effect.opacity())
        self._anim_fade.setEndValue(0.0)
        def _on_hidden():
            if self.opacity_effect.opacity() == 0.0:
                self.btn_container.hide()
        self._anim_fade.finished.connect(_on_hidden)
        self._anim_fade.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = float(self.width())
        h = float(self.height())
        rect = QRectF(0, 0, w, h)

        path = QPainterPath()
        path.addRoundedRect(rect, 12.0, 12.0)
        painter.save()
        painter.setClipPath(path)

        painter.fillRect(rect, QColor(22, 22, 26))

        if self.thumb_pixmap and not self.thumb_pixmap.isNull():
            pw = float(self.thumb_pixmap.width())
            ph = float(self.thumb_pixmap.height())
            if pw > 0 and ph > 0:
                scale = max(w / pw, h / ph)
                sw = pw * scale
                sh = ph * scale
                sx = (w - sw) / 2.0
                sy = (h - sh) / 2.0
                painter.drawPixmap(QRectF(sx, sy, sw, sh), self.thumb_pixmap, QRectF(0, 0, pw, ph))
        else:
            painter.setPen(QColor(160, 160, 160))
            painter.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
            fallback_text = "Audio" if self.is_audio else ("Video" if self.is_video else "Imagen")
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, fallback_text)

        painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.preview_requested.emit(self.item_path)
        super().mousePressEvent(event)

    def copy_to_clipboard(self):
        if self.is_video or self.is_audio:
            from PyQt6.QtCore import QMimeData, QUrl
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(os.path.abspath(self.item_path))])
            QApplication.clipboard().setMimeData(mime_data)
        else:
            if os.path.exists(self.item_path):
                abs_path = os.path.abspath(self.item_path)
                img = QImage(abs_path)
                if not img.isNull():
                    from PyQt6.QtCore import QMimeData, QUrl
                    mime_data = QMimeData()
                    mime_data.setImageData(img)
                    mime_data.setUrls([QUrl.fromLocalFile(abs_path)])
                    QApplication.clipboard().setMimeData(mime_data)
        self.copy_requested.emit()

    def request_ocr_on_demand(self):
        if os.path.exists(self.item_path):
            full_pix = QPixmap(self.item_path)
            if not full_pix.isNull():
                self.ocr_requested.emit(full_pix)

    def open_file_folder(self):
        try:
            norm_path = os.path.normpath(self.item_path)
            subprocess.Popen(f'explorer /select,"{norm_path}"', creationflags=0x08000000)
        except Exception as e:
            log_message(f"Error abriendo ubicación de archivo: {e}")

    def move_to_directory(self):
        if not os.path.exists(self.item_path):
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino", os.path.expanduser("~"))
        if dest_dir:
            try:
                dest_file = os.path.join(dest_dir, os.path.basename(self.item_path))
                if os.path.exists(dest_file):
                    reply = QMessageBox.question(
                        self,
                        "Archivo ya existente",
                        "Ya existe un archivo con ese nombre en la carpeta de destino. ¿Deseas reemplazarlo?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                shutil.copy2(self.item_path, dest_file)
                QMessageBox.information(self, "Jade", f"¡Archivo copiado con éxito en:\n{dest_file}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo copiar el archivo: {e}")

class HotkeyLineEdit(QLineEdit):
    """Campo de entrada interactivo que detecta automáticamente cualquier combinación de teclas presionada."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setPlaceholderText("Haz clic y presiona las teclas...")
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event):
        self.selectAll()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        self._capture_key(event)

    def keyReleaseEvent(self, event):
        native_vk = event.nativeVirtualKey()
        key = event.key()
        if native_vk == 0x2C or key in (Qt.Key.Key_Print, Qt.Key.Key_SysReq, 0x01000009, 0x0100000a):
            self.setText("PrtScn")
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _capture_key(self, event):
        key = event.key()

        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            event.accept()
            return

        native_vk = event.nativeVirtualKey()
        if native_vk == 0x2C or key in (Qt.Key.Key_Print, Qt.Key.Key_SysReq, 0x01000009, 0x0100000a):
            self.setText("PrtScn")
            event.accept()
            return

        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace):
            self.clear()
            event.accept()
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

        key_name = ""

        # Detección limpia de F1 a F24 sin operaciones aritméticas entre enums
        if hasattr(key, "name") and key.name.startswith("Key_F") and key.name[5:].isdigit():
            key_name = key.name.replace("Key_", "")
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            key_name = "Enter"
        elif key == Qt.Key.Key_Space:
            key_name = "Space"
        elif key == Qt.Key.Key_Tab:
            key_name = "Tab"
        elif key == Qt.Key.Key_Delete:
            key_name = "Del"
        elif key == Qt.Key.Key_Insert:
            key_name = "Ins"
        elif key == Qt.Key.Key_Home:
            key_name = "Home"
        elif key == Qt.Key.Key_End:
            key_name = "End"
        elif key == Qt.Key.Key_PageUp:
            key_name = "PageUp"
        elif key == Qt.Key.Key_PageDown:
            key_name = "PageDown"
        else:
            raw_seq = QKeySequence(key).toString().upper().strip()
            if raw_seq and len(raw_seq) <= 6 and not raw_seq.startswith("KEY_"):
                key_name = raw_seq
            elif 0x20 <= native_vk <= 0x7E:
                key_name = chr(native_vk).upper()

        if key_name:
            parts.append(key_name)
            self.setText("+".join(parts))
        event.accept()

def detect_system_gpus():
    """Detecta de forma no bloqueante todas las GPUs instaladas (NVIDIA, AMD, Intel) junto a sus versiones de controlador sin abrir consolas."""
    gpus = []
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        cmd = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -Property Name, DriverVersion, Status | ConvertTo-Json"
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            startupinfo=startupinfo,
            creationflags=0x08000000,
            timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            raw = json.loads(res.stdout.strip())
            items = [raw] if isinstance(raw, dict) else raw
            for item in items:
                name = str(item.get("Name", "") or "").strip()
                driver = str(item.get("DriverVersion", "") or "").strip()
                status = str(item.get("Status", "") or "OK").strip()
                if not name:
                    continue
                name_low = name.lower()
                vendor = "GENERIC"
                if any(k in name_low for k in ["nvidia", "geforce", "rtx", "gtx", "quadro"]):
                    vendor = "NVIDIA"
                elif any(k in name_low for k in ["amd", "radeon"]):
                    vendor = "AMD"
                elif any(k in name_low for k in ["intel", "arc", "iris", "uhd", "hd graphics"]):
                    vendor = "INTEL"

                gpus.append({
                    "name": name,
                    "driver_version": driver,
                    "vendor": vendor,
                    "status": status
                })
    except Exception as e:
        log_message(f"Excepción detectando GPUs con PowerShell: {e}")

    return gpus


class GpuDriverInstallerThread(QThread):
    """Descarga e instala de forma automatizada y completa los controladores oficiales de GPU (NVIDIA, AMD o Intel) en entornos .exe."""
    status_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, vendor: str, gpu_name: str, parent=None):
        super().__init__(parent)
        self.vendor = vendor.upper()
        self.gpu_name = gpu_name

    def run(self):
        try:
            import urllib.request
            import ssl

            bin_dir = os.path.join(get_jade_appdata_dir(), "bin")
            os.makedirs(bin_dir, exist_ok=True)

            # 1. Intentar instalación desatendida mediante Winget si está disponible en Windows
            winget_path = shutil.which("winget")
            if winget_path:
                self.status_updated.emit(f"Verificando disponibilidad de {self.vendor} en Windows Package Manager...")
                winget_pkg_id = ""
                if self.vendor == "NVIDIA":
                    winget_pkg_id = "Nvidia.GeForceExperience"
                elif self.vendor == "INTEL":
                    winget_pkg_id = "Intel.DriverAndSupportAssistant"
                elif self.vendor == "AMD":
                    winget_pkg_id = "AdvancedMicroDevices.AMDSoftwareAdrenalinEdition"

                if winget_pkg_id:
                    try:
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE
                        cmd_wg = [
                            winget_path, "install", "--id", winget_pkg_id,
                            "--silent", "--accept-package-agreements", "--accept-source-agreements"
                        ]
                        self.status_updated.emit(f"Instalando {self.vendor} automáticamente vía Winget...")
                        proc_wg = subprocess.run(
                            cmd_wg,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            creationflags=0x08000000,
                            timeout=300
                        )
                        if proc_wg.returncode == 0:
                            log_message(f"Instalación de controlador {self.vendor} completada vía Winget.")
                            self.finished.emit(True, f"¡Controlador y utilidades de {self.vendor} instalados exitosamente en tu PC!")
                            return
                    except Exception as e_wg:
                        log_message(f"Winget no completó la instalación de {self.vendor}: {e_wg}. Pasando a descarga directa...")

            # 2. Descarga directa oficial del instalador de controladores
            self.status_updated.emit(f"Descargando instalador oficial de controladores para {self.vendor}...")
            log_message(f"Iniciando descarga directa de instalador de GPU para {self.vendor}: {self.gpu_name}")

            url = ""
            installer_name = ""
            install_args = ""
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }

            if self.vendor == "NVIDIA":
                installer_name = "NVIDIA_GeForce_Setup.exe"
                url = "https://us.download.nvidia.com/GFE/GFEClient/3.28.0.417/GeForce_Experience_v3.28.0.417.exe"
                install_args = "-s"
            elif self.vendor == "AMD":
                installer_name = "AMD_Software_Adrenalin_AutoDetect.exe"
                url = "https://drivers.amd.com/drivers/installer/24.10/amd-software-adrenalin-edition-24.10.1-minimalsetup-241018_web.exe"
                headers["Referer"] = "https://www.amd.com/"
                install_args = "-install"
            elif self.vendor == "INTEL":
                installer_name = "Intel-Driver-and-Support-Assistant-Installer.exe"
                url = "https://dsadata.intel.com/installer"
                install_args = "/passive /norestart"
            else:
                self.finished.emit(False, f"Fabricante de GPU '{self.vendor}' no compatible con descarga automatizada.")
                return

            dest_path = os.path.join(bin_dir, installer_name)

            try:
                ssl_ctx = ssl._create_unverified_context()
            except Exception:
                ssl_ctx = None

            def report_progress(downloaded, total):
                if total > 0:
                    percent = int(downloaded * 100 / total)
                    percent = min(100, percent)
                    d_mb = downloaded / (1024 * 1024)
                    t_mb = total / (1024 * 1024)
                    self.status_updated.emit(f"Descargando Instalador {self.vendor}... {percent}% ({d_mb:.1f} MB / {t_mb:.1f} MB)")

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=120) as resp, open(dest_path, "wb") as out_f:
                total_size = int(resp.headers.get("Content-Length", 0))
                chunk_size = 65536
                downloaded_bytes = 0
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    downloaded_bytes += len(chunk)
                    report_progress(downloaded_bytes, total_size)

            if not os.path.exists(dest_path) or os.path.getsize(dest_path) < 1000000:
                self.finished.emit(False, "El archivo descargado está dañado o incompleto.")
                return

            # 3. Ejecución e instalación monitoreada con privilegios de Administrador
            self.status_updated.emit(f"Instalando controlador de {self.vendor} en el sistema...")
            log_message(f"Ejecutando e instalando {dest_path} con argumentos: {install_args}")

            class SHELLEXECUTEINFOW(ctypes.Structure):
                _fields_ = [
                    ('cbSize', ctypes.c_uint32),
                    ('fMask', ctypes.c_uint32),
                    ('hwnd', ctypes.wintypes.HWND),
                    ('lpVerb', ctypes.c_wchar_p),
                    ('lpFile', ctypes.c_wchar_p),
                    ('lpParameters', ctypes.c_wchar_p),
                    ('lpDirectory', ctypes.c_wchar_p),
                    ('nShow', ctypes.c_int),
                    ('hInstApp', ctypes.wintypes.HINSTANCE),
                    ('lpIDList', ctypes.c_void_p),
                    ('lpClass', ctypes.c_wchar_p),
                    ('hkeyClass', ctypes.wintypes.HKEY),
                    ('dwHotKey', ctypes.c_uint32),
                    ('hIconOrMonitor', ctypes.wintypes.HANDLE),
                    ('hProcess', ctypes.wintypes.HANDLE)
                ]

            SEE_MASK_NOCLOSEPROCESS = 0x00000040
            shinfo = SHELLEXECUTEINFOW()
            shinfo.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
            shinfo.fMask = SEE_MASK_NOCLOSEPROCESS
            shinfo.hwnd = None
            shinfo.lpVerb = "runas"
            shinfo.lpFile = dest_path
            shinfo.lpParameters = install_args
            shinfo.lpDirectory = os.path.dirname(dest_path)
            shinfo.nShow = 1

            ret_exec = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(shinfo))

            if ret_exec and shinfo.hProcess:
                self.status_updated.emit(f"Instalación de {self.vendor} en progreso, por favor espera...")
                ctypes.windll.kernel32.WaitForSingleObject(shinfo.hProcess, 600000)
                ctypes.windll.kernel32.CloseHandle(shinfo.hProcess)
                log_message(f"Instalación de controlador {self.vendor} completada.")
                self.finished.emit(True, f"¡Controlador oficial de {self.vendor} instalado exitosamente en el sistema!")
            else:
                self.finished.emit(False, f"El instalador de {self.vendor} fue descargado pero se canceló la solicitud de instalación.")

        except Exception as e:
            log_message(f"Excepción en instalación de driver GPU: {e}")
            self.finished.emit(False, f"Error instalando el controlador oficial: {str(e)}")


class HardwareCompatibilityDialog(QDialog):
    """Diálogo de diagnóstico avanzado de hardware, drivers y reparación automática de motores de Jade."""
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.detected_gpus = []
        self._auto_install_queue = []
        self.setWindowTitle("Diagnóstico de Compatibilidad y Hardware — Jade")
        self.resize(680, 600)
        self.setMinimumSize(420, 440)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        ThemeManager.get_instance().register_child(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_box = QHBoxLayout()
        icon_diag = QLabel()
        icon_diag.setPixmap(get_minimalist_svg_pixmap("tools", "adaptive", 18, 18))

        lbl_title = QLabel("Diagnóstico de Compatibilidad y Rendimiento")
        lbl_title.setObjectName("PrimaryTextLabel")
        lbl_title.setFont(QFont("Segoe UI Variable Display", 12, QFont.Weight.Bold))

        title_box.addWidget(icon_diag)
        title_box.addWidget(lbl_title)
        title_box.addStretch()
        layout.addLayout(title_box)

        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setFont(QFont("Consolas", 10))
        layout.addWidget(self.txt_report)

        buttons_layout = QGridLayout()
        buttons_layout.setSpacing(8)

        self.btn_auto_all = QPushButton(" Auto-Instalar y Reparar Todo")
        self.btn_auto_all.setIcon(get_minimalist_svg_icon("sparkle", "#FFFFFF", 16))
        self.btn_auto_all.setObjectName("PrimaryBtn")
        self.btn_auto_all.setStyleSheet("background-color: #107C41; color: white; font-weight: bold; padding: 8px;")
        self.btn_auto_all.clicked.connect(self.run_auto_install_all)

        self.btn_run = QPushButton(" Ejecutar Análisis")
        self.btn_run.setIcon(get_minimalist_svg_icon("search", "#FFFFFF", 16))
        self.btn_run.setObjectName("PrimaryBtn")
        self.btn_run.clicked.connect(self.run_full_diagnostic)

        self.btn_repair = QPushButton(" Reparar FFmpeg")
        self.btn_repair.setIcon(get_minimalist_svg_icon("lightning", "adaptive", 16))
        self.btn_repair.setObjectName("SecondaryBtn")
        self.btn_repair.clicked.connect(self.repair_ffmpeg_engine)

        self.btn_vlc = QPushButton(" Instalar LibVLC Portátil")
        self.btn_vlc.setIcon(get_minimalist_svg_icon("video", "adaptive", 16))
        self.btn_vlc.setObjectName("SecondaryBtn")
        self.btn_vlc.clicked.connect(self.install_vlc_engine)

        self.btn_ocr = QPushButton(" Instalar Motor OCR")
        self.btn_ocr.setIcon(get_minimalist_svg_icon("ocr", "adaptive", 16))
        self.btn_ocr.setObjectName("SecondaryBtn")
        self.btn_ocr.clicked.connect(self.install_ocr_engine)

        self.btn_argos = QPushButton(" Instalar Traducción")
        self.btn_argos.setIcon(get_minimalist_svg_icon("globe", "adaptive", 16))
        self.btn_argos.setObjectName("SecondaryBtn")
        self.btn_argos.clicked.connect(self.install_argos_engine)

        self.btn_gpu = QPushButton(" Instalar Driver GPU")
        self.btn_gpu.setIcon(get_minimalist_svg_icon("gpu", "adaptive", 16))
        self.btn_gpu.setObjectName("SecondaryBtn")
        self.btn_gpu.clicked.connect(self.update_gpu_driver)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)

        buttons_layout.addWidget(self.btn_auto_all, 0, 0, 1, 3)
        buttons_layout.addWidget(self.btn_run, 1, 0)
        buttons_layout.addWidget(self.btn_repair, 1, 1)
        buttons_layout.addWidget(self.btn_vlc, 1, 2)
        buttons_layout.addWidget(self.btn_ocr, 2, 0)
        buttons_layout.addWidget(self.btn_argos, 2, 1)
        buttons_layout.addWidget(self.btn_gpu, 2, 2)
        buttons_layout.addWidget(btn_close, 3, 0, 1, 3)

        layout.addLayout(buttons_layout)
        self.apply_theme(ThemeManager.get_instance().is_dark)
        QTimer.singleShot(100, self.run_full_diagnostic)

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
            QTextEdit {{
                background-color: {p['bg_card']};
                color: {p['text_primary']};
                border: 1px solid {p['border']};
                border-radius: 8px;
            }}
        """)

    def run_full_diagnostic(self):
        self.txt_report.clear()
        self.txt_report.append("--- INICIANDO ANÁLISIS DE COMPATIBILIDAD JADE ---\n")

        self.detected_gpus = detect_system_gpus()
        if self.detected_gpus:
            self.txt_report.append("🎮 TARJETAS GRÁFICAS (GPU) DETECTADAS:")
            for g in self.detected_gpus:
                self.txt_report.append(f"   • {g['name']} [{g['vendor']}] — Driver: {g['driver_version']}")
            self.txt_report.append("")
        else:
            self.txt_report.append("⚠️ No se pudo determinar el modelo de GPU mediante Win32.\n")

        ffmpeg_executable = get_ffmpeg_path()
        if ffmpeg_executable:
            self.txt_report.append(f"✔️ Motor FFmpeg: Detectado e íntegro en {ffmpeg_executable}")
            nvenc_ok, nvenc_msg = check_nvenc_support(ffmpeg_executable)
            if nvenc_ok:
                self.txt_report.append("✔️ Aceleración por GPU NVIDIA NVENC: Compatible y funcional.")
                self.config.set("use_nvenc", True)
            else:
                self.txt_report.append(f"⚠️ Aceleración NVENC: No disponible ({nvenc_msg}). Se usará códec CPU x264.")
                self.config.set("use_nvenc", False)
        else:
            self.txt_report.append("❌ Motor FFmpeg: NO ENCONTRADO O CORRUPTO.")
            self.txt_report.append("   -> Haz clic en 'Reparar FFmpeg' o 'Auto-Instalar Todo' para solucionarlo.")

        find_and_setup_vlc()
        if VLC_AVAILABLE:
            self.txt_report.append("✔️ Motor Portátil LibVLC: Listo para reproducción interna HD.")
        else:
            self.txt_report.append("⚠️ Motor Portátil LibVLC: No detectado en el sistema.")
            self.txt_report.append("   -> Haz clic en 'Instalar LibVLC Portátil' para que Jade pueda reproducir de forma nativa.")

        ensure_wasapi_script_exists()
        wasapi_script = os.path.join(get_jade_appdata_dir(), "bin", "wasapi_recorder.ps1")
        if os.path.exists(wasapi_script):
            self.txt_report.append("✔️ Controlador de Audio Loopback (WASAPI C#): Configurado correctamente.")

        tess_bin = os.path.join(get_jade_appdata_dir(), "bin", "tesseract.exe")
        if not os.path.exists(tess_bin):
            tess_bin = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        if os.path.exists(tess_bin):
            self.txt_report.append("✔️ Motor de Extracción de Texto (OCR Tesseract): Configurado e íntegro.")
        else:
            self.txt_report.append("⚠️ Motor OCR Tesseract: No instalado en AppData/Roaming/Jade.")
            self.txt_report.append("   -> Haz clic en 'Instalar Motor OCR' para solucionarlo.")

        from_lang = self.config.get("translate_from_lang") or "en"
        to_lang = self.config.get("translate_to_lang") or "es"
        argos_model_path = os.path.join(get_jade_appdata_dir(), "argos_models", f"translate-{from_lang}_{to_lang}-1_0.argosmodel")

        if os.path.exists(argos_model_path):
            self.txt_report.append(f"✔️ Motor de Traducción Offline (Argos): Modelo ({from_lang.upper()}➔{to_lang.upper()}) instalado.")
        else:
            self.txt_report.append(f"⚠️ Traducción Offline (Argos): Modelo ({from_lang.upper()}➔{to_lang.upper()}) no instalado en AppData.")
            self.txt_report.append("   -> Haz clic en 'Instalar Traducción' para descargarlo de forma automática.")

        if ffmpeg_executable:
            mic_devs, _ = get_system_audio_drivers_and_devices(ffmpeg_executable)
            if mic_devs:
                self.txt_report.append(f"✔️ Micrófonos: {len(mic_devs)} dispositivos detectados ({mic_devs[0]}).")

        self.txt_report.append("\n--- ESTADO DEL SISTEMA LISTO ---")

    def run_auto_install_all(self):
        """Descarga e instala en lote y de forma ordenada todos los componentes que hagan falta."""
        self._auto_install_queue = []

        if not get_ffmpeg_path():
            self._auto_install_queue.append("ffmpeg")

        find_and_setup_vlc()
        if not VLC_AVAILABLE:
            self._auto_install_queue.append("vlc")

        tess_bin = os.path.join(get_jade_appdata_dir(), "bin", "tesseract.exe")
        if not os.path.exists(tess_bin) and not shutil.which("tesseract"):
            self._auto_install_queue.append("ocr")

        from_lang = self.config.get("translate_from_lang") or "en"
        to_lang = self.config.get("translate_to_lang") or "es"
        argos_model_path = os.path.join(get_jade_appdata_dir(), "argos_models", f"translate-{from_lang}_{to_lang}-1_0.argosmodel")
        if not os.path.exists(argos_model_path):
            self._auto_install_queue.append("argos")

        if not self._auto_install_queue:
            QMessageBox.information(self, "Jade", "¡Todos los motores y dependencias de Jade ya están instalados y al día!")
            return

        self._process_next_auto_install()

    def _process_next_auto_install(self):
        if not self._auto_install_queue:
            QMessageBox.information(self, "Jade", "¡La instalación por lote de todos los componentes ha finalizado exitosamente!")
            self.run_full_diagnostic()
            return

        task = self._auto_install_queue.pop(0)
        if task == "ffmpeg":
            self.repair_ffmpeg_engine(in_batch=True)
        elif task == "vlc":
            self.install_vlc_engine(in_batch=True)
        elif task == "ocr":
            self.install_ocr_engine(in_batch=True)
        elif task == "argos":
            self.install_argos_engine(in_batch=True)

    def update_gpu_driver(self):
        if not self.detected_gpus:
            self.detected_gpus = detect_system_gpus()

        if not self.detected_gpus:
            QMessageBox.warning(self, "Controlador GPU", "No se detectó ninguna tarjeta gráfica compatible en el sistema.")
            return

        target_gpu = None
        if len(self.detected_gpus) == 1:
            target_gpu = self.detected_gpus[0]
        else:
            priority = [g for g in self.detected_gpus if g["vendor"] in ("NVIDIA", "AMD")]
            if priority:
                target_gpu = priority[0]
            else:
                names = [f"{g['name']} ({g['vendor']})" for g in self.detected_gpus]
                choice, ok = QInputDialog.getItem(self, "Seleccionar GPU", "Elige la GPU a actualizar:", names, 0, False)
                if ok and choice:
                    idx = names.index(choice)
                    target_gpu = self.detected_gpus[idx]

        if not target_gpu:
            return

        vendor = target_gpu["vendor"]
        if vendor not in ("NVIDIA", "AMD", "INTEL"):
            QMessageBox.information(
                self,
                "Controlador GPU",
                f"La GPU detectada ({target_gpu['name']}) es genérica o no posee instalador directo automatizado."
            )
            return

        self.btn_gpu.setEnabled(False)
        self.progress_dialog = QProgressDialog(f"Descargando instalador oficial de controladores para {vendor}...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle(f"Instalación de Controlador {vendor}")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.gpu_installer = GpuDriverInstallerThread(vendor, target_gpu["name"], self)
        self.gpu_installer.status_updated.connect(self.progress_dialog.setLabelText)
        self.gpu_installer.finished.connect(self.on_gpu_driver_finished)
        self.gpu_installer.start()

    def on_gpu_driver_finished(self, success: bool, message: str):
        self.progress_dialog.close()
        self.btn_gpu.setEnabled(True)
        if success:
            QMessageBox.information(self, "Controlador GPU", message)
            self.run_full_diagnostic()
        else:
            QMessageBox.warning(self, "Controlador GPU", f"Error al actualizar controlador: {message}")

    def repair_ffmpeg_engine(self, in_batch: bool = False):
        self._in_batch = in_batch
        self.btn_repair.setEnabled(False)
        self.txt_report.append("\nIniciando descarga e instalación limpia de FFmpeg...")

        self.progress_dialog = QProgressDialog("Descargando ejecutable limpio de FFmpeg...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Reparación de Motor FFmpeg")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.installer_thread = FFmpegInstallerThread(self)
        self.installer_thread.status_updated.connect(self.progress_dialog.setLabelText)
        self.installer_thread.finished.connect(self.on_repair_finished)
        self.installer_thread.start()

    def install_vlc_engine(self, in_batch: bool = False):
        self._in_batch = in_batch
        self.btn_vlc.setEnabled(False)
        self.txt_report.append("\nIniciando descarga de componentes portátiles LibVLC...")

        self.progress_dialog = QProgressDialog("Descargando motor portátil VLC para Jade...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Instalación de Motor VLC")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.vlc_installer = VLCInstallerThread(self)
        self.vlc_installer.status_updated.connect(self.progress_dialog.setLabelText)
        self.vlc_installer.finished.connect(self.on_vlc_installed)
        self.vlc_installer.start()

    def install_ocr_engine(self, in_batch: bool = False):
        self._in_batch = in_batch
        self.btn_ocr.setEnabled(False)
        self.txt_report.append("\nIniciando descarga de componentes de OCR Tesseract...")

        self.progress_dialog = QProgressDialog("Descargando e instalando motor OCR Tesseract para Jade...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Instalación de Motor OCR")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.ocr_installer = OcrInstallerThread(self)
        self.ocr_installer.status_updated.connect(self.progress_dialog.setLabelText)
        self.ocr_installer.finished.connect(self.on_ocr_installed)
        self.ocr_installer.start()

    def install_argos_engine(self, in_batch: bool = False):
        self._in_batch = in_batch
        self.btn_argos.setEnabled(False)
        from_lang = self.config.get("translate_from_lang") or "en"
        to_lang = self.config.get("translate_to_lang") or "es"

        self.txt_report.append(f"\nIniciando descarga del modelo de traducción offline ({from_lang.upper()}➔{to_lang.upper()})...")

        self.progress_dialog = QProgressDialog(f"Descargando paquete de idioma ({from_lang.upper()}➔{to_lang.upper()})...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Instalación de Modelo de Traducción")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.argos_installer = ArgosInstallerThread(from_lang, to_lang, self)
        self.argos_installer.status_updated.connect(self.progress_dialog.setLabelText)
        self.argos_installer.finished.connect(self.on_argos_installed)
        self.argos_installer.start()

    def on_repair_finished(self, success: bool, message: str):
        self.progress_dialog.close()
        self.btn_repair.setEnabled(True)
        if success:
            if getattr(self, "_in_batch", False):
                self._process_next_auto_install()
            else:
                QMessageBox.information(self, "Jade", "¡El motor FFmpeg ha sido configurado!")
                self.run_full_diagnostic()
        else:
            QMessageBox.warning(self, "Jade", f"Error en FFmpeg: {message}")

    def on_vlc_installed(self, success: bool, message: str):
        self.progress_dialog.close()
        self.btn_vlc.setEnabled(True)
        if success:
            if getattr(self, "_in_batch", False):
                self._process_next_auto_install()
            else:
                QMessageBox.information(self, "Jade", "¡El motor VLC embebido ha sido configurado!")
                self.run_full_diagnostic()
        else:
            QMessageBox.warning(self, "Jade", f"Error en VLC: {message}")

    def on_ocr_installed(self, success: bool, message: str):
        self.progress_dialog.close()
        self.btn_ocr.setEnabled(True)
        if success:
            if getattr(self, "_in_batch", False):
                self._process_next_auto_install()
            else:
                QMessageBox.information(self, "Jade", "¡El motor OCR Tesseract ha sido configurado con éxito!")
                self.run_full_diagnostic()
        else:
            QMessageBox.warning(self, "Jade", f"Error en OCR: {message}")

    def on_argos_installed(self, success: bool, message: str):
        self.progress_dialog.close()
        self.btn_argos.setEnabled(True)
        if success:
            if getattr(self, "_in_batch", False):
                self._process_next_auto_install()
            else:
                QMessageBox.information(self, "Jade", "¡El modelo de traducción offline ha sido instalado exitosamente!")
                self.run_full_diagnostic()
        else:
            QMessageBox.warning(self, "Jade", f"Error en Traducción: {message}")


class SettingsDialog(QDialog):
    """Diálogo de opciones de configuración de Jade totalmente responsivo y adaptativo con pestañas por secciones."""
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Ajustes — Jade")
        self.resize(580, 620)
        self.setMinimumSize(420, 460)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        ThemeManager.get_instance().register_child(self)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(12, 12, 12, 12)
        dialog_layout.setSpacing(10)

        self.tab_widget = QTabWidget()

        # Pestaña 1: General
        tab_gen = QWidget()
        layout_gen = QVBoxLayout(tab_gen)
        layout_gen.setContentsMargins(4, 8, 4, 4)

        scroll_gen = QScrollArea()
        scroll_gen.setWidgetResizable(True)
        content_gen = QWidget()
        gen_box = QVBoxLayout(content_gen)
        gen_box.setSpacing(10)
        gen_box.setContentsMargins(6, 6, 6, 6)

        lbl_img_folder = QLabel("Carpeta para Capturas de Imagen:")
        lbl_img_folder.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))

        h_img = QHBoxLayout()
        self.edit_img_folder = QLineEdit(self.config.get("images_folder"))
        self.edit_img_folder.setReadOnly(True)
        btn_browse_img = QPushButton("Explorar...")
        btn_browse_img.clicked.connect(self.browse_images_folder)
        h_img.addWidget(self.edit_img_folder)
        h_img.addWidget(btn_browse_img)

        lbl_vid_folder = QLabel("Carpeta para Grabaciones de Video:")
        lbl_vid_folder.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))

        h_vid = QHBoxLayout()
        self.edit_vid_folder = QLineEdit(self.config.get("videos_folder"))
        self.edit_vid_folder.setReadOnly(True)
        btn_browse_vid = QPushButton("Explorar...")
        btn_browse_vid.clicked.connect(self.browse_videos_folder)
        h_vid.addWidget(self.edit_vid_folder)
        h_vid.addWidget(btn_browse_vid)

        lbl_aud_folder = QLabel("Carpeta para Grabaciones de Audio MP3:")
        lbl_aud_folder.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))

        h_aud = QHBoxLayout()
        self.edit_aud_folder = QLineEdit(self.config.get("audios_folder"))
        self.edit_aud_folder.setReadOnly(True)
        btn_browse_aud = QPushButton("Explorar...")
        btn_browse_aud.clicked.connect(self.browse_audios_folder)
        h_aud.addWidget(self.edit_aud_folder)
        h_aud.addWidget(btn_browse_aud)

        gen_box.addWidget(lbl_img_folder)
        gen_box.addLayout(h_img)
        gen_box.addWidget(lbl_vid_folder)
        gen_box.addLayout(h_vid)
        gen_box.addWidget(lbl_aud_folder)
        gen_box.addLayout(h_aud)

        self.chk_autostart = QCheckBox("Iniciar Jade automáticamente con Windows")
        self.chk_autostart.setChecked(self.config.get("autostart"))

        self.chk_override_prtscn = QCheckBox("Capturar tecla nativa Impr Pant (remplaza Recortes de Windows 10/11)")
        self.chk_override_prtscn.setChecked(self.config.get("override_printscreen"))

        self.chk_auto_copy = QCheckBox("Copiar automáticamente captura al portapapeles")
        self.chk_auto_copy.setChecked(self.config.get("auto_copy_clipboard"))

        self.chk_nvenc = QCheckBox("Aceleración por Hardware NVIDIA NVENC (GPU)")
        self.chk_nvenc.setChecked(self.config.get("use_nvenc"))

        self.chk_record_system = QCheckBox("Capturar audio interno del sistema (juegos, música)")
        self.chk_record_system.setChecked(self.config.get("record_system_audio"))

        self.chk_record_mic = QCheckBox("Capturar audio de micrófono (narración)")
        self.chk_record_mic.setChecked(self.config.get("record_mic_audio"))

        self.chk_mica = QCheckBox("Efecto de transparencia Mica de Windows 11")
        self.chk_mica.setChecked(self.config.get("mica_effect"))

        self.chk_hide_on_capture = QCheckBox("Ocultar ventana de Jade durante capturas")
        self.chk_hide_on_capture.setChecked(self.config.get("hide_on_capture"))

        self.chk_hdr_fix = QCheckBox("Parche HDR (Corrige brillo excesivo y sobreexposición en pantallas HDR)")
        self.chk_hdr_fix.setChecked(self.config.get("hdr_fix"))

        gen_box.addWidget(self.chk_autostart)
        gen_box.addWidget(self.chk_override_prtscn)
        gen_box.addWidget(self.chk_auto_copy)
        gen_box.addWidget(self.chk_nvenc)
        gen_box.addWidget(self.chk_record_system)
        gen_box.addWidget(self.chk_record_mic)
        gen_box.addWidget(self.chk_hdr_fix)
        gen_box.addWidget(self.chk_mica)
        gen_box.addWidget(self.chk_hide_on_capture)

        fps_layout = QHBoxLayout()
        fps_label = QLabel("Tasa de Fotogramas (FPS de Grabación):")
        self.fps_combo = QComboBox()
        self.fps_combo.addItem("Auto (Hz Reales de la Pantalla)", "auto")
        self.fps_combo.addItem("60 FPS (Estándar)", 60)
        self.fps_combo.addItem("120 FPS (Duplicación 2x)", 120)
        self.fps_combo.addItem("144 FPS (Pantallas 144Hz)", 144)
        self.fps_combo.addItem("180 FPS (Triplicación 3x / LSFG)", 180)
        self.fps_combo.addItem("240 FPS (Ultra Fluidez)", 240)

        curr_fps = self.config.get("fps")
        fps_idx = self.fps_combo.findData(curr_fps)
        if fps_idx >= 0:
            self.fps_combo.setCurrentIndex(fps_idx)
        else:
            self.fps_combo.setCurrentIndex(0)

        fps_layout.addWidget(fps_label)
        fps_layout.addWidget(self.fps_combo)
        fps_layout.addStretch()

        theme_layout = QHBoxLayout()
        theme_label = QLabel("Tema de interfaz:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["sistema", "oscuro", "claro"])
        curr_theme = self.config.get("theme", "sistema")
        if curr_theme in ("sistema", "oscuro", "claro"):
            self.theme_combo.setCurrentText(curr_theme)
        else:
            self.theme_combo.setCurrentText("sistema")
        self.theme_combo.currentTextChanged.connect(self._on_theme_combo_changed)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        card_pos_layout = QHBoxLayout()
        card_pos_label = QLabel("Posición de tarjeta flotante:")
        self.card_pos_combo = QComboBox()
        self.card_pos_combo.addItem("Inferior Izquierda", "bottom_left")
        self.card_pos_combo.addItem("Inferior Derecha", "bottom_right")
        self.card_pos_combo.addItem("Superior Izquierda", "top_left")
        self.card_pos_combo.addItem("Superior Derecha", "top_right")

        curr_pos = self.config.get("card_position") or "bottom_left"
        idx = self.card_pos_combo.findData(curr_pos)
        if idx >= 0:
            self.card_pos_combo.setCurrentIndex(idx)

        card_pos_layout.addWidget(card_pos_label)
        card_pos_layout.addWidget(self.card_pos_combo)
        card_pos_layout.addStretch()

        draw_col_layout = QHBoxLayout()
        lbl_draw_col = QLabel("Color de trazado en vivo (Video):")
        self.btn_draw_color = QPushButton()
        self.btn_draw_color.setFixedSize(36, 26)
        self.btn_draw_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self.selected_draw_color = QColor(self.config.get("draw_color") or "#E81123")
        self.btn_draw_color.setStyleSheet(f"background-color: {self.selected_draw_color.name()}; border: 2px solid rgba(255,255,255,0.4); border-radius: 6px;")
        self.btn_draw_color.clicked.connect(self.choose_draw_color)
        draw_col_layout.addWidget(lbl_draw_col)
        draw_col_layout.addWidget(self.btn_draw_color)
        draw_col_layout.addStretch()

        gen_box.addLayout(fps_layout)
        gen_box.addLayout(theme_layout)
        gen_box.addLayout(card_pos_layout)
        gen_box.addLayout(draw_col_layout)

        btn_set_default = QPushButton(" Establecer Jade como App Predeterminada (Fotos, Videos y Audios)")
        btn_set_default.setIcon(get_minimalist_svg_icon("star", "#FFFFFF", 16))
        btn_set_default.setObjectName("PrimaryBtn")
        btn_set_default.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_set_default.setStyleSheet("background-color: #0078D4; color: white; font-weight: bold; padding: 9px 16px; border-radius: 8px; font-size: 11px;")
        btn_set_default.clicked.connect(self.register_windows_default_associations)
        gen_box.addWidget(btn_set_default)

        btn_compat = QPushButton(" Compatibilidad y Optimización de PC")
        btn_compat.setIcon(get_minimalist_svg_icon("tools", "adaptive", 16))
        btn_compat.setObjectName("SecondaryBtn")
        btn_compat.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_compat.clicked.connect(self.open_compatibility_dialog)
        gen_box.addWidget(btn_compat)

        scroll_gen.setWidget(content_gen)
        layout_gen.addWidget(scroll_gen)

        # Pestaña 2: Atajos Globales
        tab_hk = QWidget()
        layout_hk = QVBoxLayout(tab_hk)
        layout_hk.setContentsMargins(4, 8, 4, 4)

        scroll_hk = QScrollArea()
        scroll_hk.setWidgetResizable(True)
        content_hk = QWidget()
        hk_box = QVBoxLayout(content_hk)
        hk_box.setSpacing(10)
        hk_box.setContentsMargins(6, 6, 6, 6)

        title_hk_row = QHBoxLayout()
        icon_kb = QLabel()
        icon_kb.setPixmap(get_minimalist_svg_pixmap("keyboard", "adaptive", 16, 16))

        lbl_hotkeys_title = QLabel("Teclas de Acceso Rápido (Atajos Globales):")
        lbl_hotkeys_title.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))

        title_hk_row.addWidget(icon_kb)
        title_hk_row.addWidget(lbl_hotkeys_title)
        title_hk_row.addStretch()

        lbl_hk_hint = QLabel("Haz clic en la casilla y presiona la combinación deseada (ej: PrtScn, Ctrl+Shift+S)")
        lbl_hk_hint.setObjectName("HighlightTimeLabel")
        lbl_hk_hint.setStyleSheet("font-size: 11px;")

        hk_box.addLayout(title_hk_row)
        hk_box.addWidget(lbl_hk_hint)

        hk_grid = QGridLayout()
        hk_grid.setSpacing(6)

        hk_grid.addWidget(QLabel("Capturar pantalla:"), 0, 0)
        self.edit_hk_cap = HotkeyLineEdit(self.config.get("hotkey_capture"))
        hk_grid.addWidget(self.edit_hk_cap, 0, 1)

        hk_grid.addWidget(QLabel("Grabar / Detener video:"), 1, 0)
        self.edit_hk_rec = HotkeyLineEdit(self.config.get("hotkey_record"))
        hk_grid.addWidget(self.edit_hk_rec, 1, 1)

        hk_grid.addWidget(QLabel("Grabar / Detener solo Audio:"), 2, 0)
        self.edit_hk_rec_aud = HotkeyLineEdit(self.config.get("hotkey_record_audio"))
        hk_grid.addWidget(self.edit_hk_rec_aud, 2, 1)

        hk_grid.addWidget(QLabel("Pausar / Reanudar:"), 3, 0)
        self.edit_hk_pause = HotkeyLineEdit(self.config.get("hotkey_pause"))
        hk_grid.addWidget(self.edit_hk_pause, 3, 1)

        hk_grid.addWidget(QLabel("Ventana Historial de Textos:"), 4, 0)
        self.edit_hk_hist = HotkeyLineEdit(self.config.get("hotkey_text_history"))
        hk_grid.addWidget(self.edit_hk_hist, 4, 1)

        hk_grid.addWidget(QLabel("Ventana Galería Flotante:"), 5, 0)
        self.edit_hk_gal = HotkeyLineEdit(self.config.get("hotkey_media_gallery"))
        hk_grid.addWidget(self.edit_hk_gal, 5, 1)

        hk_grid.addWidget(QLabel("Activar / Desactivar Atajos:"), 6, 0)
        self.edit_hk_tog = HotkeyLineEdit(self.config.get("hotkey_toggle_hotkeys"))
        hk_grid.addWidget(self.edit_hk_tog, 6, 1)

        hk_grid.addWidget(QLabel("Dibujar señalador en vivo (Video):"), 7, 0)
        self.edit_hk_draw = HotkeyLineEdit(self.config.get("hotkey_draw_arrow"))
        hk_grid.addWidget(self.edit_hk_draw, 7, 1)

        hk_grid.addWidget(QLabel("Limpiar señaladores (Video):"), 8, 0)
        self.edit_hk_clr = HotkeyLineEdit(self.config.get("hotkey_clear_draw"))
        hk_grid.addWidget(self.edit_hk_clr, 8, 1)

        hk_grid.addWidget(QLabel("Seleccionar Área y Traducir (Argos):"), 9, 0)
        self.edit_hk_trans = HotkeyLineEdit(self.config.get("hotkey_translate") or "Ctrl+Shift+T")
        hk_grid.addWidget(self.edit_hk_trans, 9, 1)

        hk_grid.addWidget(QLabel("Ventana Flotante de Traducción Directa:"), 10, 0)
        self.edit_hk_qtrans = HotkeyLineEdit(self.config.get("hotkey_quick_translator") or "Ctrl+Shift+Z")
        hk_grid.addWidget(self.edit_hk_qtrans, 10, 1)

        hk_grid.addWidget(QLabel("Activar Traducción en Vivo de Modo Juego:"), 11, 0)
        self.edit_hk_game = HotkeyLineEdit(self.config.get("hotkey_game_mode") or "Ctrl+Shift+Enter")
        hk_grid.addWidget(self.edit_hk_game, 11, 1)

        hk_box.addLayout(hk_grid)

        trans_lang_layout = QHBoxLayout()
        icon_globe_lang = QLabel()
        icon_globe_lang.setPixmap(get_minimalist_svg_pixmap("globe", "adaptive", 16, 16))

        lbl_trans_lang = QLabel("Traductor Argos (Idioma Origen ➔ Destino):")
        self.combo_from_lang = QComboBox()
        self.combo_from_lang.addItem("Inglés (en)", "en")
        self.combo_from_lang.addItem("Español (es)", "es")
        self.combo_from_lang.addItem("Francés (fr)", "fr")
        self.combo_from_lang.addItem("Alemán (de)", "de")
        self.combo_from_lang.addItem("Italiano (it)", "it")
        self.combo_from_lang.addItem("Portugués (pt)", "pt")

        self.combo_to_lang = QComboBox()
        self.combo_to_lang.addItem("Español (es)", "es")
        self.combo_to_lang.addItem("Inglés (en)", "en")
        self.combo_to_lang.addItem("Francés (fr)", "fr")
        self.combo_to_lang.addItem("Alemán (de)", "de")
        self.combo_to_lang.addItem("Italiano (it)", "it")
        self.combo_to_lang.addItem("Portugués (pt)", "pt")

        idx_from = self.combo_from_lang.findData(self.config.get("translate_from_lang") or "en")
        if idx_from >= 0: self.combo_from_lang.setCurrentIndex(idx_from)

        idx_to = self.combo_to_lang.findData(self.config.get("translate_to_lang") or "es")
        if idx_to >= 0: self.combo_to_lang.setCurrentIndex(idx_to)

        trans_lang_layout.addWidget(icon_globe_lang)
        trans_lang_layout.addWidget(lbl_trans_lang)
        trans_lang_layout.addWidget(self.combo_from_lang)
        trans_lang_layout.addWidget(QLabel("➔"))
        trans_lang_layout.addWidget(self.combo_to_lang)
        trans_lang_layout.addStretch()

        hk_box.addLayout(trans_lang_layout)

        btn_install_ext = QPushButton(" Activar Clic Derecho en Navegadores (Chrome, Edge, Brave, Firefox, Opera, Vivaldi)")
        btn_install_ext.setIcon(get_minimalist_svg_icon("globe", "#FFFFFF", 16))
        btn_install_ext.setObjectName("PrimaryBtn")
        btn_install_ext.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_install_ext.clicked.connect(self.install_browser_extension_automated)

        hk_box.addWidget(btn_install_ext)

        scroll_hk.setWidget(content_hk)
        layout_hk.addWidget(scroll_hk)

        # Pestaña 3: Modo Juego
        tab_game = QWidget()
        layout_game = QVBoxLayout(tab_game)
        layout_game.setContentsMargins(4, 8, 4, 4)

        scroll_game = QScrollArea()
        scroll_game.setWidgetResizable(True)
        content_game = QWidget()
        game_box = QVBoxLayout(content_game)
        game_box.setSpacing(12)
        game_box.setContentsMargins(6, 6, 6, 6)

        title_game_row = QHBoxLayout()
        icon_game_tab = QLabel()
        icon_game_tab.setPixmap(get_minimalist_svg_pixmap("game", "adaptive", 18, 18))

        lbl_game_title = QLabel("Configuración y Acceso Directo de Modo Juego")
        lbl_game_title.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))

        title_game_row.addWidget(icon_game_tab)
        title_game_row.addWidget(lbl_game_title)
        title_game_row.addStretch()

        lbl_game_hint = QLabel(
            "Desde aquí puedes configurar tus plantillas de recuadros o activar directamente la traducción en vivo sobre cualquier juego sin necesidad de abrir la ventana de gestión previamente."
        )
        lbl_game_hint.setWordWrap(True)
        lbl_game_hint.setStyleSheet("color: #8A8A8A; font-size: 11px;")

        btn_game_config = QPushButton(" Configurar Plantillas y Atajos de Juego")
        btn_game_config.setIcon(get_minimalist_svg_icon("settings", "#FFFFFF", 16))
        btn_game_config.setObjectName("PrimaryBtn")
        btn_game_config.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_game_config.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_game_config.clicked.connect(self.open_game_mode_from_settings)

        btn_game_direct = QPushButton(" Iniciar Traducción en Vivo Directa")
        btn_game_direct.setIcon(get_minimalist_svg_icon("play", "#FFFFFF", 16))
        btn_game_direct.setObjectName("PrimaryBtn")
        btn_game_direct.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_game_direct.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_game_direct.setStyleSheet("background-color: #107C41; color: white; font-weight: bold;")
        btn_game_direct.clicked.connect(self.direct_start_game_live_translation)

        # Campo editable para cambiar el atajo directamente desde esta pestaña
        hk_game_layout = QVBoxLayout()
        hk_game_layout.setSpacing(4)

        lbl_hk_game_title = QLabel("Cambiar Atajo Global Directo de Modo Juego:")
        lbl_hk_game_title.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))
        lbl_hk_game_title.setStyleSheet("color: #0078D4;")

        curr_game_hk = self.config.get("hotkey_game_mode") or "Ctrl+Shift+Enter"
        self.edit_hk_game_mode = HotkeyLineEdit(curr_game_hk)

        lbl_hk_game_desc = QLabel("(Inicia automáticamente los contenedores de traducción activa sobre cualquier juego)")
        lbl_hk_game_desc.setStyleSheet("color: #8A8A8A; font-size: 10px;")

        hk_game_layout.addWidget(lbl_hk_game_title)
        hk_game_layout.addWidget(self.edit_hk_game_mode)
        hk_game_layout.addWidget(lbl_hk_game_desc)

        game_box.addLayout(title_game_row)
        game_box.addWidget(lbl_game_hint)
        game_box.addWidget(btn_game_config)
        game_box.addWidget(btn_game_direct)
        game_box.addLayout(hk_game_layout)
        game_box.addStretch()

        scroll_game.setWidget(content_game)
        layout_game.addWidget(scroll_game)

        self.tab_widget.addTab(tab_gen, get_minimalist_svg_icon("settings", "adaptive", 16), " General")
        self.tab_widget.addTab(tab_hk, get_minimalist_svg_icon("keyboard", "adaptive", 16), " Atajos Globales")
        self.tab_widget.addTab(tab_game, get_minimalist_svg_icon("game", "adaptive", 16), " Modo Juego")

        dialog_layout.addWidget(self.tab_widget, stretch=1)

        bottom_buttons = QHBoxLayout()
        btn_save = QPushButton("Guardar Cambios")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self.save_settings)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        bottom_buttons.addStretch()
        bottom_buttons.addWidget(btn_cancel)
        bottom_buttons.addWidget(btn_save)

        dialog_layout.addLayout(bottom_buttons)

    def install_browser_extension_automated(self):
        ext_dir = os.path.join(get_jade_appdata_dir(), "chrome_extension")
        os.makedirs(ext_dir, exist_ok=True)

        if hasattr(self, "parent") and self.parent() and hasattr(self.parent(), "register_jade_protocol"):
            self.parent().register_jade_protocol()

        QApplication.clipboard().setText(ext_dir)

        try:
            norm_path = os.path.normpath(ext_dir)
            subprocess.Popen(f'explorer /select,"{norm_path}"', creationflags=0x08000000)
        except Exception:
            pass

        # Abrir páginas de administración de extensiones
        for url in ["chrome://extensions", "edge://extensions", "opera://extensions", "about:debugging#/runtime/this-firefox"]:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        QMessageBox.information(
            self,
            "Jade — Clic Derecho en Navegadores",
            "¡Integración de Clic Derecho lista!\n\n"
            "Por motivos de seguridad, Google Chrome y Microsoft Edge prohíben estrictamente que cualquier programa externo modifique su menú web de clic derecho sin el permiso del usuario.\n\n"
            "Jade ya realizó todos los pasos por ti:\n"
            "1. Se copió la ruta de la extensión al portapapeles.\n"
            "2. Se abrió la carpeta lista para usar.\n"
            "3. Se abrieron las páginas de administración de extensiones en tu navegador.\n\n"
            "Paso final único en tu navegador (solo toma 5 segundos):\n"
            "• En Chrome/Edge: Activa 'Modo Desarrollador', haz clic en 'Cargar descomprimida' y presiona Ctrl + V o arrastra la carpeta.\n\n"
            "💡 ALTERNATIVA INSTANTÁNEA SIN CLIC DERECHO:\n"
            "Selecciona cualquier texto en Chrome, Word, PDF o cualquier programa y presiona Ctrl + Shift + T para traducirlo al instante en la tarjeta flotante."
        )

    def _on_theme_combo_changed(self, text: str):
        ThemeManager.get_instance().set_config_theme(text)

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        p = ThemePalette.get(is_dark)
        if hasattr(self, "btn_compat") and self.btn_compat:
            self.btn_compat.setIcon(get_minimalist_svg_icon("tools", p['icon_color'], 16))

    def choose_draw_color(self):
        c = QColorDialog.getColor(self.selected_draw_color, self, "Seleccionar color de trazado en vivo")
        if c.isValid():
            self.selected_draw_color = c
            self.btn_draw_color.setStyleSheet(f"background-color: {c.name()}; border: 2px solid rgba(255,255,255,0.4); border-radius: 6px;")

    def open_compatibility_dialog(self):
        dialog = HardwareCompatibilityDialog(self.config, self)
        dialog.exec()
        self.chk_nvenc.setChecked(self.config.get("use_nvenc"))

    def open_game_mode_from_settings(self):
        try:
            import juego
            dialog = juego.GameSettingsDialog(parent=self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Modo Juego", f"No se pudo abrir la configuración del Modo Juego: {e}")

    def direct_start_game_live_translation(self):
        try:
            if self.parent() and hasattr(self.parent(), "start_direct_game_translation"):
                self.parent().start_direct_game_translation()
            else:
                import juego
                main_win = self.parent()
                if main_win:
                    if not hasattr(main_win, "game_win") or main_win.game_win is None:
                        main_win.game_win = juego.GameTranslatorWindow(main_win.config, parent=None)
                    main_win.game_win.launch_saved_templates()
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Modo Juego", f"No se pudo iniciar la traducción en vivo: {e}")

    def browse_images_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de imágenes", self.edit_img_folder.text())
        if folder:
            self.edit_img_folder.setText(folder)

    def browse_videos_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de videos", self.edit_vid_folder.text())
        if folder:
            self.edit_vid_folder.setText(folder)

    def browse_audios_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de audios", self.edit_aud_folder.text())
        if folder:
            self.edit_aud_folder.setText(folder)

    def save_settings(self):
        img_folder = self.edit_img_folder.text()
        vid_folder = self.edit_vid_folder.text()
        aud_folder = self.edit_aud_folder.text()
        autostart_val = self.chk_autostart.isChecked()

        override_val = self.chk_override_prtscn.isChecked()
        self.config.set("images_folder", img_folder)
        self.config.set("videos_folder", vid_folder)
        self.config.set("audios_folder", aud_folder)
        self.config.set("hotkey_capture", self.edit_hk_cap.text().strip() or "PrtScn")
        self.config.set("hotkey_record", self.edit_hk_rec.text().strip() or "Ctrl+Shift+R")
        self.config.set("hotkey_record_audio", self.edit_hk_rec_aud.text().strip() or "Ctrl+Shift+A")
        self.config.set("hotkey_pause", self.edit_hk_pause.text().strip() or "Ctrl+Shift+P")
        self.config.set("hotkey_text_history", self.edit_hk_hist.text().strip() or "Ctrl+Shift+H")
        self.config.set("hotkey_media_gallery", self.edit_hk_gal.text().strip() or "Ctrl+Shift+G")
        self.config.set("hotkey_toggle_hotkeys", self.edit_hk_tog.text().strip() or "Ctrl+Shift+X")
        self.config.set("hotkey_draw_arrow", self.edit_hk_draw.text().strip() or "Ctrl+Shift+D")
        self.config.set("hotkey_clear_draw", self.edit_hk_clr.text().strip() or "Ctrl+Shift+E")
        self.config.set("hotkey_translate", self.edit_hk_trans.text().strip() or "Ctrl+Shift+T")
        self.config.set("hotkey_quick_translator", self.edit_hk_qtrans.text().strip() or "Ctrl+Shift+Z")
        
        # Obtener el atajo editado directamente desde la Pestaña Modo Juego o Pestaña Atajos
        if hasattr(self, "edit_hk_game_mode") and self.edit_hk_game_mode.text().strip():
            hk_game_val = self.edit_hk_game_mode.text().strip()
        elif hasattr(self, "edit_hk_game") and self.edit_hk_game.text().strip():
            hk_game_val = self.edit_hk_game.text().strip()
        else:
            hk_game_val = "Ctrl+Shift+Enter"

        self.config.set("hotkey_game_mode", hk_game_val)
        try:
            import juego
            juego.set_game_launch_hotkey(hk_game_val)
        except Exception:
            pass
        self.config.set("translate_from_lang", self.combo_from_lang.currentData() or "en")
        self.config.set("translate_to_lang", self.combo_to_lang.currentData() or "es")
        self.config.set("override_printscreen", override_val)
        self.config.set("autostart", autostart_val)
        self.config.set("auto_copy_clipboard", self.chk_auto_copy.isChecked())
        override_windows_printscreen_key(override_val)
        self.config.set("use_nvenc", self.chk_nvenc.isChecked())
        self.config.set("record_system_audio", self.chk_record_system.isChecked())
        self.config.set("record_mic_audio", self.chk_record_mic.isChecked())
        self.config.set("hdr_fix", self.chk_hdr_fix.isChecked())
        selected_pos = self.card_pos_combo.currentData() or "bottom_left"
        selected_fps = self.fps_combo.currentData() if hasattr(self, "fps_combo") else "auto"
        self.config.set("fps", selected_fps)
        self.config.set("mica_effect", self.chk_mica.isChecked())
        self.config.set("hide_on_capture", self.chk_hide_on_capture.isChecked())
        self.config.set("theme", self.theme_combo.currentText())
        self.config.set("card_position", selected_pos)
        self.config.set("draw_color", self.selected_draw_color.name())

        AutostartManager.set_autostart(autostart_val)
        os.makedirs(img_folder, exist_ok=True)
        os.makedirs(vid_folder, exist_ok=True)
        os.makedirs(aud_folder, exist_ok=True)
        self.accept()

    def register_windows_default_associations(self):
        try:
            if getattr(sys, "frozen", False):
                exe_target = f'"{sys.executable}" "%1"'
                icon_src = sys.executable
            else:
                exe_target = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}" "%1"'
                icon_src = get_resource_path(".py/resources/icon.ico")

            # 1. Catálogo exhaustivo de formatos multimedia soportados
            IMAGE_EXTENSIONS = [
                ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".ico", ".tiff", ".tif",
                ".jfif", ".heic", ".heif", ".avif", ".svg"
            ]
            VIDEO_EXTENSIONS = [
                ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".3gp",
                ".ts", ".mts", ".m2ts", ".vob", ".ogv", ".asf", ".f4v", ".mpg", ".mpeg", ".mpv"
            ]
            AUDIO_EXTENSIONS = [
                ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma", ".opus", ".aiff", ".alac"
            ]

            prog_configs = {
                "Jade.PictureView": ("Imagen de Jade", IMAGE_EXTENSIONS),
                "Jade.VideoView": ("Video de Jade", VIDEO_EXTENSIONS),
                "Jade.AudioView": ("Audio de Jade", AUDIO_EXTENSIONS)
            }

            # 2. Registrar los ProgIDs oficiales en el Registro de Windows
            for prog_id, (friendly_name, exts) in prog_configs.items():
                prog_key_path = rf"Software\Classes\{prog_id}"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prog_key_path) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, friendly_name)
                    winreg.SetValueEx(key, "FriendlyTypeName", 0, winreg.REG_SZ, friendly_name)

                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prog_key_path + r"\DefaultIcon") as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, icon_src)

                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prog_key_path + r"\shell\open\command") as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, exe_target)

                # 3. Vincular cada extensión individual bajo OpenWithProgids y OpenWithList
                for ext in exts:
                    ext_key_path = rf"Software\Classes\{ext}\OpenWithProgids"
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ext_key_path) as key:
                        winreg.SetValueEx(key, prog_id, 0, winreg.REG_SZ, "")

            # 4. Registrar Capacidades de la aplicación para Windows 10/11
            cap_key_path = r"Software\Jade\Capabilities"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cap_key_path) as key:
                winreg.SetValueEx(key, "ApplicationName", 0, winreg.REG_SZ, "Jade")
                winreg.SetValueEx(key, "ApplicationDescription", 0, winreg.REG_SZ, "Visualizador y Reproductor Multimedia de Alto Rendimiento Jade")

            assoc_key_path = r"Software\Jade\Capabilities\FileAssociations"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, assoc_key_path) as key:
                for ext in IMAGE_EXTENSIONS:
                    winreg.SetValueEx(key, ext, 0, winreg.REG_SZ, "Jade.PictureView")
                for ext in VIDEO_EXTENSIONS:
                    winreg.SetValueEx(key, ext, 0, winreg.REG_SZ, "Jade.VideoView")
                for ext in AUDIO_EXTENSIONS:
                    winreg.SetValueEx(key, ext, 0, winreg.REG_SZ, "Jade.AudioView")

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\RegisteredApplications") as key:
                winreg.SetValueEx(key, "Jade", 0, winreg.REG_SZ, r"Software\Jade\Capabilities")

            # 5. Notificar a la shell del explorador de Windows
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)

            # 6. Abrir la configuración oficial de Aplicaciones Predeterminadas de Windows
            try:
                os.system("start ms-settings:defaultapps")
            except Exception:
                pass

            total_exts = len(IMAGE_EXTENSIONS) + len(VIDEO_EXTENSIONS) + len(AUDIO_EXTENSIONS)
            QMessageBox.information(
                self,
                "Jade — App Predeterminada Registrada",
                f"¡Jade se ha registrado exitosamente en Windows para {total_exts} extensiones multimedia!\n\n"
                f"• {len(IMAGE_EXTENSIONS)} Formatos de Fotos (.png, .jpg, .jpeg, .webp, .gif, .avif, etc.)\n"
                f"• {len(VIDEO_EXTENSIONS)} Formatos de Video (.mp4, .mkv, .avi, .mov, .webm, .ts, etc.)\n"
                f"• {len(AUDIO_EXTENSIONS)} Formatos de Audio (.mp3, .wav, .flac, .m4a, .opus, etc.)\n\n"
                f"Se abrió el panel de Windows. Solo haz clic en 'Establecer predeterminado' para Jade."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudieron registrar las extensiones en el sistema: {e}")

from datetime import timedelta


class TextNoteCard(QFrame):
    """Tarjeta de texto responsiva que autoajusta sus botones y dimensiones según el ancho de la ventana."""
    copy_requested = pyqtSignal(str, str)
    pin_requested = pyqtSignal(str)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("TextNoteCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        is_pinned = self.entry.get("pinned", False)
        if is_pinned:
            pin_icon = QLabel()
            pin_icon.setPixmap(get_minimalist_svg_pixmap("pin", "#0078D4", 12, 12))
            header_row.addWidget(pin_icon)

        clock_icon = QLabel()
        clock_icon.setPixmap(get_minimalist_svg_pixmap("clock", "#60CDFF", 12, 12))
        header_row.addWidget(clock_icon)

        time_lbl = QLabel(self.entry.get('display_time', ''))
        time_lbl.setObjectName("HighlightTimeLabel")
        time_lbl.setMinimumWidth(0)
        time_lbl.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold))
        header_row.addWidget(time_lbl)

        note_val = self.entry.get("note", "")
        if note_val:
            clean_note = " ".join(note_val.split())
            display_note = clean_note[:18] + ("..." if len(clean_note) > 18 else "")

            tag_icon = QLabel()
            tag_icon.setPixmap(get_minimalist_svg_pixmap("tag", "#FFB900", 12, 12))

            note_lbl = QLabel(display_note)
            note_lbl.setObjectName("HighlightNoteLabel")
            note_lbl.setMinimumWidth(0)
            note_lbl.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Normal))
            header_row.addStretch()
            header_row.addWidget(tag_icon)
            header_row.addWidget(note_lbl)

        txt_content = self.entry.get("text", "")
        clean_txt = " ".join(txt_content.split())
        preview_text = clean_txt[:110] + ("..." if len(clean_txt) > 110 else "")

        txt_lbl = QLabel(preview_text)
        txt_lbl.setObjectName("PrimaryTextLabel")
        txt_lbl.setWordWrap(True)
        txt_lbl.setMinimumWidth(0)
        txt_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        txt_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        txt_lbl.setFont(QFont("Segoe UI Variable Text", 9))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self.btn_copy = QPushButton(" Copiar Texto")
        self.btn_copy.setIcon(get_minimalist_svg_icon("copy", "#FFFFFF", 14))
        self.btn_copy.setObjectName("PrimaryBtn")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setMinimumWidth(0)
        self.btn_copy.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_copy.clicked.connect(lambda: self.copy_requested.emit(txt_content, self.entry.get("id", "")))

        self.btn_pin = QPushButton(" Desfijar" if is_pinned else " Fijar")
        self.btn_pin.setIcon(get_minimalist_svg_icon("unpin" if is_pinned else "pin", "#FFFFFF" if is_pinned else "adaptive", 14))
        self.btn_pin.setObjectName("PrimaryBtn" if is_pinned else "SecondaryBtn")
        self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pin.setMinimumWidth(0)
        self.btn_pin.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_pin.clicked.connect(lambda: self.pin_requested.emit(self.entry.get("id", "")))

        btn_row.addWidget(self.btn_copy, stretch=1)
        btn_row.addWidget(self.btn_pin)

        layout.addLayout(header_row)
        layout.addWidget(txt_lbl)
        layout.addLayout(btn_row)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        is_pinned = self.entry.get("pinned", False)
        if w < 320:
            self.btn_copy.setText("")
            self.btn_pin.setText("")
        elif w < 400:
            self.btn_copy.setText(" Copiar")
            self.btn_pin.setText("")
        else:
            self.btn_copy.setText(" Copiar Texto")
            self.btn_pin.setText(" Desfijar" if is_pinned else " Fijar")


class QuickNotesWindow(QDialog):
    """Ventana flotante independiente para notas con diseño completamente responsivo y fluido."""
    def __init__(self, history_manager: TextHistoryManager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.days_to_show = 1
        self.setWindowTitle("Jade — Notas Rápidas & Portapapeles OS")
        self.resize(460, 560)
        self.setMinimumSize(280, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        ThemeManager.get_instance().register_child(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.icon_header = QLabel()
        self.icon_header.setPixmap(get_minimalist_svg_pixmap("pin", "adaptive", 18, 18))

        title_lbl = QLabel("Portapapeles Activo & Notas")
        title_lbl.setObjectName("PrimaryTextLabel")
        title_lbl.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))

        btn_add = QPushButton(" Nueva Nota")
        btn_add.setIcon(get_minimalist_svg_icon("plus", "#FFFFFF", 14))
        btn_add.setObjectName("PrimaryBtn")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self.add_custom_note)

        top_bar.addWidget(self.icon_header)
        top_bar.addWidget(title_lbl)
        top_bar.addStretch()
        top_bar.addWidget(btn_add)

        layout.addLayout(top_bar)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar en historial de copias y notas...")
        self.search_box.textChanged.connect(self.refresh_list)
        layout.addWidget(self.search_box)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container_widget = QWidget()
        self.container_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.cards_layout = QVBoxLayout(self.container_widget)
        self.cards_layout.setSpacing(6)
        self.cards_layout.setContentsMargins(4, 4, 4, 4)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.container_widget)
        layout.addWidget(self.scroll_area)

        QTimer.singleShot(10, self.refresh_list)

    def add_custom_note(self):
        text, ok = QInputDialog.getMultiLineText(self, "Nueva Nota Rápida", "Escribe el contenido de la nota:")
        if ok and text.strip():
            self.history_manager.add_entry(text.strip(), "Nota manual")
            self.refresh_list()

    def toggle_pin_entry(self, entry_id: str):
        self.history_manager.toggle_pinned(entry_id)
        self.refresh_list()

    def load_more_days(self):
        self.days_to_show += 1
        self.refresh_list()

    def refresh_list(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self.search_box.text().lower().strip()
        entries = self.history_manager.entries

        if not entries:
            lbl = QLabel("Sin elementos registrados en el portapapeles de Jade.")
            lbl.setObjectName("SubTextLabel")
            lbl.setFont(QFont("Segoe UI Variable Display", 10))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(lbl)
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        grouped = {}

        for entry in entries:
            txt = entry.get("text", "")
            nt = entry.get("note", "")
            if query and (query not in txt.lower() and query not in nt.lower()):
                continue

            edate = entry.get("date", "")
            try:
                dt_obj = datetime.strptime(edate, "%Y-%m-%d")
                days_diff = (datetime.now() - dt_obj).days
                if edate == today_str:
                    group_key = "HOY"
                elif edate == yesterday_str:
                    group_key = "AYER"
                elif days_diff <= 30:
                    group_key = f"DÍA: {dt_obj.strftime('%d/%m/%Y')}"
                else:
                    group_key = f"MES: {dt_obj.strftime('%B %Y').capitalize()}"
            except Exception:
                group_key = "OTROS"

            grouped.setdefault(group_key, []).append(entry)

        all_group_keys = list(grouped.keys())
        visible_group_keys = all_group_keys[:self.days_to_show]

        for group_title in visible_group_keys:
            group_entries = grouped[group_title]

            header_widget = QWidget()
            header_layout = QHBoxLayout(header_widget)
            header_layout.setContentsMargins(0, 4, 0, 4)
            header_layout.setSpacing(6)

            h_icon = QLabel()
            h_icon.setPixmap(get_minimalist_svg_pixmap("calendar", "#60CDFF", 14, 14))
            section_header = QLabel(group_title)
            section_header.setObjectName("HighlightTimeLabel")
            section_header.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))

            header_layout.addWidget(h_icon)
            header_layout.addWidget(section_header)
            header_layout.addStretch()

            self.cards_layout.addWidget(header_widget)

            # Las notas ancladas de esta fecha se sitúan arriba y la última copiada se ubica en primer lugar
            day_pinned = [e for e in group_entries if e.get("pinned", False)]
            day_pinned.sort(key=lambda x: x.get("pinned_time", 0.0), reverse=True)
            day_normal = [e for e in group_entries if not e.get("pinned", False)]
            sorted_entries = day_pinned + day_normal

            for entry in sorted_entries:
                card = TextNoteCard(entry)
                card.copy_requested.connect(self.copy_and_close)
                card.pin_requested.connect(self.toggle_pin_entry)
                self.cards_layout.addWidget(card)

        if len(all_group_keys) > self.days_to_show:
            next_day_title = all_group_keys[self.days_to_show]
            btn_load_more = QPushButton(f" Cargar día anterior ({next_day_title})")
            btn_load_more.setIcon(get_minimalist_svg_icon("chevron_down", "#FFFFFF", 14))
            btn_load_more.setObjectName("PrimaryBtn")
            btn_load_more.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_load_more.setStyleSheet("margin-top: 10px; margin-bottom: 10px; padding: 8px; font-weight: bold;")
            btn_load_more.clicked.connect(self.load_more_days)
            self.cards_layout.addWidget(btn_load_more)

        self.cards_layout.addStretch()

    def showEvent(self, event):
        super().showEvent(event)
        is_dark = ThemeManager.get_instance().is_dark
        self.apply_theme(is_dark)

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
            }}
            QScrollArea {{
                background-color: {p['bg_window']};
                border: none;
            }}
            QLineEdit {{
                background-color: {p['bg_card']};
                color: {p['text_primary']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 6px 10px;
            }}
        """)
        if hasattr(self, "icon_header") and self.icon_header:
            self.icon_header.setPixmap(get_minimalist_svg_pixmap("pin", p['icon_color'], 18, 18))
        if hasattr(self, "refresh_list"):
            self.refresh_list()

    def copy_and_close(self, text: str, entry_id: str = ""):
        QApplication.clipboard().setText(text)
        if entry_id:
            self.history_manager.touch_pinned_entry(entry_id)
        self.close()

class StandaloneGalleryWindow(QDialog):
    """Ventana flotante independiente para la galería multimedia con soporte de pestañas, memoria de selección y diseño responsivo autoajustable."""
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.populated_tabs = set()
        self.img_files = []
        self.vid_files = []
        self.aud_files = []
        self.days_to_show = 1

        self.setWindowTitle("Jade — Galería Multimedia Flotante")
        self.resize(460, 560)
        self.setMinimumSize(280, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        ThemeManager.get_instance().register_child(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title_box = QHBoxLayout()
        self.icon_gal = QLabel()
        self.icon_gal.setPixmap(get_minimalist_svg_pixmap("image", "adaptive", 18, 18))

        title_lbl = QLabel("Galería Flotante Multimedia")
        title_lbl.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))

        title_box.addWidget(self.icon_gal)
        title_box.addWidget(title_lbl)
        title_box.addStretch()
        layout.addLayout(title_box)

        self.tabs = QTabWidget()
        self.tab_images = QWidget()
        self.tab_videos = QWidget()
        self.tab_audios = QWidget()

        self.setup_tab_layout(self.tab_images)
        self.setup_tab_layout(self.tab_videos)
        self.setup_tab_layout(self.tab_audios)

        self.tabs.addTab(self.tab_images, get_minimalist_svg_icon("image", "adaptive", 16), " Fotos")
        self.tabs.addTab(self.tab_videos, get_minimalist_svg_icon("video", "adaptive", 16), " Videos")
        self.tabs.addTab(self.tab_audios, get_minimalist_svg_icon("audio", "adaptive", 16), " Audios")

        last_tab = self.config.get("last_gallery_tab")
        if last_tab is not None and isinstance(last_tab, int) and 0 <= last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)

        self.tabs.currentChanged.connect(self.on_tab_changed)

        layout.addWidget(self.tabs)
        self.load_media()

    def setup_tab_layout(self, tab_widget: QWidget):
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        list_layout = QVBoxLayout(container)
        list_layout.setSpacing(6)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        tab_layout.addWidget(scroll)
        tab_widget.scroll_area = scroll
        tab_widget.container = container
        tab_widget.list_layout = list_layout

    def load_more_days(self):
        self.days_to_show += 1
        self.populated_tabs.clear()
        current_index = self.tabs.currentIndex()
        if current_index == 0:
            self.populate_tab(self.tab_images, self.img_files, is_video=False)
        elif current_index == 1:
            self.populate_tab(self.tab_videos, self.vid_files, is_video=True)
        else:
            self.populate_tab(self.tab_audios, self.aud_files, is_video=False)
        self.populated_tabs.add(current_index)

    def on_tab_changed(self, index: int):
        self.config.set("last_gallery_tab", index)
        if index not in self.populated_tabs:
            if index == 0:
                target_tab, file_list, is_video = self.tab_images, self.img_files, False
            elif index == 1:
                target_tab, file_list, is_video = self.tab_videos, self.vid_files, True
            else:
                target_tab, file_list, is_video = self.tab_audios, self.aud_files, False
            self.populate_tab(target_tab, file_list, is_video)
            self.populated_tabs.add(index)

    def showEvent(self, event):
        super().showEvent(event)
        is_dark = ThemeManager.get_instance().is_dark
        self.apply_theme(is_dark)

    def apply_theme(self, is_dark: bool = None):
        if is_dark is None:
            is_dark = ThemeManager.get_instance().is_dark
        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass
        p = ThemePalette.get(is_dark)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg_window']};
                color: {p['text_primary']};
            }}
            QTabWidget::pane {{
                border: none;
                background-color: {p['bg_window']};
            }}
            QTabBar::tab {{
                background-color: {p['bg_card']};
                color: {p['text_primary']};
                padding: 6px 14px;
                border-radius: 6px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {p['nav_btn_checked_bg']};
                color: {p['nav_btn_accent']};
                font-weight: bold;
            }}
        """)
        if hasattr(self, "icon_gal") and self.icon_gal:
            self.icon_gal.setPixmap(get_minimalist_svg_pixmap("image", p['icon_color'], 18, 18))
        if hasattr(self, "tabs") and self.tabs:
            self.tabs.setTabIcon(0, get_minimalist_svg_icon("image", p['icon_color'], 16))
            self.tabs.setTabIcon(1, get_minimalist_svg_icon("video", p['icon_color'], 16))
            self.tabs.setTabIcon(2, get_minimalist_svg_icon("audio", p['icon_color'], 16))
        if hasattr(self, "load_media"):
            self.load_media()

    def load_media(self):
        img_dir = self.config.get("images_folder")
        vid_dir = self.config.get("videos_folder")
        aud_dir = self.config.get("audios_folder")

        self.img_files = [os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))] if os.path.exists(img_dir) else []
        self.vid_files = [os.path.join(vid_dir, f) for f in os.listdir(vid_dir) if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))] if os.path.exists(vid_dir) else []
        self.aud_files = [os.path.join(aud_dir, f) for f in os.listdir(aud_dir) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))] if os.path.exists(aud_dir) else []

        self.img_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        self.vid_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        self.aud_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        self.populated_tabs.clear()
        current_index = self.tabs.currentIndex()
        if current_index == 0:
            self.populate_tab(self.tab_images, self.img_files, is_video=False)
        elif current_index == 1:
            self.populate_tab(self.tab_videos, self.vid_files, is_video=True)
        else:
            self.populate_tab(self.tab_audios, self.aud_files, is_video=False)
        self.populated_tabs.add(current_index)

    def populate_tab(self, tab_widget: QWidget, file_list: list, is_video: bool):
        layout = tab_widget.list_layout
        tab_widget.setUpdatesEnabled(False)
        try:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not file_list:
                lbl = QLabel("No hay archivos multimedia guardados en esta sección.")
                lbl.setStyleSheet("color: #8A8A8A; font-size: 13px; padding: 20px;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(lbl)
                return

            today_date = datetime.now().date()
            yesterday_date = today_date - timedelta(days=1)

            grouped = {}
            for filepath in file_list:
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    fdate = mtime.date()
                    days_diff = (today_date - fdate).days

                    if fdate == today_date:
                        group_title = "HOY"
                    elif fdate == yesterday_date:
                        group_title = "AYER"
                    elif days_diff <= 30:
                        group_title = f"DÍA: {mtime.strftime('%d/%m/%Y')}"
                    else:
                        group_title = f"MES: {mtime.strftime('%B %Y').capitalize()}"
                except Exception:
                    group_title = "OTROS MEDIOS"

                grouped.setdefault(group_title, []).append(filepath)

            all_group_keys = list(grouped.keys())
            visible_group_keys = all_group_keys[:self.days_to_show]

            visible_files = []
            for g_key in visible_group_keys:
                visible_files.extend(grouped[g_key])
            self.current_visible_file_list = visible_files

            for group_title in visible_group_keys:
                group_files = grouped[group_title]
                section_header = QLabel(f" {group_title} ")
                section_header.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))
                section_header.setStyleSheet("""
                    color: #60CDFF;
                    background-color: rgba(0, 120, 212, 0.15);
                    border-left: 3px solid #0078D4;
                    border-radius: 4px;
                    padding: 4px 8px;
                    margin-top: 6px;
                    margin-bottom: 2px;
                """)
                layout.addWidget(section_header)

                for fpath in group_files:
                    card = GalleryCard(fpath)
                    card.preview_requested.connect(self.on_item_preview)
                    card.delete_requested.connect(self.delete_and_reload)
                    card.copy_requested.connect(self.on_card_copied)
                    card.ocr_requested.connect(self.on_card_ocr_requested)
                    layout.addWidget(card)

            if len(all_group_keys) > self.days_to_show:
                next_day_title = all_group_keys[self.days_to_show]
                btn_load_more = QPushButton(f" Cargar día anterior ({next_day_title})")
                btn_load_more.setIcon(get_minimalist_svg_icon("chevron_down", "#FFFFFF", 14))
                btn_load_more.setObjectName("PrimaryBtn")
                btn_load_more.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_load_more.setStyleSheet("margin-top: 8px; margin-bottom: 8px; padding: 8px; font-weight: bold;")
                btn_load_more.clicked.connect(self.load_more_days)
                layout.addWidget(btn_load_more)

            layout.addStretch()
        finally:
            tab_widget.setUpdatesEnabled(True)

    def on_card_ocr_requested(self, pixmap: QPixmap):
        if hasattr(self, "parent") and self.parent():
            main_win = self.parent()
            if hasattr(main_win, "perform_ocr"):
                main_win.perform_ocr(pixmap)

    def on_card_copied(self):
        current_tab = self.tabs.currentIndex()
        self.config.set("last_gallery_tab", current_tab)
        self.close()

    def on_item_preview(self, filepath: str):
        current_list = getattr(self, "current_visible_file_list", [filepath])
        if filepath in current_list:
            curr_idx = current_list.index(filepath)
        else:
            curr_idx = 0
            current_list = [filepath]
        dialog = HDMediaViewerDialog(filepath, parent=self, file_list=current_list, current_index=curr_idx)
        dialog.exec()

    def delete_and_reload(self, filepath: str):
        try:
            os.remove(filepath)
            self.load_media()
        except Exception as e:
            log_message(f"Error eliminando archivo: {e}")

class TextHistoryWidget(QWidget):
    """Pestaña de historial de textos copiados con carga ultraligera de 10 entradas por acción."""
    def __init__(self, history_manager: TextHistoryManager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.items_to_show = 10
        self.init_ui()
        ThemeManager.get_instance().register_child(self)

    def apply_theme(self, is_dark: bool = None):
        if hasattr(self, "refresh_list"):
            self.refresh_list()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        top_controls = QHBoxLayout()
        top_controls.setSpacing(8)

        icon_title = QLabel()
        icon_title.setPixmap(get_minimalist_svg_pixmap("note", "adaptive", 18, 18))

        lbl_title = QLabel("Historial de Textos Copiados & Notas")
        lbl_title.setObjectName("PrimaryTextLabel")
        lbl_title.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))

        btn_quick_window = QPushButton(" Ventana Dedicada")
        btn_quick_window.setIcon(get_minimalist_svg_icon("pin", "#FFFFFF", 14))
        btn_quick_window.setObjectName("PrimaryBtn")
        btn_quick_window.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_quick_window.clicked.connect(self.open_quick_notes_window)

        btn_clear = QPushButton(" Borrar Caché")
        btn_clear.setIcon(get_minimalist_svg_icon("trash", "#FF99A4", 14))
        btn_clear.setObjectName("DangerBtn")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_all_cache)

        top_controls.addWidget(icon_title)
        top_controls.addWidget(lbl_title)
        top_controls.addStretch()
        top_controls.addWidget(btn_quick_window)
        top_controls.addWidget(btn_clear)

        layout.addLayout(top_controls)

        self.list_widget = QListWidget()
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.list_widget)

        self.refresh_list()

    def open_quick_notes_window(self):
        win = QuickNotesWindow(self.history_manager, self)
        win.exec()

    def load_more_entries(self):
        self.items_to_show += 10
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        entries = self.history_manager.entries

        if not entries:
            item = QListWidgetItem("No hay textos guardados en el historial de Jade.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return

        visible_entries = entries[:self.items_to_show]

        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        grouped = {}
        for entry in visible_entries:
            edate = entry.get("date", "")
            try:
                dt_obj = datetime.strptime(edate, "%Y-%m-%d")
                days_diff = (datetime.now() - dt_obj).days
                if edate == today_str:
                    group_key = "🗓️ HOY"
                elif edate == yesterday_str:
                    group_key = "🗓️ AYER"
                elif days_diff <= 30:
                    group_key = f"📅 DÍA: {dt_obj.strftime('%d/%m/%Y')}"
                else:
                    group_key = f"📆 MES: {dt_obj.strftime('%B %Y').capitalize()}"
            except Exception:
                group_key = "📅 OTROS"

            grouped.setdefault(group_key, []).append(entry)

        for group, group_entries in grouped.items():
            header_item = QListWidgetItem(f"--- {group} ---")
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            header_item.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Bold))
            self.list_widget.addItem(header_item)

            for entry in group_entries:
                item_widget = QWidget()
                item_layout = QVBoxLayout(item_widget)
                item_layout.setContentsMargins(6, 6, 6, 6)
                item_layout.setSpacing(6)

                header_layout = QHBoxLayout()
                header_layout.setSpacing(6)

                clock_icon = QLabel()
                clock_icon.setPixmap(get_minimalist_svg_pixmap("clock", "#60CDFF", 12, 12))
                header_layout.addWidget(clock_icon)

                lbl_date = QLabel(entry.get('display_time'))
                lbl_date.setObjectName("HighlightTimeLabel")
                lbl_date.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold))
                header_layout.addWidget(lbl_date)

                note_val = entry.get("note", "")
                if note_val:
                    tag_icon = QLabel()
                    tag_icon.setPixmap(get_minimalist_svg_pixmap("tag", "#FFB900", 12, 12))

                    lbl_note = QLabel(note_val)
                    lbl_note.setObjectName("HighlightNoteLabel")
                    lbl_note.setFont(QFont("Segoe UI Variable Display", 9))
                    header_layout.addStretch()
                    header_layout.addWidget(tag_icon)
                    header_layout.addWidget(lbl_note)

                txt_edit = QTextEdit()
                txt_edit.setPlainText(entry.get("text", ""))
                txt_edit.setReadOnly(True)
                txt_edit.setMaximumHeight(80)

                actions_layout = QHBoxLayout()
                actions_layout.setSpacing(6)

                is_dark_curr = ThemeManager.get_instance().is_dark
                btn_copy = QPushButton(" Copiar Texto")
                btn_copy.setIcon(get_minimalist_svg_icon("copy", "#FFFFFF", 16))
                btn_copy.setObjectName("PrimaryBtn")
                btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_copy.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn_copy.clicked.connect(lambda _, txt=entry.get("text"): self.copy_text(txt))

                btn_note = QPushButton(" Nota")
                btn_note.setIcon(get_minimalist_svg_icon("rename", "adaptive", 16))
                btn_note.setObjectName("SecondaryBtn")
                btn_note.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_note.clicked.connect(lambda _, eid=entry.get("id"), curr=entry.get("note"): self.edit_note(eid, curr))

                btn_del = QPushButton()
                btn_del.setIcon(get_minimalist_svg_icon("delete", "#FF99A4" if is_dark_curr else "#C42B1C", 16))
                btn_del.setObjectName("DangerBtn")
                btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_del.clicked.connect(lambda _, eid=entry.get("id"): self.delete_entry(eid))

                actions_layout.addWidget(btn_copy)
                actions_layout.addWidget(btn_note)
                actions_layout.addWidget(btn_del)

                item_layout.addLayout(header_layout)
                item_layout.addWidget(txt_edit)
                item_layout.addLayout(actions_layout)

                list_item = QListWidgetItem(self.list_widget)
                list_item.setSizeHint(item_widget.sizeHint())
                self.list_widget.setItemWidget(list_item, item_widget)

        if len(entries) > self.items_to_show:
            remaining = len(entries) - self.items_to_show
            load_item = QListWidgetItem()
            btn_load_more = QPushButton(f" Cargar 10 entradas más ({remaining} restantes)")
            btn_load_more.setIcon(get_minimalist_svg_icon("chevron_down", "#FFFFFF", 14))
            btn_load_more.setObjectName("PrimaryBtn")
            btn_load_more.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_load_more.setStyleSheet("padding: 8px; font-weight: bold; margin: 6px;")
            btn_load_more.clicked.connect(self.load_more_entries)
            load_item.setSizeHint(btn_load_more.sizeHint())
            self.list_widget.addItem(load_item)
            self.list_widget.setItemWidget(load_item, btn_load_more)

    def copy_text(self, text: str):
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Jade", "Texto copiado al portapapeles.")

    def edit_note(self, entry_id: str, current_note: str):
        note, ok = QInputDialog.getText(self, "Añadir / Editar Nota", "Escribe una nota para este texto:", QLineEdit.EchoMode.Normal, current_note)
        if ok:
            self.history_manager.update_note(entry_id, note)
            self.refresh_list()

    def delete_entry(self, entry_id: str):
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Estás seguro de que deseas eliminar esta entrada del historial?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.delete_entry(entry_id)
            self.refresh_list()

    def clear_all_cache(self):
        reply = QMessageBox.question(
            self,
            "Confirmar vaciado de caché",
            "¿Estás seguro de que deseas eliminar TODO el historial de textos de Jade?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.clear_cache()
            self.refresh_list()

def apply_app_theme(config: ConfigManager = None) -> str:
    cfg_theme = config.get("theme", "sistema") if config else "sistema"
    tm = ThemeManager.get_instance()
    tm.set_config_theme(cfg_theme)
    tm.apply_global_styles()
    return tm.effective_theme

class SaveCaptureWorker(QThread):
    """Hilo secundario dedicado para guardar la captura en disco de forma instantánea sin bloquear la UI ni el portapapeles."""
    finished = pyqtSignal(str)

    def __init__(self, pixmap: QPixmap, save_dir: str, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.save_dir = save_dir

    def run(self):
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            filename = f"Captura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.save_dir, filename)
            self.pixmap.save(filepath, "PNG")
            self.finished.emit(filepath)
        except Exception as e:
            log_message(f"Error guardando captura en hilo: {e}")
            self.finished.emit("")

class SmoothScrollArea(QScrollArea):
    """Área de desplazamiento con animación fluida de inercia y caché de posición para sensación premium."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._target_pos = None
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._clear_target)
        self.verticalScrollBar().sliderPressed.connect(self._clear_target)

    def _clear_target(self):
        self._target_pos = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        sb = self.verticalScrollBar()
        current = sb.value() if self._target_pos is None else self._target_pos
        step = -int(delta * 1.3)
        target = max(sb.minimum(), min(sb.maximum(), current + step))
        self._target_pos = target

        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()

        self._anim.setStartValue(sb.value())
        self._anim.setEndValue(target)
        self._anim.start()
        event.accept()

class MainWindow(QMainWindow):
    """Ventana principal de la aplicación Jade."""
    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self.history_manager = TextHistoryManager()
        self.is_recording = False
        self.recorder_thread = None
        self.was_visible_before_capture = False
        self.is_capturing_active = False
        self.really_quit = False
        self.is_dark = ThemeManager.get_instance().is_dark
        self.current_applied_theme = None
        self.view_mode = self.config.get("view_mode") or "detail"

        self.setWindowTitle("Jade")
        self.resize(1060, 720)
        self.setMinimumSize(760, 520)

        icon_path = get_resource_path(".py/resources/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        os.makedirs(self.config.get("images_folder"), exist_ok=True)
        os.makedirs(self.config.get("videos_folder"), exist_ok=True)

        self.floating_bar = FloatingControlBar()
        self.floating_bar.pause_requested.connect(self.pause_recording)
        self.floating_bar.resume_requested.connect(self.resume_recording)
        self.floating_bar.stop_requested.connect(self.toggle_record)
        self.floating_bar.settings_requested.connect(self.open_settings)

        self.is_recording_audio = False
        self.audio_recorder_thread = None

        override_windows_printscreen_key(self.config.get("override_printscreen"))
        self.scan_media_files()
        self.init_ui()
        self.setup_tray_icon()
        self.setup_hotkey()
        self.setup_shortcuts()
        self.apply_theme()
        self.setup_clipboard_listener()

        self.theme_timer = QTimer(self)
        self.theme_timer.setInterval(1000)
        self.theme_timer.timeout.connect(self.check_system_theme_change)
        self.theme_timer.start()

        ThemeManager.get_instance().set_config_theme(self.config.get("theme", "sistema"))
        ThemeManager.get_instance().register_child(self)
        ThemeManager.get_instance().theme_changed.connect(self.on_theme_changed)

        self.setup_ipc_server()
        log_message("Jade iniciado en modo ultraligero.")

    def setup_ipc_server(self):
        self.ipc_server = QLocalServer(self)
        self.ipc_server.removeServer("Jade_SingleInstance_IPC_Server")
        self.ipc_server.listen("Jade_SingleInstance_IPC_Server")
        self.ipc_server.newConnection.connect(self._handle_ipc_incoming_connection)

    def _handle_ipc_incoming_connection(self):
        client_socket = self.ipc_server.nextPendingConnection()
        if client_socket:
            if client_socket.waitForReadyRead(600):
                raw_bytes = client_socket.readAll().data()
                try:
                    args_list = json.loads(raw_bytes.decode("utf-8"))
                    self.process_command_args(args_list)
                except Exception as e:
                    log_message(f"Error procesando argumentos IPC: {e}")
            client_socket.disconnectFromServer()

    def check_system_theme_change(self):
        cfg_theme = self.config.get("theme")
        if cfg_theme in ("oscuro", "claro"):
            target_theme = cfg_theme
        else:
            target_theme = detect_windows_system_theme()

        if getattr(self, "current_applied_theme", None) != target_theme:
            self.apply_theme()

    def setup_shortcuts(self):
        for attr in (
            "_shortcut_cap", "_shortcut_rec", "_shortcut_rec_aud", "_shortcut_pause",
            "_shortcut_hist", "_shortcut_gal", "_shortcut_tog", "_shortcut_trans",
            "_shortcut_qtrans", "_shortcut_game", "_shortcut_pin"
        ):
            if hasattr(self, attr):
                sc = getattr(self, attr)
                if sc:
                    sc.setParent(None)
                setattr(self, attr, None)

    def setup_hotkey(self):
        if hasattr(self, "hotkey_thread") and self.hotkey_thread:
            self.hotkey_thread.stop()

        hk_cap = self.config.get("hotkey_capture") or "PrtScn"
        hk_rec = self.config.get("hotkey_record") or "Ctrl+Shift+R"
        hk_rec_aud = self.config.get("hotkey_record_audio") or "Ctrl+Shift+A"
        hk_pause = self.config.get("hotkey_pause") or "Ctrl+Shift+P"
        hk_hist = self.config.get("hotkey_text_history") or "Ctrl+Shift+H"
        hk_gal = self.config.get("hotkey_media_gallery") or "Ctrl+Shift+G"
        hk_tog = self.config.get("hotkey_toggle_hotkeys") or "Ctrl+Shift+X"
        hk_draw = self.config.get("hotkey_draw_arrow") or "Ctrl+Shift+D"
        hk_clr = self.config.get("hotkey_clear_draw") or "Ctrl+Shift+E"
        hk_trans = self.config.get("hotkey_translate") or "Ctrl+Shift+T"
        hk_qtrans = self.config.get("hotkey_quick_translator") or "Ctrl+Shift+Z"
        hk_game = self.config.get("hotkey_game_mode") or "Ctrl+Shift+Enter"
        hk_pin = self.config.get("hotkey_pin_note") or "Ctrl+Shift+C"

        self.hotkey_thread = GlobalHotkeyThread(hk_cap, hk_rec, hk_rec_aud, hk_pause, hk_hist, hk_gal, hk_tog, hk_draw, hk_clr, hk_trans, hk_qtrans, hk_game, hk_pin, self)
        self.hotkey_thread.capture_triggered.connect(self.trigger_capture)
        self.hotkey_thread.record_triggered.connect(self.toggle_record)
        self.hotkey_thread.record_audio_triggered.connect(self.toggle_record_audio)
        self.hotkey_thread.pause_triggered.connect(self.pause_recording)
        self.hotkey_thread.history_triggered.connect(self.open_quick_notes_window)
        self.hotkey_thread.gallery_triggered.connect(self.open_standalone_gallery_window)
        self.hotkey_thread.toggle_hotkeys_triggered.connect(self.on_hotkeys_toggled)
        self.hotkey_thread.draw_arrow_triggered.connect(self.toggle_recording_draw_mode)
        self.hotkey_thread.clear_draw_triggered.connect(self.clear_recording_annotations)
        self.hotkey_thread.translate_triggered.connect(self.trigger_translate_area)
        self.hotkey_thread.quick_translator_triggered.connect(self.open_quick_translator_window)
        self.hotkey_thread.game_mode_triggered.connect(self.start_direct_game_translation)
        self.hotkey_thread.pin_note_triggered.connect(self.trigger_pin_selected_text)
        self.hotkey_thread.start()

    def on_theme_changed(self, mode: str, is_dark: bool):
        self.apply_theme(is_dark)
        if hasattr(self, "_galeria_win") and self._galeria_win is not None:
            try:
                self._galeria_win.apply_theme(is_dark)
            except Exception:
                pass
        if hasattr(self, "game_win") and self.game_win is not None:
            try:
                self.game_win.apply_theme(is_dark)
            except Exception:
                pass
        if hasattr(self, "_active_cards"):
            for card in list(self._active_cards):
                try:
                    if hasattr(card, "apply_theme"):
                        card.apply_theme(is_dark)
                except Exception:
                    pass
        try:
            self.load_gallery()
        except Exception:
            pass

    def apply_theme(self, is_dark: bool = None):
        tm = ThemeManager.get_instance()
        if is_dark is None:
            is_dark = tm.is_dark
        self.is_dark = is_dark
        self.current_applied_theme = tm.effective_theme
        p = tm.get_palette()

        try:
            enable_win11_effects(int(self.winId()), dark_mode=is_dark)
        except Exception:
            pass

        # Actualizar barra lateral
        if hasattr(self, "sidebar_frame") and self.sidebar_frame:
            self.sidebar_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {p['sidebar_bg']};
                    border: 1px solid {p['sidebar_border']};
                    border-radius: 10px;
                }}
            """)

        # Actualizar botones de navegación con íconos contrastantes según tema
        if hasattr(self, "nav_buttons"):
            nav_icon_names = ["image", "video", "audio", "note"]
            for i, btn in enumerate(self.nav_buttons):
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: 6px;
                    }}
                    QPushButton:hover {{
                        background-color: {p['nav_btn_hover']};
                    }}
                    QPushButton:checked {{
                        background-color: {p['nav_btn_checked_bg']};
                        border-left: 3px solid {p['nav_btn_accent']};
                        border-radius: 4px;
                    }}
                """)
                if i < len(nav_icon_names):
                    btn.setIcon(get_minimalist_svg_icon(nav_icon_names[i], p['icon_color'], 18))

        if hasattr(self, "btn_galeria_pro") and self.btn_galeria_pro:
            self.btn_galeria_pro.setIcon(get_minimalist_svg_icon("gallery_pro", p['icon_color'], 18))
            self.btn_galeria_pro.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: rgba(0, 120, 212, 0.18);
                }}
            """)

        if hasattr(self, "btn_gear") and self.btn_gear:
            self.btn_gear.setIcon(get_minimalist_svg_icon("settings", p['icon_color'], 18))
            self.btn_gear.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: {p['nav_btn_hover']};
                }}
            """)

        # Actualizar pestañas de la galería y sus áreas de desplazamiento
        for tab in [getattr(self, 'tab_images', None), getattr(self, 'tab_videos', None), getattr(self, 'tab_audios', None)]:
            if tab:
                tab.setStyleSheet(f"background-color: {p['bg_window']};")
                if hasattr(tab, "scroll_area") and tab.scroll_area:
                    tab.scroll_area.setStyleSheet(f"background-color: {p['bg_window']}; border: none;")
                    if tab.scroll_area.viewport():
                        tab.scroll_area.viewport().setStyleSheet(f"background-color: {p['bg_window']};")
                if hasattr(tab, "container") and tab.container:
                    tab.container.setStyleSheet(f"background-color: {p['bg_window']};")
                if hasattr(tab, "btn_floating_more") and tab.btn_floating_more:
                    tab.btn_floating_more.setIcon(get_minimalist_svg_icon("chevron_down", p['text_primary'], 20))
                    tab.btn_floating_more.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {p['bg_floating']};
                            border: 1px solid {p['border_strong']};
                            border-radius: 20px;
                            padding: 0px;
                        }}
                        QPushButton:hover {{
                            background-color: rgba(0, 120, 212, 0.92);
                            border: 1px solid rgba(255, 255, 255, 0.35);
                        }}
                        QPushButton:pressed {{
                            background-color: #005A9E;
                        }}
                    """)

        if hasattr(self, "tab_text_history") and hasattr(self.tab_text_history, "apply_theme"):
            self.tab_text_history.apply_theme(is_dark)
        if hasattr(self, "tray_menu") and self.tray_menu:
            self.tray_menu.setStyleSheet(ThemePalette.get_menu_style(is_dark))

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # Barra lateral izquierda refinada al estilo Windows 11 Fluent
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setFixedWidth(58)
        self.sidebar_frame.setStyleSheet("""
            QFrame {
                background-color: #202020;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
            }
        """)

        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(4, 10, 4, 10)
        sidebar_layout.setSpacing(6)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        class AvatarProfileButton(QPushButton):
            def __init__(self, config: ConfigManager, parent=None):
                super().__init__(parent)
                self.config = config
                self.setFixedSize(40, 40)
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setToolTip("Cambiar foto de perfil")
                self.setStyleSheet("background: transparent; border: none;")
                self._avatar_pixmap = None
                self.load_avatar()
                self.clicked.connect(self.select_avatar)

            def load_avatar(self):
                avatar_path = self.config.get("user_avatar")
                if avatar_path and os.path.exists(avatar_path):
                    pix = QPixmap(avatar_path)
                    if not pix.isNull():
                        self._avatar_pixmap = pix
                    else:
                        self._avatar_pixmap = None
                else:
                    self._avatar_pixmap = None
                self.update()

            def select_avatar(self):
                fpath, _ = QFileDialog.getOpenFileName(
                    self, "Seleccionar Foto de Perfil", "",
                    "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)"
                )
                if fpath and os.path.exists(fpath):
                    self.config.set("user_avatar", fpath)
                    self.load_avatar()

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                rect = QRectF(1, 1, self.width() - 2, self.height() - 2)

                path = QPainterPath()
                path.addEllipse(rect)
                painter.setClipPath(path)

                if self._avatar_pixmap and not self._avatar_pixmap.isNull():
                    pw = float(self._avatar_pixmap.width())
                    ph = float(self._avatar_pixmap.height())
                    scale = max(rect.width() / pw, rect.height() / ph)
                    sw = pw * scale
                    sh = ph * scale
                    sx = rect.x() + (rect.width() - sw) / 2.0
                    sy = rect.y() + (rect.height() - sh) / 2.0
                    painter.drawPixmap(QRectF(sx, sy, sw, sh), self._avatar_pixmap, QRectF(0, 0, pw, ph))
                else:
                    painter.fillRect(rect, QColor(36, 36, 36))
                    icon_pix = get_minimalist_svg_pixmap("sparkle", "#CCCCCC", 18, 18)
                    ix = rect.x() + (rect.width() - 18) / 2.0
                    iy = rect.y() + (rect.height() - 18) / 2.0
                    painter.drawPixmap(int(ix), int(iy), icon_pix)

        self.btn_avatar = AvatarProfileButton(self.config, self)
        sidebar_layout.addWidget(self.btn_avatar, 0, Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addSpacing(16)

        self.nav_buttons = []
        nav_items = [
            ("image", "Imágenes", 0),
            ("video", "Videos", 1),
            ("audio", "Audios", 2),
            ("note", "Historial de Textos", 3),
        ]

        def create_nav_btn(icon_name, tooltip, target_idx):
            btn = QPushButton()
            btn.setIcon(get_minimalist_svg_icon(icon_name, "adaptive", 18))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tooltip)
            btn.setFixedSize(38, 38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.06);
                }
                QPushButton:checked {
                    background-color: rgba(255, 255, 255, 0.12);
                    border-left: 3px solid #60CDFF;
                    border-radius: 4px;
                }
            """)
            btn.clicked.connect(lambda _, idx=target_idx: self.switch_category_tab(idx))
            return btn

        for icon_key, tip, idx in nav_items:
            btn = create_nav_btn(icon_key, tip, idx)
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)

        sidebar_layout.addSpacing(8)

        self.btn_galeria_pro = QPushButton()
        self.btn_galeria_pro.setIcon(get_minimalist_svg_icon("gallery_pro", "adaptive", 18))
        self.btn_galeria_pro.setIconSize(QSize(18, 18))
        self.btn_galeria_pro.setToolTip("Galería Fotos Pro")
        self.btn_galeria_pro.setFixedSize(38, 38)
        self.btn_galeria_pro.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_galeria_pro.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 212, 0.22);
            }
        """)
        self.btn_galeria_pro.clicked.connect(lambda: self.open_galeria_app())
        sidebar_layout.addWidget(self.btn_galeria_pro, 0, Qt.AlignmentFlag.AlignCenter)

        sidebar_layout.addStretch()

        self.btn_gear = QPushButton()
        self.btn_gear.setIcon(get_minimalist_svg_icon("settings", "adaptive", 18))
        self.btn_gear.setIconSize(QSize(18, 18))
        self.btn_gear.setToolTip("Opciones y Ajustes")
        self.btn_gear.setFixedSize(38, 38)
        self.btn_gear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_gear.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)
        self.btn_gear.clicked.connect(self.show_gear_menu)
        sidebar_layout.addWidget(self.btn_gear, 0, Qt.AlignmentFlag.AlignCenter)

        root_layout.addWidget(self.sidebar_frame)

        # Contenedor principal de contenidos
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.blockSignals(True)

        self.tab_images = QWidget()
        self.tab_videos = QWidget()
        self.tab_audios = QWidget()
        self.tab_text_history = TextHistoryWidget(self.history_manager, self)

        self.setup_gallery_tab(self.tab_images)
        self.setup_gallery_tab(self.tab_videos)
        self.setup_gallery_tab(self.tab_audios)

        self.tabs.addTab(self.tab_images, "Imágenes")
        self.tabs.addTab(self.tab_videos, "Videos")
        self.tabs.addTab(self.tab_audios, "Audios")
        self.tabs.addTab(self.tab_text_history, "Textos")

        self.tabs.blockSignals(False)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        root_layout.addWidget(self.tabs, stretch=1)
        self.status_label = QLabel()

        self.switch_category_tab(0)

    def switch_category_tab(self, index: int):
        self.tabs.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def show_gear_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(ThemePalette.get_menu_style(ThemeManager.get_instance().is_dark))
        act_mosaic = menu.addAction(get_minimalist_svg_icon("mosaic", "adaptive", 16), "Vista Mosaico")
        act_detail = menu.addAction(get_minimalist_svg_icon("detail", "adaptive", 16), "Vista Detalle")
        menu.addSeparator()
        act_pro = menu.addAction(get_minimalist_svg_icon("image", "#0078D4", 16), "Galería Fotos Pro")
        act_game = menu.addAction(get_minimalist_svg_icon("game", "adaptive", 16), "Modo Juego")
        menu.addSeparator()
        act_settings = menu.addAction(get_minimalist_svg_icon("settings", "adaptive", 16), "Ajustes de Jade")

        act_mosaic.triggered.connect(lambda: self.set_view_mode("mosaic"))
        act_detail.triggered.connect(lambda: self.set_view_mode("detail"))
        act_pro.triggered.connect(lambda: self.open_galeria_app())
        act_game.triggered.connect(self.open_game_translator)
        act_settings.triggered.connect(self.open_settings)

        menu.exec(self.btn_gear.mapToGlobal(QPoint(self.btn_gear.width() + 6, -60)))

    def setup_gallery_tab(self, tab_widget: QWidget):
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        p = ThemeManager.get_instance().get_palette()
        tab_widget.setStyleSheet(f"background-color: {p['bg_window']};")

        scroll_area = SmoothScrollArea(tab_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet(f"background-color: {p['bg_window']}; border: none;")
        scroll_area.viewport().setStyleSheet(f"background-color: {p['bg_window']};")

        container = QWidget()
        container.setStyleSheet(f"background-color: {p['bg_window']};")
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        list_layout = QVBoxLayout(container)
        list_layout.setSpacing(6)
        list_layout.setContentsMargins(8, 6, 8, 8)
        list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        btn_floating = QPushButton(tab_widget)
        btn_floating.setIcon(get_minimalist_svg_icon("chevron_down", "#FFFFFF", 20))
        btn_floating.setIconSize(QSize(20, 20))
        btn_floating.setToolTip("Cargar día anterior")
        btn_floating.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_floating.setFixedSize(40, 40)
        btn_floating.setStyleSheet("""
            QPushButton {
                background-color: rgba(28, 28, 28, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 20px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 212, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.35);
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        shadow = QGraphicsDropShadowEffect(btn_floating)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        btn_floating.setGraphicsEffect(shadow)
        btn_floating.hide()
        btn_floating.clicked.connect(self.load_more_days)

        orig_resize = tab_widget.resizeEvent
        def on_tab_resize(event):
            orig_resize(event)
            if hasattr(tab_widget, "btn_floating_more") and tab_widget.btn_floating_more:
                btn = tab_widget.btn_floating_more
                bx = (tab_widget.width() - btn.width()) // 2
                by = tab_widget.height() - btn.height() - 16
                btn.move(max(10, bx), max(10, by))
                btn.raise_()

        tab_widget.resizeEvent = on_tab_resize
        tab_widget.scroll_area = scroll_area
        tab_widget.container = container
        tab_widget.grid_layout = list_layout
        tab_widget.btn_floating_more = btn_floating

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "view_mode", "detail") == "mosaic":
            if not hasattr(self, "_mosaic_resize_timer"):
                self._mosaic_resize_timer = QTimer(self)
                self._mosaic_resize_timer.setSingleShot(True)
                self._mosaic_resize_timer.setInterval(200)
                self._mosaic_resize_timer.timeout.connect(self._on_mosaic_resized)
            self._mosaic_resize_timer.start()

    def _on_mosaic_resized(self):
        curr_w = self.width()
        if getattr(self, "_last_mosaic_width", 0) != curr_w:
            self._last_mosaic_width = curr_w
            self.render_current_gallery_tab()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
                QTimer.singleShot(0, self.hide)
                event.ignore()
                return
        super().changeEvent(event)

    def set_view_mode(self, mode: str):
        self.view_mode = mode
        self.config.set("view_mode", mode)
        if hasattr(self, "btn_view_detail"):
            self.btn_view_detail.setChecked(mode == "detail")
        if hasattr(self, "btn_view_mosaic"):
            self.btn_view_mosaic.setChecked(mode == "mosaic")
        if hasattr(self, "populated_tabs"):
            self.populated_tabs.clear()
        self.render_current_gallery_tab()
        if hasattr(self, "populated_tabs"):
            self.populated_tabs.add(self.tabs.currentIndex())

    def on_tab_changed(self, index: int):
        self.days_to_show = 1
        if not hasattr(self, "populated_tabs"):
            self.populated_tabs = set()

        if hasattr(self, "btn_view_detail") and hasattr(self, "btn_view_mosaic"):
            is_media = (index != 3)
            self.btn_view_detail.setEnabled(is_media)
            self.btn_view_mosaic.setEnabled(is_media)

        if index == 3:
            self.tab_text_history.refresh_list()
        else:
            if index not in self.populated_tabs:
                self.render_current_gallery_tab()
                self.populated_tabs.add(index)

    def render_current_gallery_tab(self):
        idx = self.tabs.currentIndex()
        image_files = getattr(self, "image_files", [])
        video_files = getattr(self, "video_files", [])
        audio_files = getattr(self, "audio_files", [])

        if idx == 0:
            self.populate_tab_grid(self.tab_images, image_files)
        elif idx == 1:
            self.populate_tab_grid(self.tab_videos, video_files)
        elif idx == 2:
            self.populate_tab_grid(self.tab_audios, audio_files)

    def scan_media_files(self):
        img_dir = self.config.get("images_folder")
        vid_dir = self.config.get("videos_folder")
        aud_dir = self.config.get("audios_folder")

        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(vid_dir, exist_ok=True)
        os.makedirs(aud_dir, exist_ok=True)

        self.image_files = [
            os.path.join(img_dir, f) for f in os.listdir(img_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ] if os.path.exists(img_dir) else []

        self.video_files = [
            os.path.join(vid_dir, f) for f in os.listdir(vid_dir)
            if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))
        ] if os.path.exists(vid_dir) else []

        self.audio_files = [
            os.path.join(aud_dir, f) for f in os.listdir(aud_dir)
            if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))
        ] if os.path.exists(aud_dir) else []

        self.image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        self.video_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        self.audio_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        self.all_files = sorted(self.image_files + self.video_files + self.audio_files, key=lambda x: os.path.getmtime(x), reverse=True)

        if hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(f"Jade Medios — Imágenes: {len(self.image_files)} | Videos: {len(self.video_files)} | Audios: {len(self.audio_files)}")

    def load_gallery(self):
        self.scan_media_files()
        if hasattr(self, "populated_tabs"):
            self.populated_tabs.clear()
        self.render_current_gallery_tab()
        if hasattr(self, "populated_tabs"):
            self.populated_tabs.add(self.tabs.currentIndex())

    def toggle_record(self):
        if not self.is_recording:
            ffmpeg_bin = get_ffmpeg_path()
            if not ffmpeg_bin:
                reply = QMessageBox.question(
                    self,
                    "Instalar Componente de Grabación",
                    "Para activar la grabación de pantalla por GPU en Jade se requiere configurar FFmpeg.\n\n"
                    "¿Deseas que Jade lo instale automáticamente ahora?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.install_ffmpeg_and_record()
                return

            self.was_visible_before_capture = self.isVisible() and not self.isMinimized()
            if self.config.get("hide_on_capture"):
                self.hide()
            QTimer.singleShot(180, self._show_recording_area_selection)
        else:
            if self.recorder_thread:
                self.floating_bar.stop_timer()
                self.recorder_thread.stop_recording()

    def toggle_pause(self):
        if self.is_recording and self.recorder_thread:
            self.floating_bar.toggle_pause()
        elif self.is_recording_audio and self.audio_recorder_thread:
            self.floating_bar.toggle_pause()

    def pause_recording(self):
        if self.is_recording and self.recorder_thread:
            self.recorder_thread.pause_recording()
            self.status_label.setText("⏸️ Grabación Pausada")
        elif self.is_recording_audio and self.audio_recorder_thread:
            self.audio_recorder_thread.pause_recording()
            self.status_label.setText("⏸️ Grabación de Audio Pausada")

    def resume_recording(self):
        if self.is_recording and self.recorder_thread:
            self.recorder_thread.resume_recording()
            self.status_label.setText("📹 Grabando activamente a 60 FPS con Jade")
        elif self.is_recording_audio and self.audio_recorder_thread:
            self.audio_recorder_thread.resume_recording()
            self.status_label.setText("🎙️ Grabando Audio MP3 HQ con Jade")

    def toggle_record_audio(self):
        if not self.is_recording_audio:
            if self.is_recording:
                QMessageBox.warning(self, "Jade", "Ya hay una grabación de video en curso.")
                return

            ffmpeg_bin = get_ffmpeg_path()
            if not ffmpeg_bin:
                QMessageBox.warning(self, "Jade", "Se requiere FFmpeg para codificar audios MP3.")
                return

            save_dir = self.config.get("audios_folder")
            os.makedirs(save_dir, exist_ok=True)

            filename = f"Audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            filepath = os.path.join(save_dir, filename)

            self.audio_recorder_thread = AudioOnlyRecorder(
                output_filepath=filepath,
                parent=self
            )
            self.audio_recorder_thread.recording_started.connect(self.on_audio_recording_started)
            self.audio_recorder_thread.recording_finished.connect(self.on_audio_recording_finished)
            self.audio_recorder_thread.error_occurred.connect(self.on_audio_recording_error)

            self.audio_recorder_thread.start()

            self.countdown_overlay = CountdownOverlay()
            self.countdown_overlay.finished.connect(self.audio_recorder_thread.trigger_go)
            self.countdown_overlay.start()
        else:
            if self.audio_recorder_thread:
                self.floating_bar.stop_timer()
                self.audio_recorder_thread.stop_recording()

    def on_audio_recording_started(self):
        self.is_recording_audio = True
        self.floating_bar.start_timer()
        self.status_label.setText("🎙️ Grabando solo Audio MP3 en Alta Calidad con Jade")

    def on_audio_recording_finished(self, filepath: str):
        self.is_recording_audio = False
        self.floating_bar.stop_timer()

        self.tray_icon.showMessage(
            "Jade - Audio Guardado",
            f"Grabación de audio guardada en {filepath}",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

        QTimer.singleShot(250, self.load_gallery)

    def on_audio_recording_error(self, err_msg: str):
        self.is_recording_audio = False
        self.floating_bar.stop_timer()
        self.tray_icon.showMessage("Jade - Audio Error", err_msg, QSystemTrayIcon.MessageIcon.Warning, 4000)

    def _show_recording_area_selection(self):
        try:
            full_desktop = capture_full_desktop()
            self.area_overlay = AreaSelectionOverlay(full_desktop)
            self.area_overlay.area_selected.connect(self._start_recording_with_area)
            self.area_overlay.canceled.connect(self._restore_visibility_if_needed)
            self.area_overlay.show()
        except Exception as e:
            log_message(f"Error al abrir selector de área: {e}")
            self._restore_visibility_if_needed()

    def _restore_visibility_if_needed(self):
        self.is_capturing_active = False

    def _start_recording_with_area(self, rect: QRect):
        if self.config.get("hide_on_capture"):
            self.hide()

        save_dir = self.config.get("videos_folder")
        os.makedirs(save_dir, exist_ok=True)

        filename = f"Grabacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        filepath = os.path.join(save_dir, filename)

        # Determinar FPS dinámicos para capturar duplicación/triplicación de cuadros (LSFG / AFMF / DLSS 3 / SVP)
        configured_fps = self.config.get("fps")
        target_fps = 60
        if configured_fps in ("auto", "0", 0, None):
            detected_hz = 0
            try:
                class DEVMODEW(ctypes.Structure):
                    _fields_ = [
                        ('dmDeviceName', ctypes.c_wchar * 32),
                        ('dmSpecVersion', ctypes.c_ushort),
                        ('dmDriverVersion', ctypes.c_ushort),
                        ('dmSize', ctypes.c_ushort),
                        ('dmDriverExtra', ctypes.c_ushort),
                        ('dmFields', ctypes.c_uint),
                        ('dmOrientation', ctypes.c_short),
                        ('dmPaperSize', ctypes.c_short),
                        ('dmPaperLength', ctypes.c_short),
                        ('dmPaperWidth', ctypes.c_short),
                        ('dmScale', ctypes.c_short),
                        ('dmCopies', ctypes.c_short),
                        ('dmDefaultSource', ctypes.c_short),
                        ('dmPrintQuality', ctypes.c_short),
                        ('dmColor', ctypes.c_short),
                        ('dmDuplex', ctypes.c_short),
                        ('dmYResolution', ctypes.c_short),
                        ('dmTTOption', ctypes.c_short),
                        ('dmCollate', ctypes.c_short),
                        ('dmFormName', ctypes.c_wchar * 32),
                        ('dmLogPixels', ctypes.c_ushort),
                        ('dmBitsPerPel', ctypes.c_ulong),
                        ('dmPelsWidth', ctypes.c_ulong),
                        ('dmPelsHeight', ctypes.c_ulong),
                        ('dmDisplayFlags', ctypes.c_ulong),
                        ('dmDisplayFrequency', ctypes.c_ulong),
                        ('dmICMMethod', ctypes.c_ulong),
                        ('dmICMIntent', ctypes.c_ulong),
                        ('dmMediaType', ctypes.c_ulong),
                        ('dmDitherType', ctypes.c_ulong),
                        ('dmReserved1', ctypes.c_ulong),
                        ('dmReserved2', ctypes.c_ulong),
                        ('dmPanningWidth', ctypes.c_ulong),
                        ('dmPanningHeight', ctypes.c_ulong)
                    ]
                devmode = DEVMODEW()
                devmode.dmSize = ctypes.sizeof(DEVMODEW)
                ENUM_CURRENT_SETTINGS = -1
                if ctypes.windll.user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode)):
                    detected_hz = int(devmode.dmDisplayFrequency)
            except Exception:
                pass

            if detected_hz > 0:
                target_fps = detected_hz
            else:
                screen = QApplication.primaryScreen()
                if screen and screen.refreshRate() > 0:
                    target_fps = int(round(screen.refreshRate()))
                else:
                    target_fps = 60
        else:
            try:
                target_fps = int(configured_fps)
            except Exception:
                target_fps = 60

        target_fps = max(30, min(360, target_fps))

        self.recorder_thread = ScreenRecorder(
            output_filepath=filepath,
            fps=target_fps,
            use_nvenc=self.config.get("use_nvenc"),
            record_system=self.config.get("record_system_audio"),
            record_mic=self.config.get("record_mic_audio"),
            rect=rect,
            hdr_fix=self.config.get("hdr_fix"),
            parent=self
        )
        self.recorder_thread.recording_started.connect(self.on_recording_started)
        self.recorder_thread.recording_finished.connect(self.on_recording_finished)
        self.recorder_thread.error_occurred.connect(self.on_recording_error)

        self.recorder_thread.start()

        self.countdown_overlay = CountdownOverlay()
        self.countdown_overlay.finished.connect(self.recorder_thread.trigger_go)
        self.countdown_overlay.start()

    def install_ffmpeg_and_record(self):
        self.progress_dialog = QProgressDialog("Configurando el motor de video para Jade...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Configurando GPU")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.installer_thread = FFmpegInstallerThread(self)
        self.installer_thread.status_updated.connect(self.progress_dialog.setLabelText)
        self.installer_thread.finished.connect(self.on_ffmpeg_installed)
        self.installer_thread.start()

    def on_ffmpeg_installed(self, success: bool, message: str):
        self.progress_dialog.close()
        if success:
            QMessageBox.information(self, "Jade", message)
            self.toggle_record()
        else:
            QMessageBox.warning(self, "Jade", message)

    def on_recording_started(self):
        self.is_recording = True
        self.floating_bar.start_timer()
        self.status_label.setText("📹 Grabando activamente a 60 FPS con Jade")

    def register_jade_protocol(self):
        try:
            if getattr(sys, "frozen", False):
                cmd_play = f'"{sys.executable}" --play "%1"'
                cmd_copy = f'"{sys.executable}" --copy-file "%1"'
                cmd_trans = f'"{sys.executable}" --translate "%1"'
                cmd_clip = f'"{sys.executable}" --translate-clip'
            else:
                py_exe = sys.executable
                main_py = os.path.abspath(sys.argv[0])
                cmd_play = f'"{py_exe}" "{main_py}" --play "%1"'
                cmd_copy = f'"{py_exe}" "{main_py}" --copy-file "%1"'
                cmd_trans = f'"{py_exe}" "{main_py}" --translate "%1"'
                cmd_clip = f'"{py_exe}" "{main_py}" --translate-clip'

            # 1. Registro Protocolo jade-play
            key_path_play = r"Software\Classes\jade-play"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_play) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL: Jade Play Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_play + r"\shell\open\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd_play)

            # 2. Registro Protocolo jade-copy
            key_path_copy = r"Software\Classes\jade-copy"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_copy) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL: Jade Copy Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_copy + r"\shell\open\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd_copy)

            # 3. Registro Protocolo jade-translate
            key_path_trans = r"Software\Classes\jade-translate"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_trans) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL: Jade Translate Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_trans + r"\shell\open\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd_trans)

            # 4. Registro Automático de Clic Derecho Contextual en Windows y Navegadores ("🌐 Traducir con Jade")
            shell_keys = [
                r"Software\Classes\*\shell\JadeTranslate",
                r"Software\Classes\Directory\shell\JadeTranslate",
                r"Software\Classes\Directory\Background\shell\JadeTranslate"
            ]
            for skey in shell_keys:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, skey) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "🌐 Traducir con Jade")
                    winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, sys.executable)
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, skey + r"\command") as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd_clip)

        except Exception as e:
            log_message(f"Error registrando menú contextual e integración nativa: {e}")

    def ensure_video_thumbnail(self, video_path: str) -> str:
        try:
            import hashlib
            cache_dir = os.path.join(get_jade_appdata_dir(), "cache", "thumbs_hd")
            os.makedirs(cache_dir, exist_ok=True)
            media_hash = hashlib.md5(video_path.encode("utf-8")).hexdigest()
            thumb_path = os.path.join(cache_dir, f"{media_hash}.jpg")

            if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    _RAM_THUMB_CACHE[video_path] = pix
                return thumb_path

            ffmpeg_bin = get_ffmpeg_path()
            if ffmpeg_bin and os.path.exists(ffmpeg_bin):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                cmd = [
                    ffmpeg_bin, "-threads", "1", "-ss", "00:00:00.000", "-i", video_path,
                    "-vf", "scale=640:-1", "-vframes", "1", "-q:v", "3", thumb_path, "-y"
                ]
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    creationflags=0x08000000,
                    timeout=4
                )
                if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                    pix = QPixmap(thumb_path)
                    if not pix.isNull():
                        _RAM_THUMB_CACHE[video_path] = pix
                    return thumb_path
        except Exception as e:
            log_message(f"Error generando miniatura para notificación: {e}")
        return ""

    def show_native_video_toast(self, filepath: str):
        try:
            abs_video_path = os.path.abspath(filepath).replace("\\", "/")
            video_dir = os.path.dirname(abs_video_path).replace("\\", "/")
            video_name = os.path.basename(filepath)
            thumb_file = self.ensure_video_thumbnail(filepath)
            thumb_xml = ""
            if thumb_file and os.path.exists(thumb_file):
                abs_thumb_path = os.path.abspath(thumb_file).replace("\\", "/")
                thumb_xml = f'<image placement="inline" src="file:///{abs_thumb_path}"/>'

            ps_script = f'''
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

$xml = @"
<toast duration="short">
    <visual>
        <binding template="ToastGeneric">
            <text>Jade — Video Guardado</text>
            <text>{video_name}</text>
            {thumb_xml}
        </binding>
    </visual>
    <actions>
        <action content="Reproducir en Jade" activationType="protocol" arguments="jade-play:///{abs_video_path}"/>
        <action content="Copiar Video" activationType="protocol" arguments="jade-copy:///{abs_video_path}"/>
        <action content="Abrir Carpeta" activationType="protocol" arguments="file:///{video_dir}"/>
    </actions>
</toast>
"@

try {{
    $xmlDoc = [Windows.Data.Xml.Dom.XmlDocument]::new()
    $xmlDoc.LoadXml($xml)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xmlDoc)
    $appId = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
}} catch {{}}
[Environment]::Exit(0)
'''
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                startupinfo=startupinfo,
                creationflags=0x08000000
            )
        except Exception as e:
            log_message(f"Error mostrando notificación nativa con miniatura: {e}")

    def on_recording_finished(self, filepath: str):
        self.is_recording = False
        self.floating_bar.stop_timer()

        if hasattr(self, "video_draw_overlay") and self.video_draw_overlay:
            self.video_draw_overlay.clear_annotations()
            self.video_draw_overlay.hide()
            self.video_draw_overlay.close()
            self.video_draw_overlay.deleteLater()
            self.video_draw_overlay = None

        self.show_native_video_toast(filepath)
        QTimer.singleShot(250, self.load_gallery)

    def show_native_recording_error_toast(self, err_msg: str):
        try:
            clean_msg = err_msg.replace('"', "'").replace("\n", " ").strip()
            display_msg = clean_msg[:220] + ("..." if len(clean_msg) > 220 else "")

            ps_script = f'''
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

$xml = @"
<toast duration="long">
    <visual>
        <binding template="ToastGeneric">
            <text>⚠️ Grabación Interrumpida (Jade)</text>
            <text>{display_msg}</text>
        </binding>
    </visual>
</toast>
"@

try {{
    $xmlDoc = [Windows.Data.Xml.Dom.XmlDocument]::new()
    $xmlDoc.LoadXml($xml)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xmlDoc)
    $appId = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
}} catch {{}}
'''
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                startupinfo=startupinfo,
                creationflags=0x08000000
            )
        except Exception as e:
            log_message(f"Error mostrando notificación nativa de error de grabación: {e}")

    def on_recording_error(self, err_msg: str):
        self.is_recording = False
        self.floating_bar.stop_timer()
        self.tray_icon.showMessage("Jade - Grabación Interrumpida", err_msg, QSystemTrayIcon.MessageIcon.Warning, 5000)
        self.show_native_recording_error_toast(err_msg)

    def quit_application(self):
        self.really_quit = True
        QApplication.instance().quit()

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = get_resource_path(".py/resources/icon.ico")

        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = get_minimalist_svg_icon("sparkle", "#107C41", 32)

        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Jade — Capturas, OCR & Grabaciones")

        tray_menu = QMenu()
        tray_menu.setStyleSheet(ThemePalette.get_menu_style(self.is_dark))
        self.tray_menu = tray_menu
        action_show = tray_menu.addAction("Ver Galería de Jade")
        action_show.triggered.connect(self.show_main_window_without_stealing_focus)
        action_cap = tray_menu.addAction("Capturar Pantalla")
        action_cap.triggered.connect(self.trigger_capture)
        action_rec = tray_menu.addAction("Grabar Video")
        action_rec.triggered.connect(self.toggle_record)
        action_rec_aud = tray_menu.addAction("Grabar Solo Audio")
        action_rec_aud.triggered.connect(self.toggle_record_audio)
        tray_menu.addSeparator()
        action_exit = tray_menu.addAction("Salir de Jade")
        action_exit.triggered.connect(self.quit_application)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def show_main_window_without_stealing_focus(self):
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_main_window_without_stealing_focus()

    def toggle_recording_draw_mode(self):
        if not hasattr(self, "video_draw_overlay") or self.video_draw_overlay is None:
            self.video_draw_overlay = VideoAnnotationOverlay()

        if self.video_draw_overlay.isVisible() and not self.video_draw_overlay.click_through:
            self.video_draw_overlay.set_click_through_mode(True)
        else:
            self.video_draw_overlay.set_click_through_mode(False)
            self.video_draw_overlay.show()
            self.video_draw_overlay.raise_()

    def clear_recording_annotations(self):
        if hasattr(self, "video_draw_overlay") and self.video_draw_overlay:
            self.video_draw_overlay.clear_annotations()

    def on_toggle_hotkeys_triggered(self):
        if hasattr(self, "hotkey_thread") and self.hotkey_thread:
            self.hotkey_thread.hotkeys_muted = not self.hotkey_thread.hotkeys_muted
            self.hotkey_thread.toggle_hotkeys_triggered.emit(not self.hotkey_thread.hotkeys_muted)

    def on_hotkeys_toggled(self, enabled: bool):
        if enabled:
            msg = "Los atajos globales de Jade han sido ACTIVADOS."
            log_message(msg)
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.showMessage("Jade - Atajos Activos", msg, QSystemTrayIcon.MessageIcon.Information, 2500)
        else:
            msg = "Jade ha SILENCIADO sus atajos globales para no interferir con otras aplicaciones."
            log_message(msg)
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.showMessage("Jade - Atajos Silenciados", msg, QSystemTrayIcon.MessageIcon.Warning, 2500)

    def open_quick_translator_window(self):
        if not hasattr(self, "_quick_translator_win") or self._quick_translator_win is None:
            self._quick_translator_win = QuickTranslatorWindow(from_lang="es", to_lang="en", parent=None)
            self._quick_translator_win.finished.connect(self._clear_quick_translator_ref)
        self._quick_translator_win.show()
        self._quick_translator_win.raise_()
        self._quick_translator_win.activateWindow()

    def _clear_quick_translator_ref(self):
        self._quick_translator_win = None

    def open_quick_notes_window(self):
        if not hasattr(self, "_quick_notes_win") or self._quick_notes_win is None:
            self._quick_notes_win = QuickNotesWindow(self.history_manager, self)
            self._quick_notes_win.finished.connect(self._clear_quick_notes_ref)
        self._quick_notes_win.show()
        self._quick_notes_win.raise_()
        self._quick_notes_win.activateWindow()

    def _clear_quick_notes_ref(self):
        self._quick_notes_win = None

    def open_standalone_gallery_window(self):
        if not hasattr(self, "_standalone_gallery_win") or self._standalone_gallery_win is None:
            self._standalone_gallery_win = StandaloneGalleryWindow(self.config, self)
            self._standalone_gallery_win.finished.connect(self._clear_standalone_gallery_ref)
        self._standalone_gallery_win.show()
        self._standalone_gallery_win.raise_()
        self._standalone_gallery_win.activateWindow()

   
    def open_galeria_app(self, folder_path: str = None, file_path: str = None):
        try:
            import galeria

            if not hasattr(self, "_galeria_win") or self._galeria_win is None:
                gal_cls = getattr(galeria, 'JadePhotosGalleryWindow', None)
                self._galeria_win = gal_cls(self.config, initial_folder=folder_path, initial_file=file_path, parent=None)
                ThemeManager.get_instance().register_child(self._galeria_win)
                self._galeria_win.destroyed.connect(self._clear_galeria_ref)
            else:
                if file_path and hasattr(self._galeria_win, "open_media_viewer"):
                    self._galeria_win.open_media_viewer(file_path)
                elif folder_path and hasattr(self._galeria_win, "filter_and_switch_to_folder"):
                    self._galeria_win.filter_and_switch_to_folder(folder_path)

            if self._galeria_win.isMinimized():
                self._galeria_win.setWindowState(self._galeria_win.windowState() & ~Qt.WindowState.WindowMinimized)
            self._galeria_win.show()
            self._galeria_win.raise_()
            self._galeria_win.activateWindow()
        except Exception as e:
            import traceback
            err_trace = traceback.format_exc()
            log_message(f"Error abriendo Galería Pro: {err_trace}")
            QMessageBox.warning(self, "Galería Jade", f"No se pudo abrir la Galería:\n{e}")

    def process_command_args(self, args: list):
        if not args or args == ["--minimized"]:
            return

        # 1. Manejo del protocolo de reproducción (Notificaciones nativas Toast)
        if "--play" in args:
            try:
                play_idx = args.index("--play")
                if play_idx + 1 < len(args):
                    raw_url = args[play_idx + 1]
                    import urllib.parse
                    clean_path = urllib.parse.unquote(raw_url)
                    for prefix in ["jade-play:///", "jade-play://", "jade-play:", "file:///"]:
                        if clean_path.startswith(prefix):
                            clean_path = clean_path[len(prefix):]
                    clean_path = re.sub(r'^[/\\]+([A-Za-z]:)', r'\1', clean_path)
                    clean_path = os.path.normpath(clean_path)
                    if os.path.exists(clean_path):
                        self.show_hd_preview(clean_path)
                        return
            except Exception as e:
                log_message(f"Error procesando protocolo IPC --play: {e}")

        # 2. Manejo del protocolo de copiado desde notificación
        if "--copy-file" in args:
            try:
                c_idx = args.index("--copy-file")
                if c_idx + 1 < len(args):
                    raw_url = args[c_idx + 1]
                    import urllib.parse
                    clean_path = urllib.parse.unquote(raw_url)
                    for prefix in ["jade-copy:///", "jade-copy://", "jade-copy:", "file:///"]:
                        if clean_path.startswith(prefix):
                            clean_path = clean_path[len(prefix):]
                    clean_path = re.sub(r'^[/\\]+([A-Za-z]:)', r'\1', clean_path)
                    clean_path = os.path.normpath(clean_path)
                    if os.path.exists(clean_path):
                        from PyQt6.QtCore import QMimeData, QUrl
                        cb = QApplication.clipboard()
                        mime_data = QMimeData()
                        mime_data.setUrls([QUrl.fromLocalFile(os.path.abspath(clean_path))])
                        cb.setMimeData(mime_data)
                        return
            except Exception as e:
                log_message(f"Error procesando protocolo IPC --copy-file: {e}")

        # 3. Apertura directa de archivos multimedia al hacer doble clic en el explorador de Windows
        MEDIA_EXTENSIONS = (
            '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif', '.ico', '.tiff', '.tif', '.jfif', '.heic', '.heif', '.avif', '.svg',
            '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ts', '.mts', '.m2ts', '.vob', '.ogv', '.asf', '.f4v', '.mpg', '.mpeg', '.mpv'
        )

        for arg in args:
            if not arg.startswith("-") and os.path.exists(arg) and os.path.isfile(arg):
                clean_path = os.path.abspath(arg)
                if clean_path.lower().endswith(MEDIA_EXTENSIONS):
                    self.show_hd_preview(clean_path)
                    return

        # 4. Parámetros de Galería
        if "--gallery" in args or "--fotos" in args:
            target_dir = None
            for flag in ["--gallery", "--fotos"]:
                if flag in args:
                    f_idx = args.index(flag)
                    if f_idx + 1 < len(args) and not args[f_idx + 1].startswith("-"):
                        target_dir = args[f_idx + 1]
                    break
            self.open_galeria_app(folder_path=target_dir)
            return

        # 5. Parámetros de Traducción directa
        if "--translate-clip" in args or "jade-translate:" in args or "--translate" in args:
            self.trigger_translate_selected_text()
            return

        self.show_main_window_without_stealing_focus()

    def _clear_galeria_ref(self):
        self._galeria_win = None

    def _clear_standalone_gallery_ref(self):
        self._standalone_gallery_win = None

    def _hide_all_jade_windows(self):
        self._hidden_dialogs = []
        if not self.config.get("hide_on_capture"):
            return
        for widget in QApplication.topLevelWidgets():
            if widget.isVisible() and not widget.isMinimized():
                if widget.__class__.__name__ in ("GameTranslationOverlay", "VideoAnnotationOverlay", "VideoAnnotationHUD"):
                    continue
                widget.hide()
                self._hidden_dialogs.append(widget)

    def _restore_all_jade_windows(self):
        if hasattr(self, "_hidden_dialogs") and self._hidden_dialogs:
            for widget in self._hidden_dialogs:
                if widget != self:
                    try:
                        widget.show()
                    except Exception:
                        pass
            self._hidden_dialogs = []

    def trigger_capture(self):
        if getattr(self, "is_capturing_active", False):
            return
        self.is_capturing_active = True

        if hasattr(self, "overlay") and self.overlay:
            try:
                self.overlay.blockSignals(True)
                self.overlay.hide()
                self.overlay.close()
                self.overlay.deleteLater()
            except Exception:
                pass
            self.overlay = None

        self._hide_all_jade_windows()
        QTimer.singleShot(10, self._perform_capture)

    def _perform_capture(self):
        try:
            full_desktop = capture_full_desktop()
            self.overlay = SnippingOverlay(full_desktop)
            self.overlay.area_captured.connect(self.process_captured_area)
            self.overlay.canceled.connect(self._restore_visibility_if_needed)
            self.overlay.show()
        except Exception as e:
            log_message(f"Error al realizar captura: {e}")
            self._restore_visibility_if_needed()

    def process_captured_area(self, pixmap: QPixmap, rect: QRect):
        self._restore_all_jade_windows()
        self.is_capturing_active = False

        if pixmap is None or pixmap.isNull():
            return

        if self.config.get("auto_copy_clipboard"):
            cb = QApplication.clipboard()
            cb.blockSignals(True)
            cb.setPixmap(pixmap)
            cb.blockSignals(False)

        save_dir = self.config.get("images_folder")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"Captura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(save_dir, filename)

        try:
            import jade_editor
            if not hasattr(self, "_active_cards"):
                self._active_cards = []

            card = jade_editor.ScreenshotFloatingCard(filepath=filepath, pixmap=pixmap, parent=None)
            ThemeManager.get_instance().register_child(card)
            self.current_floating_card = card
            self._active_cards.append(card)

            def _cleanup(obj=None, ref=card):
                if hasattr(self, "_active_cards") and ref in self._active_cards:
                    self._active_cards.remove(ref)

            card.destroyed.connect(_cleanup)
            card.position_card()
            card.show()
            card.raise_()
            card.activateWindow()
        except Exception as e:
            log_message(f"Error mostrando tarjeta flotante instantánea: {e}")

        self.save_worker = SaveCaptureWorker(pixmap, save_dir, self)
        self.save_worker.finished.connect(self._on_capture_saved)
        self.save_worker.start()

    def trigger_translate_selected_text(self, direct_text_input: str = None):
        """Captura el texto seleccionado en cualquier programa (Word, Navegador, etc.) y lo traduce al instante en la tarjeta flotante descartando URLs accidentales."""
        import time

        if direct_text_input:
            clean_check = direct_text_input.strip().strip("/").lower()
            if clean_check in ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh"] or clean_check.startswith("--"):
                direct_text_input = None

        selected_text = direct_text_input

        if not selected_text:
            cb = QApplication.clipboard()
            cb.clear()

            user32 = ctypes.windll.user32
            user32.keybd_event(0x11, 0, 0, 0)      # Ctrl Down
            user32.keybd_event(0x43, 0, 0, 0)      # C Down
            time.sleep(0.06)
            user32.keybd_event(0x43, 0, 0x0002, 0) # C Up
            user32.keybd_event(0x11, 0, 0x0002, 0) # Ctrl Up
            time.sleep(0.08)

            selected_text = cb.text()

        # Descartar enlaces o URLs generadas por el navegador al presionar Ctrl+C
        is_url = False
        if selected_text and selected_text.strip():
            s_clean = selected_text.strip().lower()
            if s_clean.startswith(("http://", "https://", "www.", "chrome://", "edge://", "file://", "about:")) or (len(s_clean.split()) == 1 and ("/" in s_clean or "." in s_clean)):
                is_url = True

        if selected_text and selected_text.strip() and not is_url:
            from_lang = self.config.get("translate_from_lang") or "en"
            to_lang = self.config.get("translate_to_lang") or "es"

            mouse_pos = QCursor.pos()
            self.translation_card = TranslationFloatingCard(mouse_pos, from_lang, to_lang)
            self.translation_card.show()

            self.trans_worker = ArgosTranslatorWorker(direct_text=selected_text, from_code=from_lang, to_code=to_lang)
            self.trans_worker.status_updated.connect(self.translation_card.update_status)

            def _on_success(orig, trans):
                self.translation_card.set_result(orig, trans)
                self.on_translation_finished(orig, trans)

            def _on_fail(err):
                self.translation_card.set_error(err)
                self.on_translation_error(err)

            self.trans_worker.finished.connect(_on_success)
            self.trans_worker.error.connect(_on_fail)
            self.trans_worker.start()
        else:
            self.trigger_translate_area()

    def trigger_translate_area(self):
        if getattr(self, "is_capturing_active", False):
            return
        self.is_capturing_active = True

        self._hide_all_jade_windows()
        QApplication.processEvents()
        QTimer.singleShot(60, self._perform_translate_capture)

    def _perform_translate_capture(self):
        try:
            full_desktop = capture_full_desktop()
            self.overlay = SnippingOverlay(full_desktop)
            self.overlay.area_captured.connect(self.process_translate_area)
            self.overlay.canceled.connect(self._restore_visibility_if_needed)
            self.overlay.show()
        except Exception as e:
            log_message(f"Error al realizar captura para traducción: {e}")
            self._restore_visibility_if_needed()

    def process_translate_area(self, pixmap: QPixmap, rect: QRect):
        self._restore_all_jade_windows()
        self.is_capturing_active = False

        if pixmap is None or pixmap.isNull():
            return

        from_lang = self.config.get("translate_from_lang") or "en"
        to_lang = self.config.get("translate_to_lang") or "es"

        mouse_pos = QCursor.pos()
        self.translation_card = TranslationFloatingCard(mouse_pos, from_lang, to_lang)
        self.translation_card.show()

        self.trans_worker = ArgosTranslatorWorker(pixmap=pixmap, direct_text=None, from_code=from_lang, to_code=to_lang, parent=self)
        self.trans_worker.status_updated.connect(self.translation_card.update_status)

        def _on_success(orig, trans):
            self.translation_card.set_result(orig, trans)
            self.on_translation_finished(orig, trans)
            if hasattr(self, "trans_worker") and self.trans_worker:
                self.trans_worker.deleteLater()
                self.trans_worker = None
            import gc; gc.collect()

        def _on_fail(err):
            self.translation_card.set_error(err)
            self.on_translation_error(err)
            if hasattr(self, "trans_worker") and self.trans_worker:
                self.trans_worker.deleteLater()
                self.trans_worker = None
            import gc; gc.collect()

        self.trans_worker.finished.connect(_on_success)
        self.trans_worker.error.connect(_on_fail)
        self.trans_worker.start()

    def on_translation_finished(self, original_text: str, translated_text: str):
        from_lang = self.config.get("translate_from_lang") or "en"
        to_lang = self.config.get("translate_to_lang") or "es"

        entry_note = f"🌐 Traducción Argos ({from_lang} ➔ {to_lang})\nTexto Original: {original_text[:80]}..."
        self.history_manager.add_entry(translated_text, entry_note)

        cb = QApplication.clipboard()
        cb.blockSignals(True)
        cb.setText(translated_text)
        cb.blockSignals(False)

        if hasattr(self, "tab_text_history"):
            self.tab_text_history.refresh_list()

        self.show_native_translation_toast(translated_text, from_lang, to_lang)

    def on_translation_error(self, err_msg: str):
        self.show_native_ocr_toast(f"Error en traducción: {err_msg}")

    def show_native_translation_toast(self, text_content: str, from_l: str, to_l: str):
        try:
            clean_text = text_content.replace('"', "'").replace("\n", " ").strip()
            display_text = clean_text[:220] + ("..." if len(clean_text) > 220 else "")

            ps_script = f'''
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

$xml = @"
<toast duration="short">
    <visual>
        <binding template="ToastGeneric">
            <text>Jade — Traducción Lista ({from_l} ➔ {to_l})</text>
            <text>{display_text}</text>
        </binding>
    </visual>
</toast>
"@

try {{
    $xmlDoc = [Windows.Data.Xml.Dom.XmlDocument]::new()
    $xmlDoc.LoadXml($xml)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xmlDoc)
    $appId = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
}} catch {{}}
'''
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                startupinfo=startupinfo,
                creationflags=0x08000000
            )
        except Exception as e:
            log_message(f"Error mostrando notificación nativa de traducción: {e}")

    def _on_capture_saved(self, filepath: str):
        self.is_capturing_active = False
        if filepath and os.path.exists(filepath):
            if hasattr(self, "current_floating_card") and self.current_floating_card:
                self.current_floating_card.filepath = filepath

            if self.config.get("auto_copy_clipboard"):
                abs_path = os.path.abspath(filepath)
                img = QImage(abs_path)
                if not img.isNull():
                    cb = QApplication.clipboard()
                    cb.blockSignals(True)
                    cb.setImage(img)
                    cb.blockSignals(False)

            QTimer.singleShot(0, self.load_gallery)

    def load_more_days(self):
        if not hasattr(self, "days_to_show"):
            self.days_to_show = 1
        self.days_to_show += 1
        curr_tab = self.tabs.currentWidget()
        old_scroll = 0
        if hasattr(curr_tab, "scroll_area") and curr_tab.scroll_area:
            old_scroll = curr_tab.scroll_area.verticalScrollBar().value()
        self.render_current_gallery_tab()
        if hasattr(curr_tab, "scroll_area") and curr_tab.scroll_area:
            curr_tab.scroll_area.verticalScrollBar().setValue(old_scroll)

    def show_hd_preview(self, filepath: str):
        current_list = getattr(self, "current_visible_file_list", [filepath])
        if filepath in current_list:
            curr_idx = current_list.index(filepath)
        else:
            curr_idx = 0
            current_list = [filepath]

        dialog = HDMediaViewerDialog(filepath, parent=self, file_list=current_list, current_index=curr_idx)
        dialog.ocr_requested.connect(self.perform_ocr)
        dialog.exec()

    def rename_item(self, filepath: str):
        if not os.path.exists(filepath):
            return

        dir_name, old_filename = os.path.split(filepath)
        name, ext = os.path.splitext(old_filename)

        new_name, ok = QInputDialog.getText(
            self,
            "Renombrar Archivo",
            "Nuevo nombre para el archivo:",
            QLineEdit.EchoMode.Normal,
            name
        )

        if ok and new_name.strip():
            new_filename = new_name.strip() + ext
            new_filepath = os.path.join(dir_name, new_filename)

            if new_filepath == filepath:
                return

            if os.path.exists(new_filepath):
                QMessageBox.warning(self, "Jade", "Ya existe un archivo con ese nombre.")
                return

            try:
                os.rename(filepath, new_filepath)
                self.load_gallery()
            except Exception as e:
                QMessageBox.warning(self, "Jade", f"No se pudo renombrar el archivo: {e}")

    def populate_tab_grid(self, tab_widget: QWidget, file_list: list):
        list_layout = tab_widget.grid_layout

        def _clear_recursive(layout):
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
                elif child.layout():
                    _clear_recursive(child.layout())

        _clear_recursive(list_layout)

        if not file_list:
            empty_lbl = QLabel("No hay elementos para mostrar en esta sección.")
            empty_lbl.setStyleSheet("color: #777777; font-size: 13px; padding: 30px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            list_layout.addWidget(empty_lbl)
            if hasattr(tab_widget, "btn_floating_more") and tab_widget.btn_floating_more:
                tab_widget.btn_floating_more.hide()
            return

        if not hasattr(self, "days_to_show"):
            self.days_to_show = 1

        today_date = datetime.now().date()
        yesterday_date = today_date - timedelta(days=1)

        grouped = {}
        for filepath in file_list:
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                fdate = mtime.date()
                days_diff = (today_date - fdate).days

                if fdate == today_date:
                    group_title = "HOY"
                elif fdate == yesterday_date:
                    group_title = "AYER"
                elif days_diff <= 30:
                    group_title = f"{mtime.strftime('%d/%m/%Y')}"
                else:
                    group_title = f"{mtime.strftime('%B %Y').capitalize()}"
            except Exception:
                group_title = "OTROS MEDIOS"

            grouped.setdefault(group_title, []).append(filepath)

        all_group_keys = list(grouped.keys())
        visible_group_keys = all_group_keys[:self.days_to_show]

        visible_files = []
        for g_key in visible_group_keys:
            visible_files.extend(grouped[g_key][:100])
        self.current_visible_file_list = visible_files

        is_mosaic = getattr(self, "view_mode", "detail") == "mosaic"

        for group_title in visible_group_keys:
            group_files = grouped[group_title][:100]
            section_header = QLabel(group_title.upper())
            section_header.setObjectName("SubTextLabel")
            section_header.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.DemiBold))
            p_head = ThemeManager.get_instance().get_palette()
            section_header.setStyleSheet(f"""
                color: {p_head['text_secondary']};
                background: transparent;
                border: none;
                padding: 10px 4px 4px 4px;
            """)
            list_layout.addWidget(section_header)

            if is_mosaic:
                grid_widget = QWidget()
                grid_widget.setStyleSheet("background-color: transparent;")
                grid_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                grid_layout = QGridLayout(grid_widget)
                grid_layout.setContentsMargins(0, 4, 0, 8)
                grid_layout.setSpacing(10)
                grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

                container_w = max(320, tab_widget.scroll_area.viewport().width() - 20)
                cols = max(2, (container_w + 10) // 190)

                for c in range(cols):
                    grid_layout.setColumnStretch(c, 1)

                for idx_f, filepath in enumerate(group_files):
                    tile = GalleryTileCard(filepath)
                    tile.delete_requested.connect(self.delete_item)
                    tile.ocr_requested.connect(self.perform_ocr)
                    tile.preview_requested.connect(self.show_hd_preview)
                    tile.rename_requested.connect(self.rename_item)
                    tile.copy_requested.connect(self.load_gallery)
                    grid_layout.addWidget(tile, idx_f // cols, idx_f % cols)

                list_layout.addWidget(grid_widget)
            else:
                for filepath in group_files:
                    card = GalleryCard(filepath)
                    card.delete_requested.connect(self.delete_item)
                    card.ocr_requested.connect(self.perform_ocr)
                    card.preview_requested.connect(self.show_hd_preview)
                    card.rename_requested.connect(self.rename_item)
                    list_layout.addWidget(card)

        if hasattr(tab_widget, "btn_floating_more") and tab_widget.btn_floating_more:
            if len(all_group_keys) > self.days_to_show:
                tab_widget.btn_floating_more.show()
                bx = (tab_widget.width() - tab_widget.btn_floating_more.width()) // 2
                by = tab_widget.height() - tab_widget.btn_floating_more.height() - 16
                tab_widget.btn_floating_more.move(max(10, bx), max(10, by))
                tab_widget.btn_floating_more.raise_()
            else:
                tab_widget.btn_floating_more.hide()

    def setup_clipboard_listener(self):
        self.last_clipboard_text = ""
        cb = QApplication.clipboard()
        cb.dataChanged.connect(self.on_system_clipboard_changed)

    def on_system_clipboard_changed(self):
        if not hasattr(self, "history_manager") or getattr(self, "_is_closing", False):
            return

        def _read_clipboard_safe():
            try:
                cb = QApplication.clipboard()
                mime = cb.mimeData()
                if mime and mime.hasText():
                    text = cb.text()
                    if text and text.strip() and text != getattr(self, "last_clipboard_text", ""):
                        self.last_clipboard_text = text
                        self.history_manager.add_entry(text, "Copiado desde Sistema OS")
                        if hasattr(self, "tab_text_history") and self.tab_text_history.isVisible():
                            self.tab_text_history.refresh_list()
            except Exception as e:
                log_message(f"Error monitoreando portapapeles del sistema: {e}")

        QTimer.singleShot(100, _read_clipboard_safe)

    def delete_item(self, filepath: str):
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Estás seguro de que deseas eliminar este elemento?\n\n{os.path.basename(filepath)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(filepath)
                self.load_gallery()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo eliminar el archivo: {e}")

    def perform_ocr(self, pixmap: QPixmap):
        if pixmap is None or pixmap.isNull():
            self.show_native_ocr_toast("No hay una imagen válida para extraer texto.")
            return

        mouse_pos = QCursor.pos()
        self.ocr_card = TranslationFloatingCard(mouse_pos, mode="ocr")
        self.ocr_card.show()

        self.ocr_thread = OCRWorker(pixmap)
        
        def _on_ocr_success(text):
            if text == "REQUIRES_LITE_OCR_INSTALL":
                self.ocr_card.fade_out_and_destroy()
                self.on_ocr_finished(text)
            else:
                self.ocr_card.set_result(text, text)
                self.on_ocr_finished(text)
            if hasattr(self, "ocr_thread") and self.ocr_thread:
                self.ocr_thread.deleteLater()
                self.ocr_thread = None
            import gc; gc.collect()

        def _on_ocr_fail(err):
            self.ocr_card.set_error(err)
            self.on_ocr_error(err)
            if hasattr(self, "ocr_thread") and self.ocr_thread:
                self.ocr_thread.deleteLater()
                self.ocr_thread = None
            import gc; gc.collect()

        self.ocr_thread.finished.connect(_on_ocr_success)
        self.ocr_thread.error.connect(_on_ocr_fail)
        self.ocr_thread.start()

    def on_ocr_error(self, err_msg: str):
        self.show_native_ocr_toast(f"Error en OCR: {err_msg}")

    def show_native_ocr_toast(self, text_content: str):
        try:
            clean_text = text_content.replace('"', "'").replace("\n", " ").strip()
            display_text = clean_text[:220] + ("..." if len(clean_text) > 220 else "")

            ps_script = f'''
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

$xml = @"
<toast duration="short">
    <visual>
        <binding template="ToastGeneric">
            <text>Jade — Texto Extraído (OCR)</text>
            <text>{display_text}</text>
        </binding>
    </visual>
</toast>
"@

try {{
    $xmlDoc = [Windows.Data.Xml.Dom.XmlDocument]::new()
    $xmlDoc.LoadXml($xml)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xmlDoc)
    $appId = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
}} catch {{}}
'''
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                startupinfo=startupinfo,
                creationflags=0x08000000
            )
        except Exception as e:
            log_message(f"Error mostrando notificación nativa de OCR: {e}")

    def on_ocr_finished(self, text: str):
        if text == "REQUIRES_LITE_OCR_INSTALL":
            reply = QMessageBox.question(
                self,
                "Windows Lite Detectado — Motor OCR Requerido",
                "Tu sistema Windows Lite no posee el motor nativo de lectura de texto de Windows.\n\n"
                "¿Deseas que Jade descargue e instale automáticamente el componente portátil de lectura de texto?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.install_ocr_engine_for_lite()
            return

        if text and text.strip() and text not in ("No se reconoció texto en la captura.", "⚠️ No se pudo inicializar el motor de idioma de Windows OCR.", "No se pudo cargar la imagen para OCR."):
            clean_text = text.strip()
            self.history_manager.add_entry(clean_text, "Extraído mediante OCR")

            cb = QApplication.clipboard()
            cb.blockSignals(True)
            cb.setText(clean_text)
            cb.blockSignals(False)

            if hasattr(self, "tab_text_history"):
                self.tab_text_history.refresh_list()

            self.show_native_ocr_toast(clean_text)
        else:
            self.show_native_ocr_toast(text if text else "No se encontró texto reconocible en la imagen.")

    def install_ocr_engine_for_lite(self):
        self.progress_dialog = QProgressDialog("Descargando componentes OCR para Windows Lite...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Configuración OCR")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.ocr_installer = OcrInstallerThread(self)
        self.ocr_installer.status_updated.connect(self.progress_dialog.setLabelText)
        self.ocr_installer.finished.connect(self.on_ocr_installed)
        self.ocr_installer.start()

    def on_ocr_installed(self, success: bool, message: str):
        self.progress_dialog.close()
        if success:
            QMessageBox.information(self, "Jade", "¡El motor OCR portátil ha sido instalado con éxito! Ya puedes extraer texto de cualquier imagen.")
        else:
            QMessageBox.warning(self, "Jade", f"Error al configurar OCR: {message}")

    def on_ocr_error(self, err_msg: str):
        if hasattr(self, "ocr_overlay") and self.ocr_overlay:
            self.ocr_overlay.stop_animation()
            self.ocr_overlay = None
        self.tray_icon.showMessage("Jade - OCR Error", err_msg, QSystemTrayIcon.MessageIcon.Warning, 3000)

    def open_game_translator(self):
        try:
            import juego
            import importlib
            importlib.reload(juego)
            self.game_win = juego.GameTranslatorWindow(self.config, parent=None)
            ThemeManager.get_instance().register_child(self.game_win)
            self.game_win.show()
            self.game_win.raise_()
            self.game_win.activateWindow()
        except Exception as e:
            log_message(f"Error abriendo ventana de modo juego: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error Modo Juego", f"No se pudo abrir la ventana de Modo Juego:\n\n{str(e)}")

    def start_direct_game_translation(self):
        try:
            import juego
            if not hasattr(self, "game_win") or self.game_win is None:
                self.game_win = juego.GameTranslatorWindow(self.config, parent=None)
            ThemeManager.get_instance().register_child(self.game_win)
            if hasattr(self.game_win, "toggle_saved_templates"):
                self.game_win.toggle_saved_templates()
            else:
                self.game_win.launch_saved_templates()
        except Exception as e:
            log_message(f"Error iniciando traducción en vivo directa: {e}")

    def open_settings(self):
        if hasattr(self, "hotkey_thread") and self.hotkey_thread:
            self.hotkey_thread.stop()
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setup_shortcuts()
            self.setup_hotkey()
            self.apply_theme()
            self.load_gallery()
        else:
            self.setup_hotkey()

    def trigger_pin_selected_text(self):
        now_t = time.time()
        if now_t - getattr(self, "_last_pin_timestamp", 0) < 0.75:
            return
        self._last_pin_timestamp = now_t

        cb = QApplication.clipboard()
        cb.clear()

        user32 = ctypes.windll.user32
        user32.keybd_event(0x10, 0, 0x0002, 0)  # VK_SHIFT UP
        user32.keybd_event(0xA0, 0, 0x0002, 0)  # VK_LSHIFT UP
        user32.keybd_event(0xA1, 0, 0x0002, 0)  # VK_RSHIFT UP
        user32.keybd_event(0x12, 0, 0x0002, 0)  # VK_MENU (Alt) UP
        time.sleep(0.03)

        user32.keybd_event(0x11, 0, 0, 0)       # Ctrl DOWN
        user32.keybd_event(0x43, 0, 0, 0)       # 'C' DOWN
        time.sleep(0.05)
        user32.keybd_event(0x43, 0, 0x0002, 0)  # 'C' UP
        user32.keybd_event(0x11, 0, 0x0002, 0)  # Ctrl UP

        self._pin_retry_count = 0
        QTimer.singleShot(90, self._process_pinned_text)

    def _process_pinned_text(self):
        cb = QApplication.clipboard()
        text = cb.text()

        if not text or not text.strip():
            retry_cnt = getattr(self, "_pin_retry_count", 0)
            if retry_cnt < 3:
                self._pin_retry_count = retry_cnt + 1
                QTimer.singleShot(60, self._process_pinned_text)
                return
            return

        self._pin_retry_count = 0
        clean_text = text.strip()
        self.last_clipboard_text = clean_text
        self.history_manager.add_pinned_entry(clean_text, "Anclada con Ctrl+Shift+C")
        if hasattr(self, "tab_text_history") and self.tab_text_history.isVisible():
            self.tab_text_history.refresh_list()
        if hasattr(self, "tray_icon") and self.tray_icon:
            clean_display = " ".join(clean_text.split())[:65]
            self.tray_icon.showMessage(
                "Jade — Nota Anclada y Copiada",
                f"📌 {clean_display}...",
                QSystemTrayIcon.MessageIcon.Information,
                1500
            )

    def closeEvent(self, event):
        if not getattr(self, "really_quit", False):
            event.ignore()
            self.hide()
            return

        self._is_closing = True
        
        try:
            QApplication.clipboard().dataChanged.disconnect(self.on_system_clipboard_changed)
        except Exception:
            pass

        try:
            if hasattr(self, "hotkey_thread") and self.hotkey_thread:
                self.hotkey_thread.stop()
        except Exception as e:
            log_message(f"Error deteniendo hotkey_thread: {e}")

        try:
            if self.is_recording and self.recorder_thread:
                self.recorder_thread.stop_recording()
                self.recorder_thread.wait(2000)
            if hasattr(self, "is_recording_audio") and self.is_recording_audio and self.audio_recorder_thread:
                self.audio_recorder_thread.stop_recording()
                self.audio_recorder_thread.wait(2000)
        except Exception as e:
            log_message(f"Error deteniendo hilos de grabación: {e}")

        try:
            if hasattr(self, "ocr_thread") and self.ocr_thread and self.ocr_thread.isRunning():
                self.ocr_thread.quit()
                self.ocr_thread.wait(1000)
        except Exception:
            pass

        try:
            clear_thumb_cache()
        except Exception:
            pass

        try:
            if hasattr(self, "floating_bar") and self.floating_bar:
                self.floating_bar.close()
        except Exception:
            pass

        try:
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.hide()
                self.tray_icon.deleteLater()
        except Exception:
            pass

        log_message("Jade cerrado y recursos de GPU/VRAM/Hilos liberados correctamente.")
        event.accept()

def is_admin() -> bool:
    """Comprueba de forma precisa en Windows si el proceso actual posee token de Administrador con integridad alta."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_to_admin():
    """Solicita elevación UAC en Windows relanzando el proceso con su directorio de trabajo exacto
    para operar de forma uniforme en Windows Home, Pro y Enterprise."""
    if is_admin():
        return True

    try:
        if getattr(sys, "frozen", False):
            target = sys.executable
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            working_dir = os.path.abspath(os.path.dirname(sys.executable))
        else:
            target = sys.executable
            script_path = os.path.abspath(sys.argv[0])
            args_list = [f'"{script_path}"'] + [f'"{arg}"' for arg in sys.argv[1:]]
            params = " ".join(args_list)
            working_dir = os.path.abspath(os.path.dirname(script_path))

        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            target,
            params,
            working_dir,
            1  # SW_SHOWNORMAL
        )
        if int(ret) > 32:
            sys.exit(0)
    except Exception as e:
        log_message(f"Error al solicitar elevación UAC: {e}")
    return False

def configure_system_permissions_environment():
    """Configura variables de entorno para que Argos, Tesseract y FFmpeg operen en AppData sin restricciones de UAC."""
    base_appdata = get_jade_appdata_dir()
    packages_dir = os.path.join(base_appdata, "argos_packages")
    data_dir = os.path.join(base_appdata, "argos_data")
    cache_dir = os.path.join(base_appdata, "cache", "argos")

    for d in [packages_dir, data_dir, cache_dir]:
        os.makedirs(d, exist_ok=True)

    os.environ["ARGOS_PACKAGES_DIR"] = packages_dir
    os.environ["ARGOS_PACKAGE_DIR"] = packages_dir
    os.environ["ARGOS_TRANSLATE_PACKAGE_DIR"] = packages_dir
    os.environ["XDG_DATA_HOME"] = data_dir
    os.environ["XDG_CONFIG_HOME"] = data_dir
    os.environ["XDG_CACHE_HOME"] = cache_dir

def main():
    import multiprocessing
    multiprocessing.freeze_support()

    # 1. Elevación inmediata obligatoria a Administrador para Windows Home, Pro y Enterprise
    if not is_admin():
        elevate_to_admin()
        sys.exit(0)

    # 2. Configurar directorio de trabajo y variables de entorno para evitar bloqueo de System32
    if getattr(sys, "frozen", False):
        app_dir = os.path.abspath(os.path.dirname(sys.executable))
    else:
        app_dir = os.path.abspath(os.path.dirname(sys.argv[0]))

    try:
        os.chdir(app_dir)
    except Exception:
        pass

    configure_system_permissions_environment()

    try:
        hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd_console:
            ctypes.windll.user32.ShowWindow(hwnd_console, 0)
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        qt_plugins = os.path.join(base_dir, "PyQt6", "Qt6", "plugins")
        if os.path.exists(qt_plugins):
            os.environ["QT_PLUGIN_PATH"] = qt_plugins
            QApplication.addLibraryPath(qt_plugins)

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    app.setApplicationName("Jade")
    app.setQuitOnLastWindowClosed(False)

    QThreadPool.globalInstance().setMaxThreadCount(4)

    icon_path = get_resource_path(".py/resources/icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 3. Comunicación Instantánea Inter-Proceso (Single-Instance IPC a < 15 ms)
    ipc_client = QLocalSocket()
    ipc_client.connectToServer("Jade_SingleInstance_IPC_Server")
    if ipc_client.waitForConnected(100):
        payload_data = json.dumps(sys.argv[1:]).encode("utf-8")
        ipc_client.write(payload_data)
        ipc_client.waitForBytesWritten(250)
        ipc_client.disconnectFromServer()
        sys.exit(0)
    del ipc_client

    config = ConfigManager()
    effective_theme = apply_app_theme(config)
    is_dark_theme = (effective_theme == "oscuro")

    MEDIA_EXTENSIONS = (
        '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif', '.ico', '.tiff', '.tif', '.jfif', '.heic', '.heif', '.avif', '.svg',
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ts', '.mts', '.m2ts', '.vob', '.ogv', '.asf', '.f4v', '.mpg', '.mpeg', '.mpv'
    )
    direct_media_file = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and os.path.exists(arg) and os.path.isfile(arg):
            clean_arg = os.path.abspath(arg)
            if clean_arg.lower().endswith(MEDIA_EXTENSIONS):
                direct_media_file = clean_arg
                break

    if direct_media_file:
        viewer_dialog = HDMediaViewerDialog(direct_media_file)
        hwnd = int(viewer_dialog.winId())
        enable_win11_effects(hwnd, dark_mode=is_dark_theme)
        viewer_dialog.show()
        viewer_dialog.raise_()
        viewer_dialog.activateWindow()
        sys.exit(viewer_dialog.exec())

    main_win = MainWindow(config)

    if "--minimized" in sys.argv:
        pass
    elif len(sys.argv) > 1:
        main_win.process_command_args(sys.argv[1:])
    else:
        main_win.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

JadeCaptureApp = MainWindow
