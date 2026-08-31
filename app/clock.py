import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Set, Dict, Any, List
from app.db import get_db_connection

class SimulationEngine:
    def __init__(self):
        self.active_listeners: Set[asyncio.Queue] = set()
        self.is_running = False
        self._task: asyncio.Task = None

    def get_state(self) -> Dict[str, Any]:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM global_simulation WHERE id = 1;").fetchone()
        conn.close()
        if row:
            sim_dt = datetime.fromisoformat(row["current_sim_time"])
            return {
                "current_sim_time": row["current_sim_time"],
                "formatted_time": sim_dt.strftime("%d %b %Y, %I:%M %p"),
                "day_number": (sim_dt.date() - datetime(2030, 9, 12).date()).days + 1,
                "hour": sim_dt.hour,
                "minute": sim_dt.minute,
                "speed_multiplier": row["speed_multiplier"],
                "status": row["status"],
                "active_events": json.loads(row["active_events"])
            }
        return {}

    def set_speed(self, speed_multiplier: float, status: str = None) -> Dict[str, Any]:
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
            # Set to 09:00 AM on the new day
            new_dt = new_dt.replace(hour=9, minute=0, second=0)
            conn.execute("""
            UPDATE global_simulation
            SET current_sim_time = ?, last_real_timestamp = ?
            WHERE id = 1;
            """, (new_dt.isoformat(), time.time()))
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
        # Keep last 5 events
        events = events[-5:]
        conn.execute("UPDATE global_simulation SET active_events = ? WHERE id = 1;", (json.dumps(events),))
        
        # Also post a system message to all workspaces
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
                # 1 real second = (speed * 60) simulated seconds (e.g. speed=1 -> 1 min sim/sec; speed=5 -> 5 min sim/sec; speed=30 -> 30 min sim/sec)
                sim_delta_seconds = speed * 60
                curr_dt = datetime.fromisoformat(row["current_sim_time"])
                next_dt = curr_dt + timedelta(seconds=sim_delta_seconds)

                conn.execute("""
                UPDATE global_simulation
                SET current_sim_time = ?, last_real_timestamp = ?
                WHERE id = 1;
                """, (next_dt.isoformat(), time.time()))

                # Advance task progress if within working hours (09:00 - 18:00) on weekdays (0-4)
                if next_dt.weekday() < 5 and 9 <= next_dt.hour < 18:
                    sim_hours_worked = sim_delta_seconds / 3600.0
                    
                    # Fetch all in_progress tasks
                    in_progress_tasks = conn.execute("""
                        SELECT t.id, t.workspace_id, t.estimated_hours, t.completed_hours, t.assignee_id,
                               p.productivity_factor, p.seniority, p.availability_status
                        FROM tasks t
                        LEFT JOIN talent_profiles p ON t.assignee_id = p.id
                        WHERE t.status = 'in_progress' AND (p.availability_status IS NULL OR p.availability_status != 'sick');
                    """).fetchall()

                    for task in in_progress_tasks:
                        factor = task["productivity_factor"] if task["productivity_factor"] else 1.0
                        delta_comp = sim_hours_worked * factor
                        new_comp = min(task["estimated_hours"] * 1.05, task["completed_hours"] + delta_comp)
                        
                        new_status = "in_progress"
                        if new_comp >= task["estimated_hours"]:
                            new_status = "done"
                        elif new_comp >= task["estimated_hours"] * 0.85:
                            new_status = "review"

                        conn.execute("""
                        UPDATE tasks
                        SET completed_hours = ?, status = ?, updated_at = ?
                        WHERE id = 1;
                        """ if False else """
                        UPDATE tasks
                        SET completed_hours = ?, status = ?, updated_at = ?
                        WHERE id = ?;
                        """, (new_comp, new_status, datetime.utcnow().isoformat(), task["id"]))

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
