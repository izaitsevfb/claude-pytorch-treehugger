#!/usr/bin/env python3
"""
Test the resource endpoint for failure details
"""

import asyncio
import json

from pytorch_hud.server.mcp_server import get_failure_details_resource

async def main():
    print("Testing resource endpoint...")
    try:
        result = await get_failure_details_resource(
            "pytorch", 
            "pytorch", 
            "main", 
            "3960f978325222392d89ecdeb0d5baf968f654a7",
            page="1", 
            per_page="2",
            include_lines="summary"
        )
        # Result is a JSON string from the resource endpoint
        result_data = json.loads(result)
        print(f"Success! Got {len(result_data.get('failed_jobs', []))} failed jobs")
        print(result)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())