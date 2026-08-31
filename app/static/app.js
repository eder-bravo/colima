// Colima PM Sandbox Application Logic

const STORAGE_KEYS = {
  WORKSPACE_ID: 'colima_workspace_id',
  API_KEY: 'colima_gemini_api_key',
  THEME_PREF: 'colima_theme_pref' // 'system', 'light', 'dark'
};

// Workspace ID
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
const talentListEl = document.getElementById('talent-list');
const talentCountBadge = document.getElementById('talent-count-badge');
const activeSkillsCount = document.getElementById('active-skills-count');
const skillsContainer = document.getElementById('skills-container');
const calendarContainer = document.getElementById('calendar-container');
const decisionsContainer = document.getElementById('decisions-container');
const trajectoriesListEl = document.getElementById('trajectories-list');

// Skill Modal
const skillModal = document.getElementById('skill-modal');
const skillModalTitle = document.getElementById('skill-modal-title');
const skillModalPrompt = document.getElementById('skill-modal-prompt');

// 1. THEME ENGINE (System-based default + Manual Toggle)
function initTheme() {
  const savedPref = localStorage.getItem(STORAGE_KEYS.THEME_PREF) || 'system';
  applyTheme(savedPref);

  // Listen to OS system theme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
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

// 2. STAGE TABS
function switchStage(stage) {
  document.querySelectorAll('.stage-tab').forEach(tab => {
    tab.className = 'stage-tab font-medium text-xs px-3.5 py-2 rounded-lg transition text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 flex items-center gap-1.5';
  });
  document.querySelectorAll('.stage-view').forEach(view => view.classList.add('hidden'));

  const activeTab = document.getElementById(`tab-stage-${stage}`);
  const activeView = document.getElementById(`stage-${stage}`);

  if (activeTab && activeView) {
    activeTab.className = 'stage-tab font-semibold text-xs px-3.5 py-2 rounded-lg transition text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-500/30 flex items-center gap-1.5';
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
        appendSystemMessage(`🚨 **EVENTO GLOBAL DEL TALLER:** ${payload.event.title}\n\n${payload.event.description}`);
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
  simTimeEl.textContent = state.formatted_time || '12 Sep 2030, 09:00 AM';

  const speed = state.speed_multiplier || 0;
  if (state.status === 'paused' || speed === 0) {
    simSpeedBadge.textContent = 'Pausado';
    simSpeedBadge.className = 'text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300';
    clockPulse.classList.add('hidden');
  } else {
    simSpeedBadge.textContent = `${speed}x Vel.`;
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

    renderKanban(data.tasks || []);
    renderSkills(data.skills || []);
    renderTalentPool(data.talent_pool || []);
    renderCalendar(data.calendar_events || []);
    renderDecisions(data.managerial_decisions || []);
    renderTrajectories(data.trajectories || []);

    if (renderChat && data.messages && data.messages.length > 0) {
      renderChatHistory(data.messages);
    }
  } catch (e) {
    console.error('[Load Error]', e);
  }
}

// 5. Render Kanban
function renderKanban(tasks) {
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
    card.className = 'bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-sm space-y-2';

    let priorityBadge = '<span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-500">Normal</span>';
    if (task.priority === 'urgent') {
      priorityBadge = '<span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/30">Urgente</span>';
    } else if (task.priority === 'high') {
      priorityBadge = '<span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-500/30">Alta</span>';
    }

    card.innerHTML = `
      <div class="flex items-start justify-between gap-1">
        <h4 class="font-bold text-xs text-slate-900 dark:text-white leading-snug">${escapeHtml(task.title)}</h4>
        ${priorityBadge}
      </div>
      <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">${escapeHtml(task.description || '')}</p>
      
      <!-- Progress Bar -->
      <div class="space-y-1 pt-1">
        <div class="flex justify-between text-[10px] text-slate-500 font-mono">
          <span>${task.completed_hours}h / ${task.estimated_hours}h</span>
          <span class="font-bold text-indigo-600 dark:text-indigo-400">${task.progress_percent}%</span>
        </div>
        <div class="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full bg-gradient-to-r from-indigo-500 to-blue-500 rounded-full task-progress-bar" style="width: ${task.progress_percent}%"></div>
        </div>
      </div>

      <!-- Assignee Footer -->
      <div class="flex items-center justify-between pt-1 border-t border-slate-200 dark:border-slate-800/60 text-[10px]">
        <span class="text-slate-600 dark:text-slate-300 font-medium flex items-center gap-1">
          <i class="fa-solid fa-user-circle text-indigo-500"></i> ${escapeHtml(task.assignee_name || 'Sin asignar')}
        </span>
        <span class="text-slate-400">${escapeHtml(task.role_required)}</span>
      </div>
    `;

    cols[status].appendChild(card);
  });

  document.getElementById('count-backlog').textContent = counts.backlog;
  document.getElementById('count-in_progress').textContent = counts.in_progress;
  document.getElementById('count-review').textContent = counts.review;
  document.getElementById('count-done').textContent = counts.done;
}

// 6. Render Skills Hub
function renderSkills(skills) {
  skillsContainer.innerHTML = '';
  let activeCount = 0;

  skills.forEach(skill => {
    if (skill.is_active) activeCount++;
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-3';
    
    card.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2.5">
          <div class="w-8 h-8 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-sm font-bold">
            <i class="fa-solid ${skill.icon || 'fa-brain'}"></i>
          </div>
          <div>
            <h4 class="font-bold text-xs text-slate-900 dark:text-white">${escapeHtml(skill.name)}</h4>
            <span class="text-[10px] text-slate-400 font-mono">${escapeHtml(skill.id)}</span>
          </div>
        </div>
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" ${skill.is_active ? 'checked' : ''} onchange="toggleSkill('${skill.id}', this.checked)" class="sr-only peer">
          <div class="w-9 h-5 bg-slate-300 dark:bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
        </label>
      </div>
      <p class="text-xs text-slate-600 dark:text-slate-300">${escapeHtml(skill.description)}</p>
      
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
    alert('Error actualizando habilidad: ' + e.message);
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

// 7. Render Talent ATS
function renderTalentPool(talent) {
  talentListEl.innerHTML = '';
  talentCountBadge.textContent = talent.length;

  if (talent.length === 0) {
    talentListEl.innerHTML = `
      <div class="col-span-2 text-center py-6 text-slate-400 text-xs">
        <p>No hay perfiles cargados en el ATS. Haz clic en "Cargar Demo" o arrastra un PDF.</p>
      </div>
    `;
    return;
  }

  talent.forEach(p => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-2';
    
    let seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400">Mid</span>';
    if (p.seniority === 'Senior') {
      seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30">Senior</span>';
    } else if (p.seniority === 'Junior') {
      seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30">Junior</span>';
    }

    const skillsPills = (p.skills || []).map(s => 
      `<span class="text-[9px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded-full">${escapeHtml(s)}</span>`
    ).join(' ');

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div>
          <h4 class="font-bold text-xs text-slate-900 dark:text-white">${escapeHtml(p.name)}</h4>
          <p class="text-[11px] text-slate-500">${escapeHtml(p.role)}</p>
        </div>
        ${seniorityBadge}
      </div>
      <div class="flex flex-wrap gap-1 pt-1">
        ${skillsPills}
      </div>
      <div class="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] text-slate-400">
        <span>Factor Productividad: <b>${p.productivity_factor}x</b></span>
        <span class="text-emerald-500 font-medium">● Disponible</span>
      </div>
    `;
    talentListEl.appendChild(card);
  });
}

// 8. Render Decisions & Calendar
function renderDecisions(decisions) {
  decisionsContainer.innerHTML = '';
  if (decisions.length === 0) {
    decisionsContainer.innerHTML = '<p class="text-slate-400 text-xs py-2">No hay solicitudes de aprobación pendientes de la Dirección.</p>';
    return;
  }

  decisions.forEach(d => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-500/40 rounded-2xl p-4 shadow-sm space-y-2';

    let actionButtons = `
      <div class="flex items-center space-x-2 pt-2 border-t border-slate-100 dark:border-slate-800">
        <button onclick="respondDecision('${d.id}', 'approved')" class="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-3 py-1.5 rounded-xl text-xs transition flex items-center gap-1">
          <i class="fa-solid fa-check"></i> Aprobar Decisión
        </button>
        <button onclick="respondDecision('${d.id}', 'rejected')" class="bg-slate-200 dark:bg-slate-800 hover:bg-rose-100 dark:hover:bg-rose-950 text-slate-700 dark:text-rose-300 font-semibold px-3 py-1.5 rounded-xl text-xs transition flex items-center gap-1">
          <i class="fa-solid fa-xmark"></i> Rechazar
        </button>
      </div>
    `;

    if (d.status !== 'pending') {
      actionButtons = `
        <div class="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px]">
          <span class="font-bold ${d.status === 'approved' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}">
            ● Decisión ${d.status === 'approved' ? 'Aprobada' : 'Rechazada'} por el Gerente
          </span>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-xs text-amber-700 dark:text-amber-300 flex items-center gap-1.5">
          <i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(d.title)}
        </h4>
        <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400">Escalación</span>
      </div>
      <p class="text-xs text-slate-700 dark:text-slate-200">${escapeHtml(d.description)}</p>
      <div class="bg-slate-50 dark:bg-slate-950 p-2.5 rounded-xl text-[11px] text-slate-600 dark:text-slate-300">
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
    alert('Error respondiendo decisión: ' + e.message);
  }
}

function renderCalendar(events) {
  calendarContainer.innerHTML = '';
  if (events.length === 0) {
    calendarContainer.innerHTML = '<p class="col-span-2 text-slate-400 text-xs py-2">No hay reuniones agendadas en el calendario aún.</p>';
    return;
  }

  events.forEach(evt => {
    const card = document.createElement('div');
    card.className = 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-1.5';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-xs text-slate-900 dark:text-white">${escapeHtml(evt.title)}</h4>
        <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">${escapeHtml(evt.time_slot)}</span>
      </div>
      <p class="text-[11px] text-slate-500 font-medium">📅 ${escapeHtml(evt.sim_date)} • 👥 ${escapeHtml(evt.attendees)}</p>
      <p class="text-xs text-slate-600 dark:text-slate-300 pt-1">${escapeHtml(evt.agenda || '')}</p>
    `;
    calendarContainer.appendChild(card);
  });
}

// 9. Render Trajectories
function renderTrajectories(trajs) {
  trajectoriesListEl.innerHTML = '';
  if (trajs.length === 0) {
    trajectoriesListEl.innerHTML = '<p class="text-slate-400 text-center py-4">No hay trazas registradas aún.</p>';
    return;
  }

  trajs.forEach(t => {
    const item = document.createElement('div');
    item.className = 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 space-y-2 shadow-sm';
    
    let toolsHtml = '';
    if (t.tool_calls && t.tool_calls.length > 0) {
      toolsHtml = `
        <div class="bg-slate-50 dark:bg-slate-950 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1">
          <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">Herramientas Ejecutadas:</span>
          ${t.tool_calls.map(tc => `<div class="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">▶ ${tc.tool}(${JSON.stringify(tc.args)})</div>`).join('')}
        </div>
      `;
    }

    item.innerHTML = `
      <div class="flex items-center justify-between text-[10px] text-slate-400">
        <span class="font-bold text-indigo-500">Turno de Usuario</span>
        <span>${new Date(t.created_at).toLocaleTimeString()}</span>
      </div>
      <p class="text-xs text-slate-800 dark:text-slate-200 font-sans"><b>Prompt:</b> "${escapeHtml(t.prompt_used)}"</p>
      ${toolsHtml}
      <div class="text-xs text-slate-600 dark:text-slate-300">
        <span class="text-indigo-500 font-bold">Respuesta:</span>
        <p class="font-sans mt-0.5 line-clamp-3">${escapeHtml(t.final_response)}</p>
      </div>
    `;
    trajectoriesListEl.appendChild(item);
  });
}

// 10. Chat Message Handlers
function renderChatHistory(messages) {
  chatMessagesEl.innerHTML = '';
  messages.forEach(m => {
    if (m.sender === 'user') appendUserMessage(m.content, false);
    else if (m.sender === 'system') appendSystemMessage(m.content, false);
    else appendAssistantMessage(m.content, false, m.metadata ? JSON.parse(m.metadata) : null);
  });
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function appendUserMessage(text, scroll = true) {
  const div = document.createElement('div');
  div.className = 'flex items-start justify-end space-x-2';
  div.innerHTML = `
    <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-sm p-3 max-w-[85%] shadow-sm leading-relaxed text-xs">
      <p>${escapeHtml(text)}</p>
    </div>
  `;
  chatMessagesEl.appendChild(div);
  if (scroll) chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function appendAssistantMessage(text, scroll = true, metadata = null) {
  const div = document.createElement('div');
  div.className = 'flex items-start space-x-2.5';
  
  let toolBadges = '';
  if (metadata && metadata.tools && metadata.tools.length > 0) {
    toolBadges = `
      <div class="flex flex-wrap gap-1 mb-1.5">
        ${metadata.tools.map(t => `<span class="text-[9px] bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30 px-1.5 py-0.5 rounded font-mono font-medium">⚡ ${t.tool}</span>`).join('')}
      </div>
    `;
  }

  div.innerHTML = `
    <div class="w-7 h-7 rounded-lg bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold shrink-0 text-xs">
      H
    </div>
    <div class="bg-slate-100 dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm p-3 max-w-[88%] text-slate-800 dark:text-slate-200 shadow-sm leading-relaxed chat-body text-xs">
      ${toolBadges}
      <p class="whitespace-pre-line">${escapeHtml(text)}</p>
    </div>
  `;
  chatMessagesEl.appendChild(div);
  if (scroll) chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function appendSystemMessage(text, scroll = true) {
  const div = document.createElement('div');
  div.className = 'flex justify-center my-2';
  div.innerHTML = `
    <div class="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-500/40 text-amber-800 dark:text-amber-300 text-xs px-3 py-2 rounded-xl max-w-[92%] text-center">
      <p class="whitespace-pre-line">${escapeHtml(text)}</p>
    </div>
  `;
  chatMessagesEl.appendChild(div);
  if (scroll) chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

// 11. Event Listeners
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
    typingIndicator.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-indigo-500"></i> <span>Hermes está razonando y ejecutando herramientas...</span>';
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
      appendAssistantMessage(data.response, true, { tools: data.tools_executed });
      loadWorkspaceData(false);
    } catch (err) {
      typingIndicator.remove();
      appendSystemMessage(`Error al comunicar con Hermes: ${err.message}`);
    } finally {
      chatSubmitBtn.disabled = false;
    }
  });

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
        appendSystemMessage('⚡ Se han cargado 5 perfiles de desarrolladores en el ATS listos para asignación.');
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
        appendSystemMessage(`📄 CV de **${data.profile.name}** (${data.profile.role} - ${data.profile.seniority}) procesado.`);
      }
    } catch (err) {
      alert(`Error subiendo ${file.name}: ${err.message}`);
    }
  }
  loadWorkspaceData();
}

function updateApiKeyUI() {
  if (geminiApiKey && geminiApiKey.length > 10) {
    apiKeyStatusText.textContent = 'API Key Activa ✓';
    btnSettings.className = 'text-xs bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg font-medium shadow-sm flex items-center gap-1.5 transition';
  } else {
    apiKeyStatusText.textContent = 'API Key';
    btnSettings.className = 'text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg font-medium shadow-sm flex items-center gap-1.5 transition';
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Start
initTheme();
updateApiKeyUI();
setupSSE();
loadWorkspaceData();
setupEventListeners();
