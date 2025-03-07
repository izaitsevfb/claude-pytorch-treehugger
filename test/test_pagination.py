#!/usr/bin/env python3
"""
Test pagination functionality in PyTorch HUD MCP.
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

class TestPagination(unittest.TestCase):
    """Test pagination in the get_hud_data function."""
    
    @patch('pytorch_hud.tools.hud_data.api')
    def test_explicit_page(self, mock_api):
        """Test that explicit page parameter is passed to the API."""
        from pytorch_hud.tools.hud_data import get_hud_data
        
        # Mock API response
        mock_api.get_hud_data.return_value = {
            "shaGrid": [{"sha": "a"}, {"sha": "b"}, {"sha": "c"}]
        }
        
        # Create mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Run the async function with page=2
        result = asyncio.run(get_hud_data("pytorch", "pytorch", "main", page=2, ctx=mock_ctx))
        
        # Verify API was called with correct parameters
        mock_api.get_hud_data.assert_called_with(
            "pytorch", "pytorch", "main", per_page=3, merge_lf=True, page=2
        )
        
        # Verify pagination info was added with correct page
        self.assertIn("_pagination", result)
        self.assertEqual(result["_pagination"]["page"], 2)
    
    @patch('pytorch_hud.tools.hud_data.api')
    def test_default_pagination(self, mock_api):
        """Test that the default per_page is 3 in the get_hud_data."""
        from pytorch_hud.tools.hud_data import get_hud_data
        
        # Mock API response
        mock_api.get_hud_data.return_value = {
            "shaGrid": [{"sha": "1"}, {"sha": "2"}, {"sha": "3"}]
        }
        
        # Create mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Run the async function in a synchronous test
        result = asyncio.run(get_hud_data("pytorch", "pytorch", "main", ctx=mock_ctx))
        
        # Verify API was called with per_page=3 and default page
        mock_api.get_hud_data.assert_called_with(
            "pytorch", "pytorch", "main", per_page=3, merge_lf=True, page=1
        )
        
        # Verify pagination info was added
        self.assertIn("_pagination", result)
        self.assertEqual(result["_pagination"]["per_page"], 3)
        self.assertEqual(result["_pagination"]["page"], 1)
        
    @patch('pytorch_hud.tools.hud_data.api')
    def test_custom_per_page(self, mock_api):
        """Test that custom per_page value is properly used."""
        from pytorch_hud.tools.hud_data import get_hud_data
        
        # Mock API response with 10 items
        mock_api.get_hud_data.return_value = {
            "shaGrid": [{"sha": str(i)} for i in range(10)]
        }
        
        # Create mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Run the async function with custom per_page
        result = asyncio.run(get_hud_data("pytorch", "pytorch", "main", per_page=10, ctx=mock_ctx))
        
        # Verify API was called with per_page=10 and page=1
        mock_api.get_hud_data.assert_called_with(
            "pytorch", "pytorch", "main", per_page=10, merge_lf=True, page=1
        )
        
        # Verify pagination info was added
        self.assertIn("_pagination", result)
        self.assertEqual(result["_pagination"]["per_page"], 10)
        
    @patch('pytorch_hud.tools.hud_data.api')
    def test_custom_page(self, mock_api):
        """Test that custom page value is properly used."""
        from pytorch_hud.tools.hud_data import get_hud_data
        
        # Mock API response
        mock_api.get_hud_data.return_value = {
            "shaGrid": [{"sha": str(i)} for i in range(3)]
        }
        
        # Create mock context with async methods
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()
        
        # Run the async function with custom page
        result = asyncio.run(get_hud_data("pytorch", "pytorch", "main", page=3, ctx=mock_ctx))
        
        # Verify API was called with page=3
        mock_api.get_hud_data.assert_called_with(
            "pytorch", "pytorch", "main", per_page=3, merge_lf=True, page=3
        )
        
        # Verify pagination info was added
        self.assertIn("_pagination", result)
        self.assertEqual(result["_pagination"]["page"], 3)

if __name__ == '__main__':
    unittest.main()