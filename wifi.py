#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
from pisugar import connect_tcp, PiSugarServer
from datetime import datetime, timedelta
import json
import subprocess
import threading
import time

# ---- Paths / constants ----

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
IFACE = "wlan0"
AP_CONN_NAME = "calendar"    # NetworkManager connection name for the hotspot
PING_INTERVAL = 60           # seconds between connectivity checks
BOOT_GRACE = 20              # wait after boot before first AP decision
WIFI_RETRY_WAIT = 20         # wait after turning AP off to let Wi-Fi client come up
AP_SSID = "Calendar Setup"
PISUGAR_SOCKET = "/tmp/pisugar-server.sock"
PISUGAR_ALARM_REPEAT = 127  # 1111111 in binary: every day

# ---- Flask setup ----

app = Flask(__name__, static_folder=SCRIPT_DIR, static_url_path="")

# ---- PiSugar setup ----
try:
    conn, event_conn = connect_tcp("127.0.0.1", 8423)
    pisugar = PiSugarServer(conn, event_conn)
    print("[device] Connected to PiSugar server on 127.0.0.1:8423")
except Exception as e:
    pisugar = None
    print("[device] Failed to connect to PiSugar server:", e)

# ---- small helpers ----

def run(cmd) -> int:
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_out(cmd) -> str:
    return subprocess.check_output(cmd, text=True)


def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception as e:
            print("[device] failed to read config:", e)
            return {}
    try:
        CONFIG_PATH.write_text("{}")
    except Exception as e:
        print("[device] failed to create config file:", e)
    return {}


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


# ---- Wi-Fi helpers (NetworkManager based) ----

def wifi_scan():
    try:
        run(["nmcli", "device", "wifi", "rescan", "ifname", IFACE])
        out = run_out(["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"])
    except Exception as e:
        print("[device] wifi_scan error:", e)
        return []
    networks = []
    seen = set()
    for line in out.splitlines():
        if not line:
            continue
        parts = line.split(":")
        ssid = parts[0]
        signal = parts[1] if len(parts) > 1 else ""
        if ssid and ssid not in seen:
            seen.add(ssid)
            networks.append({"ssid": ssid, "signal": signal})
    return networks


def check_internet() -> bool:
    try:
        out = run_out(["nmcli", "networking", "connectivity", "check"]).strip()
        return out == "full"
    except:
        return False


def in_ap_mode() -> bool:
    try:
        out = run_out([
            "nmcli", "-t", "-f", "NAME,TYPE,DEVICE",
            "connection", "show", "--active"
        ])
    except subprocess.CalledProcessError:
        return False

    for line in out.splitlines():
        if not line:
            continue
        name, ctype, dev = (line.split(":") + ["", "", ""])[:3]
        if name == AP_CONN_NAME and dev == IFACE:
            return True
    return False


def ap_has_clients() -> bool:
    try:
        out = run_out(["iw", "dev", IFACE, "station", "dump"])
    except subprocess.CalledProcessError:
        return False
    return "Station " in out


def ap_connection_exists(name) -> bool:
    try:
        out = run_out(["nmcli", "-t", "-f", "NAME", "connection", "show"])
    except Exception as e:
        print("[device] ap_connection_exists error:", e)
        return False
    for line in out.splitlines():
        if line.strip() == name:
            return True
    return False


def ensure_ap_connection():
    if ap_connection_exists(AP_CONN_NAME):
        return
    print(f"[device] creating OPEN AP connection {AP_CONN_NAME!r}")
    rc = run([
        "nmcli", "connection", "add",
        "type", "wifi",
        "ifname", IFACE,
        "con-name", AP_CONN_NAME,
        "autoconnect", "no",
        "wifi.mode", "ap",
        "wifi.ssid", AP_SSID,
        "ipv4.method", "shared",
    ])
    print("[device] nmcli con add exit code", rc)


def start_ap():
    print("[device] starting AP", AP_CONN_NAME)
    ensure_ap_connection()
    rc = run(["nmcli", "connection", "up", AP_CONN_NAME])
    print("[device] start_ap: nmcli exit code", rc)


def stop_ap():
    print("[device] stopping AP (config-ap)")
    run(["nmcli", "connection", "down", AP_CONN_NAME])
    print(f"[device] waiting {WIFI_RETRY_WAIT} s for wifi client to come up")
    time.sleep(WIFI_RETRY_WAIT)


def schedule_wakeup_24h(hour: int, minute: int):
    if pisugar is None:
        raise RuntimeError("PiSugar server not connected")
    now = datetime.now().astimezone()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    repeat_mask = 127  # every day
    print(f"[device] Scheduling wake-up at {target.isoformat()} repeat={repeat_mask}")
    pisugar.set_battery_auto_power_on(False)
    pisugar.rtc_alarm_set(target, repeat_mask)
    pisugar.set_battery_auto_power_on(True)
    return target


# ---- Flask routes ----

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(load_config())

@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.get_json(force=True)
    save_config(data)
    return jsonify({"status": "ok"})

@app.route("/api/wifi/networks", methods=["GET"])
def list_networks():
    return jsonify(wifi_scan())

@app.route("/api/wifi/set", methods=["POST"])
def set_wifi():
    payload = request.get_json(force=True)
    ssid = payload.get("ssid", "").strip()
    psk = payload.get("password", "").strip()
    if not ssid or not psk:
        return jsonify({"status": "error", "message": "SSID and password required"}), 400
    if in_ap_mode():
        print("[device] set_wifi: bringing AP down to connect client Wi-Fi")
        run(["nmcli", "connection", "down", AP_CONN_NAME])
        time.sleep(2)
    if ap_connection_exists(ssid):
        cmd = ["nmcli", "connection", "up", ssid]
    else:
        cmd = ["nmcli", "device", "wifi", "connect", ssid, "password", psk, "ifname", IFACE]
    print("[device] set_wifi: running:", " ".join(cmd))
    result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
    print("[device] set_wifi: nmcli exit code", result.stderr)
    if result.returncode != 0:
        return jsonify({
            "status": "error",
            "message": result.stderr
        }), 500
    return jsonify({"status": "ok", "message": "Wi-Fi connected successfully."})

@app.route("/api/update", methods=["POST"])
def update_software():
    """
    Run `git pull` in the directory where this script lives.
    Assumes this directory is the root of the git repo.
    """
    try:
        # 1) Ensure this repo is marked safe for the user running the service
        subprocess.run(
            ["sudo", "git", "config", "--global", "--add", "safe.directory", str(SCRIPT_DIR)],
            capture_output=True,
            text=True
        )
        # 2) Run git pull with no timeout
        result = subprocess.run(
            ["git", "-C", str(SCRIPT_DIR), "pull"],
            capture_output=True,
            text=True
        )
    except Exception as e:
        print("[device] update_software error:", e)
        return jsonify({
            "status": "error",
            "message": f"Update failed: {e}"
        }), 500

    if result.returncode != 0:
        print("[device] git pull stderr:", result.stderr)
        return jsonify({
            "status": "error",
            "message": (result.stderr or "git pull failed").strip()
        }), 500

    stdout = (result.stdout or "").strip()
    msg = stdout if stdout else "Already up to date."
    print("[device] git pull stdout:", stdout)

    return jsonify({
        "status": "ok",
        "message": msg
    })

@app.route("/api/wakeup", methods=["POST"])
def api_wakeup():
    payload = request.get_json(force=True) or {}
    try:
        hour = int(payload.get("hour", -1))
        minute = int(payload.get("minute", -1))
    except Exception:
        return jsonify({"status": "error", "message": "Invalid hour/minute"}), 400

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return jsonify({
            "status": "error",
            "message": "Hour must be 0–23 and minute 0–59"
        }), 400

    try:
        next_alarm = schedule_wakeup_24h(hour, minute)
    except Exception as e:
        print("[device] wakeup error:", e)
        return jsonify({"status": "error", "message": f"PiSugar error: {e}"}), 500

    # Convert back to 12-hour format for friendly message
    hour12 = ((hour + 11) % 12) + 1
    ampm = "AM" if hour < 12 else "PM"
    friendly = f"{hour12:02d}:{minute:02d} {ampm}"

    return jsonify({
        "status": "ok",
        "message": f"Wake up scheduled for {friendly}."
    })

@app.route("/api/battery", methods=["GET"])
def api_battery():
    """
    Return basic battery status for the UI.

    {
      "level": 83.5,
      "charging": true,
      "plugged": true,
      "model": "PiSugar 3",
      "temperature": 31.2
    }
    """
    # If PiSugar isn’t connected, fail gracefully
    if pisugar is None:
        return jsonify({
            "status": "error",
            "message": "PiSugar not connected"
        }), 503

    try:
        level = pisugar.get_battery_level()             # %
        charging = pisugar.get_battery_charging()       # bool
        plugged = pisugar.get_battery_power_plugged()   # bool
        model = pisugar.get_model()                     # string
        try:
            temp = pisugar.get_temperature()
        except Exception:
            temp = None

        return jsonify({
            "status": "ok",
            "level": level,
            "charging": charging,
            "plugged": plugged,
            "model": model,
            "temperature": temp
        })
    except Exception as e:
        print("[device] api_battery error:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ---- Connectivity loop ----

def connectivity_loop():
    """
    Background loop:
      - if online: keep AP off
      - if offline: bring AP up
      - if offline + AP up with no clients: briefly stop AP and let NM try client Wi-Fi again
    """
    print("[device] connectivity loop starting, grace", BOOT_GRACE, "s")
    time.sleep(BOOT_GRACE)

    while True:
        online = check_internet()
        ap_mode = in_ap_mode()

        if online:
            if ap_mode:
                print("[device] internet up; turning AP off")
                stop_ap()
            else:
                print("[device] online in wifi-client mode")
        else:
            print("[device] offline")
            if not ap_mode:
                print("[device] no internet in wifi-client; bringing up AP")
                start_ap()
            else:
                # already in AP mode
                if not ap_has_clients():
                    print("[device] AP has no clients; try wifi-client again")
                    stop_ap()
                    if not check_internet():
                        print("[device] still offline; back to AP")
                        start_ap()
                    else:
                        print("[device] wifi-client back online")
                else:
                    print("[device] AP has clients; staying in AP mode")

        time.sleep(PING_INTERVAL)

def run_flask():
    # no debug/reloader under systemd
    app.run(host="0.0.0.0", port=80, debug=False, use_reloader=False)

def main():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    connectivity_loop()

if __name__ == "__main__":
    main()
