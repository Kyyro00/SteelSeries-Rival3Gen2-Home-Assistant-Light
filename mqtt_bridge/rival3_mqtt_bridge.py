import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import paho.mqtt.client as mqtt

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
CORE_PROPS_PATH = (
    Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    / "SteelSeries"
    / "SteelSeries Engine 3"
    / "coreProps.json"
)
USB_HARDWARE_ID = "VID_1038&PID_1870"

DEVICE_ID = "steelseries_rival3_gen2"
AVAILABILITY_TOPIC = "rival3/availability"

GAMESENSE_STATE_TOPIC = "rival3/light/state"
GAMESENSE_CMD_TOPIC = "rival3/light/set"

POLLING_RATES = ["125", "250", "500", "1000"]

RAINBOW_OPTIONS = {
    "Desactivado (color fijo)": None,
    "Todo el ratón": "all",
    "Zona inferior": "bottom",
    "Zona central": "middle",
    "Zona superior": "top",
    "Inferior y central": "bottom-middle",
    "Central y superior": "middle-top",
    "Inferior y superior": "bottom-top",
}

DEFAULT_LIGHTING_OPTIONS = {
    "Arcoíris": "rainbow",
    "Apagada": "off",
    "Reactiva al clic": "reactive",
    "Arcoíris + Reactiva": "reactive-rainbow",
}

DPI_BUTTON_OPTIONS = {
    "Cambiar DPI (por defecto)": "buttons(button6=dpi)",
    "Desactivado": "buttons(button6=disable)",
    "Clic central": "buttons(button6=button3)",
}

FACTORY_DEFAULTS = {
    "dpi": 800,
    "polling_rate": "1000",
    "led_brightness": 100,
    "rainbow_effect": "Todo el ratón",
    "default_lighting": "Arcoíris",
    "dpi_button": "Cambiar DPI (por defecto)",
    "z1": {"state": "ON", "color": {"r": 255, "g": 0, "b": 0}},
    "z2": {"state": "ON", "color": {"r": 0, "g": 255, "b": 0}},
    "z3": {"state": "ON", "color": {"r": 0, "g": 0, "b": 255}},
    "reactive": {"state": "OFF", "color": {"r": 255, "g": 255, "b": 255}},
}


def acquire_single_instance_mutex() -> object | None:
    """Evita que haya múltiples instancias del puente corriendo a la vez en Windows."""
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "Local\\Rival3HAMQTTBridgeMutex")
    if not mutex:
        return None
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(mutex)
        return None
    return mutex


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"No se encontró {CONFIG_PATH}.")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_saved_state() -> dict:
    state = json.loads(json.dumps(FACTORY_DEFAULTS))
    if STATE_PATH.exists():
        try:
            saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            for k, v in saved.items():
                if k in state:
                    state[k] = v
        except Exception:
            pass
    return state


def save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def is_mouse_connected() -> bool:
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"(Get-CimInstance Win32_PnPEntity -Filter \"DeviceID LIKE '%{USB_HARDWARE_ID}%' AND Status = 'OK'\" -ErrorAction SilentlyContinue | Select-Object -First 1) -ne $null",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        return res.stdout.strip().lower() == "true"
    except Exception:
        return False


def get_gamesense_url() -> str | None:
    if not CORE_PROPS_PATH.exists():
        return None
    try:
        data = json.loads(CORE_PROPS_PATH.read_text(encoding="utf-8"))
        addr = data.get("address")
        return f"http://{addr}" if addr else None
    except Exception:
        return None


def post_json(url: str, payload: dict, timeout: float = 2.0) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout):
        pass


def ensure_gamesense_registered() -> None:
    url = get_gamesense_url()
    if not url:
        return
    meta = {
        "game": "HOMEASSISTANT",
        "game_display_name": "Home Assistant",
        "icon_color_id": 5,
        "deinitialize_timer_length_ms": 86400000,
    }
    bind = {
        "game": "HOMEASSISTANT",
        "event": "SET_COLOR",
        "handlers": [
            {"device-type": "mouse", "zone": "logo", "mode": "context-color", "context-frame-key": "base_color"},
            {"device-type": "mouse", "zone": "base", "mode": "context-color", "context-frame-key": "base_color"},
            {"device-type": "rgb-3-zone", "zone": "one", "mode": "context-color", "context-frame-key": "base_color"},
            {"device-type": "rgb-3-zone", "zone": "two", "mode": "context-color", "context-frame-key": "base_color"},
            {"device-type": "rgb-3-zone", "zone": "three", "mode": "context-color", "context-frame-key": "base_color"},
        ],
    }
    try:
        post_json(f"{url}/game_metadata", meta)
        post_json(f"{url}/bind_game_event", bind)
    except Exception:
        pass


def send_gamesense_color(r: int, g: int, b: int) -> None:
    url = get_gamesense_url()
    if not url:
        return
    event_data = {
        "game": "HOMEASSISTANT",
        "event": "SET_COLOR",
        "data": {
            "frame": {
                "base_color": {
                    "red": max(0, min(255, int(r))),
                    "green": max(0, min(255, int(g))),
                    "blue": max(0, min(255, int(b))),
                }
            }
        },
    }
    try:
        post_json(f"{url}/game_event", event_data)
    except Exception:
        pass


def run_rivalcfg(*args: str) -> bool:
    """Ejecuta rivalcfg con los argumentos indicados."""
    cmd = [sys.executable, "-m", "rivalcfg", *args]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        if res.returncode != 0:
            print(f"[rivalcfg ERROR] {' '.join(args)} -> {res.stderr.strip()}")
            return False
        return True
    except Exception as exc:
        print(f"[rivalcfg EXCEPTION] {exc}")
        return False


def rgb_to_hex(color: dict) -> str:
    return f"#{int(color['r']):02x}{int(color['g']):02x}{int(color['b']):02x}"


class Rival3Bridge:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.running = True

        self.gs_on = False
        self.gs_brightness = 255
        self.gs_color = {"r": 255, "g": 255, "b": 255}

        self.hw = load_saved_state()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="steelseries_rival3_gen2_bridge")
        username = cfg.get("mqtt_user", "")
        password = cfg.get("mqtt_password", "")
        if username:
            self.client.username_pw_set(username, password)

        self.client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def device_info(self) -> dict:
        return {
            "identifiers": [DEVICE_ID],
            "name": "SteelSeries Rival 3 Gen 2",
            "manufacturer": "SteelSeries",
            "model": "Rival 3 Gen 2",
        }

    def base_entity(self, object_id: str, name: str, category: str | None = None) -> dict:
        payload = {
            "name": name,
            "unique_id": f"{DEVICE_ID}_{object_id}",
            "availability_topic": AVAILABILITY_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": self.device_info(),
        }
        if category:
            payload["entity_category"] = category
        return payload

    def publish_discovery_all(self) -> None:
        # Limpiar entidades antiguas si existieran
        for old_topic in (
            f"homeassistant/light/{DEVICE_ID}/config",
            f"homeassistant/text/{DEVICE_ID}_sensitivity/config",
            f"homeassistant/text/{DEVICE_ID}_buttons/config",
        ):
            self.client.publish(old_topic, "", qos=1, retain=True)

        entities: list[tuple[str, dict]] = []

        # Control principal en vivo
        gs_light = self.base_entity("base_light", "Luz RGB")
        gs_light.update({
            "schema": "json",
            "state_topic": GAMESENSE_STATE_TOPIC,
            "command_topic": GAMESENSE_CMD_TOPIC,
            "supported_color_modes": ["rgb"],
            "brightness": True,
            "brightness_scale": 255,
            "optimistic": False,
        })
        entities.append((f"homeassistant/light/{DEVICE_ID}_base/config", gs_light))

        # Zonas individuales y reactiva en memoria
        for key, label in [
            ("z1", "Zona superior"),
            ("z2", "Zona central"),
            ("z3", "Zona inferior"),
            ("reactive", "Luz al hacer clic"),
        ]:
            ent = self.base_entity(key, label, "config")
            ent.update({
                "schema": "json",
                "state_topic": f"rival3/hw/{key}/state",
                "command_topic": f"rival3/hw/{key}/set",
                "supported_color_modes": ["rgb"],
                "optimistic": False,
            })
            entities.append((f"homeassistant/light/{DEVICE_ID}_{key}/config", ent))

        # Sliders: Brillo LED y DPI
        bri = self.base_entity("led_brightness", "Brillo LED", "config")
        bri.update({
            "state_topic": "rival3/hw/led_brightness/state",
            "command_topic": "rival3/hw/led_brightness/set",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
        })
        entities.append((f"homeassistant/number/{DEVICE_ID}_led_brightness/config", bri))

        dpi = self.base_entity("dpi", "Sensibilidad (DPI)", "config")
        dpi.update({
            "state_topic": "rival3/hw/dpi/state",
            "command_topic": "rival3/hw/dpi/set",
            "min": 200,
            "max": 8500,
            "step": 100,
            "unit_of_measurement": "DPI",
            "icon": "mdi:mouse-move-vertical",
        })
        entities.append((f"homeassistant/number/{DEVICE_ID}_dpi/config", dpi))

        # Selectores amigables
        for key, label, options, icon in [
            ("polling_rate", "Frecuencia (Hz)", POLLING_RATES, "mdi:speedometer"),
            ("rainbow_effect", "Efecto arcoíris", list(RAINBOW_OPTIONS.keys()), "mdi:looks"),
            ("default_lighting", "Luz al encender", list(DEFAULT_LIGHTING_OPTIONS.keys()), "mdi:lightbulb-auto"),
            ("dpi_button", "Botón superior", list(DPI_BUTTON_OPTIONS.keys()), "mdi:mouse"),
        ]:
            sel = self.base_entity(key, label, "config")
            sel.update({
                "state_topic": f"rival3/hw/{key}/state",
                "command_topic": f"rival3/hw/{key}/set",
                "options": options,
                "icon": icon,
            })
            entities.append((f"homeassistant/select/{DEVICE_ID}_{key}/config", sel))

        # Botón de reseteo
        rst = self.base_entity("reset", "Restablecer de fábrica", "config")
        rst.update({
            "command_topic": "rival3/hw/reset/set",
            "payload_press": "PRESS",
            "icon": "mdi:restore",
        })
        entities.append((f"homeassistant/button/{DEVICE_ID}_reset/config", rst))

        for topic, payload in entities:
            self.client.publish(topic, json.dumps(payload), qos=1, retain=True)

    def publish_all_states(self) -> None:
        self.publish_gamesense_state()
        for key in ("z1", "z2", "z3", "reactive"):
            z = self.hw[key]
            payload = {"state": z["state"], "color_mode": "rgb", "color": z["color"]}
            self.client.publish(f"rival3/hw/{key}/state", json.dumps(payload), qos=1, retain=True)

        for key in ("led_brightness", "dpi", "polling_rate", "rainbow_effect", "default_lighting", "dpi_button"):
            self.client.publish(f"rival3/hw/{key}/state", str(self.hw[key]), qos=1, retain=True)

    def publish_gamesense_state(self) -> None:
        payload = {
            "state": "ON" if self.gs_on else "OFF",
            "brightness": self.gs_brightness,
            "color_mode": "rgb",
            "color": self.gs_color,
        }
        self.client.publish(GAMESENSE_STATE_TOPIC, json.dumps(payload), qos=1, retain=True)

    def effective_gamesense_rgb(self) -> tuple[int, int, int]:
        if not self.gs_on:
            return 0, 0, 0
        scale = self.gs_brightness / 255.0
        return (
            round(self.gs_color["r"] * scale),
            round(self.gs_color["g"] * scale),
            round(self.gs_color["b"] * scale),
        )

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("[OK] Conectado al broker MQTT")
            self.publish_discovery_all()
            client.publish(AVAILABILITY_TOPIC, payload="online", qos=1, retain=True)
            client.subscribe(GAMESENSE_CMD_TOPIC, qos=1)
            client.subscribe("rival3/hw/+/set", qos=1)
            self.publish_all_states()
        else:
            print(f"[ERROR] Fallo al conectar a MQTT: {reason_code}")

    def handle_gamesense_cmd(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except Exception:
            return
        with self.lock:
            if "state" in data:
                self.gs_on = str(data["state"]).upper() == "ON"
            if "brightness" in data:
                self.gs_brightness = max(0, min(255, int(data["brightness"])))
            if "color" in data and isinstance(data["color"], dict):
                c = data["color"]
                self.gs_color = {
                    "r": max(0, min(255, int(c.get("r", self.gs_color["r"])))),
                    "g": max(0, min(255, int(c.get("g", self.gs_color["g"])))),
                    "b": max(0, min(255, int(c.get("b", self.gs_color["b"])))),
                }
            r, g, b = self.effective_gamesense_rgb()

        send_gamesense_color(r, g, b)
        self.publish_gamesense_state()

    def handle_hw_cmd(self, key: str, raw: str) -> None:
        if key == "reset":
            if run_rivalcfg("-r"):
                self.hw = json.loads(json.dumps(FACTORY_DEFAULTS))
                save_state(self.hw)
                self.publish_all_states()
            return

        if key in ("z1", "z2", "z3", "reactive"):
            try:
                data = json.loads(raw)
            except Exception:
                return
            entry = self.hw[key]
            if "state" in data:
                entry["state"] = "ON" if str(data["state"]).upper() == "ON" else "OFF"
            if "color" in data and isinstance(data["color"], dict):
                c = data["color"]
                entry["color"] = {
                    "r": max(0, min(255, int(c.get("r", entry["color"]["r"])))),
                    "g": max(0, min(255, int(c.get("g", entry["color"]["g"])))),
                    "b": max(0, min(255, int(c.get("b", entry["color"]["b"])))),
                }
            flag = {"z1": "--z1", "z2": "--z2", "z3": "--z3", "reactive": "-a"}[key]
            val = ("off" if key == "reactive" else "black") if entry["state"] == "OFF" else rgb_to_hex(entry["color"])
            if run_rivalcfg(flag, val):
                save_state(self.hw)
                self.client.publish(
                    f"rival3/hw/{key}/state",
                    json.dumps({"state": entry["state"], "color_mode": "rgb", "color": entry["color"]}),
                    qos=1,
                    retain=True,
                )
            return

        if key == "led_brightness":
            val = max(0, min(100, int(float(raw))))
            if run_rivalcfg("-l", str(val)):
                self.hw["led_brightness"] = val
                save_state(self.hw)
                self.client.publish("rival3/hw/led_brightness/state", str(val), qos=1, retain=True)
            return

        if key == "dpi":
            val = max(200, min(8500, int(round(float(raw) / 100.0) * 100)))
            if run_rivalcfg("-s", str(val)):
                self.hw["dpi"] = val
                save_state(self.hw)
                self.client.publish("rival3/hw/dpi/state", str(val), qos=1, retain=True)
            return

        if key == "rainbow_effect" and raw == "Desactivado (color fijo)":
            z_args = []
            for z_key, z_flag in (("z1", "--z1"), ("z2", "--z2"), ("z3", "--z3")):
                z_entry = self.hw[z_key]
                z_val = "black" if z_entry["state"] == "OFF" else rgb_to_hex(z_entry["color"])
                z_args.extend([z_flag, z_val])
            if run_rivalcfg(*z_args):
                self.hw["rainbow_effect"] = raw
                save_state(self.hw)
                self.client.publish("rival3/hw/rainbow_effect/state", raw, qos=1, retain=True)
            return

        select_map = {
            "polling_rate": ("-p", {v: v for v in POLLING_RATES}),
            "rainbow_effect": ("-e", RAINBOW_OPTIONS),
            "default_lighting": ("-d", DEFAULT_LIGHTING_OPTIONS),
            "dpi_button": ("-b", DPI_BUTTON_OPTIONS),
        }
        if key in select_map and raw in select_map[key][1]:
            flag, mapping = select_map[key]
            if run_rivalcfg(flag, mapping[raw]):
                self.hw[key] = raw
                save_state(self.hw)
                self.client.publish(f"rival3/hw/{key}/state", raw, qos=1, retain=True)

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="ignore")
        if msg.topic == GAMESENSE_CMD_TOPIC:
            self.handle_gamesense_cmd(payload)
        elif msg.topic.startswith("rival3/hw/") and msg.topic.endswith("/set"):
            key = msg.topic.split("/")[2]
            self.handle_hw_cmd(key, payload)

    def heartbeat_loop(self) -> None:
        while self.running:
            time.sleep(1.5)
            with self.lock:
                active = self.gs_on
                r, g, b = self.effective_gamesense_rgb()
            if not active:
                continue
            url = get_gamesense_url()
            if not url:
                continue
            try:
                post_json(f"{url}/game_heartbeat", {"game": "HOMEASSISTANT"}, timeout=1.0)
                send_gamesense_color(r, g, b)
            except Exception:
                pass

    def run(self) -> None:
        hb = threading.Thread(target=self.heartbeat_loop, daemon=True)
        hb.start()

        host = self.cfg.get("mqtt_host", "127.0.0.1")
        port = int(self.cfg.get("mqtt_port", 1883))
        self.client.connect(host, port, keepalive=60)
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self.client.publish(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)
            self.client.disconnect()


def main() -> int:
    mutex = acquire_single_instance_mutex()
    if not mutex:
        print("Ya hay una instancia del puente en ejecución. Saliendo...")
        return 0

    connected = False
    for _ in range(6):
        if is_mouse_connected():
            connected = True
            break
        time.sleep(5)

    if not connected:
        print("SteelSeries Rival 3 Gen 2 no detectado. Saliendo...")
        return 0

    for _ in range(30):
        if get_gamesense_url():
            break
        time.sleep(2)

    ensure_gamesense_registered()
    cfg = load_config()
    bridge = Rival3Bridge(cfg)
    bridge.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
