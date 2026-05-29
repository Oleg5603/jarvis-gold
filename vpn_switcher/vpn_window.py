"""Main VPN Switcher window."""
import sys
import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFrame, QGroupBox,
    QSizePolicy, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from vpn_gate import (
    COUNTRIES, COUNTRY_FLAGS,
    get_best_servers, get_current_ip,
    measure_ping, OpenVPNProcess, is_admin,
)


# ─── Worker threads ──────────────────────────────────────────────────────────

class IPCheckerThread(QThread):
    result = pyqtSignal(dict)

    def run(self):
        self.result.emit(get_current_ip())


class FetchAndPingThread(QThread):
    """Fetches best servers for a country, then measures real ping."""
    status   = pyqtSignal(str)
    ready    = pyqtSignal(dict)  # best server dict
    error    = pyqtSignal(str)

    def __init__(self, country_name: str):
        super().__init__()
        self.country_name = country_name
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        code = COUNTRIES[self.country_name]
        self.status.emit(f"Загружаю серверы {self.country_name}...")
        try:
            servers = get_best_servers(code, count=10)
        except ConnectionError as e:
            self.error.emit(str(e))
            return

        if not servers:
            self.error.emit(f"Нет серверов для {self.country_name}")
            return

        if self._abort:
            return

        self.status.emit(f"Измеряю пинг... ({len(servers)} серверов)")
        best = None
        best_ping = 99999
        for srv in servers[:5]:
            if self._abort:
                return
            self.status.emit(f"Пинг {srv['ip']}...")
            real_ping = measure_ping(srv["ip"])
            if real_ping < best_ping:
                best_ping = real_ping
                srv["real_ping"] = real_ping
                best = srv

        if best:
            self.ready.emit(best)
        else:
            self.error.emit("Не удалось измерить пинг ни одного сервера")


class VPNConnectThread(QThread):
    log_line  = pyqtSignal(str)
    connected = pyqtSignal()
    failed    = pyqtSignal(str)

    def __init__(self, server: dict, vpn_proc: OpenVPNProcess):
        super().__init__()
        self.server = server
        self.vpn = vpn_proc

    def run(self):
        try:
            self.vpn.connect(self.server["config_b64"])
        except (FileNotFoundError, RuntimeError) as e:
            self.failed.emit(str(e))
            return

        self.log_line.emit("OpenVPN запущен, ожидаю подключения...")
        deadline = time.time() + 60
        while time.time() < deadline:
            if not self.vpn.is_running():
                self.failed.emit("OpenVPN завершился неожиданно")
                return
            line = self.vpn.read_log_line()
            if not line:
                time.sleep(0.1)
                continue
            line = line.strip()
            if line:
                self.log_line.emit(line)
            if "Initialization Sequence Completed" in line:
                self.connected.emit()
                return

        self.vpn.disconnect()
        self.failed.emit("Таймаут подключения (60 сек)")


# ─── Country button ───────────────────────────────────────────────────────────

class CountryButton(QPushButton):
    def __init__(self, country_name: str):
        flag = COUNTRY_FLAGS.get(country_name, "")
        super().__init__(f"{flag} {country_name}")
        self.country_name = country_name
        self._ping: str = ""
        self.setFixedHeight(54)
        self.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._set_idle()

    def set_ping(self, ms: int):
        self._ping = f"{ms} мс" if ms < 9999 else "нет"
        flag = COUNTRY_FLAGS.get(self.country_name, "")
        self.setText(f"{flag} {self.country_name}  [{self._ping}]")

    def set_loading(self):
        flag = COUNTRY_FLAGS.get(self.country_name, "")
        self.setText(f"{flag} {self.country_name}  [...]")
        self.setStyleSheet(
            "QPushButton { background:#4a4a00; color:#ffff88; border:2px solid #888800;"
            "border-radius:8px; padding:4px 12px; }"
            "QPushButton:hover { background:#666600; }"
        )

    def set_active(self):
        self.setStyleSheet(
            "QPushButton { background:#004400; color:#88ff88; border:2px solid #00aa00;"
            "border-radius:8px; padding:4px 12px; }"
        )

    def set_connecting(self):
        self.setStyleSheet(
            "QPushButton { background:#002244; color:#88aaff; border:2px solid #0055cc;"
            "border-radius:8px; padding:4px 12px; }"
        )

    def _set_idle(self):
        self.setStyleSheet(
            "QPushButton { background:#2a2a2a; color:#dddddd; border:2px solid #555555;"
            "border-radius:8px; padding:4px 12px; }"
            "QPushButton:hover { background:#3a3a3a; border-color:#888888; }"
            "QPushButton:pressed { background:#1a1a1a; }"
        )

    def reset(self):
        flag = COUNTRY_FLAGS.get(self.country_name, "")
        self.setText(f"{flag} {self.country_name}" + (f"  [{self._ping}]" if self._ping else ""))
        self._set_idle()


# ─── Main window ──────────────────────────────────────────────────────────────

class VPNWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VPN Switcher — Гаврик")
        self.setMinimumSize(520, 580)
        self.setStyleSheet("QMainWindow { background:#1a1a1a; }")

        self._vpn = OpenVPNProcess()
        self._connected_country: str = ""
        self._fetch_thread: FetchAndPingThread | None = None
        self._connect_thread: VPNConnectThread | None = None
        self._current_server: dict | None = None

        self._build_ui()

        # Check IP on start
        self._refresh_ip()

        # Auto-ping all countries in background on startup
        QTimer.singleShot(500, self._ping_all_startup)

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # IP block
        ip_box = QGroupBox("Текущий IP")
        ip_box.setStyleSheet(
            "QGroupBox { color:#aaaaaa; border:1px solid #444; border-radius:6px;"
            "margin-top:8px; padding-top:4px; font-size:11px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }"
        )
        ip_layout = QHBoxLayout(ip_box)
        self.lbl_ip = QLabel("—")
        self.lbl_ip.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        self.lbl_ip.setStyleSheet("color:#00ff88;")
        self.lbl_country_flag = QLabel("")
        self.lbl_country_flag.setFont(QFont("Segoe UI Emoji", 22))
        self.lbl_country_info = QLabel("")
        self.lbl_country_info.setStyleSheet("color:#888888; font-size:11px;")
        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedSize(30, 30)
        btn_refresh.setToolTip("Обновить IP")
        btn_refresh.setStyleSheet(
            "QPushButton { background:#333; color:#aaa; border:1px solid #555; border-radius:4px; font-size:16px; }"
            "QPushButton:hover { background:#444; }"
        )
        btn_refresh.clicked.connect(self._refresh_ip)
        ip_layout.addWidget(self.lbl_country_flag)
        ip_layout.addWidget(self.lbl_ip)
        ip_layout.addWidget(self.lbl_country_info)
        ip_layout.addStretch()
        ip_layout.addWidget(btn_refresh)
        root.addWidget(ip_box)

        # Status bar
        self.lbl_status = QLabel("Не подключён")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setFont(QFont("Segoe UI", 11))
        self.lbl_status.setStyleSheet(
            "color:#ff6666; background:#2a1a1a; border:1px solid #552222;"
            "border-radius:6px; padding:6px;"
        )
        root.addWidget(self.lbl_status)

        # Progress bar (hidden by default)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet(
            "QProgressBar { background:#222; border:none; border-radius:3px; }"
            "QProgressBar::chunk { background:#0077ff; border-radius:3px; }"
        )
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # Country buttons
        btn_box = QGroupBox("Выберите страну")
        btn_box.setStyleSheet(
            "QGroupBox { color:#aaaaaa; border:1px solid #444; border-radius:6px;"
            "margin-top:8px; padding-top:4px; font-size:11px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }"
        )
        btn_layout = QVBoxLayout(btn_box)
        btn_layout.setSpacing(6)
        self._country_buttons: dict[str, CountryButton] = {}
        for name in COUNTRIES:
            btn = CountryButton(name)
            btn.clicked.connect(lambda checked, n=name: self._on_country_click(n))
            btn_layout.addWidget(btn)
            self._country_buttons[name] = btn
        root.addWidget(btn_box)

        # Disconnect button
        self.btn_disconnect = QPushButton("⏹  Отключиться")
        self.btn_disconnect.setFixedHeight(44)
        self.btn_disconnect.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.setStyleSheet(
            "QPushButton { background:#440000; color:#ff8888; border:2px solid #880000;"
            "border-radius:8px; }"
            "QPushButton:enabled { background:#550000; color:#ffaaaa; border-color:#cc0000; }"
            "QPushButton:enabled:hover { background:#660000; }"
            "QPushButton:disabled { color:#444; border-color:#333; background:#222; }"
        )
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        root.addWidget(self.btn_disconnect)

        # Log
        log_box = QGroupBox("Лог")
        log_box.setStyleSheet(
            "QGroupBox { color:#aaaaaa; border:1px solid #444; border-radius:6px;"
            "margin-top:8px; padding-top:4px; font-size:11px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }"
        )
        log_layout = QVBoxLayout(log_box)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setFont(QFont("Consolas", 9))
        self.log.setStyleSheet("background:#111; color:#888; border:none;")
        log_layout.addWidget(self.log)
        root.addWidget(log_box)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _log(self, text: str):
        self.log.append(text)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _set_status(self, text: str, color: str = "#ffcc44"):
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(
            f"color:{color}; background:#1e1e1e; border:1px solid #444;"
            "border-radius:6px; padding:6px;"
        )

    def _set_connected_status(self, country: str):
        flag = COUNTRY_FLAGS.get(country, "")
        self.lbl_status.setText(f"✅ Подключён: {flag} {country}")
        self.lbl_status.setStyleSheet(
            "color:#88ff88; background:#0a1a0a; border:1px solid #00aa00;"
            "border-radius:6px; padding:6px;"
        )

    def _set_disconnected_status(self):
        self.lbl_status.setText("⛔ Не подключён")
        self.lbl_status.setStyleSheet(
            "color:#ff6666; background:#2a1a1a; border:1px solid #552222;"
            "border-radius:6px; padding:6px;"
        )

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._country_buttons.values():
            btn.setEnabled(enabled)

    # ── IP refresh ────────────────────────────────────────────────────────────

    def _refresh_ip(self):
        self.lbl_ip.setText("...")
        self.lbl_country_flag.setText("")
        self.lbl_country_info.setText("")
        t = IPCheckerThread(self)
        t.result.connect(self._on_ip_result)
        t.finished.connect(t.deleteLater)
        t.start()

    def _on_ip_result(self, data: dict):
        self.lbl_ip.setText(data.get("ip", "?"))
        country_code = data.get("country", "")
        city = data.get("city", "")
        org = data.get("org", "")
        self.lbl_country_info.setText(f"{city} · {org}" if city or org else country_code)
        # Simple flag from country code
        flag = _country_code_to_flag(country_code)
        self.lbl_country_flag.setText(flag)

    # ── Startup ping ─────────────────────────────────────────────────────────

    def _ping_all_startup(self):
        """Ping all countries one by one on startup to show latency."""
        self._pending_startup_pings = list(COUNTRIES.keys())
        self._ping_next_startup()

    def _ping_next_startup(self):
        if not self._pending_startup_pings:
            return
        if self._connected_country:  # don't ping during connection
            return
        country = self._pending_startup_pings.pop(0)
        t = _SinglePingThread(self, country)
        t.done.connect(self._on_startup_ping_done)
        t.finished.connect(t.deleteLater)
        t.start()

    def _on_startup_ping_done(self, country: str, ping_ms: int):
        if country in self._country_buttons:
            self._country_buttons[country].set_ping(ping_ms)
        self._ping_next_startup()

    # ── Country click ─────────────────────────────────────────────────────────

    def _on_country_click(self, country: str):
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.abort()

        self._set_buttons_enabled(False)
        for btn in self._country_buttons.values():
            btn.reset()
        self._country_buttons[country].set_loading()

        self.progress.setVisible(True)
        self._set_status(f"Ищу лучший сервер: {COUNTRY_FLAGS.get(country,'')} {country}...")

        self._fetch_thread = FetchAndPingThread(country)
        self._fetch_thread.status.connect(self._set_status)
        self._fetch_thread.ready.connect(lambda srv: self._on_server_ready(country, srv))
        self._fetch_thread.error.connect(self._on_fetch_error)
        self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)
        self._fetch_thread.start()

    def _on_fetch_error(self, msg: str):
        self.progress.setVisible(False)
        self._set_status(f"❌ {msg}", "#ff6666")
        self._set_buttons_enabled(True)

    def _on_server_ready(self, country: str, server: dict):
        self.progress.setVisible(False)
        ping = server.get("real_ping", server.get("ping", 0))
        self._country_buttons[country].set_ping(ping)
        self._country_buttons[country].set_connecting()
        self._current_server = server

        self._log(f"→ Сервер: {server['ip']} | Пинг: {ping} мс | {server['country']}")
        self._set_status(f"⏳ Подключаюсь: {COUNTRY_FLAGS.get(country,'')} {country} ({ping} мс)...")
        self.progress.setVisible(True)

        if not is_admin():
            self._log("⚠️  Запустите приложение от имени Администратора для OpenVPN!")

        self._connect_thread = VPNConnectThread(server, self._vpn)
        self._connect_thread.log_line.connect(self._log)
        self._connect_thread.connected.connect(lambda: self._on_vpn_connected(country))
        self._connect_thread.failed.connect(self._on_vpn_failed)
        self._connect_thread.finished.connect(self._connect_thread.deleteLater)
        self._connect_thread.start()

    def _on_vpn_connected(self, country: str):
        self.progress.setVisible(False)
        self._connected_country = country
        self._set_connected_status(country)
        self._country_buttons[country].set_active()
        self._set_buttons_enabled(True)
        self.btn_disconnect.setEnabled(True)
        self._log(f"✅ Подключён к {country}")
        # Refresh IP to show new one
        QTimer.singleShot(2000, self._refresh_ip)

    def _on_vpn_failed(self, msg: str):
        self.progress.setVisible(False)
        self._set_status(f"❌ Ошибка: {msg}", "#ff6666")
        self._set_buttons_enabled(True)
        for btn in self._country_buttons.values():
            btn.reset()
        self._log(f"❌ {msg}")

    # ── Disconnect ────────────────────────────────────────────────────────────

    def _on_disconnect(self):
        self._vpn.disconnect()
        self._connected_country = ""
        self._set_disconnected_status()
        self.btn_disconnect.setEnabled(False)
        for btn in self._country_buttons.values():
            btn.reset()
        self._log("— Отключено")
        QTimer.singleShot(1500, self._refresh_ip)

    def closeEvent(self, event):
        self._vpn.disconnect()
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.abort()
        event.accept()


# ── Single-country ping thread (used in startup scan) ───────────────────────

class _SinglePingThread(QThread):
    done = pyqtSignal(str, int)  # country_name, ping_ms

    def __init__(self, parent, country_name: str):
        super().__init__(parent)
        self.country_name = country_name

    def run(self):
        from vpn_gate import fetch_servers, COUNTRIES, measure_ping
        code = COUNTRIES[self.country_name]
        try:
            servers = fetch_servers(code)
            if not servers:
                self.done.emit(self.country_name, 9999)
                return
            # Use VPNGate's own ping value for speed; also try real ping on top server
            best_vg_ping = servers[0]["ping"]
            real = measure_ping(servers[0]["ip"])
            self.done.emit(self.country_name, min(best_vg_ping, real))
        except Exception:
            self.done.emit(self.country_name, 9999)


# ── Utility ──────────────────────────────────────────────────────────────────

def _country_code_to_flag(code: str) -> str:
    """Convert ISO 3166-1 alpha-2 to emoji flag."""
    if not code or len(code) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())
