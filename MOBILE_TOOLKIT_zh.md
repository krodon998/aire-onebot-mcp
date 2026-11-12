# Aire 手机机房小工具

`airectl.py` 用来把目前的 Termux / Ubuntu / Linux QQ / NapCat / AireOneBot / RikkaHub Heartbeat 这条链收成几个固定命令，避免闪退或重启后重新翻历史命令。

## 常用命令

```bash
cd /opt/aire-onebot-mcp
python3 airectl.py status
python3 airectl.py recover
```

`recover` 会按顺序尝试恢复 Xvfb/noVNC、QQ/NapCat、AireOneBot MCP、Heartbeat 和 QQ 群观察器。若 QQ 需要扫码，它会停在登录提示；登录完成后再执行一次 `recover` 即可继续。

### RikkaHub 会话 UUID / 绑定窗口

```bash
python3 airectl.py uuid Aire02
python3 airectl.py target '↑Aire02'
```

`target` 会更新 Heartbeat 的 `conversation_id`，自动备份旧 `state.json`，并重启 Heartbeat。

### Heartbeat 时间

```bash
python3 airectl.py heartbeat show
python3 airectl.py heartbeat set --idle 60 --repeat 180 --start 00:00 --end 23:59 --enable
```

默认会在修改后重启 Heartbeat；加 `--no-restart` 可只改配置。

### QQ 群接收白名单

先列群：

```bash
python3 airectl.py groups list
```

只监听一个群：

```bash
python3 airectl.py groups watch '群名'
python3 airectl.py watcher restart
```

多个群：

```bash
python3 airectl.py groups watch '群A' '群B'
python3 airectl.py watcher restart
```

查看或清空：

```bash
python3 airectl.py groups show
python3 airectl.py groups clear
python3 airectl.py watcher stop
```

`qq_watch.py` 只轮询 `watch_groups` 白名单里的群。第一次启动只把当前历史当作基线，不会把旧消息一次性唤醒到 RikkaHub。之后发现新外部消息时，按冷却时间合并为一次 RikkaHub 唤醒；真正需要完整上下文时再由模型通过 AireOneBot MCP 读取。

这层白名单限制的是“自动接收/唤醒范围”。MCP 的手动群工具本身仍保留完整能力，方便显式操作；如果以后需要硬隔离，可以再把白名单下沉到 MCP 层。

## 本地状态

这些文件只保存在设备上，不应提交：

- `airectl.json`
- `qq_watch_state.json`
- `rikkahub-heartbeat/`

`airectl.example.json` 是无敏感信息的模板。
