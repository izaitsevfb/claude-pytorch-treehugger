#!/usr/bin/env python3
"""
Test script specifically for validating the job status counting logic in 
the get_recent_commit_status function.

This test uses sample JSON responses to verify proper parsing.
"""

import json
import unittest
from unittest.mock import patch

# Import function directly for testing
from pytorch_hud.server.mcp_server import get_recent_commit_status

# Load sample data from fixtures directory
def load_sample_data():
    with open("test/fixtures/hud_data_response_sample_per_page_50.json", "r") as f:
        return json.load(f)

class TestRecentCommitStatusParsing(unittest.IsolatedAsyncioTestCase):
    """Tests job status counting mechanism of get_recent_commit_status."""

    def setUp(self):
        """Load sample data for tests."""
        self.hud_sample = load_sample_data()
        
        # Sample with various types of failure indicators
        self.test_failures_sample = {
            "shaGrid": [
                {
                    "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
                    "commitTitle": "Test commit with failures",
                    "author": "test-user",
                    "time": "2025-03-06T22:10:53Z",
                    "prNum": 12345,
                    "jobs": [
                        # Traditional failure - conclusion is explicitly "failure"
                        {"id": "job1", "status": "completed", "conclusion": "failure", "test_failures": ["Test failure 1"]},
                        # Hidden failure - conclusion is "success" but has failure lines
                        {"id": "job2", "status": "completed", "conclusion": "success", "failureLines": ["Error: Build failed with code 1"]},
                        # Another traditional failure
                        {"id": "job3", "status": "completed", "conclusion": "failure", "test_failures": ["Test failure 2"]},
                        # Empty failure lines should still count as success
                        {"id": "job4", "status": "completed", "conclusion": "success", "failureLines": []},
                        # Success job
                        {"id": "job5", "status": "completed", "conclusion": "success"}
                    ]
                }
            ]
        }
        
        # Sample commit summary response
        self.commit_summary_sample = {
            "sha": "e6800bda7fabaf1de7c0586c9851c2326e142993",
            "title": "Test commit",
            "author": "test-user",
            "time": "2025-03-06T22:10:53Z",
            "pr_num": 12345,
            "prNum": 12345
        }
        
    async def test_job_status_counting_from_sample(self):
        """Test job status counting using our sample data."""
        with patch('pytorch_hud.server.mcp_server.get_commit_summary') as mock_get_commit_summary, \
             patch('pytorch_hud.server.mcp_server.api.get_hud_data') as mock_get_hud_data:
            
            # Setup mocks
            mock_get_commit_summary.return_value = self.commit_summary_sample
            mock_get_hud_data.return_value = self.hud_sample
            
            # Call the function
            result = await get_recent_commit_status("pytorch", "pytorch", count=1)
            
            # Verify job counts are correctly calculated
            job_counts = result["commits"][0]["job_counts"]
            
            # Print the actual counts for debugging
            print(f"Actual job counts: {job_counts}")
            
            # The real sample has many jobs with various statuses
            # We're expecting:
            # - Multiple success jobs
            # - Some failure jobs
            # - Some in_progress/queued jobs (pending)
            # - Some skipped jobs
            
            # Check that we have reasonable numbers (exact counts will vary based on the sample)
            self.assertGreater(job_counts["total"], 0, "Total job count should be positive")
            
            # Ensure the status categories make sense
            self.assertEqual(
                job_counts["total"], 
                job_counts["success"] + job_counts["failure"] + job_counts["pending"] + job_counts["skipped"],
                "Job counts by status should sum to total"
            )
            
            # The status should be one of: red, green, pending, unknown
            self.assertIn(result["commits"][0]["status"], ["red", "green", "pending", "unknown"])
        
    async def test_test_failures_counted(self):
        """Test that jobs with test failures are properly counted as failures."""
        with patch('pytorch_hud.server.mcp_server.get_commit_summary') as mock_get_commit_summary, \
             patch('pytorch_hud.server.mcp_server.api.get_hud_data') as mock_get_hud_data:
            
            # Setup mocks
            mock_get_commit_summary.return_value = self.commit_summary_sample
            mock_get_hud_data.return_value = self.test_failures_sample
            
            # Call the function
            result = await get_recent_commit_status("pytorch", "pytorch", count=1)
            
            # Verify job counts
            job_counts = result["commits"][0]["job_counts"]
            
            print(f"Job counts for test_failures_counted: {job_counts}")
            
            # This sample has:
            # - 2 traditional failures (conclusion = "failure")
            # - 1 job with success conclusion but failure lines (counted as success)
            # - 2 real successes (one with empty failureLines, one without)
            self.assertEqual(job_counts["total"], 5, "Should count all jobs")
            self.assertEqual(job_counts["success"], 3, "Should count 3 success jobs")
            self.assertEqual(job_counts["failure"], 2, "Should count 2 failures (only explicit failures)")
            self.assertEqual(job_counts["pending"], 0, "Should have no pending jobs")
            self.assertEqual(job_counts["skipped"], 0, "Should have no skipped jobs")
            
            # This commit should be marked as red due to failures
            self.assertEqual(result["commits"][0]["status"], "red")
        
    async def test_empty_jobs_handled(self):
        """Test that commits with no jobs are handled gracefully."""
        with patch('pytorch_hud.server.mcp_server.get_commit_summary') as mock_get_commit_summary, \
             patch('pytorch_hud.server.mcp_server.api.get_hud_data') as mock_get_hud_data:
            
            # Setup mocks
            mock_get_commit_summary.return_value = self.commit_summary_sample
            
            # Create a sample with no jobs
            empty_jobs_sample = {
                "shaGrid": [
                    {
                        "sha": "abcd1234",
                        "commitTitle": "Test commit",
                        "author": "test-user",
                        "time": "2025-03-06T22:02:26Z",
                        "prNum": 12345,
                        "jobs": []
                    }
                ]
            }
            mock_get_hud_data.return_value = empty_jobs_sample
            
            # Call the function
            result = await get_recent_commit_status("pytorch", "pytorch", count=1)
            
            # Verify job counts
            job_counts = result["commits"][0]["job_counts"]
            
            # All counts should be zero
            self.assertEqual(job_counts["total"], 0)
            self.assertEqual(job_counts["success"], 0)
            self.assertEqual(job_counts["failure"], 0)
            self.assertEqual(job_counts["pending"], 0)
            self.assertEqual(job_counts["skipped"], 0)
            
            # Status should be unknown
            self.assertEqual(result["commits"][0]["status"], "unknown")
        
    async def test_include_pending_parameter(self):
        """Test that the include_pending parameter works correctly."""
        with patch('pytorch_hud.server.mcp_server.get_commit_summary') as mock_get_commit_summary, \
             patch('pytorch_hud.server.mcp_server.api.get_hud_data') as mock_get_hud_data:
            
            # Setup mocks
            mock_get_commit_summary.return_value = self.commit_summary_sample
            
            # Create a sample with only pending jobs
            pending_jobs_sample = {
                "shaGrid": [
                    {
                        "sha": "abcd1234",
                        "commitTitle": "Test commit",
                        "author": "test-user",
                        "time": "2025-03-06T22:02:26Z",
                        "prNum": 12345,
                        "jobs": [
                            {"id": "job1", "status": "in_progress", "conclusion": "pending"},
                            {"id": "job2", "status": "queued", "conclusion": None}
                        ]
                    }
                ]
            }
            mock_get_hud_data.return_value = pending_jobs_sample
            
            # Test with include_pending=True (default)
            result_with_pending = await get_recent_commit_status("pytorch", "pytorch", count=1, include_pending=True)
            
            # Status should be pending
            self.assertEqual(result_with_pending["commits"][0]["status"], "pending")
            
            # Test with include_pending=False
            result_without_pending = await get_recent_commit_status("pytorch", "pytorch", count=1, include_pending=False)
            
            # Status should be unknown since we're ignoring pending jobs
            self.assertEqual(result_without_pending["commits"][0]["status"], "unknown")
            
            # Job counts should be the same in both cases
            self.assertEqual(result_with_pending["commits"][0]["job_counts"], 
                            result_without_pending["commits"][0]["job_counts"])

if __name__ == "__main__":
    import asyncio
    import sys
    
    async def run_tests():
        # Create test instance
        test_case = TestRecentCommitStatusParsing()
        # Run setup first
        test_case.setUp()
        
        # Now run individual tests
        print("\nRunning test_job_status_counting_from_sample:")
        await test_case.test_job_status_counting_from_sample()
        print("✓ test_job_status_counting_from_sample passed")
        
        print("\nRunning test_test_failures_counted:")
        await test_case.test_test_failures_counted()
        print("✓ test_test_failures_counted passed")
        
        print("\nRunning test_empty_jobs_handled:")
        await test_case.test_empty_jobs_handled()
        print("✓ test_empty_jobs_handled passed")
        
        print("\nRunning test_include_pending_parameter:")
        await test_case.test_include_pending_parameter()
        print("✓ test_include_pending_parameter passed")
    
    # Create a new event loop and run all tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_tests())
        print("\nAll tests passed! ✓")
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)