#!/usr/bin/env python3
"""
PyTorch HUD MCP server entry point
"""

from pytorch_hud.server.mcp_server import mcp

def main():
    """Main entry point for the application"""
    print("Starting PyTorch HUD MCP server...")
    mcp.run()

if __name__ == "__main__":
    main()