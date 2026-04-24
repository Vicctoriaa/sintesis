/* ─────────────────────────────────────────────────────────────────
   api.js — Honeypot Dashboard · SOC honeycos
   Integración con la API Flask (CT109 · /api/).
   Depende de: charts.js y views.js (debe cargarse el último).
───────────────────────────────────────────────────────────────── */

/* ── Configuración ── */
const API_BASE   = '/api';   // Nginx proxy → http://127.0.0.1:5000
const REFRESH_MS = 30_000;   // Auto-refresh cada 30s

let apiAvailable = false;    // Se actualiza tras primer health check
let lastSince    = null;     // Cursor ISO para polling incremental de logs
let refreshTimer = null;

async function apiFetch(path) {
  try {
    const r = await fetch(API_BASE + path, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

async function checkApiHealth() {
  const h = await apiFetch('/health');
  apiAvailable = !!(h && h.status === 'ok');
  const dot = document.querySelector('.live-dot');
  if (dot) dot.style.background = apiAvailable ? '#22c55e' : '#c0392b';
  return apiAvailable;
}

/* ═══════════════════════════════════════════════════════════════
   INTEGRACIÓN API REAL — CT109 Flask
   Reemplaza datos estáticos con datos reales de la API cada 30s.
═══════════════════════════════════════════════════════════════ */

  /* ── Helpers ── */
  function sevFromEvent(ev) {
    const a = ev.action || '', l = ev.level || '';
    if (a === 'brute_force' || l === 'ERROR')   return 'CRÍTICO';
    if (a === 'login_attempt' || a === 'command') return 'ALTO';
    if (a === 'file_access' || a === 'request')   return 'MEDIO';
    return 'BAJO';
  }

  function fmtTs(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      const pad = n => String(n).padStart(2,'0');
      return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    } catch { return iso; }
  }

  function msgFromEvent(ev) {
    const a = ev.action || '';
    if (a === 'brute_force')   return `Brute force detectado — ${ev.src_ip}`;
    if (a === 'login_attempt') return `Login ${ev.username ? ev.username + ' · ' : ''}${ev.src_ip}`;
    if (a === 'command')       return `Comando ejecutado — ${ev.command || '?'}`;
    if (a === 'request')       return `Request ${ev.method || 'GET'} ${ev.path || '/'}`;
    if (a === 'file_access')   return `Acceso fichero ${ev.path || '?'}`;
    if (a === 'connection')    return `Conexión — ${ev.src_ip}`;
    return ev.message || a;
  }

  function subFromEvent(ev) {
    const parts = [];
    if (ev.src_ip)   parts.push(ev.src_ip);
    if (ev.username) parts.push(`user: ${ev.username}`);
    if (ev.path)     parts.push(ev.path);
    if (ev.method)   parts.push(ev.method);
    if (ev.status)   parts.push(String(ev.status));
    return parts.join(' · ') || '—';
  }

  /* ── Actualizar métricas tarjetas ── */
  function updateMetricCards(stats) {
    const el = id => document.getElementById(id);
    if (el('m-conn'))  el('m-conn').textContent  = stats.total ?? '—';
    if (el('m-login')) el('m-login').textContent = stats.login_attempts ?? '—';
    if (el('m-bf'))    el('m-bf').textContent    = stats.brute_force ?? '—';
    // IPs únicas: contamos top_ips
    if (el('m-ip'))    el('m-ip').textContent    = stats.unique_ips ?? stats.top_ips?.length ?? '—';  // unique_ips = COUNT(DISTINCT src_ip) de la API
  }

  /* ── Actualizar gráfico de tráfico 24h ── */
  function updateTrafficFromStats(stats) {
    if (!stats.by_hour) return;
    const now   = new Date();
    const slots = [];
    for (let i = 23; i >= 0; i--) {
      const d = new Date(now);
      d.setHours(d.getHours() - i, 0, 0, 0);
      const key = d.toISOString().slice(0, 14) + '00:00Z';
      slots.push(stats.by_hour[key] || 0);
    }
    trafficData = slots;
    drawTrafficChart();
  }

  /* ── Actualizar donut chart de servicios ── */
  function updateSvcChartFromStats(stats) {
    if (!stats.by_service) return;
    // Delegar en la función de charts.js que mantiene HTTP y HTTPS separados
    if (typeof updateSvcChartFromStats_charts === 'function') {
      updateSvcChartFromStats_charts(stats.by_service);
    } else {
      // Fallback: orden correcto SSH, HTTP, HTTPS, FTP, SMB, RDP, Otro
      const s     = stats.by_service;
      const order = ['ssh','http','https','ftp','smb','rdp'];
      const otros = Object.entries(s)
        .filter(([k]) => !order.includes(k))
        .reduce((acc, [, v]) => acc + v, 0);
      svcData = [...order.map(k => s[k] || 0), otros];
      drawSvcChart();
    }
  }

  /* ── Actualizar tabla Top IPs (resumen) ── */
  function updateTopIPsTable(topIps) {
    const tbody = document.getElementById('top-ips-tbody');
    if (!tbody || !topIps?.length) return;
    tbody.innerHTML = topIps.slice(0, 6).map(d => `
      <tr>
        <td class="ip-addr">${d.ip}</td>
        <td class="ip-count">${d.hits}</td>
        <td><span class="ip-tag it-blue">${d.hits > 10 ? 'alto volumen' : 'normal'}</span></td>
      </tr>`).join('');
  }

  /* ── Actualizar feed de actividad reciente (resumen) ── */
  function updateActivityFeed(events) {
    const feed = document.getElementById('activity-feed');
    if (!feed || !events?.length) return;

    const colorMap = {
      CRÍTICO: 'ind-red', ALTO: 'ind-amber', MEDIO: 'ind-blue', BAJO: 'ind-gray'
    };
    const tagMap = {
      CRÍTICO: 'tag-red', ALTO: 'tag-amber', MEDIO: 'tag-blue', BAJO: 'tag-gray'
    };

    feed.innerHTML = events.slice(0, 6).map(ev => {
      const sev = sevFromEvent(ev);
      return `
        <div class="event-row">
          <div class="event-indicator ${colorMap[sev] || 'ind-gray'}"></div>
          <div class="event-body">
            <div class="event-service">${ev.service || '?'} · ${ev.action || '?'}</div>
            <div class="event-msg">${msgFromEvent(ev)}</div>
            <div class="event-meta">${subFromEvent(ev)}</div>
          </div>
          <div class="event-right">
            <div class="event-time">${fmtTs(ev.timestamp || ev.received_at)}</div>
            <span class="event-tag ${tagMap[sev] || 'tag-gray'}">${sev}</span>
          </div>
        </div>`;
    }).join('');
  }

  /* ── Actualizar tabla eventos (pestaña Eventos) ── */
  function updateEventsFromAPI(events) {
    if (!events?.length) return;
    EV_EVENTS = events.map(ev => ({
      sev:    sevFromEvent(ev),
      ts:     fmtTs(ev.timestamp || ev.received_at),
      svc:    ev.service || '?',
      action: ev.action  || '?',
      src:    ev.src_ip  || '?',
      msg:    msgFromEvent(ev),
      sub:    subFromEvent(ev),
      extra:  ev,
    }));
    evPage = 0;
    evRender();
  }

  /* ── Actualizar visor de logs ── */
  function updateLogsFromAPI(events) {
    if (!events?.length) return;
    const term = document.getElementById('log-terminal');
    if (!term) return;

    // Solo añadir líneas nuevas (modo incremental)
    events.slice().reverse().forEach(ev => {
      const entry = {
        ts:     fmtTs(ev.timestamp || ev.received_at)
                + '.' + String(new Date().getMilliseconds()).padStart(3,'0'),
        lvl:    ev.level  || 'INFO',
        svc:    ev.service || '?',
        action: ev.action  || '?',
        src:    ev.src_ip  || '',
        msg:    [ev.message || ev.action, ev.src_ip, ev.path || ev.command || '']
                  .filter(Boolean).join(' · '),
      };
      const line = renderLogLine(entry, true);
      term.insertBefore(line, term.firstChild);
    });

    // Guardar cursor para próximo poll
    if (events[0]?.received_at) {
      // Normalizar: quitar offset +00:00/Z y microsegundos para compatibilidad SQLite
      lastSince = events[0].received_at
        .replace(/\.\d+/, '')       // quitar microsegundos
        .replace('+00:00', '')      // quitar offset
        .replace('Z', '');          // quitar Z
    }

    // Limitar a 500 líneas
    const all = term.querySelectorAll('.log-line');
    if (all.length > 500) for (let i = 500; i < all.length; i++) all[i].remove();

    applyLogFilters();
  }

  /* ── Actualizar pestaña IPs desde API ── */

  // Carga el endpoint /geo (coordenadas + país reales) y actualiza el mapa
  async function loadGeoData() {
    const geoData = await apiFetch('/geo?hours=24');
    if (!geoData?.length) return;
    IP_DATA = geoData.map(d => ({
      ip:    d.ip,
      hits:  d.hits,
      sev:   d.sev,
      lat:   d.lat  || 0,
      lon:   d.lon  || 0,
      label: d.country || 'Desconocido',
      city:  d.city  || '',
      flag:  d.flag  || '🌐',
      type:  d.country_iso || '—',
    }));
    buildIPTable();
    buildCountryBars();
    updateIPStats();
    // Actualizar solo los marcadores del mapa (sin reconstruir el base)
    if (typeof refreshMapMarkers === 'function') refreshMapMarkers();
    else if (typeof buildD3Map === 'function') buildD3Map();
  }

  function updateIPsFromAPI(topIps, stats) {
    if (!topIps?.length) return;
    // Siempre cargar desde /geo (fuente de verdad con pais, coords, flag)
    // No rellenar IP_DATA con datos basicos primero para evitar sobreescribir
    loadGeoData();
  }

  /* ── Actualizar vista Servicios desde API ── */
  function updateServiciosFromAPI(stats, events) {
    if (!stats) return;
    const byService = stats.by_service || {};
    const byAction  = stats.by_action  || {};
    const byHour    = stats.by_hour    || {};

    // ── 1. Actualizar hits por servicio ──────────────────────────────
    SVC_DEF.forEach(s => { s.hits = byService[s.id] || 0; });

    // ── 2. Actualizar contadores de acciones ─────────────────────────
    ACTIONS.forEach(a => { a.count = byAction[a.name] || 0; });
    // Añadir acciones nuevas de los detectores si vienen de la API
    ['port_scan','credential_stuffing','decoy_file_access','scanner_probe'].forEach(name => {
      if (byAction[name] && !ACTIONS.find(a => a.name === name)) {
        ACTIONS.push({ name, count: byAction[name], color: '#c0392b' });
      } else {
        const a = ACTIONS.find(x => x.name === name);
        if (a) a.count = byAction[name] || 0;
      }
    });

    // ── 3. Rellenar SVC_TIMELINE desde by_hour ───────────────────────
    // by_hour tiene claves ISO "2026-04-23T14:00:00Z" — extraer últimas 12h
    const now = new Date();
    const svcIds = SVC_DEF.map(s => s.id);
    svcIds.forEach(id => { SVC_TIMELINE[id] = Array(12).fill(0); });

    // Agrupar eventos de la última hora por servicio para la timeline
    // (by_hour de la API es total, no por servicio — usamos los eventos)
    if (events?.length) {
      const cutoff12h = new Date(now - 12 * 3600 * 1000);
      events.forEach(ev => {
        const ts = new Date(ev.received_at || ev.timestamp);
        if (isNaN(ts) || ts < cutoff12h) return;
        const svcId = ev.service;
        if (!SVC_TIMELINE[svcId]) return;
        // Calcular slot (0=hace 12h, 11=más reciente)
        const hoursAgo = (now - ts) / 3600000;
        const slot = 11 - Math.min(11, Math.floor(hoursAgo));
        SVC_TIMELINE[svcId][slot]++;
      });
    }

    // ── 4. Actualizar CREDS desde eventos multi-servicio ─────────────
    CREDS.length = 0;
    if (events?.length) {
      const credMap = {};
      events.forEach(ev => {
        const svc = ev.service || '';
        let key = null;
        if (ev.action === 'login_attempt' && ev.username) {
          const user = ev.username;
          const pass = ev.password || '—';
          const tag  = (svc === 'ssh') ? '' : ` [${svc.toUpperCase()}]`;
          key = `${user}|||${pass}|||${tag}`;
        }
        if (key) credMap[key] = (credMap[key] || 0) + 1;
      });
      Object.entries(credMap)
        .sort((a,b) => b[1]-a[1])
        .slice(0, 10)
        .forEach(([key, n]) => {
          const [user, pass, tag] = key.split('|||');
          CREDS.push({ user: user + tag, pass, n });
        });
    }

    // ── 5. Actualizar PATHS desde eventos HTTP ───────────────────────
    PATHS.length = 0;
    if (events?.length) {
      const pathMap = {};
      events.forEach(ev => {
        if ((ev.service === 'http' || ev.service === 'https') && ev.path) {
          pathMap[ev.path] = (pathMap[ev.path] || 0) + 1;
        }
      });
      Object.entries(pathMap)
        .sort((a,b) => b[1]-a[1])
        .slice(0, 8)
        .forEach(([path, n]) => PATHS.push({ path, n }));
    }

    // ── 6. Actualizar TECH con datos del config.yaml si disponibles ──
    // (se mantiene estático por ahora — se podría enriquecer con /db/stats)

    // ── 7. Reconstruir la vista ──────────────────────────────────────
    svcAnimated = false;
    ['svc-status-row','svc-timeline','svc-actions',
     'svc-creds-body','svc-paths','svc-tech-details'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = '';
    });

    buildServiciosView();
    setTimeout(animateServiciosView, 80);
  }

  /* ── Actualizar hits de servicios en resumen ── */
  function updateSvcHits(byService) {
    const svcs = {ssh:'ssh', http:'http', https:'https', ftp:'ftp', smb:'smb', rdp:'rdp'};
    Object.entries(svcs).forEach(([key, id]) => {
      const el = document.getElementById(`svc-hits-${id}`);
      if (el) el.textContent = byService[key] || 0;
    });
  }

  /* ── Actualizar rutas HTTP más accedidas ── */
  function updateHttpPaths(events) {
    const container = document.getElementById('http-paths-list');
    if (!container) return;
    const paths = {};
    events.forEach(ev => {
      if ((ev.service === 'http' || ev.service === 'https') && ev.path) {
        paths[ev.path] = (paths[ev.path] || 0) + 1;
      }
    });
    const sorted = Object.entries(paths).sort((a,b) => b[1]-a[1]).slice(0,6);
    if (!sorted.length) { container.innerHTML = '<div style="color:var(--text-tertiary);font-size:12px;padding:8px 0;">Sin datos aún</div>'; return; }
    const max = sorted[0][1];
    container.innerHTML = sorted.map(([path, n]) => `
      <div class="bar-row">
        <span class="bar-key">${path}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.round(n/max*100)}%;background:var(--blue);"></div></div>
        <span class="bar-val">${n}</span>
      </div>`).join('');
  }

  /* ── Exportación CSV / JSON ── */
  function exportEvents({ fmt = 'csv', hours = 24, service = '', action = '', level = '' } = {}) {
    // Construir URL del endpoint /export con los filtros activos
    const base = window.API_BASE || 'http://192.168.1.112/api';
    const params = new URLSearchParams({ format: fmt, hours, limit: 10000 });
    if (service) params.set('service', service);
    if (action)  params.set('action',  action);
    if (level)   params.set('level',   level);

    const url = `${base}/export?${params.toString()}`;
    const a   = document.createElement('a');
    a.href    = url;
    a.download = `honeypot_events_${new Date().toISOString().slice(0,10)}.${fmt}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // Inyectar botones de exportación en la barra de logs y eventos si existen
  function injectExportButtons() {
    const targets = [
      { barId: 'logs-toolbar',    view: 'logs' },
      { barId: 'eventos-toolbar', view: 'eventos' },
    ];
    targets.forEach(({ barId }) => {
      const bar = document.getElementById(barId);
      if (!bar || bar.querySelector('.export-btn')) return;

      const wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;gap:6px;margin-left:auto;';

      const btnCSV = document.createElement('button');
      btnCSV.className = 'export-btn';
      btnCSV.textContent = '⬇ CSV';
      btnCSV.title = 'Exportar eventos a CSV';
      btnCSV.style.cssText = [
        'padding:4px 10px', 'font-size:11px', 'border-radius:6px',
        'border:1px solid rgba(0,0,0,0.15)', 'background:#fff',
        'cursor:pointer', 'color:#1a5fa8', 'font-weight:600',
      ].join(';');
      btnCSV.addEventListener('click', () => exportEvents({ fmt: 'csv' }));

      const btnJSON = document.createElement('button');
      btnJSON.className = 'export-btn';
      btnJSON.textContent = '⬇ JSON';
      btnJSON.title = 'Exportar eventos a JSON';
      btnJSON.style.cssText = btnCSV.style.cssText.replace('#1a5fa8', '#1a7a4a');
      btnJSON.addEventListener('click', () => exportEvents({ fmt: 'json' }));

      wrap.appendChild(btnCSV);
      wrap.appendChild(btnJSON);
      bar.appendChild(wrap);
    });
  }

  /* ── Actualizar credenciales más probadas ── */
  // Captura credenciales de SSH, HTTP, FTP y SMB
  function updateCredsList(events) {
    const container = document.getElementById('creds-list');
    if (!container) return;
    const creds = {};
    events.forEach(ev => {
      const svc = ev.service || '';
      // SSH: campos username + password directos
      if (svc === 'ssh' && ev.username && ev.password) {
        const key = `${ev.username} / ${ev.password}`;
        creds[key] = (creds[key] || 0) + 1;
        return;
      }
      // HTTP: login_attempt en /admin, /login, /wp-admin, /phpmyadmin
      if ((svc === 'http' || svc === 'https') &&
          ev.action === 'login_attempt' && ev.username) {
        const pwd = ev.password ? ` / ${ev.password}` : '';
        const key = `${ev.username}${pwd} [${svc.toUpperCase()}]`;
        creds[key] = (creds[key] || 0) + 1;
        return;
      }
      // FTP: on_login_failed incluye username + password
      if (svc === 'ftp' && ev.action === 'login_attempt' && ev.username) {
        const pwd = ev.password ? ` / ${ev.password}` : '';
        const key = `${ev.username}${pwd} [FTP]`;
        creds[key] = (creds[key] || 0) + 1;
        return;
      }
      // SMB: NTLM negotiate — solo username disponible
      if (svc === 'smb' && ev.action === 'login_attempt') {
        const key = `ntlm_negotiate [SMB]`;
        creds[key] = (creds[key] || 0) + 1;
      }
    });
    const sorted = Object.entries(creds).sort((a,b) => b[1]-a[1]).slice(0,8);
    if (!sorted.length) { container.innerHTML = '<div style="color:var(--text-tertiary);font-size:12px;padding:8px 0;">Sin datos aún</div>'; return; }
    const max = sorted[0][1];
    container.innerHTML = sorted.map(([cred, n]) => `
      <div class="bar-row">
        <span class="bar-key" style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${cred}">${cred}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.round(n/max*100)}%;background:var(--red);"></div></div>
        <span class="bar-val">${n}</span>
      </div>`).join('');
  }

  /* ── Actualizar stats panel Logs con IDs ── */
  function updateLogsStats(stats) {
    const byLevel   = stats.by_level   || {};
    const byService = stats.by_service || {};
    const total     = stats.total      || 0;

    // Tarjetas stats
    const elTotal   = document.getElementById('logs-stat-total');
    const elError   = document.getElementById('logs-stat-error');
    const elWarning = document.getElementById('logs-stat-warning');
    const elLast    = document.getElementById('logs-stat-last');
    if (elTotal)   elTotal.textContent   = total;
    if (elError)   elError.textContent   = byLevel.ERROR   || 0;
    if (elWarning) elWarning.textContent = byLevel.WARNING || 0;
    if (elLast && stats.last_event) elLast.textContent = fmtTs(stats.last_event);

    // Barras por nivel con IDs
    const levelMap = {INFO:'dist-info', WARNING:'dist-warning', ERROR:'dist-error', DEBUG:'dist-debug'};
    const maxL = Math.max(...Object.values(byLevel), 1);
    Object.entries(levelMap).forEach(([lvl, id]) => {
      const countEl = document.getElementById(id);
      if (countEl) countEl.textContent = byLevel[lvl] || 0;
    });
    // Actualizar barras por nivel
    const fills = document.querySelectorAll('.logs-bar-anim');
    const levels = ['INFO','WARNING','ERROR','DEBUG'];
    levels.forEach((l, i) => {
      if (fills[i]) {
        const pct = Math.round(((byLevel[l] || 0) / maxL) * 100);
        fills[i].style.width = pct + '%';
        fills[i].dataset.w   = pct;
      }
    });

    // Barras por servicio con IDs
    const svcMap = {ssh:'dist-ssh', http:'dist-http', ftp:'dist-ftp', smb:'dist-smb', rdp:'dist-rdp'};
    const maxS = Math.max(...Object.values(byService), 1);
    const svcFills = document.querySelectorAll('.logs-bar-anim');
    const svcs = ['ssh','http','ftp','smb','rdp'];
    svcs.forEach((s, i) => {
      const countEl = document.getElementById(svcMap[s]);
      if (countEl) countEl.textContent = byService[s] || 0;
      const fillEl = svcFills[levels.length + i];
      if (fillEl) {
        const pct = Math.round(((byService[s] || 0) / maxS) * 100);
        fillEl.style.width = pct + '%';
      }
    });
  }

  /* ── Actualizar alerta banner ── */
  function updateAlertBanner(stats) {
    const banner = document.getElementById('alert-banner');
    if (!banner) return;
    if ((stats.brute_force || 0) === 0) {
      banner.style.display = 'none';
      return;
    }
    banner.style.display = '';
    const text = document.getElementById('alert-text');
    const time = document.getElementById('alert-time');
    if (text) text.innerHTML = `Brute force detectado · <strong>${stats.brute_force}</strong> alertas en las últimas 24h`;
    if (time && stats.last_event) {
      const diff = Math.round((Date.now() - new Date(stats.last_event)) / 60000);
      time.textContent = diff < 1 ? 'hace <1 min' : `hace ${diff} min`;
    }
  }

  /* ── Refresh completo desde API ── */
  async function apiRefreshAll() {
    const stats = await apiFetch('/stats?hours=24');
    if (!stats) return;

    apiAvailable = true;

    // Resumen
    updateMetricCards(stats);
    updateTrafficFromStats(stats);
    updateSvcChartFromStats(stats);
    updateTopIPsTable(stats.top_ips);
    updateAlertBanner(stats);
    updateSvcHits(stats.by_service || {});
    await loadGeoData();  // carga IPs con geo, país, coords y flag

    // Últimos eventos para feed de actividad
    const recent = await apiFetch('/events?limit=200');
    if (recent?.length) {
      updateActivityFeed(recent);
      updateHttpPaths(recent);
      updateCredsList(recent);

      // Actualizar última actualización
      const lr = document.getElementById('last-refresh');
      if (lr) lr.textContent = new Date().toLocaleTimeString('es-ES');

      // Actualizar tabla eventos si está activa
      const activeTab = document.querySelector('.nav-tab.active')?.dataset?.view;
      if (activeTab === 'eventos') updateEventsFromAPI(recent);
      if (activeTab === 'servicios') updateServiciosFromAPI(stats, recent);

      // Actualizar logs si está activa (incremental)
      if (activeTab === 'logs') {
        const sinceParam = lastSince ? `&since=${encodeURIComponent(lastSince)}` : '';
        const newLogs = await apiFetch(`/events?limit=20${sinceParam}`);
        if (newLogs?.length) updateLogsFromAPI(newLogs);
        updateLogsStats(stats);
      }
    }
  }

  /* ── Poll incremental de logs (cada 3s cuando la pestaña está activa) ── */
  async function pollLogs() {
    if (!apiAvailable || !logLiveMode) return;
    const activeTab = document.querySelector('.nav-tab.active')?.dataset?.view;
    if (activeTab !== 'logs') return;
    const sinceParam = lastSince ? `?since=${encodeURIComponent(lastSince)}&limit=20` : '?limit=20';
    const newLogs = await apiFetch(`/events${sinceParam}`);
    if (newLogs?.length) updateLogsFromAPI(newLogs);
  }

  /* ── Inicialización ── */
  async function initAPI() {
    const ok = await checkApiHealth();
    if (!ok) {
      console.warn('[dashboard] API no disponible — usando datos estáticos');
      return;
    }
    console.info('[dashboard] API conectada en', API_BASE);

    // Carga inicial
    await apiRefreshAll();

    // Inyectar botones de exportación
    setTimeout(injectExportButtons, 200);

    // Auto-refresh cada 30s
    refreshTimer = setInterval(apiRefreshAll, REFRESH_MS);

    // Poll logs cada 3s
    setInterval(pollLogs, 3000);

    // Refresh al cambiar de pestaña
    document.querySelector('.nav-tabs').addEventListener('click', async e => {
      const btn = e.target.closest('[data-view]');
      if (!btn) return;
      const view = btn.dataset.view;
      if (view === 'eventos') {
        const ev = await apiFetch('/events?limit=200');
        if (ev) updateEventsFromAPI(ev);
      }
      if (view === 'ips') {
        buildD3Map();
        await loadGeoData();
      }
      if (view === 'servicios') {
        const st = await apiFetch('/stats?hours=24');
        const ev = await apiFetch('/events?limit=200');
        if (st) updateServiciosFromAPI(st, ev || []);
      }
      injectExportButtons();
      if (view === 'logs') {
        lastSince = null;  // reset cursor para cargar últimos 50
        // Cargar stats y eventos en paralelo para que los contadores aparezcan rápido
        const [stats, ev] = await Promise.all([
          apiFetch('/stats?hours=24'),
          apiFetch('/events?limit=50'),
        ]);
        if (stats) updateLogsStats(stats);
        if (ev)    updateLogsFromAPI(ev);
      }
    });
  }

  // Arrancar tras cargar el DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAPI);
  } else {
    initAPI();
  }
