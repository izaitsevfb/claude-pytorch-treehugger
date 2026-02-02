"""
PyTorch HUD MCP server implementation

This module implements the MCP server for interfacing with PyTorch HUD API.
The server provides access to various CI/CD analytics and tools for debugging
CI issues, analyzing logs, and querying data from ClickHouse.
"""

# ==============================================================================
# MCP Registration Guidelines
# ==============================================================================
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

import json
from typing import Optional, Any, Dict
from dotenv import load_dotenv
load_dotenv()
from mcp.server.fastmcp import FastMCP, Context

from pytorch_hud.api.client import PyTorchHudAPI
from pytorch_hud.tools.hud_data import (
    get_job_details,
    get_recent_commits_with_jobs
)
from pytorch_hud.log_analysis.tools import (
    get_artifacts, get_s3_log_url, find_commits_with_similar_failures,
    download_log_to_file, extract_log_patterns, extract_test_results, filter_log_sections
)
from pytorch_hud.clickhouse.queries import (
    query_clickhouse, get_master_commit_red, get_queued_jobs, get_disabled_test_historical,
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
        "\n\n<RESPONSE TRUNCATED>\n"
        "The response exceeds the maximum size limit. Please use more specific parameters or pagination.\n"
    )

    # Calculate safe truncation size
    trunc_size = max_size - len(warning_msg)
    if trunc_size < 200:  # Ensure we have some minimal content
        trunc_size = 200

    # Return truncated JSON with error message
    return json_str[:trunc_size] + warning_msg


# ==============================================================================
# MCP Resources
# ==============================================================================
@mcp.tool()
def readme_howto_pytorch_treehugging_guide() -> str:
    """Returns a guide on identifying ongoing trunk failures and using HUD tools.
    Note: This guide gives a starting point for common pytorch treehugging tasks, but is not exhaustive.

    It is recommended to read it before using any other tools!
    """
    return (
"""

## How to: Figure out which failures are currently occurring in the latest commits of the main branch, that aren’t fixed in subsequent commits.

1. List recent commits using `get_recent_commits_with_jobs_resource`

2. Identify failing jobs
    Look for any commits that have failing jobs.

3. Compare with newer commits
    If the same job or test is failing in the same way at multiple previous commits and also at the most recent commit
    (that has no pending jobs), then it is likely an ongoing failure.
    If the most recent commit is green (and has no pending jobs), then the failure is likely fixed.
    
    Note: periodic jobs don't run on every commit, so you may need to run `get_recent_commits_with_jobs_resource` with 
    `include_success=True` and `job_name_filter_regex` to ensure that the job was run on the commits.


## How to: For a particular failure, figure out which commit first introduced it.

1. Gather the exact error text
    If the exact failure message is not known, try to infer it using
    `get_recent_commits_with_jobs_resource` or `find_commits_with_similar_failures_resource`.

2. If the error is known to be recent, use
    `get_recent_commits_with_jobs_resource` with `failure_line_filter_regex` to find the list of commits that have the error.

3. If the error is not known to be recent, use `find_commits_with_similar_failures_resource` and use the bisection by 
    `start_date` and `end_date` to narrow down the search to the smallest range of commits.

    Note: if you have a specific commit, you can use `get_recent_commits_with_jobs_resource` with `branch_or_commit_sha`
    with per_page=1 to to get the list of jobs for that commit or per_page > 1 to get the list of commits starting from this commit.

4. Double-check the specific job logs
    Once you suspect a culprit commit with job_id = X, fetch more details with:
        `get_job_details_resource(job_id=X)`
        `download_log_to_file_resource(job_id=X)`
    You can also use `extract_log_patterns_resource` to extract specific patterns from the log file.
    
    If you need to match the failure to the specific commit, see the guide on `howto_research_the_root_cause_of_the_failure`


## How to: determine why a failure is happening—whether it’s a commit, an upstream dependency, or an infra issue.

1. Make sure the failing commit (suspected root cause) and job_id.

2. Examine the logs
    `download_log_to_file_resource(job_id=X)`
    Extract relevant sections:
    `filter_log_sections_resource(file_path, start_pattern, end_pattern, max_lines=100)`
    or use pattern matching:
    `extract_log_patterns_resource(file_path, patterns)`

3. Check commit details
    If the log strongly suggests a code regression, check the commit changes.
    This might mean using the GitHub PR or commit metadata.

4. Investigate possible infra or dependency issues
    Correlate the time of failure with known system outages or changes in upstream libraries.
)
""")


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
async def get_job_details_resource(job_id: int, ctx: Optional[Context] = None) -> str:
    """Get detailed information for a specific job."""
    job_details = await get_job_details(job_id, ctx=ctx)
    return safe_json_dumps(job_details, indent=2)

@mcp.tool()
async def download_log_to_file_resource(job_id: int, ctx: Optional[Context] = None) -> str:
    """Download a job log to a temporary file for analysis."""
    log_info = await download_log_to_file(job_id, ctx=ctx)
    return safe_json_dumps(log_info, indent=2)


@mcp.tool()
async def extract_log_patterns_resource(file_path: str, patterns: Optional[Dict[Any, Any]] = None,
                                        ctx: Optional[Context] = None) -> str:
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
def find_commits_with_similar_failures_resource(query: str,
                        repo: Optional[str] = None,
                        workflow: Optional[str] = None,
                        branch: Optional[str] = None,
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        min_score: float = 1.0) -> str:
    """Find commits and jobs with similar failure text using the OpenSearch API.
    
    This tool is essential for investigating CI failures - it helps you find historical
    jobs that experienced similar error messages, helping to narrow down when issues
    first appeared or finding patterns across different jobs and workflows.
    
    Use cases:
    - Find when a specific error first started occurring
    - Check if an error is occurring in specific workflows only
    - Identify if errors are tied to specific branches or commits
    - Discover patterns in failures over time
    
    Args:
        query: The search query string containing the error or failure text
        repo: Optional repository filter (e.g., "pytorch/pytorch")
        workflow: Optional workflow name filter
        branch: Optional branch name filter (e.g., "main")
        start_date: ISO format date to begin search from (defaults to 7 days ago)
        end_date: ISO format date to end search at (defaults to now)
        min_score: Minimum relevance score for matches (defaults to 1.0)
    
    Returns:
        JSON string with matching jobs and their details, including:
        - matches: List of jobs with matching failure text
        - total_matches: Total number of matches found
        - total_lines: Total number of matching lines
    
    Examples:
        Find all Linux CI jobs with CUDA errors in the past day:
        ```
        find_commits_with_similar_failures_resource(
            query="CUDA error",
            workflow="linux-build",
            start_date="2023-03-09T00:00:00Z",
            end_date="2023-03-10T00:00:00Z"
        )
        ```
        
        Narrow down when package hash errors started appearing:
        ```
        find_commits_with_similar_failures_resource(
            query="PACKAGES DO NOT MATCH THE HASHES",
            repo="pytorch/pytorch",
            branch="main"
        )
        ```
    """
    search_result = find_commits_with_similar_failures(
        failure=query,
        repo=repo,
        workflow_name=workflow,
        branch_name=branch,
        start_date=start_date,
        end_date=end_date,
        min_score=min_score
    )
    return safe_json_dumps(search_result, indent=2)

# Alias for backward compatibility
search_logs_resource = find_commits_with_similar_failures_resource


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




# ClickHouse query resource endpoints

@mcp.tool()
def query_clickhouse_resource(query_name: str, parameters: Optional[Dict[Any, Any]] = None) -> str:
    """Run a ClickHouse query by name with parameters."""
    results = query_clickhouse(query_name, parameters or {})
    return safe_json_dumps(results, indent=2)


@mcp.tool()
async def get_master_commit_red_resource(time_range: str = "7d", timezone: str = "America/Los_Angeles",
                                         ctx: Optional[Context] = None) -> str:
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
