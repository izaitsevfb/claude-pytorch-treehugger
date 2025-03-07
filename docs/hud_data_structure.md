# PyTorch HUD API Data Structure Documentation

This document outlines the structure of data returned by the PyTorch HUD API.

## Top Level Structure

The PyTorch HUD API returns a JSON object with the following top-level fields:

```json
{
  "shaGrid": [],  // Array of commit objects
  "jobNames": []  // Array of job name strings
}
```

- `shaGrid`: Array of commit objects, each representing a single commit with all its jobs
- `jobNames`: Array of job name strings, used for job name reference

## Pagination

The `per_page` parameter controls how many commits are returned in the `shaGrid` array:
- `per_page=1`: Returns only the specified commit
- `per_page=N`: Returns the specified commit plus N-1 previous commits

## Commit Object Structure

Each commit object in the `shaGrid` array has the following structure:

```json
{
  "author": "string",         // GitHub username of the commit author
  "authorUrl": "string",      // GitHub URL for the author
  "time": "string",           // ISO timestamp of the commit
  "sha": "string",            // Full commit SHA
  "commitUrl": "string",      // GitHub URL to the commit
  "commitTitle": "string",    // First line of the commit message
  "commitMessageBody": "string", // Rest of the commit message
  "prNum": number,            // PR number (if applicable)
  "diffNum": null,            // Differential number (if applicable)
  "jobs": [],                 // Array of job objects
  "isForcedMerge": boolean,   // Whether commit was force-merged
  "isForcedMergeWithFailures": boolean // Whether commit was force-merged despite failures
}
```

## Job Object Structure

Each job object has the following structure:

```json
{
  "id": number,              // Job ID (numeric)
  "name": "string",          // Job name
  "conclusion": "string",    // Job status: "success", "failure", "pending", "skipped", "queued"
  "workflowName": "string",  // Name of the workflow this job belongs to
  "url": "string",           // URL to view job details
  "duration": number,        // Job duration in seconds
  "failureLines": [          // Array of failure message lines (only present for failures)
    "string",
    "string",
    ...
  ]
}
```

Common job status values:
- `success`: Job completed successfully
- `failure`: Job failed
- `pending`: Job is running
- `skipped`: Job was skipped
- `queued`: Job is waiting to start

## Usage Examples

### Iterating Through Commits

```python
data = api.get_hud_data("pytorch", "pytorch", COMMIT_SHA, per_page=5)
for commit in data["shaGrid"]:
    print(f"Commit SHA: {commit['sha']}")
    print(f"Author: {commit['author']}")
    print(f"PR: {commit['prNum']}")
```

### Analyzing Jobs for a Commit

```python
commit = data["shaGrid"][0]  # Get the first commit in the response
jobs = commit["jobs"]

# Count jobs by status
status_counts = {}
for job in jobs:
    status = job.get("conclusion", "pending")
    status_counts[status] = status_counts.get(status, 0) + 1

# Find failing jobs
failing_jobs = [job for job in jobs if job.get("conclusion") == "failure"]
for job in failing_jobs:
    print(f"Failed job: {job.get('name')}")
    if "failureLines" in job:
        print(f"Failure reason: {job['failureLines'][0]}")
```

## Notes

1. Job IDs are numeric and should be used as integers when making API calls to get job details.
2. When using `per_page=1`, you get only the requested commit.
3. Failure information is only included for jobs that have failed.
4. Some job entries might be missing certain fields depending on their status.