"""
Test utilities for PyTorch HUD MCP.
"""

from unittest.mock import MagicMock, AsyncMock

def create_async_mock_context():
    """
    Create a mock context with async methods.
    
    This helper function returns a MagicMock with async info, warning, and error methods.
    Use this for consistent mocking in tests that test async functions using the MCP context.
    
    Returns:
        MagicMock: A mock context with async info, warning, and error methods
    """
    ctx_mock = MagicMock()
    ctx_mock.info = AsyncMock()
    ctx_mock.warning = AsyncMock()
    ctx_mock.error = AsyncMock()
    return ctx_mock