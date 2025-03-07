import unittest

from pytorch_hud.tools.hud_data import get_hud_data


class TestGetHudDataLive(unittest.IsolatedAsyncioTestCase):
    """Test get_hud_data against real HTTP calls."""

    async def test_branch_and_commit_sha_behavior(self):
        """
        Test that get_hud_data correctly handles both branch names and commit SHAs.
        
        1. Call with branch name 'main' to get recent commits
        2. Extract a specific commit SHA from the results
        3. Call again with that specific commit SHA
        4. Verify that the specific commit is the first in the results
        
        Note: The branch_or_commit_sha parameter determines what's returned:
        - Branch name ('main'): Returns recent commits from that branch
        - Commit SHA: Returns commits starting from that specific commit
        """
        # 1. Get recent commits from branch
        branch_data = await get_hud_data(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha="main",  # Pass branch name to get recent commits
            per_page=3  # Get multiple commits
        )
        
        self.assertIsNotNone(branch_data)
        self.assertIn("shaGrid", branch_data)
        self.assertGreater(len(branch_data["shaGrid"]), 1, "Expected multiple commits from branch")
        
        # 2. Extract a specific commit SHA
        all_shas = []
        for commit_data in branch_data["shaGrid"]:
            sha = commit_data.get("sha")
            if sha:
                all_shas.append(sha)
        
        self.assertGreater(len(all_shas), 1, "Expected multiple commit SHAs")
        first_commit_sha = all_shas[0]  # Use the first commit
        last_commit_sha = all_shas[-1]  # Use the last commit
        
        # 3a. Call with the first commit SHA
        first_commit_data = await get_hud_data(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha=first_commit_sha,  # Pass first commit SHA
            per_page=3  # Request more than one
        )
        
        # 3b. Call with the last commit SHA
        last_commit_data = await get_hud_data(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha=last_commit_sha,  # Pass last commit SHA
            per_page=3  # Request more than one
        )
        
        # 4a. Verify that the first commit is included in the results
        self.assertIsNotNone(first_commit_data)
        self.assertIn("shaGrid", first_commit_data)
        
        # The API returns commits starting from the specified SHA
        self.assertGreaterEqual(len(first_commit_data["shaGrid"]), 1)
        
        # Verify that the first commit SHA matches our request
        first_returned_sha = first_commit_data["shaGrid"][0].get("sha")
        self.assertEqual(
            first_returned_sha, 
            first_commit_sha, 
            f"Expected first SHA to be {first_commit_sha}, got {first_returned_sha}"
        )
        
        # Check that we got the right number of items based on per_page
        self.assertLessEqual(
            len(first_commit_data["shaGrid"]), 
            3,  # We requested per_page=3
            "Should not exceed per_page value"
        )
        
        # 4b. Verify that the last commit is included in the results
        self.assertIsNotNone(last_commit_data)
        self.assertIn("shaGrid", last_commit_data)
        
        # The API returns commits starting from the specified SHA
        self.assertGreaterEqual(len(last_commit_data["shaGrid"]), 1)
        
        # Verify that the first commit SHA in the response matches our requested last commit
        last_returned_sha = last_commit_data["shaGrid"][0].get("sha")
        self.assertEqual(
            last_returned_sha, 
            last_commit_sha, 
            f"Expected first SHA to be {last_commit_sha}, got {last_returned_sha}"
        )
        
        # Check that we got the right number of items based on per_page
        self.assertLessEqual(
            len(last_commit_data["shaGrid"]), 
            3,  # We requested per_page=3
            "Should not exceed per_page value"
        )
    
    async def test_pagination(self):
        """
        Test that per_page parameter correctly limits the number of results.
        """
        # Get with per_page=1
        single_data = await get_hud_data(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha="main",
            per_page=1
        )
        
        self.assertIsNotNone(single_data)
        self.assertIn("shaGrid", single_data)
        self.assertEqual(len(single_data["shaGrid"]), 1, "Should return exactly 1 commit")
        
        # Get with per_page=3
        multi_data = await get_hud_data(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha="main",
            per_page=3
        )
        
        self.assertIsNotNone(multi_data)
        self.assertIn("shaGrid", multi_data)
        self.assertGreaterEqual(len(multi_data["shaGrid"]), 2, "Should return multiple commits")
        self.assertLessEqual(len(multi_data["shaGrid"]), 3, "Should not exceed per_page")
        
        # First commit from both requests should be the same (latest on main)
        first_sha_single = single_data["shaGrid"][0].get("sha")
        first_sha_multi = multi_data["shaGrid"][0].get("sha")
        
        self.assertEqual(
            first_sha_single, 
            first_sha_multi, 
            "First commit should be the same regardless of per_page"
        )
        
    async def test_commit_sequence(self):
        """
        Test that when using a commit SHA, the API returns a sequence of commits 
        starting from that commit, not just the specific commit.
        
        This verifies our understanding and documentation of the API behavior.
        """
        # First get a sequence of commits from main
        main_data = await get_hud_data(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha="main",
            per_page=3  # Get 3 commits
        )
        
        self.assertIsNotNone(main_data)
        self.assertIn("shaGrid", main_data)
        self.assertGreaterEqual(len(main_data["shaGrid"]), 2, "Expected at least 2 commits")
        
        # Extract the second commit SHA
        second_commit_sha = main_data["shaGrid"][1].get("sha")
        
        # Now fetch using that second commit SHA with per_page=2
        second_commit_data = await get_hud_data(
            repo_owner="pytorch",
            repo_name="pytorch",
            branch_or_commit_sha=second_commit_sha,
            per_page=2  # Get 2 commits
        )
        
        self.assertIsNotNone(second_commit_data)
        self.assertIn("shaGrid", second_commit_data)
        
        # Verify that the API returns a sequence starting from the second commit
        self.assertGreaterEqual(len(second_commit_data["shaGrid"]), 1, "Expected at least 1 commit")
        
        # The first returned commit should be the second commit from the main query
        first_returned_sha = second_commit_data["shaGrid"][0].get("sha")
        self.assertEqual(
            first_returned_sha,
            second_commit_sha,
            f"Expected the first returned commit to be {second_commit_sha}"
        )
        
        # If we got more than one commit back, the second one should be the third from main
        if len(second_commit_data["shaGrid"]) > 1 and len(main_data["shaGrid"]) > 2:
            third_commit_sha = main_data["shaGrid"][2].get("sha")
            second_returned_sha = second_commit_data["shaGrid"][1].get("sha")
            
            self.assertEqual(
                second_returned_sha,
                third_commit_sha,
                "The sequence of commits should be preserved"
            )


if __name__ == "__main__":
    unittest.main()