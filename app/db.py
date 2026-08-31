import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/colima.db")

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Global Simulation State (Master Clock)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS global_simulation (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        current_sim_time TEXT NOT NULL,
        speed_multiplier REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'paused',
        last_real_timestamp REAL NOT NULL,
        active_events TEXT NOT NULL DEFAULT '[]'
    );
    """)
    
    cursor.execute("SELECT id FROM global_simulation WHERE id = 1;")
    if not cursor.fetchone():
        now_ts = datetime.utcnow().timestamp()
        cursor.execute("""
        INSERT INTO global_simulation (id, current_sim_time, speed_multiplier, status, last_real_timestamp, active_events)
        VALUES (1, '2030-09-12T09:00:00', 0.0, 'paused', ?, '[]');
        """, (now_ts,))
    
    # Workspaces (Student Sandboxes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        project_name TEXT DEFAULT 'Fintech Micro-Lending MVP',
        project_description TEXT DEFAULT 'Desarrollo de un MVP para préstamos digitales con onboarding, KYC, pasarela de pagos y backoffice.',
        custom_prompt TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """)

    # Talent Pool Profiles (ATS)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS talent_profiles (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        seniority TEXT NOT NULL,
        skills TEXT NOT NULL,
        productivity_factor REAL NOT NULL DEFAULT 1.0,
        availability_status TEXT NOT NULL DEFAULT 'available',
        current_task_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
    );
    """)

    # Kanban Tasks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        role_required TEXT NOT NULL,
        estimated_hours REAL NOT NULL DEFAULT 8.0,
        completed_hours REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'backlog',
        assignee_id TEXT,
        assignee_name TEXT,
        priority TEXT NOT NULL DEFAULT 'medium',
        blocker_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
    );
    """)

    # Hiring Requests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hiring_requests (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        role TEXT NOT NULL,
        required_skills TEXT NOT NULL,
        urgency TEXT NOT NULL DEFAULT 'medium',
        rationale TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
    );
    """)

    # Chat Messages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        sender_name TEXT NOT NULL,
        content TEXT NOT NULL,
        message_type TEXT NOT NULL DEFAULT 'chat',
        metadata TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
    );
    """)

    # Agent Trajectories (Thinking, Tool Calling, Inspector)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_trajectories (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        prompt_used TEXT NOT NULL,
        thoughts TEXT DEFAULT '',
        tool_calls TEXT DEFAULT '[]',
        tool_results TEXT DEFAULT '[]',
        final_response TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
