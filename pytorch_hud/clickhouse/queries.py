"""
PyTorch HUD ClickHouse query wrappers
"""

from typing import Dict, Any, Optional
from mcp.server.fastmcp import Context

from pytorch_hud.api.client import PyTorchHudAPI
from pytorch_hud.api.utils import parse_time_range

# Initialize API client singleton
api = PyTorchHudAPI()

def query_clickhouse(query_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a ClickHouse query by name with parameters."""
    return api.query_clickhouse(query_name, parameters)

async def get_master_commit_red(time_range: str = "7d", 
                         timezone: str = "America/Los_Angeles", 
                         ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get historical master commit status aggregated by day for a specified time range.
    
    This function provides a historical view of trunk health with daily aggregation,
    showing counts of red/green/pending commits per day. For immediate trunk status
    of specific recent commits, use get_recent_commit_status instead.
    
    Args:
        time_range: Time range (e.g., 7d, 24h, 2023-01-01:2023-01-31)
        timezone: Timezone to use for the query
        ctx: MCP context
        
    Returns:
        Dictionary with daily counts of red/green/pending commits
    """
    if ctx:
        await ctx.info(f"Fetching master commit red data for time range: {time_range}")
        
    start_time, end_time = parse_time_range(time_range)
    
    if ctx:
        await ctx.info(f"Time range resolved to: {start_time} - {end_time}")
        
    parameters = {
        "startTime": start_time,
        "stopTime": end_time,
        "timezone": timezone
    }
    
    return api.query_clickhouse("master_commit_red", parameters)

def get_queued_jobs() -> Dict[str, Any]:
    """Get queued jobs data."""
    return api.query_clickhouse("queued_jobs", {})

async def get_disabled_test_historical(time_range: str = "7d", 
                                  label: str = "skipped", 
                                  repo: str = "pytorch/pytorch",
                                  state: str = "open", 
                                  platform: str = "", 
                                  triaged: str = "", 
                                  granularity: str = "day",
                                  ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get historical disabled test data."""
    if ctx:
        await ctx.info(f"Fetching disabled test data for time range: {time_range}")
        
    start_time, end_time = parse_time_range(time_range)
    
    if ctx:
        await ctx.info(f"Time range resolved to: {start_time} - {end_time}")
        
    parameters = {
        "startTime": start_time,
        "stopTime": end_time,
        "label": label,
        "repo": repo,
        "state": state,
        "platform": platform,
        "triaged": triaged,
        "granularity": granularity
    }
    
    return api.query_clickhouse("disabled_test_historical", parameters)


async def get_flaky_tests(time_range: str = "7d",
                    test_name: Optional[str] = None, 
                    ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Get flaky test data."""
    if ctx:
        await ctx.info(f"Fetching flaky test data for test: {test_name or 'all tests'}")
        
    start_time, end_time = parse_time_range(time_range)
    
    if ctx:
        await ctx.info(f"Time range resolved to: {start_time} - {end_time}")
        
    parameters = {
        "startTime": start_time,
        "stopTime": end_time
    }
    
    if test_name:
        parameters["test_name"] = test_name
    
    return api.query_clickhouse("flaky_tests/across_jobs", parameters)
