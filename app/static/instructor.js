// Colima Instructor Control Logic

let instructorPin = sessionStorage.getItem('colima_instructor_pin') || '';

const authScreen = document.getElementById('auth-screen');
const appScreen = document.getElementById('app-screen');
const pinForm = document.getElementById('pin-form');
const pinInput = document.getElementById('pin-input');
const pinError = document.getElementById('pin-error');
const btnLogout = document.getElementById('btn-logout');

const instTimeDisplay = document.getElementById('inst-time-display');
const instDayDisplay = document.getElementById('inst-day-display');
const instSpeedDisplay = document.getElementById('inst-speed-display');
const instStatusLabel = document.getElementById('inst-status-label');
const statActiveStudents = document.getElementById('stat-active-students');

const customEventForm = document.getElementById('custom-event-form');
const eventTitle = document.getElementById('event-title');
const eventDesc = document.getElementById('event-desc');

function init() {
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

  customEventForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = eventTitle.value.trim();
    const desc = eventDesc.value.trim();
    if (!title || !desc) return;

    await injectEvent(title, desc, 'warning');
    eventTitle.value = '';
    eventDesc.value = '';
    alert('Evento global emitido a todos los alumnos!');
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
    pinError.textContent = 'Error de conexión: ' + err.message;
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
    instStatusLabel.className = 'text-xs uppercase font-bold tracking-widest text-slate-400';
  } else {
    instSpeedDisplay.textContent = `${speed}x Vel.`;
    instStatusLabel.textContent = 'EN EJECUCIÓN CONTINUA';
    instStatusLabel.className = 'text-xs uppercase font-bold tracking-widest text-emerald-400';
  }

  // Update speed button active styling
  document.querySelectorAll('.speed-btn').forEach(btn => {
    const s = parseFloat(btn.dataset.speed);
    if (s === speed) {
      btn.classList.add('bg-indigo-600', 'text-white', 'border-indigo-500');
      btn.classList.remove('bg-slate-800', 'text-slate-200');
    } else {
      btn.classList.remove('bg-indigo-600', 'text-white', 'border-indigo-500');
      btn.classList.add('bg-slate-800', 'text-slate-200');
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
    const res = await fetch('/api/instructor/speed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: instructorPin, speed_multiplier: multiplier })
    });
    if (!res.ok) alert('Error al actualizar velocidad');
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function stepDay() {
  try {
    const res = await fetch('/api/instructor/step-day', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: instructorPin })
    });
    if (!res.ok) alert('Error avanzando día');
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function resetClock() {
  if (!confirm('¿Seguro que deseas reiniciar el reloj al Día 1 (12 Sep 2030)?')) return;
  try {
    const res = await fetch('/api/instructor/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: instructorPin })
    });
    if (!res.ok) alert('Error reiniciando reloj');
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
    desc = 'El desarrollador backend principal reporta baja por 3 días. Sus tareas asignadas no avanzarán hasta su recuperación.';
    sev = 'danger';
  } else if (type === 'scope') {
    title = 'Cambio de Alcance: Pasarela SPEI';
    desc = 'El cliente solicitó con carácter de urgencia incorporar soporte bancario SPEI directo no considerado en el backlog inicial.';
    sev = 'warning';
  } else if (type === 'speedup') {
    title = 'Entrega Anticipada en Frontend';
    desc = 'El equipo frontend completó la maquetación de interfaces con 40% de ahorro en horas estimadas.';
    sev = 'info';
  } else if (type === 'outage') {
    title = 'Fallo Crítico en Pasarela de Pagos (QA)';
    desc = 'Las pruebas de integración detectaron un error 500 intermitente en el webhook de pagos que bloquea el pase a staging.';
    sev = 'danger';
  }

  await injectEvent(title, desc, sev);
  alert(`Evento "${title}" emitido a todos los alumnos!`);
}

async function injectEvent(title, desc, severity) {
  try {
    const res = await fetch('/api/instructor/inject-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pin: instructorPin,
        title: title,
        description: desc,
        severity: severity
      })
    });
    if (!res.ok) alert('Error inyectando evento');
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// Start
init();
