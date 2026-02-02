"""
PyTorch HUD API client implementation
"""

import json
import os
import requests
import logging
import time
from typing import Dict, Any, List, Optional
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PyTorchHud")

class PyTorchHudAPIError(Exception):
    """Base exception for API errors."""
    pass

class PyTorchHudAPI:
    """Python wrapper for the PyTorch Hud APIs."""

    BASE_URL = "https://hud.pytorch.org/api"

    def __init__(self, base_url: Optional[str] = None, retry_attempts: int = 3, retry_delay: float = 1.0):
        """Initialize with optional custom base URL.

        Args:
            base_url: Optional custom base URL for the API
            retry_attempts: Number of times to retry failed requests (default: 3)
            retry_delay: Initial delay between retries in seconds, doubles after each retry (default: 1.0)
        """
        self.base_url = base_url or self.BASE_URL
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._clickhouse_queries_cache: Optional[List[str]] = None

        bot_token = os.environ.get("HUD_INTERNAL_BOT_TOKEN", "")
        self._headers: Dict[str, str] = {}
        if bot_token:
            self._headers["x-hud-internal-bot"] = bot_token

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
                     retry_remaining: Optional[int] = None) -> Dict[str, Any]:
        """Make a GET request to the API with retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            retry_remaining: Number of retry attempts left (internal use)

        Returns:
            Parsed JSON response

        Raises:
            PyTorchHudAPIError: If the request fails after all retries
        """
        if retry_remaining is None:
            retry_remaining = self.retry_attempts

        url = f"{self.base_url}/{endpoint}"

        try:
            logger.debug(f"Making request to {url} with params {params}")
            response = requests.get(url, params=params, headers=self._headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if retry_remaining > 0:
                delay = self.retry_delay * (2 ** (self.retry_attempts - retry_remaining))
                logger.warning(f"Request to {url} failed: {e}. Retrying in {delay:.2f}s... ({retry_remaining} attempts left)")
                time.sleep(delay)
                return self._make_request(endpoint, params, retry_remaining - 1)
            else:
                logger.error(f"Request to {url} failed after {self.retry_attempts} attempts: {e}")
                raise PyTorchHudAPIError(f"Failed to make request to {url}: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from {url}: {e}")
            raise PyTorchHudAPIError(f"Failed to parse JSON response from {url}: {e}") from e

    def get_hud_data(self, repo_owner: str, repo_name: str, branch_or_commit_sha: str,
                     per_page: Optional[int] = None, merge_lf: Optional[bool] = None, 
                     page: Optional[int] = None) -> Dict[str, Any]:
        """Get HUD data for a specific commit or branch.

        Args:
            repo_owner: Repository owner (e.g., 'pytorch')
            repo_name: Repository name (e.g., 'pytorch')
            branch_or_commit_sha: Branch name (e.g., 'main') or commit SHA
                - When passing a branch name like 'main', returns recent commits on that branch
                - When passing a full commit SHA, returns data starting from that specific commit
                  (the requested commit will be the first in the result list)
            per_page: Number of items per page
            merge_lf: Whether to merge LandingFlow data
            page: Page number for pagination

        Returns:
            Dictionary containing HUD data for the specified commit(s)
            
        Note:
            The API doesn't accept "HEAD" as a special value. To get the latest commit,
            use a branch name like "main" instead.
        """
        if page is None or page < 1:
            page = 1

        if per_page is None or per_page < 1:
            per_page = 20

        # Use the branch_or_commit_sha parameter directly in the endpoint
        endpoint = f"hud/{repo_owner}/{repo_name}/{branch_or_commit_sha}/{page}"

        params = {"per_page": per_page, "mergeLF": str(merge_lf).lower()}

        logger.info(f"Making HUD data request to {endpoint} with params {params}")
        return self._make_request(endpoint, params)

    def query_clickhouse(self, query_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a ClickHouse query by name with parameters.

        Args:
            query_name: Name of the ClickHouse query to run
            parameters: Query parameters

        Returns:
            Query results

        Note:
            The ClickHouse API is sensitive to parameters format. This method will
            automatically format the parameters as required by the API.
        """
        endpoint = f"clickhouse/{query_name}"
        params = {}

        if parameters is not None:
            # ClickHouse API requires JSON-encoded parameters
            params["parameters"] = json.dumps(parameters)

        return self._make_request(endpoint, params)

    def get_clickhouse_queries(self, use_cache: bool = True) -> List[str]:
        """Get a list of all available ClickHouse queries.

        This method attempts to discover all available ClickHouse queries by
        looking at the URL structure and testing query names.

        Args:
            use_cache: Whether to use cached results if available

        Returns:
            List of query names
        """
        if use_cache and self._clickhouse_queries_cache is not None:
            return self._clickhouse_queries_cache

        # Try to fetch from repo directory structure first
        try:
            # This is a basic implementation. The real implementation would
            # need to be more sophisticated to parse the directory structure.
            github_queries: List[str] = []
            url = "https://api.github.com/repos/pytorch/test-infra/contents/torchci/clickhouse_queries"
            response = requests.get(url)
            response.raise_for_status()

            for item in response.json():
                if item['type'] == 'dir':
                    github_queries.append(item['name'])

            if github_queries:
                self._clickhouse_queries_cache = github_queries
                return github_queries
        except Exception as e:
            logger.warning(f"Failed to fetch queries from GitHub: {e}")

        # Fallback to a hardcoded list based on known queries
        hardcoded_queries: List[str] = [
            "master_commit_red",
            "queued_jobs",
            "disabled_test_historical",
            "master_commit_red_percent",
            "master_commit_red_jobs",
            "nightly_jobs_red",
            "nightly_jobs_red_by_name",
            "commit_jobs_query",
            "commit_jobs_batch_query",
            "flaky_tests",
            "disabled_tests",
            "tts_avg",
            "tts_percentile",
            "ttrs_percentiles"
        ]

        self._clickhouse_queries_cache = hardcoded_queries
        return hardcoded_queries

    def get_clickhouse_query_parameters(self, query_name: str) -> Dict[str, Any]:
        """Get the expected parameters for a specific ClickHouse query.

        Args:
            query_name: Name of the query

        Returns:
            Dictionary of parameter names and example values
        """
        try:
            # Try to fetch from repo
            url = f"https://api.github.com/repos/pytorch/test-infra/contents/torchci/clickhouse_queries/{query_name}/params.json"
            response = requests.get(url)
            response.raise_for_status()

            # Get file contents (Base64 encoded)
            content = response.json()['content']
            decoded_content = base64.b64decode(content).decode('utf-8')
            return json.loads(decoded_content)
        except Exception as e:
            logger.warning(f"Failed to fetch parameters for query {query_name}: {e}")

            # Fallback to common parameters
            from datetime import datetime, timedelta
            now = datetime.now()
            return {
                "startTime": (now - timedelta(days=7)).isoformat(),
                "stopTime": now.isoformat(),
                "timezone": "America/Los_Angeles"
            }

    def get_artifacts(self, provider: str, job_id: str) -> Dict[str, Any]:
        """Get artifacts for a job.

        Args:
            provider: Artifact provider (e.g., 's3')
            job_id: Job ID
        """
        endpoint = f"artifacts/{provider}/{job_id}"
        return self._make_request(endpoint)

    def get_s3_log_url(self, job_id: str) -> str:
        """Get the S3 log URL for a job.

        Args:
            job_id: Job ID

        Returns:
            S3 log URL
        """
        return f"https://ossci-raw-job-status.s3.amazonaws.com/log/{job_id}"


    def find_commits_with_similar_failures(self, failure: str, 
                  repo: Optional[str] = None, 
                  workflow_name: Optional[str] = None,
                  branch_name: Optional[str] = None,
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None,
                  min_score: float = 1.0) -> Dict[str, Any]:
        """Find commits and jobs with similar failure text using the OpenSearch API.
        
        This is useful for investigating CI failures by finding historical jobs with similar
        error messages. It can help narrow down when a particular issue first appeared or
        identify patterns across different jobs and workflows.

        Args:
            failure: String containing the error or failure text to search for
            repo: Optional repository filter (e.g., "pytorch/pytorch")
            workflow_name: Optional filter for specific workflow
            branch_name: Optional filter for specific branch (like "main")
            start_date: ISO format date to begin search from (required by API, defaults to 7 days ago)
            end_date: ISO format date to end search at (required by API, defaults to now)
            min_score: Minimum relevance score for matches (defaults to 1.0)

        Returns:
            Dictionary with matching jobs and their commit details, containing:
            - matches: List of jobs with matching failure text
            - total_matches: Total number of matches found
            - total_lines: Total number of matching lines

        Note:
            Results are limited to the first 100 matching lines per job,
            and lines are truncated to 100 characters for brevity.
        """
        endpoint = "search"
        
        # Set default dates if not provided
        if not start_date or not end_date:
            from datetime import datetime, timedelta
            now = datetime.now()
            if not end_date:
                end_date = now.isoformat()
            if not start_date:
                start_date = (now - timedelta(days=7)).isoformat()
        
        params = {
            "failure": failure,
            "startDate": start_date,
            "endDate": end_date,
            "minScore": min_score
        }
        
        if repo:
            params["repo"] = repo
        if workflow_name:
            params["workflowName"] = workflow_name
        if branch_name:
            params["branchName"] = branch_name
            
        return self._make_request(endpoint, params)
        
    # Alias for backward compatibility
    search_logs = find_commits_with_similar_failures

    def download_log(self, job_id: str) -> str:
        """Download the full text log for a job.

        Args:
            job_id: The job ID

        Returns:
            The log content as a string

        Raises:
            PyTorchHudAPIError: If the log cannot be downloaded
        """
        url = f"https://ossci-raw-job-status.s3.amazonaws.com/log/{job_id}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download log for job {job_id}: {e}")
            raise PyTorchHudAPIError(f"Failed to download log for job {job_id}: {e}") from e

