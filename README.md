<p align="center">
  <img src="resources/icon.ico" width="96" height="96" alt="Jade Logo" />
</p>

<h1 align="center">💎 Jade — Suite Multimedia Inteligente para Windows</h1>

<p align="center">
  <strong>Captura ultrarrápida, grabación a 60 FPS con GPU, OCR nativo WinRT, traducción en tiempo real y galería virtualizada de alto rendimiento.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/OS-Windows%2010%20%7C%2011%20(64--bit)-0078D6?logo=windows" alt="Windows Support" />
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt" alt="PyQt6" />
  <img src="https://img.shields.io/badge/Compiler-Nuitka%20C%2B%2B-FF6F00?logo=c%2B%2B" alt="Nuitka" />
  <img src="https://img.shields.io/badge/Architecture-Clean%20Modular-blueviolet" alt="Architecture" />
</p>

---

## 🌟 Características Principales

- ⚡ **Captura de Pantalla Instantánea (< 15 ms):** Captura GDI nativa en memoria C con mapeo tonal HDR en RAM y exclusión de overlays.
- 🎥 **Grabación de Video a 60 FPS:** Motor DDAGRAB / GPU con aceleración por hardware (NVIDIA NVENC / x264) y captura simultánea de audio de sistema (WASAPI Loopback) y micrófono.
- 🔍 **OCR Dual en Memoria:** Reconocimiento de texto ultrarrápido utilizando la API nativa de Windows (WinRT `Windows.Media.Ocr`) en RAM con fallback transparente a motor Tesseract.
- 🌐 **Traducción en Tiempo Real:** Traducción local sin conexión a internet (Argos Translate) y soporte online instantáneo.
- 🎮 **Modo Juego:** Detección y traducción sobrepuesta al vuelo en videojuegos y aplicaciones DirectX/Vulkan mediante recuadros transparentes flotantes y plantillas por juego.
- 🖼️ **Editor Gráfico Multicapas:** Anotación profesional con flechas direccionales, rectángulos, círculos, difuminado/mosaico censor y texto con sombra.
- 📚 **Galería Fotográfica Virtualizada:** Mural fluido estilo *justified layout* con virtualización de viewport (reciclaje de widgets), búsqueda binaria de filas visibles, soporte para más de 100,000 archivos sin sobrecarga de memoria (< 120 MB RAM).
- 🎬 **Visor HD con LibVLC:** Zoom suave hasta el 800%, rotaciones sin pérdida y reproducción fluida de más de 30 formatos multimedia.
- 🌓 **Motor de Temas Reactivo:** Sincronización instantánea con el modo Claro y Oscuro de Windows 11 / 10 en tiempo real con efectos DWM nativos.

---

## 📋 Requisitos Previos

- **Sistema Operativo:** Windows 10 (versión 1903+) o Windows 11 (64-bit).
- **Python:** Versión 3.11 o 3.12 (64-bit) agregada al `PATH`.
- **Privilegios:** Ejecución como Administrador (Jade incorpora auto-elevación UAC nativa).

---

## 🚀 Inicio Rápido (Modo Pruebas y Desarrollo)

Para clonar y probar el proyecto de inmediato sin configurar nada manualmente:

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/usuario/jade.git
   cd jade
   ```

2. **Ejecutar el lanzador inteligente:**
   Haz doble clic sobre:
   ```cmd
   run_test.bat
   ```
   > **¿Qué hace `run_test.bat` automáticamente?**
   > - Detecta si existe un entorno virtual (`.venv`); si no existe, lo crea.
   > - Sincroniza e instala silenciosamente todas las librerías oficiales de `requirements.txt`.
   > - Inicia Jade con todos sus subsistemas activos.

---

## 📦 Compilación a Ejecutable Independiente (.EXE)

El proyecto está diseñado para compilarse en un ejecutable nativo de C++ de un solo archivo (`--onefile`), sin necesidad de que el usuario final tenga Python instalado.

Para compilar el binario:

1. Haz doble clic sobre:
   ```cmd
   build_exe.bat
   ```

2. Al finalizar, el ejecutable listo para producción estará en:
   ```text
   dist\Jade.exe
   ```

El archivo `.exe` compilado incorpora:
- Manifiesto PE con privilegios UAC automáticos (`--windows-uac-admin`).
- Ocultación total de consolas parásitas (`--windows-disable-console`).
- Icono oficial integrado y assets incrustados en memoria (`sys._MEIPASS`).
- Solo abrir y usar en cualquier computadora con Windows.

---

## 🏛️ Arquitectura del Software

Para detalles técnicos exhaustivos sobre la estructura modular en `src/`, el flujo de llamadas entre capas, la gestión de memoria y el reciclaje de widgets, consulta la documentación oficial:

👉 **[Ver ARCHITECTURE.md](ARCHITECTURE.md)**

---

## 📂 Estructura del Código

```text
Jade/
├── main.py                  # Punto de entrada y fachada de compatibilidad
├── src/                     # Código fuente modularizado
│   ├── config/              # Rutas dinámicas, constantes Win32 y configuraciones
│   ├── utils/               # Llamadas Win32, detección de hardware, gráficos SVG y logs
│   ├── core/                # Captura GDI, grabación WASAPI, OCR WinRT, traducción e instaladores
│   └── ui/                  # Componentes visuales, overlays, tarjetas, diálogos y MainWindow
├── galeria.py               # Galería virtualizada de alto rendimiento
├── reproductor.py           # Visor multimedia HD con LibVLC
├── jade_editor.py           # Editor gráfico multicapas
├── juego.py                 # Módulo de traducción para videojuegos
├── theme_manager.py         # Motor de temas Claro / Oscuro
├── run_test.bat             # Lanzador automatizado para desarrollo
├── build_exe.bat            # Compilador a .EXE independiente
├── requirements.txt         # Dependencias del proyecto
└── ARCHITECTURE.md          # Especificación técnica de arquitectura
```

---

## 📄 Licencia

Distribuido bajo la licencia MIT. Consulta `LICENSE` para más información.
