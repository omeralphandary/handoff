"""Reolink HTTP API — camera imaging, IR and white LED control."""
from __future__ import annotations
import logging
import time
from urllib.parse import urlparse
import httpx

log = logging.getLogger(__name__)
_BASE_TIMEOUT = 5.0

# Token cache: host -> (token, expires_at)
_token_cache: dict[str, tuple[str, float]] = {}


def _parse_camera(rtsp_url: str) -> tuple[str, str, str]:
    p = urlparse(rtsp_url)
    return p.hostname, p.username or "admin", p.password or ""


def _base(host: str) -> str:
    return f"http://{host}/api.cgi"


def _login(host: str, user: str, pw: str) -> str | None:
    cached = _token_cache.get(host)
    if cached and time.time() < cached[1]:
        return cached[0]
    payload = [{"cmd": "Login", "action": 0, "param": {
        "User": {"Version": "0", "userName": user, "password": pw}
    }}]
    def _do_login() -> dict:
        r = httpx.post(f"{_base(host)}?cmd=Login", json=payload, timeout=_BASE_TIMEOUT)
        return r.json()[0]

    try:
        data = _do_login()
        if data.get("code") != 0:
            detail = data.get("error", {}).get("detail", "unknown")
            if detail == "max session":
                log.warning("[reolink] max session — attempting logout to free a slot")
                _logout_all(host)
                data = _do_login()
            if data.get("code") != 0:
                log.error("[reolink] login rejected: %s", data.get("error", {}).get("detail", detail))
                return None
        token = data["value"]["Token"]["name"]
        lease = data["value"]["Token"].get("leaseTime", 3600)
        _token_cache[host] = (token, time.time() + lease - 30)
        log.info("[reolink] logged in, token valid for %ds", lease)
        return token
    except Exception as e:
        log.error("[reolink] login failed: %s", e)
        return None


def _logout_all(host: str) -> None:
    """Best-effort logout of any cached token to free a camera session slot."""
    cached = _token_cache.pop(host, None)
    if cached:
        try:
            httpx.post(f"{_base(host)}?cmd=Logout&token={cached[0]}",
                       json=[{"cmd": "Logout", "action": 0, "param": {}}],
                       timeout=_BASE_TIMEOUT)
            log.info("[reolink] logged out existing session")
        except Exception:
            pass


def get_camera_settings(rtsp_url: str) -> dict | None:
    host, user, pw = _parse_camera(rtsp_url)
    token = _login(host, user, pw)
    if not token:
        return None
    cmds = ["GetImage", "GetIsp", "GetIrLights", "GetWhiteLed"]
    payload = [{"cmd": c, "action": 0, "param": {"channel": 0}} for c in cmds]
    try:
        r = httpx.post(f"{_base(host)}?token={token}", json=payload, timeout=_BASE_TIMEOUT)
        results = {item["cmd"]: item.get("value", {}) for item in r.json() if item.get("code") == 0}
        img = results.get("GetImage", {}).get("Image", {})
        isp = results.get("GetIsp", {}).get("Isp", {})
        ir  = results.get("GetIrLights", {}).get("IrLights", {})
        led = results.get("GetWhiteLed", {}).get("WhiteLed", {})
        return {
            "brightness":  img.get("bright", 128),
            "contrast":    img.get("contrast", 128),
            "hue":         img.get("hue", 128),
            "saturation":  img.get("saturation", 128),
            "sharpness":   img.get("sharpen", 128),
            "day_night":   isp.get("dayNight", "Auto"),
            "white_balance": isp.get("whiteBalance", "Auto"),
            "backlight":   isp.get("backLight", "Off"),
            "ir_state":    ir.get("state", "Auto"),
            "led_state":   led.get("state", 0),
            "led_bright":  led.get("bright", 50),
        }
    except Exception as e:
        log.error("[reolink] get settings failed: %s", e)
        return None


def set_image(rtsp_url: str, brightness: int, contrast: int,
              hue: int, saturation: int, sharpness: int) -> bool:
    host, user, pw = _parse_camera(rtsp_url)
    token = _login(host, user, pw)
    if not token:
        return False
    payload = [{"cmd": "SetImage", "action": 0, "param": {"Image": {
        "channel": 0,
        "bright": brightness, "contrast": contrast, "hue": hue,
        "saturation": saturation, "sharpen": sharpness,
    }}}]
    try:
        r = httpx.post(f"{_base(host)}?cmd=SetImage&token={token}", json=payload, timeout=_BASE_TIMEOUT)
        r.raise_for_status()
        log.info("[reolink] image settings updated")
        return True
    except Exception as e:
        log.error("[reolink] set image failed: %s", e)
        return False


def set_ir(rtsp_url: str, state: str) -> bool:
    """state: 'Auto' | 'On' | 'Off'"""
    host, user, pw = _parse_camera(rtsp_url)
    token = _login(host, user, pw)
    if not token:
        return False
    payload = [{"cmd": "SetIrLights", "action": 0, "param": {
        "IrLights": {"channel": 0, "state": state}
    }}]
    try:
        r = httpx.post(f"{_base(host)}?cmd=SetIrLights&token={token}", json=payload, timeout=_BASE_TIMEOUT)
        r.raise_for_status()
        log.info("[reolink] IR set to %s", state)
        return True
    except Exception as e:
        log.error("[reolink] set IR failed: %s", e)
        return False


def set_white_led(rtsp_url: str, state: int, bright: int) -> bool:
    """state: 0=off, 1=on. bright: 0-100."""
    host, user, pw = _parse_camera(rtsp_url)
    token = _login(host, user, pw)
    if not token:
        return False
    payload = [{"cmd": "SetWhiteLed", "action": 0, "param": {"WhiteLed": {
        "channel": 0, "state": state, "bright": bright, "mode": 1 if state else 0,
        "LightingSchedule": {"StartHour": 0, "StartMin": 0, "EndHour": 23, "EndMin": 59},
    }}}]
    try:
        r = httpx.post(f"{_base(host)}?cmd=SetWhiteLed&token={token}", json=payload, timeout=_BASE_TIMEOUT)
        r.raise_for_status()
        log.info("[reolink] white LED state=%s bright=%s", state, bright)
        return True
    except Exception as e:
        log.error("[reolink] set white LED failed: %s", e)
        return False
