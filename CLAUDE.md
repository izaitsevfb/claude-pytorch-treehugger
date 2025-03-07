# PyTorch HUD API Development Guide

## Build/Run Commands
- Run MCP server: `python -m pytorch_hud` or `mcp dev pytorch_hud`
- Run API example: `python examples.py`
- Run single test: `python -m unittest test.test_log_analysis`
- Run all tests: `python -m unittest discover test`
- Run with pytest: `pytest` or `pytest test/test_specific_file.py`
- Type checking: `mypy -p pytorch_hud -p test`
- Linting: `ruff check pytorch_hud/ test/`

## Non-MCP Usage (Direct API Client)

For non-MCP use cases, you can use the API client directly:

```python
from pytorch_hud import PyTorchHudAPI
from datetime import datetime, timedelta

# Initialize API client
api = PyTorchHudAPI()

# Get HUD data for a specific commit
hud_data = api.get_hud_data("pytorch", "pytorch", "main", per_page=3)

# Query ClickHouse for CI metrics
now = datetime.now()
start_time = (now - timedelta(days=7)).isoformat()
end_time = now.isoformat()
master_red = api.query_clickhouse("master_commit_red", {
    "startTime": start_time,
    "stopTime": end_time,
    "timezone": "America/Los_Angeles"
})

# Search logs across jobs
search_results = api.search_logs("OutOfMemoryError", repo="pytorch/pytorch")
```

## Code Style Guidelines
- **Imports**: Standard library first, then third-party, then local (separated by newlines)
- **Type Hints**: Use type hints for all function parameters and return values
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants
- **Docstrings**: Use Google-style docstrings with Args/Returns sections
- **Error Handling**: Use specific exceptions, wrap external API calls with retry logic
- **Line Length**: 88 characters (Black formatting standard)
- **Formatting**: Compatible with Black and ruff
- **Logging**: Use Python's logging module with appropriate log levels (not print)
- **API Wrapper Pattern**: Create clean interfaces over external HTTP APIs

## MCP Server Implementation Notes

### Async Functions and MCP

FastMCP fully supports async functions as tools. You can register them directly with `@mcp.tool()` or using the function call style `mcp.tool()(function_name)`.

#### Direct Registration Example:

```python
# Register an async function directly - this is completely fine
@mcp.tool()
async def get_failure_details(repo_owner: str, repo_name: str, ...) -> Dict[str, Any]:
    """Async function that fetches failure details."""
    # Implementation...
    return result_data
```

#### Resource Endpoints for Extra Processing:

You can also create resource endpoints that await async functions. This approach can be useful when you need to:
- Parse string parameters to appropriate types
- Apply additional processing to the results
- Format the results differently (e.g., return JSON string)

```python
# 1. Define your async function in the tools module
@mcp.tool()  # Register the direct async function
async def get_failure_details(repo_owner: str, repo_name: str, ...) -> Dict[str, Any]:
    """Async function that fetches failure details."""
    # Implementation...
    return result_data

# 2. Create a resource endpoint for additional processing
@mcp.tool()
async def get_failure_details_resource(repo_owner: str, repo_name: str, ...) -> str:
    """Resource endpoint with additional processing."""
    # Parse string parameters to proper types if needed
    page_int = int(page) if page is not None else 1
    
    # Call the async function with await
    failure_details = await get_failure_details(repo_owner, repo_name, ..., page=page_int)
    
    # Apply additional processing if needed
    filtered_results = process_results(failure_details, include_lines)
    
    # Return the result as a JSON string
    return safe_json_dumps(filtered_results)
```

Both approaches work correctly with FastMCP, which properly handles awaiting async functions.

### Tool Registration

For both async and non-async functions, use the simple decorator syntax without specifying URL paths:

```python
# Synchronous function
@mcp.tool()
def get_artifacts(provider: str, job_id: str) -> Dict[str, Any]:
    """Function documentation..."""
    # Implementation

# Asynchronous function - works exactly the same way
@mcp.tool()
async def get_failure_details(repo_owner: str, ...) -> Dict[str, Any]:
    """Async function documentation..."""
    # Async implementation
    result = await some_async_call()
    return result
```

The MCP server will automatically use the function name as the tool name and handle async/sync correctly.

### MCP Context Usage

The MCP Context object doesn't provide access to additional parameters, but it can be used for supplementary MCP features:

```python
@mcp.tool()
async def get_filtered_jobs_resource(repo_owner: str, repo_name: str, ...) -> str:
    """Resource endpoint for filtered jobs."""
    # Parse parameters...
    
    # Get filtered jobs
    filtered_jobs = await get_filtered_jobs(repo_owner, repo_name, ...)
    
    return safe_json_dumps(filtered_jobs)

# In the implementation function, you can use the context
async def get_filtered_jobs(repo_owner: str, repo_name: str, ..., ctx: Context = None) -> Dict[str, Any]:
    """Async function that fetches filtered jobs."""
    
    # Use the context for progress reporting and logging
    if ctx:
        ctx.info(f"Fetching filtered jobs for {repo_owner}/{repo_name}")
        
        # Report progress during long operations
        for i, file in enumerate(files):
            ctx.info(f"Processing {file}")
            await ctx.report_progress(i, len(files))
```

### Testing Async Resource Endpoints

When testing async resource endpoints, make sure to:

1. Patch at the correct import point (where the function is used, not where it's defined)
2. Use proper async test classes and methods
3. Reset mocks between calls if needed

```python
class TestFailureDetailsResource(unittest.IsolatedAsyncioTestCase):
    @patch('pytorch_hud.server.mcp_server.get_failure_details')  # Patch where it's used
    async def test_failure_details_resource(self, mock_get_failure_details):
        # Setup mock return value
        mock_get_failure_details.return_value = {...}
        
        # Call the resource endpoint
        result = await get_failure_details_resource(...)
        
        # Verify that the async function was called properly
        mock_get_failure_details.assert_called_once_with(...)
```

## Log Analysis Features

The PyTorch HUD MCP Server provides tools for efficiently analyzing CI job logs without overwhelming the context window:

### Log Analysis Workflow

1. **Get job information**:
   ```python
   from pytorch_hud.tools.hud_data import get_hud_data
   
   # You can use a branch name to get recent commits:
   hud_data = await get_hud_data("pytorch", "pytorch", "main")
   
   # Or use a specific commit SHA:
   hud_data = await get_hud_data("pytorch", "pytorch", "<commit_sha>")
   
   job_id = "<job_id_from_hud_data>"
   ```

2. **Download log to local file**:
   ```python
   from pytorch_hud.log_analysis.tools import download_log_to_file
   log_info = await download_log_to_file(job_id)
   log_path = log_info["file_path"]
   ```

3. **Choose analysis approach**:
   ```python
   from pytorch_hud.log_analysis.tools import extract_log_patterns, extract_test_results, filter_log_sections, search_logs
   
   # Find patterns
   patterns = await extract_log_patterns(log_path)
   
   # Extract test results
   test_results = await extract_test_results(log_path)
   
   # Get specific sections
   sections = await filter_log_sections(log_path, start_pattern="pattern")
   
   # Search across logs
   search_results = search_logs("pattern", repo="pytorch/pytorch")
   ```

### Common Error Patterns

- **Compilation errors**: `"error:", "undefined reference"`
- **Test failures**: `"FAIL", "AssertionError"`
- **Resource issues**: `"OutOfMemoryError", "timeout"`
- **CUDA problems**: `"CUDA error", "cudaLaunchKernel"`

## Getting Started with Trunk Health Investigation

When investigating trunk health or CI issues, always start with `get_hud_data`:

```python
# This is the primary entry point for investigating build/test failures and trunk health
from pytorch_hud.tools.hud_data import get_hud_data

# Using a branch name returns recent commits from that branch:
hud_data = await get_hud_data("pytorch", "pytorch", "main")

# Using a commit SHA returns data starting from that specific commit:
hud_data = await get_hud_data("pytorch", "pytorch", "<commit_sha>")
```

For broader trunk health overview:
```python
# Get trunk health metrics for the past 7 days
from pytorch_hud.clickhouse.queries import get_master_commit_red
trunk_health = await get_master_commit_red("7d")
```

After identifying failing jobs through `get_hud_data`, you can:
1. Download and analyze specific job logs
2. Search for error patterns across multiple logs
3. Investigate resource constraints or performance issues

## Project Overview

The primary functionality is a wrapper for the PyTorch HUD API with CLI and MCP server interfaces, providing:

1. **HUD Data Access**: Retrieve information about workflows, jobs, and test runs (always start here for investigations)
2. **Log Analysis**: Efficiently process large log files
3. **ClickHouse Queries**: Execute pre-defined queries against PyTorch CI analytics database
4. **Resource Metrics**: Analyze CI performance and resource usage

### Documentation

- **API Response Structure**: See `/docs/hud_data_structure.md` for detailed documentation of the HUD data response format and structure
- **Sample Data**: A sample HUD data response is available at `/docs/hud_data_sample.json`

## Note about Async Functions

Our earlier understanding that async functions couldn't be directly registered with FastMCP was incorrect. FastMCP fully supports async functions, as shown in their example code and implementation.

FastMCP properly detects and handles async functions by checking `inspect.iscoroutinefunction(fn)` in their Tool.from_function method.

## Known Gotchas

### Parameter Type Mismatches

When you see an `undefined` error from a tool call, it may be due to a type mismatch. Common examples:

1. **Job IDs**: While job IDs are shown and often typed as numbers (e.g., `38351555343`), the functions should use parameter type `int`, not `str`. For instance:
   
   ```python
   # CORRECT:
   async def get_job_details(job_id: int, ctx: Context = None)
   
   # INCORRECT:
   async def get_job_details(job_id: str, ctx: Context = None)
   ```
   
   When a numeric parameter is passed to a function expecting a string type, you'll get an `undefined` error with a message like:
   ```
   Error executing tool get_job_details: 1 validation error for get_job_detailsArguments
   job_id
     Input should be a valid string [type=string_type, input_value=38351555343, input_type=int]
   ```

   The solution is to use the correct parameter type (`int` for IDs) and convert to `str` inside the function when passing to API calls:
   
   ```python
   job_id_str = str(job_id)
   result = api.get_job_details(job_id_str)
   ```