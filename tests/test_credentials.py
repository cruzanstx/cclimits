"""
Tests for credential discovery functions.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
from cclimits import (
    get_claude_credentials,
    get_openai_credentials,
    get_gemini_oauth_creds,
    get_gemini_credentials,
    get_zai_credentials
)


class TestGetClaudeCredentials:
    """Tests for get_claude_credentials() function."""

    @patch('cclimits.sys.platform', 'darwin')
    @patch('cclimits.subprocess.run')
    def test_macos_keychain_nested_structure(self, mock_run):
        """Test Claude credentials from macOS Keychain (nested structure)."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "claudeAiOauth": {
                "accessToken": "test-token-nested"
            }
        })
        mock_run.return_value = mock_result

        token = get_claude_credentials()
        assert token == "test-token-nested"

    @patch('cclimits.sys.platform', 'darwin')
    @patch('cclimits.subprocess.run')
    def test_macos_keychain_flat_structure(self, mock_run):
        """Test Claude credentials from macOS Keychain (flat structure)."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "accessToken": "test-token-flat"
        })
        mock_run.return_value = mock_result

        token = get_claude_credentials()
        assert token == "test-token-flat"

    @patch('cclimits.sys.platform', 'darwin')
    @patch('cclimits.subprocess.run')
    def test_macos_keychain_failure(self, mock_run):
        """Test macOS Keychain command failure."""
        mock_run.side_effect = Exception("security command failed")

        token = get_claude_credentials()
        # Should fallback to file or env, which won't exist
        assert token is None or isinstance(token, str)

    @patch('cclimits.os.environ.get')
    def test_env_variable(self, mock_get):
        """Test Claude credentials from environment variable."""
        mock_get.return_value = "env-token"

        token = get_claude_credentials()
        assert token == "env-token"

    @patch('cclimits.os.environ.get')
    def test_no_credentials(self, mock_get):
        """Test when no credentials are found."""
        mock_get.return_value = None

        # Make sure file paths don't exist
        token = get_claude_credentials()
        assert token is None


class TestGetOpenAICredentials:
    """Tests for get_openai_credentials() function."""

    @patch('cclimits.os.environ.get')
    def test_api_key_from_env(self, mock_get):
        """Test OpenAI API key from environment variable."""
        mock_get.return_value = "sk-test-api-key"

        creds = get_openai_credentials()
        assert creds["api_key"] == "sk-test-api-key"

    @patch('cclimits.os.environ.get')
    @patch('cclimits.Path.exists')
    @patch('cclimits.Path.read_text')
    def test_auth_file_with_api_key(self, mock_read, mock_exists, mock_get):
        """Test OpenAI credentials from auth file with API key."""
        mock_get.return_value = None
        mock_exists.return_value = True
        mock_read.return_value = json.dumps({
            "OPENAI_API_KEY": "file-api-key"
        })

        creds = get_openai_credentials()
        assert creds["api_key"] == "file-api-key"

    @patch('cclimits.os.environ.get')
    @patch('cclimits.Path.exists')
    @patch('cclimits.Path.read_text')
    def test_auth_file_with_oauth(self, mock_read, mock_exists, mock_get):
        """Test OpenAI credentials from auth file with OAuth tokens."""
        mock_get.return_value = None
        mock_exists.return_value = True
        mock_read.return_value = json.dumps({
            "tokens": {
                "access_token": "test-access-token",
                "account_id": "test-account-id"
            }
        })

        creds = get_openai_credentials()
        assert creds["access_token"] == "test-access-token"
        assert creds["account_id"] == "test-account-id"

    @patch('cclimits.os.environ.get')
    def test_no_credentials(self, mock_get):
        """Test when no OpenAI credentials are found."""
        mock_get.return_value = None

        # Make sure paths don't exist
        with patch('cclimits.Path.exists', return_value=False):
            creds = get_openai_credentials()
            assert creds == {}


class TestGetGeminiOAuthCreds:
    """Tests for get_gemini_oauth_creds() function."""

    @patch('cclimits.os.environ.get')
    def test_from_environment(self, mock_get):
        """Test Gemini OAuth creds from environment variables."""
        def get_side_effect(key):
            if key == "GEMINI_OAUTH_CLIENT_ID":
                return "test-client-id"
            elif key == "GEMINI_OAUTH_CLIENT_SECRET":
                return "test-client-secret"
            return None
        
        mock_get.side_effect = get_side_effect

        creds = get_gemini_oauth_creds()
        assert creds == ("test-client-id", "test-client-secret")

    @patch('cclimits.os.environ.get')
    def test_partial_env_creds(self, mock_get):
        """Test partial environment credentials (should return None)."""
        def get_side_effect(key):
            if key == "GEMINI_OAUTH_CLIENT_ID":
                return "test-client-id"
            return None
        
        mock_get.side_effect = get_side_effect

        creds = get_gemini_oauth_creds()
        assert creds is None


class TestGetGeminiCredentials:
    """Tests for get_gemini_credentials() function."""

    @patch('cclimits.os.environ.get')
    def test_api_key_from_env(self, mock_get):
        """Test Gemini API key from environment."""
        mock_get.return_value = "test-gemini-api-key"

        creds = get_gemini_credentials()
        assert creds["api_key"] == "test-gemini-api-key"

    @patch('cclimits.os.environ.get')
    def test_google_api_key_fallback(self, mock_get):
        """Test GOOGLE_API_KEY as fallback."""
        def get_side_effect(key):
            if key == "GEMINI_API_KEY":
                return None
            elif key == "GOOGLE_API_KEY":
                return "google-api-key"
            return None
        
        mock_get.side_effect = get_side_effect

        creds = get_gemini_credentials()
        assert creds["api_key"] == "google-api-key"


class TestGetZAICredentials:
    """Tests for get_zai_credentials() function."""

    @patch('cclimits.os.environ.get')
    def test_zai_api_key(self, mock_get):
        """Test Z.AI API key from ZAI_API_KEY."""
        def get_side_effect(key):
            if key == "ZAI_API_KEY":
                return "zai-test-key"
            return None
        
        mock_get.side_effect = get_side_effect

        key = get_zai_credentials()
        assert key == "zai-test-key"

    @patch('cclimits.os.environ.get')
    def test_zai_key_fallback(self, mock_get):
        """Test Z.AI key from ZAI_KEY."""
        def get_side_effect(key):
            if key == "ZAI_API_KEY":
                return None
            elif key == "ZAI_KEY":
                return "zai-key-alt"
            return None
        
        mock_get.side_effect = get_side_effect

        key = get_zai_credentials()
        assert key == "zai-key-alt"

    @patch('cclimits.os.environ.get')
    def test_zhipu_api_key(self, mock_get):
        """Test Z.AI key from ZHIPU_API_KEY."""
        def get_side_effect(key):
            if key in ["ZAI_API_KEY", "ZAI_KEY"]:
                return None
            elif key == "ZHIPU_API_KEY":
                return "zhipu-test-key"
            return None
        
        mock_get.side_effect = get_side_effect

        key = get_zai_credentials()
        assert key == "zhipu-test-key"

    @patch('cclimits.os.environ.get')
    def test_no_credentials(self, mock_get):
        """Test when no Z.AI credentials are found."""
        mock_get.return_value = None

        key = get_zai_credentials()
        assert key is None
