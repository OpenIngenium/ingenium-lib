"""
Tests for project_config.py module
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
import sys

# Import the module under test
import project_config
import common


class TestProjectConfig:
    """Test class for project_config module functionality."""
    
    @patch('project_config.ingenium_rest_get_paginated')
    def test_get_dictionary_versions(self, mock_get_paginated):
        """Test get_dictionary_versions function."""
        mock_get_paginated.return_value = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Test Dict',
                'state': 'PUBLISHED'
            }
        ]
        
        result = project_config.get_dictionary_versions(
            'https://test-server.example.com', 'flight'
        )
        
        assert len(result) == 1
        assert result[0]['dictionary_version'] == 'v1.0'
        mock_get_paginated.assert_called_once()

    @patch('requests.delete')
    def test_delete_dictionary_version_success(self, mock_delete):
        """Test successful dictionary version deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response
        
        with patch('common.response_handler', return_value=True), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            project_config.delete_dictionary_version(
                'https://test-server.example.com', 'flight', 'v1.0'
            )
            
            mock_delete.assert_called_once()

    @patch('requests.delete')
    def test_delete_dictionary_version_failure(self, mock_delete):
        """Test failed dictionary version deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_delete.return_value = mock_response
        
        with patch('common.response_handler', return_value=False), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                project_config.delete_dictionary_version(
                    'https://test-server.example.com', 'flight', 'v1.0'
                )

    @patch('project_config.ingenium_rest_get_paginated')
    def test_get_dictionary(self, mock_get_paginated):
        """Test get_dictionary function."""
        mock_get_paginated.return_value = [
            {'command_stem': 'TEST_CMD', 'cmd_description': 'Test command'}
        ]
        
        result = project_config.get_dictionary(
            'https://test-server.example.com', 'v1.0', 'flight', 'cmds'
        )
        
        assert len(result) == 1
        assert result[0]['command_stem'] == 'TEST_CMD'
        mock_get_paginated.assert_called_once()

    def test_constants_and_endpoints(self):
        """Test that project_config uses correct endpoints and has required functions."""
        # Verify required functions exist
        assert hasattr(project_config, 'get_dictionary_versions')
        assert hasattr(project_config, 'delete_dictionary_version')
        assert hasattr(project_config, 'get_dictionary')
        
        # Verify palette functions exist
        assert hasattr(project_config, 'get_built_in_palette')
        assert hasattr(project_config, 'update_built_in_palette')
        assert hasattr(project_config, 'get_custom_palette')
        assert hasattr(project_config, 'create_custom_palette')
        assert hasattr(project_config, 'update_custom_palette')
        assert hasattr(project_config, 'delete_custom_palette')
        
        # Test that logger is properly configured
        assert hasattr(project_config, 'logger')
        assert project_config.logger.name == 'ingenium.project_config'

    @patch('project_config.ingenium_rest_get')
    def test_get_built_in_palette(self, mock_get):
        """Test get_built_in_palette function."""
        mock_get.return_value = [
            {
                'step_type': 'MANUAL_INPUT',
                'step_display_name': 'Manual Input',
                'enable_disable': True
            }
        ]
        
        result = project_config.get_built_in_palette(
            'https://test-server.example.com', {'step_type': 'MANUAL_INPUT'}
        )
        
        assert len(result) == 1
        assert result[0]['step_type'] == 'MANUAL_INPUT'
        mock_get.assert_called_once()

    @patch('requests.patch')
    def test_update_built_in_palette_success(self, mock_patch):
        """Test successful built-in palette update."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_patch.return_value = mock_response
        
        with patch('common.response_handler', return_value=True), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            result = project_config.update_built_in_palette(
                'https://test-server.example.com', 'MANUAL_INPUT', 
                {'step_display_name': 'Updated Manual Input'}
            )
            
            mock_patch.assert_called_once()

    @patch('project_config.ingenium_rest_get_paginated')
    def test_get_custom_palette(self, mock_get_paginated):
        """Test get_custom_palette function."""
        mock_get_paginated.return_value = [
            {
                'step_id': 123,
                'display_name': 'Custom Step',
                'palette_category': 'Custom'
            }
        ]
        
        result = project_config.get_custom_palette(
            'https://test-server.example.com', {'display_name': 'Custom Step'}
        )
        
        assert len(result) == 1
        assert result[0]['step_id'] == 123
        mock_get_paginated.assert_called_once()

    @patch('requests.post')
    def test_create_custom_palette_success(self, mock_post):
        """Test successful custom palette creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'step_id': 123}
        mock_post.return_value = mock_response
        
        with patch('common.response_handler', return_value=True), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            result = project_config.create_custom_palette(
                'https://test-server.example.com', 
                [{'display_name': 'New Custom Step', 'palette_category': 'Test'}]
            )
            
            assert result['step_id'] == 123
            mock_post.assert_called_once()

    @patch('requests.post')
    def test_create_custom_palette_failure(self, mock_post):
        """Test failed custom palette creation."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        with patch('common.response_handler', return_value=False), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                project_config.create_custom_palette(
                    'https://test-server.example.com', 
                    [{'display_name': 'New Custom Step'}]
                )

    @patch('requests.patch')
    def test_update_custom_palette_success(self, mock_patch):
        """Test successful custom palette update."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'step_id': 123}
        mock_patch.return_value = mock_response
        
        with patch('common.response_handler', return_value=True), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            result = project_config.update_custom_palette(
                'https://test-server.example.com', 123,
                {'display_name': 'Updated Custom Step'}
            )
            
            assert result['step_id'] == 123
            mock_patch.assert_called_once()

    @patch('requests.patch')
    def test_update_custom_palette_failure(self, mock_patch):
        """Test failed custom palette update."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_patch.return_value = mock_response
        
        with patch('common.response_handler', return_value=False), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                project_config.update_custom_palette(
                    'https://test-server.example.com', 123,
                    {'display_name': 'Updated Custom Step'}
                )

    @patch('requests.delete')
    def test_delete_custom_palette_success(self, mock_delete):
        """Test successful custom palette deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response
        
        with patch('common.response_handler', return_value=True), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            project_config.delete_custom_palette(
                'https://test-server.example.com', 123
            )
            
            mock_delete.assert_called_once()

    @patch('requests.delete')
    def test_delete_custom_palette_failure(self, mock_delete):
        """Test failed custom palette deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_delete.return_value = mock_response
        
        with patch('common.response_handler', return_value=False), \
             patch('common.token', 'test_token'), \
             patch('common.ssl_verify', True):
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                project_config.delete_custom_palette(
                    'https://test-server.example.com', 123
                )

    # ---------- Incremental create upload tests ----------

    def _mock_response(self, status_code, json_data):
        """Build a mocked requests response."""
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data
        return response

    def _auth_patches(self):
        """Patch auth header and SSL verification for batched POST tests."""
        return patch('project_config._auth_header', return_value={}), \
               patch('project_config.get_ssl_verify', return_value=True)

    def test_max_upload_batch_size_constant(self):
        """Test the default upload batch size."""
        assert project_config.MAX_UPLOAD_BATCH_SIZE == 10000

    @patch('requests.post')
    def test_create_dictionary_content_single_batch(self, mock_post):
        """Test that content below the limit is sent in one request."""
        content = [{'command_stem': 'TEST_CMD'}]
        mock_post.return_value = self._mock_response(201, content)
        auth, ssl = self._auth_patches()
        with auth, ssl:
            result = project_config.create_dictionary_content(
                'https://test-server.example.com', 'flight', content, 'v1.0', 'cmds'
            )

        assert result == content
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs['json'] == content
        assert mock_post.call_args.args[0].endswith(
            '/dictionaries/flight/versions/v1.0/cmds'
        )

    @pytest.mark.parametrize('dict_type', ['cmds', 'evrs', 'channels', 'mil1553'])
    @patch('requests.post')
    def test_create_dictionary_content_endpoints(self, mock_post, dict_type):
        """Test batching posts to the correct endpoint per dictionary type."""
        mock_post.return_value = self._mock_response(201, [])
        auth, ssl = self._auth_patches()
        with auth, ssl:
            project_config.create_dictionary_content(
                'https://test-server.example.com', 'sse', [{'id': 1}], 'v2.0', dict_type
            )

        assert mock_post.call_args.args[0].endswith(
            f'/dictionaries/sse/versions/v2.0/{dict_type}'
        )

    @patch('requests.post')
    def test_create_dictionary_content_exact_limit(self, mock_post):
        """Test that exactly MAX_UPLOAD_BATCH_SIZE elements still use one request."""
        content = [{'command_stem': f'CMD_{i}'} for i in range(3)]
        mock_post.return_value = self._mock_response(201, content)
        auth, ssl = self._auth_patches()
        with auth, ssl, \
             patch.object(project_config, 'MAX_UPLOAD_BATCH_SIZE', 3):
            result = project_config.create_dictionary_content(
                'https://test-server.example.com', 'flight', content, 'v1.0', 'cmds'
            )

        assert result == content
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs['json'] == content

    @patch('requests.post')
    def test_create_dictionary_content_multiple_batches(self, mock_post):
        """Test that content over the limit is split into ordered batches."""
        content = [{'command_stem': f'CMD_{i}'} for i in range(7)]
        original = list(content)
        mock_post.side_effect = [
            self._mock_response(201, content[0:3]),
            self._mock_response(200, content[3:6]),
            self._mock_response(201, content[6:7]),
        ]
        auth, ssl = self._auth_patches()
        with auth, ssl, \
             patch.object(project_config, 'MAX_UPLOAD_BATCH_SIZE', 3):
            result = project_config.create_dictionary_content(
                'https://test-server.example.com', 'flight', content, 'v1.0', 'cmds'
            )

        assert result == content
        assert content == original
        assert mock_post.call_count == 3
        sent = [call.kwargs['json'] for call in mock_post.call_args_list]
        assert sent == [content[0:3], content[3:6], content[6:7]]
        assert [len(batch) for batch in sent] == [3, 3, 1]
        assert all(
            call.args[0].endswith('/dictionaries/flight/versions/v1.0/cmds')
            for call in mock_post.call_args_list
        )

    @patch('requests.post')
    def test_create_dictionary_content_limit_plus_one(self, mock_post):
        """Test the limit-plus-one boundary produces batches of limit and one."""
        content = [{'command_stem': f'CMD_{i}'} for i in range(4)]
        mock_post.side_effect = [
            self._mock_response(201, content[0:3]),
            self._mock_response(201, content[3:4]),
        ]
        auth, ssl = self._auth_patches()
        with auth, ssl, \
             patch.object(project_config, 'MAX_UPLOAD_BATCH_SIZE', 3):
            result = project_config.create_dictionary_content(
                'https://test-server.example.com', 'flight', content, 'v1.0', 'cmds'
            )

        assert result == content
        sent = [call.kwargs['json'] for call in mock_post.call_args_list]
        assert sent == [content[0:3], content[3:4]]

    @patch('requests.post')
    def test_create_dictionary_content_empty(self, mock_post):
        """Test that empty content still performs a single POST."""
        mock_post.return_value = self._mock_response(201, [])
        auth, ssl = self._auth_patches()
        with auth, ssl:
            result = project_config.create_dictionary_content(
                'https://test-server.example.com', 'flight', [], 'v1.0', 'cmds'
            )

        assert result == []
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs['json'] == []

    @patch('requests.post')
    def test_create_dictionary_content_stops_on_failed_batch(self, mock_post):
        """Test that a failed batch stops the upload without sending later batches."""
        content = [{'command_stem': f'CMD_{i}'} for i in range(7)]
        mock_post.side_effect = [
            self._mock_response(201, content[0:3]),
            self._mock_response(500, {'message': 'server error'}),
            self._mock_response(201, content[6:7]),
        ]
        auth, ssl = self._auth_patches()
        with auth, ssl, \
             patch.object(project_config, 'MAX_UPLOAD_BATCH_SIZE', 3):
            with pytest.raises(project_config.IngeniumLibError):
                project_config.create_dictionary_content(
                    'https://test-server.example.com', 'flight', content, 'v1.0', 'cmds'
                )

        assert mock_post.call_count == 2

    @patch('requests.post')
    def test_create_vnv_vis_multiple_batches(self, mock_post):
        """Test that verification items are batched and responses combined."""
        content = [{'vi_id': f'VI_{i}'} for i in range(5)]
        mock_post.side_effect = [
            self._mock_response(201, content[0:3]),
            self._mock_response(201, content[3:5]),
        ]
        auth, ssl = self._auth_patches()
        with auth, ssl, \
             patch.object(project_config, 'MAX_UPLOAD_BATCH_SIZE', 3):
            result = project_config.create_vnv_vis(
                'https://test-server.example.com', content
            )

        assert result == content
        assert mock_post.call_count == 2
        sent = [call.kwargs['json'] for call in mock_post.call_args_list]
        assert sent == [content[0:3], content[3:5]]
        assert all(
            call.args[0].endswith('/vnv/vis') for call in mock_post.call_args_list
        )

    @patch('requests.post')
    def test_create_vnv_vis_default_batch_size(self, mock_post):
        """Test that the default 10,000 element limit splits 10,001 items in two."""
        content = [{'vi_id': f'VI_{i}'} for i in range(10001)]
        mock_post.side_effect = [
            self._mock_response(201, []),
            self._mock_response(201, []),
        ]
        auth, ssl = self._auth_patches()
        with auth, ssl:
            project_config.create_vnv_vis(
                'https://test-server.example.com', content
            )

        sizes = [len(call.kwargs['json']) for call in mock_post.call_args_list]
        assert sizes == [10000, 1]

    @patch('requests.post')
    def test_create_vnv_vis_connection_error(self, mock_post):
        """Test that a connection error raises IngeniumLibError."""
        mock_post.side_effect = requests.ConnectionError('unreachable')
        auth, ssl = self._auth_patches()
        with auth, ssl:
            with pytest.raises(project_config.IngeniumLibError):
                project_config.create_vnv_vis(
                    'https://test-server.example.com', [{'vi_id': 'VI_0'}]
                )