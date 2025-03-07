#!/usr/bin/env python
"""
Test async functions directly without MCP
"""

import asyncio
import json
import logging

# Import async functions we want to test
from pytorch_hud.tools.hud_data import get_job_details
from pytorch_hud.log_analysis.tools import download_log_to_file, extract_log_patterns

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_async")

async def test_async_functions():
    """Test the async functions directly"""
    
    job_id = "33277771518"  # Example job ID
    
    # Test get_job_details
    print("\n===== Testing get_job_details =====")
    try:
        job_details = await get_job_details(job_id)
        print(f"SUCCESS: Got job details for job {job_id}")
        print(json.dumps(job_details, indent=2))
    except Exception as e:
        print(f"ERROR: Failed to get job details: {e}")
    
    # Test download_log_to_file
    print("\n===== Testing download_log_to_file =====")
    try:
        log_info = await download_log_to_file(job_id)
        print(f"SUCCESS: Downloaded log for job {job_id}")
        print(json.dumps(log_info, indent=2))
        
        # If the log download succeeded, test extract_log_patterns
        if log_info.get("success") and "file_path" in log_info:
            log_path = log_info["file_path"]
            
            print("\n===== Testing extract_log_patterns =====")
            try:
                patterns = await extract_log_patterns(log_path)
                print(f"SUCCESS: Extracted patterns from log at {log_path}")
                print(json.dumps({k: v for k, v in patterns.items() if k != "samples"}, indent=2))
            except Exception as e:
                print(f"ERROR: Failed to extract patterns: {e}")
    except Exception as e:
        print(f"ERROR: Failed to download log: {e}")
    
    print("\nAsync function tests completed")

if __name__ == "__main__":
    asyncio.run(test_async_functions())