"""
PyTorch HUD data tools for MCP
"""

import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from mcp.server.fastmcp import Context

from pytorch_hud.api.client import PyTorchHudAPI

# Initialize API client singleton
api = PyTorchHudAPI()


def enrich_jobs_with_names(jobs: List[Dict[str, Any]], job_names: List[str]) -> List[Dict[str, Any]]:
    """Enrich job objects with their names from the jobNames array.
    
    Args:
        jobs: List of job objects
        job_names: List of job names from the jobNames array
        
    Returns:
        List of job objects with 'name' field added/updated
    """
    enriched_jobs = []
    
    for job in jobs:
        job_id = job.get("id")
        enriched_job = job.copy()
        
        # First try to get job name from jobNames array if ID is available 
        # and is a valid index into job_names
        if job_id is not None and isinstance(job_id, int) and 0 <= job_id < len(job_names):
            enriched_job["name"] = job_names[job_id]
        
        # Fallback: extract from URL if still needed
        elif "name" not in enriched_job and "htmlUrl" in enriched_job:
            html_url = enriched_job.get("htmlUrl", "")
            if html_url:
                parts = html_url.split("/")
                if len(parts) > 4:
                    enriched_job["name"] = parts[-1]  # Extract job name from URL
                    
        enriched_jobs.append(enriched_job)
    
    return enriched_jobs

def enrich_hud_data(hud_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and enrich jobs from HUD data with their names.
    
    This helper function handles the common pattern of extracting jobs from HUD data
    and enriching them with names from the jobNames array.
    
    Args:
        hud_data: The response from get_hud_data
        
    Returns:
        List of jobs enriched with names, or empty list if no jobs found
    """
    job_names = hud_data.get("jobNames", [])
    
    # Process job data if available
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0 and "jobs" in hud_data["shaGrid"][0]:
        jobs = hud_data["shaGrid"][0]["jobs"]
        return enrich_jobs_with_names(jobs, job_names)
    
    return []


async def get_job_details(job_id: int, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get detailed information for a specific job.

    This endpoint returns comprehensive details about a single job, including:
    - Basic job metadata (status, duration, URLs)
    - Failure information if the job failed
    - Links to artifacts

    Args:
        job_id: The ID of the job to fetch
        ctx: MCP context

    Returns:
        Dictionary with detailed job information
    """
    if ctx:
        await ctx.info(f"Fetching detailed information for job {job_id}")

    # Convert job_id to string for API calls
    job_id_str = str(job_id)
    
    result = {
        "job_id": job_id,
        "log_url": api.get_s3_log_url(job_id_str)
    }

    # Try to get artifacts
    try:
        artifacts = api.get_artifacts("s3", job_id_str)
        result["artifacts"] = artifacts
    except Exception as e:
        if ctx:
            await ctx.warning(f"Failed to get artifacts for job {job_id}: {e}")
        result["artifacts"] = None

    return result


async def get_recent_commits_with_jobs(
    repo_owner: str = "pytorch",
    repo_name: str = "pytorch",
    branch_or_commit_sha: str = "main",
    include_success: bool = False,
    include_pending: bool = False,
    include_failures: bool = False,
    include_commit_details: bool = True,
    job_name_filter_regex: Optional[str] = None,
    failure_line_filter_regex: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Get recent commits with optional job details and filtering.
    
    This universal function consolidates various HUD data endpoints, providing
    flexible options to fetch exactly the data needed while avoiding context overload.
    
    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns recent commits on that branch
            - When passing a full commit SHA, returns data starting from that specific commit
        include_success: Whether to include successful jobs in the response (default: False)
        include_pending: Whether to include pending/in-progress jobs in the response (default: False)
        include_failures: Whether to include failing jobs in the response (default: False)
        include_commit_details: Whether to include PR number, diff URL, etc. (default: True)
        job_name_filter_regex: Optional regex pattern to filter jobs by name
        failure_line_filter_regex: Optional regex pattern to filter failure lines
        page: Page number for pagination (default: 1)
        per_page: Number of commits per page (default: 10)
        ctx: MCP context
    
    Returns:
        Dictionary containing:
        - List of recent commits with status counts
        - Job details for each commit based on filter settings
        - Pagination information
    """
    if ctx:
        await ctx.info(f"Fetching recent commits for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")
        await ctx.info(f"Filters: include_success={include_success}, include_pending={include_pending}, include_failures={include_failures}")
        if job_name_filter_regex:
            await ctx.info(f"Job name filter: {job_name_filter_regex}")
        if failure_line_filter_regex:
            await ctx.info(f"Failure line filter: {failure_line_filter_regex}")
    
    # Get the data from API
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha, 
                             per_page=per_page, merge_lf=True, page=page)
    
    # Prepare job filters if needed
    job_name_pattern = None
    failure_line_pattern = None
    if job_name_filter_regex:
        job_name_pattern = re.compile(job_name_filter_regex, re.IGNORECASE)
    if failure_line_filter_regex:
        failure_line_pattern = re.compile(failure_line_filter_regex, re.IGNORECASE)
    
    # Compile result commits
    result_commits: List[Dict[str, Any]] = []
    sha_grid = hud_data.get("shaGrid", [])
    job_names = hud_data.get("jobNames", [])
    
    # Process each commit in the grid
    for commit_idx, commit in enumerate(sha_grid):
        # Stop after reaching per_page
        if len(result_commits) >= per_page:
            break
            
        # Extract commit info
        commit_sha = commit.get("sha", "")
        commit_info = {
            "sha": commit_sha,
            "short_sha": commit_sha[:7] if commit_sha else "",
            "title": commit.get("commitTitle", ""),
            "author": commit.get("author", ""),
            "time": commit.get("time", ""),
            "job_counts": {
                "total": 0,
                "success": 0,
                "failure": 0,
                "pending": 0,
                "skipped": 0
            },
            "status": "unknown",
            "hud_url": f"https://hud.pytorch.org/{repo_owner}/{repo_name}/commit/{commit_sha}"
        }
        
        # Include additional commit details if requested
        if include_commit_details:
            for field in ["prNum", "diffNum", "authorUrl", "commitUrl"]:
                if field in commit:
                    commit_info[field] = commit[field]
        
        # Process jobs for this commit
        filtered_jobs = []
        original_jobs = commit.get("jobs", [])
        
        # Get job counts regardless of filtering
        for job in original_jobs:
            # Skip empty job entries (sometimes returned in the API)
            if not job:
                continue
                
            status = job.get("status", "unknown")
            conclusion = job.get("conclusion", "unknown")
            
            # Update total count
            commit_info["job_counts"]["total"] += 1
            
            # Count by status based on conclusion
            if conclusion == "success":
                commit_info["job_counts"]["success"] += 1
            elif conclusion == "failure":
                commit_info["job_counts"]["failure"] += 1
            elif conclusion == "skipped":
                commit_info["job_counts"]["skipped"] += 1
            elif status == "queued" or status == "in_progress" or conclusion == "pending":
                commit_info["job_counts"]["pending"] += 1
        
        # Determine overall commit status
        if commit_info["job_counts"]["failure"] > 0:
            commit_info["status"] = "red"
        elif commit_info["job_counts"]["pending"] > 0:
            commit_info["status"] = "pending"
        elif commit_info["job_counts"]["success"] > 0:
            commit_info["status"] = "green"
            
        # Filter and enrich jobs based on criteria
        if include_success or include_pending or include_failures:
            # Pre-enrich all jobs with names
            all_jobs = enrich_jobs_with_names(original_jobs, job_names)
            
            # Apply filtering to jobs
            for job in all_jobs:
                include_job = False
                status = job.get("status", "unknown")
                conclusion = job.get("conclusion", "unknown")
                
                # Apply status filters
                if conclusion == "success" and include_success:
                    include_job = True
                elif conclusion == "failure" and include_failures:
                    include_job = True
                elif (status == "queued" or status == "in_progress" or conclusion == "pending") and include_pending:
                    include_job = True
                    
                # Apply job name filter if needed
                if include_job and job_name_pattern:
                    job_name = job.get("name", "")
                    if not job_name_pattern.search(job_name):
                        include_job = False
                        
                # Apply failure line filter if needed
                if include_job and failure_line_pattern and "failureLines" in job:
                    failure_match = False
                    for line in job["failureLines"]:
                        if failure_line_pattern.search(line):
                            failure_match = True
                            break
                    if not failure_match:
                        include_job = False
                
                # Add job if it passed all filters
                if include_job:
                    filtered_jobs.append(job)
            
            # Add filtered jobs to commit info
            if filtered_jobs:
                commit_info["jobs"] = filtered_jobs
                
        # Add commit to results
        result_commits.append(commit_info)
    
    # Prepare result
    result = {
        "repo": f"{repo_owner}/{repo_name}",
        "branch_or_commit_sha": branch_or_commit_sha,
        "commits": result_commits,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_commits": len(sha_grid),  # This is an approximation, API doesn't provide total count
            "returned_commits": len(result_commits)
        },
        "filters": {
            "include_success": include_success,
            "include_pending": include_pending,
            "include_failures": include_failures,
            "job_name_filter_regex": job_name_filter_regex,
            "failure_line_filter_regex": failure_line_filter_regex
        },
        "_metadata": {
            "timestamp": datetime.now().isoformat(),
            "api_request": {
                "page": page,
                "per_page": per_page,
                "merge_lf": True
            }
        }
    }
    
    return result