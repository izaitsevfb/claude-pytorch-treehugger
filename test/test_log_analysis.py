#!/usr/bin/env python3
"""
Unit tests for log analysis tools
"""

import os
import tempfile
import unittest
import requests
from unittest.mock import patch, MagicMock, AsyncMock

from pytorch_hud import PyTorchHudAPI
from pytorch_hud.log_analysis.tools import extract_log_patterns, extract_test_results, filter_log_sections, search_logs
from pytorch_hud.log_analysis.tools import get_artifacts, get_s3_log_url

class LogAnalysisTest(unittest.IsolatedAsyncioTestCase):
    """Test suite for log analysis tools"""

    def setUp(self):
        """Set up test environment"""
        # Create a sample log file
        self.sample_log = """
2025-03-06 10:15:22 INFO: Starting PyTorch build
2025-03-06 10:15:25 INFO: Configuring build environment
2025-03-06 10:15:30 WARNING: CUDA version might be outdated
2025-03-06 10:15:45 INFO: Building PyTorch
2025-03-06 10:16:10 ERROR: Compilation error in aten/src/ATen/native/cuda/Loss.cu
2025-03-06 10:16:15 ERROR: undefined reference to 'cudaLaunchKernel'
2025-03-06 10:16:20 INFO: Build failed
2025-03-06 10:16:25 INFO: Attempting to run tests anyway
2025-03-06 10:16:30 INFO: Running tests
============================== test session starts ==============================
test_basic.py::TestBasic::test_addition ... passed
test_basic.py::TestBasic::test_subtraction ... passed
test_tensor.py::TestTensor::test_reshape ... ERROR
test_tensor.py::TestTensor::test_device ... FAILED
test_tensor.py::TestTensor::test_dtype ... passed
test_nn.py::TestNN::test_linear ... skipped (not implemented)
======================= 3 passed, 1 failed, 1 error, 1 skipped in 5.2s ====================
2025-03-06 10:17:30 ERROR: OutOfMemoryError: CUDA out of memory. Tried to allocate 2.50 GiB
2025-03-06 10:17:35 INFO: Test run complete
"""
        
        # Create a temporary file
        fd, self.log_path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write(self.sample_log)
    
    def tearDown(self):
        """Clean up after tests"""
        os.unlink(self.log_path)
    
    def test_api_wrappers(self):
        """Test that API wrapper functions correctly call the API client"""
        # Mock the API client
        with patch('pytorch_hud.log_analysis.tools.api') as mock_api:
            # Set up return values
            mock_api.get_artifacts.return_value = {"artifacts": []}
            mock_api.get_s3_log_url.return_value = "https://example.com/logs/123456"
            mock_api.search_logs.return_value = {"results": []}
            
            # Test the wrapper functions
            job_id = "123456"
            artifacts = get_artifacts("s3", job_id)
            log_url = get_s3_log_url(job_id)
            search_result = search_logs("error", repo="pytorch/pytorch")
            
            # Verify correct API methods were called
            mock_api.get_artifacts.assert_called_once_with("s3", job_id)
            mock_api.get_s3_log_url.assert_called_once_with(job_id)
            mock_api.search_logs.assert_called_once_with("error", repo="pytorch/pytorch", workflow=None)
            
            # Verify returned values
            self.assertEqual(artifacts, {"artifacts": []})
            self.assertEqual(log_url, "https://example.com/logs/123456")
            self.assertEqual(search_result, {"results": []})
    
    def test_download_log(self):
        """Test downloading log content"""
        api = PyTorchHudAPI()
        
        # Mock the requests.get method
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = self.sample_log
            mock_get.return_value = mock_response
            
            # Call the method
            result = api.download_log("123456")
            
            # Verify the result
            self.assertEqual(result, self.sample_log)
            mock_get.assert_called_once_with("https://ossci-raw-job-status.s3.amazonaws.com/log/123456")
    
    def test_download_log_error(self):
        """Test handling of download errors"""
        api = PyTorchHudAPI()
        
        # Mock the requests.get method to raise an exception
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException("Connection refused")
            
            # Verify that the exception is propagated correctly
            with self.assertRaises(Exception) as context:
                api.download_log("123456")
            
            # Check that the exception message includes the original error
            self.assertIn("Connection refused", str(context.exception))
    
    async def test_extract_log_patterns(self):
        """Test extracting patterns from log file"""
        # Create a context mock with async methods
        ctx_mock = MagicMock()
        ctx_mock.info = AsyncMock()
        ctx_mock.error = AsyncMock()
        ctx_mock.warning = AsyncMock()
        
        # Run the function
        result = await extract_log_patterns(self.log_path, ctx=ctx_mock)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertTrue("error" in result["counts"])
        self.assertTrue("warning" in result["counts"])
        
        # Check counts
        self.assertEqual(result["counts"]["error"], 3)  
        self.assertEqual(result["counts"]["warning"], 1)
        
        # Check samples
        self.assertEqual(len(result["samples"]["error"]), 3)
        self.assertEqual(len(result["samples"]["warning"]), 1)
        
        # Test with custom patterns
        custom_result = await extract_log_patterns(
            self.log_path,
            patterns={
                "cuda_issues": r"CUDA|cudaLaunch",
                "memory_issues": r"OutOfMemoryError|OOM"
            },
            ctx=ctx_mock
        )
        
        self.assertTrue(custom_result["success"])
        self.assertEqual(custom_result["counts"]["cuda_issues"], 3)
        self.assertEqual(custom_result["counts"]["memory_issues"], 1)
        
        # Test with non-existent file
        invalid_result = await extract_log_patterns("/nonexistent/file.log", ctx=ctx_mock)
        self.assertFalse(invalid_result["success"])
        self.assertIn("error", invalid_result)
        self.assertIn("File not found", invalid_result["error"])
    
    async def test_extract_test_results(self):
        """Test extracting test results from log file"""
        # Create a context mock with async methods
        ctx_mock = MagicMock()
        ctx_mock.info = AsyncMock()
        ctx_mock.error = AsyncMock()
        ctx_mock.warning = AsyncMock()
        
        # Run the function
        result = await extract_test_results(self.log_path, ctx=ctx_mock)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["test_counts"])
        
        # Test with both pytest and unittest patterns
        # Log for pytest that we expect it to match
        pytest_log = """
Running pytest tests...
============================= test session starts ==============================
test_foo.py::test_something PASSED
test_bar.py::test_other FAILED
====================== 1 failed, 1 passed, 0 skipped in 0.5s =================
"""
        # Create a temporary file with pytest output
        fd, pytest_log_path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write(pytest_log)
        
        try:
            # Test pytest pattern matching
            pytest_result = await extract_test_results(pytest_log_path, ctx=ctx_mock)
            self.assertTrue(pytest_result["success"])
            
            # Verify it recognized the pytest summary format
            self.assertEqual(pytest_result["test_counts"]["failed"], 1)
            self.assertEqual(pytest_result["test_counts"]["passed"], 1)
            self.assertEqual(pytest_result["test_counts"]["skipped"], 0)
            self.assertEqual(pytest_result["test_counts"]["total"], 2)
        finally:
            os.unlink(pytest_log_path)
        
        # Test with non-existent file
        invalid_result = await extract_test_results("/nonexistent/file.log", ctx=ctx_mock)
        self.assertFalse(invalid_result["success"])
        self.assertIn("error", invalid_result)
        self.assertIn("File not found", invalid_result["error"])
    
    async def test_filter_log_sections(self):
        """Test filtering log sections by patterns"""
        # Create a context mock with async methods
        ctx_mock = MagicMock()
        ctx_mock.info = AsyncMock()
        ctx_mock.error = AsyncMock()
        ctx_mock.warning = AsyncMock()
        
        # Run the function to get test session section
        result = await filter_log_sections(
            self.log_path,
            start_pattern=r"====+ test session starts ====+",
            end_pattern=r"====+ .* in \d+\.\ds ====+",
            ctx=ctx_mock
        )
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["section_count"], 1)
        self.assertIn("test session starts", result["sections"][0]["content"])
        self.assertIn("3 passed, 1 failed, 1 error, 1 skipped", result["sections"][0]["content"])
        
        # Test with max_lines limitation
        limited_result = await filter_log_sections(
            self.log_path,
            start_pattern=r"INFO: Starting PyTorch build",
            max_lines=3,
            ctx=ctx_mock
        )
        
        self.assertTrue(limited_result["success"])
        self.assertEqual(limited_result["section_count"], 1)
        self.assertTrue(limited_result["sections"][0]["truncated"])
        self.assertEqual(len(limited_result["sections"][0]["content"].split("\n")), 4)  # 3 lines + truncation note
        
        # Test with missing start pattern
        missing_start_result = await filter_log_sections(
            self.log_path,
            start_pattern=None,
            ctx=ctx_mock
        )
        
        self.assertFalse(missing_start_result["success"])
        self.assertIn("error", missing_start_result)
        self.assertIn("Start pattern is required", missing_start_result["error"])
        
        # Test with invalid file
        invalid_result = await filter_log_sections(
            "/nonexistent/file.log",
            start_pattern="pattern",
            ctx=ctx_mock
        )
        
        self.assertFalse(invalid_result["success"])
        self.assertIn("error", invalid_result)
        self.assertIn("File not found", invalid_result["error"])

if __name__ == "__main__":
    unittest.main()