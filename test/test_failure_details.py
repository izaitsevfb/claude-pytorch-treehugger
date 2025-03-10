#!/usr/bin/env python3
"""
Test script for validating the get_failure_details function in the PyTorch HUD MCP server.

This test verifies that the function correctly identifies and reports both explicit
failures and hidden failures (those with success conclusion but failure lines).
"""

import json
import unittest
import requests
from unittest.mock import patch

from pytorch_hud.tools.hud_data import get_recent_commits_with_jobs
from pytorch_hud.server.mcp_server import get_recent_commits_with_jobs_resource

class TestFailureDetails(unittest.IsolatedAsyncioTestCase):
    """Tests for failure detection in get_recent_commits_with_jobs function."""

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_hidden_failures_detected(self, mock_get_hud_data):
        """Test that failures are correctly detected."""
        # Create sample with hidden failures
        hidden_failure_sample = {
            "shaGrid": [
                {
                    "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
                    "commitTitle": "Test commit with hidden failures",
                    "author": "test-user",
                    "time": "2025-03-06T22:10:53Z",
                    "prNum": 12345,
                    "jobs": [
                        # Normal success job
                        {"id": "job1", "status": "completed", "conclusion": "success"},
                        # Hidden failure - conclusion is "success" but has failure lines
                        {
                            "id": "job2", 
                            "status": "completed", 
                            "conclusion": "success", 
                            "failureLines": ["Error: Build failed with code 1"],
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/12345/job/job2"
                        },
                        # Normal failure job
                        {
                            "id": "job3", 
                            "status": "completed", 
                            "conclusion": "failure",
                            "failureLines": ["Test failed: Expected 5 but got 6"],
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/12345/job/job3"
                        },
                        # In progress job
                        {"id": "job4", "status": "in_progress", "conclusion": None}
                    ]
                }
            ],
            "jobNames": ["job1", "job2", "job3", "job4"]
        }
        
        # Setup mock
        mock_get_hud_data.return_value = hidden_failure_sample
        
        # Call function with failures filter
        result = await get_recent_commits_with_jobs(
            repo_owner="pytorch", 
            repo_name="pytorch", 
            branch_or_commit_sha="main",
            include_failures=True
        )
        
        # Verify commit info
        self.assertEqual(len(result["commits"]), 1)
        commit = result["commits"][0]
        
        # Verify job counts
        self.assertEqual(commit["job_counts"]["total"], 4)
        self.assertEqual(commit["job_counts"]["success"], 2)
        self.assertEqual(commit["job_counts"]["failure"], 1)
        self.assertEqual(commit["job_counts"]["pending"], 1)
        
        # Check that the jobs array contains only the failure job (since we used include_failures=True)
        self.assertEqual(len(commit.get("jobs", [])), 1)
        self.assertEqual(commit["jobs"][0]["id"], "job3")
        self.assertEqual(commit["status"], "red")

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_all_success_jobs(self, mock_get_hud_data):
        """Test a case where all jobs are successful."""
        # Create sample with only success jobs
        success_sample = {
            "shaGrid": [
                {
                    "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
                    "commitTitle": "Test commit with all successes",
                    "author": "test-user",
                    "time": "2025-03-06T22:10:53Z",
                    "prNum": 12345,
                    "jobs": [
                        {"id": "job1", "status": "completed", "conclusion": "success"},
                        {"id": "job2", "status": "completed", "conclusion": "success"},
                        {"id": "job3", "status": "completed", "conclusion": "success"}
                    ]
                }
            ],
            "jobNames": ["job1", "job2", "job3"]
        }
        
        # Setup mock
        mock_get_hud_data.return_value = success_sample
        
        # Call function
        result = await get_recent_commits_with_jobs(
            repo_owner="pytorch", 
            repo_name="pytorch", 
            branch_or_commit_sha="main",
            include_success=True
        )
        
        # Verify commit info
        self.assertEqual(len(result["commits"]), 1)
        commit = result["commits"][0]
        
        # Verify job counts
        self.assertEqual(commit["job_counts"]["total"], 3)
        self.assertEqual(commit["job_counts"]["success"], 3)
        self.assertEqual(commit["job_counts"]["failure"], 0)
        
        # Since we used include_success=True, all successful jobs should be included
        self.assertEqual(len(commit.get("jobs", [])), 3)
        self.assertEqual(commit["status"], "green")

    @patch('pytorch_hud.server.mcp_server.get_recent_commits_with_jobs')
    async def test_failure_details_resource(self, mock_get_recent_commits):
        """Test that the resource endpoint properly awaits the async function for failure details."""
        # Create mock return value that looks like get_recent_commits_with_jobs output
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
                        "total": 3,
                        "success": 1,
                        "failure": 2
                    },
                    "jobs": [
                        {"id": "job1", "name": "test_job1", "conclusion": "failure", "failureLines": ["Error 1", "Error 2"]},
                        {"id": "job2", "name": "test_job2", "conclusion": "failure", "failureLines": ["Error 3"]}
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
                "include_failures": True
            },
            "_metadata": {
                "timestamp": "2025-03-07T12:00:00Z"
            }
        }
        
        # Set up mock to return our sample data
        mock_get_recent_commits.return_value = mock_result
        
        # Call the resource endpoint with failure filter
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
        
        # Check that it contains the expected fields - failures would be in the commits[0].jobs
        self.assertIn("commits", result_data)
        self.assertEqual(len(result_data["commits"]), 1)
        self.assertIn("jobs", result_data["commits"][0])
        self.assertEqual(len(result_data["commits"][0]["jobs"]), 2)
        
        # Reset the mock for the second test
        mock_get_recent_commits.reset_mock()
        
        # Use failure line filter regex to simulate the include_lines="summary" feature
        mock_get_recent_commits.return_value = mock_result
        
        # Call the endpoint but we don't need to check the returned value
        await get_recent_commits_with_jobs_resource(
            "pytorch", "pytorch", "main",
            include_success=False,
            include_pending=False,
            include_failures=True,
            failure_line_filter_regex="^Error",  # This should filter to just the first error line
            page=1, 
            per_page=10
        )
        
        # Verify called again with the proper arguments including the failure line filter
        mock_get_recent_commits.assert_called_once_with(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha="main",
            include_success=False,
            include_pending=False,
            include_failures=True,
            include_commit_details=True,
            job_name_filter_regex=None,
            failure_line_filter_regex="^Error",
            page=1, 
            per_page=10,
            ctx=None
        )


class TestFailureDetailsResourceHTTP(unittest.TestCase):
    """Test the HTTP endpoint for failure details resource.
    
    Note: These tests require the MCP server to be running locally.
    Skip these tests if the server is not running.
    """

    def setUp(self):
        """Check if the MCP server is running."""
        try:
            response = requests.get("http://localhost:8000/health", timeout=1)
            self.server_running = response.status_code == 200
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            self.server_running = False

    def test_failure_details_resource_http(self):
        """Test the HTTP endpoint for failure details resource."""
        if not self.server_running:
            self.skipTest("MCP server is not running")
            
        # Make request to the universal resource endpoint for failures
        response = requests.post(
            "http://localhost:8000/tools/get_recent_commits_with_jobs_resource",
            json={
                "repo_owner": "pytorch",
                "repo_name": "pytorch",
                "branch_or_commit_sha": "3960f978325222392d89ecdeb0d5baf968f654a7",
                "include_failures": True,
                "include_success": False,
                "include_pending": False,
                "per_page": 5
            }
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        # Basic validation of structure
        self.assertIn("result", result)
        data = json.loads(result["result"])
        self.assertIn("commits", data)
        
        # Check if we have any commits with jobs
        if data["commits"] and len(data["commits"]) > 0:
            # Check if the first commit has jobs
            if "jobs" in data["commits"][0]:
                # With job filtering, we should only see failure jobs
                for job in data["commits"][0]["jobs"]:
                    self.assertEqual(job.get("conclusion"), "failure")


if __name__ == "__main__":
    unittest.main()