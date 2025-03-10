#!/usr/bin/env python3
"""
Test script demonstrating the use of the consolidated PyTorch HUD APIs for better context management.

This script shows how to use the get_recent_commits_with_jobs endpoint with different options
to get specific pieces of information without overwhelming the context window with unnecessary data.
"""

import asyncio
import json
import time
from typing import Dict, Any

# Import the MCP functions directly for testing
from pytorch_hud.tools.hud_data import (
    get_job_details,
    get_recent_commits_with_jobs
)

def print_response(name: str, response: Dict[str, Any]) -> None:
    """Helper to print responses in a readable format"""
    print(f"\n===== {name} =====")
    json_str = json.dumps(response, indent=2)
    # Print truncated response if it's too long
    if len(json_str) > 500:
        print(json_str[:500] + "...")
    else:
        print(json_str)
    
    # Also print the size of the response in bytes
    print(f"Response size: {len(json_str)} bytes")

async def test_api():
    print("Testing PyTorch HUD Consolidated APIs")
    
    # Set up test parameters
    repo_owner = "pytorch"
    repo_name = "pytorch"
    branch = "main"
    commit_sha = "679e7d257e6429a131b18406be84318f0554bc16"  # Example commit SHA
    
    # 1. Get basic commit data
    print("\nStep 1: Get basic commit data")
    start_time = time.time()
    basic_data = await get_recent_commits_with_jobs(repo_owner, repo_name, branch)
    print_response("Basic Data", basic_data)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 2. Get commit summary (lightweight, without jobs)
    print("\nStep 2: Get commit summary without job data")
    start_time = time.time()
    commit_summary = await get_recent_commits_with_jobs(
        repo_owner, repo_name, commit_sha, 
        include_commit_details=True
    )
    print_response("Commit Summary", commit_summary)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 3. Get filtered jobs (only failures)
    print("\nStep 3: Get filtered jobs (only failures)")
    start_time = time.time()
    filtered_jobs = await get_recent_commits_with_jobs(
        repo_owner, repo_name, branch,
        include_failures=True,
        per_page=5
    )
    print_response("Filtered Jobs (Failures)", filtered_jobs)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 4. Get detailed failure information with failure lines
    print("\nStep 4: Get detailed failure information")
    start_time = time.time()
    failure_details = await get_recent_commits_with_jobs(
        repo_owner, repo_name, branch,
        include_failures=True,
        include_commit_details=True,
        per_page=3
    )
    print_response("Failure Details", failure_details)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 5. Get GPU job failures
    print("\nStep 5: Get GPU job failures")
    start_time = time.time()
    gpu_jobs = await get_recent_commits_with_jobs(
        repo_owner, repo_name, branch,
        include_failures=True,
        job_name_filter_regex="cuda|gpu",
        per_page=3
    )
    print_response("GPU Job Failures", gpu_jobs)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 6. Get OOM failures
    print("\nStep 6: Get OOM failures")
    start_time = time.time()
    oom_failures = await get_recent_commits_with_jobs(
        repo_owner, repo_name, branch,
        include_failures=True,
        failure_line_filter_regex="OOM|OutOfMemoryError|out of memory",
        per_page=3
    )
    print_response("OOM Failures", oom_failures)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # Try to get some job ID from the results to use in next step
    job_id = None
    for commit in failure_details.get("commits", []):
        if "jobs" in commit and commit["jobs"]:
            for job in commit["jobs"]:
                if "id" in job:
                    job_id = job["id"]
                    break
            if job_id:
                break
    
    if job_id:
        # 7. Get details for a specific job
        print(f"\nStep 7: Get details for a specific job (ID: {job_id})")
        start_time = time.time()
        job_details = await get_job_details(job_id)
        print_response("Job Details", job_details)
        print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(test_api())