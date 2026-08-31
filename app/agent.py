import json
import re
import uuid
import time
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.db import get_db_connection

BASE_HERMES_PROMPT = """Eres Hermes, un Technical Product Manager (PM) ágil, proactivo, estructurado y muy humano.

REGLAS DE COMUNICACIÓN Y TONO (CRÍTICAS):
1. HABLA COMO UN PM EXPERTO: Sé directo, conciso, colaborativo y natural. Evita explicaciones robóticas, párrafos largos o lenguaje académico. Máximo 2 a 4 oraciones por respuesta a menos que te pidan un reporte formal.
2. CERO METATEXTO TÉCNICO: NUNCA menciones nombres de funciones, librerías ni herramientas internas en tu texto (NUNCA escribas 'get_talent_pool()', 'schedule_meeting()', 'create_task()', etc.). Ejecuta las herramientas en silencio y habla de los resultados reales.
3. SALUDOS Y CONVERSACIÓN: Si te dicen 'hola', 'buenas', '¿cómo estás?', saluda cordialmente en 1-2 líneas y pregunta en qué nos enfocamos hoy en el proyecto.
4. GESTIÓN PROACTIVA: Tras planificar o detectar problemas, da un resumen breve y propón el siguiente paso lógico (ej. agendar el kickoff, revisar un bloqueo o validar con gerencia).
"""

GEMINI_TOOLS_DECLARATION = [
    {
        "function_declarations": [
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
    conn.close()

    parts = [BASE_HERMES_PROMPT]
    if custom_prompt and len(custom_prompt.strip()) > 5:
        parts.append(f"\n[CONTEXTO DEL PROYECTO]:\n{custom_prompt.strip()}")

    if skills:
        parts.append("\n[HABILIDADES ACTIVAS DEL PM]:")
        for s in skills:
            parts.append(f"- {s['name']}: {s['prompt_instructions']}")

    return "\n\n".join(parts)

def execute_tool(workspace_id: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    result = {}
    
    if tool_name == "get_talent_pool":
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

    # Fallback to local heuristic mode if no API key is provided
    if not api_key or len(api_key.strip()) < 10:
        return await run_simulated_fallback(workspace_id, user_message, system_instruction)

    # Secure Google AI Studio call with x-goog-api-key header
    model_name = "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
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
        contents.append({
            "role": role,
            "parts": [{"text": m["content"]}]
        })

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "tools": GEMINI_TOOLS_DECLARATION,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024
        }
    }

    trajectory_id = f"trj-{int(time.time()*1000)}"
    executed_tools = []
    tool_results = []
    final_text = ""
    thinking_text = "Evaluando contexto del sprint y requerimientos..."

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code != 200:
                return await run_simulated_fallback(workspace_id, user_message, system_instruction)
            
            data = res.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return await run_simulated_fallback(workspace_id, user_message, system_instruction)
            
            content_resp = candidates[0].get("content", {})
            parts = content_resp.get("parts", [])
            
            func_calls = [p.get("functionCall") for p in parts if "functionCall" in p]
            text_parts = [p.get("text") for p in parts if "text" in p]
            
            if text_parts:
                final_text = "\n".join(text_parts)

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
                    final_text = "\n".join([p.get("text") for p in parts2 if "text" in p])

    except Exception:
        return await run_simulated_fallback(workspace_id, user_message, system_instruction)

    if not final_text:
        final_text = "Tablero actualizado y tareas organizadas para el equipo."

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

async def run_simulated_fallback(workspace_id: str, user_message: str, system_prompt: str, error_msg: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    user_lower = user_message.lower().strip()
    
    executed_tools = []
    tool_results = []
    thinking = "Evaluando solicitud del PM..."
    
    # Natural conversation handling
    if user_lower in ["hola", "buenas", "buenos dias", "buenas tardes", "hey", "hola hermes", "estas ahi", "estas ahi ?"]:
        final_text = "¡Hola! Todo el equipo está activo. ¿En qué nos enfocamos hoy? ¿Planificamos el sprint, revisamos la daily o agendamos una sesión?"

    elif "borra" in user_lower or "limpia" in user_lower or "reinicia tablero" in user_lower:
        c_res = execute_tool(workspace_id, "clear_board", {})
        executed_tools.append({"tool": "clear_board", "args": {}})
        tool_results.append({"tool": "clear_board", "result": c_res})
        final_text = "Listo, he limpiado las tareas del Kanban. Cuando quieras, podemos estructurar un nuevo backlog desde cero."

    elif "planifica" in user_lower or "inicia" in user_lower or "organiza" in user_lower:
        t_res = execute_tool(workspace_id, "get_talent_pool", {})
        executed_tools.append({"tool": "get_talent_pool", "args": {}})
        tool_results.append({"tool": "get_talent_pool", "result": t_res})
        
        talent = t_res.get("talent_pool", [])
        tasks_to_create = [
            {"title": "Arquitectura Backend & Setup FastAPI", "role": "Backend Developer", "hours": 16.0, "prio": "high"},
            {"title": "UI Onboarding & Flujo KYC", "role": "Frontend Developer", "hours": 20.0, "prio": "high"},
            {"title": "Pasarela de Pagos & Webhooks SPEI", "role": "Backend Developer", "hours": 24.0, "prio": "urgent"},
            {"title": "Pipeline CI/CD en Kubernetes", "role": "DevOps & Cloud Engineer", "hours": 14.0, "prio": "medium"},
            {"title": "Suite de Pruebas E2E en Cypress", "role": "QA Automation Engineer", "hours": 18.0, "prio": "high"}
        ]
        
        for t in tasks_to_create:
            assignee = "Ana Morales"
            for p in talent:
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

    elif "reunión" in user_lower or "reunion" in user_lower or "calendario" in user_lower or "agendar" in user_lower or "checkpoint" in user_lower:
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
        final_text = "Agendé la sesión en el calendario. Puedes ver los detalles en la pestaña **Calendario & Decisiones**."

    elif "contratar" in user_lower or "decisión" in user_lower or "decision" in user_lower or "aprobación" in user_lower or "aprobar" in user_lower:
        d_args = {
            "title": "Aprobación: Contratación de Senior Mobile Dev",
            "description": "Requerimiento de app nativa en React Native. El equipo actual está a tope con backend y web.",
            "impact_summary": "+$4,200 USD / Asegura entrega en 3 semanas."
        }
        d_res = execute_tool(workspace_id, "request_managerial_approval", d_args)
        executed_tools.append({"tool": "request_managerial_approval", "args": d_args})
        tool_results.append({"tool": "request_managerial_approval", "result": d_res})
        final_text = "Creé una solicitud de aprobación para la Dirección en la pestaña **Calendario & Decisiones**. Échale un ojo para aprobarla o rechazarla."

    elif "standup" in user_lower or "daily" in user_lower or "estado" in user_lower or "cómo vamos" in user_lower:
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
        final_text = "Entendido. El equipo está avanzando. Puedes pedirme: *'Planifica el MVP'*, *'Cómo va la daily'* o *'Agenda una reunión de avance'*."

    agent_msg_id = f"msg-hermes-{int(time.time()*1000)}"
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
