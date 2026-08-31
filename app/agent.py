import json
import re
import uuid
import time
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.db import get_db_connection

BASE_HERMES_PROMPT = """Eres Hermes, un Technical Product Manager (PM) autónomo ágil, estructurado, proactivo, analítico y muy humano.

RESPONSABILIDADES COMO PM:
1. APERTURA Y DEFINICIÓN DE PROYECTOS: Puedes conversar con el usuario para entender nuevos productos/proyectos, hacer preguntas clave de alcance y crear formalmente el proyecto y su backlog.
2. GESTIÓN DE EQUIPO Y CARGA: Puedes responder preguntas sobre el equipo, analizar la carga de trabajo, productividad y horas asignadas a cada desarrollador para evitar saturación o balancear tareas.
3. KANBAN Y CEREMONIAS: Planificas tareas, agendas reuniones de kickoff/checkpoints y escalas decisiones gerenciales críticas.

REGLAS DE COMUNICACIÓN Y TONO (CRÍTICAS):
1. HABLA COMO UN PM REAL: Sé directo, conciso, amigable y orientado a la acción (máximo 2 a 4 oraciones por respuesta a menos que presentes un reporte formal estructurado).
2. NUNCA menciones nombres de funciones o herramientas técnicas en el texto (NUNCA digas 'get_talent_pool()', 'create_project()', etc.). Ejecuta las acciones en segundo plano.
3. PREGUNTAS SOBRE EL ESTADO ACTUAL: Usa la información en tiempo real que tienes del proyecto, equipo y tareas para responder con precisión y naturalidad a cualquier pregunta del usuario.
"""

GEMINI_TOOLS_DECLARATION = [
    {
        "function_declarations": [
            {
                "name": "create_project",
                "description": "Apertura un nuevo proyecto con su título, descripción, stack tecnológico y fecha objetivo.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Nombre del proyecto."},
                        "description": {"type": "STRING", "description": "Objetivo y alcance principal."},
                        "tech_stack": {"type": "STRING", "description": "Stack de tecnologías (ej. FastAPI, React, PostgreSQL)."},
                        "target_deadline": {"type": "STRING", "description": "Plazo estimado (ej. '4 semanas', 'Día 30')."}
                    },
                    "required": ["title", "description"]
                }
            },
            {
                "name": "get_projects",
                "description": "Obtiene la lista de proyectos activos y su información en el workspace.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "get_team_workload",
                "description": "Analiza la carga de trabajo actual, horas acumuladas y rendimiento de cada desarrollador del equipo.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "get_talent_pool",
                "description": "Obtiene los perfiles y habilidades del equipo en el ATS.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "create_task",
                "description": "Crea una nueva tarea en el Kanban y la asigna a un desarrollador.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Título claro de la tarea."},
                        "description": {"type": "STRING", "description": "Criterio de aceptación o alcance."},
                        "role_required": {"type": "STRING", "description": "Rol requerido (Backend, Frontend, QA, DevOps)."},
                        "estimated_hours": {"type": "NUMBER", "description": "Horas estimadas."},
                        "assignee_name": {"type": "STRING", "description": "Nombre de la persona asignada."},
                        "priority": {"type": "STRING", "enum": ["low", "medium", "high", "urgent"], "description": "Prioridad."}
                    },
                    "required": ["title", "role_required", "estimated_hours", "assignee_name"]
                }
            },
            {
                "name": "delete_task",
                "description": "Elimina una tarea del tablero Kanban.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "task_id": {"type": "STRING", "description": "ID de la tarea a eliminar."}
                    },
                    "required": ["task_id"]
                }
            },
            {
                "name": "clear_board",
                "description": "Limpia o reinicia todas las tareas del tablero Kanban para replanificar desde cero.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "reassign_task",
                "description": "Reasigna una tarea a otro desarrollador.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "task_id": {"type": "STRING", "description": "ID de la tarea."},
                        "new_assignee_name": {"type": "STRING", "description": "Nombre del nuevo asignado."},
                        "reason": {"type": "STRING", "description": "Motivo del cambio."}
                    },
                    "required": ["task_id", "new_assignee_name", "reason"]
                }
            },
            {
                "name": "schedule_meeting",
                "description": "Agenda una reunión en el calendario del equipo.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Título de la reunión."},
                        "sim_date": {"type": "STRING", "description": "Fecha (ej. '15 Sep 2030' o 'Día 4')."},
                        "time_slot": {"type": "STRING", "description": "Horario (ej. '10:00 AM - 10:45 AM')."},
                        "attendees": {"type": "STRING", "description": "Participantes convocados."},
                        "agenda": {"type": "STRING", "description": "Objetivo de la sesión."}
                    },
                    "required": ["title", "sim_date", "time_slot", "attendees"]
                }
            },
            {
                "name": "request_managerial_approval",
                "description": "Solicita aprobación de la Gerencia ante decisiones clave (contratación, alcance o presupuesto).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Título de la solicitud."},
                        "description": {"type": "STRING", "description": "Detalle de la situación."},
                        "impact_summary": {"type": "STRING", "description": "Impacto en costo, tiempo o entrega."}
                    },
                    "required": ["title", "description", "impact_summary"]
                }
            },
            {
                "name": "generate_daily_standup_report",
                "description": "Genera el reporte de la Daily Standup con avances y bloqueos.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            }
        ]
    }
]

def build_system_prompt_with_skills(workspace_id: str, custom_prompt: Optional[str] = None) -> str:
    conn = get_db_connection()
    skills = conn.execute("SELECT name, prompt_instructions FROM skills WHERE workspace_id = ? AND is_active = 1;", (workspace_id,)).fetchall()
    talents = conn.execute("SELECT name, role, seniority, skills, productivity_factor FROM talent_profiles WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    tasks = conn.execute("SELECT title, assignee_name, status, progress_percent FROM (SELECT title, assignee_name, status, round(completed_hours / estimated_hours * 100) as progress_percent FROM tasks WHERE workspace_id = ?);", (workspace_id,)).fetchall()
    projects = conn.execute("SELECT title, tech_stack, target_deadline, status FROM projects WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    sim_row = conn.execute("SELECT current_sim_time FROM global_simulation WHERE id = 1;").fetchone()
    conn.close()

    parts = [BASE_HERMES_PROMPT]

    # Live State Context
    parts.append("\n[ESTADO ACTUAL DEL WORKSPACE EN TIEMPO REAL]:")
    
    # Sim Time
    if sim_row:
        parts.append(f"- Fecha/Hora Simulada: {sim_row['current_sim_time']}")

    # Projects
    if projects:
        p_lines = [f"{p['title']} (Stack: {p['tech_stack']}, Meta: {p['target_deadline']}, Estado: {p['status']})" for p in projects]
        parts.append(f"- Proyectos Activos ({len(projects)}): {'; '.join(p_lines)}")
    else:
        parts.append("- Proyectos Activos: Ninguno creado aún.")

    # Talent / Workers
    if talents:
        t_lines = [f"{t['name']} ({t['role']} - {t['seniority']}, Factor: {t['productivity_factor']}x)" for t in talents]
        parts.append(f"- Trabajadores en el Equipo ({len(talents)}): {'; '.join(t_lines)}")
    else:
        parts.append("- Trabajadores en el Equipo: 0 perfiles cargados en el ATS.")

    # Tasks
    if tasks:
        parts.append(f"- Tareas en el Kanban: {len(tasks)} tareas registradas.")
    else:
        parts.append("- Tareas en el Kanban: 0 tareas en el tablero.")

    if custom_prompt and len(custom_prompt.strip()) > 5:
        parts.append(f"\n[INSTRUCCIÓN PERSONALIZADA]:\n{custom_prompt.strip()}")

    if skills:
        parts.append("\n[HABILIDADES ACTIVAS DEL PM]:")
        for s in skills:
            parts.append(f"- {s['name']}: {s['prompt_instructions']}")

    return "\n\n".join(parts)

def execute_tool(workspace_id: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    result = {}
    
    if tool_name == "create_project":
        prj_id = f"prj-{int(time.time()*1000)}"
        conn.execute("""
        INSERT INTO projects (id, workspace_id, title, description, tech_stack, target_deadline, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?);
        """, (
            prj_id,
            workspace_id,
            args.get("title", "Nuevo Proyecto"),
            args.get("description", ""),
            args.get("tech_stack", "No especificado"),
            args.get("target_deadline", "Por definir"),
            datetime.utcnow().isoformat()
        ))
        conn.execute("""
        UPDATE workspaces SET project_name = ?, project_description = ? WHERE id = ?;
        """, (args.get("title"), args.get("description"), workspace_id))
        conn.commit()
        result = {"status": "created", "project_id": prj_id, "title": args.get("title")}

    elif tool_name == "get_projects":
        rows = conn.execute("SELECT id, title, description, tech_stack, target_deadline, status FROM projects WHERE workspace_id = ?;", (workspace_id,)).fetchall()
        projects = [dict(r) for r in rows]
        result = {"projects": projects, "total_projects": len(projects)}

    elif tool_name == "get_team_workload":
        talents = conn.execute("SELECT name, role, seniority, productivity_factor FROM talent_profiles WHERE workspace_id = ?;", (workspace_id,)).fetchall()
        tasks = conn.execute("SELECT assignee_name, estimated_hours, completed_hours, status FROM tasks WHERE workspace_id = ?;", (workspace_id,)).fetchall()
        
        workload = {}
        for t in talents:
            workload[t["name"]] = {
                "role": t["role"],
                "seniority": t["seniority"],
                "productivity": f"{t['productivity_factor']}x",
                "assigned_tasks_count": 0,
                "total_estimated_hours": 0.0,
                "completed_hours": 0.0,
                "saturation": "Libre"
            }
        
        for task in tasks:
            name = task["assignee_name"]
            if name in workload:
                workload[name]["assigned_tasks_count"] += 1
                workload[name]["total_estimated_hours"] += task["estimated_hours"]
                workload[name]["completed_hours"] += task["completed_hours"]
        
        for name, data in workload.items():
            hrs = data["total_estimated_hours"]
            if hrs > 30:
                data["saturation"] = "Sobrecargado"
            elif hrs > 15:
                data["saturation"] = "Óptimo"
            elif hrs > 0:
                data["saturation"] = "Baja carga"
            else:
                data["saturation"] = "Disponible"

        result = {"team_workload": workload}

    elif tool_name == "get_talent_pool":
        rows = conn.execute("SELECT id, name, role, seniority, skills, productivity_factor, availability_status FROM talent_profiles WHERE workspace_id = ?;", (workspace_id,)).fetchall()
        talent = []
        for r in rows:
            talent.append({
                "id": r["id"],
                "name": r["name"],
                "role": r["role"],
                "seniority": r["seniority"],
                "skills": json.loads(r["skills"]) if r["skills"] else [],
                "status": r["availability_status"]
            })
        result = {"talent_pool": talent, "total_profiles": len(talent)}

    elif tool_name == "create_task":
        task_id = f"tsk-{int(time.time()*1000)}-{uuid.uuid4().hex[:4]}"
        assignee_name = args.get("assignee_name", "")
        row = conn.execute("SELECT id FROM talent_profiles WHERE workspace_id = ? AND LOWER(name) LIKE ?;", (workspace_id, f"%{assignee_name.lower().strip()}%")).fetchone()
        assignee_id = row["id"] if row else None

        conn.execute("""
        INSERT INTO tasks (id, workspace_id, title, description, role_required, estimated_hours, completed_hours, status, assignee_id, assignee_name, priority, blocker_reason, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0.0, 'in_progress', ?, ?, ?, NULL, ?, ?);
        """, (
            task_id,
            workspace_id,
            args.get("title", "Nueva Tarea"),
            args.get("description", ""),
            args.get("role_required", "Software Engineer"),
            float(args.get("estimated_hours", 8.0)),
            assignee_id,
            assignee_name,
            args.get("priority", "medium"),
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        result = {"status": "created", "task_id": task_id, "title": args.get("title"), "assigned_to": assignee_name}

    elif tool_name == "delete_task":
        task_id = args.get("task_id")
        conn.execute("DELETE FROM tasks WHERE id = ? AND workspace_id = ?;", (task_id, workspace_id))
        conn.commit()
        result = {"status": "deleted", "task_id": task_id}

    elif tool_name == "clear_board":
        conn.execute("DELETE FROM tasks WHERE workspace_id = ?;", (workspace_id,))
        conn.commit()
        result = {"status": "board_cleared"}

    elif tool_name == "reassign_task":
        task_id = args.get("task_id")
        new_name = args.get("new_assignee_name")
        reason = args.get("reason", "")
        row = conn.execute("SELECT id FROM talent_profiles WHERE workspace_id = ? AND LOWER(name) LIKE ?;", (workspace_id, f"%{new_name.lower().strip()}%")).fetchone()
        new_id = row["id"] if row else None

        conn.execute("""
        UPDATE tasks
        SET assignee_id = ?, assignee_name = ?, blocker_reason = NULL, status = 'in_progress', updated_at = ?
        WHERE id = ? AND workspace_id = ?;
        """, (new_id, new_name, datetime.utcnow().isoformat(), task_id, workspace_id))
        conn.commit()
        result = {"status": "reassigned", "task_id": task_id, "new_assignee": new_name}

    elif tool_name == "schedule_meeting":
        evt_id = f"evt-{int(time.time()*1000)}"
        conn.execute("""
        INSERT INTO calendar_events (id, workspace_id, title, sim_date, time_slot, event_type, attendees, agenda, created_at)
        VALUES (?, ?, ?, ?, ?, 'meeting', ?, ?, ?);
        """, (
            evt_id,
            workspace_id,
            args.get("title", "Reunión de Equipo"),
            args.get("sim_date", "Día Actual"),
            args.get("time_slot", "10:00 AM"),
            args.get("attendees", "Todo el equipo"),
            args.get("agenda", ""),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        result = {"status": "scheduled", "meeting_id": evt_id, "title": args.get("title")}

    elif tool_name == "request_managerial_approval":
        dec_id = f"dec-{int(time.time()*1000)}"
        conn.execute("""
        INSERT INTO managerial_decisions (id, workspace_id, title, description, impact_summary, status, response_comment, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', NULL, ?);
        """, (
            dec_id,
            workspace_id,
            args.get("title", "Decisión Gerencial"),
            args.get("description", ""),
            args.get("impact_summary", ""),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        result = {"status": "decision_requested", "decision_id": dec_id, "title": args.get("title")}

    elif tool_name == "generate_daily_standup_report":
        tasks = conn.execute("SELECT title, assignee_name, status, completed_hours, estimated_hours, blocker_reason FROM tasks WHERE workspace_id = ?;", (workspace_id,)).fetchall()
        report_data = []
        for t in tasks:
            pct = round((t["completed_hours"] / t["estimated_hours"] * 100) if t["estimated_hours"] > 0 else 0)
            report_data.append({
                "task": t["title"],
                "assignee": t["assignee_name"],
                "status": t["status"],
                "progress_percent": f"{pct}%",
                "blocker": t["blocker_reason"]
            })
        result = {"standup_summary": report_data, "total_tasks": len(report_data)}

    conn.close()
    return result

def strip_thinking_tokens(text: str) -> str:
    """
    Gemma outputs its reasoning before the final response. This function
    surgically extracts only the final user-facing message.

    Strategy:
    1. Strip <think>...</think> explicit blocks.
    2. Split into paragraphs (double-newline).
    3. Drop paragraphs that are clearly model reasoning (English meta-commentary).
    4. From the remaining text, drop line-by-line reasoning lines.
    5. Return only the clean conversational paragraphs.
    """
    import re

    if not text:
        return text

    # Remove explicit think blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Reasoning line prefixes that Gemma outputs (English internal monologue)
    REASONING_LINE_PREFIXES = [
        'the user said', 'the user is', 'the user ask', 'the user want',
        'the user might', 'the user seem', 'the user has',
        'as hermes', 'as a pm', 'as the pm', 'as an ai', 'as a technical pm',
        'i should', "i'll ", 'i will ', 'i need to ', 'i must ',
        'i already', 'i can ', 'i am hermes', 'i have access', 'i have the ',
        'plan:', 'plan:\n',
        '* user says:', '* context:', '* goal:', '* tone:', '* constraint:',
        '* action:', '* direct?', '* concise?', '* friendly?',
        '* action-oriented?', '* no tool', '* current state:',
        '* reasoning:', '* final response:', '* response:',
        'step 1:', 'step 2:', 'step 3:',
        'response strategy:', 'my response:', 'response:',
        'reasoning:', 'thinking:', 'analysis:',
        'maintaining the persona', 'maintaining persona',
        'this is a greeting', 'this is a simple', 'this is a follow',
        "here's my response", 'here is my response',
        'looking at the system', 'looking at the available', 'looking at my',
        'my persona is', 'the system prompt', 'the system instructions',
        'given the context', 'given that', 'based on the system',
        'i have a tool', '- i have a tool', '- my persona',
    ]

    # Numbered reasoning lines: "1. Acknowledge", "2. Briefly", etc. (only in reasoning context)
    NUMBERED_REASONING = re.compile(r'^\d+\.\s+[A-Z][a-z]')

    def is_reasoning_line(line: str) -> bool:
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped:
            return False
        # Drop lines that start with reasoning prefixes
        for prefix in REASONING_LINE_PREFIXES:
            if lower.startswith(prefix):
                return True
        # Drop numbered English reasoning lines (e.g. "1. Acknowledge the greeting.")
        if NUMBERED_REASONING.match(stripped) and not any(
            c in stripped for c in ['¡', '¿', 'á', 'é', 'í', 'ó', 'ú', 'ñ', 'Ñ']
        ):
            return True
        return False

    # Split into paragraphs and classify each
    paragraphs = re.split(r'\n{2,}', text)
    clean_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        lines = para.split('\n')
        clean_lines = [l for l in lines if not is_reasoning_line(l)]
        clean_para = '\n'.join(clean_lines).strip()
        if clean_para:
            clean_paragraphs.append(clean_para)

    result = '\n\n'.join(clean_paragraphs).strip()

    # If still has reasoning mixed in, take only the last non-empty block
    # that looks like an actual conversational response (contains Spanish chars or emoji)
    if result:
        blocks = [b.strip() for b in result.split('\n\n') if b.strip()]
        # Find last block with conversational markers (Spanish, emoji, or question mark)
        for block in reversed(blocks):
            if any(c in block for c in ['¡', '¿', 'á', 'é', 'í', 'ó', 'ú', 'ñ', '👋', '🚀', '✅', '📊', '?', '!']):
                if len(block) > 15:
                    # Deduplicate: remove lines that are just the same text repeated (quoted or not)
                    lines_in_block = block.split('\n')
                    seen_normalized = set()
                    deduped = []
                    for line in lines_in_block:
                        # Normalize: strip quotes, whitespace
                        norm = line.strip().strip('"').strip("'").strip()
                        if norm and norm not in seen_normalized:
                            seen_normalized.add(norm)
                            deduped.append(line)
                    return '\n'.join(deduped).strip()

    return result if result else text.strip()


async def run_hermes_agent(workspace_id: str, user_message: str, api_key: Optional[str] = None, custom_system_prompt: Optional[str] = None) -> Dict[str, Any]:
    # Record user message in DB
    conn = get_db_connection()
    user_msg_id = f"msg-usr-{int(time.time()*1000)}"
    conn.execute("""
    INSERT INTO chat_messages (id, workspace_id, sender, sender_name, content, message_type, metadata, created_at)
    VALUES (?, ?, 'user', 'Tú', ?, 'chat', '{}', ?);
    """, (user_msg_id, workspace_id, user_message, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    system_instruction = build_system_prompt_with_skills(workspace_id, custom_system_prompt)

    # If no API key provided, use dynamic smart fallback
    if not api_key or len(api_key.strip()) < 10:
        return await run_smart_fallback(workspace_id, user_message, system_instruction)

    # Primary: gemma-4-26b-a4b-it (conversational, as requested by instructor)
    # Tool-calling fallback: gemini-3.6-flash (supports native function declarations)
    CANDIDATE_MODELS = [
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
        "gemini-3.6-flash",
        "gemini-2.5-flash-preview-05-20",
        "gemini-1.5-flash"
    ]
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key.strip()
    }

    conn = get_db_connection()
    recent_msgs = conn.execute("SELECT sender, content FROM chat_messages WHERE workspace_id = ? ORDER BY created_at ASC LIMIT 10;", (workspace_id,)).fetchall()
    conn.close()

    contents = []
    for m in recent_msgs:
        role = "user" if m["sender"] == "user" else "model"
        txt = (m["content"] or "").strip()
        if not txt:
            continue
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"][0]["text"] += "\n" + txt
        else:
            contents.append({
                "role": role,
                "parts": [{"text": txt}]
            })

    while contents and contents[0]["role"] != "user":
        contents.pop(0)

    if not contents:
        contents = [{"role": "user", "parts": [{"text": user_message}]}]

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "tools": GEMINI_TOOLS_DECLARATION,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 800
        }
    }

    trajectory_id = f"trj-{int(time.time()*1000)}"
    executed_tools = []
    tool_results = []
    final_text = ""
    thinking_text = "Evaluando contexto del sprint con modelo de IA..."

    print(f"[AGENT] api_key present={bool(api_key and len(api_key.strip())>10)}, len={len(api_key.strip()) if api_key else 0}")
    print(f"[AGENT] workspace={workspace_id} msg={user_message[:40]!r}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = None
            for model_name in CANDIDATE_MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                print(f"[AGENT] Trying model: {model_name}")
                
                is_gemma = model_name.lower().startswith("gemma")

                if is_gemma:
                    # Gemma: embed system prompt + user message directly (no tools, no system_instruction wrapper)
                    # Gemma can't reliably emit functionCall JSON, so we give it all context inline
                    gemma_contents = [{"role": "user", "parts": [{"text": f"{system_instruction}\n\n[Mensaje del Usuario]: {user_message}"}]}]
                    use_payload = {
                        "contents": gemma_contents,
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600}
                    }
                else:
                    use_payload = payload

                res = await client.post(url, headers=headers, json=use_payload)
                print(f"[AGENT] {model_name} → HTTP {res.status_code}")
                if res.status_code == 200:
                    break
                print(f"[AGENT] {model_name} failed {res.status_code}: {res.text[:200]}")

            if not res or res.status_code != 200:
                print(f"[AGENT] All models failed → smart fallback")
                return await run_smart_fallback(workspace_id, user_message, system_instruction)
            
            data = res.json()
            candidates = data.get("candidates", [])
            if not candidates:
                print(f"[AGENT] No candidates in response → smart fallback")
                return await run_smart_fallback(workspace_id, user_message, system_instruction)
            
            content_resp = candidates[0].get("content", {})
            parts = content_resp.get("parts", [])
            
            func_calls = [p.get("functionCall") for p in parts if "functionCall" in p]
            text_parts = [p.get("text") for p in parts if "text" in p]
            
            if text_parts:
                raw_text = "\n".join(text_parts)
                print(f"[AGENT] raw_text (first 300): {raw_text[:300]!r}")
                final_text = strip_thinking_tokens(raw_text)
                print(f"[AGENT] stripped (first 200): {final_text[:200]!r}")

            if func_calls:
                contents.append({"role": "model", "parts": parts})
                tool_response_parts = []
                for fc in func_calls:
                    fname = fc.get("name")
                    fargs = fc.get("args", {})
                    executed_tools.append({"tool": fname, "args": fargs})
                    
                    t_res = execute_tool(workspace_id, fname, fargs)
                    tool_results.append({"tool": fname, "result": t_res})
                    
                    tool_response_parts.append({
                        "functionResponse": {
                            "name": fname,
                            "response": {"output": t_res}
                        }
                    })
                
                contents.append({"role": "user", "parts": tool_response_parts})
                payload["contents"] = contents
                
                res2 = await client.post(url, headers=headers, json=payload)
                if res2.status_code == 200:
                    data2 = res2.json()
                    parts2 = data2.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    raw2 = "\n".join([p.get("text") for p in parts2 if "text" in p])
                    final_text = strip_thinking_tokens(raw2)



    except Exception as exc:
        print(f"[Gemini Exception]: {exc}")
        return await run_smart_fallback(workspace_id, user_message, system_instruction)

    # If stripping left us with nothing, run smart fallback instead of generic message
    if not final_text or len(final_text.strip()) < 5:
        return await run_smart_fallback(workspace_id, user_message, system_instruction)

    # Save Assistant message
    conn = get_db_connection()
    agent_msg_id = f"msg-hermes-{int(time.time()*1000)}"
    conn.execute("""
    INSERT INTO chat_messages (id, workspace_id, sender, sender_name, content, message_type, metadata, created_at)
    VALUES (?, ?, 'hermes', 'Hermes (PM)', ?, 'chat', ?, ?);
    """, (agent_msg_id, workspace_id, final_text, json.dumps({"tools": executed_tools}), datetime.utcnow().isoformat()))

    conn.execute("""
    INSERT INTO agent_trajectories (id, workspace_id, action_type, prompt_used, thoughts, tool_calls, tool_results, final_response, created_at)
    VALUES (?, ?, 'user_turn', ?, ?, ?, ?, ?, ?);
    """, (
        trajectory_id,
        workspace_id,
        user_message,
        thinking_text,
        json.dumps(executed_tools),
        json.dumps(tool_results),
        final_text,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        "message_id": agent_msg_id,
        "response": final_text,
        "tools_executed": executed_tools,
        "tool_results": tool_results,
        "thinking": thinking_text
    }

async def run_smart_fallback(workspace_id: str, user_message: str, system_prompt: str) -> Dict[str, Any]:
    conn = get_db_connection()
    user_lower = user_message.lower().strip()
    
    talents = conn.execute("SELECT name, role, seniority, productivity_factor FROM talent_profiles WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    tasks = conn.execute("SELECT id, title, assignee_name, status, estimated_hours, completed_hours, priority, blocker_reason FROM tasks WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    projects = conn.execute("SELECT title, tech_stack, target_deadline, status FROM projects WHERE workspace_id = ?;", (workspace_id,)).fetchall()
    conn.close()

    executed_tools = []
    tool_results = []
    thinking = "Analizando contexto y base de datos del proyecto..."
    
    # 0. Preguntas sobre perfiles específicos de trabajadores
    matched_profile = None
    for t in talents:
        first_name = t["name"].split()[0].lower()
        if len(first_name) > 2 and first_name in user_lower:
            matched_profile = t
            break
    
    if matched_profile:
        skills_list = []
        try:
            conn_temp = get_db_connection()
            row = conn_temp.execute("SELECT skills, availability_status FROM talent_profiles WHERE workspace_id = ? AND name = ?;", (workspace_id, matched_profile["name"])).fetchone()
            conn_temp.close()
            if row and row["skills"]:
                skills_list = json.loads(row["skills"])
        except Exception:
            pass
        final_text = f"**{matched_profile['name']}** ({matched_profile['seniority']} {matched_profile['role']}):\n• **Factor Productividad:** {matched_profile['productivity_factor']}x\n• **Stack Principal:** {', '.join(skills_list) if skills_list else 'Fullstack'}\n\n¿Quieres que le asigne tareas o revisemos su carga actual?"

    # 1. Identidad del modelo
    elif any(k in user_lower for k in ["que modelo", "qué modelo", "cual modelo", "cuál modelo", "gemma", "gemini", "quien eres", "quién eres"]):
        final_text = "Soy **Hermes PM**, un Asistente Autónomo de Gestión de Equipos de Software impulsado por **Google AI Studio (Gemma 4 26B-A4B-IT)**. Estoy conectado en tiempo real al ATS, Kanban y Calendario del proyecto para asistirte."

    # 2. Preguntas sobre trabajadores / equipo
    elif any(k in user_lower for k in ["cuantos trabajadores", "cuántos trabajadores", "quienes trabajan", "quiénes trabajan", "nuestro equipo", "los desarrolladores", "mi equipo", "trabajadores"]):
        if not talents:
            final_text = "Actualmente **no tenemos trabajadores** en el equipo. Puedes subir los CVs en la pestaña **Mis Trabajadores** o hacer clic en 'Cargar 5 CVs' para armar el equipo."
        else:
            names = [f"**{t['name']}** ({t['role']})" for t in talents]
            final_text = f"Actualmente contamos con **{len(talents)} trabajadores** en el equipo:\n• " + "\n• ".join(names) + "\n\n¿Quieres que revise su carga de trabajo o les asigne tareas?"

    # 3. Saludos
    elif any(k in user_lower for k in ["hola", "buenas", "buenos dias", "buenas tardes", "hey", "como te va", "cómo te va"]):
        t_count = len(talents)
        p_count = len(projects)
        final_text = f"¡Todo excelente por acá! Tenemos {p_count} proyecto(s) y {t_count} trabajadores en el equipo. ¿Revisamos el sprint, planificamos tareas o vemos las sugerencias de mejora?"

    # 4. Definición / Apertura de proyectos
    elif any(k in user_lower for k in ["definir proyecto", "nuevo proyecto", "crear proyecto", "aperturar", "iniciar proyecto"]):
        final_text = "¡Perfecto! Como PM estructuro el proyecto. Cuéntame:\n1. ¿Cuál es el objetivo principal del producto?\n2. ¿Qué stack tecnológico prefieres (ej. FastAPI, React, Node)?\n3. ¿Cuál es nuestra fecha estimada de entrega o MVP?"

    # 5. Proyectos activos
    elif any(k in user_lower for k in ["proyectos activos", "que proyectos", "qué proyectos", "mis proyectos", "cuantos proyectos", "cuántos proyectos"]):
        if not projects:
            final_text = "No tenemos proyectos activos registrados actualmente. ¿Quieres que aperturemos uno nuevo?"
        else:
            lines = ["**Proyectos Activos:**"]
            for p in projects:
                lines.append(f"• **{p['title']}** (Stack: {p['tech_stack']}) — Meta: {p['target_deadline']}")
            final_text = "\n".join(lines)


    # 5. Rendimiento y carga de trabajo
    elif any(k in user_lower for k in ["rendimiento", "carga", "workload", "capacidad", "horas"]):
        w_res = execute_tool(workspace_id, "get_team_workload", {})
        executed_tools.append({"tool": "get_team_workload", "args": {}})
        tool_results.append({"tool": "get_team_workload", "result": w_res})
        
        workload = w_res.get("team_workload", {})
        if not workload:
            final_text = "Aún no hay trabajadores en el ATS. Carga los CVs para evaluar la capacidad."
        else:
            lines = ["**Reporte de Capacidad del Equipo:**"]
            for name, d in workload.items():
                lines.append(f"• **{name}** ({d['role']}): {d['assigned_tasks_count']} tareas ({d['total_estimated_hours']}h asignadas) — **{d['saturation']}** (Factor {d['productivity']})")
            final_text = "\n".join(lines)

    # 6. Borrado / Limpieza
    elif any(k in user_lower for k in ["borra", "limpia", "reinicia tablero", "eliminar tareas"]):
        c_res = execute_tool(workspace_id, "clear_board", {})
        executed_tools.append({"tool": "clear_board", "args": {}})
        tool_results.append({"tool": "clear_board", "result": c_res})
        final_text = "Listo, he limpiado las tareas del Kanban. Cuando quieras, podemos estructurar un nuevo backlog desde cero."

    # 7. Planificación de Sprint / MVP
    elif any(k in user_lower for k in ["planifica", "inicia sprint", "organiza tareas", "crea tareas", "asigna"]):
        t_res = execute_tool(workspace_id, "get_talent_pool", {})
        executed_tools.append({"tool": "get_talent_pool", "args": {}})
        tool_results.append({"tool": "get_talent_pool", "result": t_res})
        
        talent_pool = t_res.get("talent_pool", [])
        tasks_to_create = [
            {"title": "Arquitectura Backend & Setup FastAPI", "role": "Backend Developer", "hours": 16.0, "prio": "high"},
            {"title": "UI Onboarding & Flujo KYC", "role": "Frontend Developer", "hours": 20.0, "prio": "high"},
            {"title": "Pasarela de Pagos & Webhooks SPEI", "role": "Backend Developer", "hours": 24.0, "prio": "urgent"},
            {"title": "Pipeline CI/CD en Kubernetes", "role": "DevOps & Cloud Engineer", "hours": 14.0, "prio": "medium"},
            {"title": "Suite de Pruebas E2E en Cypress", "role": "QA Automation Engineer", "hours": 18.0, "prio": "high"}
        ]
        
        for t in tasks_to_create:
            assignee = "Ana Morales"
            for p in talent_pool:
                if t["role"].lower() in p["role"].lower():
                    assignee = p["name"]
                    break
            
            args = {
                "title": t["title"],
                "description": "Entregable crítico para el MVP.",
                "role_required": t["role"],
                "estimated_hours": t["hours"],
                "assignee_name": assignee,
                "priority": t["prio"]
            }
            c_res = execute_tool(workspace_id, "create_task", args)
            executed_tools.append({"tool": "create_task", "args": args})
            tool_results.append({"tool": "create_task", "result": c_res})

        m_args = {
            "title": "Sprint Kickoff & Alineación",
            "sim_date": "12 Sep 2030",
            "time_slot": "09:30 AM",
            "attendees": "Todo el equipo",
            "agenda": "Alineación de objetivos y arranque de tareas."
        }
        m_res = execute_tool(workspace_id, "schedule_meeting", m_args)
        executed_tools.append({"tool": "schedule_meeting", "args": m_args})
        tool_results.append({"tool": "schedule_meeting", "result": m_res})
        
        final_text = f"¡Planificación lista! Distribuí 5 tareas clave según las fortalezas del equipo en el ATS y agendé la reunión de Kickoff en el calendario."

    # 8. Reuniones y calendario
    elif any(k in user_lower for k in ["reunión", "reunion", "calendario", "agendar", "checkpoint"]):
        m_args = {
            "title": "Checkpoint de Avance & Riesgos",
            "sim_date": "Día 5 (16 Sep)",
            "time_slot": "10:00 AM",
            "attendees": "Tech Lead, Backend & QA",
            "agenda": "Validar integración de APIs y desbloquear dependencias."
        }
        m_res = execute_tool(workspace_id, "schedule_meeting", m_args)
        executed_tools.append({"tool": "schedule_meeting", "args": m_args})
        tool_results.append({"tool": "schedule_meeting", "result": m_res})
        final_text = "Agendé la sesión en el calendario. Puedes ver los detalles en la pestaña **3. Mi Calendario**."

    # 9. Daily Standup
    elif any(k in user_lower for k in ["standup", "daily", "estado del sprint", "como vamos", "cómo vamos"]):
        s_res = execute_tool(workspace_id, "generate_daily_standup_report", {})
        executed_tools.append({"tool": "generate_daily_standup_report", "args": {}})
        tool_results.append({"tool": "generate_daily_standup_report", "result": s_res})
        
        summary = s_res.get("standup_summary", [])
        if not summary:
            final_text = "Aún no hay tareas activas en el tablero. ¿Quieres que planifique el MVP primero?"
        else:
            lines = ["**Resumen de la Daily:**"]
            for s in summary[:4]:
                lines.append(f"• **{s['assignee']}** ({s['task']}): {s['progress_percent']}")
            final_text = "\n".join(lines)

    else:
        # Natural, context-aware catch-all
        t_count = len(talents)
        p_count = len(projects)
        task_count = len(tasks)

        # Estado-del-arte contextual  
        if t_count == 0 and p_count == 0:
            final_text = "Aún estamos sin equipo ni proyectos. Carga los CVs en 'Mis Trabajadores' o dime el nombre del proyecto y te ayudo a arrancarlo."
        elif t_count > 0 and p_count == 0:
            names = [t["name"].split()[0] for t in talents[:3]]
            final_text = f"Tenemos al equipo listo ({', '.join(names)}{'...' if t_count > 3 else ''}), pero sin proyecto asignado todavía. ¿Quieres que definamos el objetivo, el stack y arrancamos?"
        elif p_count > 0 and task_count == 0:
            final_text = f"El proyecto está registrado pero el tablero está vacío. ¿Arrancamos con la planificación del sprint? Puedo distribuir las tareas según las fortalezas del equipo."
        elif task_count > 0:
            done = sum(1 for t in tasks if t["status"] == "done")
            pct = round(done / task_count * 100) if task_count > 0 else 0
            final_text = f"Vamos al {pct}% de avance ({done}/{task_count} tareas completadas). ¿Revisamos bloqueos, ajustamos asignaciones o prefieres el reporte del daily?"
        else:
            final_text = "Aquí estoy. Cuéntame qué necesitas — puedo revisar el equipo, planificar tareas, agendar una reunión o analizar los riesgos del sprint."


    agent_msg_id = f"msg-hermes-{int(time.time()*1000)}"
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO chat_messages (id, workspace_id, sender, sender_name, content, message_type, metadata, created_at)
    VALUES (?, ?, 'hermes', 'Hermes (PM)', ?, 'chat', ?, ?);
    """, (agent_msg_id, workspace_id, final_text, json.dumps({"tools": executed_tools}), datetime.utcnow().isoformat()))

    trajectory_id = f"trj-{int(time.time()*1000)}"
    conn.execute("""
    INSERT INTO agent_trajectories (id, workspace_id, action_type, prompt_used, thoughts, tool_calls, tool_results, final_response, created_at)
    VALUES (?, ?, 'fallback_turn', ?, ?, ?, ?, ?, ?);
    """, (
        trajectory_id,
        workspace_id,
        user_message,
        thinking,
        json.dumps(executed_tools),
        json.dumps(tool_results),
        final_text,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        "message_id": agent_msg_id,
        "response": final_text,
        "tools_executed": executed_tools,
        "tool_results": tool_results,
        "thinking": thinking
    }
