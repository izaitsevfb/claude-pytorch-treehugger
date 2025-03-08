#!/usr/bin/env python3
"""
Test script for validating the get_recent_commits_with_jobs function on real data.

This tests the actual PyTorch HUD API response to verify that our function 
correctly processes real data and returns unique commits.
"""

import asyncio
import json
from datetime import datetime

# Import the function directly for testing
from pytorch_hud.tools.hud_data import get_recent_commits_with_jobs

async def run_test():
    """Test the get_recent_commits_with_jobs function on real data."""
    print(f"Starting test at {datetime.now().isoformat()}")
    
    # Set the number of commits to fetch
    per_page = 5
    
    print(f"Fetching {per_page} recent commits from PyTorch HUD API...")
    result = await get_recent_commits_with_jobs(
        repo_owner="pytorch", 
        repo_name="pytorch", 
        branch_or_commit_sha="main",
        per_page=per_page,
        # Don't include job details to minimize response size
        include_success=False,
        include_pending=False,
        include_failures=False
    )
    
    # Print basic information about the results
    print(f"\nReceived {len(result['commits'])} commits:")
    
    for i, commit in enumerate(result['commits']):
        print(f"\nCommit {i+1}:")
        print(f"  SHA: {commit['sha']} ({commit['short_sha']})")
        print(f"  Title: {commit['title']}")
        print(f"  Author: {commit['author']}")
        print(f"  Time: {commit['time']}")
        print(f"  PR: {commit.get('prNum')}")  # May use different field name
        print(f"  Status: {commit['status']}")
        print("  Job counts:")
        for status, count in commit['job_counts'].items():
            print(f"    {status}: {count}")
    
    # Check if we have duplicated commits (same SHA)
    shas = [commit['sha'] for commit in result['commits']]
    unique_shas = set(shas)
    
    if len(shas) == len(unique_shas):
        print("\n✅ Success: All commits have unique SHAs")
    else:
        print("\n❌ Error: Found duplicate commits")
        # Find the duplicates
        duplicates = {}
        for sha in shas:
            if shas.count(sha) > 1 and sha not in duplicates:
                duplicates[sha] = shas.count(sha)
        
        for sha, count in duplicates.items():
            print(f"  SHA {sha} appears {count} times")
    
    # Check pagination info
    print("\nPagination information:")
    for key, value in result['pagination'].items():
        print(f"  {key}: {value}")
    
    # Save the result to a file for further examination
    output_file = "test/fixtures/recent_commit_status_output.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nDetailed results saved to {output_file}")

if __name__ == "__main__":
    # Create a new event loop and run the test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_test())
        print("\nTest completed successfully ✅")
    except Exception as e:
        print(f"\nTest failed: {e} ❌")
        raise e