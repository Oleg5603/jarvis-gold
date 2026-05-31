"""VPN Gate API client and OpenVPN connection manager."""
import base64
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Optional

COUNTRIES = {
    "США":       "US",
    "Нидерланды": "NL",
    "Англия":    "GB",
    "Франция":   "FR",
    "Германия":  "DE",
}

COUNTRY_FLAGS = {
    "США":       "🇺🇸",
    "Нидерланды": "🇳🇱",
    "Англия":    "🇬🇧",
    "Франция":   "🇫🇷",
    "Германия":  "🇩🇪",
}

VPN_GATE_API = "https://www.vpngate.net/api/iphone/"


def fetch_servers(country_code: str) -> list[dict]:
    req = urllib.request.Request(
        VPN_GATE_API,
        headers={"User-Agent": "Mozilla/5.0 VPNSwitcher/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise ConnectionError(f"Не удалось загрузить список серверов: {e}")

    lines = [l for l in raw.splitlines() if not l.startswith("*") and l.strip()]
    if len(lines) < 2:
        return []

    reader = csv.DictReader(lines)
    servers = []
    for row in reader:
        if row.get("CountryShort", "").strip() != country_code:
            continue
        config_b64 = row.get("OpenVPN_ConfigData_Base64", "").strip()
        if not config_b64:
            continue
        try:
            servers.append({
                "hostname": row.get("HostName", "").strip(),
                "ip": row.get("IP", "").strip(),
                "ping": int(row.get("Ping", "9999") or "9999"),
                "speed": int(row.get("Speed", "0") or "0"),
                "score": int(row.get("Score", "0") or "0"),
                "country": row.get("CountryLong", "").strip(),
                "config_b64": config_b64,
            })
        except (ValueError, KeyError):
            continue

    servers.sort(key=lambda x: (x["ping"], -x["score"]))
    return servers


def get_best_servers(country_code: str, count: int = 5) -> list[dict]:
    return fetch_servers(country_code)[:count]


def measure_ping(ip: str) -> int:
    """Returns ping in ms, or 9999 on failure."""
    try:
        if sys.platform == "win32":
            cmd = ["ping", "-n", "3", "-w", "1000", ip]
        else:
            cmd = ["ping", "-c", "3", "-W", "1", ip]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        output = result.stdout
        if sys.platform == "win32":
            for line in output.split("\n"):
                if "Среднее" in line or "Average" in line:
                    parts = line.split("=")
                    if parts:
                        val = parts[-1].strip().replace("мс", "").replace("ms", "").strip()
                        return int(val)
        else:
            for line in output.split("\n"):
                if "avg" in line or "rtt" in line:
                    parts = line.split("/")
                    if len(parts) >= 5:
                        return int(float(parts[4]))
    except Exception:
        pass
    return 9999


def get_current_ip() -> dict:
    for url in [
        "https://ipinfo.io/json",
        "https://api.ipify.org?format=json",
    ]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VPNSwitcher/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "ip": data.get("ip", "?"),
                    "country": data.get("country", ""),
                    "city": data.get("city", ""),
                    "org": data.get("org", ""),
                }
        except Exception:
            continue
    return {"ip": "Нет доступа", "country": "", "city": "", "org": ""}


def get_openvpn_path() -> Optional[str]:
    candidates = [
        r"C:\Program Files\OpenVPN\bin\openvpn.exe",
        r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # Try PATH
    try:
        subprocess.run(["openvpn", "--version"], capture_output=True, timeout=3)
        return "openvpn"
    except Exception:
        pass
    return None


def is_admin() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return os.geteuid() == 0


def extract_config(config_b64: str) -> str:
    return base64.b64decode(config_b64).decode("utf-8", errors="replace")


class OpenVPNProcess:
    """Manages a single OpenVPN subprocess."""

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._config_file: Optional[str] = None

    def connect(self, config_b64: str, on_line=None) -> bool:
        self.disconnect()
        openvpn = get_openvpn_path()
        if not openvpn:
            raise FileNotFoundError(
                "OpenVPN не найден.\n"
                "Скачайте с официального сайта и установите:\n"
                "https://openvpn.net/community-downloads/"
            )

        config_data = extract_config(config_b64)
        fd, self._config_file = tempfile.mkstemp(suffix=".ovpn")
        with os.fdopen(fd, "w") as f:
            f.write(config_data)

        cmd = [openvpn, "--config", self._config_file]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception as e:
            self._cleanup_config()
            raise RuntimeError(f"Не удалось запустить OpenVPN: {e}")

        return True

    def wait_connected(self, timeout: int = 60) -> bool:
        """Blocks until 'Initialization Sequence Completed' or timeout."""
        if not self._proc:
            return False
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._proc.poll() is not None:
                return False
            line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            if "Initialization Sequence Completed" in line:
                return True
        return False

    def read_log_line(self) -> Optional[str]:
        if not self._proc:
            return None
        return self._proc.stdout.readline()

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def disconnect(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        self._cleanup_config()

    def _cleanup_config(self):
        if self._config_file and os.path.exists(self._config_file):
            try:
                os.remove(self._config_file)
            except Exception:
                pass
        self._config_file = None
