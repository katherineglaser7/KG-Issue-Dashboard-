# KG Issue Dashboard

A GitHub Issues dashboard that integrates with Devin for automated ticket resolution.

## Features
- View and triage GitHub issues across 4 columns: New, Scoped, Review, Complete
- AI-powered ticket scoping with confidence scoring
- Integration with Devin API for automated code fixes
- Real-time job tracking and PR creation

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials
2. Install backend dependencies: `cd backend && pip install -e .`
3. Install frontend dependencies: `cd frontend && npm install`
4. Run backend: `cd backend && uvicorn app.main:app --reload`
5. Run frontend: `cd frontend && npm run dev`

## Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token with repo access
- `GITHUB_REPO`: Default repository (format: owner/repo)
- `DEVIN_API_KEY`: Your Devin API key 
