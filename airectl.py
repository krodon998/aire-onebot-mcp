#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOCAL_CONFIG = ROOT / "airectl.json"
DEFAULTS: dict[str, Any] = {
    "rikkahub_base": "http://127.0.0.1:8080",
    "onebot_base": "http://127.0.0.1:3000",
    "mcp_health": "http://127.0.0.1:8766/health",
    "heartbeat_dir": "rikkahub-heartbeat",
    "display": ":1",
    "novnc_port": 6080,
    "vnc_port": 5901,
    "watch_enabled": False,
    "watch_groups": [],
    "group_poll_seconds": 15,
    "group_wake_cooldown_seconds": 120,
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def config() -> dict[str, Any]:
    c = dict(DEFAULTS)
    c.update(load_json(LOCAL_CONFIG, {}))
    return c


def save_config(c: dict[str, Any]) -> None:
    save_json(LOCAL_CONFIG, c)


def env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def http_json(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None, timeout: float = 5) -> tuple[int, Any]:
    data = None
    h = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            return r.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return e.code, parsed


def probe(url: str, timeout: float = 1.5) -> tuple[bool, int | None]:
    try:
        code, _ = http_json("GET", url, timeout=timeout)
        return True, code
    except Exception:
        return False, None


def onebot(action: str, params: dict[str, Any] | None = None) -> Any:
    c = config()
    e = env_file(ROOT / "config.env")
    token = e.get("ONEBOT_API_TOKEN") or e.get("SNOWLUMA_API_TOKEN") or ""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = c["onebot_base"].rstrip("/") + "/" + action
    status, data = http_json("POST", url, params or {}, headers=headers, timeout=6)
    if status >= 400:
        raise RuntimeError(f"OneBot {action}: HTTP {status}")
    if isinstance(data, dict) and data.get("status") == "failed":
        raise RuntimeError(f"OneBot {action}: {data.get('message') or data.get('wording') or data}")
    return data


def ps_lines() -> list[str]:
    try:
        out = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True, stderr=subprocess.DEVNULL)
        return out.splitlines()
    except Exception:
        return []


def running(needle: str) -> bool:
    me = str(os.getpid())
    for line in ps_lines():
        parts = line.strip().split(None, 1)
        if not parts or parts[0] == me:
            continue
        if len(parts) > 1 and needle in parts[1]:
            return True
    return False


def detached(cmd: list[str], log: Path, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    fh = open(log, "ab", buffering=0)
    try:
        subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        fh.close()


def heartbeat_dir(c: dict[str, Any] | None = None) -> Path:
    c = c or config()
    p = Path(c["heartbeat_dir"])
    return p if p.is_absolute() else ROOT / p


def heartbeat_config_path(c: dict[str, Any] | None = None) -> Path:
    return heartbeat_dir(c) / "config.json"


def restart_heartbeat() -> None:
    for line in ps_lines():
        if "heartbeat.py --run" in line:
            try:
                os.kill(int(line.strip().split(None, 1)[0]), 15)
            except Exception:
                pass
    time.sleep(0.4)
    c = config()
    hb = heartbeat_dir(c)
    hp = heartbeat_config_path(c)
    hc = load_json(hp, {})
    if not hc.get("enabled"):
        print("heartbeat: disabled")
        return
    if not probe(c["rikkahub_base"].rstrip("/") + "/")[0]:
        print("heartbeat: RikkaHub 8080 offline; not started")
        return
    detached([sys.executable, "heartbeat.py", "--run"], Path("/tmp/rikkahub-heartbeat.log"), cwd=hb)
    print("heartbeat: started")


def backup_heartbeat_state(hb: Path) -> None:
    state = hb / "state.json"
    if state.exists():
        bdir = hb / "backups"
        bdir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(state), str(bdir / f"state-{stamp}.json"))
    try:
        (hb / "state.json.lock").unlink()
    except FileNotFoundError:
        pass


def conversations(q: str = "") -> list[dict[str, Any]]:
    c = config()
    url = c["rikkahub_base"].rstrip("/") + "/api/conversations/paged?limit=100"
    if q:
        url += "&query=" + urllib.parse.quote(q)
    status, data = http_json("GET", url, timeout=6)
    if status >= 400 or not isinstance(data, dict):
        raise RuntimeError(f"RikkaHub conversations: HTTP {status}")
    items = data.get("items") or []
    return [x for x in items if isinstance(x, dict)]


def cmd_status(_: argparse.Namespace) -> int:
    c = config()
    checks = [
        ("RikkaHub", c["rikkahub_base"].rstrip("/") + "/"),
        ("OneBot", c["onebot_base"].rstrip("/") + "/get_login_info"),
        ("AireOneBot MCP", c["mcp_health"]),
        ("noVNC", f"http://127.0.0.1:{c['novnc_port']}/vnc.html"),
    ]
    for name, url in checks:
        try:
            if name == "OneBot":
                onebot("get_login_info")
                print(f"{name:14} online")
            else:
                ok, code = probe(url)
                print(f"{name:14} {'online' if ok else 'down'}" + (f" ({code})" if code else ""))
        except Exception:
            print(f"{name:14} down")
    print(f"Heartbeat      {'running' if running('heartbeat.py --run') else 'stopped'}")
    print(f"QQ watcher     {'running' if running('qq_watch.py --run') else 'stopped'}")
    return 0


def ensure_x_stack(c: dict[str, Any]) -> None:
    display = str(c["display"])
    env = os.environ.copy()
    env["DISPLAY"] = display
    if not running(f"Xvfb {display}"):
        if display == ":1":
            for p in [Path("/tmp/.X1-lock"), Path("/tmp/.X11-unix/X1")]:
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
                except IsADirectoryError:
                    shutil.rmtree(p, ignore_errors=True)
        detached(["Xvfb", display, "-screen", "0", "1280x720x24", "-nolisten", "tcp"], Path("/tmp/xvfb.log"), env=env)
        time.sleep(1)
    if not running("openbox"):
        detached(["dbus-launch", "openbox-session"], Path("/tmp/openbox.log"), env=env)
    if not running("x11vnc -display"):
        detached(["x11vnc", "-display", display, "-localhost", "-nopw", "-forever", "-shared", "-rfbport", str(c["vnc_port"])], Path("/tmp/x11vnc.log"), env=env)
    if not running("websockify --web=/usr/share/novnc"):
        detached(["websockify", "--web=/usr/share/novnc", f"127.0.0.1:{c['novnc_port']}", f"127.0.0.1:{c['vnc_port']}"], Path("/tmp/novnc.log"), env=env)


def ensure_qq(c: dict[str, Any]) -> None:
    if running("/opt/QQ/qq"):
        return
    env = os.environ.copy()
    env["DISPLAY"] = str(c["display"])
    detached(["/opt/QQ/qq", "--no-sandbox"], Path("/tmp/qq.log"), env=env)


def ensure_mcp(c: dict[str, Any]) -> bool:
    if probe(c["mcp_health"])[0]:
        return True
    try:
        onebot("get_login_info")
    except Exception:
        return False
    e = os.environ.copy()
    e.update(env_file(ROOT / "config.env"))
    py = ROOT / "venv" / "bin" / "python"
    detached([str(py), "server.py"], Path("/tmp/aire-onebot-mcp.log"), cwd=ROOT, env=e)
    time.sleep(1.5)
    return probe(c["mcp_health"])[0]


def ensure_heartbeat(c: dict[str, Any]) -> None:
    hb = heartbeat_dir(c)
    hc = load_json(hb / "config.json", {})
    if hc.get("enabled") and probe(c["rikkahub_base"].rstrip("/") + "/")[0] and not running("heartbeat.py --run"):
        detached([sys.executable, "heartbeat.py", "--run"], Path("/tmp/rikkahub-heartbeat.log"), cwd=hb)


def ensure_watcher(c: dict[str, Any]) -> None:
    if not c.get("watch_enabled") or not c.get("watch_groups"):
        return
    if running("qq_watch.py --run"):
        return
    try:
        onebot("get_login_info")
    except Exception:
        return
    if not probe(c["rikkahub_base"].rstrip("/") + "/")[0]:
        return
    detached([sys.executable, "qq_watch.py", "--run"], Path("/tmp/aire-qq-watch.log"), cwd=ROOT)


def cmd_recover(_: argparse.Namespace) -> int:
    c = config()
    print("[1/5] X11/noVNC")
    ensure_x_stack(c)
    print("[2/5] QQ/NapCat")
    ensure_qq(c)
    time.sleep(3)
    logged_in = False
    try:
        info = onebot("get_login_info")
        data = info.get("data", {}) if isinstance(info, dict) else {}
        print(f"      logged in: {data.get('nickname','?')} ({data.get('user_id','?')})")
        logged_in = True
    except Exception:
        print(f"      waiting for QQ login; open http://127.0.0.1:{c['novnc_port']}/vnc.html")
        print("      after login, run: python3 airectl.py recover")
    print("[3/5] AireOneBot MCP")
    if logged_in:
        print("      " + ("online" if ensure_mcp(c) else "failed"))
    else:
        print("      skipped until QQ/NapCat login")
    print("[4/5] Heartbeat")
    ensure_heartbeat(c)
    print("      " + ("running" if running("heartbeat.py --run") else "not started"))
    print("[5/5] QQ group watcher")
    if logged_in:
        ensure_watcher(c)
    print("      " + ("running" if running("qq_watch.py --run") else "not started"))
    return 0 if logged_in else 2


def cmd_conversations(args: argparse.Namespace) -> int:
    items = conversations(args.query or "")
    if not items:
        print("no conversations")
        return 1
    for x in items:
        print(f"{x.get('title') or '(untitled)'}\t{x.get('id')}")
    return 0


def resolve_conversation(value: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-fA-F-]{36}", value):
        return {"id": value, "title": value}
    items = conversations(value)
    exact = [x for x in items if str(x.get("title", "")).strip() == value.strip()]
    if len(exact) == 1:
        return exact[0]
    if len(items) == 1:
        return items[0]
    if not items:
        raise RuntimeError("no matching conversation")
    print("multiple matches:")
    for x in items[:20]:
        print(f"  {x.get('title')}\t{x.get('id')}")
    raise RuntimeError("please use an exact title or UUID")


def cmd_target(args: argparse.Namespace) -> int:
    c = config()
    hb = heartbeat_dir(c)
    hp = hb / "config.json"
    hc = load_json(hp, {})
    x = resolve_conversation(args.value)
    old = hc.get("conversation_id")
    new = str(x["id"])
    if old != new:
        backup_heartbeat_state(hb)
    hc["conversation_id"] = new
    save_json(hp, hc)
    print(f"target: {x.get('title')} -> {new}")
    if args.restart:
        restart_heartbeat()
    return 0


def cmd_heartbeat_show(_: argparse.Namespace) -> int:
    c = config()
    hc = load_json(heartbeat_config_path(c), {})
    for k in ["enabled", "conversation_id", "timezone", "active_start", "active_end", "idle_minutes", "repeat_minutes", "poll_seconds"]:
        print(f"{k} = {hc.get(k)}")
    print(f"prompt_chars = {len(str(hc.get('prompt') or ''))}")
    return 0


def cmd_heartbeat_set(args: argparse.Namespace) -> int:
    c = config()
    p = heartbeat_config_path(c)
    hc = load_json(p, {})
    changes = {
        "idle_minutes": args.idle,
        "repeat_minutes": args.repeat,
        "poll_seconds": args.poll,
        "active_start": args.start,
        "active_end": args.end,
    }
    for k, v in changes.items():
        if v is not None:
            hc[k] = v
    if args.enable:
        hc["enabled"] = True
    if args.disable:
        hc["enabled"] = False
    save_json(p, hc)
    cmd_heartbeat_show(args)
    if args.restart:
        restart_heartbeat()
    return 0


def group_rows() -> list[dict[str, Any]]:
    data = onebot("get_group_list")
    rows = data.get("data", []) if isinstance(data, dict) else []
    return [x for x in rows if isinstance(x, dict)]


def cmd_groups_list(_: argparse.Namespace) -> int:
    for g in group_rows():
        print(f"{g.get('group_name') or '(unnamed)'}\t{g.get('group_id')}")
    return 0


def resolve_group(value: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if value.isdigit():
        for g in rows:
            if str(g.get("group_id")) == value:
                return g
        return {"group_id": int(value), "group_name": value}
    exact = [g for g in rows if str(g.get("group_name", "")).strip() == value.strip()]
    if len(exact) == 1:
        return exact[0]
    fuzzy = [g for g in rows if value.lower() in str(g.get("group_name", "")).lower()]
    if len(fuzzy) == 1:
        return fuzzy[0]
    if not fuzzy:
        raise RuntimeError(f"no matching group: {value}")
    print(f"multiple groups match {value!r}:")
    for g in fuzzy:
        print(f"  {g.get('group_name')}\t{g.get('group_id')}")
    raise RuntimeError("please use exact group name or group ID")


def cmd_groups_show(_: argparse.Namespace) -> int:
    c = config()
    print(f"watch_enabled = {bool(c.get('watch_enabled'))}")
    groups = c.get("watch_groups") or []
    if not groups:
        print("watch_groups = []")
    else:
        for g in groups:
            print(f"{g.get('group_name') or '(unnamed)'}\t{g.get('group_id')}")
    print(f"poll_seconds = {c.get('group_poll_seconds')}")
    print(f"wake_cooldown_seconds = {c.get('group_wake_cooldown_seconds')}")
    return 0


def cmd_groups_watch(args: argparse.Namespace) -> int:
    c = config()
    rows = group_rows()
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()
    for value in args.groups:
        g = resolve_group(value, rows)
        gid = int(g["group_id"])
        if gid not in seen:
            selected.append({"group_id": gid, "group_name": g.get("group_name") or str(gid)})
            seen.add(gid)
    c["watch_groups"] = selected
    c["watch_enabled"] = True
    save_config(c)
    print("watch groups replaced with:")
    for g in selected:
        print(f"  {g['group_name']} ({g['group_id']})")
    print("run python3 airectl.py watcher restart to apply immediately")
    return 0


def cmd_groups_clear(_: argparse.Namespace) -> int:
    c = config()
    c["watch_groups"] = []
    c["watch_enabled"] = False
    save_config(c)
    print("group watch disabled; allowlist cleared")
    return 0


def stop_watcher() -> None:
    for line in ps_lines():
        if "qq_watch.py --run" in line:
            try:
                os.kill(int(line.strip().split(None, 1)[0]), 15)
            except Exception:
                pass


def cmd_watcher(args: argparse.Namespace) -> int:
    c = config()
    if args.action in ("stop", "restart"):
        stop_watcher()
        time.sleep(0.4)
    if args.action in ("start", "restart"):
        ensure_watcher(c)
    print("watcher: " + ("running" if running("qq_watch.py --run") else "stopped"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Aire mobile stack control tool")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("status", help="show stack status")
    sp.set_defaults(fn=cmd_status)
    sp = sub.add_parser("recover", help="recover X11 -> QQ/NapCat -> MCP -> heartbeat/watcher")
    sp.set_defaults(fn=cmd_recover)

    sp = sub.add_parser("conversations", aliases=["uuid"], help="list/search RikkaHub conversations and UUIDs")
    sp.add_argument("query", nargs="?", default="")
    sp.set_defaults(fn=cmd_conversations)

    sp = sub.add_parser("target", help="change heartbeat target by title or UUID")
    sp.add_argument("value")
    sp.add_argument("--no-restart", dest="restart", action="store_false")
    sp.set_defaults(fn=cmd_target, restart=True)

    hp = sub.add_parser("heartbeat", help="show/change heartbeat settings")
    hs = hp.add_subparsers(dest="action", required=True)
    hshow = hs.add_parser("show")
    hshow.set_defaults(fn=cmd_heartbeat_show)
    hset = hs.add_parser("set")
    hset.add_argument("--idle", type=int)
    hset.add_argument("--repeat", type=int)
    hset.add_argument("--poll", type=int)
    hset.add_argument("--start")
    hset.add_argument("--end")
    hset.add_argument("--enable", action="store_true")
    hset.add_argument("--disable", action="store_true")
    hset.add_argument("--no-restart", dest="restart", action="store_false")
    hset.set_defaults(fn=cmd_heartbeat_set, restart=True)

    gp = sub.add_parser("groups", help="configure QQ group receive allowlist")
    gs = gp.add_subparsers(dest="action", required=True)
    gl = gs.add_parser("list", help="list joined groups")
    gl.set_defaults(fn=cmd_groups_list)
    gshow = gs.add_parser("show", help="show current allowlist")
    gshow.set_defaults(fn=cmd_groups_show)
    gw = gs.add_parser("watch", help="replace allowlist with selected group(s)")
    gw.add_argument("groups", nargs="+")
    gw.set_defaults(fn=cmd_groups_watch)
    gc = gs.add_parser("clear", help="disable and clear group allowlist")
    gc.set_defaults(fn=cmd_groups_clear)

    wp = sub.add_parser("watcher", help="control QQ group watcher")
    wp.add_argument("action", choices=["start", "stop", "restart", "status"])
    wp.set_defaults(fn=cmd_watcher)
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.fn(args) or 0)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
