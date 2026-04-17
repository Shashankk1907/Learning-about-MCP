# Component 1: LLM Provider

The foundation of any AI agent is the **Large Language Model (LLM)**. For this local, cloud-free setup, we use [Ollama](https://ollama.com/) — a runtime that lets you download and run models directly on your own machine.

---

## Why a Local LLM?

In this project, the LLM is **not** accessed directly by the client. Instead, it sits behind the MCP server as a provider. Here is why that matters:

```
3-client (Streamlit UI)
       ↓  MCP over SSE
2-server (MCP Server + Security)
       ↓  provider call
1-llm  (Ollama — local LLM runtime)
```

- The **LLM** is responsible for generating text responses and understanding tool inputs.
- The **MCP server** acts as a secure proxy: it validates who is calling, enforces scopes, rate-limits requests, and only then forwards the prompt to Ollama.
- The **client** never talks to Ollama directly — it only speaks MCP.

This separation means you can swap out the local Ollama backend for any other provider (OpenAI, Anthropic, a different local runtime) without changing the client or the security layer.

---

## Prerequisites

Before setting up the server or client, complete this step first.

1. [Download and install Ollama](https://ollama.com/download) for your OS.
2. Start the Ollama application (or run `ollama serve` in a terminal).

---

## Getting Models

We recommend **`llama3.2`** as the default model — it is small enough to run comfortably on most laptops while being capable enough to handle tool calling reliably.

**Option A — Pull manually:**
```bash
ollama pull llama3.2
```

**Option B — Use the helper script in this directory:**
```bash
./pull_models.sh
```

The script pulls a curated set of models that work well with this stack.

---

## Verifying Setup

Confirm Ollama is running and the model is available:

```bash
ollama run llama3.2 "Hello, what can you do?"
```

You should get a coherent text response in your terminal. If you do, the LLM layer is fully operational.

You can also check which models are locally available at any time:

```bash
ollama list
```

---

## Role in the MCP Stack

Once Ollama is running, the MCP server in `2-server/` will connect to it automatically via its provider layer at:

```
http://localhost:11434
```

This URL is configured in `2-server/config.yaml` and can be overridden with the `MCP_LLM__BASE_URL` environment variable.

---

## ➡️ Next Step

Once Ollama is running and you have confirmed a model works, move on to:

**[Component 2: The MCP Server (`2-server/`)](../2-server/README.md)**
