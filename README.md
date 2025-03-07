# PyTorch HUD API with MCP Support

A Python library and MCP server for interacting with the PyTorch HUD API, providing access to CI/CD data, job logs, and analytics.

## Overview

This project provides tools for PyTorch CI/CD analytics including:
- Data access for workflows, jobs, and test runs
- Efficient log analysis for large CI logs
- ClickHouse query integration for analytics
- Resource utilization metrics

## Usage (for humans)

```bash
# Install from GitHub repository
pip install git+https://github.com/izaitsevfb/claude-pytorch-treehugger.git
```

```bash
claude mcp add hud pytorch-hud
```

## Development

```bash
# Install dependencies (if not installing with pip)
pip install -r requirements.txt

# Start MCP server
python -m pytorch_hud
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
python -m unittest discover test

# Type checking
mypy -p pytorch_hud -p test

# Linting
ruff check pytorch_hud/ test/
```

## Documentation

- [CLAUDE.md](CLAUDE.md): Detailed usage, code style, and implementation notes
- [mcp-guide.md](mcp-guide.md): General MCP protocol information

## License

MIT