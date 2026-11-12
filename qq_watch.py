#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "airectl.json"
STATE = ROOT / "qq_watch_state.json"
DEFAULTS = {
    "rikkahub_base": "http://127.0.0.1:8080",
    "onebot_base": "http://127.0.0.1:3000",
    "heartbeat_dir": "rikkahub-heartbeat",
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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def cfg() -> dict[str, Any]:
    c = dict(DEFAULTS)
    c.update(load_json(CONFIG, {}))
    return c


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


def http_json(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None, timeout: float = 6) -> tuple[int, Any]:
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


def onebot(c: dict[str, Any], action: str, params: dict[str, Any] | None = None) -> Any:
    e = env_file(ROOT / "config.env")
    token = e.get("ONEBOT_API_TOKEN") or e.get("SNOWLUMA_API_TOKEN") or ""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    status, data = http_json("POST", c["onebot_base"].rstrip("/") + "/" + action, params or {}, headers=headers)
    if status >= 400 or not isinstance(data, dict) or data.get("status") == "failed":
        raise RuntimeError(f"OneBot {action} failed")
    return data


def target_cid(c: dict[str, Any]) -> str:
    hb = Path(c["heartbeat_dir"])
    if not hb.is_absolute():
        hb = ROOT / hb
    hbc = load_json(hb / "config.json", {})
    cid = str(hbc.get("conversation_id") or "")
    if not cid:
        raise RuntimeError("heartbeat conversation_id is empty")
    return cid


def plain_message(m: dict[str, Any]) -> str:
    raw = m.get("raw_message")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    msg = m.get("message")
    if isinstance(msg, str):
        return msg.strip()
    if isinstance(msg, list):
        parts: list[str] = []
        for seg in msg:
            if not isinstance(seg, dict):
                continue
            typ = seg.get("type")
            data = seg.get("data") or {}
            if typ == "text":
                parts.append(str(data.get("text") or ""))
            elif typ == "at":
                parts.append("@" + str(data.get("qq") or "?"))
            elif typ:
                parts.append(f"[{typ}]")
        return "".join(parts).strip()
    return ""


def message_key(m: dict[str, Any]) -> tuple[int, int]:
    try:
        ts = int(m.get("time") or 0)
    except Exception:
        ts = 0
    try:
        mid = int(m.get("message_id") or 0)
    except Exception:
        mid = 0
    return ts, mid


def fetch_history(c: dict[str, Any], group_id: int) -> list[dict[str, Any]]:
    data = onebot(c, "get_group_msg_history", {"group_id": group_id, "count": 100})
    payload = data.get("data") or {}
    msgs = payload.get("messages") if isinstance(payload, dict) else []
    if not isinstance(msgs, list):
        return []
    rows = [m for m in msgs if isinstance(m, dict)]
    rows.sort(key=message_key)
    return rows


def send_wake(c: dict[str, Any], group: dict[str, Any], messages: list[dict[str, Any]]) -> bool:
    cid = target_cid(c)
    lines = []
    for m in messages[-8:]:
        s = m.get("sender") or {}
        name = s.get("card") or s.get("nickname") or s.get("user_id") or "?"
        text = plain_message(m).replace("\n", " ").strip()
        if len(text) > 220:
            text = text[:217] + "..."
        lines.append(f"- {name}: {text or '[非文字消息]'}")
    body = (
        "[[AIRE_QQ_GROUP_EVENT_V1]]\n"
        "这是来自允许监听的 QQ 群的新消息事件，不是使用者在 RikkaHub 的新发言。\n"
        f"群：{group.get('group_name') or group['group_id']} ({group['group_id']})\n"
        "新增消息摘录：\n" + "\n".join(lines) + "\n\n"
        "请自行判断是否需要通过 AireOneBot MCP 查看更完整群聊上下文、回复或保持沉默。"
        "只处理当前允许监听的群；不要为了回复而额外读取无关私人长期记忆。"
        "若无需行动，只回复「[沉默]」。"
    )
    url = c["rikkahub_base"].rstrip("/") + f"/api/conversations/{cid}/messages"
    status, _ = http_json("POST", url, {"parts": [{"type": "text", "text": body}]}, timeout=10)
    return status == 202


def tick(c: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    if not c.get("watch_enabled"):
        return state, ["disabled"]
    groups = c.get("watch_groups") or []
    if not groups:
        return state, ["no_groups"]
    info = onebot(c, "get_login_info")
    bot_id = int((info.get("data") or {}).get("user_id") or 0)
    now = time.time()
    gs = state.setdefault("groups", {})
    for group in groups:
        gid = int(group["group_id"])
        key = str(gid)
        rows = fetch_history(c, gid)
        if not rows:
            notes.append(f"{gid}:empty")
            continue
        latest_key = message_key(rows[-1])
        st = gs.setdefault(key, {})
        last_key = tuple(st.get("last_delivered_key") or [0, 0])
        if last_key == (0, 0):
            st["last_delivered_key"] = list(latest_key)
            st["last_wake_at"] = now
            notes.append(f"{gid}:primed")
            continue
        new_rows = [m for m in rows if message_key(m) > last_key]
        external = []
        for m in new_rows:
            sender = m.get("sender") or {}
            uid = int(sender.get("user_id") or m.get("user_id") or 0)
            if uid != bot_id:
                external.append(m)
        if not new_rows:
            notes.append(f"{gid}:quiet")
            continue
        if not external:
            st["last_delivered_key"] = list(latest_key)
            notes.append(f"{gid}:self_only")
            continue
        cooldown = int(c.get("group_wake_cooldown_seconds") or 0)
        if now - float(st.get("last_wake_at") or 0) < cooldown:
            notes.append(f"{gid}:cooldown")
            continue
        if send_wake(c, group, external):
            st["last_delivered_key"] = list(latest_key)
            st["last_wake_at"] = now
            notes.append(f"{gid}:accepted:{len(external)}")
        else:
            notes.append(f"{gid}:wake_failed")
    return state, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="Watch allowlisted QQ groups and wake a RikkaHub conversation")
    ap.add_argument("--run", action="store_true", help="poll continuously")
    args = ap.parse_args()
    while True:
        c = cfg()
        state = load_json(STATE, {})
        try:
            state, notes = tick(c, state)
            save_json(STATE, state)
            print(time.strftime("%Y-%m-%dT%H:%M:%S"), " ".join(notes), flush=True)
        except Exception as e:
            print(time.strftime("%Y-%m-%dT%H:%M:%S"), "error", type(e).__name__, flush=True)
            if not args.run:
                return 1
        if not args.run:
            return 0
        time.sleep(max(5, int(c.get("group_poll_seconds") or 15)))


if __name__ == "__main__":
    raise SystemExit(main())
