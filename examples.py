from pytorch_hud import PyTorchHudAPI
from datetime import datetime, timedelta
import json

# Initialize the API client
api = PyTorchHudAPI()

# Current time and 7 days ago for queries that need time ranges
now = datetime.now()
end_time = now.isoformat()
start_time = (now - timedelta(days=7)).isoformat()

def print_response(name, response):
    """Helper to print responses in a readable format"""
    print(f"\n===== {name} =====")
    print(json.dumps(response, indent=2)[:500] + "..." if len(json.dumps(response)) > 500 else json.dumps(response, indent=2))

# Example 1: Get HUD data (original, large API)
try:
    # Using branch name "main" to get recent commits
    branch_hud_data = api.get_hud_data("pytorch", "pytorch", "main", per_page=1, merge_lf=True)
    print_response("HUD Data for branch 'main' (Full API)", branch_hud_data)
    
    # If we extract a specific SHA from the first response
    if "shaGrid" in branch_hud_data and len(branch_hud_data["shaGrid"]) > 0:
        specific_sha = branch_hud_data["shaGrid"][0]["sha"]
        # We can request data for that specific SHA
        commit_hud_data = api.get_hud_data("pytorch", "pytorch", specific_sha, per_page=1, merge_lf=True)
        print_response(f"HUD Data for commit '{specific_sha[:7]}' (Full API)", commit_hud_data)
except Exception as e:
    print(f"Error getting HUD data: {e}")

# Example 1a: Using decomposed APIs for better context management
print("\n===== DECOMPOSED API EXAMPLES =====")

# 1. Get commit summary without job data
try:
    # Note: This API doesn't yet exist in the base PyTorchHudAPI 
    # These are examples of what the decomposed API would look like
    
    # Decomposed API would have something like:
    # commit_summary = api.get_commit_summary("pytorch", "pytorch", "main")
    # print_response("Commit Summary (without jobs)", commit_summary)
    
    # For now, we'll simulate it by extracting from the full API response:
    commit_info = branch_hud_data["shaGrid"][0].copy()
    if "jobs" in commit_info:
        del commit_info["jobs"]
    print_response("Commit Summary (without jobs)", commit_info)
except Exception as e:
    print(f"Error getting commit summary: {e}")

# 2. Get job status summary
try:
    # Simulate a job status summary API
    status_counts = {
        "success": 0,
        "failure": 0,
        "pending": 0,
        "skipped": 0,
        "total": 0
    }
    
    if "shaGrid" in branch_hud_data and len(branch_hud_data["shaGrid"]) > 0 and "jobs" in branch_hud_data["shaGrid"][0]:
        jobs = branch_hud_data["shaGrid"][0]["jobs"]
        for job in jobs:
            status_counts["total"] += 1
            conclusion = job.get("conclusion", "unknown")
            if conclusion == "success":
                status_counts["success"] += 1
            elif conclusion == "failure":
                status_counts["failure"] += 1
            elif conclusion == "skipped":
                status_counts["skipped"] += 1
            elif conclusion == "pending":
                status_counts["pending"] += 1
    
    print_response("Job Status Summary", status_counts)
except Exception as e:
    print(f"Error getting job summary: {e}")

# 3. Get only failed jobs
try:
    # Simulate a failed jobs API
    failed_jobs = []
    
    if "shaGrid" in branch_hud_data and len(branch_hud_data["shaGrid"]) > 0 and "jobs" in branch_hud_data["shaGrid"][0]:
        jobs = branch_hud_data["shaGrid"][0]["jobs"]
        for job in jobs:
            if job.get("conclusion") == "failure":
                # Extract only the necessary failure information
                failed_job = {
                    "id": job.get("id"),
                    "htmlUrl": job.get("htmlUrl", ""),
                    "failureLines": job.get("failureLines", [])
                }
                failed_jobs.append(failed_job)
    
    print_response("Failed Jobs Only", {"failed_count": len(failed_jobs), "jobs": failed_jobs})
except Exception as e:
    print(f"Error getting failed jobs: {e}")

# Example 2: Master commit red data
try:
    master_red = api.get_master_commit_red(start_time, end_time)
    print_response("Master Commit Red", master_red)
except Exception as e:
    print(f"Error getting master commit red data: {e}")

# Example 3: Queued jobs
try:
    queued_jobs = api.get_queued_jobs()
    print_response("Queued Jobs", queued_jobs)
except Exception as e:
    print(f"Error getting queued jobs: {e}")

# Example 4: Disabled test historical
try:
    disabled_tests = api.get_disabled_test_historical(
        start_time, 
        end_time,
        label="skipped",
        repo="pytorch/pytorch",
        state="open",
        granularity="day"
    )
    print_response("Disabled Tests Historical", disabled_tests)
except Exception as e:
    print(f"Error getting disabled tests: {e}")

# Example 5: Unique repos in runner cost
try:
    repos_in_cost = api.get_unique_repos_in_runnercost(start_time, end_time)
    print_response("Unique Repos in Runner Cost", repos_in_cost)
except Exception as e:
    print(f"Error getting repos in runner cost: {e}")

# Example 6: Job annotations
try:
    job_annotation_params = {
        "branch": "main",
        "repo": "pytorch/pytorch",
        "startTime": (now - timedelta(days=1)).isoformat(),
        "stopTime": end_time
    }
    job_annotations = api.get_job_annotation("pytorch", "pytorch", "failures", job_annotation_params)
    print_response("Job Annotations", job_annotations)
except Exception as e:
    print(f"Error getting job annotations: {e}")

# Example 7: Get artifacts for a specific job
try:
    artifacts = api.get_artifacts("s3", "13691336848")
    print_response("Artifacts", artifacts)
except Exception as e:
    print(f"Error getting artifacts: {e}")

# Example 8: Get utilization metadata
try:
    utilization_metadata = api.get_utilization_metadata("13691336929")
    print_response("Utilization Metadata", utilization_metadata)
except Exception as e:
    print(f"Error getting utilization metadata: {e}")

# Example 9: Get specific commit data
try:
    commit_data = api.get_commit_data("pytorch", "pytorch", "1fac47702e830f95b0f22409036babb0842ff5da")
    print_response("Commit Data", commit_data)
except Exception as e:
    print(f"Error getting commit data: {e}")

# Example 10: Get issue data
try:
    issue_data = api.get_issue_data("ci: sev")
    print_response("Issue Data", issue_data)
except Exception as e:
    print(f"Error getting issue data: {e}")

# Test for the fixed async functions
print("\n===== TESTING FIXED FUNCTIONS =====")
print("These would normally be tested via the MCP server through resource endpoints.")
print("Direct function calls to these async functions should now work properly.")
print("The MCP server no longer tries to register these async functions directly.")
print("Instead, it registers resource endpoints that properly await the async functions.")

print("\nAll examples completed!")