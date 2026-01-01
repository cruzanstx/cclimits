"""
Tests for HTTP client functions (requests and urllib fallback).
"""

import json
from unittest.mock import patch, MagicMock
import pytest
from cclimits import http_get, http_post


class TestHTTPGetWithRequests:
    """Tests for http_get() with requests library."""

    @patch('cclimits.requests')
    def test_successful_json_response(self, mock_requests):
        """Test successful GET request returning JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_requests.get.return_value = mock_response

        status, data = http_get("https://example.com/api", {"Authorization": "Bearer test"})

        assert status == 200
        assert data == {"data": "test"}
        mock_requests.get.assert_called_once_with(
            "https://example.com/api",
            headers={"Authorization": "Bearer test"},
            timeout=10
        )

    @patch('cclimits.requests')
    def test_successful_text_response(self, mock_requests):
        """Test successful GET request returning text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "plain text response"
        mock_requests.get.return_value = mock_response

        status, data = http_get("https://example.com/api", {})

        assert status == 200
        assert data == "plain text response"

    @patch('cclimits.requests')
    def test_error_response_404(self, mock_requests):
        """Test 404 error response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Not Found"
        mock_requests.get.return_value = mock_response

        status, data = http_get("https://example.com/notfound", {})

        assert status == 404
        assert data == "Not Found"

    @patch('cclimits.requests')
    def test_timeout_error(self, mock_requests):
        """Test timeout error."""
        import requests
        mock_requests.get.side_effect = requests.Timeout("Connection timeout")

        status, data = http_get("https://example.com/slow", {})

        assert status == 0
        assert "timeout" in data.lower() or "connection" in data.lower()

    @patch('cclimits.requests')
    def test_connection_error(self, mock_requests):
        """Test connection error."""
        import requests
        mock_requests.get.side_effect = requests.ConnectionError("Failed to connect")

        status, data = http_get("https://example.com/api", {})

        assert status == 0
        assert "connection" in data.lower()


class TestHTTPGetWithUrllib:
    """Tests for http_get() with urllib fallback."""

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.request.urlopen')
    def test_successful_json_response(self, mock_urlopen):
        """Test successful GET request returning JSON."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"data": "test"}'
        mock_urlopen.return_value = mock_response

        status, data = http_get("https://example.com/api", {"Authorization": "Bearer test"})

        assert status == 200
        assert data == {"data": "test"}

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.request.urlopen')
    def test_successful_text_response(self, mock_urlopen):
        """Test successful GET request returning text."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'plain text response'
        mock_urlopen.return_value = mock_response

        status, data = http_get("https://example.com/api", {})

        assert status == 200
        assert data == "plain text response"

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.error.HTTPError')
    @patch('cclimits.urllib.request.urlopen')
    def test_http_error(self, mock_urlopen, mock_http_error):
        """Test HTTP error (e.g., 404, 401)."""
        mock_urlopen.side_effect = mock_http_error(404, "Not Found", {}, None)

        status, data = http_get("https://example.com/notfound", {})

        assert status == 404
        assert data == "Not Found"

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.request.urlopen')
    def test_timeout_error(self, mock_urlopen):
        """Test timeout error."""
        import socket
        mock_urlopen.side_effect = socket.timeout("Timeout")

        status, data = http_get("https://example.com/slow", {})

        assert status == 0
        assert "timeout" in data.lower()

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.request.urlopen')
    def test_headers_passed_correctly(self, mock_urlopen):
        """Test that headers are passed correctly to urllib."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value = mock_response

        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        http_get("https://example.com/api", headers)

        # Verify the request was made
        assert mock_urlopen.called


class TestHTTPPostWithRequests:
    """Tests for http_post() with requests library."""

    @patch('cclimits.requests')
    def test_successful_json_response(self, mock_requests):
        """Test successful POST request returning JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_requests.post.return_value = mock_response

        body = {"key": "value"}
        status, data = http_post("https://example.com/api", {}, body)

        assert status == 200
        assert data == {"success": True}
        mock_requests.post.assert_called_once_with(
            "https://example.com/api",
            headers={},
            json=body,
            timeout=10
        )

    @patch('cclimits.requests')
    def test_successful_text_response(self, mock_requests):
        """Test successful POST request returning text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "OK"
        mock_requests.post.return_value = mock_response

        status, data = http_post("https://example.com/api", {}, {})

        assert status == 200
        assert data == "OK"

    @patch('cclimits.requests')
    def test_error_401(self, mock_requests):
        """Test 401 unauthorized error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Unauthorized"
        mock_requests.post.return_value = mock_response

        status, data = http_post("https://example.com/api", {}, {})

        assert status == 401
        assert data == "Unauthorized"

    @patch('cclimits.requests')
    def test_timeout(self, mock_requests):
        """Test timeout on POST."""
        import requests
        mock_requests.post.side_effect = requests.Timeout("Request timeout")

        status, data = http_post("https://example.com/api", {}, {})

        assert status == 0


class TestHTTPPostWithUrllib:
    """Tests for http_post() with urllib fallback."""

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.request.urlopen')
    def test_successful_json_response(self, mock_urlopen):
        """Test successful POST request returning JSON."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value = mock_response

        body = {"key": "value"}
        status, data = http_post("https://example.com/api", {}, body)

        assert status == 200
        assert data == {"success": True}

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.request.urlopen')
    def test_successful_text_response(self, mock_urlopen):
        """Test successful POST request returning text."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'OK'
        mock_urlopen.return_value = mock_response

        status, data = http_post("https://example.com/api", {}, {})

        assert status == 200
        assert data == "OK"

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.error.HTTPError')
    @patch('cclimits.urllib.request.urlopen')
    def test_http_error(self, mock_urlopen, mock_http_error):
        """Test HTTP error on POST."""
        mock_urlopen.side_effect = mock_http_error(401, "Unauthorized", {}, None)

        status, data = http_post("https://example.com/api", {}, {})

        assert status == 401
        assert data == "Unauthorized"

    @patch('cclimits.HAS_REQUESTS', False)
    @patch('cclimits.urllib.request.urlopen')
    def test_body_encoding(self, mock_urlopen):
        """Test that POST body is encoded correctly."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value = mock_response

        body = {"test": "data"}
        http_post("https://example.com/api", {}, body)

        # Verify the request was made
        assert mock_urlopen.called
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert request_obj.method == 'POST'
        # Body should be JSON-encoded
        import json
        assert request_obj.data == json.dumps(body).encode('utf-8')
