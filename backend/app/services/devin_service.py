"""
Devin integration service (stub implementation).

This module will handle integration with the Devin API for automated
ticket processing. Currently provides a simulation for development/testing.

To implement real Devin integration:
1. Add devin_api_key to Settings and .env
2. Replace simulation methods with actual API calls
3. Update job status handling based on Devin webhook responses

The service follows the same pattern as other services:
- Takes Settings in __init__ for configuration
- Provides async methods for API operations
- Returns structured responses for the caller

Git worktree support:
- Each ticket execution gets its own worktree for isolation
- Worktrees are created at ./worktrees/issue-{number}/
- Branches are named devin/issue-{number}
- This allows parallel execution of multiple tickets
"""

import asyncio
import subprocess
import os
from pathlib import Path
from typing import Optional, Callable, Any
from app.config import Settings
from app.schemas.models import Job

cancelled_jobs: set[str] = set()
WORKTREES_DIR = "./worktrees"


class DevinService:
    """Service for Devin API integration (stub with simulation)."""
    
    def __init__(self, settings: Settings):
        """
        Initialize with application settings.
        
        Args:
            settings: Application settings containing devin_api_key
        """
        self.settings = settings
        self.api_key = settings.devin_api_key
    
    def mark_cancelled(self, job_id: str) -> None:
        """Mark a job as cancelled so execute_task will stop."""
        cancelled_jobs.add(job_id)
    
    def is_cancelled(self, job_id: str) -> bool:
        """Check if a job has been cancelled."""
        return job_id in cancelled_jobs
    
    def clear_cancelled(self, job_id: str) -> None:
        """Remove job from cancelled set."""
        cancelled_jobs.discard(job_id)
    
    def create_worktree(self, issue_number: int) -> tuple[str, str]:
        """
        Create a git worktree for isolated ticket execution.
        
        Args:
            issue_number: The issue number to create worktree for
            
        Returns:
            Tuple of (worktree_path, branch_name)
            
        Raises:
            RuntimeError: If worktree creation fails
        """
        worktree_path = f"{WORKTREES_DIR}/issue-{issue_number}"
        branch_name = f"devin/issue-{issue_number}"
        
        try:
            Path(WORKTREES_DIR).mkdir(parents=True, exist_ok=True)
            
            if Path(worktree_path).exists():
                self.cleanup_worktree(issue_number)
            
            result = subprocess.run(
                ["git", "worktree", "add", worktree_path, "-b", branch_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                if "already exists" in result.stderr:
                    result = subprocess.run(
                        ["git", "worktree", "add", worktree_path, branch_name],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        raise RuntimeError(f"Failed to create worktree: {result.stderr}")
                else:
                    raise RuntimeError(f"Failed to create worktree: {result.stderr}")
            
            return worktree_path, branch_name
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Worktree creation timed out")
        except FileNotFoundError:
            return worktree_path, branch_name
    
    def cleanup_worktree(self, issue_number: int) -> None:
        """
        Clean up a git worktree and its branch.
        
        Args:
            issue_number: The issue number to clean up
        """
        worktree_path = f"{WORKTREES_DIR}/issue-{issue_number}"
        branch_name = f"devin/issue-{issue_number}"
        
        try:
            subprocess.run(
                ["git", "worktree", "remove", worktree_path, "--force"],
                capture_output=True,
                text=True,
                timeout=30
            )
        except Exception:
            pass
        
        try:
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                capture_output=True,
                text=True,
                timeout=30
            )
        except Exception:
            pass
        
        try:
            if Path(worktree_path).exists():
                import shutil
                shutil.rmtree(worktree_path, ignore_errors=True)
        except Exception:
            pass
    
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
        Execute a task simulation with step-by-step progress.
        
        This method simulates the steps a real Devin session would go through:
        - Step 0: Create worktree for isolated execution
        - Step 1 (2 sec): Analyzing codebase
        - Step 2 (3 sec): Implementing solution
        - Step 3 (2 sec): Running tests
        - Step 4 (1 sec): Creating pull request
        
        Args:
            job_id: The job ID to track
            ticket_number: The ticket/issue number
            ticket_data: Dict containing ticket title, body, etc.
            progress_callback: Function to call with progress updates
            completion_callback: Function to call when complete
            worktree_callback: Function to call with worktree info after creation
        """
        worktree_path = None
        branch_name = f"devin/issue-{ticket_number}"
        
        try:
            try:
                worktree_path, branch_name = self.create_worktree(ticket_number)
                if worktree_callback:
                    await worktree_callback(
                        job_id=job_id,
                        worktree_path=worktree_path,
                        branch_name=branch_name,
                    )
            except RuntimeError as e:
                pass
            
            steps = [
                (2, "Analyzing codebase..."),
                (3, "Implementing solution..."),
                (2, "Running tests..."),
                (1, "Creating pull request..."),
            ]
            
            for i, (duration, step_name) in enumerate(steps):
                if self.is_cancelled(job_id):
                    self.clear_cancelled(job_id)
                    self.cleanup_worktree(ticket_number)
                    return
                
                await progress_callback(
                    job_id=job_id,
                    status="running",
                    current_step=step_name,
                    steps_completed=i
                )
                
                await asyncio.sleep(duration)
            
            if self.is_cancelled(job_id):
                self.clear_cancelled(job_id)
                self.cleanup_worktree(ticket_number)
                return
            
            mock_pr_number = ticket_number + 100
            mock_pr_url = f"https://github.com/{self.settings.github_repo}/pull/{mock_pr_number}"
            
            await completion_callback(
                job_id=job_id,
                ticket_number=ticket_number,
                pr_number=mock_pr_number,
                pr_url=mock_pr_url,
                branch_name=branch_name,
            )
            
        except Exception as e:
            self.cleanup_worktree(ticket_number)
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
