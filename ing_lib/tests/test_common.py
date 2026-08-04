"""
Tests for common.py module
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
import sys
import datetime

# Import the module under test
import common

# Test constants
MOCK_BASE_URL = "https://mock-ingenium.example.com"
MOCK_API_ENDPOINT = f"{MOCK_BASE_URL}/api/v1/test"


class TestCommon:
    """Test class for common module functionality."""
    
    def test_ingenium_lib_error(self):
        """Test IngeniumLibError exception."""
        error_msg = "Test error message"
        
        with pytest.raises(common.IngeniumLibError) as exc_info:
            raise common.IngeniumLibError(error_msg)
        
        assert str(exc_info.value) == error_msg

    def test_response_handler_success(self):
        """Test response_handler with successful response codes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = MOCK_API_ENDPOINT
        mock_response.request.method = "GET"
        
        result = common.response_handler(mock_response)
        assert result is True

    def test_response_handler_created(self):
        """Test response_handler with 201 Created status."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        
        result = common.response_handler(mock_response)
        assert result is True

    def test_response_handler_accepted(self):
        """Test response_handler with 202 Accepted status."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        
        result = common.response_handler(mock_response)
        assert result is True

    def test_response_handler_no_content(self):
        """Test response_handler with 204 No Content status."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        result = common.response_handler(mock_response)
        assert result is True

    def test_response_handler_failure(self):
        """Test response_handler with failure status codes."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = MOCK_API_ENDPOINT
        mock_response.request.method = "GET"
        mock_response.text = "Not Found"
        
        result = common.response_handler(mock_response)
        assert result is False

    def test_response_handler_bad_request(self):
        """Test response_handler with 400 Bad Request status."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.url = MOCK_API_ENDPOINT
        mock_response.request.method = "POST"
        mock_response.text = '{"error": "Invalid request"}'
        
        result = common.response_handler(mock_response)
        assert result is False

    @patch('requests.get')

    def test_ingenium_rest_get_success(self, mock_get):
        """Test successful ingenium_rest_get call."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test", "status": "success"}
        mock_get.return_value = mock_response
        
        # Set up token
        common.set_token("test_token")
        common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc))
        common.set_ssl_verify(True)
        
        result = common.ingenium_rest_get(MOCK_API_ENDPOINT)
        
        assert result == {"data": "test", "status": "success"}
        mock_get.assert_called_once_with(
            MOCK_API_ENDPOINT,
            headers={'Authorization': 'test_token'},
            verify=True,
            params={}
        )

    @patch('requests.get')
    def test_ingenium_rest_get_failure(self, mock_get):
        """Test failed ingenium_rest_get call should raise IngeniumLibError."""
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.url = MOCK_API_ENDPOINT
        mock_response.request.method = "GET"
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response
        
        common.set_token("test_token")
        common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc))
        
        # Should raise IngeniumLibError on failure
        with pytest.raises(common.IngeniumLibError) as exc_info:
            common.ingenium_rest_get(MOCK_API_ENDPOINT)
        
        assert "Response not completed successfully" in str(exc_info.value)
        assert MOCK_API_ENDPOINT in str(exc_info.value)

    def test_constants(self):
        """Test that constants are defined correctly."""
        assert common._TOKEN_REFRESH_DURATION == 3000
        assert common._TOKEN_DURATION == 3600
        assert hasattr(common, 'auth_endpoint')
        assert hasattr(common, 'refresh_endpoint')
        assert hasattr(common, 'venue_endpoint')
        assert hasattr(common, 'dictionary_endpoint')

    def test_global_variables_initialization(self):
        """Test that global variables are properly initialized."""
        # Reset globals to test initial state
        common.token = None
        common.ssl_verify = True
        common.refresh_time = None
        
        assert common.token is None
        assert common.ssl_verify is True
        assert common.refresh_time is None

    @patch('requests.get')
    def test_ingenium_rest_get_with_ssl_disabled(self, mock_get):
        """Test ingenium_rest_get with SSL verification disabled."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test_ssl_disabled"}
        mock_get.return_value = mock_response
        
        common.set_token("test_token")
        common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc))
        common.set_ssl_verify(False)
        
        result = common.ingenium_rest_get(MOCK_API_ENDPOINT)
        
        assert result == {"data": "test_ssl_disabled"}
        mock_get.assert_called_once_with(
            MOCK_API_ENDPOINT,
            headers={'Authorization': 'test_token'},
            verify=False,
            params={}
        )

    @patch('requests.get')
    def test_ingenium_rest_get_connection_error(self, mock_get):
        """Test ingenium_rest_get with connection error."""
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        common.set_token("test_token")
        common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc))
        
        # Should raise the ConnectionError, not handle it gracefully
        with pytest.raises(requests.ConnectionError):
            common.ingenium_rest_get(MOCK_API_ENDPOINT)

    def test_endpoints_format(self):
        """Test that endpoint strings are properly formatted."""
        assert common.auth_endpoint.startswith("/")
        assert common.refresh_endpoint.startswith("/")
        assert common.venue_endpoint.startswith("/")
        assert common.dictionary_endpoint.startswith("/")
        assert common.dictionary_endpoint.endswith("/")

    @patch('requests.get')
    def test_ingenium_rest_get_json_decode_error(self, mock_get):
        """Test ingenium_rest_get with JSON decode error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        common.set_token("test_token")
        common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc))
        
        # Should raise the JSON decode error
        with pytest.raises(ValueError):
            common.ingenium_rest_get(MOCK_API_ENDPOINT)

    def test_ssl_verify_setting(self):
        """Test SSL verify setting changes."""
        # Test setting to string (CA bundle path)
        common.ssl_verify = "/path/to/ca-bundle.crt"
        assert common.ssl_verify == "/path/to/ca-bundle.crt"
        
        # Test setting to boolean
        common.ssl_verify = True
        assert common.ssl_verify is True
        
        common.ssl_verify = False
        assert common.ssl_verify is False

    def test_token_setting(self):
        """Test token setting and retrieval."""
        test_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        common.token = test_token
        assert common.token == test_token
        
        # Test clearing token
        common.token = None
        assert common.token is None

    @patch('requests.get')
    def test_ingenium_rest_get_paginated_success(self, mock_get):
        """Test successful ingenium_rest_get_paginated call."""
        # Mock successful response with pagination headers
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"item": 1}, {"item": 2}]
        mock_response.headers = {'x-total-count': '2'}
        mock_get.return_value = mock_response
        
        common.set_token("test_token")
        common.set_ssl_verify(True)
        common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc))
        
        result = common.ingenium_rest_get_paginated(MOCK_API_ENDPOINT)
        
        assert result == [{"item": 1}, {"item": 2}]
        mock_get.assert_called_once()
        
        # Verify the call included pagination parameters
        call_args = mock_get.call_args
        assert 'params' in call_args.kwargs
        assert call_args.kwargs['params']['limit'] == 1000
        assert call_args.kwargs['params']['offset'] == 0

    @patch('requests.get')
    def test_authenticate_success(self, mock_get):
        """Test successful authenticate call."""
        # Mock successful authentication response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"access_token": "mock_access_token"}'
        mock_get.return_value = mock_response
        
        # Clear existing token to test fresh authentication
        common.set_token(None)
        
        result = common.authenticate(MOCK_BASE_URL, username="testuser", password="testpass")
        
        assert result is True
        assert common.get_token() == "Bearer mock_access_token"
        
        # Verify the authentication endpoint was called
        expected_url = f"{MOCK_BASE_URL}{common.auth_endpoint}"
        mock_get.assert_called_once()
        assert mock_get.call_args[0][0] == expected_url

    @patch('requests.post')
    def test_refresh_auth_success(self, mock_post):
        """Test successful refresh_auth call."""
        # Mock successful refresh response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"access_token": "refreshed_access_token"}'
        mock_post.return_value = mock_response
        
        # Set existing token
        common.set_token("Bearer old_token")
        common.set_ssl_verify(True)
        common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=3000))
        
        result = common.refresh_auth(MOCK_BASE_URL, force=True)
        
        assert result is True
        assert common.get_token() == "Bearer refreshed_access_token"
        
        # Verify the refresh endpoint was called
        expected_url = f"{MOCK_BASE_URL}{common.refresh_endpoint}"
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == expected_url 