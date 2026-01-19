"""
Database repository layer for CRUD operations.

This module provides all database operations for tickets and jobs.
Repositories abstract the database implementation from the service layer.

To add new operations:
1. Add the method to the appropriate repository class
2. Use get_connection() context manager for all database access
3. Return domain models, not raw database rows

Design decisions:
- Each repository handles one table/entity
- Methods return None for not-found cases (caller decides if that's an error)
- JSON serialization for complex fields (scope_data)
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from app.database.connection import get_connection
from app.schemas.models import TicketDB, Job


class TicketRepository:
    """Repository for ticket CRUD operations."""
    
    def create_or_update(self, repo: str, issue_number: int, status: str = "new",
                         scope_data: Optional[str] = None, pr_number: Optional[int] = None,
                         pr_url: Optional[str] = None) -> TicketDB:
        """
        Create a new ticket or update if exists (upsert by repo + issue_number).
        
        Returns the created/updated ticket with its database ID.
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tickets (repo, issue_number, status, scope_data, pr_number, pr_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(repo, issue_number) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, status, scope_data, pr_number, pr_url, created_at, updated_at
            """, (repo, issue_number, status, scope_data, pr_number, pr_url))
            row = cursor.fetchone()
            return TicketDB(
                id=row["id"],
                repo=repo,
                issue_number=issue_number,
                status=row["status"],
                scope_data=row["scope_data"],
                pr_number=row["pr_number"],
                pr_url=row["pr_url"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
    
    def get_by_id(self, ticket_id: int) -> Optional[TicketDB]:
        """Get a ticket by its database ID."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            row = cursor.fetchone()
            if row:
                return TicketDB(**dict(row))
            return None
    
    def get_by_repo_and_number(self, repo: str, issue_number: int) -> Optional[TicketDB]:
        """Get a ticket by repository and issue number."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tickets WHERE repo = ? AND issue_number = ?",
                (repo, issue_number)
            )
            row = cursor.fetchone()
            if row:
                return TicketDB(**dict(row))
            return None
    
    def get_all(self, repo: Optional[str] = None) -> list[TicketDB]:
        """Get all tickets, optionally filtered by repository."""
        with get_connection() as conn:
            cursor = conn.cursor()
            if repo:
                cursor.execute("SELECT * FROM tickets WHERE repo = ?", (repo,))
            else:
                cursor.execute("SELECT * FROM tickets")
            return [TicketDB(**dict(row)) for row in cursor.fetchall()]
    
    def update_status(self, repo: str, issue_number: int, status: str) -> bool:
        """Update a ticket's status by repo and issue number. Returns True if updated."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE repo = ? AND issue_number = ?",
                (status, repo, issue_number)
            )
            return cursor.rowcount > 0
    
    def update_scope_data(self, repo: str, issue_number: int, scope_data: str) -> bool:
        """Update a ticket's scope data (stored as JSON string). Returns True if updated."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tickets SET scope_data = ?, updated_at = CURRENT_TIMESTAMP WHERE repo = ? AND issue_number = ?",
                (scope_data, repo, issue_number)
            )
            return cursor.rowcount > 0


class JobRepository:
    """Repository for job CRUD operations."""
    
    def create(self, ticket_id: int, total_steps: int = 4) -> Job:
        """Create a new job for a ticket with running status."""
        job_id = str(uuid.uuid4())
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO jobs (id, ticket_id, status, total_steps, started_at)
                VALUES (?, ?, 'running', ?, CURRENT_TIMESTAMP)
            """, (job_id, ticket_id, total_steps))
            return Job(id=job_id, ticket_id=ticket_id, status="running", total_steps=total_steps)
    
    def get_by_id(self, job_id: str) -> Optional[Job]:
        """Get a job by its ID."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return Job(**dict(row))
            return None
    
    def get_by_ticket_id(self, ticket_id: int) -> list[Job]:
        """Get all jobs for a ticket."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE ticket_id = ?", (ticket_id,))
            return [Job(**dict(row)) for row in cursor.fetchall()]
    
    def get_latest_for_ticket(self, ticket_id: int) -> Optional[Job]:
        """Get the most recent job for a ticket."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM jobs WHERE ticket_id = ? ORDER BY started_at DESC LIMIT 1",
                (ticket_id,)
            )
            row = cursor.fetchone()
            if row:
                return Job(**dict(row))
            return None
    
    def update_status(self, job_id: str, status: str, current_step: Optional[str] = None,
                      steps_completed: Optional[int] = None, error_message: Optional[str] = None) -> bool:
        """Update job status and progress."""
        with get_connection() as conn:
            cursor = conn.cursor()
            updates = ["status = ?"]
            params = [status]
            
            if current_step is not None:
                updates.append("current_step = ?")
                params.append(current_step)
            if steps_completed is not None:
                updates.append("steps_completed = ?")
                params.append(steps_completed)
            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)
            if status in ("completed", "failed"):
                updates.append("completed_at = CURRENT_TIMESTAMP")
            
            params.append(job_id)
            cursor.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", params)
            return cursor.rowcount > 0
    
    def update_worktree_info(self, job_id: str, worktree_path: str, branch_name: str) -> bool:
        """Update job with worktree information."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE jobs SET worktree_path = ?, branch_name = ? WHERE id = ?",
                (worktree_path, branch_name, job_id)
            )
            return cursor.rowcount > 0


ticket_repository = TicketRepository()
job_repository = JobRepository()
