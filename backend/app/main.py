"""
FastAPI application entry point.

This module creates the FastAPI app instance, configures middleware,
mounts routers, and handles startup/shutdown events.

Application structure:
- config.py: Settings and environment variables
- database/: Database connection and repositories
- services/: Business logic (GitHub, scoring, Devin)
- routers/: API endpoint handlers
- schemas/: Pydantic models for request/response

To add new functionality:
1. Create service in services/ for business logic
2. Create router in routers/ for endpoints
3. Mount router in this file
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.connection import init_database
from app.routers import tickets, jobs, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup/shutdown events.
    
    Startup: Initialize database tables
    Shutdown: (cleanup if needed in future)
    """
    init_database()
    yield


app = FastAPI(
    title="KG Issue Dashboard API",
    description="GitHub Issues Dashboard with ticket scoping and automation",
    version="1.0.0",
    lifespan=lifespan,
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(tickets.router)
app.include_router(jobs.router)
app.include_router(webhooks.router)


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "ok"}
