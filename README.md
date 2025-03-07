# PyTorch HUD API with MCP Support

A Python library and MCP server for interacting with the PyTorch HUD API, providing access to CI/CD data, job logs, and analytics.

## Overview

This project provides tools for PyTorch CI/CD analytics including:
- Data access for workflows, jobs, and test runs
- Efficient log analysis for large CI logs
- ClickHouse query integration for analytics
- Resource utilization metrics

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Start MCP server
python -m pytorch_hud
```

## Usage with Claude

```python
# Get overview of a specific commit
commit_data = await get_commit_summary("pytorch", "pytorch", "main")

# Get detailed failure information
failure_data = await get_failure_details("pytorch", "pytorch", "main")

# Analyze logs efficiently
log_info = await download_log_to_file(12345678)
patterns = await extract_log_patterns(log_info["file_path"])
```

## Key Features

### Data Access

- `get_commit_summary`: Basic commit info without jobs
- `get_job_summary`: Aggregated job status counts
- `get_filtered_jobs`: Jobs with filtering by status/workflow/name
- `get_failure_details`: Failed jobs with detailed failure info
- `get_recent_commit_status`: Status for recent commits with job statistics

### Log Analysis

- `download_log_to_file`: Download logs to local storage
- `extract_log_patterns`: Find errors, warnings, etc.
- `extract_test_results`: Parse test execution results
- `filter_log_sections`: Extract specific log sections
- `search_logs`: Search across multiple logs

## Development

```bash
# Run tests
pytest

# Type checking
mypy -p pytorch_hud -p test

# Linting
ruff check pytorch_hud/ test/
```

## Documentation

- [CLAUDE.md](CLAUDE.md): Detailed usage, code style, and implementation notes
- [README_MCP.md](README_MCP.md): MCP server features and tool reference
- [mcp-guide.md](mcp-guide.md): General MCP protocol information

## License

MIT