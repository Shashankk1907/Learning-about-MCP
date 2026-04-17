import asyncio

import streamlit as st

from chat_service import ChatService

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Local Chat Client",
    page_icon="🤖",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Service Initialization
# ---------------------------------------------------------------------------
if "chat_service" not in st.session_state:
    st.session_state.chat_service = ChatService()

service: ChatService = st.session_state.chat_service

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Sidebar - Model Selection & Status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Settings")

    # Health Check
    health = asyncio.run(service.health_check())
    if health["status"]:
        if health["authenticated"]:
            st.success("Server connected & authenticated", icon="✅")
        else:
            st.warning("Server connected but NOT authenticated", icon="🔑")
            st.info(health["error"])
    else:
        st.error("MCP Server is NOT reachable", icon="❌")
        st.info("Ensure the server is running with SSE transport.")

    # Model Selection
    available_models = asyncio.run(service.list_models())
    default_model = "llama3.2"
    if available_models:
        selected_model = st.selectbox(
            "Select Model",
            options=available_models,
            index=available_models.index(default_model)
            if default_model in available_models
            else 0,
        )
    else:
        st.warning("No models found. Pull one with `ollama pull llama3.2`")
        selected_model = default_model

    st.divider()
    st.markdown("""
    ### Security & Isolation
    - **Control Plane**: All LLM calls route through MCP.
    - **Secrets**: Stored in OS keychain or environment.
    - **Session**: History is isolated per browser session.
    - **Validation**: Prompts capped at 5000 chars.
    """)

    if st.button("Clear History", type="secondary"):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------------------------
# Main Chat UI
# ---------------------------------------------------------------------------
st.title("🤖 Local Chat")
st.caption(f"Currently chatting with: `{selected_model}`")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What is on your mind?"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Call the service layer with full history (service handles truncation)
                response = asyncio.run(service.chat(
                    messages=st.session_state.messages,
                    model=selected_model
                ))
                st.markdown(response)
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
            except ValueError as ve:
                st.warning(f"Invalid Input: {ve}")
                # Remove the invalid message from history so it doesn't break future calls
                st.session_state.messages.pop()
            except Exception:
                # Log the actual error for debugging
                import logging
                logging.getLogger("streamlit").exception("Chat error")
                # Show a safe, generic error to the user
                st.error("An internal error occurred. Please check the server status and logs.")
