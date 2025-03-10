#!/usr/bin/env python3
"""
Test for find_commits_with_similar_failures_resource MCP endpoint
(with backward compatibility support for search_logs_resource)
"""

import unittest
import json
import sys
import os
from unittest.mock import patch

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytorch_hud.server.mcp_server import search_logs_resource

class TestSearchLogsResource(unittest.TestCase):
    """Test suite for search_logs_resource endpoint"""
    
    @patch('pytorch_hud.server.mcp_server.find_commits_with_similar_failures')
    def test_search_logs_resource(self, mock_find_commits):
        """Test the search_logs_resource endpoint."""
        mock_search_result = {
            "matches": [
                {
                    "job_id": "12345",
                    "workflow": "linux-build",
                    "repository": "pytorch/pytorch",
                    "lines": [
                        {"line_number": 1024, "text": "PACKAGES DO NOT MATCH THE HASHES"}
                    ]
                }
            ],
            "total_matches": 1
        }
        mock_find_commits.return_value = mock_search_result
        
        # Test with minimal required parameters
        result = json.loads(search_logs_resource("PACKAGES DO NOT MATCH THE HASHES"))
        self.assertEqual(result, mock_search_result)
        mock_find_commits.assert_called_once_with(
            failure="PACKAGES DO NOT MATCH THE HASHES",
            repo=None,
            workflow_name=None,
            branch_name=None,
            start_date=None,
            end_date=None,
            min_score=1.0
        )
        
        # Reset mock
        mock_find_commits.reset_mock()
        
        # Test with all parameters
        result = json.loads(search_logs_resource(
            query="PACKAGES DO NOT MATCH THE HASHES",
            repo="pytorch/pytorch",
            workflow="linux-build",
            branch="main",
            start_date="2023-01-01T00:00:00Z",
            end_date="2023-01-07T00:00:00Z",
            min_score=0.8
        ))
        self.assertEqual(result, mock_search_result)
        mock_find_commits.assert_called_once_with(
            failure="PACKAGES DO NOT MATCH THE HASHES",
            repo="pytorch/pytorch",
            workflow_name="linux-build",
            branch_name="main",
            start_date="2023-01-01T00:00:00Z",
            end_date="2023-01-07T00:00:00Z",
            min_score=0.8
        )

if __name__ == "__main__":
    unittest.main()