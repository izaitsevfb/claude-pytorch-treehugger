#!/usr/bin/env python3
"""
Test script for validating the get_recent_commit_status function in the PyTorch HUD MCP server.

This test verifies that the function correctly counts jobs by status and identifies
red, green, and pending commits.
"""

import unittest
from unittest.mock import patch

from pytorch_hud.server.mcp_server import get_recent_commit_status

# Sample HUD response with various job statuses for testing
SAMPLE_HUD_DATA = {
    "shaGrid": [
        {
            "sha": "abcd1234",
            "commitTitle": "Test commit",
            "author": "test-user",
            "time": "2025-03-06T22:02:26Z",
            "prNum": 12345,
            "jobs": [
                {"id": "job1", "status": "completed", "conclusion": "success"},
                {"id": "job2", "status": "completed", "conclusion": "failure"},
                {"id": "job3", "status": "completed", "conclusion": "skipped"},
                {"id": "job4", "status": "in_progress", "conclusion": "pending"},
                {"id": "job5", "status": "queued", "conclusion": None},
                {"id": "job6", "status": "completed", "conclusion": "success"}
            ]
        }
    ]
}

# Sample commit response for testing
SAMPLE_COMMIT_DATA = {
    "sha": "abcd1234",
    "commitTitle": "Test commit",
    "author": "test-user",
    "time": "2025-03-06T22:02:26Z",
    "prNum": 12345
}

class TestRecentCommitStatus(unittest.IsolatedAsyncioTestCase):
    """Tests for the get_recent_commit_status function."""

    async def test_job_status_counting(self):
        """Test that jobs are correctly counted by status."""
        # Setup mocks
        with patch('pytorch_hud.server.mcp_server.api.get_hud_data') as mock_get_hud_data:
            # Now we directly use the shaGrid data from the HUD response
            # without calling get_commit_summary
            mock_get_hud_data.return_value = {
                "shaGrid": [
                    {
                        "sha": SAMPLE_COMMIT_DATA["sha"],
                        "commitTitle": SAMPLE_COMMIT_DATA["commitTitle"],
                        "author": SAMPLE_COMMIT_DATA["author"],
                        "time": SAMPLE_COMMIT_DATA["time"],
                        "prNum": SAMPLE_COMMIT_DATA["prNum"],
                        "jobs": SAMPLE_HUD_DATA["shaGrid"][0]["jobs"]
                    }
                ]
            }
            
            # Call the function
            result = await get_recent_commit_status("pytorch", "pytorch", count=1)
            
            # Verify the result
            self.assertEqual(len(result["commits"]), 1)
            commit = result["commits"][0]
            
            # Check job counts
            job_counts = commit["job_counts"]
            self.assertEqual(job_counts["total"], 6)
            self.assertEqual(job_counts["success"], 2)
            self.assertEqual(job_counts["failure"], 1)
            self.assertEqual(job_counts["pending"], 2)  # 1 in_progress + 1 queued
            self.assertEqual(job_counts["skipped"], 1)
            
            # Check commit status
            self.assertEqual(commit["status"], "red")  # Should be red due to failure
            
            # Verify mock calls
            mock_get_hud_data.assert_called_once()

    async def test_status_determination(self):
        """Test that commit status is correctly determined."""
        # Test cases with different job combinations
        test_cases = [
            # Only success jobs - should be green
            {
                "jobs": [
                    {"id": "job1", "status": "completed", "conclusion": "success"},
                    {"id": "job2", "status": "completed", "conclusion": "success"}
                ],
                "expected_status": "green"
            },
            # Mix of success and pending - should be pending
            {
                "jobs": [
                    {"id": "job1", "status": "completed", "conclusion": "success"},
                    {"id": "job2", "status": "in_progress", "conclusion": None}
                ],
                "expected_status": "pending"
            },
            # Any failure means red status
            {
                "jobs": [
                    {"id": "job1", "status": "completed", "conclusion": "success"},
                    {"id": "job2", "status": "completed", "conclusion": "failure"},
                    {"id": "job3", "status": "in_progress", "conclusion": None}
                ],
                "expected_status": "red"
            },
            # Empty job list - should be unknown
            {
                "jobs": [],
                "expected_status": "unknown"
            }
        ]
        
        with patch('pytorch_hud.server.mcp_server.api.get_hud_data') as mock_get_hud_data:
                
            for i, test_case in enumerate(test_cases):
                # Setup mocks for this test case
                hud_data = {
                    "shaGrid": [
                        {
                            "sha": "abcd1234",
                            "commitTitle": "Test commit",
                            "author": "test-user",
                            "time": "2025-03-06T22:02:26Z",
                            "prNum": 12345,
                            "jobs": test_case["jobs"]
                        }
                    ]
                }
                mock_get_hud_data.return_value = hud_data
                
                # Call the function
                result = await get_recent_commit_status("pytorch", "pytorch", count=1)
                
                # Verify the result
                self.assertEqual(len(result["commits"]), 1)
                commit = result["commits"][0]
                
                # Check commit status matches expected
                self.assertEqual(commit["status"], test_case["expected_status"], 
                                f"Test case {i} failed: expected {test_case['expected_status']}, got {commit['status']}")
                
                # Reset mock calls count
                mock_get_hud_data.reset_mock()

    async def test_multiple_commits(self):
        """Test that multiple commits are handled correctly."""
        with patch('pytorch_hud.server.mcp_server.api.get_hud_data') as mock_get_hud_data:
            # Create multiple commits in a single response
            hud_data = {
                "shaGrid": [
                    {
                        "sha": "commit1",
                        "commitTitle": "Test commit 1",
                        "author": "test-user",
                        "time": "2025-03-06T22:02:26Z",
                        "prNum": 12345,
                        "jobs": [
                            {"id": "job1", "status": "completed", "conclusion": "success"},
                            {"id": "job2", "status": "completed", "conclusion": "success"}
                        ]
                    },
                    {
                        "sha": "commit2",
                        "commitTitle": "Test commit 2",
                        "author": "test-user",
                        "time": "2025-03-05T22:02:26Z",
                        "prNum": 12346,
                        "jobs": [
                            {"id": "job3", "status": "completed", "conclusion": "failure"},
                            {"id": "job4", "status": "completed", "conclusion": "success"}
                        ]
                    },
                    {
                        "sha": "commit3",
                        "commitTitle": "Test commit 3",
                        "author": "test-user",
                        "time": "2025-03-04T22:02:26Z",
                        "prNum": 12347,
                        "jobs": [
                            {"id": "job5", "status": "in_progress", "conclusion": None},
                            {"id": "job6", "status": "queued", "conclusion": None}
                        ]
                    }
                ]
            }
            mock_get_hud_data.return_value = hud_data
            
            # Call the function with count=3
            result = await get_recent_commit_status("pytorch", "pytorch", count=3)
            
            # Verify the result
            self.assertEqual(len(result["commits"]), 3)
            
            # Check statuses of individual commits
            self.assertEqual(result["commits"][0]["status"], "green")
            self.assertEqual(result["commits"][1]["status"], "red")
            self.assertEqual(result["commits"][2]["status"], "pending")
            
            # Check summary counts
            self.assertEqual(result["summary"]["total_commits"], 3)
            self.assertEqual(result["summary"]["red_commits"], 1)
            self.assertEqual(result["summary"]["green_commits"], 1)
            self.assertEqual(result["summary"]["pending_commits"], 1)

if __name__ == "__main__":
    import asyncio
    
    # Create a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run the tests
    unittest.main()