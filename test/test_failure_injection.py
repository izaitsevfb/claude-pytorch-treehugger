#!/usr/bin/env python3
"""
Test script that injects failures into the sample data to verify that failure detection works correctly.
"""

import json
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import copy

from pytorch_hud.tools.hud_data import get_recent_commits_with_jobs

class TestFailureInjection(unittest.IsolatedAsyncioTestCase):
    """Tests that inject failures into sample data to validate detection logic."""

    def setUp(self):
        """Load sample HUD data from file and inject failures."""
        # Path to the sample data file
        sample_file_path = "test/fixtures/hud_data_response_sample_per_page_50.json"
        
        try:
            with open(sample_file_path, 'r') as f:
                self.original_data = json.load(f)
        except Exception as e:
            self.fail(f"Failed to load sample data: {e}")
            
        # Create a copy of the data to modify
        self.data_with_failures = copy.deepcopy(self.original_data)
        
        # Inject failures into the data
        # 1. Inject an explicit failure job
        explicit_failure = {
            "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
            "id": 99999001,
            "conclusion": "failure",
            "status": "completed",
            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/13709183265/job/99999001",
            "logUrl": "https://ossci-raw-job-status.s3.amazonaws.com/log/99999001",
            "durationS": 120,
            "repo": "pytorch/pytorch",
            "failureLines": ["ERROR: Test failed with exit code 1", "Error: Compilation failed"],
            "failureLineNumbers": [100, 200],
            "failureCaptures": ["Test failed", "Compilation failed"]
        }
        
        # 2. Inject a hidden failure job (success conclusion but with failure lines)
        hidden_failure = {
            "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
            "id": 99999002,
            "conclusion": "success",
            "status": "completed",
            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/13709183265/job/99999002",
            "logUrl": "https://ossci-raw-job-status.s3.amazonaws.com/log/99999002",
            "durationS": 150,
            "repo": "pytorch/pytorch",
            "failureLines": ["WARNING: Test output does not match expected results", "ERROR: Floating point exception"],
            "failureLineNumbers": [300, 400],
            "failureCaptures": ["Test mismatch", "FP exception"]
        }
        
        # 3. Inject a test failure job for testing get_test_summary
        test_failure = {
            "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
            "id": 99999003,
            "conclusion": "failure",
            "status": "completed",
            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/13709183265/test_workflow/job/99999003",
            "logUrl": "https://ossci-raw-job-status.s3.amazonaws.com/log/99999003",
            "durationS": 180,
            "repo": "pytorch/pytorch",
            "failureLines": [
                "FAIL: test_function1 (test_module.TestClass)",
                "ERROR: test_function2 (test_module.TestClass)",
                "AssertionError: Values not equal: 1 != 2"
            ],
            "failureLineNumbers": [500, 600, 700],
            "failureCaptures": ["Test failure", "Test error", "Assertion"]
        }
        
        # Add jobs to the first entry in shaGrid
        if len(self.data_with_failures["shaGrid"]) > 0 and "jobs" in self.data_with_failures["shaGrid"][0]:
            # Add the failure jobs to the beginning to make them easier to find
            self.data_with_failures["shaGrid"][0]["jobs"].insert(0, explicit_failure)
            self.data_with_failures["shaGrid"][0]["jobs"].insert(1, hidden_failure)
            self.data_with_failures["shaGrid"][0]["jobs"].insert(2, test_failure)
            
            # Log the number of jobs now in the test data
            success_jobs = [job for job in self.data_with_failures["shaGrid"][0]["jobs"] 
                          if job.get("conclusion") == "success" and not 
                           (job.get("failureLines", []) and len(job.get("failureLines", [])) > 0)]
            
            explicit_failure_jobs = [job for job in self.data_with_failures["shaGrid"][0]["jobs"] 
                                   if job.get("conclusion") == "failure"]
            
            hidden_failure_jobs = [job for job in self.data_with_failures["shaGrid"][0]["jobs"] 
                                if job.get("conclusion") == "success" and 
                                job.get("failureLines", []) and len(job.get("failureLines", [])) > 0]
            
            print("Test data contains:")
            print(f"- {len(success_jobs)} true success jobs")
            print(f"- {len(explicit_failure_jobs)} explicit failure jobs")
            print(f"- {len(hidden_failure_jobs)} hidden failure jobs")
        else:
            self.fail("Could not find jobs array in sample data")

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_failure_detection(self, mock_get_hud_data):
        """Test that get_recent_commits_with_jobs correctly detects failures."""
        # Mock the API to return our modified data
        mock_get_hud_data.return_value = self.data_with_failures
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call get_recent_commits_with_jobs with include_failures=True
        result = await get_recent_commits_with_jobs(
            "pytorch", 
            "pytorch", 
            "main", 
            include_failures=True,
            ctx=mock_ctx
        )
        
        # Verify we have commits in the result
        self.assertTrue(result["commits"], "No commits returned in result")
        self.assertGreaterEqual(len(result["commits"]), 1, "Expected at least 1 commit")
        
        # Get the first commit
        commit = result["commits"][0]
        
        # Verify job counts - should include our injected failures
        self.assertIn("job_counts", commit, "No job counts found in commit data")
        self.assertIn("failure", commit["job_counts"], "No failure count found")
        self.assertGreaterEqual(commit["job_counts"]["failure"], 2, 
                               f"Expected at least 2 failures, got {commit['job_counts']['failure']}")
        
        # Verify the commit status is red due to failures
        self.assertEqual(commit["status"], "red", "Commit status should be 'red' due to failures")
        
        # Verify jobs are included and contain failures
        self.assertIn("jobs", commit, "No jobs array in commit data")
        self.assertGreaterEqual(len(commit["jobs"]), 2, f"Expected at least 2 jobs, got {len(commit['jobs'])}")
        
        # Extract job IDs
        job_ids = [job.get("id") for job in commit["jobs"]]
        
        # Check for our injected failure job IDs
        # Job IDs might be returned as strings, so convert to strings for comparison
        job_id_strings = [str(job_id) for job_id in job_ids]
        self.assertTrue(
            "99999001" in job_id_strings or "99999003" in job_id_strings,
            "Neither of our explicit failure jobs (99999001, 99999003) found in result"
        )
        
        # The hidden failure job should NOT be included because it has conclusion=success
        self.assertNotIn("99999002", job_id_strings, 
                        "Hidden failure job (99999002) should not be in failures list")
        
        # Print results for debugging
        print("Failure Detection Results:")
        print(f"- Commit status: {commit['status']}")
        print(f"- Job counts: {commit['job_counts']}")
        print(f"- Number of jobs returned: {len(commit['jobs'])}")
        print(f"- Job IDs: {job_ids}")
        
    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_job_filtering(self, mock_get_hud_data):
        """Test that job filtering options work correctly."""
        # Mock the API to return our modified data
        mock_get_hud_data.return_value = self.data_with_failures
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call with job_name_filter_regex to filter for test jobs
        result = await get_recent_commits_with_jobs(
            "pytorch", 
            "pytorch", 
            "main", 
            include_failures=True,
            job_name_filter_regex="test_workflow",
            ctx=mock_ctx
        )
        
        # Verify that filtering worked
        self.assertTrue(result["commits"], "No commits returned in result")
        commit = result["commits"][0]
        
        # Should have filtered to only include test jobs
        if "jobs" in commit and commit["jobs"]:
            # For any jobs that are returned, verify they match the filter
            for job in commit["jobs"]:
                # Check job name or URL for the test_workflow pattern
                job_name = job.get("name", "")
                html_url = job.get("htmlUrl", "")
                
                # If not directly in name, check the URL
                if "test_workflow" not in job_name and html_url:
                    self.assertIn("test_workflow", html_url, 
                                 f"Job {job.get('id')} doesn't match the filter pattern")
                    
        # Print results for debugging
        print("Job Filtering Results:")
        print(f"- Commit status: {commit['status']}")
        if "jobs" in commit:
            print(f"- Number of filtered jobs: {len(commit['jobs'])}")
            print(f"- Job IDs: {[job.get('id') for job in commit['jobs']]}")
        
    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_failure_line_filtering(self, mock_get_hud_data):
        """Test filtering by failure line content."""
        # Mock the API to return our modified data
        mock_get_hud_data.return_value = self.data_with_failures
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call with failure line filter to find only compilation errors
        result = await get_recent_commits_with_jobs(
            "pytorch", 
            "pytorch", 
            "main", 
            include_failures=True,
            failure_line_filter_regex="Compilation failed",
            ctx=mock_ctx
        )
        
        # Verify that filtering worked
        self.assertTrue(result["commits"], "No commits returned in result")
        commit = result["commits"][0]
        
        # If jobs are found, they should have the specified failure line
        if "jobs" in commit and commit["jobs"]:
            for job in commit["jobs"]:
                failure_lines = job.get("failureLines", [])
                if failure_lines:
                    compilation_failure_found = any("Compilation failed" in line for line in failure_lines)
                    self.assertTrue(compilation_failure_found, 
                                  f"Job {job.get('id')} doesn't have the expected failure line")
        
        # Print results for debugging
        print("Failure Line Filtering Results:")
        if "jobs" in commit:
            print(f"- Number of jobs with compilation failures: {len(commit.get('jobs', []))}")
            for job in commit.get("jobs", []):
                print(f"- Job {job.get('id')} failure lines: {job.get('failureLines', [])}")

if __name__ == "__main__":
    unittest.main()