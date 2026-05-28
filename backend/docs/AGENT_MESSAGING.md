# Agent-to-Agent Messaging

Peer messaging antar Claude Code agent (laptop, server, ...) via Codi broker.

## Arsitektur

```
Laptop Claude Code  ←─MCP─→  Codi backend  ←─MCP─→  Server Claude Code
                              (SQLite store)
                       /api/agent/{send,inbox,wait,history}
```

State persistent di `<auth_db_dir>/codi-agent-messages.db`. Single source of
truth. Multi-tenant — beberapa agent bisa share Codi broker.

## Tools MCP

Setelah `mcp_codi_server.py` dipanggil Claude CLI (`CLAUDE_MCP_CONFIG=...`),
agent dapat 4 tool baru:

| Tool | Param | Behavior |
|---|---|---|
| `agent_send` | sender, recipient, content, thread_id? | Kirim pesan |
| `agent_inbox` | recipient, limit?, mark_read? | Tarik unread (auto-mark) |
| `agent_wait_reply` | recipient, thread_id?, since_id?, timeout? | Block sampai pesan baru |
| `agent_history` | thread_id ATAU (peer_a + peer_b), limit? | Riwayat percakapan |

## Setup

### 1. Set agent name di env masing-masing mesin

Tak ada field "agent_id" formal — pakai konvensi nama string di tiap call
(`sender`/`recipient`). Saran: `<host>-<role>` mis. `laptop-hans`, `server-codi`.

### 2. MCP config

Di setiap mesin tambahkan ke `mcp-config-codi.json` (atau equivalent):

```json
{
  "mcpServers": {
    "codi-hr": {
      "command": "python",
      "args": ["/path/to/AI-Agent-Telegram/backend/mcp_codi_server.py"],
      "env": {
        "CODI_API_URL": "https://codi.emasberlian.com",
        "CODI_API_TOKEN": "<shared token>"
      }
    }
  }
}
```

### 3. Start Codi backend (sudah include messaging store auto-init)

```bash
sudo systemctl restart codi.service
journalctl -u codi.service -n 30 | grep agent_messaging_ready
# → action=agent_messaging_ready | db=.../codi-agent-messages.db
```

## Usage pattern

**Laptop agent kirim ke server agent + tunggu reply:**

```
# Di Claude Code laptop session:
> Gunakan tool agent_send untuk kirim "API signature /chat/messages?"
  ke server-codi, thread_id "fix-mobile-chat"
> Gunakan tool agent_wait_reply recipient=laptop-hans
  thread_id=fix-mobile-chat timeout=120
```

**Server agent terima + balas:**

```
# Di Claude Code server session (mungkin tiap N menit poll):
> agent_inbox recipient=server-codi
# Baca pesan, kerjakan, lalu:
> agent_send sender=server-codi recipient=laptop-hans
  content="POST {message, conversation_id}..." thread_id=fix-mobile-chat
```

## Tradeoff

- Polling-based `wait_reply` (1s interval, max 300s timeout). Bukan
  realtime push. Cukup untuk coding workflow.
- Tak ada auth per-agent (cuma shared token Codi). Hindari kirim data
  sensitif lintas mesin yang tak trusted.
- Tak ada delete — pakai status `read` saja. History tetap utuh untuk
  audit. Manual cleanup via SQL kalau perlu.
