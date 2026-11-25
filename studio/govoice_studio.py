#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoVoice Studio — cua so desktop.

Cua so GTK + WebKitGTK (thu vien he thong, KHONG phai Electron: khong kem trinh duyet
~150 MB; app chi vai tram KB). No:
  1) bat backend (studio/server.py) trong venv cua GoVoice, voi ROS da source
  2) mo cua so tro vao backend
  3) dong cua so -> tat nhung gi app da bat (sim, LLM), dung robot

    govoice-studio                       # mo phong tren may nay
    govoice-studio --url http://192.168.123.18:8765/?token=XXXX   # noi toi CHO THAT
    govoice-studio --browser             # mo bang trinh duyet thay vi cua so

Cau hinh: ~/.config/govoice-studio/settings.json
    {"home": "~/Documents/Go2_assitant", "ros_setup": "/opt/ros/lyrical/setup.bash",
     "ws_setup": "~/ros2_ws/install/setup.bash", "port": 8765}
"""

import argparse
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.expanduser("~/.config/govoice-studio/settings.json")
DEFAULTS = {
    "home": "~/Documents/Go2_assitant",
    "ros_setup": "/opt/ros/lyrical/setup.bash",
    "ws_setup": "~/ros2_ws/install/setup.bash",
    "port": 8765,
    "width": 1480, "height": 900,
}


def settings():
    s = dict(DEFAULTS)
    try:
        with open(CONF) as f:
            s.update(json.load(f))
    except Exception:                                          # noqa: BLE001
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF, "w") as f:
            json.dump(DEFAULTS, f, indent=2)
    for k in ("home", "ros_setup", "ws_setup"):
        s[k] = os.path.expanduser(s[k])
    return s


def port_free(p):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", p)) != 0


def alive(url):
    try:
        with urllib.request.urlopen(url + "/api/info", timeout=0.5) as r:
            return r.status == 200
    except Exception:                                          # noqa: BLE001
        return False


def server_path(home):
    """Uu tien ban server di kem app (/opt/govoice-studio), sau do ban trong project."""
    for p in (os.path.join(HERE, "server.py"), os.path.join(home, "studio", "server.py")):
        if os.path.exists(p):
            return p
    return None


def start_backend(s, log):
    home = s["home"]
    py = os.path.join(home, "venv", "bin", "python")
    if not os.path.exists(py):
        py = "python3"
    if py != "python3" and subprocess.call([py, "-c", "import fastapi, uvicorn"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
        print("Lan dau: cai fastapi + uvicorn vao venv GoVoice...")
        subprocess.call([py, "-m", "pip", "install", "-q", "fastapi", "uvicorn[standard]"],
                        stdout=log, stderr=subprocess.STDOUT)
    srv = server_path(home)
    if srv is None:
        sys.exit(f"Khong thay studio/server.py (home = {home}). Sua {CONF}.")
    src = []
    for f in (s["ros_setup"], s["ws_setup"]):
        if os.path.exists(f):
            src.append(f"source {shlex.quote(f)}")
    cmd = " && ".join(src + [f"GOVOICE_HOME={shlex.quote(home)} exec {shlex.quote(py)} -u "
                             f"{shlex.quote(srv)} --port {s['port']}"])
    return subprocess.Popen(["bash", "-c", cmd], stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)


def post(url, path):
    try:
        req = urllib.request.Request(url + path, data=b"{}", method="POST",
                                     headers={"content-type": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception:                                          # noqa: BLE001
        pass


def window(url, s, on_close):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    GLib.set_prgname("govoice-studio")          # khop StartupWMClass trong .desktop
    GLib.set_application_name("GoVoice Studio")
    win = Gtk.Window(title="GoVoice Studio")
    win.set_default_size(int(s["width"]), int(s["height"]))
    icon = next((p for p in (os.path.join(HERE, "web", "icon.svg"),
                             "/usr/share/icons/hicolor/scalable/apps/govoice-studio.svg")
                 if os.path.exists(p)), None)
    if icon:
        try:
            win.set_icon_from_file(icon)
        except Exception:                                      # noqa: BLE001
            pass
    view = WebKit2.WebView()
    ws = view.get_settings()
    ws.set_enable_developer_extras(True)        # chuot phai -> Inspect (go loi giao dien)
    ws.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)
    try:
        ws.set_enable_media_stream(True)
    except Exception:                                          # noqa: BLE001
        pass
    view.set_background_color(_rgba("#0a0e13"))
    view.load_uri(url)
    win.add(view)

    def closing(*_a):
        on_close()
        Gtk.main_quit()
    win.connect("destroy", closing)
    win.show_all()
    signal.signal(signal.SIGINT, lambda *_: closing())
    GLib.timeout_add(500, lambda: True)         # de Ctrl+C trong terminal van an
    Gtk.main()


def _rgba(hexcol):
    from gi.repository import Gdk
    c = Gdk.RGBA()
    c.parse(hexcol)
    return c


def main():
    ap = argparse.ArgumentParser(description="GoVoice Studio")
    ap.add_argument("--url", help="noi toi backend co san (vd chay tren cho that)")
    ap.add_argument("--browser", action="store_true", help="mo bang trinh duyet mac dinh")
    ap.add_argument("--port", type=int)
    a = ap.parse_args()
    s = settings()
    if a.port:
        s["port"] = a.port

    if a.url:
        url, proc = a.url.rstrip("/"), None
        base = url.split("/?")[0]
    else:
        base = url = f"http://127.0.0.1:{s['port']}"
        proc = None
        if not alive(url):
            if not port_free(s["port"]):
                sys.exit(f"Cong {s['port']} dang bi chiem boi chuong trinh khac.")
            logdir = os.path.expanduser("~/.cache/govoice-studio")
            os.makedirs(logdir, exist_ok=True)
            log = open(os.path.join(logdir, "backend.log"), "ab")
            proc = start_backend(s, log)
            t0 = time.time()
            while not alive(url):
                if proc.poll() is not None or time.time() - t0 > 40:
                    sys.exit("Backend khong len. Xem ~/.cache/govoice-studio/backend.log")
                time.sleep(0.3)

    def on_close():
        if proc is not None:
            post(base, "/api/shutdown")
            try:
                os.killpg(proc.pid, signal.SIGINT)
                proc.wait(timeout=10)
            except Exception:                                  # noqa: BLE001
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:                              # noqa: BLE001
                    pass

    if a.browser:
        import webbrowser
        webbrowser.open(url)
        try:
            while proc is None or proc.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            on_close()
        return
    try:
        window(url, s, on_close)
    except (ImportError, ValueError) as e:
        print(f"Khong mo duoc cua so GTK/WebKit ({e}) -> mo trinh duyet")
        import webbrowser
        webbrowser.open(url)
        try:
            while proc is None or proc.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            on_close()


if __name__ == "__main__":
    main()
