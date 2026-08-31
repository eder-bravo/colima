import os
import json
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import init_db, get_db_connection, ensure_workspace_skills
from app.clock import sim_engine
from app.generator_assets import generate_all_samples, SAMPLES_DIR
from app.ats import parse_cv_pdf
from app.agent import run_hermes_agent, execute_tool

INSTRUCTOR_PIN_FILE = os.getenv("INSTRUCTOR_PIN_FILE", "/run/secrets/instructor_pin")

def get_instructor_pin() -> str:
    if os.path.exists(INSTRUCTOR_PIN_FILE):
        try:
            with open(INSTRUCTOR_PIN_FILE, "r") as f:
                return f.read().strip()
        except Exception:
            pass
    return os.getenv("INSTRUCTOR_PIN", "colima2026")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    generate_all_samples()
    loop_task = asyncio.create_task(sim_engine.run_loop())
    yield
    sim_engine.is_running = False
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="Colima — Asistentes PM Autónomos con IA",
    description="Portal de práctica interactiva para talleres de gestión de software con IA y agentes autónomos.",
    version="1.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
async def healthz():
    state = sim_engine.get_state()
    return {
        "status": "healthy",
        "service": "colima-workshop",
        "simulation": state.get("status", "unknown"),
        "sim_time": state.get("formatted_time", "unknown"),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/simulation/stream")
async def simulation_stream(request: Request):
    queue = asyncio.Queue()
    sim_engine.add_listener(queue)

    async def event_generator():
        try:
            initial_state = sim_engine.get_state()
            yield f"data: {json.dumps({'type': 'clock_update', 'data': initial_state})}\n\n"
            
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            sim_engine.remove_listener(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/simulation/state")
async def get_simulation_state():
    return sim_engine.get_state()

# ==================== Instructor Endpoints ====================
class InstructorAuth(BaseModel):
    pin: str

class SpeedRequest(BaseModel):
    pin: str
    speed_multiplier: float

class EventInjectionRequest(BaseModel):
    pin: str
    title: str
    description: str
    severity: str = "warning"

def verify_pin(provided_pin: str):
    real_pin = get_instructor_pin()
    if provided_pin.strip() != real_pin.strip():
        raise HTTPException(status_code=401, detail="PIN de Instructor incorrecto.")

@app.post("/api/instructor/verify")
async def instructor_verify(req: InstructorAuth):
    verify_pin(req.pin)
    return {"status": "authenticated", "message": "Acceso autorizado."}

@app.post("/api/instructor/speed")
async def instructor_set_speed(req: SpeedRequest):
    verify_pin(req.pin)
    state = sim_engine.set_speed(req.speed_multiplier)
    return {"status": "ok", "state": state}

@app.post("/api/instructor/step-day")
async def instructor_step_day(req: InstructorAuth):
    verify_pin(req.pin)
    state = sim_engine.step_day(1)
    return {"status": "ok", "state": state}

@app.post("/api/instructor/reset")
async def instructor_reset(req: InstructorAuth):
    verify_pin(req.pin)
    state = sim_engine.reset_clock()
    return {"status": "ok", "state": state}

@app.post("/api/instructor/inject-event")
async def instructor_inject_event(req: EventInjectionRequest):
    verify_pin(req.pin)
    evt = sim_engine.inject_global_event(req.title, req.description, req.severity)
    return {"status": "ok", "event": evt}

@app.get("/api/instructor/stats")
async def instructor_stats(pin: Optional[str] = None, x_instructor_pin: Optional[str] = Header(None)):
    provided_pin = pin or x_instructor_pin or ""
    verify_pin(provided_pin)
    
    conn = get_db_connection()
    workspaces_count = conn.execute("SELECT COUNT(*) as count FROM workspaces;").fetchone()["count"]
    tasks_count = conn.execute("SELECT COUNT(*) as count FROM tasks;").fetchone()["count"]
    talent_count = conn.execute("SELECT COUNT(*) as count FROM talent_profiles;").fetchone()["count"]
    hiring_count = conn.execute("SELECT COUNT(*) as count FROM hiring_requests;").fetchone()["count"]
    conn.close()

    return {
        "active_students": len(sim_engine.active_listeners),
        "total_workspaces": workspaces_count,
        "total_tasks": tasks_count,
        "total_talent": talent_count,
        "total_hiring_requests": hiring_count,
        "clock": sim_engine.get_state()
    }

# ==================== Student & Workspace Endpoints ====================
def ensure_workspace(workspace_id: str, student_name: str = "Alumno"):
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM workspaces WHERE id = ?;", (workspace_id,)).fetchone()
    if not row:
        conn.execute("""
        INSERT INTO workspaces (id, name, created_at)
        VALUES (?, ?, ?);
        """, (workspace_id, student_name, datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()
    ensure_workspace_skills(workspace_id)

@app.get("/api/workspaces/{workspace_id}")
async def get_workspace_data(workspace_id: str, student_name: str = "Alumno"):
    ensure_workspace(workspace_id, student_name)
    conn = get_db_connection()
    
    ws = conn.execute("SELECT * FROM workspaces WHERE id = ?;", (workspace_id,)).fetchone()
    talent_rows = conn.execute("SELECT * FROM talent_profiles WHERE workspace_id = ? ORDER BY created_at ASC;", (workspace_id,)).fetchall()
    task_rows = conn.execute("SELECT * FROM tasks WHERE workspace_id = ? ORDER BY created_at ASC;", (workspace_id,)).fetchall()
    skills_rows = conn.execute("SELECT * FROM skills WHERE workspace_id = ? ORDER BY id ASC;", (workspace_id,)).fetchall()
    cal_rows = conn.execute("SELECT * FROM calendar_events WHERE workspace_id = ? ORDER BY created_at DESC;", (workspace_id,)).fetchall()
    dec_rows = conn.execute("SELECT * FROM managerial_decisions WHERE workspace_id = ? ORDER BY created_at DESC;", (workspace_id,)).fetchall()
    hiring_rows = conn.execute("SELECT * FROM hiring_requests WHERE workspace_id = ? ORDER BY created_at DESC;", (workspace_id,)).fetchall()
    msg_rows = conn.execute("SELECT * FROM chat_messages WHERE workspace_id = ? ORDER BY created_at ASC;", (workspace_id,)).fetchall()
    traj_rows = conn.execute("SELECT * FROM agent_trajectories WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 10;", (workspace_id,)).fetchall()
    
    talent = []
    for r in talent_rows:
        talent.append({
            "id": r["id"],
            "name": r["name"],
            "role": r["role"],
            "seniority": r["seniority"],
            "skills": json.loads(r["skills"]) if r["skills"] else [],
            "productivity_factor": r["productivity_factor"],
            "status": r["availability_status"]
        })

    tasks = []
    for r in task_rows:
        pct = round((r["completed_hours"] / r["estimated_hours"] * 100) if r["estimated_hours"] > 0 else 0)
        tasks.append({
            "id": r["id"],
            "title": r["title"],
            "description": r["description"],
            "role_required": r["role_required"],
            "estimated_hours": r["estimated_hours"],
            "completed_hours": round(r["completed_hours"], 1),
            "progress_percent": min(100, pct),
            "status": r["status"],
            "assignee_id": r["assignee_id"],
            "assignee_name": r["assignee_name"],
            "priority": r["priority"],
            "blocker_reason": r["blocker_reason"]
        })

    messages = [dict(m) for m in msg_rows]
    trajectories = []
    for t in traj_rows:
        trajectories.append({
            "id": t["id"],
            "prompt_used": t["prompt_used"],
            "thoughts": t["thoughts"],
            "tool_calls": json.loads(t["tool_calls"]) if t["tool_calls"] else [],
            "tool_results": json.loads(t["tool_results"]) if t["tool_results"] else [],
            "final_response": t["final_response"],
            "created_at": t["created_at"]
        })

    conn.close()

    return {
        "workspace": dict(ws),
        "talent_pool": talent,
        "tasks": tasks,
        "skills": [dict(s) for s in skills_rows],
        "calendar_events": [dict(c) for c in cal_rows],
        "managerial_decisions": [dict(d) for d in dec_rows],
        "hiring_requests": [dict(h) for h in hiring_rows],
        "messages": messages,
        "trajectories": trajectories
    }

@app.post("/api/workspaces/{workspace_id}/setup-demo")
async def setup_demo_workspace(workspace_id: str):
    ensure_workspace(workspace_id)
    conn = get_db_connection()
    
    profiles = [
        {"name": "Ana Morales", "role": "Senior Fullstack Engineer", "seniority": "Senior", "skills": ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Docker"], "prod": 1.35},
        {"name": "Carlos Ruiz", "role": "Junior Frontend Developer", "seniority": "Junior", "skills": ["JavaScript", "HTML5", "CSS3", "React", "TailwindCSS"], "prod": 0.75},
        {"name": "Lucía Méndez", "role": "Senior QA Automation Engineer", "seniority": "Senior", "skills": ["QA Automation", "Cypress", "Playwright", "TestRail", "Postman"], "prod": 1.30},
        {"name": "Roberto Silva", "role": "DevOps & Cloud Engineer", "seniority": "Senior", "skills": ["Docker", "Kubernetes", "Terraform", "CI/CD", "Linux"], "prod": 1.25},
        {"name": "Diego Torres", "role": "Mid Backend Developer", "seniority": "Mid", "skills": ["Node.js", "Express", "TypeScript", "PostgreSQL", "Stripe API"], "prod": 1.0}
    ]

    for p in profiles:
        pid = f"tal-{workspace_id}-{p['name'].lower().replace(' ', '-')}"
        conn.execute("""
        INSERT OR REPLACE INTO talent_profiles (id, workspace_id, name, role, seniority, skills, productivity_factor, availability_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'available', ?);
        """, (pid, workspace_id, p["name"], p["role"], p["seniority"], json.dumps(p["skills"]), p["prod"], datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()
    return {"status": "ok", "loaded_profiles": len(profiles)}

@app.post("/api/workspaces/{workspace_id}/upload-cv")
async def upload_cv(workspace_id: str, file: UploadFile = File(...)):
    ensure_workspace(workspace_id)
    contents = await file.read()
    
    parsed = parse_cv_pdf(contents, file.filename)
    pid = f"tal-{workspace_id}-{int(datetime.utcnow().timestamp()*1000)}"
    
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO talent_profiles (id, workspace_id, name, role, seniority, skills, productivity_factor, availability_status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'available', ?);
    """, (pid, workspace_id, parsed["name"], parsed["role"], parsed["seniority"], json.dumps(parsed["skills"]), parsed["productivity_factor"], datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "profile": {
            "id": pid,
            "name": parsed["name"],
            "role": parsed["role"],
            "seniority": parsed["seniority"],
            "skills": parsed["skills"],
            "productivity_factor": parsed["productivity_factor"]
        }
    }

class SkillToggleRequest(BaseModel):
    skill_id: str
    is_active: bool

@app.post("/api/workspaces/{workspace_id}/skills/toggle")
async def toggle_skill(workspace_id: str, req: SkillToggleRequest):
    ensure_workspace(workspace_id)
    conn = get_db_connection()
    conn.execute("""
    UPDATE skills
    SET is_active = ?
    WHERE id = ? AND workspace_id = ?;
    """, (1 if req.is_active else 0, req.skill_id, workspace_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "skill_id": req.skill_id, "is_active": req.is_active}

class SkillUpdateRequest(BaseModel):
    skill_id: str
    prompt_instructions: str

@app.post("/api/workspaces/{workspace_id}/skills/update")
async def update_skill_prompt(workspace_id: str, req: SkillUpdateRequest):
    ensure_workspace(workspace_id)
    conn = get_db_connection()
    conn.execute("""
    UPDATE skills
    SET prompt_instructions = ?
    WHERE id = ? AND workspace_id = ?;
    """, (req.prompt_instructions, req.skill_id, workspace_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

class DecisionResponseRequest(BaseModel):
    status: str  # 'approved' or 'rejected'
    comment: Optional[str] = None

@app.post("/api/workspaces/{workspace_id}/decisions/{decision_id}/respond")
async def respond_decision(workspace_id: str, decision_id: str, req: DecisionResponseRequest):
    conn = get_db_connection()
    conn.execute("""
    UPDATE managerial_decisions
    SET status = ?, response_comment = ?
    WHERE id = ? AND workspace_id = ?;
    """, (req.status, req.comment, decision_id, workspace_id))
    
    # Also add a message from Manager to the chat
    action_label = "APROBADA ✅" if req.status == "approved" else "RECHAZADA ❌"
    conn.execute("""
    INSERT INTO chat_messages (id, workspace_id, sender, sender_name, content, message_type, metadata, created_at)
    VALUES (?, ?, 'system', 'Dirección Gerencial', ?, 'alert', '{}', ?);
    """, (
        f"msg-gov-{int(datetime.utcnow().timestamp()*1000)}",
        workspace_id,
        f"La solicitud gerencial ha sido **{action_label}** por la Dirección.\nComentario: {req.comment or 'Sin comentarios adicionales.'}",
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()
    return {"status": "ok"}

class ChatRequest(BaseModel):
    message: str
    custom_system_prompt: Optional[str] = None

@app.post("/api/workspaces/{workspace_id}/agent/chat")
async def agent_chat(
    workspace_id: str,
    req: ChatRequest,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key")
):
    ensure_workspace(workspace_id)
    result = await run_hermes_agent(
        workspace_id=workspace_id,
        user_message=req.message,
        api_key=x_gemini_api_key,
        custom_system_prompt=req.custom_system_prompt
    )
    return result

@app.post("/api/workspaces/{workspace_id}/chat/clear")
async def clear_chat_history(workspace_id: str):
    ensure_workspace(workspace_id)
    conn = get_db_connection()
    conn.execute("DELETE FROM chat_messages WHERE workspace_id = ?;", (workspace_id,))
    conn.commit()
    conn.close()
    return {"status": "cleared"}


@app.get("/api/samples/{filename}")
async def get_sample_file(filename: str):
    safe_name = os.path.basename(filename)
    fp = os.path.join(SAMPLES_DIR, safe_name)
    if not os.path.exists(fp):
        generate_all_samples()
    if os.path.exists(fp):
        return FileResponse(fp, filename=safe_name)
    raise HTTPException(status_code=404, detail="Archivo no encontrado.")

app.mount("/static", StaticFiles(directory="/app/app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index_page():
    with open("/app/app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/instructor", response_class=HTMLResponse)
async def instructor_page():
    with open("/app/app/static/instructor.html", "r", encoding="utf-8") as f:
        return f.read()
