# Component 3: The MCP Client

This is a **Streamlit-based chat interface** that connects to the MCP server over SSE (Server-Sent Events). It demonstrates how an MCP client discovers tools, manages an authenticated session, enforces a context window, and presents a chat UI — all without ever touching Ollama directly.

> [!NOTE]
> Before proceeding here, make sure the MCP server is running in SSE mode:
> ```bash
> make run-server-sse
> ```
> See **[Component 2: MCP Server](../2-server/README.md)** for full setup instructions.

---

## What This Client Does

- Connects to the MCP server's SSE endpoint (`http://127.0.0.1:8080/sse`)
- Authenticates every request using an API key from the OS keychain or environment
- Calls the `ollama-chat` tool to send messages to the LLM *through* the security boundary
- Calls `ollama-list-models` to populate a model-selection dropdown
- Enforces a **10-message context window** — older messages are automatically trimmed
- Validates and sanitises user input (max 5,000 characters, no control characters)
- Displays a health check in the sidebar so you know immediately if the server is reachable and authenticated
- Isolates chat history **per browser session** — two tabs = two independent sessions

---

## MCP Client Pattern: The Minimum

Before reading the full implementation, here is the bare-minimum MCP client — the pattern that everything in `chat_service.py` is built on:

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async with sse_client("http://127.0.0.1:8080/sse") as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        result = await session.call_tool("echo", arguments={"message": "hello"})
```

Three steps:
1. Open a transport connection (`sse_client` for HTTP, or `stdio_client` for local pipes)
2. Wrap it in a `ClientSession` and call `initialize()`
3. Call any tool by name with typed arguments

In this repo, that pattern is extended with authentication headers, input validation, and a 10-message context window — all in [`chat_service.py`](./chat_service.py).

---

## File Structure

```text
3-client/
├── client_app.py     ← Streamlit UI entry point
├── chat_service.py   ← service layer: MCP calls, context window, validation
└── credentials.py    ← credential manager (env var → OS keychain)
```

---

## How Authentication Works

The client uses a layered credential lookup implemented in `credentials.py`:

```
1. MCP_CLIENT_KEY  environment variable   (highest priority)
2. OS Keychain     (keyring library)
3. No key found    → connects as anonymous (only works in local/dev mode)
```

To store your key in the OS keychain (optional but recommended):

```python
from credentials import CredentialManager
CredentialManager.set_key_in_keychain("your-secret-key")
```

Or simply export the environment variable before running:

```bash
export MCP_CLIENT_KEY="your-secret-key"
```

---

## Running the Client

### Prerequisites
- Python 3.11+
- MCP server running in SSE mode (see above)
- Dependencies installed via `make install` from the repo root

### Start

```bash
make run-client
```

Or manually:

```bash
cd 3-client
streamlit run client_app.py
```

The UI opens at [http://localhost:8501](http://localhost:8501).

---

## What You See in the UI

| Area | What It Shows |
|------|--------------|
| **Sidebar — Status** | Green ✅ if server is reachable and authenticated; red ❌ if not |
| **Sidebar — Model** | Dropdown of locally available Ollama models (fetched via `ollama-list-models` tool) |
| **Sidebar — Security Info** | Summary of the client's security posture |
| **Main — Chat** | Standard chat interface; history persists per browser session |
| **Main — Clear History** | Resets the context window |

---

## Beginner Walkthrough: Reading the Code in Order

### Step 1. Start both the server and the client

Terminal 1:
```bash
make run-server-sse
```

Terminal 2:
```bash
make run-client
```

Open [http://localhost:8501](http://localhost:8501) and confirm the sidebar shows a green connected status.

### Step 2. Read `credentials.py`

Open [`credentials.py`](./credentials.py).

This is the simplest file. It shows how the client securely retrieves its API key without hardcoding it anywhere in the UI:

```python
class CredentialManager:
    def get_key(self) -> str | None:
        # 1. Check MCP_CLIENT_KEY env var
        # 2. Check OS keychain
        # 3. Return None (anonymous)
```

### Step 3. Read `chat_service.py`

Open [`chat_service.py`](./chat_service.py).

This is the core of the client. It:

- Holds the server URL and credential manager
- Opens an SSE connection and MCP `ClientSession` for every call
- Enforces the context window (`messages[-10:]`)
- Validates and strips user input
- Calls `ollama-chat` and `ollama-list-models` as standard MCP tool calls

The key MCP pattern is visible in every method:

```python
async with sse_client(self.server_url, headers=self._get_headers()) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("ollama-chat", arguments={...})
```

This mirrors the minimal client snippet from the MCP documentation — but with authentication headers and error handling added.

### Step 4. Read `client_app.py`

Open [`client_app.py`](./client_app.py).

This is the Streamlit entry point. Notice:

- `ChatService` is stored in `st.session_state` — one instance per browser session, ensuring session isolation
- The health check and model list are fetched on every page load via `asyncio.run()`
- User input is passed to `service.chat()`, which handles the full MCP round-trip
- `ValueError` (from validation) is surfaced as a UI warning; all other errors are caught and shown as a generic safe message — no stack traces leak to the user

### Step 5. Understand the full call flow

When you type a message and press Enter:

```
client_app.py (UI)
   → chat_service.chat()
       → validate_input()          # length + sanitisation
       → truncate to 10 messages   # context window
       → sse_client(server_url)    # open SSE connection
           → ClientSession.initialize()
           → session.call_tool("ollama-chat", arguments)
               → MCP Server SecurityInterceptor
                   → authenticate (API key)
                   → rate limit check
                   → scope check (tools:ollama:chat)
                   → Ollama provider
                       → llama3.2 (local model)
                   ← LLM response
               ← MCP tool result
           ← result.content[0].text
   ← response string
→ displayed in st.chat_message("assistant")
```

---

## Security Properties of This Client

| Property | Implementation |
|----------|---------------|
| **No direct LLM access** | All inference goes through `ollama-chat` MCP tool |
| **No secrets in UI** | API key loaded from env or OS keychain only |
| **No stack traces exposed** | All exceptions caught; generic error shown to user |
| **Session isolation** | `ChatService` stored in `st.session_state` per browser tab |
| **Input validation** | Max 5,000 characters; non-printable characters stripped |
| **Context window** | Hard cap of 10 messages; older history silently trimmed |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_CLIENT_KEY` | _(none)_ | API key sent with every request |
| `MCP_SERVER_URL` | `http://127.0.0.1:8080/sse` | SSE endpoint of the MCP server |
| `MCP_DEFAULT_MODEL` | `llama3.2` | Fallback model if none selected in UI |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Red ❌ in sidebar | Server not running | Run `make run-server-sse` |
| "NOT authenticated" warning | Key mismatch or missing | Set `MCP_CLIENT_KEY` to a key listed in the server's `auth_keys` |
| No models in dropdown | Ollama not running or no models pulled | Run `ollama serve` and `ollama pull llama3.2` |
| "Invalid Input" warning | Prompt > 5,000 chars or empty | Shorten your message |

---

## ✅ You've Completed the Learning Path

At this point you have:

1. ✅ Set up a local LLM with Ollama (`1-llm/`)
2. ✅ Built and secured an MCP server (`2-server/`)
3. ✅ Connected a client UI that talks to the server over MCP (`3-client/`)

**Suggested next explorations:**

- Add a new tool to the server (`2-server/mcp_server/tools/`) and call it from the client
- Read [SECURITY_ARCHITECTURE.md](../2-server/SECURITY_ARCHITECTURE.md) to explore mTLS, OAuth2/OIDC, and DLP extensions
- Integrate the server with [Claude Desktop](../2-server/README.md#claude-desktop-integration)
- Containerise the stack with `docker-compose.yml` at the repo root
