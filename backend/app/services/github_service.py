"""
GitHub API service for all GitHub interactions.

This module encapsulates all GitHub API calls. Routes should never call
the GitHub API directly - they should use this service.

To swap GitHub for GitLab or another provider:
1. Create a new service class implementing the same interface
2. Update the dependency injection in routers to use the new service
3. No changes needed to routes or other services

Design decisions:
- Uses httpx for async HTTP requests
- Raises HTTPException for API errors (caught by FastAPI)
- Returns raw dict from GitHub API (caller transforms to domain models)
"""

from typing import Optional
import httpx
from fastapi import HTTPException

from app.config import Settings


class GitHubService:
    """Service for interacting with the GitHub API."""
    
    def __init__(self, settings: Settings):
        """
        Initialize with application settings.
        
        Args:
            settings: Application settings containing github_token and github_repo
        """
        self.settings = settings
        self.base_url = "https://api.github.com"
        self.repo = settings.github_repo
    
    def _get_headers(self) -> dict[str, str]:
        """Build headers for GitHub API requests."""
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers
    
    async def get_issues(self, state: str = "all") -> list[dict]:
        """
        Fetch issues from the repository.
        
        Args:
            state: Issue state filter - "open", "closed", or "all"
        
        Returns:
            List of issue dictionaries from GitHub API
        
        Raises:
            HTTPException: If GitHub API returns an error
        """
        async with httpx.AsyncClient() as client:
            if state == "all":
                open_response = await client.get(
                    f"{self.base_url}/repos/{self.repo}/issues",
                    headers=self._get_headers(),
                    params={"state": "open", "per_page": 100}
                )
                closed_response = await client.get(
                    f"{self.base_url}/repos/{self.repo}/issues",
                    headers=self._get_headers(),
                    params={"state": "closed", "per_page": 100}
                )
                
                if open_response.status_code != 200:
                    raise HTTPException(
                        status_code=open_response.status_code,
                        detail=f"GitHub API error: {open_response.text}"
                    )
                
                return open_response.json() + closed_response.json()
            else:
                response = await client.get(
                    f"{self.base_url}/repos/{self.repo}/issues",
                    headers=self._get_headers(),
                    params={"state": state, "per_page": 100}
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"GitHub API error: {response.text}"
                    )
                
                return response.json()
    
    async def get_issue(self, issue_number: int) -> dict:
        """
        Fetch a single issue by number.
        
        Args:
            issue_number: The issue number to fetch
        
        Returns:
            Issue dictionary from GitHub API
        
        Raises:
            HTTPException: If issue not found or API error
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{self.repo}/issues/{issue_number}",
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}"
                )
            
            return response.json()
    
    async def add_label(self, issue_number: int, label: str) -> None:
        """
        Add a label to an issue.
        
        Args:
            issue_number: The issue number
            label: Label name to add
        
        Raises:
            HTTPException: If API error occurs
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/repos/{self.repo}/issues/{issue_number}/labels",
                headers=self._get_headers(),
                json={"labels": [label]}
            )
            
            if response.status_code not in (200, 201):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}"
                )
    
    async def remove_label(self, issue_number: int, label: str) -> None:
        """
        Remove a label from an issue.
        
        Args:
            issue_number: The issue number
            label: Label name to remove
        
        Raises:
            HTTPException: If API error occurs (404 is ignored - label may not exist)
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/repos/{self.repo}/issues/{issue_number}/labels/{label}",
                headers=self._get_headers()
            )
            
            if response.status_code not in (200, 204, 404):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}"
                )
    
    async def close_issue(self, issue_number: int) -> None:
        """
        Close an issue.
        
        Args:
            issue_number: The issue number to close
        
        Raises:
            HTTPException: If API error occurs
        """
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/repos/{self.repo}/issues/{issue_number}",
                headers=self._get_headers(),
                json={"state": "closed"}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}"
                )
    
    async def get_pull_requests_for_issue(self, issue_number: int) -> list[dict]:
        """
        Get pull requests that reference an issue.
        
        This searches for PRs that mention the issue number in their body or title.
        Note: This is a heuristic - GitHub doesn't have a direct API for this.
        
        Args:
            issue_number: The issue number to find PRs for
        
        Returns:
            List of PR dictionaries that reference the issue
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{self.repo}/pulls",
                headers=self._get_headers(),
                params={"state": "all", "per_page": 100}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}"
                )
            
            prs = response.json()
            issue_ref = f"#{issue_number}"
            return [
                pr for pr in prs
                if issue_ref in (pr.get("title", "") + (pr.get("body") or ""))
            ]


def get_github_service(settings: Settings) -> GitHubService:
    """Factory function for dependency injection."""
    return GitHubService(settings)
