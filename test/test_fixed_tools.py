#!/usr/bin/env python
"""
Test script for fixed MCP tools
"""

import asyncio
import json
import logging

import requests

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fixed_tools")

async def test_job_details_resource():
    """Test the job_details_resource endpoint"""
    logger.info("Testing job_details_resource endpoint...")
    
    # Make direct HTTP request to the MCP server
    response = requests.post(
        "http://localhost:8000/tools/get_job_details_resource",
        json={"job_id": "33277771518"}
    )
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"Success! Got job details resource: {json.dumps(result, indent=2)}")
        return True
    else:
        logger.error(f"Failed to get job details: {response.status_code} - {response.text}")
        return False

async def test_download_log_resource():
    """Test the download_log_to_file_resource endpoint"""
    logger.info("Testing download_log_to_file_resource endpoint...")
    
    # Make direct HTTP request to the MCP server
    response = requests.post(
        "http://localhost:8000/tools/download_log_to_file_resource",
        json={"job_id": "33277771518"}
    )
    
    if response.status_code == 200:
        result = response.json()
        logger.info(f"Success! Got download log resource: {json.dumps(result, indent=2)}")
        return True
    else:
        logger.error(f"Failed to download log: {response.status_code} - {response.text}")
        return False

async def main():
    """Main entry point"""
    logger.info("Testing fixed MCP tools...")
    
    # Test job details resource
    job_details_success = await test_job_details_resource()
    
    # Test download log resource
    download_log_success = await test_download_log_resource()
    
    # Report results
    if job_details_success and download_log_success:
        logger.info("All tests passed!")
    else:
        logger.error("Some tests failed!")

if __name__ == "__main__":
    asyncio.run(main())