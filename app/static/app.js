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

const SPEED_LEVELS = [0, 1, 5, 10, 30, 60, 120, 300];
let currentSimSpeed = 0;

function adjustSimSpeed(delta) {
  let idx = SPEED_LEVELS.indexOf(currentSimSpeed);
  if (idx === -1) {
    // Find closest
    idx = 0;
    for (let i = 0; i < SPEED_LEVELS.length; i++) {
      if (SPEED_LEVELS[i] <= currentSimSpeed) idx = i;
    }
  }
  let nextIdx = Math.max(0, Math.min(SPEED_LEVELS.length - 1, idx + delta));
  setSimSpeed(SPEED_LEVELS[nextIdx]);
}

function renderClockState(state) {
  if (!state) return;
  currentSimDay = state.day_number || 1;
  currentSimSpeed = state.speed_multiplier || 0;

  simDayEl.textContent = `Día ${currentSimDay}`;
  simTimeEl.textContent = state.formatted_time || '12 Sep, 09:00 AM';

  const calLabel = document.getElementById('cal-current-day-label');
  if (calLabel) calLabel.textContent = `Día Actual: Día ${currentSimDay}`;

  const speed = currentSimSpeed;
  if (state.status === 'paused' || speed === 0) {
    simSpeedBadge.textContent = 'Pausado';
    simSpeedBadge.className = 'text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300';
    clockPulse.classList.add('hidden');
  } else {
    simSpeedBadge.textContent = `${speed}x`;
    simSpeedBadge.className = 'text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30';
    clockPulse.classList.remove('hidden');
  }

  // Update Speed Buttons UI Highlight
  const btnPause = document.getElementById('btn-time-pause');
  const btn1x = document.getElementById('btn-time-1x');
  const btn10x = document.getElementById('btn-time-10x');
  const btn60x = document.getElementById('btn-time-60x');

  const defaultBtnClass = 'time-ctrl-btn text-[10px] px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-white transition';
  const activeBtnClass = 'time-ctrl-btn text-[10px] px-2 py-1 rounded bg-indigo-600 text-white font-bold border border-indigo-700 shadow-xs transition';

  if (btnPause) btnPause.className = (speed === 0) ? activeBtnClass : defaultBtnClass;
  if (btn1x) btn1x.className = (speed === 1) ? activeBtnClass : defaultBtnClass;
  if (btn10x) btn10x.className = (speed === 10) ? activeBtnClass : defaultBtnClass;
  if (btn60x) btn60x.className = (speed === 60) ? activeBtnClass : defaultBtnClass;
}

// 4. Load Workspace Data
async function loadWorkspaceData(renderChat = true) {
  try {
    const res = await fetch(`/api/workspaces/${workspaceId}`);
    if (!res.ok) return;
    const data = await res.json();

    renderWorkers(data.talent_pool || [], data.tasks || []);
    renderProjects(data.projects || [], data.workspace || {}, data.tasks || []);
    renderGanttChart(data.tasks || []);
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

// 6. Section 2: MIS PROYECTOS & KANBAN / GANTT
let currentProjectView = 'kanban';
let currentSimDay = 1;

function switchProjectView(view) {
  if (view === 'gantt') {
    switchStage('gantt');
    return;
  }
  switchStage('projects');
}

function promptNewProjectInChat() {
  chatInput.value = 'Hola Hermes, definamos y aperturemos el primer proyecto del taller.';
  chatForm.dispatchEvent(new Event('submit'));
}

function renderProjects(projects, ws, tasks) {
  const emptyState = document.getElementById('project-empty-state');
  const banner = document.getElementById('project-banner');
  const kanbanView = document.getElementById('kanban-view');
  const ganttView = document.getElementById('gantt-view');

  const hasProject = (projects && projects.length > 0) || Boolean(ws.project_name);

  // Always sync Gantt chart with current tasks
  renderGanttChart(tasks || []);

  const cols = {
    backlog: document.getElementById('col-backlog'),
    in_progress: document.getElementById('col-in_progress'),
    review: document.getElementById('col-review'),
    done: document.getElementById('col-done')
  };
  const counts = { backlog: 0, in_progress: 0, review: 0, done: 0 };
  Object.values(cols).forEach(c => { if (c) c.innerHTML = ''; });

  if (!hasProject) {
    if (emptyState) emptyState.classList.remove('hidden');
    if (banner) banner.classList.add('hidden');
    if (kanbanView) kanbanView.classList.add('hidden');
    if (ganttView) ganttView.classList.add('hidden');

    Object.keys(cols).forEach(key => {
      if (cols[key]) {
        cols[key].innerHTML = `
          <div class="h-20 border border-dashed border-slate-200 dark:border-slate-800/80 rounded-xl flex items-center justify-center text-[11px] text-slate-400 dark:text-slate-600">
            Sin tareas
          </div>
        `;
      }
    });
    const cB = document.getElementById('count-backlog');
    const cP = document.getElementById('count-in_progress');
    const cR = document.getElementById('count-review');
    const cD = document.getElementById('count-done');
    if (cB) cB.textContent = 0;
    if (cP) cP.textContent = 0;
    if (cR) cR.textContent = 0;
    if (cD) cD.textContent = 0;
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');
  if (banner) banner.classList.remove('hidden');
  if (currentProjectView === 'kanban') {
    if (kanbanView) kanbanView.classList.remove('hidden');
    if (ganttView) ganttView.classList.add('hidden');
  } else {
    if (kanbanView) kanbanView.classList.add('hidden');
    if (ganttView) ganttView.classList.remove('hidden');
  }

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
  Object.values(cols).forEach(c => { if (c) c.innerHTML = ''; });

  tasks.forEach(task => {
    const status = task.status in cols ? task.status : 'backlog';
    counts[status]++;

    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-xl p-3 shadow-xs hover:shadow-sm transition space-y-2.5';

    let priorityBadge = '<span class="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">Normal</span>';
    if (task.priority === 'urgent') {
      priorityBadge = '<span class="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">Urgente</span>';
    } else if (task.priority === 'high') {
      priorityBadge = '<span class="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">Alta</span>';
    }

    const assigneeName = task.assignee_name || 'Sin asignar';
    const initial = assigneeName.charAt(0).toUpperCase();

    const progressPct = task.estimated_hours > 0 ? Math.min(100, Math.round((task.completed_hours / task.estimated_hours) * 100)) : 0;

    let blockerHtml = '';
    if (task.blocker_reason && task.status !== 'done') {
      blockerHtml = `
        <div class="bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 p-1.5 rounded-lg text-[10px] text-rose-700 dark:text-rose-300 flex items-center gap-1">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>${escapeHtml(task.blocker_reason)}</span>
        </div>
      `;
    }

    let feedbackHtml = '';
    if (task.review_feedback) {
      feedbackHtml = `
        <div class="bg-indigo-50/90 dark:bg-indigo-950/60 border border-indigo-200/90 dark:border-indigo-800/60 p-2 rounded-xl text-[10px] text-indigo-950 dark:text-indigo-200 space-y-0.5 shadow-2xs">
          <div class="font-bold flex items-center gap-1 text-indigo-600 dark:text-indigo-400 text-[10px]">
            <i class="fa-solid fa-robot"></i> Feedback de Hermes PM:
          </div>
          <p class="leading-relaxed text-[10.5px] italic">${escapeHtml(task.review_feedback)}</p>
        </div>
      `;
    } else if (task.status === 'review') {
      feedbackHtml = `
        <div class="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 p-1.5 rounded-lg text-[10px] text-amber-700 dark:text-amber-300 flex items-center gap-1.5 font-medium animate-pulse">
          <i class="fa-solid fa-spinner fa-spin"></i>
          <span>Hermes está realizando la revisión técnica y pruebas...</span>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="flex items-start justify-between gap-1.5">
        <h4 class="font-medium text-xs text-slate-800 dark:text-slate-100 leading-snug">${escapeHtml(task.title)}</h4>
        ${priorityBadge}
      </div>

      ${blockerHtml}
      ${feedbackHtml}
      
      <div class="flex items-center justify-between text-[11px] pt-0.5">
        <div class="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
          <span class="w-4 h-4 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-[9px] font-bold">
            ${initial}
          </span>
          <span class="text-[11px] truncate max-w-[100px]">${escapeHtml(assigneeName)}</span>
        </div>
        <span class="font-mono text-[10px] font-semibold ${progressPct >= 100 ? 'text-emerald-600' : 'text-indigo-600 dark:text-indigo-400'}">${task.completed_hours || 0}h / ${task.estimated_hours}h (${progressPct}%)</span>
      </div>

      <div class="w-full h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div class="h-full ${progressPct >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'} rounded-full transition-all duration-300" style="width: ${progressPct}%"></div>
      </div>
    `;

    if (cols[status]) cols[status].appendChild(card);
  });

  Object.keys(cols).forEach(key => {
    if (cols[key] && counts[key] === 0) {
      cols[key].innerHTML = `
        <div class="h-20 border border-dashed border-slate-200 dark:border-slate-800/80 rounded-xl flex items-center justify-center text-[11px] text-slate-400 dark:text-slate-600">
          Sin tareas
        </div>
      `;
    }
  });

  const cB = document.getElementById('count-backlog');
  const cP = document.getElementById('count-in_progress');
  const cR = document.getElementById('count-review');
  const cD = document.getElementById('count-done');
  if (cB) cB.textContent = counts.backlog;
  if (cP) cP.textContent = counts.in_progress;
  if (cR) cR.textContent = counts.review;
  if (cD) cD.textContent = counts.done;

  // Render Gantt Timeline View
  renderGanttChart(tasks);
}

function renderGanttChart(tasks) {
  const container = document.getElementById('gantt-chart-container');
  const ganttCountBadge = document.getElementById('gantt-count-badge');
  if (ganttCountBadge) ganttCountBadge.textContent = (tasks || []).length;

  if (!container) return;

  if (!tasks || tasks.length === 0) {
    container.innerHTML = `
      <div class="text-center py-12 space-y-3">
        <div class="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-xl mx-auto shadow-xs">
          <i class="fa-solid fa-chart-gantt"></i>
        </div>
        <div>
          <h4 class="font-bold text-xs text-slate-800 dark:text-slate-200">No hay tareas creadas para el cronograma</h4>
          <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
            Habla con Hermes en el chat para definir el proyecto y generar el backlog de tareas con estimaciones de horas.
          </p>
        </div>
        <button onclick="promptNewProjectInChat()" class="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-3.5 py-1.5 rounded-xl transition shadow-xs inline-flex items-center gap-1.5">
          <i class="fa-solid fa-lightbulb"></i> Definir Tareas con Hermes
        </button>
      </div>
    `;
    return;
  }

  let html = `
    <div class="min-w-[680px] space-y-2">
      <!-- Days Header Row -->
      <div class="grid grid-cols-12 text-[10px] font-mono text-slate-400 border-b border-slate-100 dark:border-slate-800 pb-1">
        <div class="col-span-4 font-sans font-bold text-slate-700 dark:text-slate-300">Tarea & Asignado</div>
        <div class="col-span-8 grid grid-cols-6 text-center">
          <span>D1-D5</span>
          <span>D6-D10</span>
          <span>D11-D15</span>
          <span>D16-D20</span>
          <span>D21-D25</span>
          <span>D26-D30</span>
        </div>
      </div>
  `;

  tasks.forEach((task, idx) => {
    const progressPct = task.estimated_hours > 0 ? Math.min(100, Math.round((task.completed_hours / task.estimated_hours) * 100)) : 0;
    
    // Calculate synthetic start day & duration based on index and estimation
    const startDay = Math.min(25, 1 + (idx * 2));
    const durationDays = Math.max(3, Math.min(12, Math.round(task.estimated_hours / 4)));
    const leftPct = ((startDay - 1) / 30) * 100;
    const widthPct = Math.min(100 - leftPct, (durationDays / 30) * 100);

    let barColor = 'bg-slate-300 dark:bg-slate-700';
    if (task.status === 'in_progress') barColor = 'bg-blue-500';
    else if (task.status === 'review') barColor = 'bg-amber-500';
    else if (task.status === 'done') barColor = 'bg-emerald-500';

    html += `
      <div class="grid grid-cols-12 items-center py-1.5 border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 rounded-lg px-1 transition text-xs">
        <div class="col-span-4 pr-2">
          <p class="font-semibold text-slate-800 dark:text-slate-200 truncate text-[11px]">${escapeHtml(task.title)}</p>
          <p class="text-[10px] text-slate-400 truncate">👤 ${escapeHtml(task.assignee_name || 'Sin asignar')} • ${task.estimated_hours}h</p>
        </div>
        <div class="col-span-8 relative h-6 bg-slate-100 dark:bg-slate-800/60 rounded-md overflow-hidden flex items-center">
          <div class="absolute top-1 bottom-1 ${barColor} rounded opacity-90 shadow-xs flex items-center justify-between px-2 text-[9px] text-white font-bold transition-all duration-300" style="left: ${leftPct}%; width: ${widthPct}%;">
            <span>${progressPct}%</span>
            <span>${task.completed_hours}h/${task.estimated_hours}h</span>
          </div>
        </div>
      </div>
    `;
  });

  html += '</div>';
  container.innerHTML = html;
}

// 7. Section 3: MI CALENDARIO & CEREMONIAS VISUALES
function renderCalendar(events) {
  const monthGrid = document.getElementById('calendar-month-grid');
  const calLabel = document.getElementById('cal-current-day-label');
  if (calLabel) calLabel.textContent = `Día Actual: Día ${currentSimDay}`;

  if (monthGrid) {
    monthGrid.innerHTML = '';
    // Days of week header
    const daysHeader = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
    daysHeader.forEach(d => {
      const h = document.createElement('div');
      h.className = 'font-bold text-[10px] text-slate-400 py-1 uppercase';
      h.textContent = d;
      monthGrid.appendChild(h);
    });

    // 30 days of sprint
    for (let day = 1; day <= 30; day++) {
      const cell = document.createElement('div');
      const isCurrentDay = (day === currentSimDay);
      const isPastDay = (day < currentSimDay);

      let borderStyle = 'border border-slate-100 dark:border-slate-800';
      let bgStyle = isPastDay ? 'bg-slate-50/50 dark:bg-slate-900/40 text-slate-400' : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300';
      if (isCurrentDay) {
        borderStyle = 'border-2 border-indigo-500 ring-2 ring-indigo-500/20';
        bgStyle = 'bg-indigo-50/70 dark:bg-indigo-950/70 font-bold text-indigo-700 dark:text-indigo-300 shadow-xs';
      }

      // Find events matching this day
      const dayEvents = (events || []).filter(e => {
        if (e.sim_date && (e.sim_date.includes(`Día ${day}`) || e.sim_date.includes(`Dia ${day}`))) return true;
        if (day === 1 && e.title.toLowerCase().includes('kickoff')) return true;
        if (day === 15 && e.title.toLowerCase().includes('checkpoint')) return true;
        if (day === 30 && (e.title.toLowerCase().includes('demo') || e.title.toLowerCase().includes('retro'))) return true;
        return false;
      });

      let chips = '';
      dayEvents.forEach(ev => {
        let chipBg = 'bg-indigo-500 text-white';
        if (ev.title.toLowerCase().includes('desbloqueo')) chipBg = 'bg-rose-500 text-white';
        else if (ev.title.toLowerCase().includes('daily')) chipBg = 'bg-emerald-500 text-white';
        else if (ev.title.toLowerCase().includes('checkpoint')) chipBg = 'bg-amber-500 text-white';

        chips += `<span class="block truncate text-[8px] px-1 py-0.5 rounded ${chipBg} font-medium mt-0.5" title="${escapeHtml(ev.title)}">${escapeHtml(ev.title)}</span>`;
      });

      cell.className = `${borderStyle} ${bgStyle} rounded-xl p-1 h-14 flex flex-col justify-between transition`;
      cell.innerHTML = `
        <div class="flex items-center justify-between text-[10px]">
          <span>D${day}</span>
          ${isCurrentDay ? '<span class="w-1.5 h-1.5 rounded-full bg-indigo-600 animate-ping"></span>' : ''}
        </div>
        <div class="overflow-hidden space-y-0.5">${chips}</div>
      `;
      monthGrid.appendChild(cell);
    }
  }

  // Render Upcoming Events Cards
  calendarContainer.innerHTML = '';
  if (!events || events.length === 0) {
    calendarContainer.innerHTML = '<p class="col-span-2 text-slate-400 text-xs py-4 text-center">No hay reuniones ni ceremonias agendadas en el calendario aún.</p>';
    return;
  }

  events.forEach(evt => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-3.5 shadow-xs space-y-1.5';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
          <i class="fa-solid fa-calendar-check text-indigo-500"></i> ${escapeHtml(evt.title)}
        </h4>
        <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">${escapeHtml(evt.time_slot)}</span>
      </div>
      <p class="text-[11px] text-slate-500 font-medium">📅 ${escapeHtml(evt.sim_date)} • 👥 ${escapeHtml(evt.attendees)}</p>
      <p class="text-xs text-slate-600 dark:text-slate-300 pt-0.5 leading-relaxed">${escapeHtml(evt.agenda || '')}</p>
    `;
    calendarContainer.appendChild(card);
  });
}

function scheduleMeetingWithHermes() {
  chatInput.value = 'Hermes, agenda una reunión de sincronización con el equipo para hoy.';
  chatForm.dispatchEvent(new Event('submit'));
}

// 8. Section 4: SUGERENCIAS DINÁMICAS Y AUTO-LIMPIANTES
function renderSuggestions(suggestions) {
  suggestionsContainer.innerHTML = '';
  
  // Show only active suggestions
  const activeSugs = (suggestions || []).filter(s => s.status === 'active');
  suggestionsCountBadge.textContent = activeSugs.length;

  if (activeSugs.length === 0) {
    suggestionsContainer.innerHTML = `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 text-center text-xs text-slate-400 space-y-1">
        <i class="fa-solid fa-circle-check text-2xl text-emerald-500 mb-1"></i>
        <p class="font-bold text-slate-700 dark:text-slate-200">¡Todo en orden en el proyecto!</p>
        <p>Hermes no detecta riesgos de retraso, cuellos de botella ni sobrecargas por el momento.</p>
      </div>
    `;
    return;
  }

  activeSugs.forEach(s => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-500/40 rounded-2xl p-4 shadow-xs space-y-2.5 transition';

    let badge = '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400">Sugerencia PM</span>';
    if (s.category === 'risk') {
      badge = '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">Alerta de Riesgo</span>';
    } else if (s.category === 'staffing') {
      badge = '<span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">Staffing & Capacidad</span>';
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

      <div class="pt-1.5 flex items-center justify-between border-t border-slate-100 dark:border-slate-800">
        <button onclick="dismissSuggestion('${s.id}')" class="text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 text-xs font-semibold flex items-center gap-1 transition">
          <i class="fa-solid fa-xmark"></i> Omitir Sugerencia
        </button>
        <button onclick="discussSuggestionInChat('${escapeHtml(s.title).replace(/'/g, "\\'")}')" class="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition">
          <i class="fa-solid fa-comments"></i> Discutir con Hermes
        </button>
      </div>
    `;

    suggestionsContainer.appendChild(card);
  });
}

async function dismissSuggestion(sugId) {
  try {
    await fetch(`/api/workspaces/${workspaceId}/suggestions/${sugId}/dismiss`, { method: 'POST' });
    loadWorkspaceData(false);
  } catch (err) {
    console.error('Error al omitir sugerencia:', err);
  }
}

function discussSuggestionInChat(title) {
  chatInput.value = `Respecto a la sugerencia "${title}": ¿Cómo me recomiendas actuar o qué opciones tenemos?`;
  chatForm.dispatchEvent(new Event('submit'));
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

// 10. Render Skills Hub & Creator
function renderSkills(skills) {
  skillsContainer.innerHTML = '';
  let activeCount = 0;

  skills.forEach(skill => {
    if (skill.is_active) activeCount++;
    const card = document.createElement('div');
    card.className = `bg-white dark:bg-slate-900 border ${skill.is_active ? 'border-indigo-300 dark:border-indigo-800/80' : 'border-slate-200/90 dark:border-slate-800'} rounded-2xl p-4 shadow-xs space-y-2.5 transition`;
    
    card.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2.5">
          <div class="w-8 h-8 rounded-xl ${skill.is_active ? 'bg-indigo-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'} flex items-center justify-center text-xs font-bold transition">
            <i class="fa-solid ${skill.icon || 'fa-brain'}"></i>
          </div>
          <div>
            <h4 class="font-bold text-xs text-slate-900 dark:text-white">${escapeHtml(skill.name)}</h4>
            <span class="text-[10px] ${skill.is_active ? 'text-indigo-600 dark:text-indigo-400 font-semibold' : 'text-slate-400'}">
              ${skill.is_active ? '● Activa en Razonamiento' : '○ Apagada'}
            </span>
          </div>
        </div>
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" ${skill.is_active ? 'checked' : ''} onchange="toggleSkill('${skill.id}', this.checked)" class="sr-only peer">
          <div class="w-9 h-5 bg-slate-200 dark:bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
        </label>
      </div>
      <p class="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">${escapeHtml(skill.description)}</p>
      
      <div class="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center text-[11px]">
        <button onclick="openSkillModal('${skill.id}', '${escapeHtml(skill.name)}', '${escapeHtml(skill.prompt_instructions)}')" class="text-indigo-600 dark:text-indigo-400 hover:underline font-semibold flex items-center gap-1">
          <i class="fa-solid fa-code text-[10px]"></i> Ver / Editar Prompt
        </button>
      </div>
    `;
    skillsContainer.appendChild(card);
  });

  activeSkillsCount.textContent = `${activeCount} / ${skills.length}`;
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

function openNewSkillModal() {
  document.getElementById('new-skill-name').value = '';
  document.getElementById('new-skill-icon').value = 'fa-brain';
  document.getElementById('new-skill-desc').value = '';
  document.getElementById('new-skill-prompt').value = '';
  document.getElementById('new-skill-modal').classList.remove('hidden');
}

function closeNewSkillModal() {
  document.getElementById('new-skill-modal').classList.add('hidden');
}

async function saveNewSkill() {
  const name = document.getElementById('new-skill-name').value.trim();
  const icon = document.getElementById('new-skill-icon').value.trim() || 'fa-brain';
  const desc = document.getElementById('new-skill-desc').value.trim();
  const prompt = document.getElementById('new-skill-prompt').value.trim();

  if (!name || !desc || !prompt) {
    alert('Por favor completa el nombre, descripción y prompt de la habilidad.');
    return;
  }

  try {
    const res = await fetch(`/api/workspaces/${workspaceId}/skills/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        icon: icon,
        description: desc,
        prompt_instructions: prompt
      })
    });
    if (res.ok) {
      closeNewSkillModal();
      loadWorkspaceData(false);
      appendSystemMessage(`🧠 **Nueva Habilidad Creada:** "${name}" añadida y activada.`);
    } else {
      alert('Error al crear habilidad');
    }
  } catch (e) {
    alert('Error de conexión: ' + e.message);
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
  currentEditingSkillId = null;
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
      const data = await res.json();
      closeResetModal();
      chatMessagesEl.innerHTML = '';
      appendAssistantMessage('¡Hola! Soy Hermes, tu PM asistente. El workspace ha sido reiniciado por completo. ¿Qué proyecto deseas aperturar o por dónde comenzamos?', false);
      
      // Explicitly reset Gantt chart, badge and clock state
      renderGanttChart([]);
      if (data.clock_state) {
        renderClockState(data.clock_state);
      }
      
      loadWorkspaceData();
      loadInbox();
      appendSystemMessage('🔄 **Workspace reiniciado con éxito.** Todos los datos, el cronograma Gantt y el reloj de simulación han vuelto a su estado inicial.');
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

