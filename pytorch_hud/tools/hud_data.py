"""
PyTorch HUD data tools for MCP
"""

import re
from typing import Dict, Any, Optional, List, cast
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

async def get_hud_data(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                per_page: int = 3, merge_lf: bool = True, page: int = 1,
                ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get HUD data for a specific commit or branch.

    ⚠️ IMPORTANT: For most use cases, consider using the more specialized endpoints ⚠️
    This endpoint returns all data which can be overwhelming. For better performance,
    use one of these more targeted functions instead:
    - get_commit_summary: Just basic commit info
    - get_job_summary: High-level job status counts
    - get_filtered_jobs: Jobs with filtering options
    - get_failure_details: Only the failing jobs with details

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns recent commits on that branch
            - When passing a full commit SHA, returns data starting from that specific commit
              (the requested commit will be the first in the result list)
        per_page: Number of items per page (default: 3, reduced to prevent overwhelming context)
        merge_lf: Whether to merge LandingFlow data
        page: Page number for pagination
        ctx: MCP context

    Note:
        By default, this returns a small subset of data to prevent overwhelming responses.
        Use per_page to control how many items are returned per page.
        
    Important:
        The API doesn't accept "HEAD" as a special value. To get the latest commit,
        use a branch name like "main" instead.
        
    See Also:
        For detailed documentation about the response format and structure, see:
        /docs/hud_data_structure.md
    """
    if ctx:
        await ctx.info(f"Fetching HUD data for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")
        await ctx.info(f"Pagination: page={page}, per_page={per_page}")

    # Get the data
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha,
                              per_page=per_page, merge_lf=merge_lf, page=page)

    # Add pagination information to the response
    hud_data["_pagination"] = {
        "per_page": per_page,
        "page": page,
        "total_items": len(hud_data.get("shaGrid", [])),
    }

    return hud_data

async def get_commit_summary(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                      ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get just the commit metadata without jobs.

    This lightweight endpoint returns only basic information about the commit
    without including any job data, making it ideal for getting an overview
    without overwhelming the context window.

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
        ctx: MCP context

    Returns:
        Dictionary with commit metadata (author, sha, title, PR info, etc.)
    """
    if ctx:
        await ctx.info(f"Fetching commit summary for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")

    # Get minimal data with just one item
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha, per_page=1)

    # Extract only the commit info, removing the jobs data
    result = {}
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0:
        commit_info = hud_data["shaGrid"][0].copy()
        if "jobs" in commit_info:
            del commit_info["jobs"]
        result = commit_info

    return result

async def get_job_summary(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                   ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get aggregated job status summary.

    Returns counts of jobs by status (success, failure, etc.) without including
    the full job details, making it ideal for getting a quick overview of build health.

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
        ctx: MCP context

    Returns:
        Dictionary with job counts by status, workflow names, etc.
    """
    if ctx:
        await ctx.info(f"Fetching job summary for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")

    # Fetch data with a large per_page to ensure we get all jobs in a single request
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha, per_page=1)

    # Initialize counters
    status_counts = {
        "success": 0,
        "failure": 0,
        "pending": 0,
        "skipped": 0,
        "queued": 0,
        "in_progress": 0,
        "total": 0
    }

    workflow_counts: Dict[str, int] = {}

    # Process job data if available
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0 and "jobs" in hud_data["shaGrid"][0]:
        jobs = hud_data["shaGrid"][0]["jobs"]

        for job in jobs:
            status = job.get("status", "unknown")
            conclusion = job.get("conclusion", "unknown")

            # Update status counts
            status_counts["total"] += 1

            # Only use job conclusion for determining status, not failure lines
            if conclusion == "success":
                status_counts["success"] += 1
            elif conclusion == "failure":
                status_counts["failure"] += 1
            elif conclusion == "skipped":
                status_counts["skipped"] += 1
            elif status == "queued":
                status_counts["queued"] += 1
            elif status == "in_progress":
                status_counts["in_progress"] += 1
            elif conclusion == "pending":
                status_counts["pending"] += 1

            # Extract workflow name from URL if available
            html_url = job.get("htmlUrl", "")
            if html_url:
                parts = html_url.split("/")
                if len(parts) > 4:
                    workflow_name = parts[-3]  # Extract workflow name from URL
                    workflow_counts[workflow_name] = workflow_counts.get(workflow_name, 0) + 1

    # Prepare and return the summary
    commit_info = {}
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0:
        commit_info = {
            "sha": hud_data["shaGrid"][0].get("sha", ""),
            "title": hud_data["shaGrid"][0].get("commitTitle", ""),
            "author": hud_data["shaGrid"][0].get("author", ""),
            "prNum": hud_data["shaGrid"][0].get("prNum", None)
        }

    return {
        "commit": commit_info,
        "status_counts": status_counts,
        "workflow_counts": workflow_counts
    }

async def get_filtered_jobs(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                     status: Optional[str] = None, workflow: Optional[str] = None, job_name_pattern: Optional[str] = None,
                     page: int = 1, per_page: int = 20, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get jobs with filtering options.

    Returns a filtered list of jobs based on status, workflow name, or job name pattern.
    This helps reduce context window usage by returning only the jobs you're interested in.

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
        status: Filter by job status/conclusion (e.g., 'success', 'failure', 'pending', 'skipped')
        workflow: Filter by workflow name (e.g., 'linux-build')
        job_name_pattern: Filter by job name pattern (e.g., 'test', 'build')
        page: Page number for pagination
        per_page: Number of items per page
        ctx: MCP context

    Returns:
        Dictionary with filtered job list and pagination info
    """
    if ctx:
        await ctx.info(f"Fetching filtered jobs for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")
        if status:
            await ctx.info(f"Filtering by status: {status}")
        if workflow:
            await ctx.info(f"Filtering by workflow: {workflow}")
        if job_name_pattern:
            await ctx.info(f"Filtering by job name pattern: {job_name_pattern}")

    # Fetch data with a relatively large per_page to support filtering
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha, per_page=1)

    # Get enriched jobs
    enriched_jobs = enrich_hud_data(hud_data)
    filtered_jobs = []
    total_jobs = 0

    # Apply filters
    for job in enriched_jobs:
        include_job = True

                # Filter by status/conclusion
        if status:
            # Special case for "failure" filter - only include jobs with failure conclusion
            if status == "failure":
                # Only count as failure if conclusion is explicitly "failure"
                has_explicit_failure = job.get("conclusion") == "failure"

                if not has_explicit_failure:
                    include_job = False
            # Normal status matching for other statuses
            elif job.get("conclusion") != status and job.get("status") != status:
                include_job = False

        # Filter by workflow
        if workflow and include_job:
            html_url = job.get("htmlUrl", "")
            if html_url:
                if workflow.lower() not in html_url.lower():
                    include_job = False
            else:
                # If the job doesn't have an HTML URL, we can't match the workflow
                include_job = False

        # Filter by job name pattern - now we can use the enriched job name
        if job_name_pattern and include_job:
            job_name = job.get("name", "")
            if job_name:
                if not re.search(job_name_pattern, job_name, re.IGNORECASE):
                    include_job = False
            else:
                # Fallback to URL-based extraction if name is still not available
                html_url = job.get("htmlUrl", "")
                if html_url:
                    parts = html_url.split("/")
                    if len(parts) > 4:
                        job_name = parts[-1]  # Extract job name from URL
                        if not re.search(job_name_pattern, job_name, re.IGNORECASE):
                            include_job = False
                else:
                    # If the job doesn't have a name or HTML URL, we can't match the pattern
                    include_job = False

        if include_job:
            filtered_jobs.append(job)

    total_jobs = len(filtered_jobs)

    # Apply pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    filtered_jobs = filtered_jobs[start_idx:end_idx]

    # Prepare basic commit info
    commit_info = {}
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0:
        commit_info = {
            "sha": hud_data["shaGrid"][0].get("sha", ""),
            "title": hud_data["shaGrid"][0].get("commitTitle", ""),
            "author": hud_data["shaGrid"][0].get("author", "")
        }

    # Calculate total pages safely
    total_pages = 0
    if per_page > 0:
        total_pages = (total_jobs + per_page - 1) // per_page
        
    # Return filtered jobs with pagination info
    return {
        "commit": commit_info,
        "jobs": filtered_jobs,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_jobs,
            "total_pages": total_pages
        },
        "filters": {
            "status": status,
            "workflow": workflow,
            "job_name_pattern": job_name_pattern
        }
    }

async def get_failure_details(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                       page: int = 1, per_page: int = 10, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get only the failing jobs with detailed failure information.

    This specialized endpoint returns only jobs that have failed, along with their
    failure details (error messages, stack traces, etc.), making it ideal for debugging.

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
        page: Page number for pagination
        per_page: Number of items per page
        ctx: MCP context

    Returns:
        Dictionary with failed jobs and their failure details, or status information
        when jobs are still pending/in progress
    """
    if ctx:
        await ctx.info(f"Fetching failure details for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")

    # Fetch data
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha, per_page=1)

    # Get enriched jobs
    enriched_jobs = enrich_hud_data(hud_data)
    failed_jobs = []
    total_failures = 0

    # Process job data if available
    job_status_counts = {
        "total": 0,
        "success": 0,
        "failure": 0,
        "pending": 0,
        "in_progress": 0,
        "queued": 0,
        "skipped": 0
    }

    # Update total count if we have jobs
    job_status_counts["total"] = len(enriched_jobs)

    # Count jobs by status for reporting
    for job in enriched_jobs:
        status = job.get("status", "unknown")
        conclusion = job.get("conclusion", "unknown")

        # Only use job conclusion for determining status
        if conclusion == "success":
            job_status_counts["success"] += 1
        elif conclusion == "failure":
            job_status_counts["failure"] += 1
            # Extract only the necessary information
            failed_job = {
                "id": job.get("id"),
                "name": job.get("name", ""),  # Include enriched name
                "htmlUrl": job.get("htmlUrl", ""),
                "logUrl": job.get("logUrl", ""),
                "durationS": job.get("durationS", 0),
                "failureLines": job.get("failureLines", []),
                "failureCaptures": job.get("failureCaptures", []),
                "failureLineNumbers": job.get("failureLineNumbers", [])
            }
            failed_jobs.append(failed_job)
        elif conclusion == "skipped":
            job_status_counts["skipped"] += 1
        elif status == "queued":
            job_status_counts["queued"] += 1
        elif status == "in_progress":
            job_status_counts["in_progress"] += 1
        elif conclusion == "pending" or status == "pending":
            job_status_counts["pending"] += 1

    total_failures = len(failed_jobs)

    # Apply pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    failed_jobs = failed_jobs[start_idx:end_idx]

    # Extract basic commit info
    commit_info = {}
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0:
        commit_info = {
            "sha": hud_data["shaGrid"][0].get("sha", ""),
            "title": hud_data["shaGrid"][0].get("commitTitle", ""),
            "author": hud_data["shaGrid"][0].get("author", "")
        }

    # Calculate overall build status
    build_status = "unknown"
    if job_status_counts["failure"] > 0:
        build_status = "failing"
    elif job_status_counts["pending"] > 0 or job_status_counts["in_progress"] > 0 or job_status_counts["queued"] > 0:
        build_status = "pending"
    elif job_status_counts["success"] > 0:
        build_status = "passing"

    # Calculate total pages safely
    total_pages = 0
    if per_page > 0:
        total_pages = (total_failures + per_page - 1) // per_page
        
    # Return failure details with pagination info and job status summary
    return {
        "commit": commit_info,
        "build_status": build_status,
        "job_status_counts": job_status_counts,
        "failed_jobs": failed_jobs,
        "total_failures": total_failures,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_failures,
            "total_pages": total_pages
        }
    }

async def get_job_details(job_id: int, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get detailed information for a specific job.

    This endpoint returns comprehensive details about a single job, including:
    - Basic job metadata (status, duration, URLs)
    - Failure information if the job failed
    - Links to artifacts
    - Utilization metadata

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

    # Try to get utilization metadata
    try:
        utilization = api.get_utilization_metadata(job_id_str)
        result["utilization"] = utilization
    except Exception as e:
        if ctx:
            await ctx.warning(f"Failed to get utilization metadata for job {job_id}: {e}")
        result["utilization"] = None

    return result

async def get_workflow_summary(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                        ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get summary of workflow statuses.

    Returns aggregated information about workflows, including success rates,
    average durations, and status counts per workflow.

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
        ctx: MCP context

    Returns:
        Dictionary with workflow summaries
    """
    if ctx:
        await ctx.info(f"Fetching workflow summary for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")

    # Fetch data
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha, per_page=1)

    # Get enriched jobs
    enriched_jobs = enrich_hud_data(hud_data)
    workflows = {}

    for job in enriched_jobs:
        html_url = job.get("htmlUrl", "")
        if html_url:
            # Extract workflow name from URL
            parts = html_url.split("/")
            if len(parts) > 4:
                workflow_id = parts[-3]  # Extract workflow ID from URL

                # Initialize workflow data if not exists
                if workflow_id not in workflows:
                    workflows[workflow_id] = {
                        "name": workflow_id,
                        "total_jobs": 0,
                        "success": 0,
                        "failure": 0,
                        "skipped": 0,
                        "pending": 0,
                        "in_progress": 0,
                        "total_duration": 0,
                        "jobs": []
                    }

                # Update workflow stats
                workflow = workflows[workflow_id]
                workflow["total_jobs"] += 1

                status = job.get("status", "unknown")
                conclusion = job.get("conclusion", "unknown")

                # Only use conclusion for determining status
                if conclusion == "success":
                    workflow["success"] += 1
                elif conclusion == "failure":
                    workflow["failure"] += 1
                elif conclusion == "skipped":
                    workflow["skipped"] += 1
                elif status == "in_progress":
                    workflow["in_progress"] += 1
                elif conclusion == "pending":
                    workflow["pending"] += 1

                # Add duration if available
                duration = job.get("durationS", 0)
                if duration and duration > 0:
                    workflow["total_duration"] += duration

                # Add job summary to the workflow with job name
                workflow["jobs"].append({
                    "id": job.get("id"),
                    "name": job.get("name", ""),  # Include enriched name
                    "conclusion": conclusion,
                    "status": status,
                    "duration": duration
                })

    # Calculate average durations and success rates
    for workflow_id, workflow in workflows.items():
        completed_jobs = workflow["success"] + workflow["failure"]
        if completed_jobs > 0:
            workflow["avg_duration"] = workflow["total_duration"] / completed_jobs
            workflow["success_rate"] = workflow["success"] / completed_jobs * 100
        else:
            workflow["avg_duration"] = 0
            workflow["success_rate"] = 0

    # Extract basic commit info
    commit_info = {}
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0:
        commit_info = {
            "sha": hud_data["shaGrid"][0].get("sha", ""),
            "title": hud_data["shaGrid"][0].get("commitTitle", ""),
            "author": hud_data["shaGrid"][0].get("author", "")
        }

    return {
        "commit": commit_info,
        "workflows": list(workflows.values()),
        "total_workflows": len(workflows)
    }

async def get_test_summary(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                    ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get summary of test results.

    Returns aggregated information about test results, including pass/fail/skip counts
    and lists of failed tests.

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
        ctx: MCP context

    Returns:
        Dictionary with test result summaries
    """
    if ctx:
        await ctx.info(f"Fetching test summary for {repo_owner}/{repo_name} with branch_or_commit_sha={branch_or_commit_sha}")

    # Fetch data
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha, per_page=1)

    # Initialize test summary with proper typing
    test_summary: Dict[str, Any] = {
        "failed_tests": [],
        "test_jobs": 0
    }
    
    # Get enriched jobs
    enriched_jobs = enrich_hud_data(hud_data)

    for job in enriched_jobs:
        # Get job name either from enriched field or URL
        job_name = job.get("name", "")
        html_url = job.get("htmlUrl", "")
        
        # Check if this is a test job by name or URL
        is_test_job = False
        if job_name and "test" in job_name.lower():
            is_test_job = True
        elif html_url and "test" in html_url.lower():
            is_test_job = True
            
        if is_test_job:
            test_summary["test_jobs"] = cast(int, test_summary["test_jobs"]) + 1

            # Check for explicit failures only
            is_failure = job.get("conclusion") == "failure"

            if is_failure:
                # Extract any test failure patterns
                failure_lines = job.get("failureLines", [])

                # Look for test failure patterns
                test_failure_pattern = re.compile(r"(FAIL|ERROR)(\s*:)?\s*(test\w+)", re.IGNORECASE)

                for line in failure_lines:
                    match = test_failure_pattern.search(line)
                    if match:
                        test_name = match.group(3)
                        test_failure = {
                            "test_name": test_name,
                            "job_id": job.get("id"),
                            "job_name": job_name,  # Include enriched name
                            "job_url": html_url,
                            "error_line": line
                        }
                        cast(List[Dict[str, Any]], test_summary["failed_tests"]).append(test_failure)

    # Extract basic commit info
    commit_info = {}
    if "shaGrid" in hud_data and len(hud_data["shaGrid"]) > 0:
        commit_info = {
            "sha": hud_data["shaGrid"][0].get("sha", ""),
            "title": hud_data["shaGrid"][0].get("commitTitle", ""),
            "author": hud_data["shaGrid"][0].get("author", "")
        }

    test_summary["commit"] = commit_info
    test_summary["total_failed_tests"] = len(cast(List[Dict[str, Any]], test_summary["failed_tests"]))

    return test_summary

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