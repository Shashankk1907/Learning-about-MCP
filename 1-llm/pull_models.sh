#!/bin/bash
set -e

echo "Pulling recommended models into Ollama..."

echo "Pulling llama3.2..."
ollama pull llama3.2

# Add other models if needed in the future
# echo "Pulling gemma2..."
# ollama pull gemma2

echo ""
echo "Models pulled successfully! You can verify them with 'ollama list'."
