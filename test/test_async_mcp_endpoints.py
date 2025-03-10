#!/usr/bin/env python3
"""
Comprehensive test for async MCP resource endpoints

This test script ensures that all async functions in the PyTorch HUD API are properly
exposed via resource endpoints in the MCP server and that these endpoints correctly
await the underlying async functions.
"""

import json
import unittest
from unittest.mock import patch

# Import the resource endpoints from MCP server
from pytorch_hud.server.mcp_server import (
    get_job_details_resource, get_recent_commits_with_jobs_resource
)

class TestAsyncMCPEndpoints(unittest.IsolatedAsyncioTestCase):
    """Tests for the async MCP resource endpoints."""

    @patch('pytorch_hud.server.mcp_server.get_recent_commits_with_jobs')
    async def test_recent_commits_with_jobs_resource(self, mock_get_recent_commits):
        """Test that the universal resource endpoint properly awaits the async function."""
        # Create mock return value that contains filtered jobs
        mock_result = {
            "repo": "pytorch/pytorch",
            "branch_or_commit_sha": "main",
            "commits": [
                {
                    "sha": "abcdef",
                    "title": "Test Commit",
                    "author": "test-user",
                    "status": "red",
                    "job_counts": {
                        "total": 5,
                        "success": 3,
                        "failure": 2
                    },
                    "jobs": [
                        {"id": "job1", "name": "test_job1", "conclusion": "failure"},
                        {"id": "job2", "name": "test_job2", "conclusion": "failure"}
                    ]
                }
            ],
            "pagination": {
                "page": 1,
                "per_page": 10,
                "total_commits": 1,
                "returned_commits": 1
            },
            "filters": {
                "include_success": False,
                "include_pending": False,
                "include_failures": True, 
                "job_name_filter_regex": None
            },
            "_metadata": {
                "timestamp": "2025-03-07T12:00:00Z"
            }
        }
        
        # Set up mock to return our sample data
        mock_get_recent_commits.return_value = mock_result
        
        # Call the universal resource endpoint with failure filter
        result = await get_recent_commits_with_jobs_resource(
            "pytorch", "pytorch", "main", 
            include_success=False,
            include_pending=False,
            include_failures=True,
            page=1, 
            per_page=10
        )
        
        # Verify the resource endpoint was called with the correct arguments
        mock_get_recent_commits.assert_called_once_with(
            repo_owner="pytorch", 
            repo_name="pytorch", 
            branch_or_commit_sha="main",
            include_success=False,
            include_pending=False,
            include_failures=True,
            include_commit_details=True,
            job_name_filter_regex=None,
            failure_line_filter_regex=None,
            page=1, 
            per_page=10,
            ctx=None
        )
        
        # Result should be a JSON string - parse it back to verify contents
        result_data = json.loads(result)
        
        # Check that it contains the expected fields for filtered jobs
        self.assertIn("commits", result_data)
        self.assertEqual(len(result_data["commits"]), 1)
        self.assertEqual(len(result_data["commits"][0]["jobs"]), 2)
        
        # Reset mock for next test
        mock_get_recent_commits.reset_mock()
        
        # Create mock return value that contains only commit data (no jobs)
        mock_result_commits = {
            "repo": "pytorch/pytorch",
            "branch_or_commit_sha": "main",
            "commits": [
                {
                    "sha": "commit1",
                    "title": "Test Commit 1",
                    "author": "test-user",
                    "status": "green",
                    "job_counts": {"total": 10, "success": 10}
                },
                {
                    "sha": "commit2",
                    "title": "Test Commit 2",
                    "author": "test-user",
                    "status": "red",
                    "job_counts": {"total": 8, "success": 5, "failure": 3}
                }
            ],
            "pagination": {
                "page": 1,
                "per_page": 10,
                "total_commits": 2,
                "returned_commits": 2
            },
            "_metadata": {
                "timestamp": "2025-03-07T12:00:00Z"
            }
        }
        
        # Set up mock to return our commit data sample
        mock_get_recent_commits.return_value = mock_result_commits
        
        # Call the resource endpoint for recent commit status only
        result = await get_recent_commits_with_jobs_resource(
            "pytorch", "pytorch", "main", 
            include_success=False,
            include_pending=False,
            include_failures=False,
            page=1, 
            per_page=10
        )
        
        # Verify the resource endpoint was called with the correct arguments
        mock_get_recent_commits.assert_called_once_with(
            repo_owner="pytorch", 
            repo_name="pytorch", 
            branch_or_commit_sha="main",
            include_success=False,
            include_pending=False,
            include_failures=False,
            include_commit_details=True,
            job_name_filter_regex=None,
            failure_line_filter_regex=None,
            page=1, 
            per_page=10,
            ctx=None
        )
        
        # Result should be a JSON string - parse it back to verify contents
        result_data = json.loads(result)
        
        # Check that it contains the expected fields for commit status
        self.assertIn("commits", result_data)
        self.assertEqual(len(result_data["commits"]), 2)
        
        # The commits shouldn't have job details since we didn't request them
        self.assertNotIn("jobs", result_data["commits"][0])

    @patch('pytorch_hud.server.mcp_server.get_job_details')
    async def test_job_details_resource(self, mock_get_job_details):
        """Test that the job_details_resource properly awaits the async function."""
        # Create mock return value
        mock_result = {
            "job_id": "job123",
            "log_url": "https://example.com/logs/job123",
            "artifacts": ["artifact1.txt", "artifact2.log"],
            "utilization": {"cpu": 80, "memory": 60}
        }
        
        # Set up mock to return our sample data
        mock_get_job_details.return_value = mock_result
        
        # Call the resource endpoint - use an integer job ID
        job_id = 123
        result = await get_job_details_resource(job_id)
        
        # Verify the resource endpoint was called with the correct arguments
        mock_get_job_details.assert_called_once_with(job_id, ctx=None)
        
        # Result should be a JSON string - parse it back to verify contents
        result_data = json.loads(result)
        
        # Check that it contains the expected fields
        self.assertEqual(result_data["job_id"], "job123")
        self.assertIn("log_url", result_data)

    # Removed test_commit_summary_resource, test_job_summary_resource, test_test_summary_resource
    # as these functions have been consolidated into get_recent_commits_with_jobs

    # Removed test_hud_data_resource as get_hud_data has been removed

if __name__ == "__main__":
    unittest.main()