import sqlite3
import os
import json
import uuid
import time
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

DEFAULT_SKILLS = [
    {
        "id": "skill-project-discovery",
        "name": "Apertura & Descubrimiento de Proyectos",
        "icon": "fa-diagram-project",
        "description": "Formula preguntas de PM para definir alcance, stack y objetivos antes de aperturar un proyecto.",
        "prompt_instructions": "Cuando el usuario quiera iniciar o definir un nuevo producto, realiza 2 o 3 preguntas concisas de PM (problema a resolver, stack tecnológico preferido y fecha objetivo). Tras recibir la información, crea formalmente el proyecto y su backlog inicial.",
        "is_active": 1
    },
    {
        "id": "skill-workload-capacity",
        "name": "Control de Carga & Rendimiento del Equipo",
        "icon": "fa-chart-pie",
        "description": "Monitorea horas asignadas, productividad y previene el agotamiento (burnout) del equipo.",
        "prompt_instructions": "Usa 'get_team_workload' para analizar la capacidad del equipo. Si un desarrollador tiene más de 30 horas acumuladas, advierte sobre la sobrecarga y sugiere reasignar tareas a miembros disponibles.",
        "is_active": 1
    },
    {
        "id": "skill-staffing-ats",
        "name": "Staffing & Matching ATS",
        "icon": "fa-users-gear",
        "description": "Analiza perfiles de candidatos en PDF/ATS y asigna tareas según seniority y stack técnico.",
        "prompt_instructions": "Evalúa constantemente las habilidades del equipo en el ATS antes de asignar tareas. Asigna tareas críticas a desarrolladores Senior y tareas de soporte a perfiles Junior.",
        "is_active": 1
    },
    {
        "id": "skill-standup-metrics",
        "name": "Daily Standup & Bloqueos",
        "icon": "fa-chart-line",
        "description": "Modera la sincronización diaria, detecta atrasos y calcula el avance del sprint.",
        "prompt_instructions": "En cada reporte diario, resume qué hizo cada miembro, el porcentaje de avance y emite alertas inmediatas si alguna tarea está bloqueada.",
        "is_active": 1
    },
    {
        "id": "skill-calendar-meetings",
        "name": "Calendario & Ceremonias Ágiles",
        "icon": "fa-calendar-check",
        "description": "Agenda automáticamente reuniones de Sprint Planning, Checkpoint y Demos según los hitos alcanzados.",
        "prompt_instructions": "Cuando el sprint inicie o alcance hitos clave (50% de avance o incidencias mayores), usa la herramienta 'schedule_meeting' para convocar al equipo.",
        "is_active": 1
    },
    {
        "id": "skill-managerial-governance",
        "name": "Decisiones & Aprobaciones Gerenciales",
        "icon": "fa-scale-balanced",
        "description": "Escala decisiones críticas (presupuesto, contrataciones, cambios de alcance) a la dirección antes de actuar.",
        "prompt_instructions": "Ante cambios imprevistos de alcance o necesidad de contratar personal, NO tomes la decisión final solo. Usa 'request_managerial_approval' para pedir autorización al Gerente.",
        "is_active": 1
    }
]

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Global Simulation State
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
    
    # Workspaces
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

    # Projects
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        tech_stack TEXT,
        target_deadline TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL
    );
    """)

    # Talent Pool (Mis Trabajadores / ATS)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS talent_profiles (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        seniority TEXT NOT NULL,
        skills TEXT NOT NULL,
        raw_cv_text TEXT,
        source_file TEXT,
        productivity_factor REAL DEFAULT 1.0,
        availability_status TEXT DEFAULT 'available',
        created_at TEXT NOT NULL
    );
    """)

    # Tasks / Kanban
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        project_id TEXT,
        title TEXT NOT NULL,
        description TEXT,
        role_required TEXT NOT NULL,
        estimated_hours REAL NOT NULL,
        completed_hours REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'backlog',
        assignee_id TEXT,
        assignee_name TEXT,
        priority TEXT NOT NULL DEFAULT 'medium',
        blocker_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
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
        created_at TEXT NOT NULL
    );
    """)

    # Calendar Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calendar_events (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        title TEXT NOT NULL,
        sim_date TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        event_type TEXT NOT NULL DEFAULT 'meeting',
        attendees TEXT NOT NULL,
        agenda TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Managerial Decisions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS managerial_decisions (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        impact_summary TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        response_comment TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # PM Autonomous Suggestions / Insights
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pm_suggestions (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        category TEXT NOT NULL, -- staffing, workload, velocity, risk
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        action_type TEXT, -- hire, rebalance, schedule_demo, approve
        action_payload TEXT DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'active', -- active, applied, dismissed
        created_at TEXT NOT NULL
    );
    """)

    # Skills Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS skills (
        id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        name TEXT NOT NULL,
        icon TEXT NOT NULL,
        description TEXT NOT NULL,
        prompt_instructions TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        PRIMARY KEY (id, workspace_id)
    );
    """)

    # Agent Trajectories (ReAct Inspector)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_trajectories (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        prompt_used TEXT NOT NULL,
        thoughts TEXT,
        tool_calls TEXT,
        tool_results TEXT,
        final_response TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Hermes Autonomous Inbox (proactive PM messages)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hermes_inbox (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'insight',
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        read INTEGER NOT NULL DEFAULT 0,
        sim_time TEXT,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

def compute_pm_suggestions(workspace_id: str):
    conn = get_db_connection()
    talents = conn.execute("SELECT id, name, role, seniority, productivity_factor FROM talent_profiles WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    tasks = conn.execute("SELECT id, title, assignee_name, estimated_hours, completed_hours, status, blocker_reason FROM tasks WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    projects = conn.execute("SELECT id, title, target_deadline FROM projects WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    
    # Check 1: No workers present in ATS
    if len(talents) == 0:
        s_id = f"sug-{workspace_id}-no-staff"
        conn.execute("""
        INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
        VALUES (?, ?, 'staffing', 'Falta de Equipo (Staffing)', 'El proyecto no cuenta con desarrolladores en el ATS.', 'Carga los CVs de prueba o arrastra tus propios PDFs para que Hermes pueda asignar las tareas.', 'quick_load', '{}', 'active', ?);
        """, (s_id, workspace_id, datetime.utcnow().isoformat()))

    # Check 2: Worker Overload / Bottleneck
    workload = {}
    for t in talents:
        workload[t["name"]] = 0.0
    for task in tasks:
        name = task["assignee_name"]
        if name in workload:
            workload[name] += task["estimated_hours"]
            
    for name, hrs in workload.items():
        if hrs > 30.0:
            s_id = f"sug-{workspace_id}-overload-{name.lower().replace(' ', '-')}"
            conn.execute("""
            INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
            VALUES (?, ?, 'workload', 'Riesgo de Sobrecarga (Burnout)', ?, 'Se sugiere reasignar tareas menores a desarrolladores con disponibilidad.', 'rebalance', ?, 'active', ?);
            """, (s_id, workspace_id, f"{name} tiene {hrs}h acumuladas asignadas (límite saludable 30h).", json.dumps({"worker": name, "hours": hrs}), datetime.utcnow().isoformat()))

    # Check 3: Blockers in tasks
    for task in tasks:
        if task["blocker_reason"]:
            s_id = f"sug-{workspace_id}-blocker-{task['id']}"
            conn.execute("""
            INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
            VALUES (?, ?, 'risk', 'Bloqueo Activo en Tarea', ?, 'Convocar sesión de desbloqueo con el equipo.', 'schedule_meeting', ?, 'active', ?);
            """, (s_id, workspace_id, f"La tarea '{task['title']}' está detenida: {task['blocker_reason']}", json.dumps({"task_id": task["id"]}), datetime.utcnow().isoformat()))

    # Check 4: Hiring Opportunity (No QA)
    has_qa = any("qa" in t["role"].lower() or "tester" in t["role"].lower() for t in talents)
    if len(talents) > 0 and not has_qa:
        s_id = f"sug-{workspace_id}-hire-qa"
        conn.execute("""
        INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
        VALUES (?, ?, 'staffing', 'Oportunidad de Contratación: QA Engineer', 'El equipo no cuenta con un especialista en QA Automation para validar el MVP antes de producción.', 'Solicitar aprobación gerencial para contratar un QA Automation Senior.', 'request_approval', '{}', 'active', ?);
        """, (s_id, workspace_id, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

def ensure_workspace(workspace_id: str, name: str = "Alumno"):
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM workspaces WHERE id = ?;", (workspace_id,)).fetchone()
    if not row:
        conn.execute("""
        INSERT INTO workspaces (id, name, project_name, project_description, custom_prompt, created_at)
        VALUES (?, ?, 'Fintech Micro-Lending MVP', 'Desarrollo de un MVP para préstamos digitales con onboarding, KYC, pasarela de pagos y backoffice.', '', ?);
        """, (workspace_id, name, datetime.utcnow().isoformat()))
        
        # Default project
        conn.execute("""
        INSERT INTO projects (id, workspace_id, title, description, tech_stack, target_deadline, status, created_at)
        VALUES (?, ?, 'Fintech Micro-Lending MVP', 'Plataforma de préstamos digitales inmediatos con onboarding KYC.', 'FastAPI, React, PostgreSQL, Docker', '30 días', 'active', ?);
        """, (f"prj-{workspace_id}", workspace_id, datetime.utcnow().isoformat()))

    # Ensure default skills exist
    for sk in DEFAULT_SKILLS:
        s_row = conn.execute("SELECT id FROM skills WHERE id = ? AND workspace_id = ?;", (sk["id"], workspace_id)).fetchone()
        if not s_row:
            conn.execute("""
            INSERT INTO skills (id, workspace_id, name, icon, description, prompt_instructions, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (sk["id"], workspace_id, sk["name"], sk["icon"], sk["description"], sk["prompt_instructions"], sk["is_active"], datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

    compute_pm_suggestions(workspace_id)

def ensure_workspace_skills(workspace_id: str):
    ensure_workspace(workspace_id)

def reset_workspace(workspace_id: str):
    """Wipe all workspace data and re-initialize with defaults."""
    conn = get_db_connection()
    conn.execute("DELETE FROM chat_messages WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM tasks WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM managerial_decisions WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM calendar_events WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM pm_suggestions WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM hermes_inbox WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM agent_trajectories WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM projects WHERE workspace_id = ?;", (workspace_id,))
    conn.execute("DELETE FROM talent_profiles WHERE workspace_id = ?;", (workspace_id,))
    conn.execute(
        "UPDATE workspaces SET project_name = NULL, project_description = NULL, custom_prompt = '' WHERE id = ?;",
        (workspace_id,)
    )
    conn.commit()
    conn.close()
    # Re-init defaults (skills, default project)
    ensure_workspace(workspace_id)

def get_inbox_messages(workspace_id: str, unread_only: bool = False) -> list:
    conn = get_db_connection()
    if unread_only:
        rows = conn.execute(
            "SELECT * FROM hermes_inbox WHERE workspace_id = ? AND read = 0 ORDER BY created_at DESC LIMIT 50;",
            (workspace_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM hermes_inbox WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 100;",
            (workspace_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def push_inbox_message(workspace_id: str, msg_type: str, title: str, body: str, sim_time: str = None) -> dict:
    conn = get_db_connection()
    msg_id = f"inbox-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO hermes_inbox (id, workspace_id, type, title, body, read, sim_time, created_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?);",
        (msg_id, workspace_id, msg_type, title, body, sim_time, now)
    )
    conn.commit()
    conn.close()
    return {"id": msg_id, "workspace_id": workspace_id, "type": msg_type, "title": title, "body": body, "read": 0, "sim_time": sim_time, "created_at": now}

def mark_inbox_read(workspace_id: str, msg_id: str = None):
    conn = get_db_connection()
    if msg_id:
        conn.execute("UPDATE hermes_inbox SET read = 1 WHERE id = ? AND workspace_id = ?;", (msg_id, workspace_id))
    else:
        conn.execute("UPDATE hermes_inbox SET read = 1 WHERE workspace_id = ?;", (workspace_id,))
    conn.commit()
    conn.close()
