import base64
import gzip
import hashlib
import hmac
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import analyze
import shadow

CONFIG_PATH = os.environ.get("FACTORIO_BOT_CONFIG", os.path.join(HERE, "config.json"))
STATIC = os.path.join(HERE, "static")
HISTORY_MAX = 288
TEXT_TYPES = ("text/", "application/json", "application/javascript", "image/svg+xml", "application/manifest+json")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/manifest+json", ".webmanifest")


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg.setdefault("work_dir", os.path.join(HERE, "..", "data"))
    cfg.setdefault("bot_mod_dir", os.path.join(HERE, "..", "mod", shadow.MOD_NAME))
    return cfg


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


class Blob:
    def __init__(self, data):
        self.raw = data if isinstance(data, bytes) else json.dumps(
            data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.gz = gzip.compress(self.raw, 6)
        self.etag = '"%s"' % hashlib.sha1(self.raw).hexdigest()[:16]


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
        self.blobs = {}
        for f in os.listdir(self.dir):
            if f.endswith(".tmp"):
                os.remove(self._path(f))
        self._rebuild_blobs(self._read_bytes("map.json"))
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

    def _read_bytes(self, name):
        try:
            with open(self._path(name), "rb") as fh:
                return fh.read()
        except OSError:
            return None

    def _write(self, name, data):
        tmp = self._path(name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        os.replace(tmp, self._path(name))

    def _rebuild_blobs(self, map_bytes=None):
        blobs = dict(self.blobs)
        if self.latest:
            blobs["latest"] = Blob(self.latest)
        if self.raw:
            blobs["recipes"] = Blob(self.raw.get("recipes") or {})
        blobs["history"] = Blob([{"t": h["t"], "working_pct": h["working_pct"], "power": h["power"]}
                                 for h in self.history])
        if map_bytes:
            blobs["map"] = Blob(map_bytes)
        self.blobs = blobs

    def run_once(self, force=False):
        saves = os.path.join(self.cfg["factorio_dir"], "saves")
        try:
            if shadow.request_save(self.cfg, log=log):
                force = True
        except Exception as e:
            log("Nie udało się wymusić zapisu przez RCON: %s" % e)
        mtime = os.path.getmtime(shadow.newest_save(saves))
        if not force and self.last_save_mtime and mtime <= self.last_save_mtime:
            log("Brak nowego autosave'a — pomijam")
            return False
        self.running = True
        try:
            raw, game_map, save, save_mtime = shadow.collect(self.cfg, log=log)
            raw["_save"] = os.path.basename(save)
            raw["_save_mtime"] = save_mtime
            a = analyze.analyze(raw)
            a["save"] = raw["_save"]
            a["save_time"] = save_mtime
            payload = analyze.map_payload(raw, game_map, a)
            map_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            with self.lock:
                self.raw, self.latest = raw, a
                self.history.append(analyze.history_entry(a))
                self.history = self.history[-HISTORY_MAX:]
                self._write("raw.json", raw)
                self._write("latest.json", a)
                self._write("history.json", self.history)
                with open(self._path("map.json"), "wb") as fh:
                    fh.write(map_bytes)
                self._rebuild_blobs(map_bytes)
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
    static_cache = {}

    def static_blob(rel):
        full = os.path.realpath(os.path.join(STATIC, rel))
        if not full.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(full):
            return None, None
        mtime = os.path.getmtime(full)
        hit = static_cache.get(full)
        if not hit or hit[0] != mtime:
            with open(full, "rb") as fh:
                hit = (mtime, Blob(fh.read()))
            static_cache[full] = hit
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        return hit[1], ctype

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _authorized(self):
            got = self.headers.get("Authorization", "")
            if hmac.compare_digest(got.encode(), expected.encode()):
                return True
            body = b"Unauthorized"
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Factorio Dashboard", charset="UTF-8"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return False

        def _send_blob(self, blob, ctype="application/json; charset=utf-8", cache="no-cache"):
            if self.headers.get("If-None-Match") == blob.etag:
                self.send_response(304)
                self.send_header("ETag", blob.etag)
                self.send_header("Cache-Control", cache)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            gz = "gzip" in self.headers.get("Accept-Encoding", "") and any(ctype.startswith(t) for t in TEXT_TYPES)
            body = blob.gz if gz else blob.raw
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("ETag", blob.etag)
            self.send_header("Vary", "Accept-Encoding")
            self.send_header("X-Content-Type-Options", "nosniff")
            if gz:
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _status(self):
            return {"running": state.running, "last_run": state.last_run, "last_error": state.last_error,
                    "interval": int(cfg.get("interval_seconds", 300)),
                    "generated": (state.latest or {}).get("generated"),
                    "has_data": state.latest is not None}

        def do_GET(self):
            if not self._authorized():
                return
            url = urlsplit(self.path)
            path = url.path
            params = {k: v[0] for k, v in parse_qs(url.query).items()}
            if path == "/":
                path = "/index.html"
            if path == "/api/status":
                return self._send_json(200, self._status())
            if path in ("/api/latest", "/api/map", "/api/recipes") or (path == "/api/history" and "item" not in params):
                blob = state.blobs.get(path.rsplit("/", 1)[1])
                if not blob:
                    return self._send_json(404, {"error": "brak danych", "status": self._status()})
                return self._send_blob(blob)
            if path == "/api/history":
                item = params["item"]
                with state.lock:
                    hist = [{"t": h["t"], "v": h["items"].get(item, [0, 0])} for h in state.history]
                return self._send_json(200, hist)
            if not path.startswith("/api/"):
                blob, ctype = static_blob(path.lstrip("/"))
                if blob:
                    cache = "public, max-age=86400" if path.endswith(".svg") else "no-cache"
                    return self._send_blob(blob, ctype, cache)
            self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return
            if self.path == "/api/refresh":
                state.wake.set()
                return self._send_json(202, {"ok": True})
            self._send_json(404, {"error": "not found"})

    return Handler


def main():
    cfg = load_config()
    state = State(cfg)
    if "--once" in sys.argv:
        ok = state.run_once(force=True)
        if ok:
            s = state.latest["summary"]
            log("OK: czas gry %s, maszyn %d (%.0f%% pracuje), braków %d, sugestii %d" % (
                state.latest["game_time"], s["machines"], s["working_pct"] * 100, s["shortages"], s["suggestions"]))
            statuses = {}
            for r in (state.raw.get("crafters") or {}).values():
                for k, v in (r.get("status") or {}).items():
                    statuses[k] = statuses.get(k, 0) + v
            log("Statusy maszyn: " + ", ".join("%s=%d" % kv for kv in sorted(statuses.items(), key=lambda kv: -kv[1])))
            for a in state.latest["suggestions"][:10]:
                log(" - [%s] %s" % (a["severity"], a["title"]))
        sys.exit(0 if ok else 1)

    threading.Thread(target=state.loop, daemon=True).start()
    addr = (cfg.get("listen", "0.0.0.0"), int(cfg.get("port", 8080)))
    log("Dashboard na http://%s:%d" % addr)
    server = ThreadingHTTPServer(addr, make_handler(state))
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
