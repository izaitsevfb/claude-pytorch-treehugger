#!/usr/bin/env python3
"""
Tests to verify proper imports and availability of log analysis tools
"""

import unittest
import inspect

# Import all the tools we want to test
from pytorch_hud.tools.hud_data import get_job_details
from pytorch_hud.log_analysis.tools import (
    download_log_to_file, find_commits_with_similar_failures, search_logs,
    extract_log_patterns, extract_test_results, filter_log_sections
)

class LogAnalysisToolsTest(unittest.TestCase):
    """Test the availability and signatures of log analysis tools"""

    def test_tools_exist_and_have_docstrings(self):
        """Test that all log analysis tools exist and have proper docstrings"""
        tools = [
            get_job_details,
            download_log_to_file,
            find_commits_with_similar_failures,
            search_logs,  # Backward compatibility alias
            extract_log_patterns,
            extract_test_results,
            filter_log_sections
        ]
        
        for tool in tools:
            # Verify the tool exists and is callable
            self.assertTrue(callable(tool))
            
            # Verify it has a docstring
            self.assertIsNotNone(tool.__doc__)
            self.assertTrue(len(tool.__doc__.strip()) > 0)
            
            # Check for 'Args:' and 'Returns:' sections in async functions
            if inspect.iscoroutinefunction(tool):
                self.assertIn("Args:", tool.__doc__)
                self.assertIn("Returns:", tool.__doc__)
    
    def test_get_job_details_signature(self):
        """Test signature of get_job_details"""
        sig = inspect.signature(get_job_details)
        params = sig.parameters
        
        # Check key parameters
        self.assertIn("job_id", params)
        self.assertIn("ctx", params)
    
    def test_download_log_to_file_signature(self):
        """Test signature of download_log_to_file"""
        sig = inspect.signature(download_log_to_file)
        params = sig.parameters
        
        # Check key parameters
        self.assertIn("job_id", params)
        self.assertIn("ctx", params)
    
    def test_find_commits_with_similar_failures_signature(self):
        """Test signature of find_commits_with_similar_failures"""
        sig = inspect.signature(find_commits_with_similar_failures)
        params = sig.parameters
        
        # Check key parameters
        self.assertIn("failure", params)
        self.assertIn("repo", params)
        self.assertIn("workflow_name", params)
        self.assertIn("branch_name", params)
        self.assertIn("start_date", params)
        self.assertIn("end_date", params)
        self.assertIn("min_score", params)
        
    def test_search_logs_is_alias(self):
        """Test that search_logs is an alias for find_commits_with_similar_failures"""
        self.assertEqual(search_logs, find_commits_with_similar_failures)

if __name__ == "__main__":
    unittest.main()