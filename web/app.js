'use strict';
const $ = (id) => document.getElementById(id);
let state = null, token = '', activePlan = null, busy = false, fetching = false, online = false, planTimer;
const selected = new Set(), rows = new Map();
const bytes = (n) => n >= 1073741824 ? `${(n / 1073741824).toLocaleString('nl-NL', {maximumFractionDigits: 1})} GB` : `${(n / 1048576).toLocaleString('nl-NL', {maximumFractionDigits: 0})} MB`;
const percent = (n) => `${n.toLocaleString('nl-NL', {maximumFractionDigits: 1})}%`;
const text = (id, value) => { $(id).textContent = value; };
function announce(message) { text('notice', message); }
async function api(path, data) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Optimizer-Token': token}, body: JSON.stringify(data), signal: AbortSignal.timeout(12000)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'De actie kon niet worden uitgevoerd.');
  return result;
}
function selectionSummary() {
  const apps = (state?.apps || []).filter((app) => selected.has(app.id));
  text('selection-count', apps.length ? `${apps.length} ${apps.length === 1 ? 'app' : 'apps'} selected` : 'No apps selected');
  text('selection-memory', apps.length ? `About ${bytes(apps.reduce((sum, app) => sum + app.memory, 0))} RAM in use.` : 'Select apps you are not using right now.');
  $('review').disabled = !apps.length || busy || !online;
  $('select-all').disabled = !online || busy || !state?.apps.some((app) => app.closable);
}
function makeRow(app) {
  const row = document.createElement('li');
  row.className = 'app-row';
  // This static template contains no process data. All dynamic text uses textContent.
  row.innerHTML = '<div class="app-identity"><label class="select-hit"><input type="checkbox"></label><span class="app-icon" aria-hidden="true"></span><div><div class="app-name"></div><div class="app-sub"></div></div></div><div class="memory-value"><span class="mobile-label">RAM </span><span class="value"></span></div><div class="cpu-value"><span class="mobile-label">CPU </span><span class="value"></span></div><span class="app-status"></span>';
  const checkbox = row.querySelector('input');
  checkbox.setAttribute('aria-label', `${app.name} selecteren`);
  checkbox.disabled = !app.closable;
  row.querySelector('.select-hit').title = app.reason;
  checkbox.addEventListener('change', () => { checkbox.checked ? selected.add(app.id) : selected.delete(app.id); selectionSummary(); });
  row.querySelector('.app-icon').textContent = app.name.charAt(0).toUpperCase();
  row.querySelector('.app-name').textContent = app.name;
  const status = row.querySelector('.app-status');
  status.textContent = app.closable ? '○ Closable' : '◇ Protected';
  status.classList.toggle('protected', !app.closable);
  status.title = app.reason;
  return row;
}
function renderApps() {
  if (!state) return;
  const ids = new Set(state.apps.map((a) => a.id));
  for (const [id, row] of rows) { if (!ids.has(id)) { if (row.contains(document.activeElement)) $('search').focus(); row.remove(); rows.delete(id); selected.delete(id); } }
  const query = $('search').value.trim().toLocaleLowerCase('nl-NL');
  const filter = $('filter').value;
  let visible = 0;
  for (const app of state.apps) {
    if (!rows.has(app.id)) { const row = makeRow(app); rows.set(app.id, row); $('app-list').append(row); }
    const row = rows.get(app.id);
    row.querySelector('input').checked = selected.has(app.id);
    row.querySelector('.app-sub').textContent = `${app.count} ${app.count === 1 ? 'process' : 'processes'}`;
    row.querySelector('.memory-value .value').textContent = bytes(app.memory);
    row.querySelector('.cpu-value .value').textContent = percent(app.cpu);
    row.hidden = !app.name.toLocaleLowerCase('nl-NL').includes(query) || (filter === 'closable' && !app.closable) || (filter === 'protected' && app.closable);
    if (!row.hidden) visible++;
  }
  text('app-count', visible);
  $('empty').hidden = visible > 0;
  text('empty', filter === 'closable' ? 'No closable apps found. Protected processes keep running.' : 'No apps or processes found for this search.');
  selectionSummary();
}
function render() {
  text('hostname', state.hostname.toUpperCase());
  text('available', bytes(state.memory.available));
  document.querySelector('.memory-orbit').style.setProperty('--available-angle', `${state.memory.available / state.memory.total * 360}deg`);
  text('total-memory', `van ${bytes(state.memory.total)} totaal`);
  const closable = state.apps.filter((a) => a.closable);
  text('hero-description', closable.length ? `${closable.length} recognised apps use about ${bytes(closable.reduce((sum, a) => sum + a.memory, 0))} RAM. See which ones you can spare.` : 'Your processes are listed below. No closable apps are recognised right now. Protected work and system sessions remain active.');
  text('cpu', state.cpu === null ? 'Measuring…' : percent(state.cpu));
  $('cpu-bar').value = state.cpu || 0;
  text('cpu-detail', `${state.cores} logical processor cores`);
  text('memory', bytes(state.memory.used));
  $('memory-bar').value = state.memory.used / state.memory.total * 100;
  text('memory-detail', `${percent(state.memory.used / state.memory.total * 100)} used · swap ${bytes(state.memory.swapUsed)}`);
  text('disk', bytes(state.disk.free));
  $('disk-bar').value = state.disk.used / state.disk.total * 100;
  text('disk-detail', `${bytes(state.disk.free)} free of ${bytes(state.disk.total)} storage`);
  const hours = Math.floor(state.uptime / 3600);
  text('uptime', hours >= 24 ? `${Math.floor(hours / 24)} d ${hours % 24} u` : `${hours} u ${Math.floor(state.uptime % 3600 / 60)} m`);
  text('process-count', `${state.processCount} processes from your user`);
  text('updated', `Gemeten om ${new Date(state.updatedAt * 1000).toLocaleTimeString('nl-NL')}`);
  renderApps();
}
async function refresh(manual = false) {
  if (fetching || busy) return;
  fetching = true;
  $('refresh').disabled = true;
  try {
    const response = await fetch('/api/state', {signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error('No connection to the local service.');
    state = await response.json(); token = state.token; online = true;
    $('error').hidden = true;
    text('connection', $('auto-refresh').checked ? '● Connected locally' : 'Ⅱ Live refresh paused');
    render();
    if (manual) announce('Metingen en applijst bijgewerkt.');
  } catch (error) {
    online = false;
    text('connection', '○ Verbinding verbroken');
    text('error', 'De lokale service is niet bereikbaar. Getoonde metingen kunnen verouderd zijn. Start Adem opnieuw en kies Vernieuwen.');
    $('error').hidden = false;
    selectionSummary();
  } finally { fetching = false; $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', () => refresh(true));
$('search').addEventListener('input', renderApps);
$('filter').addEventListener('change', renderApps);
$('auto-refresh').addEventListener('change', () => { if ($('auto-refresh').checked) refresh(); else { text('connection', online ? 'Ⅱ Live refresh paused' : '○ Connection lost'); announce('Live refresh paused. You can refresh manually.'); } });
$('select-all').addEventListener('click', () => {
  const visible = state.apps.filter((a) => a.closable && !rows.get(a.id).hidden);
  if (!visible.length) { announce('No closable apps in this view.'); return; }
  const allSelected = visible.every((a) => selected.has(a.id));
  visible.forEach((a) => allSelected ? selected.delete(a.id) : selected.add(a.id));
  renderApps(); announce(allSelected ? 'Selection cleared in this view.' : `${visible.length} closable ${visible.length === 1 ? 'app' : 'apps'} selected. Review the selection to confirm.`);
});
$('review').addEventListener('click', async () => {
  if (busy) return;
  busy = true; selectionSummary();
  try {
    activePlan = await api('/api/plan', {apps: [...selected]});
    $('plan-apps').replaceChildren(...activePlan.apps.map((name) => { const li = document.createElement('li'); li.textContent = name; return li; }));
    text('plan-summary', `${activePlan.processCount} ${activePlan.processCount === 1 ? 'process' : 'processes'} · about ${bytes(activePlan.memory)} RAM in use. This is not a guaranteed speed improvement.`);
    text('dialog-error', ''); $('confirm').disabled = false;
    $('confirm-dialog').showModal(); $('cancel').focus();
    clearTimeout(planTimer);
    planTimer = setTimeout(() => { activePlan = null; $('confirm').disabled = true; text('dialog-error', 'The selection expired. Go back and review it again.'); }, 60000);
  } catch (error) { announce(error.message); }
  finally { busy = false; selectionSummary(); }
});
$('cancel').addEventListener('click', () => $('confirm-dialog').close());
$('confirm-dialog').addEventListener('keydown', (event) => {
  if (event.key !== 'Tab') return;
  const controls = [...$('confirm-dialog').querySelectorAll('button:not(:disabled)')];
  const first = controls[0], last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
$('confirm-dialog').addEventListener('close', () => {
  activePlan = null; clearTimeout(planTimer);
  ($('review').disabled ? $('search') : $('review')).focus();
});
$('confirm').addEventListener('click', async () => {
  if (!activePlan || busy) return;
  busy = true; $('confirm').disabled = true; clearTimeout(planTimer);
  const plan = activePlan.plan; activePlan = null;
  try {
    const result = await api('/api/close', {plan, confirmed: true});
    const closed = result.results.filter((r) => ['closed', 'already_closed'].includes(r.status)).length;
    const pending = result.results.filter((r) => r.status === 'pending').length;
    const failed = result.results.length - closed - pending;
    $('confirm-dialog').close(); selected.clear();
    announce(`${closed} ${closed === 1 ? 'process' : 'processes'} closed or already stopped. ${pending} still active after the stop request. ${failed} skipped or failed.`);
  } catch (error) {
    const message = `${error.message} De actie kan al verwerkt zijn. Ga terug, vernieuw en controleer de apps.`;
    if ($('confirm-dialog').open) text('dialog-error', message); else announce(message);
  }
  finally { busy = false; selectionSummary(); await refresh(); }
});
refresh();
setInterval(() => { if ($('auto-refresh').checked && !$('confirm-dialog').open && !document.hidden) refresh(); }, 4000);
