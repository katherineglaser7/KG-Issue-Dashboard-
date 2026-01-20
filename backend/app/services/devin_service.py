"""
Devin API integration service for automated ticket execution.

This module handles real integration with the Devin API:
- Creates Devin sessions to work on GitHub issues
- Polls for session completion
- Retrieves PR information when Devin creates PRs
- All operations hit real Devin and GitHub APIs - no simulated data

API Reference: https://docs.devin.ai/api-reference/v1/sessions
"""

import asyncio
import httpx
from typing import Optional, Callable, Any
from app.config import Settings

cancelled_jobs: set[str] = set()

DEVIN_API_BASE = "https://api.devin.ai/v1"


class DevinService:
    """Service for real Devin API integration."""
    
    def __init__(self, settings: Settings):
        """
        Initialize with application settings.
        
        Args:
            settings: Application settings containing devin_api_key
        """
        self.settings = settings
        self.api_key = settings.devin_api_key
    
    def _get_headers(self) -> dict:
        """Get headers for Devin API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def mark_cancelled(self, job_id: str) -> None:
        """Mark a job as cancelled so execute_task will stop."""
        cancelled_jobs.add(job_id)
    
    def is_cancelled(self, job_id: str) -> bool:
        """Check if a job has been cancelled."""
        return job_id in cancelled_jobs
    
    def clear_cancelled(self, job_id: str) -> None:
        """Remove job from cancelled set."""
        cancelled_jobs.discard(job_id)
    
    def cleanup_worktree(self, issue_number: int) -> None:
        """
        Cleanup resources after ticket completion.

        For Devin API integration, this is a no-op since Devin manages
        its own session cleanup. This method exists for interface
        compatibility and future local worktree support.
        """
        pass
    
    async def create_session(
        self,
        prompt: str,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> dict:
        """
        Create a new Devin session.
        
        Args:
            prompt: The task prompt for Devin
            title: Optional custom title for the session
            tags: Optional list of tags
            
        Returns:
            Dict with session_id and url
            
        Raises:
            Exception: If API call fails
        """
        if not self.api_key:
            raise Exception("Devin API key not configured. Please set DEVIN_API_KEY in your .env file.")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "prompt": prompt,
                "unlisted": False,
            }
            if title:
                payload["title"] = title
            if tags:
                payload["tags"] = tags
            
            response = await client.post(
                f"{DEVIN_API_BASE}/sessions",
                headers=self._get_headers(),
                json=payload,
            )
            
            if response.status_code not in (200, 201):
                raise Exception(f"Failed to create Devin session: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def get_session(self, session_id: str) -> dict:
        """
        Get details about an existing Devin session.
        
        Args:
            session_id: The session ID to retrieve
            
        Returns:
            Dict with session details including status, pull_request, etc.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{DEVIN_API_BASE}/sessions/{session_id}",
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get Devin session: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a Devin session.
        
        Args:
            session_id: The session ID to terminate
            
        Returns:
            True if terminated successfully
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{DEVIN_API_BASE}/sessions/{session_id}",
                headers=self._get_headers(),
            )
            
            return response.status_code in (200, 204)
    
    async def execute_task(
        self,
        job_id: str,
        ticket_number: int,
        ticket_data: dict,
        progress_callback: Callable[..., Any],
        completion_callback: Callable[..., Any],
        worktree_callback: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Execute a task using the real Devin API.
        
        This method:
        1. Creates a Devin session with a prompt to fix the issue
        2. Polls for session completion
        3. Retrieves PR information when Devin creates a PR
        
        All operations hit real Devin and GitHub APIs - no simulated data.
        
        Args:
            job_id: The job ID to track
            ticket_number: The ticket/issue number
            ticket_data: Dict containing ticket title, body, repo, etc.
            progress_callback: Function to call with progress updates
            completion_callback: Function to call when complete
            worktree_callback: Optional callback for session info
        """
        if not self.api_key:
            await progress_callback(
                job_id=job_id,
                status="failed",
                current_step="Error",
                steps_completed=0,
                error_message="Devin API key not configured. Please set DEVIN_API_KEY in .env file."
            )
            return
        
        ticket_title = ticket_data.get("title", f"Issue #{ticket_number}")
        ticket_body = ticket_data.get("body", "")
        repo = ticket_data.get("repo", self.settings.github_repo)
        
        prompt = f"""Please fix the following GitHub issue in the repository {repo}:

Issue #{ticket_number}: {ticket_title}

{ticket_body}

Instructions:
1. Clone the repository {repo}
2. Analyze the issue and understand what needs to be fixed
3. Implement the fix with proper code changes
4. Create a pull request with your changes
5. Make sure the PR description references issue #{ticket_number}

Please create a PR when you're done."""

        session_id = None
        session_url = None
        
        try:
            await progress_callback(
                job_id=job_id,
                status="running",
                current_step="Creating Devin session...",
                steps_completed=0
            )
            
            if self.is_cancelled(job_id):
                self.clear_cancelled(job_id)
                return
            
            session_response = await self.create_session(
                prompt=prompt,
                title=f"Fix issue #{ticket_number}: {ticket_title[:50]}",
                tags=[f"issue-{ticket_number}", repo],
            )
            
            session_id = session_response.get("session_id")
            session_url = session_response.get("url")
            
            if worktree_callback:
                await worktree_callback(
                    job_id=job_id,
                    worktree_path=session_url,
                    branch_name=f"devin/issue-{ticket_number}",
                )
            
            await progress_callback(
                job_id=job_id,
                status="running",
                current_step="Devin is analyzing the codebase...",
                steps_completed=1
            )
            
            max_poll_time = 3600
            poll_interval = 30
            elapsed = 0
            pr_url = None
            pr_number = None
            
            while elapsed < max_poll_time:
                if self.is_cancelled(job_id):
                    self.clear_cancelled(job_id)
                    if session_id:
                        await self.terminate_session(session_id)
                    return
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                try:
                    session_details = await self.get_session(session_id)
                except Exception:
                    continue
                
                status_enum = session_details.get("status_enum", "")
                
                if status_enum == "working":
                    step_num = min(1 + (elapsed // 60), 3)
                    step_messages = [
                        "Devin is analyzing the codebase...",
                        "Devin is implementing the solution...",
                        "Devin is testing and creating PR...",
                    ]
                    await progress_callback(
                        job_id=job_id,
                        status="running",
                        current_step=step_messages[min(step_num - 1, 2)],
                        steps_completed=step_num
                    )
                
                elif status_enum == "blocked":
                    await progress_callback(
                        job_id=job_id,
                        status="running",
                        current_step=f"Devin needs assistance - check {session_url}",
                        steps_completed=2
                    )
                
                elif status_enum == "finished":
                    pull_request = session_details.get("pull_request")
                    if pull_request:
                        pr_url = pull_request.get("url")
                        if pr_url:
                            parts = pr_url.rstrip("/").split("/")
                            try:
                                pr_number = int(parts[-1])
                            except (ValueError, IndexError):
                                pr_number = None
                    break
                
                elif status_enum in ("expired", "suspend_requested"):
                    raise Exception(f"Devin session ended unexpectedly: {status_enum}")
            
            if elapsed >= max_poll_time:
                raise Exception("Devin session timed out after 1 hour")
            
            await completion_callback(
                job_id=job_id,
                ticket_number=ticket_number,
                pr_number=pr_number,
                pr_url=pr_url,
                branch_name=f"devin/issue-{ticket_number}" if session_id else None,
                session_id=session_id,
                session_url=session_url,
            )
            
        except Exception as e:
            await progress_callback(
                job_id=job_id,
                status="failed",
                current_step="Error",
                steps_completed=0,
                error_message=str(e)
            )


def get_devin_service(settings: Settings) -> DevinService:
    """Factory function for dependency injection."""
    return DevinService(settings)
