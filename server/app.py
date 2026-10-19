import base64
import hmac
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import analyze
import shadow

CONFIG_PATH = os.environ.get("FACTORIO_BOT_CONFIG", os.path.join(HERE, "config.json"))
HISTORY_MAX = 288


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg.setdefault("work_dir", os.path.join(HERE, "..", "data"))
    cfg.setdefault("bot_mod_dir", os.path.join(HERE, "..", "mod", shadow.MOD_NAME))
    return cfg


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


class State:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dir = cfg["work_dir"]
        os.makedirs(self.dir, exist_ok=True)
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.running = False
        self.last_error = None
        self.last_run = None
        self.last_save_mtime = None
        self.latest = self._read("latest.json")
        self.raw = self._read("raw.json")
        self.history = self._read("history.json") or []
        if self.raw:
            self.last_save_mtime = self.raw.get("_save_mtime")

    def _path(self, name):
        return os.path.join(self.dir, name)

    def _read(self, name):
        try:
            with open(self._path(name), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _write(self, name, data):
        tmp = self._path(name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        os.replace(tmp, self._path(name))

    def run_once(self, force=False):
        saves = os.path.join(self.cfg["factorio_dir"], "saves")
        mtime = os.path.getmtime(shadow.newest_save(saves))
        if not force and self.last_save_mtime and mtime <= self.last_save_mtime:
            log("Brak nowego autosave'a — pomijam")
            return False
        self.running = True
        try:
            raw, save, save_mtime = shadow.collect(self.cfg, log=log)
            raw["_save"] = os.path.basename(save)
            raw["_save_mtime"] = save_mtime
            a = analyze.analyze(raw)
            a["save"] = raw["_save"]
            a["save_time"] = save_mtime
            with self.lock:
                self.raw, self.latest = raw, a
                self.history.append(analyze.history_entry(a))
                self.history = self.history[-HISTORY_MAX:]
                self._write("raw.json", raw)
                self._write("latest.json", a)
                self._write("history.json", self.history)
            self.last_save_mtime = save_mtime
            self.last_error = None
            return True
        except Exception as e:
            self.last_error = "%s: %s" % (type(e).__name__, e)
            log("BŁĄD: " + self.last_error)
            traceback.print_exc()
            return False
        finally:
            self.running = False
            self.last_run = time.time()

    def loop(self):
        interval = int(self.cfg.get("interval_seconds", 300))
        force = False
        while True:
            try:
                self.run_once(force=force)
            except Exception as e:
                self.last_error = str(e)
                log("BŁĄD: %s" % e)
            force = self.wake.wait(interval)
            self.wake.clear()


def make_handler(state):
    cfg = state.cfg
    expected = "Basic " + base64.b64encode(
        ("%s:%s" % (cfg["username"], cfg["password"])).encode()).decode()
    static = os.path.join(HERE, "static")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _authorized(self):
            got = self.headers.get("Authorization", "")
            if hmac.compare_digest(got.encode(), expected.encode()):
                return True
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Factorio Bot"')
            self.end_headers()
            return False

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _status(self):
            return {"running": state.running, "last_run": state.last_run, "last_error": state.last_error,
                    "interval": int(cfg.get("interval_seconds", 300)),
                    "has_data": state.latest is not None}

        def do_GET(self):
            if not self._authorized():
                return
            path, _, query = self.path.partition("?")
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            if path in ("/", "/index.html"):
                with open(os.path.join(static, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if path == "/api/status":
                return self._send(200, self._status())
            if path == "/api/latest":
                with state.lock:
                    data = dict(state.latest or {})
                data["status"] = self._status()
                return self._send(200, data)
            if path == "/api/history":
                item = params.get("item")
                with state.lock:
                    hist = list(state.history)
                if item:
                    from urllib.parse import unquote
                    item = unquote(item)
                    hist = [{"t": h["t"], "v": h["items"].get(item, [0, 0])} for h in hist]
                else:
                    hist = [{"t": h["t"], "working_pct": h["working_pct"], "power": h["power"]} for h in hist]
                return self._send(200, hist)
            if path == "/api/recipes":
                with state.lock:
                    return self._send(200, (state.raw or {}).get("recipes") or {})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return
            if self.path == "/api/refresh":
                state.wake.set()
                return self._send(202, {"ok": True})
            self._send(404, {"error": "not found"})

    return Handler


def main():
    cfg = load_config()
    state = State(cfg)
    if "--once" in sys.argv:
        ok = state.run_once(force=True)
        if ok:
            s = state.latest["summary"]
            log("OK: czas gry %s, maszyn %d (%.0f%% pracuje), braków %d, deficytów %d" % (
                state.latest["game_time"], s["machines"], s["working_pct"] * 100, s["shortages"], s["deficits"]))
            for a in state.latest["alerts"][:10]:
                log(" - [%s] %s" % (a["level"], a["text"]))
        sys.exit(0 if ok else 1)

    threading.Thread(target=state.loop, daemon=True).start()
    addr = (cfg.get("listen", "0.0.0.0"), int(cfg.get("port", 8080)))
    log("Dashboard na http://%s:%d" % addr)
    ThreadingHTTPServer(addr, make_handler(state)).serve_forever()


if __name__ == "__main__":
    main()
