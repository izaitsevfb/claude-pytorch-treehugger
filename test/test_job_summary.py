import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytorch_hud.tools.hud_data import get_recent_commits_with_jobs


class TestJobSummary(unittest.IsolatedAsyncioTestCase):
    @patch('pytorch_hud.tools.hud_data.api')
    async def test_hidden_failures(self, mock_api):
        """Test that jobs with success conclusion but failure lines are counted as failures."""
        # Create a test case with hidden failures
        test_data = {
            "shaGrid": [
                {
                    "sha": "test_sha",
                    "commitTitle": "Test Commit",
                    "author": "Test Author",
                    "jobs": [
                        {
                            "id": "job1",
                            "conclusion": "success",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/jobs/456",
                            "failureLines": []  # No failure lines = real success
                        },
                        {
                            "id": "job2",
                            "conclusion": "success",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/jobs/789",
                            "failureLines": ["Error in test"]  # Has failure lines = hidden failure
                        },
                        {
                            "id": "job3",
                            "conclusion": "failure",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/jobs/101",
                            "failureLines": ["Explicit failure"]  # Explicit failure
                        }
                    ]
                }
            ],
            "jobNames": ["job1", "job2", "job3"]
        }
        
        # Mock the API response
        mock_api.get_hud_data.return_value = test_data
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call the function with mock context to get commit status info
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main", 
            ctx=mock_ctx
        )
        
        # Verify the commit and job counts
        self.assertEqual(len(result["commits"]), 1)
        commit = result["commits"][0]
        
        # Check job counts
        self.assertEqual(commit["job_counts"]["total"], 3)
        self.assertEqual(commit["job_counts"]["success"], 2)  # Both jobs with success conclusion
        self.assertEqual(commit["job_counts"]["failure"], 1)  # Only explicit failures counted
        
        # Make sure the API was called correctly
        mock_api.get_hud_data.assert_called_once()

    @patch('pytorch_hud.tools.hud_data.api')
    async def test_workflow_filtering(self, mock_api):
        """Test that workflow-related job filtering works correctly."""
        # Create a test case with workflow information in URLs
        test_data = {
            "shaGrid": [
                {
                    "sha": "test_sha",
                    "commitTitle": "Test Commit",
                    "author": "Test Author",
                    "jobs": [
                        {
                            "id": "job1",
                            "conclusion": "success",
                            "status": "completed",
                            "name": "workflow1_job1",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/workflow1/job/456",
                            "durationS": 60,
                            "failureLines": []  # No failure lines = real success
                        },
                        {
                            "id": "job2",
                            "conclusion": "success", 
                            "status": "completed",
                            "name": "workflow1_job2",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/workflow1/job/789",
                            "durationS": 90,
                            "failureLines": ["Error in test"]  # Has failure lines = hidden failure
                        },
                        {
                            "id": "job3",
                            "conclusion": "failure",
                            "status": "completed",
                            "name": "workflow2_job1",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/workflow2/job/101",
                            "durationS": 120,
                            "failureLines": ["Explicit failure"]  # Explicit failure
                        }
                    ]
                }
            ],
            "jobNames": ["workflow1_job1", "workflow1_job2", "workflow2_job1"]
        }
        
        # Mock the API response
        mock_api.get_hud_data.return_value = test_data
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call the function with job name regex to filter by workflow1
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main",
            include_success=True,
            include_failures=True,
            job_name_filter_regex="workflow1",
            ctx=mock_ctx
        )
        
        # Verify the results
        self.assertEqual(len(result["commits"]), 1)
        commit = result["commits"][0]
        
        # Check job counts for all jobs
        self.assertEqual(commit["job_counts"]["total"], 3)
        self.assertEqual(commit["job_counts"]["success"], 2)
        self.assertEqual(commit["job_counts"]["failure"], 1)
        
        # Check that only workflow1 jobs are included in the jobs array
        self.assertEqual(len(commit["jobs"]), 2)
        
        job_names = [job.get("name") for job in commit["jobs"]]
        self.assertIn("workflow1_job1", job_names)
        self.assertIn("workflow1_job2", job_names)
        self.assertNotIn("workflow2_job1", job_names)
    
    @patch('pytorch_hud.tools.hud_data.api')
    async def test_test_failure_line_filtering(self, mock_api):
        """Test that filtering by test failure patterns works correctly."""
        # Create a test case with various failure patterns
        test_data = {
            "shaGrid": [
                {
                    "sha": "test_sha",
                    "commitTitle": "Test Commit",
                    "author": "Test Author",
                    "jobs": [
                        {
                            "id": "job1",
                            "name": "test_job1",
                            "conclusion": "success",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/test_workflow/job/456",
                            "failureLines": []  # No failure lines = real success
                        },
                        {
                            "id": "job2",
                            "name": "test_job2",
                            "conclusion": "failure",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/test_workflow/job/789",
                            "failureLines": ["FAIL: test_function"]  # Test failure
                        },
                        {
                            "id": "job3",
                            "name": "test_job3",
                            "conclusion": "failure",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/test_workflow/job/101",
                            "failureLines": ["ERROR: test_another_function"]  # Another test failure
                        },
                        {
                            "id": "job4",
                            "name": "build_job",
                            "conclusion": "failure",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/build_workflow/job/102",
                            "failureLines": ["Some error but not a test-related error"]  # Build failure
                        }
                    ]
                }
            ],
            "jobNames": ["test_job1", "test_job2", "test_job3", "build_job"]
        }
        
        # Mock the API response
        mock_api.get_hud_data.return_value = test_data
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call the function to find test failures
        result = await get_recent_commits_with_jobs(
            "pytorch", "pytorch", "main", 
            include_failures=True,
            failure_line_filter_regex="(?:FAIL|ERROR):\\s+test_",  # Regex to match test failures
            ctx=mock_ctx
        )
        
        # Verify the results
        self.assertEqual(len(result["commits"]), 1)
        commit = result["commits"][0]
        
        # Check counts - should include all failures, but we only extract specific ones
        self.assertEqual(commit["job_counts"]["failure"], 3)
        
        # Check that only the test failure jobs are included in jobs array
        self.assertEqual(len(commit["jobs"]), 2)
        
        job_names = [job.get("name") for job in commit["jobs"]]
        self.assertIn("test_job2", job_names)
        self.assertIn("test_job3", job_names)
        self.assertNotIn("build_job", job_names)  # Build job should be filtered out


if __name__ == '__main__':
    unittest.main()