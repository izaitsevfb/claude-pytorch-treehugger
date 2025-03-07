#!/usr/bin/env python3
"""
Backward compatibility wrapper for pytorch_hud_mcp.py
"""

import sys
import runpy

# Forward all exports from the pytorch_hud package
from pytorch_hud import *

if __name__ == "__main__":
    print("WARNING: pytorch_hud_mcp.py is deprecated. Please use 'python -m pytorch_hud' instead.")
    # Run the main module as if it were called directly
    runpy.run_module("pytorch_hud", run_name="__main__")