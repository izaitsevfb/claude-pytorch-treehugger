#!/usr/bin/env python3
"""
Unit tests for job details tools
"""

import unittest
from unittest.mock import patch, MagicMock
from test.utils import create_async_mock_context

from pytorch_hud.tools.hud_data import get_job_details

class JobDetailsTest(unittest.IsolatedAsyncioTestCase):
    """Test suite for job details tools"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock API responses - these match the real API structure
        self.expected_log_url = "https://ossci-raw-job-status.s3.amazonaws.com/log/123456"
        self.expected_artifacts = {
            "artifacts": [
                {"name": "artifact1.txt", "url": "https://api.github.com/artifacts/123"},
                {"name": "artifact2.zip", "url": "https://api.github.com/artifacts/456"}
            ]
        }
        
    async def test_get_job_details(self):
        """Test getting job details"""
        # Create API mock
        api_mock = MagicMock()
        api_mock.get_s3_log_url.return_value = self.expected_log_url
        api_mock.get_artifacts.return_value = self.expected_artifacts
        
        # Mock the API client
        with patch('pytorch_hud.tools.hud_data.api', api_mock):
            # Call the function
            job_id = "123456"
            result = await get_job_details(job_id)
            
            # Verify the result
            self.assertEqual(result["job_id"], job_id)
            self.assertEqual(result["log_url"], self.expected_log_url)
            self.assertEqual(result["artifacts"], self.expected_artifacts)
            
            # Make sure the API methods were called correctly
            api_mock.get_s3_log_url.assert_called_once_with(job_id)
            api_mock.get_artifacts.assert_called_once_with("s3", job_id)

    async def test_get_job_details_with_failures(self):
        """Test getting job details with API failures"""
        # Create API mock with artifacts failure
        api_mock = MagicMock()
        api_mock.get_s3_log_url.return_value = self.expected_log_url
        api_mock.get_artifacts.side_effect = Exception("Failed to get artifacts")
        
        # Mock the API client
        with patch('pytorch_hud.tools.hud_data.api', api_mock):
            # Call the function
            job_id = "123456"
            result = await get_job_details(job_id)
            
            # Verify the result handles the failure gracefully
            self.assertEqual(result["job_id"], job_id)
            self.assertEqual(result["log_url"], self.expected_log_url)
            self.assertIsNone(result["artifacts"])  # Should be None due to failure
            
            # Make sure the API methods were still called
            api_mock.get_s3_log_url.assert_called_once_with(job_id)
            api_mock.get_artifacts.assert_called_once_with("s3", job_id)
            
    # Removed test_get_job_details_with_all_failures as we no longer have multiple API calls that can fail
            
    async def test_get_job_details_with_context(self):
        """Test getting job details with MCP context"""
        # Create API mock
        api_mock = MagicMock()
        api_mock.get_s3_log_url.return_value = self.expected_log_url
        api_mock.get_artifacts.return_value = self.expected_artifacts
        
        # Create a mock context with async methods
        ctx_mock = create_async_mock_context()
        
        # Mock the API client
        with patch('pytorch_hud.tools.hud_data.api', api_mock):
            # Call the function with context
            job_id = "123456"
            result = await get_job_details(job_id, ctx=ctx_mock)
            
            # Verify the result
            self.assertEqual(result["job_id"], job_id)
            self.assertEqual(result["log_url"], self.expected_log_url)
            
            # Verify context was used for logging
            ctx_mock.info.assert_called_with(f"Fetching detailed information for job {job_id}")

if __name__ == "__main__":
    unittest.main()