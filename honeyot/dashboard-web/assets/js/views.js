/* ─────────────────────────────────────────────────────────────────
   views.js — Honeypot Dashboard · SOC honeycos
   Lógica de todas las pestañas: nav, eventos, servicios, logs, IPs.
   Depende de: charts.js (trafficData, svcData, drawSvcChart)
───────────────────────────────────────────────────────────────── */

  /* ── Nav tabs view switching ── */
  document.querySelectorAll('.nav-tab[data-view]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.dataset.view;
      document.getElementById('view-resumen').style.display  = view === 'resumen'  ? 'block' : 'none';
      document.getElementById('view-eventos').style.display  = view === 'eventos'  ? 'block' : 'none';
      document.getElementById('view-ips').style.display      = view === 'ips'       ? 'block' : 'none';
      document.getElementById('view-servicios').style.display = view === 'servicios' ? 'block' : 'none';
      document.getElementById('view-logs').style.display      = view === 'logs'       ? 'block' : 'none';
    });
  });

  /* ── Events panel data ── */
  let EV_EVENTS = [];

  const EV_SEV_ORDER = {CRÍTICO:0,ALTO:1,MEDIO:2,BAJO:3};
  const EV_PAGE_SIZE = 10;
  let evSvc = 'all', evSev = 'all', evSearch = '', evSortCol = 'ts', evSortDir = -1, evPage = 0, evExpanded = null;

  function evFiltered() {
    return EV_EVENTS.filter(e => {
      if (evSvc !== 'all' && e.svc !== evSvc) return false;
      if (evSev !== 'all' && e.sev !== evSev) return false;
      if (evSearch) {
        const q = evSearch.toLowerCase();
        if (![e.src,e.msg,e.sub,e.svc,e.action].join(' ').toLowerCase().includes(q)) return false;
      }
      return true;
    }).sort((a,b) => {
      let va, vb;
      if (evSortCol==='sev')    { va=EV_SEV_ORDER[a.sev]; vb=EV_SEV_ORDER[b.sev]; }
      else if (evSortCol==='ts') { va=a.ts; vb=b.ts; }
      else if (evSortCol==='svc') { va=a.svc; vb=b.svc; }
      else if (evSortCol==='action') { va=a.action; vb=b.action; }
      else if (evSortCol==='src') { va=a.src; vb=b.src; }
      else { return 0; }
      return va < vb ? evSortDir : va > vb ? -evSortDir : 0;
    });
  }

  function evSevBadge(s) {
    const cls = s==='CRÍTICO'?'ev-sev-critico':s==='ALTO'?'ev-sev-alto':s==='MEDIO'?'ev-sev-medio':'ev-sev-bajo';
    return `<span class="ev-sev ${cls}"><span class="dot"></span>${s}</span>`;
  }

  function evRender() {
    const rows = evFiltered();
    const total = rows.length;
    const maxPage = Math.max(0, Math.ceil(total / EV_PAGE_SIZE) - 1);
    if (evPage > maxPage) evPage = maxPage;
    const slice = rows.slice(evPage * EV_PAGE_SIZE, (evPage + 1) * EV_PAGE_SIZE);

    const badge = document.getElementById('ev-count-badge');
    if (badge) badge.textContent = `${total} evento${total!==1?'s':''}`;
    const fi = document.getElementById('ev-footer-info');
    if (fi) fi.textContent = `Mostrando ${total===0?0:evPage*EV_PAGE_SIZE+1}–${Math.min((evPage+1)*EV_PAGE_SIZE,total)} de ${total} eventos`;

    const tbody = document.getElementById('ev-tbody');
    const empty = document.getElementById('ev-empty');
    if (!tbody) return;

    if (slice.length === 0) {
      tbody.innerHTML = '';
      if (empty) empty.style.display = 'block';
    } else {
      if (empty) empty.style.display = 'none';
      tbody.innerHTML = slice.map((e, i) => {
        const idx = evPage * EV_PAGE_SIZE + i;
        return `<tr data-ev-idx="${idx}">
          <td class="ev-col-sev">${evSevBadge(e.sev)}</td>
          <td class="ev-col-ts"><span class="ev-ts">${e.ts}</span></td>
          <td class="ev-col-svc"><span class="ev-svc-tag">${e.svc}</span></td>
          <td class="ev-col-action"><span class="ev-act-tag">${e.action}</span></td>
          <td class="ev-col-src"><span class="ev-ip">${e.src}</span></td>
          <td class="ev-col-msg">
            <div class="ev-msg-main">${e.msg}</div>
            <div class="ev-msg-sub">${e.sub}</div>
          </td>
          <td class="ev-col-det"><button class="ev-det-btn" data-ev-idx="${idx}">ver +</button></td>
        </tr>`;
      }).join('');
    }

    const totalPages = Math.ceil(total / EV_PAGE_SIZE) || 1;
    let btns = '';
    if (evPage > 0) btns += `<button class="ev-page-btn" data-page="${evPage-1}">‹</button>`;
    for (let p=0; p<totalPages; p++) {
      if (p===0 || p===totalPages-1 || Math.abs(p-evPage)<=1)
        btns += `<button class="ev-page-btn${p===evPage?' active':''}" data-page="${p}">${p+1}</button>`;
      else if (Math.abs(p-evPage)===2)
        btns += `<span style="font-size:11px;color:#8a9ab0;padding:0 2px">…</span>`;
    }
    if (evPage < totalPages-1) btns += `<button class="ev-page-btn" data-page="${evPage+1}">›</button>`;
    const pag = document.getElementById('ev-pagination');
    if (pag) pag.innerHTML = btns;
  }

  document.getElementById('ev-svc-filters').addEventListener('click', e => {
    const chip = e.target.closest('[data-svc]');
    if (!chip) return;
    document.querySelectorAll('[data-svc]').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    evSvc = chip.dataset.svc;
    evPage = 0; evRender();
  });

  document.getElementById('ev-sev-filters').addEventListener('click', e => {
    const chip = e.target.closest('[data-sev]');
    if (!chip) return;
    document.querySelectorAll('[data-sev]').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    evSev = chip.dataset.sev;
    evPage = 0; evRender();
  });

  document.getElementById('ev-search').addEventListener('input', e => {
    evSearch = e.target.value;
    evPage = 0; evRender();
  });

  document.querySelector('.ev-table thead').addEventListener('click', e => {
    const th = e.target.closest('th[data-col]');
    if (!th) return;
    const col = th.dataset.col;
    if (evSortCol === col) evSortDir *= -1;
    else { evSortCol = col; evSortDir = -1; }
    document.querySelectorAll('.ev-table thead th').forEach(h => {
      h.classList.remove('sorted');
      h.querySelector('.sort').textContent = '↕';
    });
    th.classList.add('sorted');
    th.querySelector('.sort').textContent = evSortDir === -1 ? '↓' : '↑';
    evRender();
  });

  document.getElementById('ev-pagination').addEventListener('click', e => {
    const btn = e.target.closest('[data-page]');
    if (!btn) return;
    evPage = parseInt(btn.dataset.page);
    evRender();
  });

  document.getElementById('ev-tbody').addEventListener('click', e => {
    const btn = e.target.closest('.ev-det-btn');
    if (!btn) return;
    const idx = parseInt(btn.dataset.evIdx);
    const rows = evFiltered();
    const ev = rows[idx];
    if (!ev) return;
    document.querySelectorAll('.ev-detail-row').forEach(r => r.remove());
    const tr = btn.closest('tr');
    if (evExpanded === idx) { evExpanded = null; btn.textContent = 'ver +'; return; }
    const SKIP = new Set(['received_at','host','hostname','environment','vlan','host']);
    const detailHTML = Object.entries(ev.extra)
      .filter(([k]) => !SKIP.has(k) && typeof ev.extra[k] !== 'object')
      .map(([k,v]) =>
        `<div class="ev-detail-item"><span class="ev-detail-key">${k}</span><span class="ev-detail-val">${v}</span></div>`
      ).join('');
    const detailTr = document.createElement('tr');
    detailTr.className = 'ev-detail-row';
    detailTr.innerHTML = `<td colspan="7"><div class="ev-detail-grid">${detailHTML}</div></td>`;
    tr.after(detailTr);
    evExpanded = idx;
    btn.textContent = 'ver −';
  });

  evRender();



  /* ── Servicios view ── */

  const SVC_DEF = [
    { id:'ssh',   name:'SSH',   port:22,   lib:'paramiko 4.0.0',  hits:0, up:true,  color:'#1a5fa8', banner:'SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6' },
    { id:'http',  name:'HTTP',  port:80,   lib:'aiohttp 3.13.5',  hits:0, up:true,  color:'#0e7a4e', banner:'Apache/2.4.57 (Ubuntu)' },
    { id:'https', name:'HTTPS', port:443,  lib:'aiohttp + ssl',   hits:0, up:true,  color:'#0e7a4e', banner:'Apache/2.4.57 (Ubuntu) OpenSSL/3.0.2' },
    { id:'ftp',   name:'FTP',   port:21,   lib:'pyftpdlib 2.2.0', hits:0, up:true,  color:'#b06a00', banner:'ProFTPD 1.3.8 Server (Debian)' },
    { id:'smb',   name:'SMB',   port:445,  lib:'impacket 0.13.0', hits:0, up:true,  color:'#8a9ab0', banner:'Windows Server 2019 (decoy)' },
    { id:'rdp',   name:'RDP',   port:3389, lib:'asyncio',         hits:0, up:true,  color:'#8a9ab0', banner:'Microsoft Terminal Services' },
  ];

  const SVC_TIMELINE = {
    ssh:   [0,0,0,0,0,0,0,0,0,0,0,0],
    http:  [0,0,0,0,0,0,0,0,0,0,0,0],
    https: [0,0,0,0,0,0,0,0,0,0,0,0],
    ftp:   [0,0,0,0,0,0,0,0,0,0,0,0],
    smb:   [0,0,0,0,0,0,0,0,0,0,0,0],
    rdp:   [0,0,0,0,0,0,0,0,0,0,0,0],
  };

  const ACTIONS = [
    { name:'connection',    count:0, color:'#1a5fa8' },
    { name:'login_attempt', count:0, color:'#b06a00' },
    { name:'request',       count:0, color:'#0e7a4e' },
    { name:'command',       count:0, color:'#8a9ab0' },
    { name:'brute_force',   count:0, color:'#c0392b' },
    { name:'file_access',   count:0, color:'#8a9ab0' },
  ];

  const CREDS = [];
  const PATHS = [];

  const TECH = [
    {svc:'SSH',   key:'Host key',    val:'RSA 2048 (persistida)'},
    {svc:'SSH',   key:'Shell falsa', val:'activa'},
    {svc:'HTTP',  key:'Certificado', val:'autofirmado · válido 365d'},
    {svc:'FTP',   key:'Filesystem',  val:'virtual · ficheros señuelo'},
    {svc:'SMB',   key:'Shares',      val:'ADMIN$, C$, Backups, Finance'},
    {svc:'RDP',   key:'NTLM',        val:'negotiate capturado'},
    {svc:'ALL',   key:'Whitelist BF',val:'192.168.3.200, 10.1.1.34'},
  ];

  let svcAnimated = false;

  function buildServiciosView() {
    /* Status cards */
    const row = document.getElementById('svc-status-row');
    if (row && !row.children.length) {
      row.innerHTML = SVC_DEF.map(s => `
        <div class="svc-status-card ${s.up?'up':'down'}">
          <div class="svc-card-top">
            <span class="svc-card-name">${s.name}</span>
            <div class="svc-card-dot ${s.up?'up':'down'}"></div>
          </div>
          <div class="svc-card-hits svc-count-anim" data-target="${s.hits}">${s.hits}</div>
          <div class="svc-card-label">conexiones hoy</div>
          <span class="svc-card-port">:${s.port}</span>
        </div>`).join('');
    }

    /* Timeline */
    const tl = document.getElementById('svc-timeline');
    if (tl && !tl.children.length) {
      const hours = ['08h','09h','10h','11h','12h','13h','14h','15h','16h','17h','18h','19h'];
      tl.innerHTML = SVC_DEF.map(s => {
        const data = SVC_TIMELINE[s.id];
        const max  = Math.max(...Object.values(SVC_TIMELINE).flat());
        const bars = data.map((v,i) =>
          `<div class="timeline-bar svc-bar-anim" data-h="${Math.round((v/max)*100)}"
            style="height:2px;background:${s.color};opacity:${0.5+v/max*0.5}"></div>`
        ).join('');
        const total = data.reduce((a,b)=>a+b,0);
        return `<div class="timeline-row">
          <span class="timeline-label">${s.name}</span>
          <div class="timeline-bars">${bars}</div>
          <span class="timeline-total">${total}</span>
        </div>`;
      }).join('');

      const badge = document.getElementById('svc-total-badge');
      const total = SVC_DEF.reduce((a,s)=>a+s.hits,0);
      if (badge) badge.textContent = total + ' hits';
    }

    /* Actions */
    const actEl = document.getElementById('svc-actions');
    if (actEl && !actEl.children.length) {
      const maxA = Math.max(...ACTIONS.map(a=>a.count));
      actEl.innerHTML = ACTIONS.map(a => {
        const pct = Math.round((a.count/maxA)*100);
        return `<div class="action-row">
          <div class="action-dot" style="background:${a.color}"></div>
          <span class="action-name">${a.name}</span>
          <div class="action-track"><div class="action-fill svc-action-anim"
            data-w="${pct}" style="width:0%;background:${a.color}"></div></div>
          <span class="action-count">${a.count}</span>
        </div>`;
      }).join('');
    }

    /* Credentials */
    const cb = document.getElementById('svc-creds-body');
    if (cb && !cb.children.length) {
      cb.innerHTML = CREDS.map((c,i) => `<tr>
        <td class="cred-rank">${String(i+1).padStart(2,'0')}</td>
        <td><span class="cred-mono">${c.user}</span></td>
        <td><span class="cred-mono">${c.pass}</span></td>
        <td style="font-weight:600;font-family:'SF Mono',Consolas,monospace;font-size:12px">${c.n}</td>
      </tr>`).join('');
    }

    /* Paths */
    const pp = document.getElementById('svc-paths');
    if (pp && !pp.children.length) {
      const maxP = PATHS[0].n;
      pp.innerHTML = PATHS.map(p => {
        const pct = Math.round((p.n/maxP)*100);
        return `<div class="path-row">
          <span class="path-mono">${p.path}</span>
          <div class="path-bar-wrap"><div class="path-bar-fill svc-path-anim"
            data-w="${pct}" style="width:0%"></div></div>
          <span class="path-count">${p.n}</span>
        </div>`;
      }).join('');
    }

    /* Tech details */
    const td = document.getElementById('svc-tech-details');
    if (td && !td.children.length) {
      td.innerHTML = TECH.map(t => `
        <div class="svc-info-row">
          <span class="svc-info-key"><strong style="color:#4a5568;font-size:10px;text-transform:uppercase;letter-spacing:.05em">${t.svc}</strong> · ${t.key}</span>
          <span class="svc-info-val">${t.val}</span>
        </div>`).join('');
    }
  }

  function animateServiciosView() {
    if (svcAnimated || typeof anime === 'undefined') return;
    svcAnimated = true;

    /* Status card count-up */
    document.querySelectorAll('.svc-count-anim').forEach(el => {
      const target = parseInt(el.dataset.target);
      anime({ targets:{v:0}, v:target, duration:900, easing:'easeOutQuad',
        update: a => { el.textContent = Math.round(a.animations[0].currentValue); } });
    });

    /* Status cards slide in */
    anime({ targets:'.svc-status-card', opacity:[0,1], translateY:[-12,0],
      duration:400, delay:anime.stagger(60), easing:'easeOutQuad' });

    /* Timeline bars grow up */
    document.querySelectorAll('.svc-bar-anim').forEach((el, i) => {
      const h = parseInt(el.dataset.h);
      anime({ targets:el, height:[2, Math.max(4, Math.round(h*0.3))],
        duration:600, delay:150 + Math.floor(i/12)*80 + (i%12)*25,
        easing:'easeOutCubic' });
    });

    /* Action bars grow */
    anime({ targets:'.svc-action-anim',
      width: el => el.dataset.w + '%',
      duration:700, delay:anime.stagger(60, {start:300}), easing:'easeOutCubic' });

    /* Path bars */
    anime({ targets:'.svc-path-anim',
      width: el => el.dataset.w + '%',
      duration:700, delay:anime.stagger(55, {start:400}), easing:'easeOutCubic' });

    /* Cred rows */
    anime({ targets:'#svc-creds-body tr', opacity:[0,1], translateX:[-8,0],
      duration:350, delay:anime.stagger(45, {start:250}), easing:'easeOutQuad' });

    /* Tech details rows */
    anime({ targets:'.svc-info-row', opacity:[0,1],
      duration:300, delay:anime.stagger(40, {start:350}), easing:'easeOutQuad' });
  }

  /* Nav tab trigger */
  document.querySelector('.nav-tabs').addEventListener('click', e => {
    const btn = e.target.closest('[data-view]');
    if (btn && btn.dataset.view === 'servicios') {
      buildServiciosView();
      setTimeout(animateServiciosView, 80);
    }
  });



  /* ── Logs view ── */

  let LOG_ENTRIES = [];

  function hlLine(entry) {
    let msg = entry.msg
      .replace(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/g, '<span class="hl-ip">$1</span>')
      .replace(/(\/[^\s·]+)/g, '<span class="hl-path">$1</span>')
      .replace(/(user=[^\s·]+)/g, '<span class="hl-cred">$1</span>')
      .replace(/(result=success)/g, '<span style="color:#1fc97a">$1</span>')
      .replace(/(result=failed|brute_force detected)/g, '<span style="color:#f04a4a">$1</span>');
    return msg;
  }

  function renderLogLine(entry, flash) {
    const div = document.createElement('div');
    div.className = 'log-line' + (flash ? ' log-new' : '');
    div.dataset.lvl = entry.lvl;
    div.dataset.svc = entry.svc;
    div.dataset.raw = (entry.ts + ' ' + entry.lvl + ' ' + entry.svc + ' ' + entry.msg).toLowerCase();
    div.innerHTML = `<span class="log-ts">${entry.ts}</span><span class="log-lvl ${entry.lvl}">${entry.lvl.padEnd(7)}</span><span class="log-svc">${entry.svc.padEnd(6)}</span><span class="log-msg">${hlLine(entry)}</span>`;
    return div;
  }

  let logLvlFilter  = 'ALL';
  let logSvcFilter  = 'all';
  let logSearchTerm = '';
  let logLiveMode   = true;
  let logInterval   = null;
  let logBuilt      = false;

  function applyLogFilters() {
    const term = logSearchTerm.toLowerCase();
    let visible = 0;
    document.querySelectorAll('#log-terminal .log-line').forEach(el => {
      const lvlOk  = logLvlFilter === 'ALL' || el.dataset.lvl === logLvlFilter;
      const svcOk  = logSvcFilter === 'all' || el.dataset.svc === logSvcFilter;
      const termOk = !term || el.dataset.raw.includes(term);
      const show   = lvlOk && svcOk && termOk;
      el.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    const el = document.getElementById('log-count-el');
    if (el) el.textContent = visible + ' líneas';
  }

  function buildLogsView() {
    if (logBuilt) return;
    logBuilt = true;
    const term = document.getElementById('log-terminal');
    if (!term) return;
    LOG_ENTRIES.slice().reverse().forEach(e => {
      term.appendChild(renderLogLine(e, false));
    });
    term.scrollTop = term.scrollHeight;
    applyLogFilters();
  }

  function animateLogsView() {
    if (typeof anime === 'undefined') return;

    // Count up stats
    document.querySelectorAll('.log-count-up').forEach(el => {
      const t = parseInt(el.dataset.target);
      anime({ targets:{v:0}, v:t, duration:900, easing:'easeOutQuad',
        update: a => { el.textContent = Math.round(a.animations[0].currentValue); } });
    });

    // Distribution bars
    const fills = document.querySelectorAll('.logs-bar-anim');
    fills.forEach(el => { el._w = el.dataset.w + '%'; el.style.width = '0%'; });
    anime({ targets: fills, width: el => el._w,
      duration:800, delay:anime.stagger(60, {start:200}), easing:'easeOutCubic' });

    // Rotation bar
    setTimeout(() => {
      const fill = document.getElementById('log-rot-fill');
      const pct  = document.getElementById('log-rot-pct');
      if (fill) anime({ targets:fill, width:'0.29%', duration:1000, easing:'easeOutCubic',
        update: () => { if (pct) pct.textContent = '0.29%'; } });
    }, 400);
  }

  /* ── Live mode: gestionado por api.js via polling real ── */
  const LIVE_POOL = [];
  let liveIdx = 0;

  function nowTs() {
    const d = new Date();
    return [d.getHours(),d.getMinutes(),d.getSeconds()].map(n=>String(n).padStart(2,'0')).join(':')
      + '.' + String(d.getMilliseconds()).padStart(3,'0');
  }

  function startLive() {
    if (!LIVE_POOL.length) return;
    if (logInterval) return;
    logInterval = setInterval(() => {
      if (!logLiveMode) return;
      const term = document.getElementById('log-terminal');
      if (!term) return;
      const e = {...LIVE_POOL[liveIdx % LIVE_POOL.length], ts: nowTs()};
      liveIdx++;
      const line = renderLogLine(e, true);
      term.insertBefore(line, term.firstChild);
      applyLogFilters();
    }, 3200);
  }

  /* ── Toolbar interactions ── */
  function initLogToolbar() {
    document.querySelectorAll('[data-lvl]').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('[data-lvl]').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        logLvlFilter = chip.dataset.lvl;
        applyLogFilters();
      });
    });
    document.querySelectorAll('[data-svc2]').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('[data-svc2]').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        logSvcFilter = chip.dataset.svc2;
        applyLogFilters();
      });
    });
    const searchEl = document.getElementById('log-search-input');
    if (searchEl) searchEl.addEventListener('input', e => {
      logSearchTerm = e.target.value;
      applyLogFilters();
    });
    const liveBtn = document.getElementById('log-live-btn');
    const liveBadge = document.getElementById('log-live-badge');
    if (liveBtn) liveBtn.addEventListener('click', () => {
      logLiveMode = !logLiveMode;
      liveBtn.classList.toggle('on', logLiveMode);
      if (liveBadge) liveBadge.style.display = logLiveMode ? '' : 'none';
    });
  }

  /* Nav tab trigger */
  document.querySelector('.nav-tabs').addEventListener('click', e => {
    const btn = e.target.closest('[data-view]');
    if (btn && btn.dataset.view === 'logs') {
      buildLogsView();
      setTimeout(animateLogsView, 80);
      startLive();
      initLogToolbar();
    }
  });


  /* ── IPs view ── */

  let IP_DATA = [];

  const SEV_COLOR = {critico:'#c0392b', alto:'#b06a00', medio:'#1a5fa8', bajo:'#1a5fa8'};

  /* ── Helper: bandera como imagen (flagcdn.com) ── */
  function flagImg(country_iso, size='16x12') {
    if (!country_iso || country_iso === '—' || country_iso === '') return '<span style="font-size:13px">🌐</span>';
    const code = country_iso.toLowerCase();
    return `<img src="https://flagcdn.com/${size}/${code}.png" alt="${country_iso}"
      style="width:${size.split('x')[0]}px;height:${size.split('x')[1]}px;border-radius:2px;vertical-align:middle;margin-right:4px"
      onerror="this.style.display='none'">`;
  }

  /* ── Renderizar tabla top IPs ── */
  function buildIPTable() {
    const ipTbody = document.getElementById('ip-tbl-body');
    if (!ipTbody) return;
    if (!IP_DATA.length) {
      ipTbody.innerHTML = '<tr><td colspan="4" style="color:#8a9ab0;font-size:12px;padding:16px 0;text-align:center">Sin datos aún</td></tr>';
      return;
    }
    const MAX_HITS = Math.max(...IP_DATA.map(d => d.hits));
    ipTbody.innerHTML = IP_DATA.slice(0,8).map(d => {
      const pct = Math.round((d.hits / MAX_HITS) * 100);
      const bc  = d.sev==='critico'?'itb-red':d.sev==='alto'?'itb-amber':d.sev==='medio'?'itb-blue':'itb-gray';
      return `<tr>
        <td><span class="ip-addr-mono">${d.ip}</span></td>
        <td style="font-size:13px">${flagImg(d.type)} <span style="font-size:11px;color:#4a5568">${d.label || '—'}</span></td>
        <td>
          <div class="ip-hits-bar">
            <div class="ip-hits-track"><div class="ip-hits-fill" style="width:${pct}%;background:${SEV_COLOR[d.sev] || '#1a5fa8'}"></div></div>
            <span class="ip-hits-num">${d.hits}</span>
          </div>
        </td>
        <td><span class="ip-type-badge ${bc}">${d.type || '—'}</span></td>
      </tr>`;
    }).join('');
  }

  /* ── Renderizar barras por país ── */
  function buildCountryBars() {
    const cbars = document.getElementById('ip-country-bars');
    if (!cbars) return;
    if (!IP_DATA.length) {
      cbars.innerHTML = '<div style="color:#8a9ab0;font-size:12px;padding:8px 0">Sin datos aún</div>';
      return;
    }
    const byCountry = {};
    IP_DATA.forEach(d => {
      const key = d.label || 'Desconocido';
      if (!byCountry[key]) byCountry[key] = { flag: d.flag || '🌐', hits: 0 };
      byCountry[key].hits += d.hits;
    });
    const countries = Object.entries(byCountry).sort((a,b) => b[1].hits - a[1].hits).slice(0,7);
    const maxC = countries[0]?.[1]?.hits || 1;
    cbars.innerHTML = countries.map(([name, data]) => {
      const pct = Math.round((data.hits / maxC) * 100);
      return `<div class="ip-country-bar-row">
        <span class="ip-country-flag">${flagImg(name !== 'Desconocido' ? IP_DATA.find(d=>d.label===name)?.type || '' : '')}</span>
        <span class="ip-country-name">${name}</span>
        <div class="ip-country-track"><div class="ip-country-fill" style="width:${pct}%"></div></div>
        <span class="ip-country-count">${data.hits}</span>
      </div>`;
    }).join('');
  }

  /* ── Actualizar stats de la pestaña IPs ── */
  function updateIPStats() {
    const elUnique    = document.getElementById('ip-stat-unique');
    const elCountries = document.getElementById('ip-stat-countries');
    const elCritical  = document.getElementById('ip-stat-critical');
    const elBf        = document.getElementById('ip-stat-bruteforce');
    if (elUnique)    elUnique.textContent    = IP_DATA.length;
    const paises = new Set(IP_DATA.map(d => d.label || 'Desconocido'));
    if (elCountries) elCountries.textContent = paises.size;
    const criticas = IP_DATA.filter(d => d.sev === 'critico' || d.sev === 'alto').length;
    if (elCritical)  elCritical.textContent  = criticas;
    const bf = IP_DATA.filter(d => d.sev === 'critico').length;
    if (elBf)        elBf.textContent        = bf;
  }

  // Render inicial vacío
  buildIPTable();
  buildCountryBars();

  /* ── D3 + TopoJSON world map ── */
  let mapBuilt = false;

  function buildD3Map() {
    if (mapBuilt) return;
    const container = document.getElementById('ip-map-container');
    if (!container || typeof d3 === 'undefined' || typeof topojson === 'undefined') return;

    const W = container.getBoundingClientRect().width || container.offsetWidth;
    if (W < 100) {
      requestAnimationFrame(() => { mapBuilt = false; buildD3Map(); });
      return;
    }

    mapBuilt = true;
    d3.select('#ip-map-container').selectAll('svg').remove();

    const H = Math.round(W * 0.48);
    container.style.height = H + 'px';

    const svg = d3.select('#ip-map-container')
      .append('svg')
      .attr('width', '100%')
      .attr('height', H)
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('display', 'block');

    // Ocean background
    svg.append('rect')
      .attr('width', W).attr('height', H)
      .attr('fill', '#dce8f5');

    const projection = d3.geoNaturalEarth1()
      .scale(W / 6.0)
      .translate([W / 2, H / 2]);

    const path = d3.geoPath().projection(projection);

    // Graticule
    const graticule = d3.geoGraticule()();
    svg.append('path')
      .datum(graticule)
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', '#c8d8ec')
      .attr('stroke-width', 0.3);

    // Países atacantes dinámicos desde IP_DATA (geolocalización real)
    const attackedISO = new Set(IP_DATA.map(d => d.type).filter(Boolean));

    // Load world TopoJSON
    fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
      .then(r => r.json())
      .then(world => {
        const countries = topojson.feature(world, world.objects.countries);

        // Country fills
        svg.append('g')
          .selectAll('path')
          .data(countries.features)
          .enter()
          .append('path')
          .attr('d', path)
          .attr('fill', d => {
            const iso = isoNumericToAlpha3(d.id);
            return attackedISO.has(iso) ? '#c8d8ee' : '#e8f0f8';
          })
          .attr('stroke', '#b8cce0')
          .attr('stroke-width', 0.4)
          .on('mouseover', function() { d3.select(this).attr('fill', '#bdd0e8'); })
          .on('mouseout',  function(evt, d) {
            const iso = isoNumericToAlpha3(d.id);
            d3.select(this).attr('fill', attackedISO.has(iso) ? '#c8d8ee' : '#e8f0f8');
          });

        // Country borders
        svg.append('path')
          .datum(topojson.mesh(world, world.objects.countries, (a,b) => a !== b))
          .attr('d', path)
          .attr('fill', 'none')
          .attr('stroke', '#a8bcd4')
          .attr('stroke-width', 0.5);

        // Markers group
        const markersG = svg.append('g').attr('id', 'map-markers');

        IP_DATA.filter(d => d.lat !== 0 || d.lon !== 0).forEach((d, i) => {
          const coords = projection([d.lon, d.lat]);
          if (!coords) return;
          const [cx, cy] = coords;
          const color = SEV_COLOR[d.sev];
          const rBase = d.sev==='critico' ? 8 : d.sev==='alto' ? 6 : 5;

          const g = markersG.append('g')
            .attr('class', 'map-marker')
            .style('cursor', 'pointer');

          // Pulse rings (2)
          [1, 2].forEach(ri => {
            g.append('circle')
              .attr('cx', cx).attr('cy', cy).attr('r', rBase * 0.5)
              .attr('fill', 'none')
              .attr('stroke', color)
              .attr('stroke-width', ri === 1 ? 1.5 : 0.8)
              .attr('opacity', 0)
              .attr('class', 'pulse-ring');
          });

          // Core dot
          g.append('circle')
            .attr('cx', cx).attr('cy', cy).attr('r', rBase * 0.45)
            .attr('fill', color)
            .attr('opacity', 0)
            .attr('class', 'marker-dot');

          // Hit area
          g.append('circle')
            .attr('cx', cx).attr('cy', cy).attr('r', 14)
            .attr('fill', 'transparent')
            .on('mouseenter', (evt) => showIPTooltip(d, evt))
            .on('mouseleave', hideIPTooltip);
        });

        // Animate on build
        animateMarkers();
      })
      .catch(err => console.warn('Map load error:', err));
  }

  /* ── ISO numeric → alpha3 lookup (subset) ── */
  function isoNumericToAlpha3(id) {
    const map = {'276':'DEU','840':'USA','643':'RUS','804':'UKR','528':'NLD',
                 '250':'FRA','156':'CHN','392':'JPN','826':'GBR','056':'BEL',
                 '724':'ESP','380':'ITA','616':'POL','203':'CZE','040':'AUT'};
    return map[String(id)] || '';
  }

  /* ── Tooltip ── */
  let ipTooltipEl = null;
  function showIPTooltip(d, evt) {
    if (!ipTooltipEl) {
      ipTooltipEl = document.createElement('div');
      ipTooltipEl.style.cssText = 'position:fixed;background:#0f1923;color:#e8eaf0;padding:9px 13px;border-radius:7px;font-size:11px;font-family:SF Mono,Consolas,monospace;pointer-events:none;z-index:9999;line-height:1.7;box-shadow:0 4px 16px rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.08);';
      document.body.appendChild(ipTooltipEl);
    }
    const color = SEV_COLOR[d.sev];
    ipTooltipEl.innerHTML =
      `<div style="color:${color};font-weight:700;margin-bottom:3px">${d.ip}</div>
       <div>${flagImg(d.type, '20x15')} ${d.label}</div>
       <div style="color:#8a9ab0">${d.hits} conexiones &middot; ${d.type}</div>`;
    ipTooltipEl.style.display = 'block';
    moveIPTooltip(evt);
    document.addEventListener('mousemove', moveIPTooltip);
  }
  function moveIPTooltip(evt) {
    if (!ipTooltipEl) return;
    ipTooltipEl.style.left = (evt.clientX + 14) + 'px';
    ipTooltipEl.style.top  = (evt.clientY - 10) + 'px';
  }
  function hideIPTooltip() {
    if (ipTooltipEl) ipTooltipEl.style.display = 'none';
    document.removeEventListener('mousemove', moveIPTooltip);
  }

  /* ── Animations with anime.js ── */
  function animateMarkers() {
    if (typeof anime === 'undefined') return;

    document.querySelectorAll('.marker-dot').forEach((dot, i) => {
      anime({ targets: dot, opacity: [0, 0.9], duration: 500, delay: i * 150, easing: 'easeOutQuad' });
    });

    function pulseRings() {
      document.querySelectorAll('.map-marker').forEach((g, i) => {
        const rings = g.querySelectorAll('.pulse-ring');
        const dot   = g.querySelector('.marker-dot');
        const rBase = dot ? parseFloat(dot.getAttribute('r')) / 0.45 : 5;
        rings.forEach((ring, ri) => {
          anime({
            targets: ring,
            r: [rBase * 0.5, rBase * 3.8],
            opacity: [0.65, 0],
            duration: 2400,
            delay: i * 280 + ri * 500,
            loop: true,
            easing: 'easeOutExpo'
          });
        });
      });
    }
    setTimeout(pulseRings, 600);

    // Country bars animate in
    const fills = document.querySelectorAll('.ip-country-fill');
    fills.forEach(el => { el._w = el.style.width; el.style.width = '0%'; });
    anime({
      targets: fills,
      width: (el) => el._w,
      duration: 800,
      delay: anime.stagger(70, {start: 300}),
      easing: 'easeOutCubic'
    });

    // Table rows
    anime({
      targets: '#ip-tbl-body tr',
      opacity: [0, 1],
      translateX: [-8, 0],
      duration: 350,
      delay: anime.stagger(50, {start: 200}),
      easing: 'easeOutQuad'
    });

    // Stats count up
    document.querySelectorAll('.ip-stat-value').forEach(el => {
      const target = parseInt(el.textContent);
      if (!isNaN(target)) {
        anime({ targets: {v:0}, v: target, duration: 900, easing: 'easeOutQuad',
          update: a => { el.textContent = Math.round(a.animations[0].currentValue); } });
      }
    });
  }

  /* ── Actualizar solo marcadores del mapa (sin reconstruir el base) ── */
  function refreshMapMarkers() {
    const markersG = d3.select('#map-markers');
    if (markersG.empty()) { buildD3Map(); return; }
    markersG.selectAll('*').remove();
    const svgEl  = d3.select('#ip-map-container svg');
    if (svgEl.empty()) return;
    const svgNode = svgEl.node();
    const W = svgNode ? svgNode.getBoundingClientRect().width : 800;
    const H = parseInt(svgEl.attr('height')) || Math.round(W * 0.48);
    const projection = d3.geoNaturalEarth1().scale(W / 6.0).translate([W / 2, H / 2]);
    const SC = { critico:'#c0392b', alto:'#e67e22', medio:'#f0a030', bajo:'#4a9eff' };
    IP_DATA.filter(d => d.lat !== 0 || d.lon !== 0).forEach((d) => {
      const coords = projection([d.lon, d.lat]);
      if (!coords) return;
      const [cx, cy] = coords;
      const color = SC[d.sev] || '#4a9eff';
      const rBase = d.sev === 'critico' ? 8 : d.sev === 'alto' ? 6 : 5;
      const g = markersG.append('g').attr('class', 'map-marker').style('cursor', 'pointer');
      [1, 2].forEach(ri => {
        g.append('circle').attr('cx', cx).attr('cy', cy).attr('r', rBase * 0.5)
          .attr('fill', 'none').attr('stroke', color)
          .attr('stroke-width', ri === 1 ? 1.5 : 0.8).attr('opacity', 0).attr('class', 'pulse-ring');
      });
      g.append('circle').attr('cx', cx).attr('cy', cy).attr('r', rBase * 0.45)
        .attr('fill', color).attr('opacity', 0).attr('class', 'marker-dot');
      g.append('circle').attr('cx', cx).attr('cy', cy).attr('r', 14)
        .attr('fill', 'transparent')
        .on('mouseenter', (evt) => showIPTooltip(d, evt))
        .on('mouseleave', hideIPTooltip);
    });
    animateMarkers();
  }

  /* ── Nav tab trigger (IPs) ── */
  document.querySelector('.nav-tabs').addEventListener('click', e => {
    const btn = e.target.closest('[data-view]');
    if (btn && btn.dataset.view === 'ips') {
      buildD3Map();
    }
  });