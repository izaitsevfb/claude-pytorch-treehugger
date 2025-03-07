#!/usr/bin/env python3
"""
Script to analyze the real data in hud_data_response_sample_per_page_50.json
using the updated failure detection logic.
"""

import json

def analyze_job_statuses(data):
    """
    Analyze job statuses in the data, using our updated failure detection logic.
    """
    if not data or "shaGrid" not in data or not data["shaGrid"]:
        print("No shaGrid data found")
        return
    
    # Analyze all shaGrid entries, not just the first one
    all_jobs = []
    for grid_entry in data["shaGrid"]:
        all_jobs.extend(grid_entry.get("jobs", []))
    
    print(f"Analyzing {len(all_jobs)} jobs across all shaGrid entries")
    jobs = all_jobs
    if not jobs:
        print("No jobs found in shaGrid")
        return
    
    # Count jobs by status using both original and updated logic
    original_status_counts = {
        "success": 0,
        "failure": 0,
        "skipped": 0,
        "pending": 0,
        "in_progress": 0,
        "queued": 0,
        "total": 0
    }
    
    updated_status_counts = {
        "success": 0,
        "failure": 0,
        "skipped": 0,
        "pending": 0,
        "in_progress": 0,
        "queued": 0,
        "hidden_failure": 0,  # Special category for hidden failures
        "total": 0
    }
    
    # List to store hidden failures for detailed inspection
    hidden_failures = []
    
    for job in jobs:
        if not job:  # Skip empty job entries
            continue
            
        original_status_counts["total"] += 1
        updated_status_counts["total"] += 1
        
        status = job.get("status", "unknown")
        conclusion = job.get("conclusion", "unknown")
        
        # Check for hidden failures (success conclusion but with failure lines)
        has_failure_lines = bool(job.get("failureLines", []))
        
        # Original logic - just based on conclusion/status
        if conclusion == "success":
            original_status_counts["success"] += 1
        elif conclusion == "failure":
            original_status_counts["failure"] += 1
        elif conclusion == "skipped":
            original_status_counts["skipped"] += 1
        elif status == "queued":
            original_status_counts["queued"] += 1
        elif status == "in_progress":
            original_status_counts["in_progress"] += 1
        elif conclusion == "pending":
            original_status_counts["pending"] += 1
        
        # Updated logic - checks for hidden failures
        if has_failure_lines:
            updated_status_counts["failure"] += 1
            if conclusion == "success":
                updated_status_counts["hidden_failure"] += 1
                hidden_failures.append(job)
        elif conclusion == "success":
            updated_status_counts["success"] += 1
        elif conclusion == "failure":
            updated_status_counts["failure"] += 1
        elif conclusion == "skipped":
            updated_status_counts["skipped"] += 1
        elif status == "queued":
            updated_status_counts["queued"] += 1
        elif status == "in_progress":
            updated_status_counts["in_progress"] += 1
        elif conclusion == "pending":
            updated_status_counts["pending"] += 1
    
    # Print results
    print("Job Status Analysis")
    print("-----------------")
    print("Original Logic (Before Fix):")
    print(f"- Success: {original_status_counts['success']}")
    print(f"- Failure: {original_status_counts['failure']}")
    print(f"- Skipped: {original_status_counts['skipped']}")
    print(f"- Pending: {original_status_counts['pending']}")
    print(f"- In Progress: {original_status_counts['in_progress']}")
    print(f"- Queued: {original_status_counts['queued']}")
    print(f"- Total: {original_status_counts['total']}")
    print()
    
    print("Updated Logic (After Fix):")
    print(f"- Success: {updated_status_counts['success']}")
    print(f"- Failure: {updated_status_counts['failure']} (including {updated_status_counts['hidden_failure']} hidden failures)")
    print(f"- Skipped: {updated_status_counts['skipped']}")
    print(f"- Pending: {updated_status_counts['pending']}")
    print(f"- In Progress: {updated_status_counts['in_progress']}")
    print(f"- Queued: {updated_status_counts['queued']}")
    print(f"- Total: {updated_status_counts['total']}")
    print()
    
    if hidden_failures:
        print(f"Found {len(hidden_failures)} Hidden Failures:")
        print("-----------------")
        for i, job in enumerate(hidden_failures, 1):
            print(f"Hidden Failure #{i}:")
            print(f"- Job ID: {job.get('id')}")
            print(f"- URL: {job.get('htmlUrl', 'N/A')}")
            print(f"- Status: {job.get('status')} / Conclusion: {job.get('conclusion')}")
            print("- Failure Lines:")
            for line in job.get("failureLines", []):
                print(f"  * {line}")
            print()
    else:
        print("No hidden failures found in the data")
        
    return original_status_counts, updated_status_counts, hidden_failures


def main():
    # Path to the sample data file
    sample_file_path = "test/fixtures/hud_data_response_sample_per_page_50.json"
    
    try:
        with open(sample_file_path, 'r') as f:
            data = json.load(f)
            print(f"Successfully loaded data from {sample_file_path}")
            print(f"Data contains {len(data.get('shaGrid', []))} shaGrid entries")
            
            # Analyze job statuses
            original_counts, updated_counts, hidden_failures = analyze_job_statuses(data)
            
            # Print analysis summary
            if hidden_failures:
                print("SUMMARY: We found hidden failures in the real data!")
                print(f"Our fix correctly identified {len(hidden_failures)} jobs that were marked as success but contained failure lines.")
            else:
                print("SUMMARY: No hidden failures found in the real data.")
                print("The sample data doesn't have any jobs marked as success that contain failure lines.")
                print("This means there's no discrepancy between the original and updated logic for this particular dataset.")
            
    except Exception as e:
        print(f"Error loading or processing data: {e}")


if __name__ == "__main__":
    main()