"""Credential management for the MCP client.
Supports environment variables and OS keychain-backed storage.
"""
from __future__ import annotations

import logging
import os
import keyring

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "mcp-server"
KEY_ID = "client-auth-key"

class CredentialManager:
    """Manages secure retrieval and storage of MCP client credentials."""

    def __init__(self) -> None:
        pass

    def get_key(self) -> str | None:
        """Retrieve the authentication key with specific precedence:
        1. Environment variable MCP_CLIENT_KEY
        2. OS Keychain (keyring)
        3. Settings (config.yaml / .env)
        """
        # 1. Env Var (Strict override)
        env_key = os.environ.get("MCP_CLIENT_KEY")
        if env_key:
            logger.debug("Using auth key from environment variable.")
            return env_key

        # 2. OS Keychain
        try:
            keyring_key = keyring.get_password(KEYRING_SERVICE, KEY_ID)
            if keyring_key:
                logger.debug("Using auth key from OS keychain.")
                return keyring_key
        except Exception as e:
            logger.warning("Could not access OS keychain: %s", e)

        return None

    @staticmethod
    def set_key_in_keychain(key: str) -> bool:
        """Store the authentication key in the OS keychain."""
        try:
            keyring.set_password(KEYRING_SERVICE, KEY_ID, key)
            logger.info("Successfully stored key in OS keychain.")
            return True
        except Exception as e:
            logger.error("Failed to store key in OS keychain: %s", e)
            return False

    @staticmethod
    def delete_key_from_keychain() -> bool:
        """Remove the authentication key from the OS keychain."""
        try:
            keyring.delete_password(KEYRING_SERVICE, KEY_ID)
            logger.info("Successfully removed key from OS keychain.")
            return True
        except Exception:
            return False
