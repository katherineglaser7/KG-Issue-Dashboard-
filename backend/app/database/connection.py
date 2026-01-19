"""
SQLite database connection management.

This module handles database initialization and connection management.
Uses context managers for safe connection handling.

Database location: ./data/dashboard.db (configurable via settings)

To switch to a different database:
1. Update the database_url in config.py
2. Modify get_connection() to use the appropriate driver
3. Update SQL syntax in repositories.py if needed (e.g., for PostgreSQL)
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.config import get_settings


def init_database() -> None:
    """
    Initialize the database with required tables.
    
    Creates the data directory if it doesn't exist and sets up tables
    with IF NOT EXISTS to make this operation idempotent.
    
    Called on application startup to ensure database is ready.
    """
    settings = get_settings()
    db_path = Path(settings.database_url)
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT NOT NULL,
            issue_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            scope_data TEXT,
            pr_number INTEGER,
            pr_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(repo, issue_number)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT,
            steps_completed INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 4,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            worktree_path TEXT,
            branch_name TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN worktree_path TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN branch_name TEXT")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections.
    
    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
    
    Automatically commits on success and rolls back on exception.
    """
    settings = get_settings()
    conn = sqlite3.connect(str(settings.database_url))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
