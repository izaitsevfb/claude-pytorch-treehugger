"""
PyTorch HUD MCP server implementation

This module implements the MCP server for interfacing with PyTorch HUD API.
The server provides access to various CI/CD analytics and tools for debugging
CI issues, analyzing logs, and querying data from ClickHouse.
"""

import json
from typing import Optional, Any, Dict
from mcp.server.fastmcp import FastMCP, Context

from pytorch_hud.api.client import PyTorchHudAPI
from pytorch_hud.api.utils import parse_time_range
from pytorch_hud.tools.hud_data import (
    get_commit_summary, get_job_summary, get_filtered_jobs,
    get_failure_details, get_job_details, get_workflow_summary, get_test_summary
)
from pytorch_hud.log_analysis.tools import (
    get_artifacts, get_s3_log_url, get_utilization_metadata, search_logs,
    download_log_to_file, extract_log_patterns, extract_test_results, filter_log_sections
)
from pytorch_hud.clickhouse.queries import (
    query_clickhouse, get_master_commit_red, get_queued_jobs, get_disabled_test_historical,
    get_unique_repos_in_runnercost, get_job_duration_avg, get_workflow_duration_avg,
    get_flaky_tests, get_queue_times_historical, get_job_annotation
)

# Create an MCP server
mcp = FastMCP("PyTorch HUD")

# Initialize API client
api = PyTorchHudAPI()

# Maximum response size in bytes - set to a conservative size for context window efficiency
MAX_RESPONSE_SIZE = 10 * 1024  # 10KB

def safe_json_dumps(data: Any, indent: int = 2, max_size: int = MAX_RESPONSE_SIZE) -> str:
    """Safely serialize data to JSON with strict size limit.

    Args:
        data: The data to serialize
        indent: Indentation level for pretty printing
        max_size: Maximum response size in bytes

    Returns:
        JSON string, truncated if needed with a warning message
    """
    # Always use indentation for readability
    json_str = json.dumps(data, indent=indent)

    # Return as-is if under the size limit
    if len(json_str) <= max_size:
        return json_str

    # Hard truncate with a clear error message
    warning_msg = (
        "\n\n<ERROR: RESPONSE TRUNCATED>\n"
        "The response exceeds the maximum size limit. Please use more specific parameters:\n"
        "- Reduce 'per_page' value (try 3-5 instead)\n"
        "- Use the 'fields' parameter to request only needed data\n"
        "- For failure details, use 'include_lines=summary' or 'include_lines=none'\n"
        "- Consider using specialized endpoints like get_commit_summary or get_job_summary"
    )

    # Calculate safe truncation size
    trunc_size = max_size - len(warning_msg)
    if trunc_size < 200:  # Ensure we have some minimal content
        trunc_size = 200

    # Return truncated JSON with error message
    return json_str[:trunc_size] + warning_msg

#==============================================================================
# MCP Resources
#==============================================================================

@mcp.tool()
def get_clickhouse_queries_resource() -> str:
    """List all available ClickHouse queries."""
    queries = api.get_clickhouse_queries()
    return safe_json_dumps(queries, indent=2)

@mcp.tool()
def get_clickhouse_query_params_resource(query_name: str) -> str:
    """Get the parameters for a specific ClickHouse query."""
    params = api.get_clickhouse_query_parameters(query_name)
    return safe_json_dumps(params, indent=2)

@mcp.tool()
def get_hud_data_resource(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                         per_page: int = 3,
                         merge_lf: Optional[bool] = None,
                         page: int = 1,
                         fields: Optional[str] = None) -> str:
    """Get HUD data for a specific commit or branch.

    IMPORTANT: This is the primary entry point for investigating trunk health issues!
    Always start any CI/CD investigation with this resource to get an overview of workflows and jobs.

    Returns information about workflows and jobs for a commit, including their status,
    runtime, and failure details. This is essential for:
    1. Identifying specific failing jobs
    2. Understanding patterns of failures
    3. Getting job IDs for further log analysis

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns recent commits on that branch
            - When passing a full commit SHA, returns data starting from that specific commit
              (the requested commit will be the first in the result list)

    Query parameters:
        per_page: Number of items per page (default: 3)
          - CAUTION: Setting this too high (>10) can result in large responses
          - For detailed analysis, consider using specialized endpoints instead

        merge_lf: Whether to merge LandingFlow data (default: True)
          - Set to False to keep LandingFlow jobs separate

        page: Page number (default: 1)
          - Use for paginating through multiple pages of data

        fields: Comma-separated list of fields to include in response
          - Available fields: 'commit_info', 'jobs', 'job_names'
          - Default: all fields
          - Example: 'fields=commit_info,jobs' to exclude job_names

    Returns:
        HUD data for the specified commit in JSON format

    Recommendation:
        For better context management, consider using these specialized endpoints:
        - get_commit_summary: Just basic commit info
        - get_job_summary: High-level job status counts
        - get_filtered_jobs: Jobs with filtering options
        - get_failure_details: Only the failing jobs with details

    Note:
        The API doesn't accept "HEAD" as a special value. To get the latest commit,
        use a branch name like "main" instead.
    """
    # Use merge_lf parameter directly, or default to True if None
    merge_lf_bool = merge_lf if merge_lf is not None else True

    # Parse fields parameter to determine what to include in response
    included_fields = ['commit_info', 'jobs', 'job_names']
    if fields is not None:
        field_list = [f.strip() for f in fields.split(',')]
        if field_list:
            included_fields = field_list

    # Use integer parameters directly - no conversion needed
    page_int = page
    per_page_int = per_page

    # Get the data
    hud_data = api.get_hud_data(repo_owner, repo_name, branch_or_commit_sha,
                               per_page=per_page_int, merge_lf=merge_lf_bool, page=page_int)

    # Add pagination information to the response
    hud_data["_pagination"] = {
        "per_page": per_page_int,
        "page": page_int,
        "total_items": len(hud_data.get("shaGrid", [])),
    }

    # Filter response based on requested fields
    filtered_data = {}

    if 'job_names' in included_fields and 'jobNames' in hud_data:
        filtered_data['jobNames'] = hud_data['jobNames']

    if 'shaGrid' in hud_data:
        filtered_data['shaGrid'] = []
        for commit in hud_data['shaGrid']:
            commit_data = {}

            # Always include SHA as it's a key identifier
            commit_data['sha'] = commit.get('sha', '')

            if 'commit_info' in included_fields:
                # Include basic commit information
                for field in ['time', 'prNum', 'diffNum', 'commitUrl',
                             'commitTitle', 'author', 'authorUrl']:
                    if field in commit:
                        commit_data[field] = commit[field]

            if 'jobs' in included_fields and 'jobs' in commit:
                commit_data['jobs'] = commit['jobs']

            filtered_data['shaGrid'].append(commit_data)

    # Add pagination to filtered data
    filtered_data["_pagination"] = hud_data["_pagination"]

    # Add a size hint to help users understand potential size issues
    size_hint = {
        "per_page": per_page_int,
        "job_count": len(hud_data.get("shaGrid", [])),
        "recommended_limit": 5 if 'jobs' in included_fields else 10
    }
    filtered_data["_size_hint"] = size_hint

    return safe_json_dumps(filtered_data, indent=2)

@mcp.tool()
async def get_queued_jobs_resource(ctx: Optional[Context] = None) -> str:
    """Get queued jobs data.

    Returns information about currently queued jobs in the CI system.
    """
    if ctx:
        await ctx.info("Fetching queued jobs data")
    # Access the get_queued_jobs from the imported module, not from the api instance
    queued_jobs = get_queued_jobs()
    return safe_json_dumps(queued_jobs, indent=2)

@mcp.tool()
def get_issue_data_resource(issue_name: str) -> str:
    """Get data for a specific issue."""
    issue_data = api.get_issue_data(issue_name)
    return safe_json_dumps(issue_data, indent=2)

@mcp.tool()
def get_commit_data_resource(repo_owner: str, repo_name: str, commit_sha: str) -> str:
    """Get data for a specific commit."""
    commit_data = api.get_commit_data(repo_owner, repo_name, commit_sha)
    return safe_json_dumps(commit_data, indent=2)

@mcp.tool()
async def get_commit_summary_resource(repo_owner: str, repo_name: str, branch_or_commit_sha: str, ctx: Optional[Context] = None) -> str:
    """Get just the commit metadata without jobs.

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
    """
    commit_summary = await get_commit_summary(repo_owner, repo_name, branch_or_commit_sha, ctx=ctx)
    return safe_json_dumps(commit_summary, indent=2)

@mcp.tool()
async def get_job_summary_resource(repo_owner: str, repo_name: str, branch_or_commit_sha: str, ctx: Optional[Context] = None) -> str:
    """Get aggregated job status summary.

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
    """
    job_summary = await get_job_summary(repo_owner, repo_name, branch_or_commit_sha, ctx=ctx)
    return safe_json_dumps(job_summary, indent=2)


@mcp.tool()
async def get_filtered_jobs_resource(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                                     status: Optional[str] = None,
                                     workflow: Optional[str] = None,
                                     job_name_pattern: Optional[str] = None,
                                     page: int = 1,
                                     per_page: int = 20,
                                     fields: Optional[str] = None,
                                     ctx: Optional[Context] = None
                                     ) -> str:
    """Get jobs with filtering options.

    Returns a filtered list of jobs based on status, workflow name, or job name pattern.
    This helps reduce context window usage by returning only the jobs you're interested in.

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit

    Query parameters:
        status: Filter by job status/conclusion (e.g., 'success', 'failure', 'pending', 'skipped')
          - Returns only jobs matching this status

        workflow: Filter by workflow name (e.g., 'linux-build')
          - Substring matching, can be partial name

        job_name_pattern: Filter by job name pattern (e.g., 'test', 'build')
          - Supports regex pattern matching on job names

        page: Page number for pagination (default: 1)

        per_page: Number of items per page (default: 20)
          - Recommended range: 5-20 to avoid context overload

        fields: Comma-separated list of fields to include (default: all)
          - Available: 'commit', 'jobs', 'pagination', 'filters'
          - Omit fields to reduce response size

    Returns:
        JSON with filtered job list and pagination info
    """
    # Parse fields parameter
    all_fields = ['commit', 'jobs', 'pagination', 'filters']
    included_fields = all_fields
    if fields is not None:
        field_list = [f.strip() for f in fields.split(',')]
        if field_list:
            included_fields = field_list

    # Use integer parameters directly - no conversion needed
    filtered_jobs = await get_filtered_jobs(
        repo_owner, repo_name, branch_or_commit_sha,
        status=status, workflow=workflow, job_name_pattern=job_name_pattern,
        page=page, per_page=per_page, ctx=ctx
    )

    # Filter response based on requested fields
    result = {}
    for field in included_fields:
        if field == 'commit' and 'commit' in filtered_jobs:
            result['commit'] = filtered_jobs['commit']
        elif field == 'jobs' and 'jobs' in filtered_jobs:
            result['jobs'] = filtered_jobs['jobs']
        elif field == 'pagination' and 'pagination' in filtered_jobs:
            result['pagination'] = filtered_jobs['pagination']
        elif field == 'filters' and 'filters' in filtered_jobs:
            result['filters'] = filtered_jobs['filters']

    # Add size hints
    if 'jobs' in result:
        result['_size_hint'] = {
            "job_count": len(result.get("jobs", [])),
            "per_page": per_page,
            "recommended_max": 15
        }

    return safe_json_dumps(result, indent=2)

@mcp.tool()
async def get_failure_details_resource(repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                                     page: int = 1,
                                     per_page: int = 10,
                                     fields: Optional[str] = None,
                                     include_lines: Optional[str] = None,
                                     ctx: Optional[Context] = None) -> str:
    """Get only the failing jobs with detailed failure information.

    This specialized endpoint returns only jobs that have failed, along with their
    failure details (error messages, stack traces, etc.), making it ideal for debugging.

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit

    Query parameters:
        page: Page number for pagination (default: 1)

        per_page: Number of items per page (default: 10)
          - Recommended range: 5-15 for most use cases

        fields: Comma-separated list of fields to include (default: all)
          - Available: 'commit', 'failed_jobs', 'total_failures', 'pagination'
          - Example: fields=failed_jobs,total_failures

        include_lines: Control which failure lines to include (default: 'all')
          - 'all': Include all failure information
          - 'summary': Include only the first failure line for each job
          - 'none': Exclude failure lines completely

    Returns:
        JSON with failed jobs and their failure details
    """
    # Parse fields parameter
    all_fields = ['commit', 'failed_jobs', 'total_failures', 'pagination']
    included_fields = all_fields
    if fields is not None:
        field_list = [f.strip() for f in fields.split(',')]
        if field_list:
            included_fields = field_list

    # Use integer parameters directly - no conversion needed
    failure_details = await get_failure_details(
        repo_owner, repo_name, branch_or_commit_sha,
        page=page, per_page=per_page,
        ctx=ctx
    )

    # Filter response based on requested fields
    result = {}
    for field in included_fields:
        if field == 'commit' and 'commit' in failure_details:
            result['commit'] = failure_details['commit']
        elif field == 'failed_jobs' and 'failed_jobs' in failure_details:
            # Handle failure lines filtering based on include_lines parameter
            if include_lines == 'none':
                # Remove all failure lines
                result['failed_jobs'] = [
                    {k: v for k, v in job.items()
                     if k not in ('failureLines', 'failureCaptures', 'failureLineNumbers')}
                    for job in failure_details['failed_jobs']
                ]
            elif include_lines == 'summary':
                # Include only the first failure line
                result['failed_jobs'] = []
                for job in failure_details['failed_jobs']:
                    filtered_job = {k: v for k, v in job.items()
                                  if k not in ('failureLines', 'failureCaptures', 'failureLineNumbers')}

                    # Add just the first line of each failure type if available
                    if 'failureLines' in job and job['failureLines']:
                        filtered_job['failureLines'] = [job['failureLines'][0]]

                    if 'failureCaptures' in job and job['failureCaptures']:
                        filtered_job['failureCaptures'] = [job['failureCaptures'][0]]

                    if 'failureLineNumbers' in job and job['failureLineNumbers']:
                        filtered_job['failureLineNumbers'] = [job['failureLineNumbers'][0]]

                    result['failed_jobs'].append(filtered_job)
            else:
                # Include all failure lines (default)
                result['failed_jobs'] = failure_details['failed_jobs']
        elif field == 'total_failures' and 'total_failures' in failure_details:
            result['total_failures'] = failure_details['total_failures']
        elif field == 'pagination' and 'pagination' in failure_details:
            result['pagination'] = failure_details['pagination']

    # Add size hints
    if 'failed_jobs' in result:
        include_mode = "all" if include_lines is None else include_lines
        result['_size_hint'] = {
            "failure_count": len(result.get("failed_jobs", [])),
            "per_page": per_page,
            "include_lines": include_mode,
            "recommended_filters": "For large responses, use include_lines='summary' or include_lines='none'"
        }

    return safe_json_dumps(result, indent=2)

@mcp.tool()
async def get_job_details_resource(job_id: int, ctx: Optional[Context] = None) -> str:
    """Get detailed information for a specific job."""
    job_details = await get_job_details(job_id, ctx=ctx)
    return safe_json_dumps(job_details, indent=2)

@mcp.tool()
async def get_workflow_summary_resource(repo_owner: str, repo_name: str, branch_or_commit_sha: str, ctx: Optional[Context] = None) -> str:
    """Get summary of workflow statuses.

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
    """
    workflow_summary = await get_workflow_summary(repo_owner, repo_name, branch_or_commit_sha, ctx=ctx)
    return safe_json_dumps(workflow_summary, indent=2)

@mcp.tool()
async def get_test_summary_resource(repo_owner: str, repo_name: str, branch_or_commit_sha: str, ctx: Optional[Context] = None) -> str:
    """Get summary of test results.

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
            - When passing a branch name like 'main', returns data for the latest commit on that branch
            - When passing a full commit SHA, returns data for that specific commit
    """
    test_summary = await get_test_summary(repo_owner, repo_name, branch_or_commit_sha, ctx=ctx)
    return safe_json_dumps(test_summary, indent=2)

#==============================================================================
# MCP Registration Guidelines
#==============================================================================
#
# Only the resource endpoints should be registered with MCP. The underlying API functions
# are called by these resource endpoints and should not be registered separately.
#
# FastMCP fully supports both synchronous and asynchronous functions when registered
# as MCP tools.
#
# There are two main approaches to registering functions:
#
# 1. Using the @mcp.tool() decorator directly on the function:
#
#    @mcp.tool()
#    async def some_resource_endpoint(...) -> str:
#        """Resource documentation"""
#        # Implementation
#        return safe_json_dumps(result)
#
# 2. Using the function registration style (less common, same effect):
#
#    async def some_resource_endpoint(...) -> str:
#        """Resource documentation"""
#        # Implementation
#        return safe_json_dumps(result)
#
#    mcp.tool()(some_resource_endpoint)
#
# Only the resource endpoints are registered below. The implementation functions
# they call (get_hud_data, get_job_details, etc.) are not registered separately.
#
# Resource endpoints for log analysis tools

@mcp.tool()
async def download_log_to_file_resource(job_id: int, ctx: Optional[Context] = None) -> str:
    """Download a job log to a temporary file for analysis."""
    log_info = await download_log_to_file(job_id, ctx=ctx)
    return safe_json_dumps(log_info, indent=2)

@mcp.tool()
async def extract_log_patterns_resource(file_path: str, patterns: Optional[Dict[Any, Any]] = None, ctx: Optional[Context] = None) -> str:
    """Extract matches for specified patterns from a log file."""
    pattern_results = await extract_log_patterns(file_path, patterns, ctx=ctx)
    return safe_json_dumps(pattern_results, indent=2)

@mcp.tool()
async def extract_test_results_resource(file_path: str, ctx: Optional[Context] = None) -> str:
    """Extract test results specifically from a log file."""
    test_results = await extract_test_results(file_path, ctx=ctx)
    return safe_json_dumps(test_results, indent=2)

@mcp.tool()
async def filter_log_sections_resource(file_path: str,
                                      start_pattern: Optional[str] = None,
                                      end_pattern: Optional[str] = None,
                                      max_lines: int = 100,
                                      ctx: Optional[Context] = None) -> str:
    """Extract specific sections from a log file based on start/end patterns.
    
    Args:
        file_path: Path to the log file
        start_pattern: Pattern that marks the start of a section
        end_pattern: Pattern that marks the end of a section
        max_lines: Maximum number of lines to return per section (default: 100)
        ctx: MCP context
    """
    # Use integer parameter directly - no conversion needed
    sections = await filter_log_sections(file_path, start_pattern, end_pattern, max_lines, ctx=ctx)
    return safe_json_dumps(sections, indent=2)

@mcp.tool()
def search_logs_resource(query: str, repo: Optional[str] = None, workflow: Optional[str] = None) -> str:
    """Search job logs for a specific pattern."""
    search_result = search_logs(query, repo=repo, workflow=workflow)
    return safe_json_dumps(search_result, indent=2)

@mcp.tool()
def get_artifacts_resource(provider: str, job_id: int) -> str:
    """Get artifacts for a job."""
    # Convert job_id to string for API call
    job_id_str = str(job_id)
    artifacts = get_artifacts(provider, job_id_str)
    return safe_json_dumps(artifacts, indent=2)

@mcp.tool()
def get_s3_log_url_resource(job_id: int) -> str:
    """Get the S3 log URL for a job."""
    # Convert job_id to string for API call
    job_id_str = str(job_id)
    url = get_s3_log_url(job_id_str)
    return url  # No need to JSON encode, it's a simple string

@mcp.tool()
def get_utilization_metadata_resource(job_id: int) -> str:
    """Get utilization metadata for a job."""
    # Convert job_id to string for API call
    job_id_str = str(job_id)
    metadata = get_utilization_metadata(job_id_str)
    return safe_json_dumps(metadata, indent=2)

# ClickHouse query resource endpoints

@mcp.tool()
def query_clickhouse_resource(query_name: str, parameters: Optional[Dict[Any, Any]] = None) -> str:
    """Run a ClickHouse query by name with parameters."""
    results = query_clickhouse(query_name, parameters or {})
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_master_commit_red_resource(time_range: str = "7d", timezone: str = "America/Los_Angeles", ctx: Optional[Context] = None) -> str:
    """Get historical master commit status aggregated by day for a specified time range."""
    results = await get_master_commit_red(time_range, timezone, ctx=ctx)
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_disabled_test_historical_resource(time_range: str = "7d",
                                          label: str = "skipped",
                                          repo: str = "pytorch/pytorch",
                                          state: str = "open",
                                          platform: str = "",
                                          triaged: str = "",
                                          granularity: str = "day",
                                          ctx: Optional[Context] = None) -> str:
    """Get historical disabled test data."""
    results = await get_disabled_test_historical(
        time_range, label, repo, state, platform, triaged, granularity, ctx=ctx
    )
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_unique_repos_in_runnercost_resource(time_range: str = "7d", ctx: Optional[Context] = None) -> str:
    """Get unique repos in runner cost."""
    results = await get_unique_repos_in_runnercost(time_range, ctx=ctx)
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_job_duration_avg_resource(time_range: str = "7d",
                                  job_name: str = "",
                                  repo: str = "pytorch/pytorch",
                                  granularity: str = "day",
                                  ctx: Optional[Context] = None) -> str:
    """Get average job duration."""
    results = await get_job_duration_avg(time_range, job_name, repo, granularity, ctx=ctx)
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_workflow_duration_avg_resource(time_range: str = "7d",
                                       workflow_name: str = "",
                                       repo: str = "pytorch/pytorch",
                                       granularity: str = "day",
                                       ctx: Optional[Context] = None) -> str:
    """Get average workflow duration."""
    results = await get_workflow_duration_avg(time_range, workflow_name, repo, granularity, ctx=ctx)
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_flaky_tests_resource(time_range: str = "7d", test_name: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    """Get flaky test data."""
    results = await get_flaky_tests(time_range, test_name, ctx=ctx)
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_queue_times_historical_resource(time_range: str = "7d", granularity: str = "hour", ctx: Optional[Context] = None) -> str:
    """Get historical queue times."""
    results = await get_queue_times_historical(time_range, granularity, ctx=ctx)
    return safe_json_dumps(results, indent=2)

@mcp.tool()
async def get_job_annotation_resource(repo_owner: str, repo_name: str, annotation_type: str,
                                branch: str = "main", time_range: str = "1d", ctx: Optional[Context] = None) -> str:
    """Get job annotations."""
    results = await get_job_annotation(repo_owner, repo_name, annotation_type, branch, time_range, ctx=ctx)
    return safe_json_dumps(results, indent=2)

# ClickHouse query implementations are called by respective resource endpoints
# and do not need to be registered separately

#==============================================================================
# MCP Prompts
#==============================================================================

@mcp.prompt()
def debug_workflow_failures(repo_owner: str, repo_name: str, commit_sha: str) -> str:
    """Create a prompt for debugging workflow failures on a commit."""
    return f"""# Debugging Workflow Failures

Please help me analyze and debug workflow failures for the commit {commit_sha} in the repository {repo_owner}/{repo_name}.

## Step 1: Get Basic Overview of Trunk Health

Always start trunk health investigations with these two key functions:

```python
# First check the overall trunk health
trunk_health = await get_master_commit_red("7d") 

# Then use specialized APIs for the specific commit to avoid context overflow
```

## Step 2: Context-Efficient Data Retrieval

For optimal context management, use specialized endpoints rather than the full HUD data:

```python
# Get just the commit metadata first (very small response)
commit_summary = await get_commit_summary("{repo_owner}", "{repo_name}", "main", "{commit_sha}")

# Get job counts by status (success, failure, etc.) - small payload
job_summary = await get_job_summary("{repo_owner}", "{repo_name}", "main", "{commit_sha}")

# If there are failures, focus only on them
failure_details = await get_failure_details(
    "{repo_owner}", "{repo_name}", "main", "{commit_sha}",
    # Use these parameters to control response size:
    per_page=10,
    fields="failed_jobs,total_failures",
    include_lines="summary"  # Only get first error line to conserve context
)
```

Only if you need full details, use the complete HUD data endpoint:
```python
# Start with a small sample
hud_data = await get_hud_data(
    "{repo_owner}", "{repo_name}", "main", "{commit_sha}",
    per_page=3,  # Start with just a few items
    fields="commit_info,jobs"  # Only get what you need
)
```

## Step 3: Identify Failed Jobs and Workflows
- Look for patterns of failures (e.g., all GPU tests failing, specific platforms failing)
- Use `get_filtered_jobs` with specific filters (status="failure", workflow="linux")
- For workflow-level overview, use `get_workflow_summary`

## Step 4: For Interesting Failures, Drill Down Efficiently
- Use `get_job_details` to examine a specific job without loading all jobs
- For large logs, use the download and analysis tools:
  ```python
  # Download log to file instead of loading in context
  log_info = await download_log_to_file(job_id)
  log_path = log_info["file_path"]
  
  # Extract just what you need
  patterns = await extract_log_patterns(log_path)
  test_results = await extract_test_results(log_path)
  ```

## Step 5: Analyze the Root Causes
- Compare with previous commits for regression analysis
- Identify code changes that might have introduced failures
- Check if failures match known patterns (OOM, CUDA errors, etc.)

## Step 6: Suggest Solutions
- Propose potential solutions or workarounds based on your analysis
- Prioritize fixes based on impact (blocking failures vs. minor issues)"""

@mcp.prompt()
def analyze_flaky_tests(time_range: str = "7d") -> str:
    """Create a prompt for analyzing flaky tests."""
    start_time, end_time = parse_time_range(time_range)
    return f"""Please help me analyze flaky tests in the PyTorch CI from {start_time} to {end_time}.

1. Start with a lightweight overview of trunk health
   - Use specialized endpoints for context efficiency:
   ```python
   # Get high-level trunk health metrics
   trunk_health = await get_master_commit_red("{time_range}")
   
   # Get a recent commit summary without all job details
   commit_summary = await get_commit_summary("pytorch", "pytorch", "main", "1")
   
   # Get job summary with status counts only
   job_summary = await get_job_summary("pytorch", "pytorch", "main", "1")
   ```

2. Fetch the flaky test data for the specified time period
   ```python
   # Get all flaky tests for the time range
   flaky_tests = await get_flaky_tests(time_range="{time_range}")
   
   # For specific test patterns, use filtering
   specific_flaky_test = await get_flaky_tests(
       time_range="{time_range}",
       test_name="test_distributed"  # Optional: focus on a specific test
   )
   ```

3. Identify the most frequently failing tests
   - Sort flaky tests by failure rate (num_red / total runs)
   - Look for patterns in test names, modules, or test classes
   - Group related flaky tests that might have common causes

4. For important flaky tests, find sample failure logs
   ```python
   # Get jobs where specific test failed
   failing_jobs = await get_filtered_jobs(
       "pytorch", "pytorch", "main", "1",
       status="failure",
       job_name_pattern="test_distributed"
   )
   
   # If you found a specific job ID with this test failure:
   job_id = failing_jobs["jobs"][0]["id"]  # Example job ID
   
   # Download log to file instead of loading in context
   log_info = await download_log_to_file(job_id)
   log_path = log_info["file_path"]
   
   # Extract test results without loading entire log
   test_results = await extract_test_results(log_path)
   ```

5. Analyze patterns or common causes of flakiness
   - Time-based patterns (time of day, day of week)
   - Platform-specific issues (only flaky on specific hardware)
   - Resource constraints (memory issues, race conditions)
   - Test interdependencies or ordering issues

6. Check if there are existing issues for these flaky tests
   - Look for test names in disabled test data:
   ```python
   disabled_tests = await get_disabled_test_historical(
       time_range="{time_range}",
       granularity="day"
   )
   ```

7. Suggest potential fixes or ways to address the flakiness
   - Prioritize by impact on CI reliability and developer productivity
   - Propose specific test improvements (better isolation, more deterministic setup)
   - Suggest infrastructure changes if the issue is resource-related
   - Recommend disabling persistently flaky tests if they cannot be fixed easily"""

@mcp.prompt()
def investigate_ci_performance(time_range: str = "30d") -> str:
    """Create a prompt for investigating CI performance."""
    start_time, end_time = parse_time_range(time_range)
    return f"""Please help me analyze CI performance issues from {start_time} to {end_time}.

1. Start with high-level performance metrics using specialized endpoints
   ```python
   # Get average job duration trends
   job_duration = await get_job_duration_avg(
       time_range="{time_range}",
       granularity="day"  # Options: hour, day, week
   )
   
   # Get average workflow duration trends
   workflow_duration = await get_workflow_duration_avg(
       time_range="{time_range}",
       granularity="day"
   )
   
   # Get queue time historical data
   queue_times = await get_queue_times_historical(
       time_range="{time_range}",
       granularity="hour"  # Use hour for more granular view
   )
   ```

2. Analyze current CI state using lightweight endpoints
   ```python
   # Get high-level job summary for a recent commit 
   # (without loading all job details)
   job_summary = await get_job_summary("pytorch", "pytorch", "main", "1")
   
   # Get workflow-level summary (aggregated by workflow)
   workflow_summary = await get_workflow_summary("pytorch", "pytorch", "main", "1")
   
   # Get current queue state
   queued_jobs = await get_queued_jobs()
   ```

3. Identify specific bottlenecks with targeted queries
   ```python
   # Get slowest jobs
   filtered_jobs = await get_filtered_jobs(
       "pytorch", "pytorch", "main", "1",
       per_page=20,
       fields="jobs"  # Only request job data, not pagination/filters
   )
   
   # Get utilization metadata for resource-intensive jobs
   # (if you have a specific job ID with high duration)
   utilization = await get_utilization_metadata("<job_id>")
   ```

4. Analyze test performance (if test execution is a bottleneck)
   ```python
   # Get test summary to identify slow tests
   test_summary = await get_test_summary("pytorch", "pytorch", "main", "1")
   ```

5. Analyze key performance metrics over the specified time period
   - Plot job and workflow durations over time to identify trends
   - Examine queue time patterns by time of day and day of week
   - Look for correlations between queue times and job volume
   - Identify workflows with highest variability in performance

6. Identify specific bottlenecks and performance issues
   - Jobs with highest and most variable durations
   - Workflows with poorest parallelization efficiency
   - Resource utilization patterns (CPU, memory, disk, network)
   - Infrastructure constraints (runner availability, instance types)

7. Look for performance regressions and improvement opportunities
   - Compare job durations before and after major changes
   - Identify workflows that would benefit most from optimization
   - Analyze the impact of recent infrastructure changes
   - Look for patterns in test execution times

8. Suggest data-driven improvements for CI performance
   - Specific optimizations for the slowest-running jobs
   - Resource allocation improvements based on utilization data
   - Test sharding and parallelization strategies for longest workflows
   - Queue management improvements to reduce wait times"""

@mcp.prompt()
def analyze_job_logs() -> str:
    """Create a prompt for analyzing job logs efficiently."""
    return """# PyTorch CI Log Analysis Guide

This guide will help you analyze large CI job logs efficiently without overwhelming your context window.

## Context-Efficient Log Analysis Workflow

CI job logs can be extremely large (often 50MB+), making it impossible to load them entirely into context.
Follow this workflow to analyze them efficiently:

## Step 1: Identify the Specific Job

Instead of loading all jobs with `get_hud_data`, use these specialized endpoints:

```python
# If you know the commit but not the job ID:
# Option 1: Get only failed jobs
failure_details = await get_failure_details(
    "pytorch", "pytorch", "main", "<commit_sha>",
    fields="failed_jobs",  # Only get essential fields
    include_lines="summary"  # Only get first error line per job
)

# Option 2: Filter for specific job types
filtered_jobs = await get_filtered_jobs(
    "pytorch", "pytorch", "main", "<commit_sha>",
    status="failure",  # Only get failed jobs
    job_name_pattern="linux.*cuda",  # Filter by name pattern
    fields="jobs"  # Only get job list, not other info
)
```

## Step 2: Download the Log to File

Never try to load entire logs into context:

```python
# Download log to local file for analysis
log_info = await download_log_to_file("<job_id>")
log_path = log_info["file_path"]  # Local file path for analysis
```

## Step 3: Choose Targeted Analysis Methods

Extract only what you need from the logs:

### Option A: Extract Common Error Patterns
```python
# Use default patterns (errors, warnings, exceptions, etc.)
patterns = await extract_log_patterns(log_path)
# Most common error patterns are detected automatically!

# For specific issues, use custom patterns
custom_patterns = await extract_log_patterns(
    log_path, 
    patterns={
        "cuda_errors": r"CUDA (error|exception|Assert)", 
        "memory_issues": r"(out of memory|OOM|cannot allocate|std::bad_alloc)",
        "timeouts": r"(timed out|timeout|took too long|deadline exceeded)",
        "segfaults": r"(segmentation fault|core dumped|signal 11|SIGSEGV)"
    }
)
```

### Option B: Extract Test Results
```python
# Get test statistics and failure details
test_results = await extract_test_results(log_path)

# Example: Print test summary
print(f"Tests: {test_results['test_counts']['total']} total, "
      f"{test_results['test_counts']['failed']} failed, "
      f"{test_results['test_counts']['skipped']} skipped")

# Example: Get the first 5 failed tests
for i, failure in enumerate(test_results['failures'][:5]):
    print(f"Failure {i+1}: {failure['test_name']}")
    print(f"  {failure['message'][:100]}...")  # Print just the start of the message
```

### Option C: Extract Specific Log Sections
```python
# Extract build sections only
build_sections = await filter_log_sections(
    log_path,
    start_pattern=r"Building PyTorch",
    end_pattern=r"Build completed",
    max_lines=50  # Limit lines per section to avoid context overflow
)

# Extract compiler errors
compiler_errors = await filter_log_sections(
    log_path,
    start_pattern=r"error: ",
    max_lines=20
)

# Extract test failures only
test_failures = await filter_log_sections(
    log_path,
    start_pattern=r"FAIL: test_[a-zA-Z0-9_]+",
    max_lines=30
)

# Extract CUDA-specific errors
cuda_errors = await filter_log_sections(
    log_path,
    start_pattern=r"CUDA (error|exception|assert)",
    max_lines=25
)
```

### Option D: Search Across Multiple Logs
For finding patterns across jobs:
```python
# Search for specific errors across multiple logs
cuda_search = await search_logs(
    "CUDA error",
    repo="pytorch/pytorch"  # Limit to specific repo
)

# Search for specific test failures
test_search = await search_logs(
    "FAIL: test_distributed",
    repo="pytorch/pytorch"
)
```

## Step 4: Analyze Results Efficiently

When analyzing extracted log sections:
1. Focus on error messages and stack traces first
2. Look for patterns across multiple failures
3. Check resource constraints (memory usage, disk space, GPU memory)
4. Pay attention to timing information for potential race conditions
5. Look for version mismatches in dependencies

## Common Error Patterns by Category

- **Compilation errors**: 
  - `error:`, `undefined reference`, `no member named`
  - `cannot find -l<library>`, `ld returned 1 exit status`

- **Test failures**: 
  - `FAIL:`, `AssertionError:`, `Expected ... but got ...`
  - `torch.testing._internal.common_utils.TestCase.assertRaisesRegex`

- **Memory issues**: 
  - `CUDA out of memory`, `RuntimeError: CUDA error: out of memory`
  - `std::bad_alloc`, `cannot allocate memory`
  - `Killed` (often indicates OOM killed by OS)

- **CUDA problems**:
  - `CUDA error: device-side assert triggered`
  - `CUDA error: an illegal memory access was encountered`
  - `CUDA error: launch failed`

- **Timeout issues**:
  - `timed out after`, `Process killed after exceeding timeout`
  - `deadline exceeded`, `took longer than`

Remember: Focus on extracting and analyzing relevant portions of logs rather than attempting to process entire log files."""

@mcp.tool()
async def get_recent_commit_status(repo_owner: str, repo_name: str, branch: str = "main",
                            count: int = 20, include_pending: bool = True, 
                            ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get status information for recent commits with detailed job status breakdown.

    This function provides immediate trunk health status by examining recent commits
    and their job status. Unlike the historical view from get_master_commit_red,
    this focuses on current/recent builds with detailed job status breakdowns.

    IMPORTANT: The HUD API response structure puts jobs from different commits in all
    shaGrid entries. To get accurate failure counts, we'd need to check all entries in
    the shaGrid array. Currently, we only look at the first entry which shows the most
    recent data for the specific commit, but may miss some failures from earlier builds
    of the same commit.

    NOTE: This function determines job status based solely on the job's conclusion
    field, not on the presence of failure lines.

    Args:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch: Branch name (default: 'main')
        count: Number of recent commits to check (default: 5)
        include_pending: Whether to include pending jobs in counts (default: True)
        ctx: Optional MCP context for progress reporting

    Returns:
        Dictionary with detailed status for each recent commit, including:
        - Commit metadata (sha, title, author, PR)
        - Job counts by status (success, failure, pending, etc.)
        - Overall commit status (red, green, or pending)
        - Links to each commit's HUD page
    """
    if ctx:
        await ctx.info(f"Fetching recent commit status for {repo_owner}/{repo_name} on branch {branch}")

        # Report progress
        if hasattr(ctx, 'report_progress') and callable(ctx.report_progress):
            await ctx.report_progress(0, 2)

    # Fetch a large number of recent commits with a single API call
    # We'll use a higher per_page value to get multiple commits at once
    hud_data = api.get_hud_data(repo_owner, repo_name, branch, per_page=count)

    if ctx:
        # Report progress
        if hasattr(ctx, 'report_progress') and callable(ctx.report_progress):
            await ctx.report_progress(1, 2)
        
        await ctx.info(f"Processing {len(hud_data.get('shaGrid', []))} commits from API response")

    # Process the commits from the API response
    commits = []
    sha_grid = hud_data.get("shaGrid", [])

    # Limit to the requested number of commits
    sha_grid = sha_grid[:count]

    # Process each commit in the shaGrid
    for i, commit_entry in enumerate(sha_grid):
        if ctx:
            # Report progress
            if hasattr(ctx, 'report_progress') and callable(ctx.report_progress):
                await ctx.report_progress(i, len(sha_grid))
            
            await ctx.info(f"Processing commit {i+1}/{len(sha_grid)}: {commit_entry.get('sha', 'unknown')[:7]}")

        # Default status values
        total_jobs = 0
        success_jobs = 0
        failure_jobs = 0
        pending_jobs = 0
        skipped_jobs = 0

        # Extract jobs for this commit
        jobs = commit_entry.get("jobs", [])

        for job in jobs:
            # Skip empty job entries (sometimes returned in the API)
            if not job:
                continue

            status = job.get("status", "unknown")
            conclusion = job.get("conclusion", "unknown")

            # Count jobs by status based only on the conclusion
            if conclusion == "success":
                success_jobs += 1
            elif conclusion == "failure":
                failure_jobs += 1
            elif conclusion == "skipped":
                skipped_jobs += 1
            elif status == "queued" or status == "in_progress" or conclusion == "pending":
                pending_jobs += 1

        # Calculate total
        total_jobs = success_jobs + failure_jobs + pending_jobs + skipped_jobs

        # Determine overall status
        overall_status = "unknown"
        if failure_jobs > 0:
            overall_status = "red"
        elif pending_jobs > 0 and include_pending:
            overall_status = "pending"
        elif success_jobs > 0:
            overall_status = "green"

        # Extract commit metadata
        commit_sha = commit_entry.get("sha", "")

        # Create HUD URL for this commit
        hud_url = f"https://hud.pytorch.org/{repo_owner}/{repo_name}/commit/{commit_sha}"

        # Combine all information
        commit_info = {
            "sha": commit_sha,
            "short_sha": commit_sha[:7] if commit_sha else "",
            "title": commit_entry.get("commitTitle", ""),
            "author": commit_entry.get("author", ""),
            "time": commit_entry.get("time", ""),
            "pr_num": commit_entry.get("prNum"),
            "job_counts": {
                "total": total_jobs,
                "success": success_jobs,
                "failure": failure_jobs,
                "pending": pending_jobs,
                "skipped": skipped_jobs
            },
            "status": overall_status,
            "hud_url": hud_url
        }

        commits.append(commit_info)

    if ctx:
        await ctx.info(f"Finished processing {len(commits)} commits")

    return {
        "repo": f"{repo_owner}/{repo_name}",
        "branch": branch,
        "commits": commits,
        "summary": {
            "total_commits": len(commits),
            "red_commits": sum(1 for c in commits if c["status"] == "red"),
            "green_commits": sum(1 for c in commits if c["status"] == "green"),
            "pending_commits": sum(1 for c in commits if c["status"] == "pending")
        }
    }

@mcp.tool()
async def get_recent_commit_status_resource(repo_owner: str, repo_name: str, branch: str = "main",
                                      count: int = 20, include_pending: bool = True, ctx: Optional[Context] = None) -> str:
    """Get status information for recent commits with detailed job status breakdown.

    This function provides immediate trunk health status by examining recent commits
    and their job status. Unlike the historical aggregation from get_master_commit_red,
    this focuses on current/recent builds with their actual job status.

    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch: Branch name (default: 'main')
        count: Number of recent commits to check (default: 20)
        include_pending: Whether to include pending jobs in counts (default: True)
        ctx: Optional MCP context

    Returns:
        JSON with detailed status for recent commits, including:
        - Commit metadata (sha, title, author)
        - Job counts by status (success, failure, pending)
        - Overall commit status (red, green, or pending)
    """
    # Use parameters directly - no conversion needed
    # Get data
    commit_status = await get_recent_commit_status(
        repo_owner, repo_name, branch, count, include_pending, ctx=ctx
    )

    return safe_json_dumps(commit_status, indent=2)

# Run the server if executed directly
if __name__ == "__main__":
    mcp.run()