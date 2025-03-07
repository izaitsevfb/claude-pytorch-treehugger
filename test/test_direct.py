#!/usr/bin/env python3
"""
Simple test script to verify that the async functions can be called directly
"""

import asyncio
import json

from pytorch_hud.tools.hud_data import get_failure_details

async def main():
    print("Testing async function calls directly...")
    try:
        result = await get_failure_details(
            "pytorch", 
            "pytorch", 
            "main", 
            "3960f978325222392d89ecdeb0d5baf968f654a7",
            page=1, 
            per_page=2
        )
        print(f"Success! Got {len(result.get('failed_jobs', []))} failed jobs")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())