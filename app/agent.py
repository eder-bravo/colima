import json
import uuid
import time
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.db import get_db_connection

HERMES_SYSTEM_PROMPT = """Eres Hermes, un Asistente Product Manager (PM) Autónomo con Inteligencia Artificial, especializado en la gestión ágil de equipos de software y ejecución de sprints de alto impacto.

Tus responsabilidades principales son:
1. ANALIZAR EL POOL DE TALENTO (ATS): Evaluar los CVs/perfiles disponibles (seniority, habilidades, capacidad) para asignar las tareas correctas a las personas idóneas.
2. ESTRUCTURAR EL PROYECTO: Desglosar los requerimientos en tareas claras con estimaciones realistas de horas y prioridades bien fundamentadas.
3. MONITORIZAR Y RESOLVER BLOQUEOS: Si detectas que una tarea está bloqueada o un miembro del equipo se enferma/atrasa, reasigna tareas proactivamente o redistribuye la carga.
4. REQUISICIÓN DE CONTRATACIÓN: Si el alcance requiere una habilidad que nadie en el equipo domina o el equipo está saturado para la fecha límite, emite una requisición formal de contratación usando la herramienta correspondiente.
5. COMUNICACIÓN ÁGIL: Mantén un tono profesional, ejecutivo, claro y colaborativo en el chat del equipo.

Dispones de herramientas (function calling) para interactuar directamente con el tablero Kanban y el sistema ATS. Ejecútalas cuando sea necesario.
"""

GEMINI_TOOLS_DECLARATION = [
    {
        "function_declarations": [
            {
                "name": "get_talent_pool",
                "description": "Obtiene la lista completa de desarrolladores y especialistas disponibles en el ATS con sus habilidades técnicas, seniority y estado.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "create_task",
                "description": "Crea una nueva tarea en el tablero Kanban asignándola al trabajador más adecuado según su perfil de ATS.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Título descriptivo de la tarea técnica o de gestión."},
                        "description": {"type": "STRING", "description": "Detalles técnicos, criterios de aceptación y alcance."},
                        "role_required": {"type": "STRING", "description": "Rol requerido (ej. Backend Developer, Frontend Developer, QA Automation, DevOps)."},
                        "estimated_hours": {"type": "NUMBER", "description": "Estimación en horas de trabajo (ej. 8.0, 16.0, 24.0)."},
                        "assignee_name": {"type": "STRING", "description": "Nombre exacto del trabajador asignado según el pool de talento."},
                        "priority": {"type": "STRING", "enum": ["low", "medium", "high", "urgent"], "description": "Nivel de prioridad."}
                    },
                    "required": ["title", "role_required", "estimated_hours", "assignee_name"]
                }
            },
            {
                "name": "reassign_task",
                "description": "Reasigna una tarea a otro miembro del equipo debido a atrasos, incidencias o redistribución de carga.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "task_id": {"type": "STRING", "description": "ID de la tarea a reasignar."},
                        "new_assignee_name": {"type": "STRING", "description": "Nombre del nuevo miembro del equipo que asumirá la tarea."},
                        "reason": {"type": "STRING", "description": "Justificación técnica o de gestión para la reasignación."}
                    },
                    "required": ["task_id", "new_assignee_name", "reason"]
                }
            },
            {
                "name": "request_new_hire",
                "description": "Emite una solicitud formal de contratación cuando el equipo carece de un perfil indispensable para el éxito del proyecto.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "role": {"type": "STRING", "description": "Título del puesto requerido (ej. Senior Mobile Dev, Security Specialist)."},
                        "required_skills": {"type": "STRING", "description": "Habilidades técnicas indispensables separadas por comas."},
                        "urgency": {"type": "STRING", "enum": ["medium", "high", "critical"], "description": "Nivel de urgencia."},
                        "rationale": {"type": "STRING", "description": "Explicación de por qué el equipo actual no puede cubrir esta necesidad."}
                    },
                    "required": ["role", "required_skills", "rationale"]
                }
            },
            {
                "name": "generate_daily_standup_report",
                "description": "Escanea el tablero y genera un reporte de Daily Standup con el progreso de cada desarrollador, alertas y próximos pasos.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            }
        ]
    }
]

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
        # Find assignee id
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
        result = {"status": "reassigned", "task_id": task_id, "new_assignee": new_name, "reason": reason}

    elif tool_name == "request_new_hire":
        req_id = f"hire-{int(time.time()*1000)}"
        conn.execute("""
        INSERT INTO hiring_requests (id, workspace_id, role, required_skills, urgency, rationale, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?);
        """, (
            req_id,
            workspace_id,
            args.get("role", "Nuevo Puesto"),
            args.get("required_skills", ""),
            args.get("urgency", "medium"),
            args.get("rationale", ""),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        result = {"status": "requested", "hiring_request_id": req_id, "role": args.get("role")}

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
    VALUES (?, ?, 'user', 'Tú (Líder de Proyecto)', ?, 'chat', '{}', ?);
    """, (user_msg_id, workspace_id, user_message, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    system_instruction = custom_system_prompt if custom_system_prompt and len(custom_system_prompt.strip()) > 10 else HERMES_SYSTEM_PROMPT

    # If no API key provided, execute intelligent rule-based simulation flow
    if not api_key or len(api_key.strip()) < 10:
        return await run_simulated_fallback(workspace_id, user_message, system_instruction)

    # Call Google AI Studio (Gemini 2.5 Flash / Gemma) with Function Calling
    model_name = "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key.strip()}"

    # Build conversation context
    conn = get_db_connection()
    # Fetch recent messages
    recent_msgs = conn.execute("SELECT sender, content FROM chat_messages WHERE workspace_id = ? ORDER BY created_at ASC LIMIT 15;", (workspace_id,)).fetchall()
    conn.close()

    contents = []
    for m in recent_msgs:
        role = "user" if m["sender"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": m["content"]}]
        })

    # Prepare request payload
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "tools": GEMINI_TOOLS_DECLARATION,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048
        }
    }

    trajectory_id = f"trj-{int(time.time()*1000)}"
    executed_tools = []
    tool_results = []
    final_text = ""
    thinking_text = "Analizando contexto del proyecto, perfiles de talento y estado del tablero..."

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            # Turn 1
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            
            candidates = data.get("candidates", [])
            if not candidates:
                raise Exception("No candidates returned from Gemini API")
            
            content_resp = candidates[0].get("content", {})
            parts = content_resp.get("parts", [])
            
            # Check for function calls
            func_calls = [p.get("functionCall") for p in parts if "functionCall" in p]
            text_parts = [p.get("text") for p in parts if "text" in p]
            
            if text_parts:
                final_text = "\n".join(text_parts)

            # Execute function calls if present
            if func_calls:
                # Add model's tool calls to contents
                contents.append({
                    "role": "model",
                    "parts": parts
                })
                
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
                
                # Send tool response back to Gemini for final response
                contents.append({
                    "role": "user",
                    "parts": tool_response_parts
                })

                payload["contents"] = contents
                res2 = await client.post(url, json=payload)
                res2.raise_for_status()
                data2 = res2.json()
                
                parts2 = data2.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                final_text = "\n".join([p.get("text") for p in parts2 if "text" in p])

    except Exception as e:
        print(f"[Gemini API Error] {e}")
        # Fallback if API key fails or quota exceeded
        return await run_simulated_fallback(workspace_id, user_message, system_instruction, error_msg=str(e))

    if not final_text:
        final_text = "He procesado las acciones solicitadas y actualizado el tablero del proyecto."

    # Save Assistant message
    conn = get_db_connection()
    agent_msg_id = f"msg-hermes-{int(time.time()*1000)}"
    conn.execute("""
    INSERT INTO chat_messages (id, workspace_id, sender, sender_name, content, message_type, metadata, created_at)
    VALUES (?, ?, 'hermes', 'Hermes (PM Autónomo)', ?, 'chat', ?, ?);
    """, (agent_msg_id, workspace_id, final_text, json.dumps({"tools": executed_tools}), datetime.utcnow().isoformat()))

    # Save Trajectory
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
    """Autonomous rule-based fallback if BYOK API key is not yet configured or fails."""
    conn = get_db_connection()
    user_lower = user_message.lower()
    
    executed_tools = []
    tool_results = []
    thinking = "Ejecutando razonamiento PM heurístico basado en el estado del ATS y tareas..."
    
    if "planifica" in user_lower or "inicia" in user_lower or "comienza" in user_lower or "organiza" in user_lower:
        # 1. Fetch talent pool
        t_res = execute_tool(workspace_id, "get_talent_pool", {})
        executed_tools.append({"tool": "get_talent_pool", "args": {}})
        tool_results.append({"tool": "get_talent_pool", "result": t_res})
        
        talent = t_res.get("talent_pool", [])
        
        # 2. Create foundational tasks based on available workers
        tasks_to_create = [
            {"title": "Arquitectura de Microservicios & Setup FastAPI", "role": "Backend Developer", "hours": 16.0, "prio": "high"},
            {"title": "Diseño de Interfaces & Onboarding KYC en React", "role": "Frontend Developer", "hours": 20.0, "prio": "high"},
            {"title": "Integración de Pasarela de Pagos & SPEI Webhooks", "role": "Backend Developer", "hours": 24.0, "prio": "urgent"},
            {"title": "Pipeline CI/CD en Kubernetes & Observabilidad", "role": "DevOps & Cloud Engineer", "hours": 14.0, "prio": "medium"},
            {"title": "Plan de Pruebas E2E & Automatización con Cypress", "role": "QA Automation Engineer", "hours": 18.0, "prio": "high"}
        ]
        
        for t in tasks_to_create:
            # Match talent by role
            assignee = "Ana Morales"
            for p in talent:
                if t["role"].lower() in p["role"].lower():
                    assignee = p["name"]
                    break
            
            args = {
                "title": t["title"],
                "description": f"Alcance crítico para el MVP según especificación ATS.",
                "role_required": t["role"],
                "estimated_hours": t["hours"],
                "assignee_name": assignee,
                "priority": t["prio"]
            }
            c_res = execute_tool(workspace_id, "create_task", args)
            executed_tools.append({"tool": "create_task", "args": args})
            tool_results.append({"tool": "create_task", "result": c_res})
        
        final_text = f"¡Planificación del MVP completada con éxito! He analizado los {len(talent)} perfiles del ATS y asignado las 5 tareas estructurales en el tablero Kanban según la especialidad de cada desarrollador. Las tareas ya están en progreso en el flujo de trabajo."

    elif "standup" in user_lower or "daily" in user_lower or "estado" in user_lower or "cómo vamos" in user_lower:
        s_res = execute_tool(workspace_id, "generate_daily_standup_report", {})
        executed_tools.append({"tool": "generate_daily_standup_report", "args": {}})
        tool_results.append({"tool": "generate_daily_standup_report", "result": s_res})
        
        summary = s_res.get("standup_summary", [])
        lines = ["**Reporte de Daily Standup:**\n"]
        for s in summary:
            lines.append(f"• **{s['assignee']}** en *{s['task']}*: {s['progress_percent']} completado [{s['status']}]")
        final_text = "\n".join(lines)

    elif "contratar" in user_lower or "nuevo" in user_lower or "hiring" in user_lower:
        args = {
            "role": "Mobile Developer (React Native / iOS)",
            "required_skills": "React Native, Swift, TypeScript, Mobile Security",
            "urgency": "high",
            "rationale": "El cliente solicitó soporte para aplicaciones móviles nativas y el equipo actual está 100% enfocado en el stack web/backend."
        }
        h_res = execute_tool(workspace_id, "request_new_hire", args)
        executed_tools.append({"tool": "request_new_hire", "args": args})
        tool_results.append({"tool": "request_new_hire", "result": h_res})
        final_text = "He emitido una **Requisición Formal de Contratación** para un *Mobile Developer* con urgencia alta. Puedes ver los detalles en la pestaña de Contrataciones del panel lateral."

    else:
        final_text = f"Entendido. Como PM del equipo, estoy monitoreando el avance del proyecto y los tiempos de entrega. Puedes pedirme: *'Planifica el MVP'*, *'Genera la Daily Standup'* o *'Revisa si necesitamos contratar gente'*."

    if error_msg:
        final_text += f"\n\n*(Nota: Se usó modo de respaldo local debido a: {error_msg}. Verifica tu API Key en la barra superior).* "

    # Save Assistant message
    agent_msg_id = f"msg-hermes-{int(time.time()*1000)}"
    conn.execute("""
    INSERT INTO chat_messages (id, workspace_id, sender, sender_name, content, message_type, metadata, created_at)
    VALUES (?, ?, 'hermes', 'Hermes (PM Autónomo)', ?, 'chat', ?, ?);
    """, (agent_msg_id, workspace_id, final_text, json.dumps({"tools": executed_tools}), datetime.utcnow().isoformat()))

    # Save Trajectory
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
