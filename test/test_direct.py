#!/usr/bin/env python3
"""
Simple test script to verify that the async functions can be called directly
"""

import asyncio
import json

from pytorch_hud.tools.hud_data import get_recent_commits_with_jobs

async def main():
    print("Testing async function calls directly...")
    try:
        # Use the consolidated function with include_failures=True
        result = await get_recent_commits_with_jobs(
            "pytorch", 
            "pytorch", 
            "main",
            include_failures=True,
            page=1, 
            per_page=2
        )
        # Count the failed jobs across all commits
        failed_job_count = sum(
            len(commit.get("jobs", [])) 
            for commit in result.get("commits", [])
        )
        print(f"Success! Got {failed_job_count} failed jobs across {len(result.get('commits', []))} commits")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())