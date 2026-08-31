// Colima Student Sandbox Application Logic

const STORAGE_KEYS = {
  WORKSPACE_ID: 'colima_workspace_id',
  API_KEY: 'colima_gemini_api_key'
};

// Initialize or restore workspace ID
let workspaceId = localStorage.getItem(STORAGE_KEYS.WORKSPACE_ID);
if (!workspaceId) {
  workspaceId = 'ws-' + Math.random().toString(36).substring(2, 10);
  localStorage.setItem(STORAGE_KEYS.WORKSPACE_ID, workspaceId);
}

let geminiApiKey = localStorage.getItem(STORAGE_KEYS.API_KEY) || '';

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

const cvFileInput = document.getElementById('cv-file-input');
const dropzone = document.getElementById('dropzone');
const talentListEl = document.getElementById('talent-list');
const talentCountBadge = document.getElementById('talent-count-badge');
const hiresListEl = document.getElementById('hires-list');
const hiresCountBadge = document.getElementById('hires-count-badge');
const trajectoriesListEl = document.getElementById('trajectories-list');

// Tabs
const tabBtnTalent = document.getElementById('tab-btn-talent');
const tabBtnInspector = document.getElementById('tab-btn-inspector');
const tabBtnHires = document.getElementById('tab-btn-hires');
const tabContentTalent = document.getElementById('tab-content-talent');
const tabContentInspector = document.getElementById('tab-content-inspector');
const tabContentHires = document.getElementById('tab-content-hires');

// Init state
function init() {
  updateApiKeyUI();
  setupSSE();
  loadWorkspaceData();
  setupEventListeners();
}

function updateApiKeyUI() {
  if (geminiApiKey && geminiApiKey.length > 10) {
    apiKeyStatusText.textContent = 'API Key Activa ✓';
    btnSettings.classList.remove('bg-blue-600', 'hover:bg-blue-500');
    btnSettings.classList.add('bg-emerald-600', 'hover:bg-emerald-500');
  } else {
    apiKeyStatusText.textContent = 'Configurar API Key';
    btnSettings.classList.remove('bg-emerald-600', 'hover:bg-emerald-500');
    btnSettings.classList.add('bg-blue-600', 'hover:bg-blue-500');
  }
}

// Setup Server-Sent Events (SSE) for Real-Time Master Clock Sync
function setupSSE() {
  const evtSource = new EventSource('/api/simulation/stream');

  evtSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'clock_update') {
        renderClockState(payload.data);
        // Refresh workspace tasks to see live progress
        loadWorkspaceData(false);
      } else if (payload.type === 'global_event') {
        handleGlobalEvent(payload.event);
      }
    } catch (e) {
      console.error('[SSE Parse Error]', e);
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
    simSpeedBadge.className = 'text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-700 text-slate-300';
    clockPulse.classList.add('hidden');
  } else {
    simSpeedBadge.textContent = `${speed}x Vel.`;
    simSpeedBadge.className = 'text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30';
    clockPulse.classList.remove('hidden');
  }
}

function handleGlobalEvent(evt) {
  // Show in chat
  appendSystemMessage(`🚨 **EVENTO GLOBAL DEL TALLER:** ${evt.title}\n\n${evt.description}`);
}

// Fetch and render workspace data
async function loadWorkspaceData(renderChat = true) {
  try {
    const res = await fetch(`/api/workspaces/${workspaceId}`);
    if (!res.ok) return;
    const data = await res.json();

    renderKanban(data.tasks || []);
    renderTalentPool(data.talent_pool || []);
    renderHiringRequests(data.hiring_requests || []);
    renderTrajectories(data.trajectories || []);

    if (renderChat && data.messages && data.messages.length > 0) {
      renderChatHistory(data.messages);
    }
  } catch (e) {
    console.error('[Load Error]', e);
  }
}

// Render Kanban Board
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
    card.className = 'bg-slate-950 border border-slate-800/90 hover:border-slate-700 rounded-xl p-3 shadow-md space-y-2 transition relative';

    let priorityBadge = '<span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">Normal</span>';
    if (task.priority === 'urgent') {
      priorityBadge = '<span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">Urgente</span>';
    } else if (task.priority === 'high') {
      priorityBadge = '<span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">Alta</span>';
    }

    let blockerAlert = '';
    if (task.blocker_reason) {
      blockerAlert = `<div class="bg-rose-950/40 border border-rose-500/40 text-rose-300 text-[10px] p-1.5 rounded-lg flex items-center gap-1">
        <i class="fa-solid fa-triangle-exclamation"></i> <span>${task.blocker_reason}</span>
      </div>`;
    }

    card.innerHTML = `
      <div class="flex items-start justify-between gap-1">
        <h4 class="font-semibold text-xs text-white leading-snug">${escapeHtml(task.title)}</h4>
        ${priorityBadge}
      </div>
      <p class="text-[11px] text-slate-400 leading-tight">${escapeHtml(task.description || '')}</p>
      ${blockerAlert}
      
      <!-- Progress Bar -->
      <div class="space-y-1">
        <div class="flex justify-between text-[10px] text-slate-400 font-mono">
          <span>${task.completed_hours}h / ${task.estimated_hours}h</span>
          <span class="font-bold text-blue-400">${task.progress_percent}%</span>
        </div>
        <div class="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full task-progress-bar" style="width: ${task.progress_percent}%"></div>
        </div>
      </div>

      <!-- Assignee Footer -->
      <div class="flex items-center justify-between pt-1 border-t border-slate-900 text-[10px]">
        <span class="text-slate-400 flex items-center gap-1">
          <i class="fa-solid fa-user-circle text-blue-400"></i> ${escapeHtml(task.assignee_name || 'Sin asignar')}
        </span>
        <span class="text-slate-500">${escapeHtml(task.role_required)}</span>
      </div>
    `;

    cols[status].appendChild(card);
  });

  // Update badge counts
  document.getElementById('count-backlog').textContent = counts.backlog;
  document.getElementById('count-in_progress').textContent = counts.in_progress;
  document.getElementById('count-review').textContent = counts.review;
  document.getElementById('count-done').textContent = counts.done;

  document.getElementById('stat-tasks-total').textContent = tasks.length;
  document.getElementById('stat-tasks-progress').textContent = counts.in_progress;
  document.getElementById('stat-tasks-done').textContent = counts.done;
}

// Render Talent Pool (ATS)
function renderTalentPool(talent) {
  talentListEl.innerHTML = '';
  talentCountBadge.textContent = talent.length;

  if (talent.length === 0) {
    talentListEl.innerHTML = `
      <div class="text-center py-6 text-slate-500 text-xs">
        <i class="fa-solid fa-folder-open text-2xl mb-1 text-slate-600"></i>
        <p>No hay perfiles cargados en el ATS.</p>
        <p class="text-[10px] mt-1">Arrastra PDFs o haz clic en "Cargar Demo".</p>
      </div>
    `;
    return;
  }

  talent.forEach(p => {
    const card = document.createElement('div');
    card.className = 'bg-slate-950 border border-slate-800 rounded-xl p-3 space-y-2 shadow-sm';
    
    let seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">Mid</span>';
    if (p.seniority === 'Senior') {
      seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Senior</span>';
    } else if (p.seniority === 'Junior') {
      seniorityBadge = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Junior</span>';
    }

    const skillsPills = (p.skills || []).slice(0, 4).map(s => 
      `<span class="text-[9px] bg-slate-900 border border-slate-800 text-slate-300 px-1.5 py-0.5 rounded">${escapeHtml(s)}</span>`
    ).join(' ');

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div>
          <h4 class="font-bold text-xs text-white">${escapeHtml(p.name)}</h4>
          <p class="text-[10px] text-slate-400">${escapeHtml(p.role)}</p>
        </div>
        ${seniorityBadge}
      </div>
      <div class="flex flex-wrap gap-1 pt-1">
        ${skillsPills}
      </div>
      <div class="flex items-center justify-between pt-1 text-[10px] text-slate-500">
        <span>Factor Prod: <b>${p.productivity_factor}x</b></span>
        <span class="text-emerald-400">● ${escapeHtml(p.status || 'Disponible')}</span>
      </div>
    `;
    talentListEl.appendChild(card);
  });
}

// Render Hiring Requests
function renderHiringRequests(hires) {
  hiresListEl.innerHTML = '';
  hiresCountBadge.textContent = hires.length;

  if (hires.length === 0) {
    hiresListEl.innerHTML = `
      <div class="text-center py-6 text-slate-500 text-xs">
        <i class="fa-solid fa-clipboard-check text-2xl mb-1 text-slate-600"></i>
        <p>No hay solicitudes de contratación pendientes.</p>
      </div>
    `;
    return;
  }

  hires.forEach(h => {
    const card = document.createElement('div');
    card.className = 'bg-slate-950 border border-amber-500/30 rounded-xl p-3 space-y-1.5 shadow-sm';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-xs text-amber-300">${escapeHtml(h.role)}</h4>
        <span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">Urgencia: ${h.urgency}</span>
      </div>
      <p class="text-[11px] text-slate-300"><b>Skills requeridas:</b> ${escapeHtml(h.required_skills)}</p>
      <p class="text-[10px] text-slate-400 italic">"${escapeHtml(h.rationale)}"</p>
    `;
    hiresListEl.appendChild(card);
  });
}

// Render Inspector Trajectories
function renderTrajectories(trajs) {
  trajectoriesListEl.innerHTML = '';
  if (trajs.length === 0) {
    trajectoriesListEl.innerHTML = '<p class="text-slate-500 text-center py-4">No hay trazas registradas aún.</p>';
    return;
  }

  trajs.forEach(t => {
    const item = document.createElement('div');
    item.className = 'bg-slate-900 border border-slate-800 rounded-xl p-3 space-y-2';
    
    let toolsHtml = '';
    if (t.tool_calls && t.tool_calls.length > 0) {
      toolsHtml = `
        <div class="bg-slate-950 p-2 rounded-lg border border-slate-800 space-y-1">
          <span class="text-[10px] text-blue-400 font-bold">Herramientas Ejecutadas:</span>
          ${t.tool_calls.map(tc => `<div class="text-[10px] text-emerald-400 font-mono">▶ ${tc.tool}(${JSON.stringify(tc.args)})</div>`).join('')}
        </div>
      `;
    }

    item.innerHTML = `
      <div class="flex items-center justify-between text-[10px] text-slate-400">
        <span class="font-bold text-indigo-300">Turno de Usuario</span>
        <span>${new Date(t.created_at).toLocaleTimeString()}</span>
      </div>
      <p class="text-[11px] text-slate-200 font-sans"><b>Prompt:</b> "${escapeHtml(t.prompt_used)}"</p>
      ${toolsHtml}
      <div class="text-[10px] text-slate-400">
        <span class="text-indigo-400 font-bold">Respuesta Final:</span>
        <p class="font-sans text-slate-300 mt-0.5 line-clamp-3">${escapeHtml(t.final_response)}</p>
      </div>
    `;
    trajectoriesListEl.appendChild(item);
  });
}

// Chat functions
function renderChatHistory(messages) {
  chatMessagesEl.innerHTML = '';
  messages.forEach(m => {
    if (m.sender === 'user') {
      appendUserMessage(m.content, false);
    } else if (m.sender === 'system') {
      appendSystemMessage(m.content, false);
    } else {
      appendAssistantMessage(m.content, false, m.metadata ? JSON.parse(m.metadata) : null);
    }
  });
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function appendUserMessage(text, scroll = true) {
  const div = document.createElement('div');
  div.className = 'flex items-start justify-end space-x-2';
  div.innerHTML = `
    <div class="bg-blue-600 text-white rounded-2xl rounded-tr-sm p-3 max-w-[85%] shadow-md leading-relaxed">
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
        ${metadata.tools.map(t => `<span class="text-[9px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-1.5 py-0.5 rounded font-mono">⚡ ${t.tool}</span>`).join('')}
      </div>
    `;
  }

  div.innerHTML = `
    <div class="w-7 h-7 rounded-lg bg-blue-600/30 border border-blue-500/50 flex items-center justify-center text-blue-400 font-bold shrink-0">
      H
    </div>
    <div class="bg-slate-800/90 border border-slate-700/80 rounded-2xl rounded-tl-sm p-3 max-w-[85%] text-slate-200 shadow-sm leading-relaxed chat-body">
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
    <div class="bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs px-3 py-2 rounded-xl max-w-[90%] text-center">
      <p class="whitespace-pre-line">${escapeHtml(text)}</p>
    </div>
  `;
  chatMessagesEl.appendChild(div);
  if (scroll) chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

// Event Listeners
function setupEventListeners() {
  // Chat form submit
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = chatInput.value.trim();
    if (!msg) return;

    chatInput.value = '';
    appendUserMessage(msg);
    
    // Disable submit while processing
    chatSubmitBtn.disabled = true;
    
    // Typing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.id = 'typing-indicator';
    typingIndicator.className = 'flex items-center space-x-2 text-slate-400 text-xs p-2';
    typingIndicator.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-blue-400"></i> <span>Hermes está razonando y ejecutando herramientas...</span>';
    chatMessagesEl.appendChild(typingIndicator);
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (geminiApiKey) {
        headers['X-Gemini-API-Key'] = geminiApiKey;
      }

      const res = await fetch(`/api/workspaces/${workspaceId}/agent/chat`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({ message: msg })
      });

      const data = await res.json();
      typingIndicator.remove();
      appendAssistantMessage(data.response, true, { tools: data.tools_executed });
      
      // Reload workspace data to reflect changes
      loadWorkspaceData(false);
    } catch (err) {
      typingIndicator.remove();
      appendSystemMessage(`Error al comunicar con Hermes: ${err.message}`);
    } finally {
      chatSubmitBtn.disabled = false;
    }
  });

  // Quick Action Chips
  document.querySelectorAll('.quick-prompt').forEach(btn => {
    btn.addEventListener('click', () => {
      chatInput.value = btn.textContent.trim().replace(/^[\uD800-\uDBFF\uDC00-\uDFFF\u2600-\u27BF]+\s*/, '');
      chatForm.dispatchEvent(new Event('submit'));
    });
  });

  // Modal Settings
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

  // Modal Samples
  btnSamples.addEventListener('click', () => samplesModal.classList.remove('hidden'));
  samplesCloseBtn.addEventListener('click', () => samplesModal.classList.add('hidden'));

  // Quick Load Demo Button
  btnQuickLoad.addEventListener('click', async () => {
    try {
      const res = await fetch(`/api/workspaces/${workspaceId}/setup-demo`, { method: 'POST' });
      if (res.ok) {
        appendSystemMessage('⚡ Se han cargado 5 perfiles de desarrolladores en el ATS listos para asignación.');
        loadWorkspaceData();
      }
    } catch (e) {
      alert('Error cargando demo: ' + e.message);
    }
  });

  // Drag & Drop CV PDF
  dropzone.addEventListener('click', () => cvFileInput.click());
  cvFileInput.addEventListener('change', async (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      await uploadFiles(files);
    }
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('border-blue-500', 'bg-blue-950/20');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('border-blue-500', 'bg-blue-950/20');
  });

  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropzone.classList.remove('border-blue-500', 'bg-blue-950/20');
    if (e.dataTransfer.files.length > 0) {
      await uploadFiles(e.dataTransfer.files);
    }
  });

  // Tabs switching
  tabBtnTalent.addEventListener('click', () => switchTab('talent'));
  tabBtnInspector.addEventListener('click', () => switchTab('inspector'));
  tabBtnHires.addEventListener('click', () => switchTab('hires'));
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
        appendSystemMessage(`📄 CV de **${data.profile.name}** (${data.profile.role} - ${data.profile.seniority}) procesado y añadido al ATS.`);
      }
    } catch (err) {
      alert(`Error subiendo ${file.name}: ${err.message}`);
    }
  }
  loadWorkspaceData();
}

function switchTab(tab) {
  tabBtnTalent.className = 'flex-1 py-3 font-semibold text-slate-400 hover:text-slate-200 text-center transition';
  tabBtnInspector.className = 'flex-1 py-3 font-semibold text-slate-400 hover:text-slate-200 text-center transition';
  tabBtnHires.className = 'flex-1 py-3 font-semibold text-slate-400 hover:text-slate-200 text-center transition';

  tabContentTalent.classList.add('hidden');
  tabContentInspector.classList.add('hidden');
  tabContentHires.classList.add('hidden');

  if (tab === 'talent') {
    tabBtnTalent.className = 'flex-1 py-3 font-semibold text-blue-400 border-b-2 border-blue-500 text-center transition';
    tabContentTalent.classList.remove('hidden');
  } else if (tab === 'inspector') {
    tabBtnInspector.className = 'flex-1 py-3 font-semibold text-indigo-400 border-b-2 border-indigo-500 text-center transition';
    tabContentInspector.classList.remove('hidden');
  } else if (tab === 'hires') {
    tabBtnHires.className = 'flex-1 py-3 font-semibold text-amber-400 border-b-2 border-amber-500 text-center transition';
    tabContentHires.classList.remove('hidden');
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Start
init();
