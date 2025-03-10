#!/usr/bin/env python3
"""
Unit tests for the find_commits_with_similar_failures function
(with backward compatibility for search_logs)
"""

import unittest
from unittest.mock import patch

from pytorch_hud.log_analysis.tools import find_commits_with_similar_failures

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

    def test_find_commits_with_similar_failures(self):
        """Test searching logs with various parameters"""
        # Mock the API client
        with patch('pytorch_hud.log_analysis.tools.api') as mock_api:
            mock_api.find_commits_with_similar_failures.return_value = self.sample_search_results
            
            # Test without filters
            result = find_commits_with_similar_failures("CUDA error")
            self.assertEqual(result, self.sample_search_results)
            mock_api.find_commits_with_similar_failures.assert_called_once_with(
                failure="CUDA error", 
                repo=None, 
                workflow_name=None, 
                branch_name=None,
                start_date=None, 
                end_date=None,
                min_score=1.0
            )
            
            # Reset mock
            mock_api.reset_mock()
            
            # Test with repo filter
            result = find_commits_with_similar_failures("CUDA error", repo="pytorch/pytorch")
            self.assertEqual(result, self.sample_search_results)
            mock_api.find_commits_with_similar_failures.assert_called_once_with(
                failure="CUDA error", 
                repo="pytorch/pytorch", 
                workflow_name=None, 
                branch_name=None,
                start_date=None, 
                end_date=None,
                min_score=1.0
            )
            
            # Reset mock
            mock_api.reset_mock()
            
            # Test with workflow filter
            result = find_commits_with_similar_failures("CUDA error", workflow_name="linux-build")
            self.assertEqual(result, self.sample_search_results)
            mock_api.find_commits_with_similar_failures.assert_called_once_with(
                failure="CUDA error", 
                repo=None, 
                workflow_name="linux-build", 
                branch_name=None,
                start_date=None, 
                end_date=None,
                min_score=1.0
            )
            
            # Reset mock
            mock_api.reset_mock()
            
            # Test with multiple filters
            result = find_commits_with_similar_failures(
                "CUDA error", 
                repo="pytorch/pytorch", 
                workflow_name="linux-build",
                branch_name="main",
                start_date="2023-01-01T00:00:00Z",
                end_date="2023-01-07T00:00:00Z",
                min_score=1.5
            )
            self.assertEqual(result, self.sample_search_results)
            mock_api.find_commits_with_similar_failures.assert_called_once_with(
                failure="CUDA error", 
                repo="pytorch/pytorch", 
                workflow_name="linux-build", 
                branch_name="main",
                start_date="2023-01-01T00:00:00Z", 
                end_date="2023-01-07T00:00:00Z",
                min_score=1.5
            )

if __name__ == "__main__":
    unittest.main()