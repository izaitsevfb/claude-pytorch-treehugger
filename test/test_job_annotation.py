#!/usr/bin/env python3
"""
Unit tests for job annotation functionality
"""

import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta

from pytorch_hud.api.client import PyTorchHudAPI

class JobAnnotationTest(unittest.TestCase):
    """Test suite for job annotation functionality"""
    
    def test_get_job_annotation(self):
        """Test getting job annotations"""
        # Create test data
        end_time = datetime.now().isoformat()
        start_time = (datetime.now() - timedelta(hours=2)).isoformat()
        
        parameters = {
            'branch': 'main',
            'repo': 'pytorch/pytorch',
            'startTime': start_time,
            'stopTime': end_time
        }
        
        # Expected response
        expected_response = {
            "annotations": [
                {"job_id": "12345", "type": "failure", "message": "Test failure"}
            ],
            "count": 1
        }
        
        # Mock the requests module
        with patch('requests.get') as mock_get:
            # Set up the mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_response
            mock_get.return_value = mock_response
            
            # Create API client and call method
            api = PyTorchHudAPI()
            result = api.get_job_annotation('pytorch', 'pytorch', 'failures', parameters)
            
            # Verify the result
            self.assertEqual(result, expected_response)
            
            # Check that requests.get was called with correct URL and params
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            
            # Check URL
            self.assertEqual(args[0], "https://hud.pytorch.org/api/job_annotation/failures")
            
            # Check params - the 'parameters' key should contain a JSON string with all parameters
            self.assertIn('params', kwargs)
            self.assertIn('parameters', kwargs['params'])
            
            # Parse the parameters JSON
            params_dict = json.loads(kwargs['params']['parameters'])
            self.assertEqual(params_dict['branch'], 'main')
            self.assertEqual(params_dict['repo'], 'pytorch/pytorch')
            self.assertEqual(params_dict['startTime'], start_time)
            self.assertEqual(params_dict['stopTime'], end_time)
    
    def test_get_job_annotation_retry_logic(self):
        """Test retry logic for job annotation API calls"""
        # Create parameters
        parameters = {
            'branch': 'main',
            'repo': 'pytorch/pytorch',
            'startTime': '2023-01-01T00:00:00',
            'stopTime': '2023-01-02T00:00:00'
        }
        
        # Set up mock responses: 2 failures followed by a success
        with patch('requests.get') as mock_get:
            # Import the requests exception
            from requests.exceptions import HTTPError
            
            # First two calls raise exceptions
            error_response = MagicMock()
            error_response.status_code = 404
            error_response.raise_for_status.side_effect = HTTPError("404 Client Error: Not Found")
            error_response.json.return_value = {"error": "Not found"}
            
            # Success response
            success_response = MagicMock()
            success_response.status_code = 200
            success_response.json.return_value = {"annotations": [], "count": 0}
            
            # Set up the side effects: two errors, then a success
            mock_get.side_effect = [error_response, error_response, success_response]
            
            # Also need to patch sleep to avoid waiting in tests
            with patch('time.sleep'):
                # Call the method
                api = PyTorchHudAPI()
                # Set lower retry delay for faster tests
                api.retry_delay = 0.001
                result = api.get_job_annotation('pytorch', 'pytorch', 'failures', parameters)
                
                # Verify the result
                self.assertEqual(result, {"annotations": [], "count": 0})
                
                # Check that get was called exactly 3 times
                self.assertEqual(mock_get.call_count, 3)

if __name__ == "__main__":
    unittest.main()