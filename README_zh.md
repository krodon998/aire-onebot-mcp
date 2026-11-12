<p align="right">
  <strong>语言 / Language:</strong>
  <a href="README.md">English</a> |
  <b>简体中文</b>
</p>

# Aire OneBot MCP

一个轻量的 **OneBot v11 HTTP → Remote MCP（Streamable HTTP）** 网关，面向 Android RikkaHub 与远程 AI Agent。

项目最初围绕 SnowLuma 编写，现在已经改成与具体运行时解耦：只要上游提供兼容的 OneBot v11 HTTP API 就能接入。目前已实际跑通 **NapCat + Linux NTQQ ARM64**。

## 当前链路

```text
QQ / NTQQ
   ↓
NapCat（OneBot v11 HTTP，例如 127.0.0.1:3000）
   ↓
Aire OneBot MCP（127.0.0.1:8766/mcp）
   ↓
RikkaHub / 其他 MCP 客户端
```

## 主要能力

- Streamable HTTP MCP 端点 + Bearer Token 鉴权。
- 消息收发、历史、群资料、合并转发、媒体等 21 个高频工具。
- `call_onebot_action` 通用 OneBot 动作透传。
- QQ Reaction 中文别名映射。
- 按需看图，带体积限制与 QQ CDN 域名白名单。
- 上游不再绑定 SnowLuma；当前实测后端为 NapCat。

## 环境要求

- Python 3.10+
- 一个正在运行的 OneBot v11 HTTP 服务
- `mcp>=1.29.0,<2`

注意：代码仍使用 MCP 1.x 的 FastMCP API，因此依赖必须限制为 `<2`。此前仅写 `mcp>=1.29.0` 会被 pip 安装到 2.x 并导致启动失败。

## 快速开始

```bash
git clone https://github.com/krodon998/aire-snowluma-mcp.git
cd aire-snowluma-mcp

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cp .env.example config.env
```

编辑 `config.env`：

```env
MCP_HOST=127.0.0.1
MCP_PORT=8766
MCP_AUTH_TOKEN=请生成一个安全随机字符串

ONEBOT_API_BASE=http://127.0.0.1:3000
ONEBOT_API_TOKEN=
ONEBOT_TIMEOUT=30.0
```

服务会自动读取 `.env` 和 `config.env`，不再需要手动 `source`。

启动：

```bash
./venv/bin/python server.py
```

健康检查：

```bash
curl http://127.0.0.1:8766/health
```

正常时会返回 `"status":"online"`，并显示当前 OneBot 登录账号。

## RikkaHub 接入

添加 MCP：

- 传输类型：**Streamable HTTP**
- 同机地址：`http://127.0.0.1:8766/mcp`
- 自定义请求头名称：`Authorization`
- 自定义请求头值：`Bearer <MCP_AUTH_TOKEN>`

如果客户端不在同一台设备上，应通过 HTTPS / 反向代理暴露，不建议直接公开 8766 端口。

## 环境变量迁移

新的推荐变量名：

- `ONEBOT_API_BASE`
- `ONEBOT_API_TOKEN`
- `ONEBOT_TIMEOUT`

旧的 `SNOWLUMA_API_*` 仍作为兼容别名保留，现有部署不会立即失效。

## 部署示例

仓库内提供：

- `systemd/aire-onebot-mcp.service`
- `nginx/aire-onebot-mcp.conf`

## 开源协议

MIT。
