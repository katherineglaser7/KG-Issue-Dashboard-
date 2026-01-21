"""
Ticket API endpoints.

This module handles all /api/tickets/* routes. Routes are thin - they only
handle HTTP concerns and delegate business logic to services.

Route responsibilities:
- Parse and validate request data
- Call appropriate service methods
- Return properly typed responses

To add new ticket endpoints:
1. Add the route function with appropriate decorators
2. Use Depends() for service injection
3. Define response_model for type safety
"""

import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from app.config import Settings, get_settings
from app.schemas.models import Ticket, TicketListResponse, ScopeResponse, JobResponse
from app.services.github_service import GitHubService, get_github_service
from app.services.scoring_service import ScoringService, get_scoring_service
from app.services.devin_service import DevinService, get_devin_service
from app.database.repositories import ticket_repository, job_repository
from app.database.connection import get_connection

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _determine_status(issue: dict) -> str:
    """
    Determine ticket status based on labels and state.
    
    This helper maps GitHub issue state/labels to our internal status values.
    """
    labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
    state = issue.get("state", "open")
    
    if state == "closed":
        return "done"
    
    if "in progress" in labels or "in-progress" in labels or "wip" in labels:
        return "in_progress"
    
    if "done" in labels or "completed" in labels:
        return "done"
    
    return "todo"


def _issue_to_ticket(issue: dict, db_ticket=None, job=None) -> Ticket:
    """Convert a GitHub issue dict to a Ticket model.
    
    Status logic:
    1. If we have a db_ticket with a tracked status, use that
    2. Otherwise, issue is "new" (must be scoped through dashboard first)
    
    Note: We only show issues as "scoped" if they were processed through our
    dashboard's scope endpoint, not based on GitHub labels. This ensures
    the Action button only works for tickets that have been properly analyzed.
    """
    if db_ticket and db_ticket.status in ("scoped", "in_progress", "review", "complete"):
        status = db_ticket.status
    else:
        status = "new"
    
    analysis = None
    if db_ticket and db_ticket.scope_data:
        try:
            analysis = json.loads(db_ticket.scope_data)
        except (json.JSONDecodeError, TypeError):
            pass
    
    job_response = None
    if job:
        job_response = JobResponse(
            id=job.id,
            ticket_id=job.ticket_id,
            status=job.status,
            current_step=job.current_step,
            steps_completed=job.steps_completed,
            total_steps=job.total_steps,
            error_message=job.error_message,
            worktree_path=job.worktree_path,
            branch_name=job.branch_name,
        )
    
    branch_name = None
    if db_ticket and db_ticket.status in ("in_progress", "review", "complete"):
        branch_name = f"devin/issue-{issue['number']}"
    
    return Ticket(
        id=issue["id"],
        number=issue["number"],
        title=issue["title"],
        body=issue.get("body"),
        status=status,
        labels=[label["name"] for label in issue.get("labels", [])],
        created_at=issue["created_at"],
        updated_at=issue["updated_at"],
        html_url=issue["html_url"],
        confidence_score=analysis.get("confidence_score") if analysis else None,
        analysis=analysis,
        pr_number=db_ticket.pr_number if db_ticket else None,
        pr_url=db_ticket.pr_url if db_ticket else None,
        branch_name=branch_name,
        job=job_response,
    )


@router.get("", response_model=TicketListResponse)
async def get_tickets(
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> TicketListResponse:
    """
    Fetch all tickets from GitHub, merged with database state.
    
    Args:
        repo: Optional repo override (format: owner/repo). If not provided, uses default from settings.
    
    Returns both open and closed issues as tickets, excluding pull requests.
    Database status (scoped, in_progress, review) takes precedence over GitHub labels.
    For in_progress tickets, includes the latest job data.
    """
    target_repo = repo or settings.github_repo
    github_service = get_github_service(settings, repo=target_repo)
    issues = await github_service.get_issues(state="all")
    
    db_tickets = ticket_repository.get_all(repo=target_repo)
    db_tickets_by_number = {t.issue_number: t for t in db_tickets}
    
    tickets = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        
        db_ticket = db_tickets_by_number.get(issue["number"])
        job = None
        
        if db_ticket and db_ticket.status == "in_progress":
            job = job_repository.get_latest_for_ticket(db_ticket.id)
        
        tickets.append(_issue_to_ticket(issue, db_ticket, job))
    
    return TicketListResponse(tickets=tickets)


@router.get("/{ticket_number}/scope", response_model=ScopeResponse)
async def scope_ticket(
    ticket_number: int,
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> ScopeResponse:
    """
    Analyze a ticket and return full analysis with confidence score.
    
    Args:
        ticket_number: The issue number to scope
        repo: Optional repo override (format: owner/repo)
    
    Fetches the issue from GitHub, performs analysis (root issue, action plan,
    confidence score), stores the analysis in the database, and sets status to "scoped".
    """
    target_repo = repo or settings.github_repo
    github_service = get_github_service(settings, repo=target_repo)
    scoring_service = get_scoring_service(settings)
    
    issue = await github_service.get_issue(ticket_number)
    analysis = scoring_service.analyze_ticket(issue)
    
    ticket_repository.create_or_update(
        repo=target_repo,
        issue_number=ticket_number,
    )
    ticket_repository.update_scope_data(
        repo=target_repo,
        issue_number=ticket_number,
        scope_data=analysis.model_dump_json(),
    )
    ticket_repository.update_status(
        repo=target_repo,
        issue_number=ticket_number,
        status="scoped",
    )
    
    return ScopeResponse(
        ticket_number=ticket_number,
        title=issue["title"],
        analysis=analysis,
    )


async def _update_job_progress(
    job_id: str,
    status: str,
    current_step: str,
    steps_completed: int,
    error_message: str | None = None,
) -> None:
    """Callback to update job progress in database."""
    job_repository.update_status(
        job_id=job_id,
        status=status,
        current_step=current_step,
        steps_completed=steps_completed,
        error_message=error_message,
    )


async def _complete_job(
    job_id: str,
    ticket_number: int,
    pr_number: int,
    pr_url: str,
    branch_name: str,
    settings: Settings,
    target_repo: str | None = None,
) -> None:
    """Callback when job completes successfully."""
    repo = target_repo or settings.github_repo
    job_repository.update_status(
        job_id=job_id,
        status="completed",
        current_step="Complete",
        steps_completed=4,
    )
    
    ticket_repository.update_status(
        repo=repo,
        issue_number=ticket_number,
        status="review",
    )
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tickets SET pr_number = ?, pr_url = ?, updated_at = CURRENT_TIMESTAMP WHERE repo = ? AND issue_number = ?",
            (pr_number, pr_url, repo, ticket_number)
        )
    
    github_service = get_github_service(settings, repo=repo)
    try:
        await github_service.remove_label(ticket_number, "in-progress")
    except Exception:
        pass
    try:
        await github_service.add_label(ticket_number, "review")
    except Exception:
        pass


async def _update_worktree_info(
    job_id: str,
    worktree_path: str,
    branch_name: str,
) -> None:
    """Callback to update job with worktree information."""
    job_repository.update_worktree_info(
        job_id=job_id,
        worktree_path=worktree_path,
        branch_name=branch_name,
    )


@router.post("/{ticket_number}/execute")
async def execute_ticket(
    ticket_number: int,
    background_tasks: BackgroundTasks,
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Start execution of a scoped ticket.
    
    Args:
        ticket_number: The issue number to execute
        repo: Optional repo override (format: owner/repo)
    
    Creates a job, updates ticket status to in_progress, and starts
    background execution task with real GitHub data.
    """
    if not settings.devin_api_key:
        raise HTTPException(
            status_code=400,
            detail="DEVIN_API_KEY is not configured. Please set the DEVIN_API_KEY environment variable to enable automated execution."
        )
    
    target_repo = repo or settings.github_repo
    ticket = ticket_repository.get_by_repo_and_number(
        repo=target_repo,
        issue_number=ticket_number,
    )
    
    if not ticket or ticket.status != "scoped":
        raise HTTPException(
            status_code=400,
            detail="Ticket must be in 'scoped' status to execute"
        )
    
    github_service = get_github_service(settings, repo=target_repo)
    issue = await github_service.get_issue(ticket_number)
    
    job = job_repository.create(ticket_id=ticket.id, total_steps=4)
    
    ticket_repository.update_status(
        repo=target_repo,
        issue_number=ticket_number,
        status="in_progress",
    )
    
    try:
        await github_service.add_label(ticket_number, "in-progress")
    except Exception:
        pass
    
    devin_service = get_devin_service(settings)
    
    async def progress_callback_with_failure_handling(
        job_id: str,
        status: str,
        current_step: str,
        steps_completed: int,
        error_message: str | None = None,
    ) -> None:
        """Callback that updates job progress and resets ticket on failure."""
        await _update_job_progress(
            job_id=job_id,
            status=status,
            current_step=current_step,
            steps_completed=steps_completed,
            error_message=error_message,
        )
        if status == "failed":
            ticket_repository.update_status(
                repo=target_repo,
                issue_number=ticket_number,
                status="scoped",
            )
            github_service = get_github_service(settings, repo=target_repo)
            try:
                await github_service.remove_label(ticket_number, "in-progress")
            except Exception:
                pass
    
    async def run_execution():
        await devin_service.execute_task(
            job_id=job.id,
            ticket_number=ticket_number,
            ticket_data={
                "title": issue.get("title", f"Issue #{ticket_number}"),
                "body": issue.get("body", ""),
                "repo": target_repo,
            },
            progress_callback=progress_callback_with_failure_handling,
            completion_callback=lambda **kwargs: _complete_job(**kwargs, settings=settings, target_repo=target_repo),
            worktree_callback=_update_worktree_info,
        )
    
    asyncio.create_task(run_execution())
    
    return {"job_id": job.id, "status": "started", "branch_name": f"devin/issue-{ticket_number}"}


@router.get("/{ticket_number}/job", response_model=JobResponse)
async def get_ticket_job(
    ticket_number: int,
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    """
    Get the latest job for a ticket.
    
    Args:
        ticket_number: The issue number
        repo: Optional repo override (format: owner/repo)
    """
    target_repo = repo or settings.github_repo
    ticket = ticket_repository.get_by_repo_and_number(
        repo=target_repo,
        issue_number=ticket_number,
    )
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    job = job_repository.get_latest_for_ticket(ticket.id)
    
    if not job:
        raise HTTPException(status_code=404, detail="No job found for this ticket")
    
    return JobResponse(
        id=job.id,
        ticket_id=job.ticket_id,
        status=job.status,
        current_step=job.current_step,
        steps_completed=job.steps_completed,
        total_steps=job.total_steps,
        error_message=job.error_message,
        worktree_path=job.worktree_path,
        branch_name=job.branch_name,
    )


@router.post("/{ticket_number}/cancel")
async def cancel_ticket_job(
    ticket_number: int,
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Cancel a running or failed job for a ticket.
    
    Args:
        ticket_number: The issue number
        repo: Optional repo override (format: owner/repo)
    
    Resets the ticket status back to 'scoped' so the user can try again.
    Works for both running jobs (cancels them) and failed jobs (resets status).
    """
    target_repo = repo or settings.github_repo
    ticket = ticket_repository.get_by_repo_and_number(
        repo=target_repo,
        issue_number=ticket_number,
    )
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    job = job_repository.get_latest_for_ticket(ticket.id)
    
    if not job or job.status not in ("running", "failed"):
        raise HTTPException(status_code=400, detail="No running or failed job to cancel")
    
    if job.status == "running":
        devin_service = get_devin_service(settings)
        devin_service.mark_cancelled(job.id)
        
        job_repository.update_status(
            job_id=job.id,
            status="failed",
            error_message="Cancelled by user",
        )
    
    ticket_repository.update_status(
        repo=target_repo,
        issue_number=ticket_number,
        status="scoped",
    )
    
    github_service = get_github_service(settings, repo=target_repo)
    try:
        await github_service.remove_label(ticket_number, "in-progress")
    except Exception:
        pass
    
    return {"status": "cancelled"}


@router.get("/{ticket_number}/pr")
async def get_ticket_pr(
    ticket_number: int,
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get PR information for a ticket.
    
    Args:
        ticket_number: The issue number
        repo: Optional repo override (format: owner/repo)
    
    Fetches real PR data from GitHub API - no simulated data.
    """
    target_repo = repo or settings.github_repo
    ticket = ticket_repository.get_by_repo_and_number(
        repo=target_repo,
        issue_number=ticket_number,
    )
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if not ticket.pr_number:
        raise HTTPException(status_code=404, detail="No PR associated with this ticket")
    
    github_service = get_github_service(settings, repo=target_repo)
    
    try:
        pr_data = await github_service.get_pull_request(ticket.pr_number)
        pr_files = await github_service.get_pull_request_files(ticket.pr_number)
    except HTTPException:
        raise HTTPException(status_code=404, detail="PR not found on GitHub")
    
    root_issue = "Issue description"
    if ticket.scope_data:
        try:
            scope = json.loads(ticket.scope_data)
            root_issue = scope.get("root_issue", "Issue description")
        except (json.JSONDecodeError, TypeError):
            pass
    
    files_changed = [
        {
            "filename": f.get("filename", "unknown"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
        }
        for f in pr_files[:10]
    ]
    
    return {
        "pr_number": pr_data.get("number"),
        "pr_url": pr_data.get("html_url"),
        "pr_state": pr_data.get("state", "open"),
        "title": pr_data.get("title", f"Fix: Issue #{ticket_number}"),
        "branch_name": pr_data.get("head", {}).get("ref", f"devin/issue-{ticket_number}"),
        "summary": {
            "problem": root_issue[:80] if len(root_issue) > 80 else root_issue,
            "solution": pr_data.get("body", "")[:200] if pr_data.get("body") else f"Implemented fix for issue #{ticket_number}",
            "files_changed": files_changed
        }
    }


@router.post("/{ticket_number}/complete")
async def complete_ticket(
    ticket_number: int,
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Mark a ticket as complete.
    
    Args:
        ticket_number: The issue number
        repo: Optional repo override (format: owner/repo)
    
    Updates ticket status to complete, adds implemented label, and triggers cleanup.
    """
    target_repo = repo or settings.github_repo
    ticket = ticket_repository.get_by_repo_and_number(
        repo=target_repo,
        issue_number=ticket_number,
    )
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.status != "review":
        raise HTTPException(
            status_code=400,
            detail="Ticket must be in 'review' status to mark complete"
        )
    
    ticket_repository.update_status(
        repo=target_repo,
        issue_number=ticket_number,
        status="complete",
    )
    
    github_service = get_github_service(settings, repo=target_repo)
    try:
        await github_service.remove_label(ticket_number, "review")
    except Exception:
        pass
    try:
        await github_service.add_label(ticket_number, "implemented")
    except Exception:
        pass
    
    devin_service = get_devin_service(settings)
    devin_service.cleanup_worktree(ticket_number)
    
    return {"status": "complete", "message": "Ticket marked complete"}
