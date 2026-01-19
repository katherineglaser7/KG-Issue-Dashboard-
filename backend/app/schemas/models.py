"""
Pydantic models for request/response validation.

This module contains all data models used for API request and response validation.
Models are organized by domain: tickets, jobs, and scoring.

To add new models:
1. Define the Pydantic model with appropriate field types
2. Add validation rules using Field() or validators
3. Export from __init__.py if needed externally

Design decisions:
- Optional fields use Optional[] with default None
- Timestamps are strings (ISO format) for JSON serialization
- Nested models are used for complex structures like ConfidenceScore
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ScoreFactors(BaseModel):
    """Score for a single dimension with explanatory factors."""
    score: int = Field(ge=0, le=25, description="Score for this dimension (0-25)")
    factors: list[str] = Field(default_factory=list, description="List of factors that affected the score, e.g. 'Has acceptance criteria (+5)'")


class ConfidenceBreakdown(BaseModel):
    """Breakdown of confidence score into four auditable dimensions."""
    requirement_clarity: ScoreFactors = Field(description="Is the issue well-specified? (0-25)")
    blast_radius: ScoreFactors = Field(description="How contained is the change? (0-25)")
    system_sensitivity: ScoreFactors = Field(description="Does this touch critical systems? (0-25)")
    testability: ScoreFactors = Field(description="Can we verify the fix? (0-25)")


class ConfidenceScore(BaseModel):
    """Overall confidence score with detailed breakdown."""
    total: int = Field(ge=0, le=100, description="Total confidence score (0-100)")
    breakdown: ConfidenceBreakdown


class TicketAnalysis(BaseModel):
    """Full analysis of a ticket including root issue, action plan, and confidence score."""
    root_issue: str = Field(description="Summary of the core problem from the issue description")
    action_plan: list[str] = Field(description="List of steps to resolve the issue")
    confidence_score: ConfidenceScore


class Ticket(BaseModel):
    """GitHub issue represented as a ticket in the dashboard."""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    status: str = Field(description="Ticket status: new, scoped, in_progress, review, or complete")
    labels: list[str] = []
    created_at: str
    updated_at: str
    html_url: str
    confidence_score: Optional[ConfidenceScore] = None
    analysis: Optional[TicketAnalysis] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    branch_name: Optional[str] = None
    job: Optional["JobResponse"] = None


class TicketListResponse(BaseModel):
    """Response model for listing tickets."""
    tickets: list[Ticket]


class ScopeResponse(BaseModel):
    """Response model for ticket scoping with full analysis."""
    ticket_number: int
    title: str
    analysis: TicketAnalysis


class TicketDB(BaseModel):
    """Database model for stored ticket state."""
    id: Optional[int] = None
    repo: str
    issue_number: int
    status: str = "new"
    scope_data: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Job(BaseModel):
    """Job model for tracking async operations."""
    id: str
    ticket_id: int
    status: str = "pending"
    current_step: Optional[str] = None
    steps_completed: int = 0
    total_steps: int = 4
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    worktree_path: Optional[str] = None
    branch_name: Optional[str] = None


class JobCreateRequest(BaseModel):
    """Request model for creating a new job."""
    ticket_id: int


class JobResponse(BaseModel):
    """Response model for job status."""
    id: str
    ticket_id: int
    status: str
    current_step: Optional[str] = None
    steps_completed: int
    total_steps: int
    error_message: Optional[str] = None
    worktree_path: Optional[str] = None
    branch_name: Optional[str] = None


# Rebuild Ticket model to resolve forward reference to JobResponse
Ticket.model_rebuild()
