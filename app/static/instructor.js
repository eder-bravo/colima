// Colima Instructor Control Logic

let instructorPin = sessionStorage.getItem('colima_instructor_pin') || '';

const authScreen = document.getElementById('auth-screen');
const appScreen = document.getElementById('app-screen');
const pinForm = document.getElementById('pin-form');
const pinInput = document.getElementById('pin-input');
const pinError = document.getElementById('pin-error');
const btnLogout = document.getElementById('btn-logout');
const btnInstTheme = document.getElementById('btn-inst-theme');

const instTimeDisplay = document.getElementById('inst-time-display');
const instDayDisplay = document.getElementById('inst-day-display');
const instSpeedDisplay = document.getElementById('inst-speed-display');
const instStatusLabel = document.getElementById('inst-status-label');
const statActiveStudents = document.getElementById('stat-active-students');

function initTheme() {
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (isDark) document.documentElement.classList.add('dark');

  if (btnInstTheme) {
    btnInstTheme.addEventListener('click', () => {
      document.documentElement.classList.toggle('dark');
    });
  }
}

function init() {
  initTheme();
  if (instructorPin) {
    verifyAndUnlock(instructorPin);
  }

  pinForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pin = pinInput.value.trim();
    await verifyAndUnlock(pin);
  });

  btnLogout.addEventListener('click', () => {
    sessionStorage.removeItem('colima_instructor_pin');
    instructorPin = '';
    authScreen.classList.remove('hidden');
  });
}

async function verifyAndUnlock(pin) {
  try {
    const res = await fetch('/api/instructor/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: pin })
    });

    if (res.ok) {
      instructorPin = pin;
      sessionStorage.setItem('colima_instructor_pin', pin);
      authScreen.classList.add('hidden');
      pinError.classList.add('hidden');
      setupInstructorSSE();
      fetchTelemetry();
      setInterval(fetchTelemetry, 5000);
    } else {
      pinError.classList.remove('hidden');
    }
  } catch (err) {
    pinError.textContent = 'Error: ' + err.message;
    pinError.classList.remove('hidden');
  }
}

function setupInstructorSSE() {
  const evtSource = new EventSource('/api/simulation/stream');
  evtSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'clock_update') {
        renderClockState(payload.data);
      }
    } catch (e) {
      console.error(e);
    }
  };
}

function renderClockState(state) {
  if (!state) return;
  instTimeDisplay.textContent = state.formatted_time || '12 Sep 2030, 09:00 AM';
  instDayDisplay.textContent = `Día ${state.day_number || 1} del Proyecto`;

  const speed = state.speed_multiplier || 0;
  if (state.status === 'paused' || speed === 0) {
    instSpeedDisplay.textContent = '0x (Pausado)';
    instStatusLabel.textContent = 'PAUSADO';
    instStatusLabel.className = 'text-[11px] uppercase font-bold tracking-widest text-slate-400';
  } else {
    instSpeedDisplay.textContent = `${speed}x Vel.`;
    instStatusLabel.textContent = 'EN EJECUCIÓN';
    instStatusLabel.className = 'text-[11px] uppercase font-bold tracking-widest text-emerald-600 dark:text-emerald-400';
  }

  document.querySelectorAll('.speed-btn').forEach(btn => {
    const s = parseFloat(btn.dataset.speed);
    if (s === speed) {
      btn.className = 'speed-btn bg-indigo-600 text-white border border-indigo-500 px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-sm';
    } else {
      btn.className = 'speed-btn bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5';
    }
  });
}

async function fetchTelemetry() {
  if (!instructorPin) return;
  try {
    const res = await fetch(`/api/instructor/stats?pin=${encodeURIComponent(instructorPin)}`);
    if (res.ok) {
      const data = await res.json();
      statActiveStudents.textContent = data.active_students || 0;
    }
  } catch (e) {
    console.error(e);
  }
}

async function setSpeed(multiplier) {
  try {
    await fetch('/api/instructor/speed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: instructorPin, speed_multiplier: multiplier })
    });
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function stepDay() {
  try {
    await fetch('/api/instructor/step-day', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: instructorPin })
    });
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function resetClock() {
  if (!confirm('¿Seguro que deseas reiniciar el reloj al Día 1?')) return;
  try {
    await fetch('/api/instructor/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: instructorPin })
    });
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function injectPreset(type) {
  let title = '';
  let desc = '';
  let sev = 'warning';

  if (type === 'sick') {
    title = 'Dev Backend con Licencia Médica';
    desc = 'El desarrollador backend reporta baja médica por 3 días. Tareas en riesgo.';
    sev = 'danger';
  } else if (type === 'scope') {
    title = 'Cambio de Alcance: Pasarela SPEI';
    desc = 'El cliente solicita soporte bancario SPEI directo urgente no presupuestado.';
    sev = 'warning';
  } else if (type === 'speedup') {
    title = 'Entrega Anticipada en Frontend';
    desc = 'Frontend concluye componentes 40% antes de lo estimado.';
    sev = 'info';
  } else if (type === 'outage') {
    title = 'Bug Crítico en QA';
    desc = 'Fallo de seguridad en JWT detectado por QA bloquea el pase a staging.';
    sev = 'danger';
  }

  await injectEvent(title, desc, sev);
  alert(`Evento "${title}" emitido.`);
}

async function injectEvent(title, desc, severity) {
  try {
    await fetch('/api/instructor/inject-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pin: instructorPin,
        title: title,
        description: desc,
        severity: severity
      })
    });
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

init();
