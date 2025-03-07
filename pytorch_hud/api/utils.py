"""
PyTorch HUD API utility functions
"""

from datetime import datetime, timedelta
from typing import Tuple

def parse_time_range(time_range: str) -> Tuple[str, str]:
    """Parse a time range string into start and end times.
    
    Formats:
    - "7d" - last 7 days
    - "24h" - last 24 hours
    - "2023-01-01:2023-01-31" - specific date range
    - "2023-01-01:" - from specific date to now
    - ":2023-01-31" - from beginning to specific date
    
    Args:
        time_range: The time range string to parse
        
    Returns:
        Tuple of (start_time, end_time) as ISO format strings
    """
    now = datetime.now()
    
    # Check for relative time format
    if time_range.endswith('d'):
        days = int(time_range[:-1])
        start_time = (now - timedelta(days=days)).isoformat()
        end_time = now.isoformat()
        return start_time, end_time
    
    if time_range.endswith('h'):
        hours = int(time_range[:-1])
        start_time = (now - timedelta(hours=hours)).isoformat()
        end_time = now.isoformat()
        return start_time, end_time
    
    # Check for specific date range
    if ':' in time_range:
        start_str, end_str = time_range.split(':', 1)
        
        if start_str and end_str:
            # Both start and end specified
            start_time = datetime.fromisoformat(start_str).isoformat()
            end_time = datetime.fromisoformat(end_str).isoformat()
        elif start_str:
            # Only start specified
            start_time = datetime.fromisoformat(start_str).isoformat()
            end_time = now.isoformat()
        elif end_str:
            # Only end specified
            start_time = (now - timedelta(days=30)).isoformat()  # Default to last 30 days
            end_time = datetime.fromisoformat(end_str).isoformat()
        else:
            # Neither specified
            start_time = (now - timedelta(days=7)).isoformat()
            end_time = now.isoformat()
            
        return start_time, end_time
    
    # Default to last 7 days
    start_time = (now - timedelta(days=7)).isoformat()
    end_time = now.isoformat()
    return start_time, end_time