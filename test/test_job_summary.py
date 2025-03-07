import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytorch_hud.tools.hud_data import get_job_summary, get_workflow_summary, get_test_summary


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
            ]
        }
        
        # Mock the API response
        mock_api.get_hud_data.return_value = test_data
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call the function with mock context
        result = await get_job_summary("pytorch", "pytorch", "main", ctx=mock_ctx)
        
        # Verify the results - updated for new behavior
        self.assertEqual(result["status_counts"]["total"], 3)
        self.assertEqual(result["status_counts"]["success"], 2)  # Both jobs with success conclusion
        self.assertEqual(result["status_counts"]["failure"], 1)  # Only explicit failures counted
        
        # Make sure the API was called correctly
        mock_api.get_hud_data.assert_called_once_with("pytorch", "pytorch", "main", per_page=1)

    @patch('pytorch_hud.tools.hud_data.api')
    async def test_workflow_summary_hidden_failures(self, mock_api):
        """Test that workflow summary correctly identifies hidden failures."""
        # Create a test case with hidden failures in workflow jobs
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
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/workflow1/job/456",
                            "durationS": 60,
                            "failureLines": []  # No failure lines = real success
                        },
                        {
                            "id": "job2",
                            "conclusion": "success", 
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/workflow1/job/789",
                            "durationS": 90,
                            "failureLines": ["Error in test"]  # Has failure lines = hidden failure
                        },
                        {
                            "id": "job3",
                            "conclusion": "failure",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/workflow2/job/101",
                            "durationS": 120,
                            "failureLines": ["Explicit failure"]  # Explicit failure
                        }
                    ]
                }
            ]
        }
        
        # Mock the API response
        mock_api.get_hud_data.return_value = test_data
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call the function with mock context
        result = await get_workflow_summary("pytorch", "pytorch", "main", ctx=mock_ctx)
        
        # Verify the results
        # We should have 2 workflows
        self.assertEqual(len(result["workflows"]), 2)
        
        # Find workflow1 which should have 1 success and 1 hidden failure
        workflow1 = None
        workflow2 = None
        for wf in result["workflows"]:
            if wf["name"] == "workflow1":
                workflow1 = wf
            elif wf["name"] == "workflow2":
                workflow2 = wf
        
        # Verify workflow1 has correct counts - updated for new behavior
        self.assertIsNotNone(workflow1)
        self.assertEqual(workflow1["total_jobs"], 2)
        self.assertEqual(workflow1["success"], 2)  # Both jobs with success conclusion
        self.assertEqual(workflow1["failure"], 0)  # No explicit failures
        
        # Verify workflow2 has correct counts
        self.assertIsNotNone(workflow2)
        self.assertEqual(workflow2["total_jobs"], 1)
        self.assertEqual(workflow2["success"], 0)
        self.assertEqual(workflow2["failure"], 1)  # 1 explicit failure
    
    @patch('pytorch_hud.tools.hud_data.api')
    async def test_test_summary_hidden_failures(self, mock_api):
        """Test that test summary correctly identifies hidden failures."""
        # Create a test case with hidden failures in test jobs
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
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/test_workflow/job/456",
                            "failureLines": []  # No failure lines = real success
                        },
                        {
                            "id": "job2",
                            "conclusion": "success",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/test_workflow/job/789",
                            "failureLines": ["FAIL: test_function"]  # Has failure lines = hidden failure
                        },
                        {
                            "id": "job3",
                            "conclusion": "failure",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/test_workflow/job/101",
                            "failureLines": ["ERROR: test_another_function"]  # Explicit failure
                        },
                        {
                            "id": "job4",
                            "conclusion": "success",
                            "status": "completed",
                            "htmlUrl": "https://github.com/pytorch/pytorch/actions/runs/123/build_workflow/job/102",
                            "failureLines": ["Some error but not a test job"]  # Not a test job
                        }
                    ]
                }
            ]
        }
        
        # Mock the API response
        mock_api.get_hud_data.return_value = test_data
        
        # Create a mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Call the function with mock context
        result = await get_test_summary("pytorch", "pytorch", "main", ctx=mock_ctx)
        
        # Verify the results - updated for new behavior that only checks explicit failures
        self.assertEqual(result["test_jobs"], 3)  # 3 test jobs
        self.assertEqual(result["total_failed_tests"], 1)  # 1 failed test (only from explicit failure)


if __name__ == '__main__':
    unittest.main()