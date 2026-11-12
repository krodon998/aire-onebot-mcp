# Aire Control Android

一个很小的 Android 控制面板，用来管理手机上的 Aire/RikkaHub/QQ 实验栈。

它本身不复制 Linux QQ、NapCat 或 MCP，也不读取 Termux 私有目录；它通过 Termux 官方的 `RUN_COMMAND` Intent 调用已经存在的 `/opt/aire-onebot-mcp/airectl.py`，并接收命令 stdout/stderr。

## v0.1

- 查看整套状态
- 一键恢复 X11/noVNC → QQ/NapCat → AireOneBot MCP → Heartbeat → QQ 群观察器
- 查询 RikkaHub 会话 UUID
- 按窗口标题/UUID 切换 Heartbeat 绑定
- 快速修改 Heartbeat idle/repeat/时间窗
- 在 App 内嵌打开 `127.0.0.1:8767` Heartbeat 高级页面
- 列出 QQ 群、配置自动接收白名单
- Termux 命令结果直接回显在 App 内
- 如果直接调用失败，保留可复制输出作为排错入口

## 第一次使用

Termux 需要允许第三方 App 调用：

```bash
mkdir -p ~/.termux && touch ~/.termux/termux.properties && \
(grep -q '^allow-external-apps=true$' ~/.termux/termux.properties || \
echo 'allow-external-apps=true' >> ~/.termux/termux.properties) && termux-reload-settings
```

安装 Aire Control 后，再在系统权限里授予：

`Run commands in Termux environment`

App 首次启动也会尝试请求该权限。

## 构建

GitHub Actions 的 `Build Aire Control APK` 会在 Android 源码变化时自动构建 debug APK，并上传为 `AireControl-debug` artifact。
