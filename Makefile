.PHONY: help install dev run-server run-client clean test lint

VENV = .venv
BIN = $(VENV)/bin
SERVER_DIR = 2-server
CLIENT_DIR = 3-client

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

$(VENV)/bin/activate:
	/usr/local/bin/python3.12 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

install: $(VENV)/bin/activate ## Install dependencies for both server and client into a shared virtual environment
	$(BIN)/pip install -e $(SERVER_DIR)
	# UI dependencies are handled by the main pyproject for simplicity in this shared venv

dev: install ## Install dev dependencies
	$(BIN)/pip install -e "$(SERVER_DIR)[dev]"

run-server: ## Run the MCP Server (stdio by default)
	$(BIN)/python -m mcp_server.main

run-server-sse: ## Run the MCP Server with SSE transport (required for Streamlit client)
	$(BIN)/python -m mcp_server.main --transport sse

run-client: ## Run the local Streamlit chat client
	$(BIN)/streamlit run $(CLIENT_DIR)/client_app.py

test: ## Run tests for the server
	PYTHONPATH=$(SERVER_DIR) $(BIN)/pytest $(SERVER_DIR)/tests/ $(ARGS)

lint: ## Run ruff on the codebase
	$(BIN)/ruff check .

clean: ## Clean up virtual environment and caches
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
