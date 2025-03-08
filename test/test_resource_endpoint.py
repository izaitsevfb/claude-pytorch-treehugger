#!/usr/bin/env python3
"""
Test the resource endpoint for the universal function get_recent_commits_with_jobs_resource
"""

import asyncio
import json

from pytorch_hud.server.mcp_server import get_recent_commits_with_jobs_resource

async def main():
    print("Testing resource endpoint...")
    try:
        # Using the universal function to get failures specifically
        result = await get_recent_commits_with_jobs_resource(
            repo_owner="pytorch", 
            repo_name="pytorch", 
            branch_or_commit_sha="3960f978325222392d89ecdeb0d5baf968f654a7",
            include_success=False,
            include_pending=False,
            include_failures=True,
            page=1, 
            per_page=2
        )
        # Result is a JSON string from the resource endpoint
        result_data = json.loads(result)
        
        # Find failure jobs in the first commit
        failure_count = 0
        if "commits" in result_data and len(result_data["commits"]) > 0:
            if "jobs" in result_data["commits"][0]:
                failure_count = len(result_data["commits"][0]["jobs"])
                
        print(f"Success! Got {failure_count} failed jobs")
        print(json.dumps(result_data, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())