"""
Job API endpoints.

This module handles all /api/jobs/* routes for managing async job operations.
Jobs track the progress of automated ticket processing (e.g., Devin sessions).

Current endpoints are placeholders - implement when Devin integration is ready.

To implement job endpoints:
1. Add database operations via JobRepository
2. Integrate with DevinService for session management
3. Add webhook handlers for status updates
"""

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.schemas.models import Job, JobCreateRequest, JobResponse
from app.database.repositories import job_repository, ticket_repository
from app.services.devin_service import get_devin_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse)
async def create_job(
    request: JobCreateRequest,
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    """
    Create a new job for a ticket.
    
    This will eventually trigger a Devin session to work on the ticket.
    Currently creates a job record in pending status.
    """
    ticket = ticket_repository.get_by_id(request.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    job = job_repository.create(request.ticket_id)
    
    return JobResponse(
        id=job.id,
        ticket_id=job.ticket_id,
        status=job.status,
        current_step=job.current_step,
        steps_completed=job.steps_completed,
        total_steps=job.total_steps,
        error_message=job.error_message,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    """
    Get the current status of a job.
    """
    job = job_repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(
        id=job.id,
        ticket_id=job.ticket_id,
        status=job.status,
        current_step=job.current_step,
        steps_completed=job.steps_completed,
        total_steps=job.total_steps,
        error_message=job.error_message,
    )


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Cancel a running job.
    
    This will eventually cancel the associated Devin session.
    """
    job = job_repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Job already {job.status}")
    
    job_repository.update_status(job_id, "cancelled")
    
    return {"status": "cancelled", "job_id": job_id}


@router.post("/{job_id}/cleanup")
async def cleanup_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Manually trigger worktree cleanup for a completed/failed job.
    
    Useful if automatic cleanup failed or for manual cleanup.
    """
    job = job_repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail="Can only cleanup completed, failed, or cancelled jobs"
        )
    
    ticket = ticket_repository.get_by_id(job.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Associated ticket not found")
    
    devin_service = get_devin_service(settings)
    devin_service.cleanup_worktree(ticket.issue_number)
    
    return {"status": "cleaned", "job_id": job_id, "message": "Worktree cleaned up"}
