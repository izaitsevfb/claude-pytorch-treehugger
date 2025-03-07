#!/usr/bin/env python3
"""
Unit tests for log search tools
"""

import unittest
from unittest.mock import patch

from pytorch_hud.log_analysis.tools import search_logs

class LogSearchTest(unittest.TestCase):
    """Test suite for log search tools"""

    def setUp(self):
        """Set up test environment"""
        self.sample_search_results = {
            "matches": [
                {
                    "job_id": "123456",
                    "workflow": "linux-build",
                    "repository": "pytorch/pytorch",
                    "lines": [
                        {"line_number": 1024, "text": "CUDA error: device-side assert triggered"},
                        {"line_number": 1025, "text": "CUDA error: an illegal memory access was encountered"}
                    ]
                },
                {
                    "job_id": "789012",
                    "workflow": "windows-test",
                    "repository": "pytorch/pytorch",
                    "lines": [
                        {"line_number": 523, "text": "CUDA error: out of memory"}
                    ]
                }
            ],
            "total_matches": 2,
            "total_lines": 3
        }

    def test_search_logs(self):
        """Test searching logs with various parameters"""
        # Mock the API client
        with patch('pytorch_hud.log_analysis.tools.api') as mock_api:
            mock_api.search_logs.return_value = self.sample_search_results
            
            # Test without filters
            result = search_logs("CUDA error")
            self.assertEqual(result, self.sample_search_results)
            mock_api.search_logs.assert_called_once_with("CUDA error", repo=None, workflow=None)
            
            # Reset mock
            mock_api.reset_mock()
            
            # Test with repo filter
            result = search_logs("CUDA error", repo="pytorch/pytorch")
            self.assertEqual(result, self.sample_search_results)
            mock_api.search_logs.assert_called_once_with("CUDA error", repo="pytorch/pytorch", workflow=None)
            
            # Reset mock
            mock_api.reset_mock()
            
            # Test with workflow filter
            result = search_logs("CUDA error", workflow="linux-build")
            self.assertEqual(result, self.sample_search_results)
            mock_api.search_logs.assert_called_once_with("CUDA error", repo=None, workflow="linux-build")
            
            # Reset mock
            mock_api.reset_mock()
            
            # Test with both filters
            result = search_logs("CUDA error", repo="pytorch/pytorch", workflow="linux-build")
            self.assertEqual(result, self.sample_search_results)
            mock_api.search_logs.assert_called_once_with("CUDA error", repo="pytorch/pytorch", workflow="linux-build")

if __name__ == "__main__":
    unittest.main()