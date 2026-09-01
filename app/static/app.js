// Colima PM Sandbox Application Logic — v5.0

const STORAGE_KEYS = {
  WORKSPACE_ID: 'colima_workspace_id',
  API_KEY: 'colima_gemini_api_key',
  THEME_PREF: 'colima_theme_pref'
};

let workspaceId = localStorage.getItem(STORAGE_KEYS.WORKSPACE_ID);
if (!workspaceId) {
  workspaceId = 'ws-' + Math.random().toString(36).substring(2, 10);
  localStorage.setItem(STORAGE_KEYS.WORKSPACE_ID, workspaceId);
}

let geminiApiKey = localStorage.getItem(STORAGE_KEYS.API_KEY) || '';
let currentEditingSkillId = null;

// DOM Elements
const simDayEl = document.getElementById('sim-day');
const simTimeEl = document.getElementById('sim-time');
const simSpeedBadge = document.getElementById('sim-speed-badge');
const clockPulse = document.getElementById('clock-pulse');
const clockDot = document.getElementById('clock-dot');

const chatMessagesEl = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSubmitBtn = document.getElementById('chat-submit');
const btnClearChat = document.getElementById('btn-clear-chat');

const settingsModal = document.getElementById('settings-modal');
const btnSettings = document.getElementById('btn-settings');
const modalCloseBtn = document.getElementById('modal-close-btn');
const apiKeyInput = document.getElementById('api-key-input');
const btnSaveKey = document.getElementById('btn-save-key');
const apiKeyStatusText = document.getElementById('api-key-status-text');

const samplesModal = document.getElementById('samples-modal');
const btnSamples = document.getElementById('btn-samples');
const samplesCloseBtn = document.getElementById('samples-close-btn');
const btnQuickLoad = document.getElementById('btn-quick-load');

const btnThemeToggle = document.getElementById('btn-theme-toggle');
const themeIcon = document.getElementById('theme-icon');

const cvFileInput = document.getElementById('cv-file-input');
const dropzone = document.getElementById('dropzone');

// Badges & Containers
const workersCountBadge = document.getElementById('workers-count-badge');
const suggestionsCountBadge = document.getElementById('suggestions-count-badge');
const activeSkillsCount = document.getElementById('active-skills-count');

const workersListEl = document.getElementById('workers-list');
const projectTitleDisplay = document.getElementById('project-title-display');
const projectStackDisplay = document.getElementById('project-stack-display');
const calendarContainer = document.getElementById('calendar-container');
const suggestionsContainer = document.getElementById('suggestions-container');
const decisionsContainer = document.getElementById('decisions-container');
const skillsContainer = document.getElementById('skills-container');

// Skill Modal
const skillModal = document.getElementById('skill-modal');
const skillModalTitle = document.getElementById('skill-modal-title');
const skillModalPrompt = document.getElementById('skill-modal-prompt');

// 1. THEME ENGINE
function initTheme() {
  const savedPref = localStorage.getItem(STORAGE_KEYS.THEME_PREF) || 'system';
  applyTheme(savedPref);

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if ((localStorage.getItem(STORAGE_KEYS.THEME_PREF) || 'system') === 'system') {
      applyTheme('system');
    }
  });

  btnThemeToggle.addEventListener('click', () => {
    const current = localStorage.getItem(STORAGE_KEYS.THEME_PREF) || 'system';
    let next = 'light';
    if (current === 'system') next = 'dark';
    else if (current === 'dark') next = 'light';
    else if (current === 'light') next = 'system';
    
    localStorage.setItem(STORAGE_KEYS.THEME_PREF, next);
    applyTheme(next);
  });
}

function applyTheme(pref) {
  const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  let useDark = isSystemDark;

  if (pref === 'dark') {
    useDark = true;
    themeIcon.className = 'fa-solid fa-moon text-xs text-indigo-400';
  } else if (pref === 'light') {
    useDark = false;
    themeIcon.className = 'fa-solid fa-sun text-xs text-amber-500';
  } else {
    themeIcon.className = 'fa-solid fa-circle-half-stroke text-xs text-slate-500';
  }

  if (useDark) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

// 2. STAGE NAVIGATION (Workers, Projects, Calendar, Suggestions, Skills)
function switchStage(stage) {
  document.querySelectorAll('.stage-tab').forEach(tab => {
    tab.className = 'stage-tab font-medium text-xs px-3 py-1.5 rounded-lg transition text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 flex items-center gap-1.5';
  });
  document.querySelectorAll('.stage-view').forEach(view => view.classList.add('hidden'));

  const activeTab = document.getElementById(`tab-stage-${stage}`);
  const activeView = document.getElementById(`stage-${stage}`);

  if (activeTab && activeView) {
    activeTab.className = 'stage-tab font-semibold text-xs px-3 py-1.5 rounded-lg transition text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-500/30 flex items-center gap-1.5 shadow-xs';
    activeView.classList.remove('hidden');
  }
}

// 3. SSE Master Clock Sync
function setupSSE() {
  const evtSource = new EventSource('/api/simulation/stream');
  evtSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'clock_update') {
        renderClockState(payload.data);
        loadWorkspaceData(false);
      } else if (payload.type === 'global_event') {
        appendSystemMessage(`🚨 **EVENTO:** ${payload.event.title}\n${payload.event.description}`);
      } else if (payload.type === 'inbox_update') {
        if (!payload.workspace_id || payload.workspace_id === workspaceId) {
          loadInbox();
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  evtSource.onerror = () => {
    clockPulse.classList.add('hidden');
    clockDot.classList.replace('bg-emerald-500', 'bg-amber-500');
    simSpeedBadge.textContent = 'Reconectando...';
  };
}

function renderClockState(state) {
  if (!state) return;
  simDayEl.textContent = `Día ${state.day_number || 1}`;
  simTimeEl.textContent = state.formatted_time || '12 Sep, 09:00 AM';

  const speed = state.speed_multiplier || 0;
  if (state.status === 'paused' || speed === 0) {
    simSpeedBadge.textContent = 'Pausado';
    simSpeedBadge.className = 'text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300';
    clockPulse.classList.add('hidden');
  } else {
    simSpeedBadge.textContent = `${speed}x`;
    simSpeedBadge.className = 'text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30';
    clockPulse.classList.remove('hidden');
  }
}

// 4. Load Workspace Data
async function loadWorkspaceData(renderChat = true) {
  try {
    const res = await fetch(`/api/workspaces/${workspaceId}`);
    if (!res.ok) return;
    const data = await res.json();

    renderWorkers(data.talent_pool || [], data.tasks || []);
    renderProjects(data.projects || [], data.workspace || {}, data.tasks || []);
    renderCalendar(data.calendar_events || []);
    renderSuggestions(data.pm_suggestions || []);
    renderDecisions(data.managerial_decisions || []);
    renderSkills(data.skills || []);
    loadInbox();

    if (renderChat && data.messages && data.messages.length > 0) {
      renderChatHistory(data.messages);
    }
  } catch (e) {
    console.error('[Load Error]', e);
  }
}

// 5. Section 1: MIS TRABAJADORES
function renderWorkers(talent, tasks) {
  workersListEl.innerHTML = '';
  workersCountBadge.textContent = talent.length;

  if (talent.length === 0) {
    workersListEl.innerHTML = `
      <div class="col-span-2 text-center py-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 text-slate-400 text-xs space-y-2">
        <i class="fa-solid fa-users text-3xl text-slate-300 dark:text-slate-700"></i>
        <p class="font-bold text-slate-700 dark:text-slate-300">No hay trabajadores en el equipo todavía.</p>
        <p class="text-[11px]">Haz clic en "Cargar 5 CVs" en la barra superior o arrastra tus propios PDFs para iniciar el staffing.</p>
      </div>
    `;
    return;
  }

  talent.forEach(p => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 shadow-xs space-y-3';
    
    let seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400">Mid</span>';
    if (p.seniority === 'Senior') {
      seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30">Senior</span>';
    } else if (p.seniority === 'Junior') {
      seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30">Junior</span>';
    }

    // Calculate worker workload
    const workerTasks = tasks.filter(t => t.assignee_name && t.assignee_name.toLowerCase().includes(p.name.toLowerCase()));
    const totalHours = workerTasks.reduce((acc, t) => acc + (t.estimated_hours || 0), 0);
    const completedHours = workerTasks.reduce((acc, t) => acc + (t.completed_hours || 0), 0);

    let saturationBadge = '<span class="text-[10px] font-medium text-emerald-600 dark:text-emerald-400">● Disponible</span>';
    if (totalHours > 30) {
      saturationBadge = '<span class="text-[10px] font-bold text-rose-600 dark:text-rose-400">⚠️ Sobrecargado</span>';
    } else if (totalHours > 0) {
      saturationBadge = '<span class="text-[10px] font-medium text-blue-600 dark:text-blue-400">● En Asignación</span>';
    }

    const skillsPills = (p.skills || []).map(s => 
      `<span class="text-[9px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded-md">${escapeHtml(s)}</span>`
    ).join(' ');

    const initial = p.name.charAt(0).toUpperCase();

    card.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl bg-indigo-50 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold text-sm">
            ${initial}
          </div>
          <div>
            <h4 class="font-bold text-xs text-slate-900 dark:text-white leading-tight">${escapeHtml(p.name)}</h4>
            <p class="text-[11px] text-slate-500">${escapeHtml(p.role)}</p>
          </div>
        </div>
        ${seniorityBadge}
      </div>

      <div class="flex flex-wrap gap-1">
        ${skillsPills}
      </div>

      <div class="bg-slate-50 dark:bg-slate-950 p-2.5 rounded-xl space-y-1.5 text-[11px]">
        <div class="flex items-center justify-between text-slate-600 dark:text-slate-300">
          <span>Tareas Asignadas: <b>${workerTasks.length}</b></span>
          <span>Carga: <b>${completedHours}h / ${totalHours}h</b></span>
        </div>
        <div class="w-full h-1 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full bg-indigo-500 rounded-full" style="width: ${totalHours > 0 ? Math.min(100, Math.round(completedHours/totalHours*100)) : 0}%"></div>
        </div>
      </div>

      <div class="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800 text-[10px] text-slate-400">
        <span>Factor Productividad: <b class="text-slate-700 dark:text-slate-200">${p.productivity_factor}x</b></span>
        ${saturationBadge}
      </div>
    `;
    workersListEl.appendChild(card);
  });
}

// 6. Section 2: MIS PROYECTOS & KANBAN
function renderProjects(projects, ws, tasks) {
  if (projects && projects.length > 0) {
    const p = projects[0];
    projectTitleDisplay.textContent = p.title;
    projectStackDisplay.textContent = `Stack: ${p.tech_stack || 'FastAPI, React'} • Meta: ${p.target_deadline || '30 días'}`;
  } else if (ws.project_name) {
    projectTitleDisplay.textContent = ws.project_name;
    projectStackDisplay.textContent = `Stack: FastAPI, React, Docker • Meta: 30 días`;
  }

  // Render Kanban Board
  const cols = {
    backlog: document.getElementById('col-backlog'),
    in_progress: document.getElementById('col-in_progress'),
    review: document.getElementById('col-review'),
    done: document.getElementById('col-done')
  };
  const counts = { backlog: 0, in_progress: 0, review: 0, done: 0 };
  Object.values(cols).forEach(c => c.innerHTML = '');

  tasks.forEach(task => {
    const status = task.status in cols ? task.status : 'backlog';
    counts[status]++;

    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-xl p-3 shadow-xs hover:shadow-sm transition space-y-2.5 cursor-pointer';

    let priorityBadge = '<span class="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">Normal</span>';
    if (task.priority === 'urgent') {
      priorityBadge = '<span class="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">Urgente</span>';
    } else if (task.priority === 'high') {
      priorityBadge = '<span class="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">Alta</span>';
    }

    const assigneeName = task.assignee_name || 'Sin asignar';
    const initial = assigneeName.charAt(0).toUpperCase();

    card.innerHTML = `
      <div class="flex items-start justify-between gap-1.5">
        <h4 class="font-medium text-xs text-slate-800 dark:text-slate-100 leading-snug">${escapeHtml(task.title)}</h4>
        ${priorityBadge}
      </div>
      
      <div class="flex items-center justify-between text-[11px] pt-0.5">
        <div class="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
          <span class="w-4 h-4 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-[9px] font-bold">
            ${initial}
          </span>
          <span class="text-[11px]">${escapeHtml(assigneeName)}</span>
        </div>
        <span class="font-mono text-[10px] font-semibold text-indigo-600 dark:text-indigo-400">${task.progress_percent}%</span>
      </div>

      <div class="w-full h-1 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div class="h-full bg-indigo-500 rounded-full task-progress-bar" style="width: ${task.progress_percent}%"></div>
      </div>
    `;

    cols[status].appendChild(card);
  });

  Object.keys(cols).forEach(key => {
    if (counts[key] === 0) {
      cols[key].innerHTML = `
        <div class="h-20 border border-dashed border-slate-200 dark:border-slate-800/80 rounded-xl flex items-center justify-center text-[11px] text-slate-400 dark:text-slate-600">
          Sin tareas
        </div>
      `;
    }
  });

  document.getElementById('count-backlog').textContent = counts.backlog;
  document.getElementById('count-in_progress').textContent = counts.in_progress;
  document.getElementById('count-review').textContent = counts.review;
  document.getElementById('count-done').textContent = counts.done;
}

// 7. Section 3: MI CALENDARIO
function renderCalendar(events) {
  calendarContainer.innerHTML = '';
  if (events.length === 0) {
    calendarContainer.innerHTML = '<p class="col-span-2 text-slate-400 text-xs py-4 text-center">No hay reuniones ni ceremonias agendadas en el calendario aún.</p>';
    return;
  }

  events.forEach(evt => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-3.5 shadow-xs space-y-1.5';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-xs text-slate-900 dark:text-white">${escapeHtml(evt.title)}</h4>
        <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">${escapeHtml(evt.time_slot)}</span>
      </div>
      <p class="text-[11px] text-slate-500 font-medium">📅 ${escapeHtml(evt.sim_date)} • 👥 ${escapeHtml(evt.attendees)}</p>
      <p class="text-xs text-slate-600 dark:text-slate-300 pt-0.5">${escapeHtml(evt.agenda || '')}</p>
    `;
    calendarContainer.appendChild(card);
  });
}

// 8. Section 4: SUGERENCIAS POR PM ASISTENTE
function renderSuggestions(suggestions) {
  suggestionsContainer.innerHTML = '';
  suggestionsCountBadge.textContent = suggestions.length;

  if (suggestions.length === 0) {
    suggestionsContainer.innerHTML = `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 text-center text-xs text-slate-400 space-y-1">
        <i class="fa-solid fa-circle-check text-2xl text-emerald-500 mb-1"></i>
        <p class="font-bold text-slate-700 dark:text-slate-200">¡Todo en orden en el proyecto!</p>
        <p>Hermes no detecta riesgos de retraso, cuellos de botella ni sobrecargas por el momento.</p>
      </div>
    `;
    return;
  }

  suggestions.forEach(s => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-500/40 rounded-2xl p-4 shadow-xs space-y-2.5';

    let badge = '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400">Sugerencia PM</span>';
    if (s.category === 'risk') {
      badge = '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">Alerta de Riesgo</span>';
    } else if (s.category === 'staffing') {
      badge = '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">Staffing & Capacidad</span>';
    }

    let actionButton = '';
    if (s.action_type === 'quick_load') {
      actionButton = `
        <button onclick="applySuggestion('${s.id}')" class="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition">
          <i class="fa-solid fa-bolt"></i> Cargar 5 CVs de Prueba
        </button>
      `;
    } else if (s.action_type === 'request_approval') {
      actionButton = `
        <button onclick="applySuggestion('${s.id}')" class="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition">
          <i class="fa-solid fa-paper-plane"></i> Solicitar Aprobación a Dirección
        </button>
      `;
    } else if (s.action_type === 'schedule_meeting') {
      actionButton = `
        <button onclick="applySuggestion('${s.id}')" class="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition">
          <i class="fa-solid fa-calendar-plus"></i> Agendar Sesión de Desbloqueo
        </button>
      `;
    }

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
          <i class="fa-solid fa-lightbulb text-amber-500"></i> ${escapeHtml(s.title)}
        </h4>
        ${badge}
      </div>
      <p class="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">${escapeHtml(s.description)}</p>
      
      <div class="bg-slate-50 dark:bg-slate-950 p-2.5 rounded-xl text-[11px] text-slate-700 dark:text-slate-300">
        <b class="text-indigo-600 dark:text-indigo-400">Recomendación de Hermes:</b> ${escapeHtml(s.recommendation)}
      </div>

      ${actionButton ? `<div class="pt-1.5 flex justify-end">${actionButton}</div>` : ''}
    `;

    suggestionsContainer.appendChild(card);
  });
}

async function applySuggestion(sugId) {
  try {
    await fetch(`/api/workspaces/${workspaceId}/suggestions/${sugId}/apply`, { method: 'POST' });
    loadWorkspaceData();
  } catch (err) {
    alert('Error al aplicar sugerencia: ' + err.message);
  }
}

// 9. Render Decisions
function renderDecisions(decisions) {
  decisionsContainer.innerHTML = '';
  if (decisions.length === 0) {
    decisionsContainer.innerHTML = '<p class="text-slate-400 text-xs py-2">No hay solicitudes de aprobación pendientes.</p>';
    return;
  }

  decisions.forEach(d => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs space-y-2';

    let actionButtons = `
      <div class="flex items-center space-x-2 pt-2 border-t border-slate-100 dark:border-slate-800">
        <button onclick="respondDecision('${d.id}', 'approved')" class="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-3 py-1.5 rounded-xl text-xs transition flex items-center gap-1">
          <i class="fa-solid fa-check"></i> Aprobar
        </button>
        <button onclick="respondDecision('${d.id}', 'rejected')" class="bg-slate-100 dark:bg-slate-800 hover:bg-rose-50 dark:hover:bg-rose-950 text-slate-600 dark:text-rose-300 font-semibold px-3 py-1.5 rounded-xl text-xs transition flex items-center gap-1">
          <i class="fa-solid fa-xmark"></i> Rechazar
        </button>
      </div>
    `;

    if (d.status !== 'pending') {
      actionButtons = `
        <div class="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px]">
          <span class="font-bold ${d.status === 'approved' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}">
            ● Decisión ${d.status === 'approved' ? 'Aprobada' : 'Rechazada'}
          </span>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-xs text-amber-700 dark:text-amber-300 flex items-center gap-1.5">
          <i class="fa-solid fa-scale-balanced"></i> ${escapeHtml(d.title)}
        </h4>
        <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400">Escalación</span>
      </div>
      <p class="text-xs text-slate-700 dark:text-slate-200">${escapeHtml(d.description)}</p>
      <div class="bg-slate-50 dark:bg-slate-950 p-2 rounded-xl text-[11px] text-slate-600 dark:text-slate-300">
        <b>Impacto:</b> ${escapeHtml(d.impact_summary)}
      </div>
      ${actionButtons}
    `;
    decisionsContainer.appendChild(card);
  });
}

async function respondDecision(decId, status) {
  try {
    await fetch(`/api/workspaces/${workspaceId}/decisions/${decId}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: status })
    });
    loadWorkspaceData();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// 10. Render Skills Hub
function renderSkills(skills) {
  skillsContainer.innerHTML = '';
  let activeCount = 0;

  skills.forEach(skill => {
    if (skill.is_active) activeCount++;
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 shadow-xs space-y-2';
    
    card.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2">
          <div class="w-7 h-7 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-xs font-bold">
            <i class="fa-solid ${skill.icon || 'fa-brain'}"></i>
          </div>
          <div>
            <h4 class="font-bold text-xs text-slate-900 dark:text-white">${escapeHtml(skill.name)}</h4>
          </div>
        </div>
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" ${skill.is_active ? 'checked' : ''} onchange="toggleSkill('${skill.id}', this.checked)" class="sr-only peer">
          <div class="w-8 h-4.5 bg-slate-200 dark:bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-indigo-600"></div>
        </label>
      </div>
      <p class="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">${escapeHtml(skill.description)}</p>
      
      <div class="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center text-[11px]">
        <button onclick="openSkillModal('${skill.id}', '${escapeHtml(skill.name)}', '${escapeHtml(skill.prompt_instructions)}')" class="text-indigo-600 dark:text-indigo-400 hover:underline font-semibold flex items-center gap-1">
          <i class="fa-solid fa-code text-[10px]"></i> Ver / Editar Prompt
        </button>
        <span class="text-[10px] ${skill.is_active ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'} font-medium">
          ${skill.is_active ? '● Activa' : '○ Inactiva'}
        </span>
      </div>
    `;
    skillsContainer.appendChild(card);
  });

  activeSkillsCount.textContent = activeCount;
}

async function toggleSkill(skillId, isActive) {
  try {
    await fetch(`/api/workspaces/${workspaceId}/skills/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill_id: skillId, is_active: isActive })
    });
    loadWorkspaceData(false);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

function openSkillModal(skillId, name, prompt) {
  currentEditingSkillId = skillId;
  skillModalTitle.innerHTML = `<i class="fa-solid fa-brain text-indigo-500"></i> Habilidad: ${name}`;
  skillModalPrompt.value = prompt;
  skillModal.classList.remove('hidden');
}

function closeSkillModal() {
  skillModal.classList.add('hidden');
}

async function saveSkillPrompt() {
  if (!currentEditingSkillId) return;
  const newPrompt = skillModalPrompt.value.trim();
  try {
    await fetch(`/api/workspaces/${workspaceId}/skills/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill_id: currentEditingSkillId, prompt_instructions: newPrompt })
    });
    closeSkillModal();
    loadWorkspaceData(false);
  } catch (e) {
    alert('Error guardando prompt: ' + e.message);
  }
}

// 11. Chat Handlers
function renderMarkdown(rawText) {
  if (!rawText) return '';
  if (window.marked && window.DOMPurify) {
    try {
      marked.setOptions({ breaks: true, gfm: true });
      const rawHtml = marked.parse(rawText);
      return DOMPurify.sanitize(rawHtml);
    } catch (e) {
      console.warn('Markdown parse error, falling back:', e);
    }
  }
  return `<p class="whitespace-pre-line">${escapeHtml(rawText)}</p>`;
}

function renderChatHistory(messages) {
  chatMessagesEl.innerHTML = '';
  messages.forEach(m => {
    if (m.sender === 'user') appendUserMessage(m.content, false);
    else if (m.sender === 'system') appendSystemMessage(m.content, false);
    else appendAssistantMessage(m.content, false);
  });
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function appendUserMessage(text, scroll = true) {
  const div = document.createElement('div');
  div.className = 'flex items-start justify-end space-x-2';
  div.innerHTML = `
    <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-xs p-3 max-w-[85%] shadow-xs leading-relaxed text-xs">
      <p class="whitespace-pre-line">${escapeHtml(text)}</p>
    </div>
  `;
  chatMessagesEl.appendChild(div);
  if (scroll) chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function sanitizeMessage(text) {
  if (!text) return '';
  return text.replace(/\*\[Nota:[\s\S]*$/gi, '').replace(/\[Nota:[\s\S]*?\]/gi, '').trim();
}

function appendAssistantMessage(text, scroll = true) {
  const cleanText = sanitizeMessage(text) || 'Acción procesada.';
  const div = document.createElement('div');
  div.className = 'flex items-start space-x-2';
  
  const contentHtml = renderMarkdown(cleanText);

  div.innerHTML = `
    <div class="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold shrink-0 text-[11px] mt-0.5">
      H
    </div>
    <div class="bg-slate-100 dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 rounded-2xl rounded-tl-xs p-3 max-w-[88%] text-slate-800 dark:text-slate-200 shadow-xs leading-relaxed chat-body text-xs space-y-1.5 [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_p]:mb-1.5 [&_p:last-child]:mb-0 [&_strong]:font-bold [&_strong]:text-indigo-950 dark:[&_strong]:text-indigo-200 [&_code]:bg-slate-200 dark:[&_code]:bg-slate-700 [&_code]:px-1 [&_code]:rounded [&_code]:font-mono">
      ${contentHtml}
    </div>
  `;
  chatMessagesEl.appendChild(div);
  if (scroll) chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function appendSystemMessage(text, scroll = true) {
  const div = document.createElement('div');
  div.className = 'flex justify-center my-1.5';
  const contentHtml = renderMarkdown(text);
  div.innerHTML = `
    <div class="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-500/40 text-amber-800 dark:text-amber-300 text-xs px-3 py-1.5 rounded-xl max-w-[92%] text-center [&_strong]:font-bold">
      ${contentHtml}
    </div>
  `;
  chatMessagesEl.appendChild(div);
  if (scroll) chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

// 12. Event Listeners
function setupEventListeners() {
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = chatInput.value.trim();
    if (!msg) return;

    chatInput.value = '';
    appendUserMessage(msg);
    chatSubmitBtn.disabled = true;

    const typingIndicator = document.createElement('div');
    typingIndicator.id = 'typing-indicator';
    typingIndicator.className = 'flex items-center space-x-2 text-slate-400 text-xs p-2';
    typingIndicator.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-indigo-500"></i> <span>Hermes está pensando...</span>';
    chatMessagesEl.appendChild(typingIndicator);
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (geminiApiKey) headers['X-Gemini-API-Key'] = geminiApiKey;

      const res = await fetch(`/api/workspaces/${workspaceId}/agent/chat`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({ message: msg })
      });

      const data = await res.json();
      typingIndicator.remove();
      appendAssistantMessage(data.response, true);
      loadWorkspaceData(false);
    } catch (err) {
      typingIndicator.remove();
      appendSystemMessage(`Error al comunicar con Hermes: ${err.message}`);
    } finally {
      chatSubmitBtn.disabled = false;
    }
  });

  if (btnClearChat) {
    btnClearChat.addEventListener('click', async () => {
      if (!confirm('¿Deseas reiniciar la conversación del chat con Hermes?')) return;
      try {
        await fetch(`/api/workspaces/${workspaceId}/chat/clear`, { method: 'POST' });
        chatMessagesEl.innerHTML = '';
        appendAssistantMessage('¡Hola! Soy Hermes, tu PM asistente. Puedo ayudarte a definir proyectos nuevos, monitorear la carga de trabajo del equipo, planificar el Kanban y agendar reuniones. ¿Por dónde empezamos hoy?', false);
      } catch (err) {
        alert('Error al limpiar el chat: ' + err.message);
      }
    });
  }

  document.querySelectorAll('.quick-prompt').forEach(btn => {
    btn.addEventListener('click', () => {
      chatInput.value = btn.textContent.trim().replace(/^[\uD800-\uDBFF\uDC00-\uDFFF\u2600-\u27BF]+\s*/, '');
      chatForm.dispatchEvent(new Event('submit'));
    });
  });

  btnSettings.addEventListener('click', () => {
    apiKeyInput.value = geminiApiKey;
    settingsModal.classList.remove('hidden');
  });
  modalCloseBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
  btnSaveKey.addEventListener('click', () => {
    geminiApiKey = apiKeyInput.value.trim();
    localStorage.setItem(STORAGE_KEYS.API_KEY, geminiApiKey);
    updateApiKeyUI();
    settingsModal.classList.add('hidden');
  });

  btnSamples.addEventListener('click', () => samplesModal.classList.remove('hidden'));
  samplesCloseBtn.addEventListener('click', () => samplesModal.classList.add('hidden'));

  btnQuickLoad.addEventListener('click', async () => {
    try {
      const res = await fetch(`/api/workspaces/${workspaceId}/setup-demo`, { method: 'POST' });
      if (res.ok) {
        appendSystemMessage('⚡ 5 trabajadores cargados en el ATS.');
        loadWorkspaceData();
      }
    } catch (e) {
      alert('Error: ' + e.message);
    }
  });

  dropzone.addEventListener('click', () => cvFileInput.click());
  cvFileInput.addEventListener('change', async (e) => {
    if (e.target.files.length > 0) await uploadFiles(e.target.files);
  });
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('border-indigo-500');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('border-indigo-500'));
  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropzone.classList.remove('border-indigo-500');
    if (e.dataTransfer.files.length > 0) await uploadFiles(e.dataTransfer.files);
  });
}

async function uploadFiles(files) {
  for (let file of files) {
    if (!file.name.endsWith('.pdf')) continue;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`/api/workspaces/${workspaceId}/upload-cv`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        appendSystemMessage(`📄 CV de **${data.profile.name}** procesado.`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  }
  loadWorkspaceData();
}

function updateApiKeyUI() {
  if (geminiApiKey && geminiApiKey.length > 10) {
    apiKeyStatusText.textContent = 'API Key Activa ✓';
    btnSettings.className = 'text-xs bg-emerald-600 hover:bg-emerald-500 text-white px-2.5 py-1.5 rounded-lg font-medium shadow-xs flex items-center gap-1 transition';
  } else {
    apiKeyStatusText.textContent = 'API Key';
    btnSettings.className = 'text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-2.5 py-1.5 rounded-lg font-medium shadow-xs flex items-center gap-1 transition';
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 13. TIME CONTROLS (SIMULATION SPEED)
let instructorPin = sessionStorage.getItem('colima_instructor_pin') || '';
let pendingSpeedAction = null;

function getOrPromptPin(actionCallback) {
  if (instructorPin) {
    actionCallback(instructorPin);
    return;
  }
  pendingSpeedAction = actionCallback;
  const modal = document.getElementById('pin-prompt-modal');
  if (modal) {
    modal.classList.remove('hidden');
    const input = document.getElementById('pin-prompt-input');
    if (input) {
      input.value = '';
      input.focus();
    }
  } else {
    const entered = prompt('Ingresa el PIN del instructor/taller:');
    if (entered) {
      instructorPin = entered.trim();
      sessionStorage.setItem('colima_instructor_pin', instructorPin);
      actionCallback(instructorPin);
    }
  }
}

function closePinModal() {
  const modal = document.getElementById('pin-prompt-modal');
  if (modal) modal.classList.add('hidden');
  pendingSpeedAction = null;
}

function savePinPrompt() {
  const input = document.getElementById('pin-prompt-input');
  const pinVal = input ? input.value.trim() : '';
  if (!pinVal) return;
  instructorPin = pinVal;
  sessionStorage.setItem('colima_instructor_pin', pinVal);
  closePinModal();
  if (pendingSpeedAction) {
    pendingSpeedAction(pinVal);
    pendingSpeedAction = null;
  }
}

async function setSimSpeed(speedMultiplier) {
  getOrPromptPin(async (pin) => {
    try {
      const res = await fetch(`/api/workspaces/${workspaceId}/time/speed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed_multiplier: speedMultiplier, instructor_pin: pin })
      });
      if (res.status === 401) {
        sessionStorage.removeItem('colima_instructor_pin');
        instructorPin = '';
        alert('PIN incorrecto. Por favor verifícalo con el instructor.');
        return;
      }
      const data = await res.json();
      if (data.state) renderClockState(data.state);
    } catch (e) {
      console.error('Error setting speed:', e);
    }
  });
}

async function stepSimDay() {
  getOrPromptPin(async (pin) => {
    try {
      const res = await fetch(`/api/workspaces/${workspaceId}/time/step-day`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pin })
      });
      if (res.status === 401) {
        sessionStorage.removeItem('colima_instructor_pin');
        instructorPin = '';
        alert('PIN incorrecto. Por favor verifícalo con el instructor.');
        return;
      }
      const data = await res.json();
      if (data.state) renderClockState(data.state);
      loadWorkspaceData();
    } catch (e) {
      console.error('Error stepping day:', e);
    }
  });
}

// 14. WORKSPACE RESET
const resetModal = document.getElementById('reset-modal');
const btnResetWorkspace = document.getElementById('btn-reset-workspace');

if (btnResetWorkspace) {
  btnResetWorkspace.addEventListener('click', () => {
    if (resetModal) resetModal.classList.remove('hidden');
  });
}

function closeResetModal() {
  if (resetModal) resetModal.classList.add('hidden');
}

async function confirmResetWorkspace() {
  try {
    const res = await fetch(`/api/workspaces/${workspaceId}/reset`, {
      method: 'POST'
    });
    if (res.ok) {
      closeResetModal();
      chatMessagesEl.innerHTML = '';
      appendAssistantMessage('¡Hola! Soy Hermes, tu PM asistente. El workspace ha sido reiniciado por completo. ¿Qué proyecto deseas aperturar o por dónde comenzamos?', false);
      loadWorkspaceData();
      loadInbox();
      appendSystemMessage('🔄 **Workspace reiniciado con éxito.** Todos los datos han vuelto a su estado inicial.');
    } else {
      alert('Error al reiniciar el workspace');
    }
  } catch (e) {
    alert('Error de conexión al reiniciar: ' + e.message);
  }
}

// 15. SUGERENCIAS & INBOX SUB-TABS
function switchSugTab(tabId) {
  const tabPm = document.getElementById('sug-tab-pm');
  const tabInbox = document.getElementById('sug-tab-inbox');
  const panelPm = document.getElementById('sug-panel-pm');
  const panelInbox = document.getElementById('sug-panel-inbox');

  if (tabId === 'sug-pm') {
    if (tabPm) {
      tabPm.className = 'sug-tab active text-xs font-semibold px-3 py-1.5 rounded-t-lg border border-b-0 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5';
    }
    if (tabInbox) {
      tabInbox.className = 'sug-tab text-xs font-medium px-3 py-1.5 rounded-t-lg border border-b-0 border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white flex items-center gap-1.5 transition';
    }
    if (panelPm) panelPm.classList.remove('hidden');
    if (panelInbox) panelInbox.classList.add('hidden');
  } else if (tabId === 'sug-inbox') {
    if (tabInbox) {
      tabInbox.className = 'sug-tab active text-xs font-semibold px-3 py-1.5 rounded-t-lg border border-b-0 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5';
    }
    if (tabPm) {
      tabPm.className = 'sug-tab text-xs font-medium px-3 py-1.5 rounded-t-lg border border-b-0 border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white flex items-center gap-1.5 transition';
    }
    if (panelPm) panelPm.classList.add('hidden');
    if (panelInbox) panelInbox.classList.remove('hidden');
    loadInbox();
  }
}

// 16. INBOX HERMES (AUTONOMOUS MESSAGES)
async function loadInbox() {
  try {
    const res = await fetch(`/api/workspaces/${workspaceId}/inbox`);
    if (!res.ok) return;
    const data = await res.json();
    renderInbox(data.messages || [], data.unread_count || 0);
  } catch (e) {
    console.error('[Inbox Error]', e);
  }
}

function renderInbox(messages, unreadCount) {
  const container = document.getElementById('inbox-container');
  const badgeTop = document.getElementById('inbox-unread-badge');
  const badgeSub = document.getElementById('inbox-badge-sub');

  if (unreadCount > 0) {
    if (badgeTop) {
      badgeTop.textContent = unreadCount;
      badgeTop.classList.remove('hidden');
    }
    if (badgeSub) {
      badgeSub.textContent = unreadCount;
      badgeSub.classList.remove('hidden');
    }
  } else {
    if (badgeTop) badgeTop.classList.add('hidden');
    if (badgeSub) badgeSub.classList.add('hidden');
  }

  if (!container) return;

  if (messages.length === 0) {
    container.innerHTML = `
      <div class="text-center py-10 text-slate-400 dark:text-slate-500 text-xs">
        <i class="fa-solid fa-robot text-2xl mb-2 opacity-30"></i>
        <p>Hermes analiza el estado del workspace periódicamente.<br>Los avisos e insights autónomos aparecerán aquí.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  messages.forEach(msg => {
    const card = document.createElement('div');
    const isUnread = !msg.read;
    
    let icon = 'fa-lightbulb text-amber-500';
    let bgClass = isUnread ? 'bg-indigo-50/50 dark:bg-indigo-950/30 border-indigo-200 dark:border-indigo-800' : 'bg-white dark:bg-slate-900 border-slate-200/90 dark:border-slate-800';
    
    if (msg.type === 'alerta') {
      icon = 'fa-triangle-exclamation text-rose-500';
      if (isUnread) bgClass = 'bg-rose-50/50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900/60';
    } else if (msg.type === 'insight') {
      icon = 'fa-chart-line text-blue-500';
    } else if (msg.type === 'acción') {
      icon = 'fa-bolt text-indigo-500';
    }

    const bodyHtml = renderMarkdown(msg.body);

    card.className = `${bgClass} border rounded-2xl p-4 shadow-xs space-y-2.5 transition`;
    card.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2">
          <i class="fa-solid ${icon} text-sm"></i>
          <h4 class="font-bold text-xs text-slate-900 dark:text-white">${escapeHtml(msg.title)}</h4>
          ${isUnread ? '<span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-600 text-white">Nuevo</span>' : ''}
        </div>
        <div class="flex items-center space-x-2">
          <span class="text-[10px] text-slate-400 font-mono">${escapeHtml(msg.sim_time || '')}</span>
          ${isUnread ? `<button onclick="markInboxMessageRead('${msg.id}')" title="Marcar como leída" class="text-slate-400 hover:text-indigo-600 text-xs px-1 py-0.5 rounded transition"><i class="fa-solid fa-check"></i></button>` : ''}
        </div>
      </div>
      <div class="text-xs text-slate-700 dark:text-slate-300 leading-relaxed space-y-1 [&_strong]:font-bold [&_ul]:list-disc [&_ul]:pl-4">
        ${bodyHtml}
      </div>
      <div class="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <button onclick="discussInboxInChat('${escapeHtml(msg.title).replace(/'/g, "\\'")}')" class="text-[11px] text-indigo-600 dark:text-indigo-400 font-semibold hover:underline flex items-center gap-1">
          <i class="fa-solid fa-comments"></i> Conversar con Hermes sobre esto
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

async function markInboxMessageRead(msgId) {
  try {
    await fetch(`/api/workspaces/${workspaceId}/inbox/mark-read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ msg_id: msgId })
    });
    loadInbox();
  } catch (e) {
    console.error(e);
  }
}

async function markAllInboxRead() {
  try {
    await fetch(`/api/workspaces/${workspaceId}/inbox/mark-read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    loadInbox();
  } catch (e) {
    console.error(e);
  }
}

function discussInboxInChat(title) {
  chatInput.value = `Respecto al aviso de "${title}": ¿Qué me recomiendas hacer o qué acciones debemos tomar?`;
  chatForm.dispatchEvent(new Event('submit'));
}

// Start
initTheme();
updateApiKeyUI();
setupSSE();
loadWorkspaceData();
setupEventListeners();

