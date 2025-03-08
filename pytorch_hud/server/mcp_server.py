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
    get_commit_summary, get_job_summary, get_job_details, get_test_summary,
    get_recent_commits_with_jobs
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


# The get_filtered_jobs_resource function has been replaced by the more flexible
# get_recent_commits_with_jobs_resource function.
# 
# For equivalent functionality, use:
# get_recent_commits_with_jobs_resource(
#     repo_owner=repo_owner,
#     repo_name=repo_name,
#     branch_or_commit_sha=branch_or_commit_sha,
#     include_success=True if status=="success" else False,
#     include_pending=True if status=="pending" else False,
#     include_failures=True if status=="failure" else False, 
#     job_name_filter_regex=job_name_pattern,
#     page=page,
#     per_page=per_page
# )

# The get_failure_details_resource function has been replaced by the more flexible
# get_recent_commits_with_jobs_resource function.
# 
# For equivalent functionality, use:
# get_recent_commits_with_jobs_resource(
#     repo_owner=repo_owner,
#     repo_name=repo_name,
#     branch_or_commit_sha=branch_or_commit_sha,
#     include_failures=True,
#     include_success=False,
#     include_pending=False,
#     page=page,
#     per_page=per_page,
#     # Optionally filter by specific failure lines
#     # failure_line_filter_regex="pattern"
# )
# 
# Note: The new function doesn't have an equivalent of the 'include_lines' parameter
# for controlling the verbosity of failure lines. This feature may need to be added
# to the universal function if needed.

@mcp.tool()
async def get_job_details_resource(job_id: int, ctx: Optional[Context] = None) -> str:
    """Get detailed information for a specific job."""
    job_details = await get_job_details(job_id, ctx=ctx)
    return safe_json_dumps(job_details, indent=2)

# The get_workflow_summary_resource function has been replaced by the more flexible
# get_recent_commits_with_jobs_resource function.
# 
# For equivalent workflow summary, use:
# get_recent_commits_with_jobs_resource(
#     repo_owner=repo_owner,
#     repo_name=repo_name,
#     branch_or_commit_sha=branch_or_commit_sha,
#     include_success=True,
#     include_failures=True,
#     include_pending=True
# )
# 
# Note: The workflow aggregation will need to be done client-side with the
# data from the universal function.

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

# The get_recent_commit_status and get_recent_commit_status_resource functions
# have been replaced by the more flexible get_recent_commits_with_jobs and
# get_recent_commits_with_jobs_resource functions.
# 
# For equivalent functionality as the old get_recent_commit_status_resource, use:
# get_recent_commits_with_jobs_resource(
#     repo_owner=repo_owner, 
#     repo_name=repo_name, 
#     branch_or_commit_sha=branch_or_commit_sha,
#     per_page=count
# )

@mcp.tool()
async def get_recent_commits_with_jobs_resource(
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
) -> str:
    """Universal function for getting recent commits with flexible filtering options.
    
    This consolidated endpoint replaces multiple specialized endpoints, providing
    a single interface for retrieving commits and jobs with precise control over
    what data is included to optimize context window usage.
    
    Parameters:
        repo_owner: Repository owner (e.g., 'pytorch')
        repo_name: Repository name (e.g., 'pytorch')
        branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
        
        # Job inclusion filters - control what job types to include
        include_success: Include successful jobs (default: False)
        include_pending: Include pending/in-progress jobs (default: False)
        include_failures: Include failing jobs (default: False)
        include_commit_details: Include PR number, diff URL, etc. (default: True)
        
        # Job content filters - control which jobs to include based on content
        job_name_filter_regex: Only include jobs with names matching regex
        failure_line_filter_regex: Only include jobs with failure lines matching regex
        
        # Pagination parameters
        page: Page number (default: 1)
        per_page: Number of commits per page (default: 10)
        
        ctx: Optional MCP context
    
    Returns:
        JSON with flexible combination of commits and jobs based on filter settings
        
    Usage examples:
    
    1. Get basic commit info (default):
       ```
       get_recent_commits_with_jobs_resource()
       ```
       
    2. Get failing GPU jobs:
       ```
       get_recent_commits_with_jobs_resource(include_failures=True, job_name_filter_regex="cuda|gpu")
       ```
       
    3. Get OOM errors:
       ```
       get_recent_commits_with_jobs_resource(include_failures=True, failure_line_filter_regex="OOM")
       ```
    """
    result = await get_recent_commits_with_jobs(
        repo_owner=repo_owner,
        repo_name=repo_name,
        branch_or_commit_sha=branch_or_commit_sha,
        include_success=include_success,
        include_pending=include_pending,
        include_failures=include_failures,
        include_commit_details=include_commit_details,
        job_name_filter_regex=job_name_filter_regex,
        failure_line_filter_regex=failure_line_filter_regex,
        page=page,
        per_page=per_page,
        ctx=ctx
    )
    
    # Add timestamp and request metadata
    result["_metadata"].update({
        "api_call": "get_recent_commits_with_jobs_resource",
        "parameter_signatures": {
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "branch_or_commit_sha": branch_or_commit_sha,
            "include_success": include_success,
            "include_pending": include_pending,
            "include_failures": include_failures,
            "page": page,
            "per_page": per_page
        }
    })
    
    return safe_json_dumps(result, indent=2)

# Run the server if executed directly
if __name__ == "__main__":
    mcp.run()