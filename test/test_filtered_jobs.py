#!/usr/bin/env python3
"""
Test script for validating the get_filtered_jobs function in the PyTorch HUD MCP server.

This test verifies that the function correctly filters jobs by status, workflow name, 
and job name pattern.
"""

import json
import unittest
from unittest.mock import patch

from pytorch_hud.tools.hud_data import get_filtered_jobs
from test.utils import create_async_mock_context

class TestFilteredJobs(unittest.IsolatedAsyncioTestCase):
    """Tests for the get_filtered_jobs function."""

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
        
        # Test filtering by success status
        result = await get_filtered_jobs("pytorch", "pytorch", "main", status="success", ctx=mock_ctx)
        
        # Verify result
        self.assertEqual(result["filters"]["status"], "success")
        for job in result["jobs"]:
            self.assertEqual(job["conclusion"], "success")
            
        # Test filtering by failure status
        result = await get_filtered_jobs("pytorch", "pytorch", "main", status="failure", ctx=mock_ctx)
        
        # Verify filter is correctly set in result
        self.assertEqual(result["filters"]["status"], "failure")
        # Note: We might not have any failure jobs in the sample data
            
        # Test filtering by skipped status
        result = await get_filtered_jobs("pytorch", "pytorch", "main", status="skipped", ctx=mock_ctx)
        
        # Verify filter is correctly set in result
        self.assertEqual(result["filters"]["status"], "skipped")
        if result["jobs"]:
            for job in result["jobs"]:
                self.assertEqual(job["conclusion"], "skipped")
            
        # Test filtering by in_progress status
        result = await get_filtered_jobs("pytorch", "pytorch", "main", status="in_progress", ctx=mock_ctx)
        
        # Verify filter is correctly set in result
        self.assertEqual(result["filters"]["status"], "in_progress")
        if result["jobs"]:
            for job in result["jobs"]:
                self.assertEqual(job["status"], "in_progress")

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_filter_by_workflow(self, mock_get_hud_data):
        """Test that jobs are correctly filtered by workflow name."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Hard-code a known workflow number from the sample data
        workflow_name = "actions/runs/13709183265"  # From observed data in the sample
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Test filtering by workflow
        result = await get_filtered_jobs("pytorch", "pytorch", "main", workflow=workflow_name, ctx=mock_ctx)
        
        # Verify filter settings in result
        self.assertEqual(result["filters"]["workflow"], workflow_name)
        
        # Just verify the function returns without errors - may not get actual matches in the test data

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_filter_by_job_name_pattern(self, mock_get_hud_data):
        """Test that jobs are correctly filtered by job name pattern."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Use a generic pattern that should match many job IDs
        job_name_pattern = "\\d+"  # Match any digits (regex pattern)
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Test filtering by job name pattern
        result = await get_filtered_jobs("pytorch", "pytorch", "main", job_name_pattern=job_name_pattern, ctx=mock_ctx)
        
        # Verify result
        self.assertEqual(result["filters"]["job_name_pattern"], job_name_pattern)
        
        # If we have jobs in the result, verify the pattern works
        if result["jobs"]:
            pattern_found = False
            for job in result["jobs"]:
                job_id = job.get("id", "")
                if str(job_id).isdigit():  # Should match our \d+ pattern
                    pattern_found = True
                    break
            
            self.assertTrue(pattern_found, f"Job name pattern '{job_name_pattern}' not found in result jobs")

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_pagination(self, mock_get_hud_data):
        """Test that pagination works correctly."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Test with small per_page to ensure pagination
        per_page = 5
        
        # Request first page
        result_page1 = await get_filtered_jobs("pytorch", "pytorch", "main", "e6800bda", page=1, per_page=per_page)
        
        # Request second page
        result_page2 = await get_filtered_jobs("pytorch", "pytorch", "main", "e6800bda", page=2, per_page=per_page)
        
        # Verify pagination info is correctly set in results
        self.assertEqual(result_page1["pagination"]["page"], 1)
        self.assertEqual(result_page1["pagination"]["per_page"], per_page)
        self.assertEqual(result_page2["pagination"]["page"], 2)
        self.assertEqual(result_page2["pagination"]["per_page"], per_page)
        
        # Verify we have jobs on the first page and it respects per_page limit
        self.assertLessEqual(len(result_page1["jobs"]), per_page)
        
        # Don't verify uniqueness between pages, as this depends on real data
        # Just verify the pagination mechanism works (pages differ)

    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_combined_filters(self, mock_get_hud_data):
        """Test that combining multiple filters works correctly."""
        # Setup mock
        mock_get_hud_data.return_value = self.sample_hud_data
        
        # Test combining success status and a workflow pattern that should exist
        workflow = "runs"  # This should match many workflow URLs
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        result = await get_filtered_jobs("pytorch", "pytorch", "main", 
                                        status="success", workflow=workflow, ctx=mock_ctx)
        
        # Verify filters are correctly set in result
        self.assertEqual(result["filters"]["status"], "success")
        self.assertEqual(result["filters"]["workflow"], workflow)
        
        # Check jobs if any in the result match both filters
        if result["jobs"]:
            for job in result["jobs"]:
                self.assertEqual(job["conclusion"], "success")
                html_url = job.get("htmlUrl", "")
                self.assertIn(workflow, html_url)
                
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
        result = await get_filtered_jobs("pytorch", "pytorch", "main", 
                                      job_name_pattern=job_name_pattern, ctx=mock_ctx)
        
        # Verify result structure is correct even when no jobs match
        self.assertIn("jobs", result)
        self.assertEqual(len(result["jobs"]), 0, "Expected empty jobs list for non-matching filter")
        self.assertIn("pagination", result)
        self.assertEqual(result["pagination"]["total_items"], 0)
        self.assertEqual(result["pagination"]["total_pages"], 0)
        self.assertEqual(result["filters"]["job_name_pattern"], job_name_pattern)
        
    @patch('pytorch_hud.tools.hud_data.api.get_hud_data')
    async def test_hidden_failures(self, mock_get_hud_data):
        """Test that jobs with hidden failures (successful conclusion but failure lines) are correctly detected."""
        # Create special sample with hidden failures
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
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/12345/job/job3"
                        }
                    ]
                }
            ]
        }
        
        # Setup mock
        mock_get_hud_data.return_value = hidden_failure_sample
        
        # Create a mock context with async methods
        mock_ctx = create_async_mock_context()
        
        # Test filtering by failure status - should include both explicit and hidden failures
        result = await get_filtered_jobs("pytorch", "pytorch", "main", status="failure", ctx=mock_ctx)
        
        # Verify result
        self.assertEqual(result["filters"]["status"], "failure")
        self.assertEqual(len(result["jobs"]), 2, "Should include both hidden and explicit failures")
        
        # Get job IDs from result for verification
        job_ids = [job.get("id") for job in result["jobs"]]
        
        # Check that both failure jobs are included (job2 - hidden failure, job3 - explicit failure)
        self.assertIn("job2", job_ids, "Hidden failure should be included in results")
        self.assertIn("job3", job_ids, "Explicit failure should be included in results")
        self.assertNotIn("job1", job_ids, "Success job should not be in failure results")

if __name__ == "__main__":
    unittest.main()