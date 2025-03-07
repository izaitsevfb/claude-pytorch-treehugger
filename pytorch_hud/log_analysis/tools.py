"""
PyTorch HUD log analysis tools
"""

import os
import re
import datetime
from typing import Dict, Any, Optional, List, cast
from mcp.server.fastmcp import Context

from pytorch_hud.api.client import PyTorchHudAPI

# Initialize API client singleton
api = PyTorchHudAPI()

def get_artifacts(provider: str, job_id: str) -> Dict[str, Any]:
    """Get artifacts for a job."""
    return api.get_artifacts(provider, job_id)

def get_s3_log_url(job_id: str) -> str:
    """Get the S3 log URL for a job."""
    return api.get_s3_log_url(job_id)

def get_utilization_metadata(job_id: str) -> Dict[str, Any]:
    """Get utilization metadata for a job."""
    return api.get_utilization_metadata(job_id)

def search_logs(query: str, repo: Optional[str] = None, workflow: Optional[str] = None) -> Dict[str, Any]:
    """Search job logs.
    
    Args:
        query: The search query (can be regex pattern)
        repo: Optional repository filter (e.g., "pytorch/pytorch") 
        workflow: Optional workflow name filter
        
    Note:
        This search is limited to showing the first 100 matching lines per job,
        and lines are truncated to 100 characters if longer.
    """
    return api.search_logs(query, repo=repo, workflow=workflow)

async def download_log_to_file(job_id: int, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Download a job log to a temporary file for analysis.
    
    This tool helps with analyzing large log files by downloading them
    to local storage instead of loading them entirely into context.
    
    Args:
        job_id: The job ID to download
        ctx: MCP context
        
    Returns:
        Dictionary with file path and metadata
    """
    # Log the start of download
    if ctx:
        await ctx.info(f"Downloading log for job {job_id}")
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.getcwd(), "temp_logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Convert job_id to string for API calls
    job_id_str = str(job_id)
    
    # Generate a filename based on job_id
    filename = f"job_{job_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    filepath = os.path.join(logs_dir, filename)
    
    try:
        # Download the log
        log_content = api.download_log(job_id_str)
        
        # Write to file
        with open(filepath, 'w') as f:
            f.write(log_content)
        
        # Get basic metadata
        file_size = os.path.getsize(filepath)
        line_count = log_content.count('\n') + 1
        
        if ctx:
            await ctx.info(f"Log downloaded successfully: {filepath} ({file_size} bytes, {line_count} lines)")
        
        return {
            "success": True,
            "file_path": filepath,
            "job_id": job_id,
            "size_bytes": file_size,
            "line_count": line_count,
            "url": api.get_s3_log_url(job_id_str)
        }
    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to download log: {e}")
        return {
            "success": False,
            "error": str(e),
            "job_id": job_id
        }

async def extract_log_patterns(file_path: str, 
                          patterns: Optional[Dict[str, str]] = None, 
                          ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Extract matches for specified patterns from a log file.
    
    This tool helps analyze log files by finding patterns of interest
    without loading the entire file into context.
    
    Args:
        file_path: Path to the log file
        patterns: Dictionary of pattern_name:regex_pattern pairs to search for
                 If None, uses default patterns for common errors and warnings
        ctx: MCP context
    
    Returns:
        Dictionary with pattern matches and counts
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }
    
    if ctx:
        await ctx.info(f"Analyzing log file: {file_path}")
    
    # Default patterns if none provided
    default_patterns = {
        "error": r"(?i)error:",
        "exception": r"(?i)exception:",
        "warning": r"(?i)warning:",
        "test_failed": r"FAILED.*test_",
        "test_results": r"Ran (\d+) tests.*?(\d+) failures",
        "cuda_error": r"CUDA error|CUDA exception|cudaError",
        "out_of_memory": r"OutOfMemoryError|OOM|out of memory",
        "build_failed": r"Build failed|compilation failed|error: command .* failed"
    }
    
    use_patterns = patterns or default_patterns
    
    # Initialize result dict with properly typed fields
    results: Dict[str, Any] = {
        "success": True,
        "file_path": file_path,
        "matches": {},
        "counts": {},
        "samples": {}
    }
    
    if ctx:
        await ctx.info(f"Searching for {len(use_patterns)} patterns: {', '.join(use_patterns.keys())}")
    
    # Compile patterns
    compiled_patterns = {name: re.compile(pattern) for name, pattern in use_patterns.items()}
    
    # Process file
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                for name, pattern in compiled_patterns.items():
                    match = pattern.search(line)
                    if match:
                        # Initialize if first match
                        if name not in cast(Dict[str, Any], results["matches"]):
                            results["matches"][name] = []
                            results["counts"][name] = 0
                            results["samples"][name] = []
                        
                        # Add match information
                        cast(Dict[str, int], results["counts"])[name] += 1
                        
                        # Store limited number of samples with line numbers
                        sample_list = cast(Dict[str, List[Dict[str, Any]]], results["samples"])[name]
                        if len(sample_list) < 5:
                            truncated_line = line.strip()[:150]
                            sample_list.append({
                                "line_num": line_num,
                                "text": truncated_line,
                                "groups": match.groups() if match.groups() else None
                            })
        
        if ctx:
            await ctx.info(f"Analysis complete. Found matches for {len(cast(Dict[str, Any], results['counts']))} patterns.")
            for name, count in cast(Dict[str, int], results["counts"]).items():
                await ctx.info(f"  - {name}: {count} matches")
        
        return results
    except Exception as e:
        if ctx:
            await ctx.error(f"Error analyzing log: {e}")
        return {
            "success": False,
            "error": str(e),
            "file_path": file_path
        }

async def extract_test_results(file_path: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Extract test results specifically from a log file.
    
    This tool specializes in finding test execution results from various
    testing frameworks (pytest, unittest) without loading the entire log
    into context.
    
    Args:
        file_path: Path to the log file
        ctx: MCP context
        
    Returns:
        Dictionary with test statistics and failures
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }
    
    if ctx:
        await ctx.info(f"Extracting test results from: {file_path}")
    
    # Initialize results with proper typing
    results: Dict[str, Any] = {
        "success": True,
        "file_path": file_path,
        "test_counts": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        },
        "failed_tests": [],
        "duration": None
    }
    
    # Patterns for different test frameworks
    patterns = {
        "pytest_summary": re.compile(r"=+ ([\d]+) failed, ([\d]+) passed, ([\d]+) skipped"),
        "unittest_summary": re.compile(r"Ran ([\d]+) tests in ([\d\.]+)s"),
        "unittest_failure": re.compile(r"FAILED \((.+)\)"),
        "test_failure": re.compile(r"FAIL: (test\w+)"),
        "error_failure": re.compile(r"ERROR: (test\w+)")
    }
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Check for pytest summary
                pytest_match = patterns["pytest_summary"].search(line)
                if pytest_match:
                    test_counts = cast(Dict[str, int], results["test_counts"])
                    test_counts["failed"] = int(pytest_match.group(1))
                    test_counts["passed"] = int(pytest_match.group(2))
                    test_counts["skipped"] = int(pytest_match.group(3))
                    test_counts["total"] = (
                        test_counts["failed"] + 
                        test_counts["passed"] + 
                        test_counts["skipped"]
                    )
                
                # Check for unittest summary
                unittest_match = patterns["unittest_summary"].search(line)
                if unittest_match:
                    cast(Dict[str, int], results["test_counts"])["total"] = int(unittest_match.group(1))
                    results["duration"] = unittest_match.group(2)
                
                # Check for failure details
                for pattern_name in ["test_failure", "error_failure"]:
                    failure_match = patterns[pattern_name].search(line)
                    failed_tests = cast(List[Dict[str, Any]], results["failed_tests"])
                    if failure_match and len(failed_tests) < 20:  # Limit number of failures
                        test_name = failure_match.group(1)
                        
                        # Get a few lines of context after the failure
                        context_lines: List[str] = []
                        for i in range(line_num, min(line_num + 5, len(lines) + 1)):
                            if i-1 < len(lines):  # Make sure we don't go out of bounds
                                context_lines.append(lines[i-1].strip())
                        
                        failed_tests.append({
                            "test_name": test_name,
                            "line_num": line_num,
                            "context": context_lines  # Context lines
                        })
        
        if ctx:
            test_counts = cast(Dict[str, int], results["test_counts"])
            if test_counts["total"] > 0:
                await ctx.info(f"Found test results: {test_counts['total']} total tests")
                await ctx.info(f"  - Passed: {test_counts['passed']}")
                await ctx.info(f"  - Failed: {test_counts['failed']}")
                await ctx.info(f"  - Skipped: {test_counts['skipped']}")
                failed_tests = cast(List[Dict[str, Any]], results["failed_tests"])
                if failed_tests:
                    await ctx.info(f"  - Found {len(failed_tests)} failed test details")
            else:
                await ctx.info("No test results found in the log")
        
        return results
    except Exception as e:
        if ctx:
            await ctx.error(f"Error extracting test results: {e}")
        return {
            "success": False,
            "error": str(e),
            "file_path": file_path
        }

async def filter_log_sections(file_path: str, 
                        start_pattern: Optional[str] = None, 
                        end_pattern: Optional[str] = None,
                        max_lines: int = 100, 
                        ctx: Optional[Context] = None) -> Dict[str, Any]:
    """Extract specific sections from a log file based on start/end patterns.
    
    This tool helps retrieve only relevant sections of large log files
    without loading the entire file into context.
    
    Args:
        file_path: Path to the log file
        start_pattern: Regex pattern that marks the start of a section
        end_pattern: Regex pattern that marks the end of a section
        max_lines: Maximum number of lines to return per section
        ctx: MCP context
        
    Returns:
        Dictionary with extracted sections
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }
    
    if ctx:
        await ctx.info(f"Filtering sections from log file: {file_path}")
    
    if not start_pattern:
        return {
            "success": False,
            "error": "Start pattern is required"
        }
    
    try:
        start_re = re.compile(start_pattern)
        end_re = re.compile(end_pattern) if end_pattern else None
        
        # Initialize results with proper typing
        results: Dict[str, Any] = {
            "success": True,
            "file_path": file_path,
            "sections": [],
            "section_count": 0
        }
        
        with open(file_path, 'r') as f:
            in_section = False
            current_section: List[str] = []
            current_start_line = 0
            
            for line_num, line in enumerate(f, 1):
                # Check for section start
                if not in_section and start_re.search(line):
                    in_section = True
                    current_section = [line.rstrip()]
                    current_start_line = line_num
                    continue
                
                # Add lines while in a section
                if in_section:
                    # Check if we've reached max lines for this section
                    if len(current_section) >= max_lines:
                        # Add truncation note and end the section
                        current_section.append(f"... [truncated after {max_lines} lines] ...")
                        cast(List[Dict[str, Any]], results["sections"]).append({
                            "start_line": current_start_line,
                            "content": "\n".join(current_section),
                            "truncated": True
                        })
                        results["section_count"] = cast(int, results["section_count"]) + 1
                        in_section = False
                        current_section = []
                        continue
                    
                    # Check for section end if an end pattern was provided
                    if end_re and end_re.search(line):
                        current_section.append(line.rstrip())
                        cast(List[Dict[str, Any]], results["sections"]).append({
                            "start_line": current_start_line,
                            "content": "\n".join(current_section),
                            "truncated": False
                        })
                        results["section_count"] = cast(int, results["section_count"]) + 1
                        in_section = False
                        current_section = []
                        continue
                    
                    # Otherwise, add the line to the current section
                    current_section.append(line.rstrip())
            
            # If we're still in a section at the end of the file, add it
            if in_section and current_section:
                cast(List[Dict[str, Any]], results["sections"]).append({
                    "start_line": current_start_line,
                    "content": "\n".join(current_section),
                    "truncated": False
                })
                results["section_count"] = cast(int, results["section_count"]) + 1
        
        if ctx:
            await ctx.info(f"Found {results['section_count']} matching sections")
        
        return results
    except Exception as e:
        if ctx:
            await ctx.error(f"Error filtering log sections: {e}")
        return {
            "success": False,
            "error": str(e),
            "file_path": file_path
        }