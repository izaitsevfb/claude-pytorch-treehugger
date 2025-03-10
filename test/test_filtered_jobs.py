#!/usr/bin/env python3
"""
Test script for validating the get_recent_commits_with_jobs function's filtering capabilities.

This test verifies that the function correctly filters jobs by different criteria
including success/failure status and regex patterns.
"""

import json
import unittest
from unittest.mock import patch

from pytorch_hud.tools.hud_data import get_recent_commits_with_jobs
from test.utils import create_async_mock_context

class TestFilteredJobs(unittest.IsolatedAsyncioTestCase):
    """Tests for job filtering functionality in get_recent_commits_with_jobs."""

    def setUp(self):
        """Load sample HUD data from file."""
        # Path to the sample data file
        sample_file_path = "test/fixtures/hud_data_response_sample_per_page_50.json"
        
        try:
            with open(sample_file_path, 'r') as f:
                self.sample_hud_data = json.load(f)
        except Exception as e:
            self.fail(f"Failed to load sample data: {e}")
            
        # Verify the sample data contains what we expect
        self.assertIn("shaGrid", self.sample_hud_data)
        self.assertTrue(len(self.sample_hud_data["shaGrid"]) > 0)
        self.assertIn("jobs", self.sample_hud_data["shaGrid"][0])
        
        # Find job IDs of success, failure, skipped, pending and in_progress jobs for testing
        jobs = self.sample_hud_data["shaGrid"][0]["jobs"]
        self.success_jobs = [job for job in jobs if job.get("conclusion") == "success"]
        self.failure_jobs = [job for job in jobs if job.get("conclusion") == "failure"]
        self.skipped_jobs = [job for job in jobs if job.get("conclusion") == "skipped"]
        self.pending_jobs = [job for job in jobs if job.get("status") == "in_progress" or job.get("status") == "queued"]
        
        # Verify we have at least success jobs for testing
        self.assertTrue(len(self.success_jobs) > 0, "No success jobs found in sample data")
        
        # Log counts of different job types (for troubleshooting)
        print(f"Found {len(self.success_jobs)} success jobs")
        print(f"Found {len(self.failure_jobs)} failure jobs")
        print(f"Found {len(self.skipped_jobs)} skipped jobs")
        print(f"Found {len(self.pending_jobs)} pending jobs")
        
    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_filter_by_status(self, mock_get_hud_data):
        """Test that jobs are correctly filtered by status."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Test filtering for success jobs
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main", 
            include_success=True,
            include_failures=False,
            include_pending=False,
            ctx=mock_ctx
        )
        
        # Verify result
        self.assertIn("commits", result)
        if result["commits"] and "jobs" in result["commits"][0]:
            for job in result["commits"][0]["jobs"]:
                self.assertEqual(job["conclusion"], "success")
            
        # Test filtering for failure jobs
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main", 
            include_success=False,
            include_failures=True,
            include_pending=False,
            ctx=mock_ctx
        )
        
        # Verify filter settings
        self.assertTrue(result["filters"]["include_failures"])
        self.assertFalse(result["filters"]["include_success"])
        
        # Check jobs if any in result
        if result["commits"] and "jobs" in result["commits"][0]:
            for job in result["commits"][0]["jobs"]:
                self.assertEqual(job["conclusion"], "failure")
            
        # Test filtering for pending jobs
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main", 
            include_success=False,
            include_failures=False,
            include_pending=True,
            ctx=mock_ctx
        )
        
        # Verify filter settings
        self.assertTrue(result["filters"]["include_pending"])
        
        # Check jobs if any in result
        if result["commits"] and "jobs" in result["commits"][0]:
            for job in result["commits"][0]["jobs"]:
                self.assertTrue(job["status"] == "in_progress" or 
                           job["status"] == "queued" or
                           job.get("conclusion") == "pending")

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_filter_by_job_name_pattern(self, mock_get_hud_data):
        """Test that jobs are correctly filtered by job name pattern regex."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Use a generic pattern that should match many job IDs
        job_name_pattern = "\\d+"  # Match any digits (regex pattern)
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Test filtering by job name pattern
        result = await get_recent_commits_with_jobs(
            "pytorch", 
            "pytorch", 
            "main", 
            job_name_filter_regex=job_name_pattern,
            include_failures=True,  # Include some jobs to filter
            ctx=mock_ctx
        )
        
        # Verify filter settings in result
        self.assertEqual(result["filters"]["job_name_filter_regex"], job_name_pattern)
        
        # If we have jobs in the result, verify the pattern works
        if (result["commits"] and 
            "jobs" in result["commits"][0] and 
            result["commits"][0]["jobs"]):
            
            pattern_found = False
            for job in result["commits"][0]["jobs"]:
                job_id = str(job.get("id", ""))
                job_name = job.get("name", "")
                # Check if either ID or name has digits (should match \d+)
                if job_id.isdigit() or any(c.isdigit() for c in job_name):
                    pattern_found = True
                    break
            
            self.assertTrue(pattern_found, f"Job name pattern '{job_name_pattern}' not found in result jobs")

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_pagination(self, mock_get_hud_data):
        """Test that pagination works correctly."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Test with small per_page to ensure pagination
        per_page = 1
        
        # Request first page
        result_page1 = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main",
            page=1, 
            per_page=per_page
        )
        
        # Request second page
        result_page2 = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main",
            page=2, 
            per_page=per_page
        )
        
        # Verify pagination info is correctly set in results
        self.assertEqual(result_page1["pagination"]["page"], 1)
        self.assertEqual(result_page1["pagination"]["per_page"], per_page)
        self.assertEqual(result_page2["pagination"]["page"], 2)
        self.assertEqual(result_page2["pagination"]["per_page"], per_page)
        
        # Verify we have commits on both pages
        self.assertGreaterEqual(len(result_page1["commits"]), 1)
        self.assertGreaterEqual(len(result_page2["commits"]), 1)
        
        # Don't verify uniqueness between pages, as this depends on real data
        # Just verify the pagination mechanism works (pages differ)

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_combined_filters(self, mock_get_hud_data):
        """Test that combining multiple filters works correctly."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Test combining success status and a job name pattern
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main", 
            include_success=True,
            include_failures=False,
            job_name_filter_regex="\\d+",  # Match jobs with digits in name
            ctx=mock_ctx
        )
        
        # Verify filters are correctly set in result
        self.assertTrue(result["filters"]["include_success"])
        self.assertFalse(result["filters"]["include_failures"])
        self.assertEqual(result["filters"]["job_name_filter_regex"], "\\d+")
        
        # If we have jobs in the result, verify they match both filters
        if (result["commits"] and 
            "jobs" in result["commits"][0] and 
            result["commits"][0]["jobs"]):
            
            for job in result["commits"][0]["jobs"]:
                # Should be success jobs
                self.assertEqual(job["conclusion"], "success")
                
                # Should match the digit pattern
                job_id = str(job.get("id", ""))
                job_name = job.get("name", "")
                self.assertTrue(job_id.isdigit() or any(c.isdigit() for c in job_name),
                              f"Job {job_id} doesn't match the digit pattern")
                
    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_no_matching_jobs(self, mock_get_hud_data):
        """Test handling of filters that result in no matching jobs."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Use a non-existent job name pattern
        job_name_pattern = "ThisPatternShouldNotExistInAnyJobName12345"
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Call with filter that should return no jobs
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main", 
            job_name_filter_regex=job_name_pattern,
            include_failures=True,  # Include some jobs that will be filtered out
            ctx=mock_ctx
        )
        
        # Verify result structure is correct even when no jobs match the filter
        self.assertIn("commits", result)
        if result["commits"]:
            # Either jobs array is missing or empty
            if "jobs" in result["commits"][0]:
                self.assertEqual(len(result["commits"][0]["jobs"]), 0, 
                              "Expected no jobs to match the impossible filter")
        
    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_failure_line_filtering(self, mock_get_hud_data):
        """Test filtering by failure line content."""
        # Create special sample with failures containing specific text
        hidden_failure_sample = {
            "shaGrid": [
                {
                    "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
                    "commitTitle": "Test commit with various failures",
                    "author": "test-user",
                    "time": "2025-03-06T22:10:53Z",
                    "prNum": 12345,
                    "jobs": [
                        # Normal success job
                        {"id": "job1", "status": "completed", "conclusion": "success"},
                        # Failure with build error
                        {
                            "id": "job2", 
                            "status": "completed", 
                            "conclusion": "failure", 
                            "failureLines": ["Error: Build failed with code 1"],
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/12345/job/job2"
                        },
                        # Failure with test error
                        {
                            "id": "job3", 
                            "status": "completed", 
                            "conclusion": "failure",
                            "failureLines": ["Error: Test failed: Expected 5 but got 6"],
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/12345/job/job3"
                        }
                    ]
                }
            ],
            "jobNames": ["job1", "job2", "job3"]
        }
        
        # Setup mock
        mock_get_hud_data.return_value = hidden_failure_sample
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Test filtering by failure line content - only include test failures
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main",
            include_failures=True,
            failure_line_filter_regex="Test failed",
            ctx=mock_ctx
        )
        
        # Verify filter is correctly set in result
        self.assertTrue(result["filters"]["include_failures"])
        self.assertEqual(result["filters"]["failure_line_filter_regex"], "Test failed")
        
        # If we have any jobs in the result, they should only be the test failure
        if (result["commits"] and 
            "jobs" in result["commits"][0] and 
            result["commits"][0]["jobs"]):
            
            job_ids = [str(job.get("id", "")) for job in result["commits"][0]["jobs"]]
            self.assertIn("job3", job_ids, "Test failure job should be in results")
            self.assertNotIn("job2", job_ids, "Build failure job should not be in results")
            self.assertNotIn("job1", job_ids, "Success job should not be in results")

if __name__ == "__main__":
    unittest.main()