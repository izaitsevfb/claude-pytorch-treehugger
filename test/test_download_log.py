#!/usr/bin/env python3
"""
Unit tests for log download tools
"""

import os
import tempfile
import unittest
import requests
from unittest.mock import patch, MagicMock, AsyncMock

from pytorch_hud.log_analysis.tools import download_log_to_file

class LogDownloadTest(unittest.IsolatedAsyncioTestCase):
    """Test suite for log download tools"""

    def setUp(self):
        """Set up test environment"""
        self.sample_log_content = """
2025-03-06 10:15:22 INFO: Starting PyTorch build
2025-03-06 10:15:25 INFO: Configuring build environment
2025-03-06 10:15:30 WARNING: CUDA version might be outdated
2025-03-06 10:16:10 ERROR: Compilation error in aten/src/ATen/native/cuda/Loss.cu
"""
        self.sample_job_id = "98765432"
        self.sample_s3_url = f"https://ossci-raw-job-status.s3.amazonaws.com/log/{self.sample_job_id}"

    async def test_download_log_to_file(self):
        """Test downloading log to file"""
        # Mock the API client
        with patch('pytorch_hud.log_analysis.tools.api') as mock_api:
            # Configure mocks
            mock_api.download_log.return_value = self.sample_log_content
            mock_api.get_s3_log_url.return_value = self.sample_s3_url
            
            # Create a context mock with async methods
            ctx_mock = MagicMock()
            ctx_mock.info = AsyncMock()
            ctx_mock.error = AsyncMock()
            
            # Run with a temporary directory as cwd
            with tempfile.TemporaryDirectory() as temp_dir:
                # Change to the temp directory
                original_dir = os.getcwd()
                os.chdir(temp_dir)
                
                try:
                    # Verify temp_logs directory doesn't exist yet
                    self.assertFalse(os.path.exists("temp_logs"))
                    
                    # Call the function
                    result = await download_log_to_file(self.sample_job_id, ctx=ctx_mock)
                    
                    # Verify the result
                    self.assertTrue(result["success"])
                    self.assertEqual(result["job_id"], self.sample_job_id)
                    self.assertEqual(result["url"], self.sample_s3_url)
                    
                    # Verify file was created
                    self.assertTrue(os.path.exists("temp_logs"))
                    self.assertTrue(os.path.exists(result["file_path"]))
                    
                    # Verify file content
                    with open(result["file_path"], 'r') as f:
                        content = f.read()
                        self.assertEqual(content, self.sample_log_content)
                    
                    # Verify size and line count
                    self.assertEqual(result["size_bytes"], len(self.sample_log_content))
                    self.assertEqual(result["line_count"], self.sample_log_content.count('\n') + 1)
                    
                    # Verify API calls
                    mock_api.download_log.assert_called_once_with(self.sample_job_id)
                    mock_api.get_s3_log_url.assert_called_once_with(self.sample_job_id)
                    
                    # Verify context logging
                    ctx_mock.info.assert_any_call(f"Downloading log for job {self.sample_job_id}")
                finally:
                    # Restore original directory
                    os.chdir(original_dir)

    async def test_download_log_error_handling(self):
        """Test download log error handling"""
        # Mock the API client
        with patch('pytorch_hud.log_analysis.tools.api') as mock_api:
            # Configure mocks for failure
            mock_api.download_log.side_effect = Exception("Download failed")
            mock_api.get_s3_log_url.return_value = self.sample_s3_url
            
            # Create a context mock with async methods
            ctx_mock = MagicMock()
            ctx_mock.info = AsyncMock()
            ctx_mock.error = AsyncMock()
            
            # Run with a temporary directory as cwd
            with tempfile.TemporaryDirectory() as temp_dir:
                # Change to the temp directory
                original_dir = os.getcwd()
                os.chdir(temp_dir)
                
                try:
                    # Call the function
                    result = await download_log_to_file(self.sample_job_id, ctx=ctx_mock)
                    
                    # Verify error result
                    self.assertFalse(result["success"])
                    self.assertEqual(result["job_id"], self.sample_job_id)
                    self.assertIn("error", result)
                    self.assertIn("Download failed", result["error"])
                    
                    # Verify context error logging
                    ctx_mock.error.assert_called_with("Failed to download log: Download failed")
                finally:
                    # Restore original directory
                    os.chdir(original_dir)
    
    async def test_download_log_to_file_network_error(self):
        """Test downloading log with network errors"""
        # Mock the API client
        with patch('pytorch_hud.log_analysis.tools.api') as mock_api:
            # Configure mocks for network error
            mock_api.download_log.side_effect = requests.exceptions.ConnectionError("Connection refused")
            mock_api.get_s3_log_url.return_value = self.sample_s3_url
            
            # Create a context mock with async methods
            ctx_mock = MagicMock()
            ctx_mock.info = AsyncMock()
            ctx_mock.error = AsyncMock()
            
            # Run with a temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Change to the temp directory
                original_dir = os.getcwd()
                os.chdir(temp_dir)
                
                try:
                    # Call the function
                    result = await download_log_to_file(self.sample_job_id, ctx=ctx_mock)
                    
                    # Verify error result
                    self.assertFalse(result["success"])
                    self.assertEqual(result["job_id"], self.sample_job_id)
                    self.assertIn("error", result)
                    self.assertIn("Connection refused", result["error"])
                finally:
                    # Restore original directory
                    os.chdir(original_dir)

if __name__ == "__main__":
    unittest.main()