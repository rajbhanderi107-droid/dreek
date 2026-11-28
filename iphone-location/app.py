#!/usr/bin/env python3
"""
iPhone Location Changer
-----------------------
A small local app that changes the GPS location of a USB-connected iPhone.
Everything on the phone that reads location (Maps, Find My, Weather, apps...)
then sees the location you picked, until you press "Stop" or unplug the phone.

It drives Apple's developer location simulation through `pymobiledevice3`.
Run it with:  python app.py   and open http://127.0.0.1:8765
"""

import hmac
import json
import os
import plistlib
import secrets
import socket
import re
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from math import atan2, cos, radians, sin, sqrt
from datetime import datetime, timedelta, timezone

# By default the app also listens on your Wi-Fi so you can control it from the iPhone.
# Start with --local-only to allow this computer only.
LAN = "--local-only" not in sys.argv
HOST = "0.0.0.0" if LAN else "127.0.0.1"
PORT = int(os.environ.get("PORT", "8765"))
HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
PMD = [sys.executable, "-m", "pymobiledevice3"]
STATE_FILE = os.path.join(HERE, "last_location.json")
KEY_FILE = os.path.join(HERE, "access_key.txt")


def load_key():
    """Secret that other devices (your iPhone) must present. Kept across restarts
    so the Home Screen shortcut on the iPhone keeps working."""
    try:
        with open(KEY_FILE) as f:
            k = f.read().strip()
            if len(k) >= 16:
                return k
    except OSError:
        pass
    k = secrets.token_urlsafe(18)
    with open(KEY_FILE, "w") as f:
        f.write(k)
    return k


ACCESS_KEY = load_key()


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the Wi-Fi interface
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def phone_url():
    ip = lan_ip() if LAN else None
    return f"http://{ip}:{PORT}/?key={ACCESS_KEY}" if ip else None


# --------------------------------------------------------------------------
# Helpers around the pymobiledevice3 command line
# --------------------------------------------------------------------------

def run_pmd(args, timeout=120):
    """Run a pymobiledevice3 command and return (ok, combined output)."""
    try:
        p = subprocess.run(
            PMD + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "NO_COLOR": "1"},
        )
    except subprocess.TimeoutExpired:
        return False, "Timed out waiting for the iPhone."
    except FileNotFoundError:
        return False, "pymobiledevice3 is not installed. Run: pip install -r requirements.txt"
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode == 0, out.strip()


def list_devices():
    ok, out = run_pmd(["usbmux", "list"], timeout=30)
    if not ok:
        return [], clean_error(out)
    start = out.find("[")
    try:
        data = json.loads(out[start:]) if start >= 0 else []
    except json.JSONDecodeError:
        return [], "Could not read the device list:\n" + out
    devices = []
    for d in data:
        if not isinstance(d, dict):
            continue
        devices.append({
            "udid": d.get("UniqueDeviceID") or d.get("Identifier"),
            "name": d.get("DeviceName", "iPhone"),
            "version": d.get("ProductVersion", "?"),
            "model": d.get("ProductType", ""),
            "connection": d.get("ConnectionType", ""),
        })
    return devices, None


def ios_major(version):
    m = re.match(r"(\d+)", str(version or ""))
    return int(m.group(1)) if m else 17


def clean_error(text):
    """Turn a noisy traceback/log into something a person can act on."""
    t = text or ""
    hints = []
    low = t.lower()
    if "usbmuxd" in low:
        hints.append("No connection to the iPhone service. On Windows install 'Apple Devices' "
                      "(or iTunes) from Microsoft Store; on Linux install usbmuxd.")
    if "developer mode" in low or "developermode" in low:
        hints.append("Turn on Developer Mode: iPhone Settings > Privacy & Security > Developer Mode, "
                      "then restart the phone. Use the 'Prepare iPhone' button first if the toggle is missing.")
    if "image" in low and "mount" in low:
        hints.append("Click 'Prepare iPhone' to mount the developer disk image.")
    if "pair" in low or "trust" in low:
        hints.append("Unlock the iPhone and tap 'Trust This Computer'.")
    if "no device" in low or "device not found" in low or "notconnected" in low:
        hints.append("Plug the iPhone in with a USB cable and unlock it.")
    lines = [l for l in t.splitlines() if "ERROR" in l or "Error" in l]
    summary = "\n".join(lines[-3:]) if lines else t[-600:]
    return ("\n".join(hints) + ("\n\n" if hints else "") + summary).strip()


# --------------------------------------------------------------------------
# Location session: on iOS 17+ the simulation only lasts while a connection
# stays open, so we keep one pymobiledevice3 process running per session.
# --------------------------------------------------------------------------

class Session:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.udid = None
        self.major = None
        self.mode = "idle"            # idle | fixed | route
        self.location = None          # [lat, lon]
        self.route_info = None
        self.log = []
        self.ready = threading.Event()
        self.gpx_path = None

    # ---- process management ----
    def _reader(self, proc):
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            self.log.append(line)
            self.log = self.log[-200:]
            if "Press Ctrl+C" in line or "press Enter" in line.lower():
                self.ready.set()
        self.ready.set()  # process exited

    def _kill(self):
        p = self.proc
        self.proc = None
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def _spawn(self, args, wait_ready=60):
        self.ready.clear()
        self.log = []
        proc = subprocess.Popen(
            PMD + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "NO_COLOR": "1"},
        )
        self.proc = proc
        threading.Thread(target=self._reader, args=(proc,), daemon=True).start()
        self.ready.wait(wait_ready)
        if proc.poll() is not None and proc.returncode != 0:
            self.proc = None
            raise RuntimeError(clean_error("\n".join(self.log)))
        return proc

    # ---- public actions ----
    def set_fixed(self, udid, version, lat, lon):
        with self.lock:
            self._kill()
            self.udid, self.major = udid, ios_major(version)
            coords = [f"{lat:.7f}", f"{lon:.7f}"]
            if self.major >= 17:
                self._spawn(["developer", "dvt", "simulate-location", "set", "--udid", udid, "--"] + coords)
            else:
                ok, out = run_pmd(["developer", "simulate-location", "set", "--udid", udid, "--"] + coords)
                if not ok:
                    raise RuntimeError(clean_error(out))
            self.mode, self.location, self.route_info = "fixed", [lat, lon], None
            save_last(lat, lon)

    def play_route(self, udid, version, points, speed_kmh):
        with self.lock:
            self._kill()
            self.udid, self.major = udid, ios_major(version)
            path, total_m, seconds = build_gpx(points, speed_kmh)
            self.gpx_path = path
            if self.major >= 17:
                args = ["developer", "dvt", "simulate-location", "play", "--udid", udid, path, "0"]
            else:
                args = ["developer", "simulate-location", "play", "--udid", udid, path, "0"]
            # The route starts playing straight away; don't wait for it to finish.
            self._spawn(args, wait_ready=4)
            self.mode = "route"
            self.location = list(points[-1])
            self.route_info = {
                "distance_km": round(total_m / 1000, 2),
                "minutes": round(seconds / 60, 1),
                "speed_kmh": speed_kmh,
                "started": time.time(),
                "points": points,
            }
            save_last(*points[-1])

    def stop(self):
        with self.lock:
            self._kill()
            msg = "Stopped."
            if self.udid:
                cmd = (["developer", "dvt", "simulate-location", "clear", "--udid", self.udid]
                       if (self.major or 17) >= 17 else
                       ["developer", "simulate-location", "clear", "--udid", self.udid])
                ok, out = run_pmd(cmd, timeout=60)
                msg = "Real GPS restored." if ok else "Stopped (clear reported: " + clean_error(out) + ")"
            self.mode, self.location, self.route_info = "idle", None, None
            return msg

    def status(self):
        alive = self.proc is not None and self.proc.poll() is None
        if self.mode != "idle" and (self.major or 17) >= 17 and not alive:
            # The connection dropped (cable unplugged, phone locked for long, ...)
            mode = "disconnected"
        else:
            mode = self.mode
        info = dict(self.route_info) if self.route_info else None
        if info:
            elapsed = time.time() - info["started"]
            info["progress"] = min(1.0, elapsed / max(1.0, info["minutes"] * 60))
            info["position"] = position_along(info["points"], info["progress"])
        return {"mode": mode, "location": self.location, "route": info,
                "udid": self.udid, "log": self.log[-8:]}


SESSION = Session()


# --------------------------------------------------------------------------
# Geometry / GPX
# --------------------------------------------------------------------------

def haversine(a, b):
    r = 6371000.0
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * r * atan2(sqrt(h), sqrt(1 - h))


def build_gpx(points, speed_kmh):
    """Interpolate the route to one point per second at the chosen speed."""
    speed = max(0.5, float(speed_kmh)) / 3.6  # m/s
    t0 = datetime.now(timezone.utc)
    t = 0.0
    out = [(points[0][0], points[0][1], 0.0)]
    total = 0.0
    for a, b in zip(points, points[1:]):
        d = haversine(a, b)
        total += d
        steps = max(1, int(d / speed))
        for i in range(1, steps + 1):
            f = i / steps
            t += d / speed / steps
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, t))
    rows = "\n".join(
        f'<trkpt lat="{la:.7f}" lon="{lo:.7f}"><time>'
        f'{(t0 + timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}</time></trkpt>'
        for la, lo, s in out
    )
    gpx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<gpx version="1.1" creator="iphone-location" xmlns="http://www.topografix.com/GPX/1/1">'
           f"<trk><trkseg>\n{rows}\n</trkseg></trk></gpx>")
    fd, path = tempfile.mkstemp(suffix=".gpx", prefix="route_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(gpx)
    return path, total, t


def position_along(points, progress):
    lengths = [haversine(a, b) for a, b in zip(points, points[1:])]
    target = sum(lengths) * progress
    for (a, b), d in zip(zip(points, points[1:]), lengths):
        if target <= d and d > 0:
            f = target / d
            return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
        target -= d
    return list(points[-1])


def make_pairing_file(udid):
    """Export this computer's pairing record for the iPhone, in the format the
    on-device location apps (Locus, WaypointApp, StikDebug-based apps...) import.
    Returns (bytes, warning) or (None, error)."""
    fd, tmp = tempfile.mkstemp(suffix=".plist")
    os.close(fd)
    try:
        # 1. Make sure the phone is paired (shows "Trust This Computer" if needed).
        ok, out = run_pmd(["lockdown", "save-pair-record", "--udid", udid, tmp], timeout=60)
        if not ok:
            ok2, out2 = run_pmd(["lockdown", "pair", "--udid", udid], timeout=120)
            if not ok2:
                return None, ("Could not pair. Unlock the iPhone and tap 'Trust This Computer', then try again.\n\n"
                              + clean_error(out2))
            ok, out = run_pmd(["lockdown", "save-pair-record", "--udid", udid, tmp], timeout=60)
            if not ok:
                return None, clean_error(out)
        with open(tmp, "rb") as f:
            record = plistlib.load(f)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    # 2. The phone-only apps reach the iPhone over its network interface, which
    #    needs Wi-Fi connections enabled for this pairing.
    warning = None
    ok, out = run_pmd(["lockdown", "wifi-connections", "--udid", udid, "on"], timeout=60)
    if not ok:
        warning = "Warning: could not enable Wi-Fi connections: " + clean_error(out)
    record.setdefault("UDID", udid)  # some apps look for it in the file
    return plistlib.dumps(record), warning


def save_last(lat, lon):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"lat": lat, "lon": lon}, f)
    except OSError:
        pass


def load_last():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def valid_point(p):
    try:
        lat, lon = float(p[0]), float(p[1])
    except (TypeError, ValueError, IndexError):
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return [lat, lon]
    return None


# --------------------------------------------------------------------------
# HTTP server (local only)
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def _is_local(self):
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _authorized(self):
        """This computer may always use the app; other devices need the access key."""
        if self._is_local():
            return True
        given = self.headers.get("X-Key") or ""
        return hmac.compare_digest(given.encode(), ACCESS_KEY.encode())

    def do_GET(self):
        if self.path.startswith("/api/") and not self._authorized():
            return self._json({"error": "Wrong or missing access key. Scan the QR code shown on the computer again."}, 401)
        if self.path == "/" or self.path.startswith("/index.html") or self.path.startswith("/?"):
            with open(os.path.join(STATIC, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/devices":
            devices, err = list_devices()
            self._json({"devices": devices, "error": err})
        elif self.path == "/api/info":
            self._json({"phone_url": phone_url() if self._is_local() else None})
        elif self.path == "/api/status":
            st = SESSION.status()
            st["last"] = load_last()
            self._json(st)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._authorized():
            return self._json({"error": "Wrong or missing access key. Scan the QR code shown on the computer again."}, 401)
        # Stop other websites open in this computer's browser from driving the app.
        origin = self.headers.get("Origin")
        if self._is_local() and origin and origin not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"):
            return self._json({"error": "forbidden"}, 403)
        data = self._body()
        udid = str(data.get("udid") or "")
        version = data.get("version")
        try:
            if self.path == "/api/prepare":
                if not udid:
                    return self._json({"error": "Select an iPhone first."}, 400)
                steps = []
                ok, out = run_pmd(["amfi", "developer-mode-status", "--udid", udid], timeout=60)
                dev_on = ok and "true" in out.lower()
                if not dev_on:
                    run_pmd(["amfi", "reveal-developer-mode", "--udid", udid], timeout=60)
                    steps.append("Developer Mode is OFF. On the iPhone open Settings > Privacy & Security > "
                                 "Developer Mode, switch it on and restart the phone. Then click Prepare again.")
                    return self._json({"ok": False, "message": "\n".join(steps)})
                steps.append("Developer Mode: on")
                ok, out = run_pmd(["mounter", "auto-mount", "--udid", udid], timeout=600)
                if ok or "already" in out.lower():
                    steps.append("Developer disk image: mounted")
                    return self._json({"ok": True, "message": "\n".join(steps) + "\n\nReady! Pick a place on the map."})
                return self._json({"ok": False, "message": "\n".join(steps) + "\n" + clean_error(out)})

            if self.path == "/api/pairing":
                if not udid:
                    return self._json({"error": "Select an iPhone first."}, 400)
                data_bytes, warn = make_pairing_file(udid)
                if data_bytes is None:
                    return self._json({"ok": False, "error": warn}, 500)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-plist")
                self.send_header("Content-Disposition", 'attachment; filename="pairing.plist"')
                self.send_header("Content-Length", str(len(data_bytes)))
                if warn:
                    self.send_header("X-Warning", " ".join(warn.split())[:300].encode("ascii", "ignore").decode())
                self.end_headers()
                self.wfile.write(data_bytes)
                return

            if self.path == "/api/set":
                p = valid_point([data.get("lat"), data.get("lon")])
                if not udid or not p:
                    return self._json({"error": "Select an iPhone and a valid location."}, 400)
                SESSION.set_fixed(udid, version, p[0], p[1])
                return self._json({"ok": True, "message": f"Location set to {p[0]:.6f}, {p[1]:.6f}"})

            if self.path == "/api/route":
                pts = [valid_point(p) for p in data.get("points") or []]
                pts = [p for p in pts if p]
                if not udid or len(pts) < 2:
                    return self._json({"error": "Select an iPhone and at least 2 route points."}, 400)
                speed = float(data.get("speed_kmh") or 5)
                SESSION.play_route(udid, version, pts, speed)
                return self._json({"ok": True, "message": "Moving along the route..."})

            if self.path == "/api/stop":
                return self._json({"ok": True, "message": SESSION.stop()})
        except RuntimeError as e:
            return self._json({"ok": False, "error": str(e)}, 500)
        except Exception as e:  # keep the UI informative
            return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        self._json({"error": "not found"}, 404)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"iPhone Location Changer running at {url}  (Ctrl+C to quit)")
    if phone_url():
        print("\nControl it from your iPhone (same Wi-Fi): scan the QR code in the app, or open")
        print("   " + phone_url())
        print("Keep this link private: it works like a password.\n")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nRestoring real GPS...")
        try:
            print(SESSION.stop())
        except Exception:
            pass


if __name__ == "__main__":
    main()
