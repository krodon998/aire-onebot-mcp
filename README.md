<p align="right">
  <strong>Language:</strong>
  <b>English</b> |
  <a href="README_zh.md">简体中文</a>
</p>

# Aire OneBot MCP

A lightweight **OneBot v11 HTTP → Remote MCP (Streamable HTTP)** gateway for Android RikkaHub and remote AI agents.

Originally built around SnowLuma, the gateway is now runtime-agnostic. It talks to a standard OneBot v11 HTTP endpoint and is currently tested with **NapCat + Linux NTQQ ARM64**.

## Architecture

```text
QQ / NTQQ
   ↓
NapCat (OneBot v11 HTTP, e.g. 127.0.0.1:3000)
   ↓
Aire OneBot MCP (127.0.0.1:8766/mcp)
   ↓
RikkaHub / remote MCP client
```

## Highlights

- Streamable HTTP MCP endpoint with Bearer authentication.
- 21 high-level tools for messaging, history, groups, forwarding and media.
- Universal OneBot action passthrough.
- QQ Reaction helpers with Chinese aliases.
- On-demand image viewing with size limits and QQ CDN allow-listing.
- Compatible with any sufficiently compatible OneBot v11 HTTP implementation; NapCat is the current tested backend.

## Requirements

- Python 3.10+
- A running OneBot v11 HTTP endpoint
- `mcp>=1.29.0,<2` (the code uses the MCP 1.x FastMCP API)

## Quick start

```bash
git clone https://github.com/krodon998/aire-snowluma-mcp.git
cd aire-snowluma-mcp

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cp .env.example config.env
```

Edit `config.env`:

```env
MCP_HOST=127.0.0.1
MCP_PORT=8766
MCP_AUTH_TOKEN=generate_a_secure_random_token_here

ONEBOT_API_BASE=http://127.0.0.1:3000
ONEBOT_API_TOKEN=
ONEBOT_TIMEOUT=30.0
```

The server automatically reads both `.env` and `config.env`.

Start it:

```bash
./venv/bin/python server.py
```

Health check:

```bash
curl http://127.0.0.1:8766/health
```

A successful response includes `"status":"online"` and the logged-in OneBot account.

## RikkaHub

Add an MCP server:

- Transport: **Streamable HTTP**
- URL: `http://127.0.0.1:8766/mcp` when RikkaHub and the service run on the same Android device/network namespace
- Header name: `Authorization`
- Header value: `Bearer <MCP_AUTH_TOKEN>`

For remote access, put the service behind HTTPS/reverse proxy instead of exposing port 8766 directly.

## Environment variables

Preferred names:

- `ONEBOT_API_BASE`
- `ONEBOT_API_TOKEN`
- `ONEBOT_TIMEOUT`

Legacy `SNOWLUMA_API_*` variables remain accepted as compatibility aliases.

## Deployment

Example files are included under:

- `systemd/aire-onebot-mcp.service`
- `nginx/aire-onebot-mcp.conf`

## License

MIT.
