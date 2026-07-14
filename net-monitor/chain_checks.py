"""
chain_checks.py — проверка цепочки прохождения интернет-сигнала:
ОС/адаптер -> Роутер (шлюз) -> Провайдер (ISP) -> VPN (если активен) -> DNS -> Целевой сайт.

Каждый шаг возвращает CheckResult(ok, detail). Первый упавший шаг = точка обрыва.
"""
import socket
import subprocess
import time
import platform
import re
from dataclasses import dataclass

import psutil

_IS_WIN = platform.system() == "Windows"
_SUBPROCESS_KW = {"creationflags": subprocess.CREATE_NO_WINDOW} if _IS_WIN else {}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    latency_ms: float | None = None


PING_TIMEOUT_MS = 1500
DNS_TEST_HOST = "google.com"
PUBLIC_DNS_IPS = ["1.1.1.1", "8.8.8.8"]
TARGET_URLS = ["https://www.google.com", "https://ya.ru"]
CLAUDE_API_URL = "https://api.anthropic.com"

VPN_HINTS = ("tun", "tap", "wireguard", "wg", "vpn", "openvpn", "nordlynx", "zerotier", "cloudflarewarp")


def _ping(ip: str, timeout_ms: int = PING_TIMEOUT_MS) -> tuple[bool, float | None, str]:
    """Возвращает (успех, latency_ms, сырой_вывод_причины)."""
    is_win = platform.system() == "Windows"
    cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip] if is_win else \
          ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), ip]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_ms / 1000 + 2,
                              encoding="cp866" if is_win else "utf-8", errors="replace", **_SUBPROCESS_KW)
        text = out.stdout + out.stderr
    except Exception as e:
        return False, None, f"ошибка запуска ping: {e}"

    if is_win:
        if "TTL=" in text or "ttl=" in text:
            m = re.search(r"(?:время|time)[=<]\s*(\d+)", text, re.IGNORECASE)
            lat = float(m.group(1)) if m else None
            return True, lat, "ok"
        if "Заданный узел недоступен" in text or "Destination host unreachable" in text:
            return False, None, "узел недоступен (нет маршрута)"
        if "Превышен интервал ожидания" in text or "Request timed out" in text:
            return False, None, "таймаут (нет ответа)"
        return False, None, text.strip().splitlines()[-1] if text.strip() else "нет ответа"
    else:
        if "1 received" in text or " 0% packet loss" in text:
            m = re.search(r"time=([\d.]+)", text)
            lat = float(m.group(1)) if m else None
            return True, lat, "ok"
        return False, None, "нет ответа"


def get_default_gateway() -> str | None:
    is_win = platform.system() == "Windows"
    try:
        if is_win:
            out = subprocess.run(["ipconfig"], capture_output=True, text=True,
                                  encoding="cp866", errors="replace", **_SUBPROCESS_KW).stdout
            m = re.search(r"Основной шлюз[^\n:]*:\s*([\d.]+)", out)
            if not m:
                m = re.search(r"Default Gateway[^\n:]*:\s*([\d.]+)", out)
            return m.group(1) if m and m.group(1) else None
        else:
            out = subprocess.run(["ip", "route"], capture_output=True, text=True, **_SUBPROCESS_KW).stdout
            m = re.search(r"default via ([\d.]+)", out)
            return m.group(1) if m else None
    except Exception:
        return None


def check_os_adapter() -> CheckResult:
    stats = psutil.net_if_stats()
    up_ifaces = [name for name, s in stats.items() if s.isup and "loopback" not in name.lower()]
    if not up_ifaces:
        return CheckResult("ОС / сетевой адаптер", False, "нет активных сетевых интерфейсов")
    return CheckResult("ОС / сетевой адаптер", True, f"активны: {', '.join(up_ifaces[:4])}")


PING_RETRIES = 1  # доп. попытки пинга перед тем, как считать шаг упавшим (гасит единичную потерю пакета)


def _ping_with_retry(ip: str) -> tuple[bool, float | None, str]:
    ok, lat, detail = _ping(ip)
    for _ in range(PING_RETRIES):
        if ok:
            break
        ok, lat, detail = _ping(ip)
    return ok, lat, detail


def check_router() -> CheckResult:
    gw = get_default_gateway()
    if not gw:
        return CheckResult("Роутер (шлюз)", False, "не удалось определить шлюз по умолчанию")
    ok, lat, detail = _ping_with_retry(gw)
    lat_s = f", {lat:.0f} мс" if lat else ""
    return CheckResult("Роутер (шлюз)", ok, f"{gw}: {detail}{lat_s}", lat)


def check_isp() -> CheckResult:
    """Пинг публичных IP напрямую (без DNS) — проверка, что провайдер пропускает трафик наружу."""
    last_detail = ""
    for ip in PUBLIC_DNS_IPS:
        ok, lat, detail = _ping_with_retry(ip)
        if ok:
            return CheckResult("Провайдер (интернет по IP)", True, f"{ip}: {detail}, {lat:.0f} мс" if lat else f"{ip}: ok", lat)
        last_detail = f"{ip}: {detail}"
    return CheckResult("Провайдер (интернет по IP)", False, last_detail)


def check_vpn() -> CheckResult:
    stats = psutil.net_if_stats()
    active_vpn = [name for name, s in stats.items()
                  if s.isup and any(h in name.lower() for h in VPN_HINTS)]
    if not active_vpn:
        return CheckResult("VPN", True, "VPN не используется (интерфейс не найден)")
    return CheckResult("VPN", True, f"активен: {', '.join(active_vpn)}")


DNS_RETRIES = 1


def check_dns() -> CheckResult:
    last_err = None
    for _ in range(DNS_RETRIES + 1):
        try:
            t0 = time.time()
            ip = socket.gethostbyname(DNS_TEST_HOST)
            lat = (time.time() - t0) * 1000
            return CheckResult("DNS", True, f"{DNS_TEST_HOST} -> {ip}", lat)
        except socket.gaierror as e:
            last_err = f"не удалось разрешить {DNS_TEST_HOST}: {e}"
        except Exception as e:
            last_err = f"ошибка DNS: {e}"
    return CheckResult("DNS", False, last_err)


TARGET_TIMEOUT_SEC = 8
TARGET_RETRIES = 1


def check_target() -> CheckResult:
    import urllib.request
    errors = []
    for url in TARGET_URLS:
        url_err = ""
        for attempt in range(TARGET_RETRIES + 1):
            try:
                t0 = time.time()
                urllib.request.urlopen(url, timeout=TARGET_TIMEOUT_SEC)
                lat = (time.time() - t0) * 1000
                return CheckResult("Целевой сайт (HTTPS)", True, f"{url}: {lat:.0f} мс", lat)
            except Exception as e:
                url_err = f"{url}: {e}"
        errors.append(url_err)
    return CheckResult("Целевой сайт (HTTPS)", False, "; ".join(errors))


def check_claude_api() -> CheckResult:
    """Проверка реального эндпоинта Claude API, а не произвольного сайта —
    прежние обрывы фиксировались только для ya.ru/google.com, что не доказывает,
    что рвётся именно соединение чата с Anthropic."""
    import urllib.request
    for attempt in range(TARGET_RETRIES + 1):
        try:
            t0 = time.time()
            urllib.request.urlopen(CLAUDE_API_URL, timeout=TARGET_TIMEOUT_SEC)
            lat = (time.time() - t0) * 1000
            return CheckResult("Claude API (api.anthropic.com)", True, f"{lat:.0f} мс", lat)
        except urllib.error.HTTPError as e:
            # любой HTTP-ответ (даже 404/401) означает, что соединение установлено
            lat = (time.time() - t0) * 1000
            return CheckResult("Claude API (api.anthropic.com)", True, f"HTTP {e.code} (соединение есть), {lat:.0f} мс", lat)
        except Exception as e:
            last_err = str(e)
    return CheckResult("Claude API (api.anthropic.com)", False, last_err)


def check_claude_code_auth() -> CheckResult:
    """Отдельная причина обрыва: не сеть, а сбой авторизации Claude Code
    (истёкший токен, разлогин) — сеть при этом может быть полностью исправна."""
    try:
        out = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True,
                              timeout=15, shell=_IS_WIN, **_SUBPROCESS_KW)
        text = (out.stdout or "") + (out.stderr or "")
        if out.returncode != 0:
            return CheckResult("Claude Code (авторизация)", False,
                                f"команда завершилась с ошибкой (код {out.returncode}): {text.strip()[:200]}")
        import json
        try:
            data = json.loads(text)
        except Exception:
            return CheckResult("Claude Code (авторизация)", False, f"не удалось разобрать ответ: {text.strip()[:200]}")
        if data.get("loggedIn"):
            return CheckResult("Claude Code (авторизация)", True,
                                f"вход выполнен ({data.get('authMethod', '?')}, {data.get('email', '?')})")
        return CheckResult("Claude Code (авторизация)", False, "не авторизован (loggedIn=false), нужен повторный вход")
    except FileNotFoundError:
        return CheckResult("Claude Code (авторизация)", True, "claude CLI не найден — проверка пропущена")
    except subprocess.TimeoutExpired:
        return CheckResult("Claude Code (авторизация)", False, "команда claude auth status не ответила за 15с")
    except Exception as e:
        return CheckResult("Claude Code (авторизация)", False, f"ошибка проверки: {e}")


CHAIN = [check_os_adapter, check_router, check_isp, check_vpn, check_dns, check_target, check_claude_api, check_claude_code_auth]


def run_chain() -> list[CheckResult]:
    """Выполняет цепочку по порядку. Останавливается на первом обрыве (кроме VPN — он информационный)."""
    results = []
    for fn in CHAIN:
        r = fn()
        results.append(r)
        if not r.ok and r.name != "VPN":
            break
    return results


def find_break_point(results: list[CheckResult]) -> CheckResult | None:
    for r in results:
        if not r.ok:
            return r
    return None
