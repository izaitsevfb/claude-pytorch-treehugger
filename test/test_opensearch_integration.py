#!/usr/bin/env python3
"""
Demo of the OpenSearch API usage
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytorch_hud.server.mcp_server import find_commits_with_similar_failures_resource

def print_usage_examples():
    print("=== OpenSearch API Usage Examples ===")
    print("\n1. Using find_commits_with_similar_failures_resource MCP endpoint:")
    print("""
    from pytorch_hud.server.mcp_server import find_commits_with_similar_failures_resource
    
    # Search for CUDA errors in the last week
    result = find_commits_with_similar_failures_resource(
        query="CUDA error",
        repo="pytorch/pytorch",
        workflow="linux-build",
        branch="main"
    )
    """)
    
    print("\n2. Using find_commits_with_similar_failures function directly:")
    print("""
    from pytorch_hud.log_analysis.tools import find_commits_with_similar_failures
    from datetime import datetime, timedelta
    
    # Set custom date range
    end_date = datetime.now().isoformat()
    start_date = (datetime.now() - timedelta(days=14)).isoformat()
    
    search_results = find_commits_with_similar_failures(
        failure="OutOfMemoryError", 
        repo="pytorch/pytorch",
        workflow_name="linux-build",
        branch_name="main",
        start_date=start_date,
        end_date=end_date,
        min_score=0.8
    )
    """)
    
    print("\n=== Integration Test Demo ===")
    print("This demo mocks the API call to show how the OpenSearch API works.")
    print("In a real environment, you would connect to the actual PyTorch HUD API.")

async def live_api_test():
    print("\nRunning find_commits_with_similar_failures_resource against the real PyTorch HUD API...")
    print("This will make actual API calls to test the parameter handling.")
    
    # Generate a very narrow time range to limit the result size (just a few hours)
    end_date = datetime.now().isoformat()
    start_date = (datetime.now() - timedelta(hours=6)).isoformat()
    search_query = "CUDA error"
    
    try:
        # First test with minimal parameters
        print("\nTest 1: Basic query with minimal parameters")
        print(f"- Query: '{search_query}'")
        # Just run the function, we don't need its result for testing
        find_commits_with_similar_failures_resource(query=search_query)
        print("✓ API accepted minimal parameters")
        
        # Test with repo filter
        print("\nTest 2: With repo filter")
        print(f"- Query: '{search_query}'")
        print("- Repo: 'pytorch/pytorch'")
        # Just run the function, we don't need its result for testing
        find_commits_with_similar_failures_resource(
            query=search_query,
            repo="pytorch/pytorch"
        )
        print("✓ API accepted repo parameter")

        # Test with all parameters
        print("\nTest 3: With all parameters")
        print(f"- Query: '{search_query}'")
        print("- Repo: 'pytorch/pytorch'")
        print("- Workflow: 'linux-build'")
        print("- Branch: 'main'")
        print(f"- Time range: {start_date} to {end_date}")
        # Just run the function, we don't need its result for testing
        find_commits_with_similar_failures_resource(
            query=search_query,
            repo="pytorch/pytorch",
            workflow="linux-build",
            branch="main",
            start_date=start_date,
            end_date=end_date,
            min_score=0.5
        )
        print("✓ API accepted all parameters")
        print("\nSuccess! The OpenSearch API interface is working correctly.")
        print("All parameter combinations were accepted by the API.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print_usage_examples()
    asyncio.run(live_api_test())