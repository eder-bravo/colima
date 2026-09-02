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
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
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
        "is_active": 0
    },
    {
        "id": "skill-workload-capacity",
        "name": "Control de Carga & Rendimiento del Equipo",
        "icon": "fa-chart-pie",
        "description": "Monitorea horas asignadas, productividad y previene el agotamiento (burnout) del equipo.",
        "prompt_instructions": "Usa 'get_team_workload' para analizar la capacidad del equipo. Si un desarrollador tiene más de 30 horas acumuladas, advierte sobre la sobrecarga y sugiere reasignar tareas a miembros disponibles.",
        "is_active": 0
    },
    {
        "id": "skill-staffing-ats",
        "name": "Staffing & Matching ATS",
        "icon": "fa-users-gear",
        "description": "Analiza perfiles de candidatos en PDF/ATS y asigna tareas según seniority y stack técnico.",
        "prompt_instructions": "Evalúa constantemente las habilidades del equipo en el ATS antes de asignar tareas. Asigna tareas críticas a desarrolladores Senior y tareas de soporte a perfiles Junior.",
        "is_active": 0
    },
    {
        "id": "skill-standup-metrics",
        "name": "Daily Standup & Bloqueos",
        "icon": "fa-chart-line",
        "description": "Modera la sincronización diaria, detecta atrasos y calcula el avance del sprint.",
        "prompt_instructions": "En cada reporte diario, resume qué hizo cada miembro, el porcentaje de avance y emite alertas inmediatas si alguna tarea está bloqueada.",
        "is_active": 0
    },
    {
        "id": "skill-calendar-meetings",
        "name": "Calendario & Ceremonias Ágiles",
        "icon": "fa-calendar-check",
        "description": "Agenda automáticamente reuniones de Sprint Planning, Checkpoint y Demos según los hitos alcanzados.",
        "prompt_instructions": "Cuando el sprint inicie o alcance hitos clave (50% de avance o incidencias mayores), usa la herramienta 'schedule_meeting' para convocar al equipo.",
        "is_active": 0
    },
    {
        "id": "skill-managerial-governance",
        "name": "Decisiones & Aprobaciones Gerenciales",
        "icon": "fa-scale-balanced",
        "description": "Escala decisiones críticas (presupuesto, contrataciones, cambios de alcance) a la dirección antes de actuar.",
        "prompt_instructions": "Ante cambios imprevistos de alcance o necesidad de contratar personal, NO tomes la decisión final solo. Usa 'request_managerial_approval' para pedir autorización al Gerente.",
        "is_active": 0
    },
    {
        "id": "skill-executive-briefing",
        "name": "Minutas & Correo Ejecutivo",
        "icon": "fa-envelope-open-text",
        "description": "Redacta informes ejecutivos concisos y formales para directores y clientes.",
        "prompt_instructions": "Cuando el usuario pida un reporte para directores o minuta, formatea el texto en tono ejecutivo: resumen de 3 bullets, estado del presupuesto y próximos pasos críticos.",
        "is_active": 0
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
        project_name TEXT DEFAULT NULL,
        project_description TEXT DEFAULT NULL,
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

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN review_feedback TEXT;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN review_hours REAL DEFAULT 0.0;")
    except Exception:
        pass

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
        is_active INTEGER NOT NULL DEFAULT 0,
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
    """Dynamically recomputes suggestions and automatically deactivates stale ones."""
    conn = get_db_connection()
    talents = conn.execute("SELECT id, name, role, seniority, productivity_factor FROM talent_profiles WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    tasks = conn.execute("SELECT id, title, assignee_name, estimated_hours, completed_hours, status, blocker_reason FROM tasks WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    projects = conn.execute("SELECT id, title, target_deadline FROM projects WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    
    # Check 1: Staffing
    if len(talents) == 0:
        s_id = f"sug-{workspace_id}-no-staff"
        conn.execute("""
        INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
        VALUES (?, ?, 'staffing', 'Falta de Equipo (Staffing)', 'El proyecto no cuenta con desarrolladores en el ATS.', 'Carga o arrastra CVs en PDF para que Hermes pueda asignar tareas.', 'quick_load', '{}', 'active', ?);
        """, (s_id, workspace_id, datetime.utcnow().isoformat()))
    else:
        # Clean up stale no-staff suggestion
        conn.execute("UPDATE pm_suggestions SET status = 'dismissed' WHERE id = ? AND workspace_id = ? AND status = 'active';", (f"sug-{workspace_id}-no-staff", workspace_id))

    # Check 2: Worker Overload / Bottleneck (only active pending tasks)
    workload = {}
    for t in talents:
        workload[t["name"]] = 0.0
    for task in tasks:
        name = task["assignee_name"]
        if name and name in workload and task["status"] not in ("done", "review"):
            workload[name] += max(0.0, task["estimated_hours"] - task["completed_hours"])
            
    active_overloads = set()
    for name, hrs in workload.items():
        if hrs > 30.0:
            slug = name.lower().replace(' ', '-')
            s_id = f"sug-{workspace_id}-overload-{slug}"
            active_overloads.add(s_id)
            conn.execute("""
            INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
            VALUES (?, ?, 'workload', 'Riesgo de Sobrecarga (Burnout)', ?, 'Se sugiere reasignar tareas menores a desarrolladores con disponibilidad.', 'rebalance', ?, 'active', ?);
            """, (s_id, workspace_id, f"{name} tiene {hrs:.0f}h pendientes asignadas (límite saludable 30h).", json.dumps({"worker": name, "hours": hrs}), datetime.utcnow().isoformat()))

            # Automatically create or keep active a pending managerial decision
            dec_id = f"dec-{workspace_id}-rebalance-{slug}"
            conn.execute("""
            INSERT OR IGNORE INTO managerial_decisions (id, workspace_id, title, description, impact_summary, status, response_comment, created_at)
            VALUES (?, ?, ?, ?, 'Reduce sobrecarga a nivel saludable (~24h) y evita retraso en la entrega del MVP.', 'pending', NULL, ?);
            """, (
                dec_id, 
                workspace_id, 
                f"Aprobación: Rebalanceo de Carga ({name})", 
                f"{name} acumula {hrs:.0f}h de trabajo pendiente en el sprint. Hermes propone reasignar tareas secundarias a perfiles disponibles para balancear la capacidad del equipo.",
                datetime.utcnow().isoformat()
            ))

    # Dismiss overloads that no longer exist
    all_overload_sugs = conn.execute("SELECT id FROM pm_suggestions WHERE workspace_id = ? AND category = 'workload' AND status = 'active';", (workspace_id,)).fetchall()
    for row in all_overload_sugs:
        if row["id"] not in active_overloads:
            conn.execute("UPDATE pm_suggestions SET status = 'dismissed' WHERE id = ?;", (row["id"],))

    # Check 3: Blockers in tasks
    active_blockers = set()
    for task in tasks:
        if task["blocker_reason"] and task["status"] != "done":
            s_id = f"sug-{workspace_id}-blocker-{task['id']}"
            active_blockers.add(s_id)
            conn.execute("""
            INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
            VALUES (?, ?, 'risk', 'Bloqueo Activo en Tarea', ?, 'Convocar sesión de desbloqueo con el equipo.', 'schedule_meeting', ?, 'active', ?);
            """, (s_id, workspace_id, f"La tarea '{task['title']}' está detenida: {task['blocker_reason']}", json.dumps({"task_id": task["id"]}), datetime.utcnow().isoformat()))

    all_blocker_sugs = conn.execute("SELECT id FROM pm_suggestions WHERE workspace_id = ? AND category = 'risk' AND status = 'active';", (workspace_id,)).fetchall()
    for row in all_blocker_sugs:
        if row["id"] not in active_blockers:
            conn.execute("UPDATE pm_suggestions SET status = 'dismissed' WHERE id = ?;", (row["id"],))

    # Check 4: Hiring Opportunity (No QA)
    has_qa = any("qa" in t["role"].lower() or "tester" in t["role"].lower() or "qa" in t["name"].lower() for t in talents)
    qa_sug_id = f"sug-{workspace_id}-hire-qa"
    if len(talents) > 0 and not has_qa:
        conn.execute("""
        INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
        VALUES (?, ?, 'staffing', 'Oportunidad de Contratación: QA Engineer', 'El equipo no cuenta con un especialista en QA Automation para validar el proyecto antes de producción.', 'Considera incorporar un perfil de QA Automation.', 'request_approval', '{}', 'active', ?);
        """, (qa_sug_id, workspace_id, datetime.utcnow().isoformat()))
    elif has_qa:
        conn.execute("UPDATE pm_suggestions SET status = 'dismissed' WHERE id = ? AND workspace_id = ? AND status = 'active';", (qa_sug_id, workspace_id))

    conn.commit()
    conn.close()

def dismiss_suggestion(workspace_id: str, suggestion_id: str):
    conn = get_db_connection()
    conn.execute("UPDATE pm_suggestions SET status = 'dismissed' WHERE id = ? AND workspace_id = ?;", (suggestion_id, workspace_id))
    conn.commit()
    conn.close()

def create_custom_skill(workspace_id: str, name: str, icon: str, description: str, prompt_instructions: str) -> dict:
    conn = get_db_connection()
    skill_id = f"skill-custom-{int(time.time()*1000)}"
    icon = icon if icon.startswith("fa-") else f"fa-{icon}"
    now = datetime.utcnow().isoformat()
    conn.execute("""
    INSERT INTO skills (id, workspace_id, name, icon, description, prompt_instructions, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, 1, ?);
    """, (skill_id, workspace_id, name, icon, description, prompt_instructions, now))
    conn.commit()
    conn.close()
    return {"id": skill_id, "workspace_id": workspace_id, "name": name, "icon": icon, "description": description, "prompt_instructions": prompt_instructions, "is_active": 1}

def ensure_workspace(workspace_id: str, name: str = "Alumno"):
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM workspaces WHERE id = ?;", (workspace_id,)).fetchone()
    if not row:
        conn.execute("""
        INSERT INTO workspaces (id, name, project_name, project_description, custom_prompt, created_at)
        VALUES (?, ?, NULL, NULL, '', ?);
        """, (workspace_id, name, datetime.utcnow().isoformat()))

    # Ensure default skills exist (inactive by default for workshop discovery)
    for sk in DEFAULT_SKILLS:
        s_row = conn.execute("SELECT id FROM skills WHERE id = ? AND workspace_id = ?;", (sk["id"], workspace_id)).fetchone()
        if not s_row:
            conn.execute("""
            INSERT INTO skills (id, workspace_id, name, icon, description, prompt_instructions, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (sk["id"], workspace_id, sk["name"], sk["icon"], sk["description"], sk["prompt_instructions"], 0, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

    compute_pm_suggestions(workspace_id)

def ensure_workspace_skills(workspace_id: str):
    ensure_workspace(workspace_id)

def reset_workspace(workspace_id: str):
    """Wipe all workspace data and re-initialize cleanly with 0 projects and inactive skills."""
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
    # Reset all skills to inactive (is_active = 0)
    conn.execute("UPDATE skills SET is_active = 0 WHERE workspace_id = ?;", (workspace_id,))
    conn.commit()
    conn.close()
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
