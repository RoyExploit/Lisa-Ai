import sys
import os
import shutil
import time
import win32com.client
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QProgressBar, QFileDialog, QGraphicsDropShadowEffect, QStackedWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter, QRadialGradient

APP_NAME = "Lisa AI"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "Lisa AI"
APP_EXE = "LisaAI.exe"
UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\LisaAI"


def _write_uninstall_entry(target_dir, setup_source=""):
    """Register in Add/Remove Programs so users can find + uninstall the app."""
    try:
        import winreg
        exe_path = os.path.join(target_dir, APP_EXE)
        uninstaller = os.path.join(target_dir, "uninstall.bat")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, target_dir)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe_path)
            # Add/Remove Programs needs these to show size + a real uninstall command
            try:
                size = sum(os.path.getsize(os.path.join(r, f))
                           for r, _, fs in os.walk(target_dir) for f in fs)
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size // 1024)
            except Exception:
                pass
            if os.path.exists(uninstaller):
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                                  '"' + uninstaller + '"')
                winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ,
                                  '"' + uninstaller + '"')
            else:
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                                  '"' + exe_path + '"')
            if setup_source:
                winreg.SetValueEx(key, "InstallSource", 0, winreg.REG_SZ, setup_source)
        return True
    except Exception as e:
        print(f"Failed to write uninstall entry: {e}")
        return False


def _remove_uninstall_entry():
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except Exception:
        pass


def _create_shortcut(shell, folder_kind, name, target, workdir, icon):
    """Create a .lnk; returns True on success. Raises nothing."""
    try:
        folder = shell.SpecialFolders(folder_kind)
        path = os.path.join(folder, name)
        sc = shell.CreateShortCut(path)
        sc.Targetpath = target
        sc.WorkingDirectory = workdir
        if icon and os.path.exists(icon):
            sc.IconLocation = icon
        sc.WindowStyle = 1
        sc.save()
        return os.path.exists(path)
    except Exception as e:
        print(f"Failed to create {folder_kind} shortcut: {e}")
        return False


def _write_uninstaller(target_dir):
    """Create an uninstall.bat that removes the app + shortcuts + registry entry."""
    try:
        bat_path = os.path.join(target_dir, "uninstall.bat")
        desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", "Lisa AI.lnk")
        programs = os.path.join(
            os.environ.get("APPDATA", ""), "Microsoft", "Windows",
            "Start Menu", "Programs", "Lisa AI.lnk")
        script = (
            "@echo off\r\n"
            "echo Uninstalling Lisa AI...\r\n"
            f'reg delete "HKCU\\{UNINSTALL_KEY}" /f >nul 2>&1\r\n'
            f'if exist "{desktop}" del /f /q "{desktop}"\r\n'
            f'if exist "{programs}" del /f /q "{programs}"\r\n'
            "timeout /t 2 /nobreak >nul\r\n"
            f'rmdir /s /q "{target_dir}"\r\n'
            "echo Done.\r\n"
        )
        with open(bat_path, "w") as f:
            f.write(script)
        return bat_path
    except Exception as e:
        print(f"Failed to write uninstaller: {e}")
        return None


class NativeOrbBackdrop(QWidget):
    """Black-screen particle orb backdrop (no WebEngine, no old web UI)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        import math
        import random
        self._n = 260
        golden = math.pi * (3.0 - math.sqrt(5.0))
        self._pts = []
        for i in range(self._n):
            y = 1.0 - (i / float(self._n - 1)) * 2.0
            r = math.sqrt(max(0.0, 1.0 - y * y))
            th = golden * i
            self._pts.append((math.cos(th) * r, y, math.sin(th) * r))
        self._phase = [random.uniform(0, math.tau) for _ in range(self._n)]
        self._angle = 0.0
        self._t0 = time.time()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        self._angle += 0.01
        self.update()

    def paintEvent(self, _event):
        import math
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(4, 6, 10))
        w, h = max(1, self.width()), max(1, self.height())
        cx, cy = w / 2.0, h / 2.0
        r0 = min(w, h) * 0.30
        t = time.time() - self._t0
        grad = QRadialGradient(cx, cy, r0 * 1.8)
        alpha = int(255 * (0.10 + 0.10 * (0.5 + 0.5 * math.sin(t * 1.2))))
        grad.setColorAt(0.0, QColor(0, 229, 255, alpha))
        grad.setColorAt(1.0, QColor(0, 229, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRect(0, 0, w, h)
        ca, sa = math.cos(self._angle), math.sin(self._angle)
        for i, (x, y, z) in enumerate(self._pts):
            amp = 0.5 + 0.5 * math.sin(t * 1.5 + self._phase[i])
            rad = r0 * (1.0 + 0.18 * amp)
            sx = cx + (x * ca - z * sa) * rad
            sy = cy + y * rad * 0.9
            b = int(90 + 120 * amp)
            p.setBrush(QColor(0, min(255, b + 60), 255))
            p.drawEllipse(int(sx), int(sy), 2, 2)
        p.end()

class InstallThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, source_dir, target_dir):
        super().__init__()
        self.source_dir = source_dir
        self.target_dir = target_dir

    def run(self):
        try:
            self.status.emit("Preparing installation...")
            self.progress.emit(10)
            time.sleep(1) # Let user see the text

            if os.path.exists(self.target_dir):
                self.status.emit("Removing old version...")
                shutil.rmtree(self.target_dir, ignore_errors=True)
            
            self.progress.emit(20)
            self.status.emit("Copying files... This might take a minute.")
            
            # Walk directory to calculate size or just use a simple copy tree
            if not os.path.exists(self.target_dir):
                os.makedirs(self.target_dir)

            total_files = sum([len(files) for r, d, files in os.walk(self.source_dir)])
            copied = 0
            
            for src_dir, dirs, files in os.walk(self.source_dir):
                dst_dir = src_dir.replace(self.source_dir, self.target_dir, 1)
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)
                for file_ in files:
                    src_file = os.path.join(src_dir, file_)
                    dst_file = os.path.join(dst_dir, file_)
                    shutil.copy2(src_file, dst_file)
                    copied += 1
                    if total_files > 0:
                        prog = 20 + int((copied / total_files) * 60)
                        if prog % 5 == 0:  # throttle signals
                            self.progress.emit(prog)

            self.progress.emit(80)
            self.status.emit("Creating shortcuts...")

            try:
                shell = win32com.client.Dispatch("WScript.Shell")
            except Exception:
                shell = None

            # Create Desktop + Start Menu shortcuts (verified, not assumed)
            exe_path = os.path.join(self.target_dir, APP_EXE)
            icon_path = os.path.join(self.target_dir, 'assets', 'Lisa_Lite_Logo.ico')
            desktop_ok = start_ok = False
            if os.path.exists(exe_path) and shell is not None:
                desktop_ok = _create_shortcut(shell, "Desktop", "Lisa AI.lnk",
                                              exe_path, self.target_dir, icon_path)
                start_ok = _create_shortcut(shell, "Programs", "Lisa AI.lnk",
                                            exe_path, self.target_dir, icon_path)

            self.progress.emit(100)
            self.status.emit("Registering app...")

            _write_uninstaller(self.target_dir)
            _write_uninstall_entry(self.target_dir)

            self.progress.emit(100)
            if not desktop_ok or not start_ok:
                self.status.emit("Installation Complete! (Note: a shortcut could not be created.)")
            else:
                self.status.emit("Installation Complete!")
            time.sleep(0.5)
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))

class InstallWizard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lisa AI - Setup")
        self.resize(800, 500)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Background Container (black screen + native orb; old WebEngine
        # golden-orb page removed project-wide)
        self.bg_container = QWidget(self)
        self.bg_container.resize(self.size())
        self.bg_container.setStyleSheet("background: #04060a;")

        # Native orb backdrop (pure Qt paint, no WebEngine, no old web UI)
        self.orb_backdrop = NativeOrbBackdrop(self.bg_container)
        self.orb_backdrop.resize(self.size())

        # Find assets folder (payload root inside the setup bundle)
        if hasattr(sys, '_MEIPASS'):
            self.base_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Overlay UI
        self.overlay = QWidget(self)
        self.overlay.resize(self.size())
        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(50, 50, 50, 50)

        # Content Box
        self.content_box = QWidget()
        self.content_box.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 200);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 30);
            }
            QLabel {
                background: transparent;
                border: none;
                color: white;
            }
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a73e8, stop:1 #4285f4);
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4285f4, stop:1 #1a73e8);
            }
            QPushButton:disabled {
                background-color: #555;
                color: #aaa;
            }
            QProgressBar {
                border: none;
                background-color: rgba(255, 255, 255, 20);
                border-radius: 5px;
                text-align: center;
                color: white;
                height: 15px;
            }
            QProgressBar::chunk {
                background-color: #4285f4;
                border-radius: 5px;
            }
        """)
        box_layout = QVBoxLayout(self.content_box)
        
        # Title
        title = QLabel("Lisa AI Setup")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(title)

        self.stacked_widget = QStackedWidget()
        box_layout.addWidget(self.stacked_widget)
        
        # PAGE 1: Welcome & Path
        self.page1 = QWidget()
        self.page1.setStyleSheet("background: transparent; border: none;")
        p1_layout = QVBoxLayout(self.page1)
        
        desc = QLabel("Welcome to the Lisa AI Setup Wizard.\nClick Install to continue.")
        desc.setFont(QFont("Segoe UI", 12))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p1_layout.addWidget(desc)
        
        # Default Path
        self.install_path = os.path.join(os.environ.get('LOCALAPPDATA', os.environ['USERPROFILE']), 'Lisa_Evo')
        path_label = QLabel(f"Destination Folder: {self.install_path}")
        path_label.setFont(QFont("Segoe UI", 10))
        path_label.setStyleSheet("color: #aaa;")
        path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p1_layout.addWidget(path_label)

        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.close)
        self.btn_install = QPushButton("Install")
        self.btn_install.clicked.connect(self.start_installation)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_install)
        btn_layout.addStretch()
        p1_layout.addLayout(btn_layout)
        
        self.stacked_widget.addWidget(self.page1)

        # PAGE 2: Installing
        self.page2 = QWidget()
        self.page2.setStyleSheet("background: transparent; border: none;")
        p2_layout = QVBoxLayout(self.page2)
        
        self.lbl_status = QLabel("Preparing to install...")
        self.lbl_status.setFont(QFont("Segoe UI", 12))
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p2_layout.addWidget(self.lbl_status)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        p2_layout.addWidget(self.progress_bar)
        
        self.stacked_widget.addWidget(self.page2)

        # PAGE 3: Finished
        self.page3 = QWidget()
        self.page3.setStyleSheet("background: transparent; border: none;")
        p3_layout = QVBoxLayout(self.page3)
        
        lbl_finish = QLabel("Installation Complete!")
        lbl_finish.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_finish.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p3_layout.addWidget(lbl_finish)
        
        btn_finish = QPushButton("Launch Lisa AI")
        btn_finish.clicked.connect(self.launch_app)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)

        btn_layout_finish = QHBoxLayout()
        btn_layout_finish.addStretch()
        btn_layout_finish.addWidget(btn_close)
        btn_layout_finish.addWidget(btn_finish)
        btn_layout_finish.addStretch()
        
        p3_layout.addLayout(btn_layout_finish)
        
        self.stacked_widget.addWidget(self.page3)

        overlay_layout.addWidget(self.content_box)
        layout.addWidget(self.overlay)

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.content_box.setGraphicsEffect(shadow)
        
    def resizeEvent(self, event):
        self.bg_container.resize(self.size())
        if hasattr(self, 'orb_backdrop'):
            self.orb_backdrop.resize(self.size())
        self.overlay.resize(self.size())
        super().resizeEvent(event)

    def start_installation(self):
        self.stacked_widget.setCurrentIndex(1)
        source_dir = os.path.join(self.base_dir, 'LisaAI')
        if not os.path.exists(source_dir):
            self.lbl_status.setText(f"Error: Payload missing.\n{source_dir}")
            return
            
        self.thread = InstallThread(source_dir, self.install_path)
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.status.connect(self.lbl_status.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.error.connect(self.on_error)
        self.thread.start()
        
    def on_finished(self):
        self.stacked_widget.setCurrentIndex(2)
        
    def on_error(self, msg):
        self.lbl_status.setText(f"Installation failed:\n{msg}")
        self.lbl_status.setStyleSheet("color: #ff4444;")
        
    def launch_app(self):
        exe_path = os.path.join(self.install_path, 'LisaAI.exe')
        if os.path.exists(exe_path):
            os.startfile(exe_path)
        self.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    wizard = InstallWizard()
    wizard.show()
    sys.exit(app.exec())
