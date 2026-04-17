# Component 1: LLM Provider

The foundation of an AI Agent is the Large Language Model (LLM). For this local setup, we use [Ollama](https://ollama.com/), which allows you to run models directly on your machine without relying on a cloud service.

## Prerequisites

1.  [Download and install Ollama](https://ollama.com/download) for your OS.
2.  Start the Ollama application.

## Getting Models

We recommend using the `llama3.2` model, which is small and fast enough to run locally but capable enough to handle tool calling.

You can pull the model manually:

```bash
ollama pull llama3.2
```

Or you can use the provided helper script:

```bash
./pull_models.sh
```

## Verifying Setup

To ensure Ollama is running correctly, you can test it:

```bash
ollama run llama3.2 "Hello, what models do you know?"
```

Once this is working, you are ready to move on to **Component 2: The Server**.
