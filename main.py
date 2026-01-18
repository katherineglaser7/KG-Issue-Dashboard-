from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import os
from dotenv import load_dotenv
import re

load_dotenv()

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "katherineglaser7/devin-automation-test")


class ConfidenceBreakdown(BaseModel):
    requirement_clarity: int
    code_complexity: int
    test_coverage: int
    risk_assessment: int


class ConfidenceScore(BaseModel):
    total: int
    breakdown: ConfidenceBreakdown


class Ticket(BaseModel):
    id: int
    number: int
    title: str
    body: Optional[str]
    status: str
    labels: list[str]
    created_at: str
    updated_at: str
    html_url: str
    confidence_score: Optional[ConfidenceScore] = None


def calculate_confidence_score(issue: dict) -> ConfidenceScore:
    """Calculate confidence score based on issue content."""
    body = issue.get("body", "") or ""
    title = issue.get("title", "") or ""
    labels = [l.get("name", "") for l in issue.get("labels", [])]

    requirement_clarity = 10
    if "## Description" in body or "## Requirements" in body:
        requirement_clarity += 5
    if "## Acceptance Criteria" in body:
        requirement_clarity += 5
    if len(body) > 200:
        requirement_clarity += 3
    if "## Files to modify" in body or "## Files to create" in body:
        requirement_clarity += 2
    requirement_clarity = min(25, requirement_clarity)

    code_complexity = 15
    files_mentioned = len(re.findall(r'`[^`]+\.(py|js|ts|tsx|jsx|css|html)`', body))
    if files_mentioned <= 2:
        code_complexity += 5
    elif files_mentioned <= 5:
        code_complexity += 3
    if "bug" in labels or "fix" in [lab.lower() for lab in labels]:
        code_complexity += 3
    if "enhancement" in labels:
        code_complexity += 2
    code_complexity = min(25, code_complexity)

    test_coverage = 15
    if "test" in body.lower() or "testing" in labels:
        test_coverage += 5
    if "## Tests" in body or "test_" in body:
        test_coverage += 5
    test_coverage = min(25, test_coverage)

    risk_assessment = 18
    if "breaking" not in body.lower():
        risk_assessment += 3
    if "migration" not in body.lower():
        risk_assessment += 2
    if "database" not in body.lower():
        risk_assessment += 2
    risk_assessment = min(25, risk_assessment)

    total = requirement_clarity + code_complexity + test_coverage + risk_assessment

    return ConfidenceScore(
        total=total,
        breakdown=ConfidenceBreakdown(
            requirement_clarity=requirement_clarity,
            code_complexity=code_complexity,
            test_coverage=test_coverage,
            risk_assessment=risk_assessment,
        )
    )


def determine_status(issue: dict) -> str:
    """Determine ticket status based on labels and state."""
    labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
    state = issue.get("state", "open")

    if state == "closed":
        return "done"

    if "in progress" in labels or "in-progress" in labels or "wip" in labels:
        return "in_progress"

    if "done" in labels or "completed" in labels:
        return "done"

    return "todo"


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/api/tickets")
async def get_tickets():
    """Fetch all issues from GitHub and return as tickets."""
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient() as client:
        open_response = await client.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers=headers,
            params={"state": "open", "per_page": 100}
        )

        closed_response = await client.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers=headers,
            params={"state": "closed", "per_page": 100}
        )

        if open_response.status_code != 200:
            raise HTTPException(
                status_code=open_response.status_code,
                detail=f"GitHub API error: {open_response.text}"
            )

        issues = open_response.json() + closed_response.json()

    tickets = []
    for issue in issues:
        if "pull_request" in issue:
            continue

        status = determine_status(issue)
        ticket = Ticket(
            id=issue["id"],
            number=issue["number"],
            title=issue["title"],
            body=issue.get("body"),
            status=status,
            labels=[l["name"] for l in issue.get("labels", [])],
            created_at=issue["created_at"],
            updated_at=issue["updated_at"],
            html_url=issue["html_url"],
            confidence_score=None,
        )
        tickets.append(ticket)

    return {"tickets": tickets}


@app.get("/api/tickets/{ticket_number}/scope")
async def scope_ticket(ticket_number: int):
    """Calculate and return confidence score for a specific ticket."""
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues/{ticket_number}",
            headers=headers,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )

        issue = response.json()

    confidence_score = calculate_confidence_score(issue)

    return {
        "ticket_number": ticket_number,
        "title": issue["title"],
        "confidence_score": confidence_score,
    }
