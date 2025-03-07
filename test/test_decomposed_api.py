#!/usr/bin/env python3
"""
Test script demonstrating the use of decomposed PyTorch HUD APIs for better context management.

This script shows how to use the specialized endpoints to get specific pieces of information
without overwhelming the context window with unnecessary data.
"""

import asyncio
import json
import time
from typing import Dict, Any

# Import the MCP functions directly for testing
from pytorch_hud.tools.hud_data import (
    get_commit_summary,
    get_job_summary,
    get_filtered_jobs,
    get_failure_details,
    get_job_details,
    get_workflow_summary,
    get_test_summary
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

async def test_decomposed_apis():
    print("Testing PyTorch HUD Decomposed APIs")
    
    # Set up test parameters
    repo_owner = "pytorch"
    repo_name = "pytorch"
    branch = "main"
    commit_sha = "679e7d257e6429a131b18406be84318f0554bc16"  # Example commit SHA
    
    # 1. Get commit summary (lightweight, without jobs)
    print("\nStep 1: Get commit summary without job data")
    start_time = time.time()
    commit_summary = await get_commit_summary(repo_owner, repo_name, branch, commit_sha)
    print_response("Commit Summary", commit_summary)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 2. Get job status summary (counts only, no details)
    print("\nStep 2: Get job status summary (counts only)")
    start_time = time.time()
    job_summary = await get_job_summary(repo_owner, repo_name, branch, commit_sha)
    print_response("Job Summary", job_summary)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 3. Get filtered jobs (only failures)
    print("\nStep 3: Get filtered jobs (only failures)")
    start_time = time.time()
    filtered_jobs = await get_filtered_jobs(
        repo_owner, repo_name, branch, commit_sha,
        status="failure", per_page=5
    )
    print_response("Filtered Jobs (Failures)", filtered_jobs)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 4. Get detailed failure information
    print("\nStep 4: Get detailed failure information")
    start_time = time.time()
    failure_details = await get_failure_details(repo_owner, repo_name, branch, commit_sha)
    print_response("Failure Details", failure_details)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 5. Get workflow summary
    print("\nStep 5: Get workflow summary")
    start_time = time.time()
    workflow_summary = await get_workflow_summary(repo_owner, repo_name, branch, commit_sha)
    print_response("Workflow Summary", workflow_summary)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # 6. Get test summary
    print("\nStep 6: Get test summary")
    start_time = time.time()
    test_summary = await get_test_summary(repo_owner, repo_name, branch, commit_sha)
    print_response("Test Summary", test_summary)
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    # If there are any failed jobs, get details for the first one
    job_id = None
    if filtered_jobs.get("jobs") and len(filtered_jobs["jobs"]) > 0:
        job_id = filtered_jobs["jobs"][0].get("id")
    
    if job_id:
        # 7. Get details for a specific job
        print(f"\nStep 7: Get details for a specific job (ID: {job_id})")
        start_time = time.time()
        job_details = await get_job_details(job_id)
        print_response("Job Details", job_details)
        print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(test_decomposed_apis())