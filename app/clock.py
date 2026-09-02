import os
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set, Optional
from app.db import get_db_connection

def simulation_tick_workspaces(conn, sim_hours_worked: float):
    now_iso = datetime.utcnow().isoformat()
    workspaces = conn.execute("SELECT id FROM workspaces;").fetchall()
    
    for ws in workspaces:
        ws_id = ws["id"]
        
        # 1. Backlog -> In Progress (Pick up next task when worker has no in_progress task)
        talents = conn.execute("SELECT id, name, role FROM talent_profiles WHERE workspace_id = ?;", (ws_id,)).fetchall()
        for t in talents:
            active_cnt = conn.execute("""
                SELECT COUNT(*) as cnt FROM tasks 
                WHERE workspace_id = ? AND status = 'in_progress' AND (assignee_id = ? OR assignee_name = ?);
            """, (ws_id, t["id"], t["name"])).fetchone()["cnt"]
            
            if active_cnt == 0:
                role_keyword = t["role"].split()[-1] if t["role"] else ""
                task = conn.execute("""
                    SELECT id, title FROM tasks 
                    WHERE workspace_id = ? AND status = 'backlog' 
                      AND (assignee_id = ? OR assignee_name = ? OR (assignee_name IS NULL AND role_required LIKE ?))
                    ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at ASC
                    LIMIT 1;
                """, (ws_id, t["id"], t["name"], f"%{role_keyword}%")).fetchone()
                
                if task:
                    conn.execute("""
                        UPDATE tasks 
                        SET status = 'in_progress', assignee_id = ?, assignee_name = ?, updated_at = ?
                        WHERE id = ?;
                    """, (t["id"], t["name"], now_iso, task["id"]))
                    conn.execute("""
                        UPDATE talent_profiles
                        SET availability_status = 'busy', current_task_id = ?
                        WHERE id = ?;
                    """, (task["id"], t["id"]))

        # 2. Advance In-Progress tasks (Development phase)
        if sim_hours_worked > 0:
            in_progress_tasks = conn.execute("""
                SELECT t.id, t.estimated_hours, t.completed_hours, p.productivity_factor
                FROM tasks t
                LEFT JOIN talent_profiles p ON t.assignee_id = p.id
                WHERE t.workspace_id = ? AND t.status = 'in_progress' AND (t.blocker_reason IS NULL OR t.blocker_reason = '');
            """, (ws_id,)).fetchall()

            for task in in_progress_tasks:
                factor = task["productivity_factor"] if task["productivity_factor"] else 1.0
                delta_comp = sim_hours_worked * factor
                new_comp = task["completed_hours"] + delta_comp
                
                # Check if dev completed their part -> Moves to 'review' for QA / Hermes PM inspection
                if new_comp >= task["estimated_hours"]:
                    conn.execute("""
                    UPDATE tasks
                    SET completed_hours = estimated_hours, status = 'review', review_hours = 0.0, updated_at = ?
                    WHERE id = ?;
                    """, (now_iso, task["id"]))
                else:
                    conn.execute("""
                    UPDATE tasks
                    SET completed_hours = ?, status = 'in_progress', updated_at = ?
                    WHERE id = ?;
                    """, (round(new_comp, 1), now_iso, task["id"]))

        # 3. Advance Review Phase for tasks in 'review' (Hermes & QA Evaluation)
        # Real-world behavior: Tasks stay in review for ~4h of simulated review time
        if sim_hours_worked > 0:
            review_tasks = conn.execute("""
                SELECT id, title, role_required, estimated_hours, completed_hours, assignee_name, assignee_id, review_feedback, review_hours
                FROM tasks
                WHERE workspace_id = ? AND status = 'review';
            """, (ws_id,)).fetchall()

            for task in review_tasks:
                current_rev = task["review_hours"] if task["review_hours"] is not None else 0.0
                new_rev = current_rev + (sim_hours_worked * 0.5)
                required_review_hours = 4.0
                
                if new_rev < required_review_hours:
                    # Still undergoing review
                    conn.execute("UPDATE tasks SET review_hours = ?, updated_at = ? WHERE id = ?;", (round(new_rev, 1), now_iso, task["id"]))
                else:
                    # Review completed! Generate feedback and move to 'done'
                    title_lower = task["title"].lower()
                    
                    if any(k in title_lower for k in ["scoring", "riesgo", "algoritmo"]):
                        feedback = "Hermes PM: Aprobado tras revisión técnica. Reglas de cálculo crediticio validadas contra matriz de riesgo y cobertura de tests al 94%."
                        followup_title = "Optimización de Caché en Redis para Scoring Crediticio"
                        followup_role = "Senior Fullstack Engineer"
                        followup_hours = 12.0
                    elif any(k in title_lower for k in ["react", "frontend", "kyc", "portal", "ui", "onboarding", "administración", "administracion"]):
                        feedback = "Hermes PM: Aprobado. Interfaces responsivas y accesibles; flujo validado sin fricciones en mobile y desktop."
                        followup_title = "Componentes de Alertas y Notificaciones en Vivo en React"
                        followup_role = "Junior Frontend Developer"
                        followup_hours = 10.0
                    elif any(k in title_lower for k in ["pago", "spei", "webhook", "stripe", "dispersión", "dispersion"]):
                        feedback = "Hermes PM: Aprobado tras pruebas sandbox. Webhooks y dispersión SPEI validados con idempotencia y manejo de reintentos."
                        followup_title = "Módulo de Conciliación Automática de Saldos y Reportes Financieros"
                        followup_role = "Mid Backend Developer"
                        followup_hours = 16.0
                    elif any(k in title_lower for k in ["docker", "ci/cd", "kubernetes", "cloud", "pipeline", "infraestructura"]):
                        feedback = "Hermes PM: Aprobado. Pipeline CI/CD automatizado con escaneo de vulnerabilidades y despliegue reproducible en clúster."
                        followup_title = "Monitoreo de Métricas y Alertas de Latencia con Prometheus"
                        followup_role = "DevOps & Cloud Engineer"
                        followup_hours = 12.0
                    elif any(k in title_lower for k in ["qa", "cypress", "prueba", "test", "e2e"]):
                        feedback = "Hermes PM: Aprobado. Suite de pruebas E2E ejecutada con éxito y matriz de cobertura validada para pase a producción."
                        followup_title = "Pruebas de Carga y Concurrencia de API con k6"
                        followup_role = "Senior QA Automation Engineer"
                        followup_hours = 14.0
                    else:
                        feedback = "Hermes PM: Aprobado. Criterios de aceptación y calidad cumplidos satisfactoriamente tras revisión técnica."
                        followup_title = None
                        followup_role = None
                        followup_hours = 0.0

                    conn.execute("""
                        UPDATE tasks 
                        SET status = 'done', completed_hours = estimated_hours, review_hours = ?, review_feedback = ?, updated_at = ?
                        WHERE id = ?;
                    """, (required_review_hours, feedback, now_iso, task["id"]))

                    # Free the developer in talent_profiles
                    if task["assignee_id"]:
                        conn.execute("UPDATE talent_profiles SET availability_status = 'available', current_task_id = NULL WHERE id = ?;", (task["assignee_id"],))

                    # Insert Hermes review insight in inbox
                    inbox_id = f"inbox-{int(time.time()*1000)}-{task['id']}"
                    conn.execute("""
                        INSERT INTO hermes_inbox (id, workspace_id, type, title, body, read, sim_time, created_at)
                        VALUES (?, ?, 'insight', ?, ?, 0, 'Sprint 1', ?);
                    """, (
                        inbox_id,
                        ws_id,
                        f"Revisión Aprobada: {task['title']}",
                        f"Hermes ha revisado la entrega de {task['assignee_name'] or 'desarrollador'}.\n\nFeedback: {feedback}",
                        now_iso
                    ))

                    # Spawn follow-up task if applicable
                    if followup_title:
                        exists = conn.execute("SELECT id FROM tasks WHERE workspace_id = ? AND title = ?;", (ws_id, followup_title)).fetchone()
                        if not exists:
                            new_tsk_id = f"tsk-auto-{int(time.time()*1000)}-{task['id']}"
                            conn.execute("""
                                INSERT INTO tasks (id, workspace_id, title, description, role_required, estimated_hours, completed_hours, status, assignee_id, assignee_name, priority, created_at, updated_at)
                                VALUES (?, ?, ?, 'Tarea de mejora generada automáticamente por Hermes tras revisión de sprint.', ?, ?, 0.0, 'backlog', ?, ?, 'medium', ?, ?);
                            """, (new_tsk_id, ws_id, followup_title, followup_role, followup_hours, task["assignee_id"], task["assignee_name"], now_iso, now_iso))

        # 4. Recompute suggestions and burnout alerts (ONLY pending hours!)
        talents_all = conn.execute("SELECT id, name, role FROM talent_profiles WHERE workspace_id = ?;", (ws_id,)).fetchall()
        tasks_all = conn.execute("SELECT id, title, assignee_name, estimated_hours, completed_hours, status FROM tasks WHERE workspace_id = ?;", (ws_id,)).fetchall()
        workload = {t["name"]: 0.0 for t in talents_all}
        for task in tasks_all:
            name = task["assignee_name"]
            if name and name in workload and task["status"] not in ("done", "review"):
                workload[name] += max(0.0, task["estimated_hours"] - task["completed_hours"])
        
        for name, hrs in workload.items():
            slug = name.lower().replace(' ', '-')
            if hrs > 30.0:
                s_id = f"sug-{ws_id}-overload-{slug}"
                conn.execute("""
                INSERT OR IGNORE INTO pm_suggestions (id, workspace_id, category, title, description, recommendation, action_type, action_payload, status, created_at)
                VALUES (?, ?, 'workload', 'Riesgo de Sobrecarga (Burnout)', ?, 'Se sugiere reasignar tareas menores a desarrolladores con disponibilidad.', 'rebalance', ?, 'active', ?);
                """, (s_id, ws_id, f"{name} tiene {hrs:.0f}h pendientes asignadas (límite saludable 30h).", json.dumps({"worker": name, "hours": hrs}), now_iso))

                dec_id = f"dec-{ws_id}-rebalance-{slug}"
                conn.execute("""
                INSERT OR IGNORE INTO managerial_decisions (id, workspace_id, title, description, impact_summary, status, response_comment, created_at)
                VALUES (?, ?, ?, ?, 'Reduce sobrecarga a nivel saludable (~24h) y evita retraso en la entrega del MVP.', 'pending', NULL, ?);
                """, (
                    dec_id, 
                    ws_id, 
                    f"Aprobación: Rebalanceo de Carga ({name})", 
                    f"{name} acumula {hrs:.0f}h de trabajo pendiente en el sprint. Hermes propone reasignar tareas secundarias a perfiles disponibles para balancear la capacidad del equipo.",
                    now_iso
                ))
            else:
                conn.execute("UPDATE pm_suggestions SET status = 'dismissed' WHERE id = ? AND workspace_id = ? AND status = 'active';", (f"sug-{ws_id}-overload-{slug}", ws_id))


class SimulationEngine:
    def __init__(self):
        self.active_listeners: Set[asyncio.Queue] = set()
        self.is_running = False

    def get_state(self) -> Dict[str, Any]:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM global_simulation WHERE id = 1;").fetchone()
        conn.close()
        if not row:
            sim_time_iso = "2030-09-12T09:00:00"
            speed = 0.0
            status = "paused"
            events = []
        else:
            sim_time_iso = row["current_sim_time"]
            speed = row["speed_multiplier"]
            status = row["status"]
            events = json.loads(row["active_events"]) if row["active_events"] else []
        
        sim_dt = datetime.fromisoformat(sim_time_iso)
        base_dt = datetime(2030, 9, 12, 9, 0, 0)
        day_num = max(1, (sim_dt.date() - base_dt.date()).days + 1)
        
        months_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        month_name = months_es[sim_dt.month - 1]
        
        am_pm = "AM" if sim_dt.hour < 12 else "PM"
        hour_12 = sim_dt.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        formatted_time = f"{sim_dt.day} {month_name[:3]}, {hour_12:02d}:{sim_dt.minute:02d} {am_pm}"
        formatted_full_date = f"{sim_dt.day} de {month_name}, {sim_dt.year}"
        
        return {
            "current_sim_time": sim_time_iso,
            "sim_date": sim_dt.strftime("%Y-%m-%d"),
            "sim_day": sim_dt.day,
            "sim_month": sim_dt.month,
            "sim_month_name": month_name,
            "sim_year": sim_dt.year,
            "day_number": day_num,
            "formatted_time": formatted_time,
            "formatted_full_date": formatted_full_date,
            "speed_multiplier": speed,
            "status": status,
            "active_events": events
        }

    def set_speed(self, speed_multiplier: float, status: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        if status is None:
            status = "running" if speed_multiplier > 0 else "paused"
        now_ts = time.time()
        conn.execute("""
        UPDATE global_simulation
        SET speed_multiplier = ?, status = ?, last_real_timestamp = ?
        WHERE id = 1;
        """, (speed_multiplier, status, now_ts))
        conn.commit()
        conn.close()
        state = self.get_state()
        self.broadcast({"type": "clock_update", "data": state})
        return state

    def step_day(self, days: int = 1) -> Dict[str, Any]:
        conn = get_db_connection()
        row = conn.execute("SELECT current_sim_time FROM global_simulation WHERE id = 1;").fetchone()
        if row:
            current_dt = datetime.fromisoformat(row["current_sim_time"])
            new_dt = current_dt + timedelta(days=days)
            new_dt = new_dt.replace(hour=9, minute=0, second=0)
            conn.execute("""
            UPDATE global_simulation
            SET current_sim_time = ?, last_real_timestamp = ?
            WHERE id = 1;
            """, (new_dt.isoformat(), time.time()))

            simulation_tick_workspaces(conn, 8.0 * days)

            conn.commit()
        conn.close()
        state = self.get_state()
        self.broadcast({"type": "clock_update", "data": state})
        return state

    def reset_clock(self) -> Dict[str, Any]:
        conn = get_db_connection()
        conn.execute("""
        UPDATE global_simulation
        SET current_sim_time = '2030-09-12T09:00:00',
            speed_multiplier = 0.0,
            status = 'paused',
            last_real_timestamp = ?,
            active_events = '[]'
        WHERE id = 1;
        """, (time.time(),))
        conn.commit()
        conn.close()
        state = self.get_state()
        self.broadcast({"type": "clock_update", "data": state})
        return state

    def inject_global_event(self, event_title: str, event_description: str, severity: str = "warning") -> Dict[str, Any]:
        conn = get_db_connection()
        row = conn.execute("SELECT active_events FROM global_simulation WHERE id = 1;").fetchone()
        events = json.loads(row["active_events"]) if row else []
        new_event = {
            "id": f"evt-{int(time.time()*1000)}",
            "title": event_title,
            "description": event_description,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }
        events.append(new_event)
        events = events[-5:]
        conn.execute("UPDATE global_simulation SET active_events = ? WHERE id = 1;", (json.dumps(events),))
        
        workspaces = conn.execute("SELECT id FROM workspaces;").fetchall()
        for ws in workspaces:
            conn.execute("""
            INSERT INTO chat_messages (id, workspace_id, sender, sender_name, content, message_type, metadata, created_at)
            VALUES (?, ?, 'system', 'Sistema de Simulación', ?, 'alert', ?, ?);
            """, (
                f"msg-sys-{int(time.time()*1000)}-{ws['id']}",
                ws["id"],
                f"🚨 EVENTO GLOBAL: {event_title}\n{event_description}",
                json.dumps(new_event),
                datetime.utcnow().isoformat()
            ))

        conn.commit()
        conn.close()
        
        self.broadcast({
            "type": "global_event",
            "event": new_event
        })
        return new_event

    def add_listener(self, queue: asyncio.Queue):
        self.active_listeners.add(queue)

    def remove_listener(self, queue: asyncio.Queue):
        self.active_listeners.discard(queue)

    def broadcast(self, message: dict):
        dead = []
        for queue in list(self.active_listeners):
            try:
                queue.put_nowait(message)
            except Exception:
                dead.append(queue)
        for d in dead:
            self.active_listeners.discard(d)

    async def run_loop(self):
        self.is_running = True
        while self.is_running:
            try:
                await asyncio.sleep(1.0)
                conn = get_db_connection()
                row = conn.execute("SELECT * FROM global_simulation WHERE id = 1;").fetchone()
                if not row or row["status"] != "running" or row["speed_multiplier"] <= 0:
                    conn.close()
                    continue

                speed = row["speed_multiplier"]
                sim_delta_seconds = speed * 60
                curr_dt = datetime.fromisoformat(row["current_sim_time"])
                next_dt = curr_dt + timedelta(seconds=sim_delta_seconds)

                conn.execute("""
                UPDATE global_simulation
                SET current_sim_time = ?, last_real_timestamp = ?
                WHERE id = 1;
                """, (next_dt.isoformat(), time.time()))

                sim_hours_worked = (sim_delta_seconds / 3600.0) * 0.33
                simulation_tick_workspaces(conn, sim_hours_worked)

                conn.commit()
                conn.close()

                # Broadcast tick
                state = self.get_state()
                self.broadcast({"type": "clock_update", "data": state})

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ClockWorker Error] {e}")
                await asyncio.sleep(2.0)

sim_engine = SimulationEngine()
