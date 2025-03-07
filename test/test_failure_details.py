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

from pytorch_hud.tools.hud_data import get_failure_details
from pytorch_hud.server.mcp_server import get_failure_details_resource

class TestFailureDetails(unittest.IsolatedAsyncioTestCase):
    """Tests for the get_failure_details function."""

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_hidden_failures_detected(self, mock_get_hud_data):
        """Test that hidden failures (successful conclusion but failure lines) are correctly detected."""
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
            ]
        }
        
        # Setup mock
        mock_get_hud_data.return_value = hidden_failure_sample
        
        # Call function
        result = await get_failure_details("pytorch", "pytorch", "main")
        
        # Verify job counts - updated to reflect new behavior of only counting explicit failures
        self.assertEqual(result["job_status_counts"]["total"], 4, "Should count all jobs")
        self.assertEqual(result["job_status_counts"]["success"], 2, "Should count 2 success jobs (including one with failure lines)")
        self.assertEqual(result["job_status_counts"]["failure"], 1, "Should count 1 explicit failure")
        self.assertEqual(result["job_status_counts"]["in_progress"], 1, "Should count 1 in-progress job")
        
        # Verify failures list - now only including explicit failures
        self.assertEqual(result["total_failures"], 1, "Should list 1 failure")
        self.assertEqual(len(result["failed_jobs"]), 1, "Should include 1 failed job")
        
        # Verify only the explicit failure is in the list
        failure_ids = [job.get("id") for job in result["failed_jobs"]]
        self.assertNotIn("job2", failure_ids, "Job with success conclusion but failure lines should NOT be in failed_jobs list")
        self.assertIn("job3", failure_ids, "Explicit failure should be in failed_jobs list")
        
        # Check that hiddenFailure flag is correctly set
        for job in result["failed_jobs"]:
            if job["id"] == "job3":
                self.assertFalse(job["hiddenFailure"], "Explicit failure should be marked with hiddenFailure=False")
                
        # Build status should be "failing" due to failures
        self.assertEqual(result["build_status"], "failing")

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
            ]
        }
        
        # Setup mock
        mock_get_hud_data.return_value = success_sample
        
        # Call function
        result = await get_failure_details("pytorch", "pytorch", "main")
        
        # Verify job counts
        self.assertEqual(result["job_status_counts"]["total"], 3, "Should count all jobs")
        self.assertEqual(result["job_status_counts"]["success"], 3, "Should count 3 success jobs")
        self.assertEqual(result["job_status_counts"]["failure"], 0, "Should count 0 failures")
        
        # Verify failures list
        self.assertEqual(result["total_failures"], 0, "Should list 0 failures")
        self.assertEqual(len(result["failed_jobs"]), 0, "Should include 0 failed jobs")
                
        # Build status should be "passing" due to no failures
        self.assertEqual(result["build_status"], "passing")

    @patch('pytorch_hud.server.mcp_server.get_failure_details')
    async def test_failure_details_resource(self, mock_get_failure_details):
        """Test that the failure_details_resource properly awaits the async function."""
        # Create mock return value for get_failure_details
        mock_failure_details = {
            "commit": {"sha": "abcdef", "title": "Test Commit", "author": "test-user"},
            "build_status": "failing",
            "job_status_counts": {"total": 3, "success": 1, "failure": 2},
            "failed_jobs": [
                {"id": "job1", "failureLines": ["Error 1", "Error 2"]},
                {"id": "job2", "failureLines": ["Error 3"]}
            ],
            "total_failures": 2,
            "pagination": {"page": 1, "per_page": 10, "total_items": 2}
        }
        
        # Set up mock to return our sample data
        mock_get_failure_details.return_value = mock_failure_details
        
        # Call the resource endpoint
        result = await get_failure_details_resource(
            "pytorch", "pytorch", "main", 
            page=1, per_page=10
        )
        
        # Verify the resource endpoint was called with the correct arguments
        mock_get_failure_details.assert_called_once_with(
            "pytorch", "pytorch", "main",
            page=1, per_page=10, ctx=None
        )
        
        # Result should be a JSON string - parse it back to verify contents
        result_data = json.loads(result)
        
        # Check that it contains the expected fields
        self.assertIn("failed_jobs", result_data)
        self.assertEqual(len(result_data["failed_jobs"]), 2)
        
        # Reset the mock for the second test
        mock_get_failure_details.reset_mock()
        mock_get_failure_details.return_value = mock_failure_details
        
        # Include_lines parameter should handle failure line filtering
        result_summary = await get_failure_details_resource(
            "pytorch", "pytorch", "main", 
            page=1, per_page=10, include_lines="summary"
        )
        
        # Verify called again with the same arguments
        mock_get_failure_details.assert_called_once_with(
            "pytorch", "pytorch", "main",
            page=1, per_page=10, ctx=None
        )
        
        # Parse result to verify that only first failure line was included
        summary_data = json.loads(result_summary)
        for job in summary_data["failed_jobs"]:
            self.assertEqual(len(job["failureLines"]), 1, 
                            "With include_lines=summary, each job should have only one failure line")


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
            
        # Make request to failure details resource endpoint
        response = requests.post(
            "http://localhost:8000/tools/get_failure_details_resource",
            json={
                "repo_owner": "pytorch",
                "repo_name": "pytorch",
                "branch": "main",
                "commit_sha": "3960f978325222392d89ecdeb0d5baf968f654a7",
                "per_page": "5",
                "include_lines": "summary"
            }
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        # Basic validation of structure
        self.assertIn("result", result)
        data = json.loads(result["result"])
        self.assertIn("failed_jobs", data)
        
        # With include_lines=summary, each job should have at most one failure line
        for job in data["failed_jobs"]:
            if "failureLines" in job:
                self.assertLessEqual(len(job["failureLines"]), 1)


if __name__ == "__main__":
    unittest.main()