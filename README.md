# Learn MCP: Local Server, Client, and LLM

This repository is designed as a **step-by-step learning resource** for understanding the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It provides a complete, local-first stack that you can run on your own machine without any cloud dependencies.

To make things easy to digest, the project is split into three main components, and you should explore them in order:

## 🛣️ The Learning Path

### [1. The LLM Provider (`1-llm/`)](./1-llm/README.md)
Start here. Before you can build an AI agent, you need an AI model. This section helps you install and verify [Ollama](https://ollama.com/), which will act as the "brain" of our local setup.
- **Goal**: Get a small, fast model (like `llama3.2`) running locally.

### [2. The MCP Server (`2-server/`)](./2-server/README.md)
This is where the magic happens. The MCP Server exposes tools (like accessing Ollama) and resources to any standardized MCP Client.
- **Goal**: Understand how to define tools, enforce security, and run a server using the FastMCP framework.

### [3. The MCP Client (`3-client/`)](./3-client/README.md)
The final piece of the puzzle. This is a Streamlit-based UI that connects to the MCP Server over SSE (Server-Sent Events) to provide a chat interface. It knows nothing about Ollama; it only knows how to talk to the MCP Server.
- **Goal**: See how a client discovers tools and maintains conversation state.

---

## 🚀 Quick Setup (All-in-One)

If you already have Ollama installed and just want to see it run, use the root `Makefile` which manages a shared virtual environment for both the client and the server:

### 1. Install Dependencies
```bash
make install
```

### 2. Start the Server (Terminal 1)
For the UI to connect, the server needs to run in SSE mode:
```bash
make run-server-sse
```

### 3. Start the Client UI (Terminal 2)
```bash
make run-client
```
The UI will open at [http://localhost:8501](http://localhost:8501).

---

## Why is it structured this way?

We separated the core components into their own folders to emphasize **decoupling**. 
In a real-world scenario, your MCP Server and your MCP Client might be written in completely different languages and run on different machines. By separating `2-server` logic from `3-client` logic, we enforce a strict boundary: **they only communicate via the Model Context Protocol.**
