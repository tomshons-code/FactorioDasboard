import json
import os
import secrets
import shutil
import subprocess
import time
import zipfile

from rcon import Rcon

MOD_NAME = "factorio-bot-collector"


def newest_save(saves_dir):
    saves = [
        os.path.join(saves_dir, f)
        for f in os.listdir(saves_dir)
        if f.endswith(".zip") and not f.startswith(".")
    ]
    if not saves:
        raise RuntimeError("Brak zapisów .zip w %s" % saves_dir)
    return max(saves, key=os.path.getmtime)


def _stable_copy(src, dst, settle=5, attempts=10):
    for _ in range(attempts):
        m1 = os.path.getmtime(src)
        if time.time() - m1 < settle:
            time.sleep(settle)
            continue
        shutil.copy2(src, dst)
        if os.path.getmtime(src) == m1 and zipfile.is_zipfile(dst):
            with zipfile.ZipFile(dst) as z:
                if z.namelist():
                    return
        time.sleep(settle)
    raise RuntimeError("Nie udało się skopiować stabilnego zapisu %s" % src)


def _prepare_mods(server_mods, shadow_mods, bot_mod_src):
    if os.path.isdir(shadow_mods):
        shutil.rmtree(shadow_mods)
    os.makedirs(shadow_mods)
    mod_list = {"mods": [{"name": "base", "enabled": True}]}
    if os.path.isdir(server_mods):
        for f in os.listdir(server_mods):
            src = os.path.join(server_mods, f)
            if f == "mod-list.json":
                with open(src, encoding="utf-8") as fh:
                    mod_list = json.load(fh)
            elif f == "mod-settings.dat":
                shutil.copy2(src, os.path.join(shadow_mods, f))
            else:
                os.symlink(src, os.path.join(shadow_mods, f))
    mod_list["mods"] = [m for m in mod_list["mods"] if m.get("name") != MOD_NAME]
    mod_list["mods"].append({"name": MOD_NAME, "enabled": True})
    with open(os.path.join(shadow_mods, "mod-list.json"), "w", encoding="utf-8") as fh:
        json.dump(mod_list, fh, indent=2)
    shutil.copytree(bot_mod_src, os.path.join(shadow_mods, MOD_NAME))


def request_save(cfg, log=print, timeout=90):
    live = cfg.get("live_rcon") or {}
    if not live.get("password"):
        return False
    saves = os.path.join(cfg["factorio_dir"], "saves")
    before = os.path.getmtime(newest_save(saves))
    with Rcon(live.get("host", "127.0.0.1"), int(live.get("port", 27015)), live["password"], timeout=30) as conn:
        conn.command("/server-save")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        if os.path.getmtime(newest_save(saves)) > before:
            log("Serwer zapisał świat (/server-save)")
            return True
    log("Serwer nie zapisał świata w %ds — używam ostatniego zapisu" % timeout)
    return False


def collect(cfg, log=print):
    run = os.path.join(cfg["work_dir"], "shadow", "run")
    try:
        return _collect(cfg, log)
    finally:
        shutil.rmtree(run, ignore_errors=True)


def _collect(cfg, log=print):
    fdir = cfg["factorio_dir"]
    work = os.path.join(cfg["work_dir"], "shadow")
    run = os.path.join(work, "run")
    binary = os.path.join(fdir, "bin", "x64", "factorio")

    save = newest_save(os.path.join(fdir, "saves"))
    save_mtime = os.path.getmtime(save)
    log("Zapis: %s" % save)

    if os.path.isdir(run):
        shutil.rmtree(run)
    os.makedirs(os.path.join(run, "write-data"))
    save_copy = os.path.join(run, "shadow.zip")
    _stable_copy(save, save_copy)
    _prepare_mods(os.path.join(fdir, "mods"), os.path.join(run, "mods"), cfg["bot_mod_dir"])

    config_ini = os.path.join(run, "config.ini")
    with open(config_ini, "w", encoding="utf-8") as fh:
        fh.write("[path]\nread-data=%s\nwrite-data=%s\n" % (
            os.path.join(fdir, "data"), os.path.join(run, "write-data")))

    settings = os.path.join(run, "server-settings.json")
    with open(settings, "w", encoding="utf-8") as fh:
        json.dump({
            "name": "factorio-bot-shadow",
            "description": "kopia tylko do odczytu",
            "visibility": {"public": False, "lan": False},
            "require_user_verification": False,
            "game_password": secrets.token_hex(16),
            "max_players": 1,
            "auto_pause": False,
            "autosave_interval": 9999,
            "autosave_slots": 1,
        }, fh)

    rcon_pw = secrets.token_hex(16)
    rcon_port = int(cfg.get("shadow_rcon_port", 27099))
    cmd = [
        binary, "-c", config_ini,
        "--start-server", save_copy,
        "--mod-directory", os.path.join(run, "mods"),
        "--server-settings", settings,
        "--bind", "127.0.0.1:%d" % int(cfg.get("shadow_game_port", 34299)),
        "--rcon-bind", "127.0.0.1:%d" % rcon_port,
        "--rcon-password", rcon_pw,
    ]
    log_path = os.path.join(work, "shadow-factorio.log")
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8") as logf:
        proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        try:
            deadline = t0 + int(cfg.get("startup_timeout", 300))
            conn = None
            while time.time() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError("Factorio-cień zakończył się (kod %s). Log: %s\n%s"
                                       % (proc.returncode, log_path, _tail(log_path)))
                try:
                    conn = Rcon("127.0.0.1", rcon_port, rcon_pw, timeout=120)
                    break
                except (OSError, ConnectionError):
                    time.sleep(2)
            if conn is None:
                raise RuntimeError("Timeout przy starcie cienia. Log: %s\n%s" % (log_path, _tail(log_path)))
            warmup = float(cfg.get("warmup_seconds", 5))
            log("Cień gotowy po %.0fs, rozgrzewka %.0fs..." % (time.time() - t0, warmup))
            time.sleep(warmup)
            with conn:
                body = conn.command("/fb_collect")
            try:
                reply = json.loads(body)
            except ValueError:
                raise RuntimeError("Mod nie zwrócił JSON-a (czy się załadował?): %s" % body[:500])
            if "error" in reply:
                raise RuntimeError("Błąd w modzie: %s" % reply["error"])
            if reply.get("files"):
                out_dir = os.path.join(run, "write-data", "script-output", "factorio-bot")
                data = _read_when_ready(os.path.join(out_dir, "stats.json"))
                game_map = _read_when_ready(os.path.join(out_dir, "map.json"))
            else:
                data = reply
                game_map = data.pop("map", {})
        finally:
            proc.kill()
            proc.wait()
    log("Zebrano dane w %.0fs" % (time.time() - t0))
    return data, game_map, save, save_mtime


def _read_when_ready(path, timeout=60):
    deadline = time.time() + timeout
    last = -1
    while time.time() < deadline:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size > 0 and size == last:
                try:
                    with open(path, encoding="utf-8") as fh:
                        return json.load(fh)
                except ValueError:
                    pass
            last = size
        time.sleep(0.5)
    raise RuntimeError("Mod nie zapisał pliku %s" % path)


def _tail(path, n=20):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-n:])
    except OSError:
        return ""
