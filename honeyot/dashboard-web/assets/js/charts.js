/* ─────────────────────────────────────────────────────────────────
   charts.js — Honeypot Dashboard · SOC honeycos
   Reloj, gráfico de tráfico 24h y donut chart de servicios.
   Expone: trafficData[], svcData[], drawTrafficChart(), drawSvcChart()
   (modificados por api.js para actualizar con datos reales)
───────────────────────────────────────────────────────────────── */

/* ── Reloj ── */
function tick() {
  const d    = new Date();
  const MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  const pad  = n => String(n).padStart(2, '0');

  // Timezone real del browser en lugar de CEST hardcodeado
  // Formato corto: "CET", "CEST", "UTC", etc.
  const tzName = d.toLocaleTimeString('es-ES', { timeZoneName: 'short' })
                  .split(' ').pop() || 'UTC';

  document.getElementById('clock').textContent =
    `${d.getDate()} ${MESES[d.getMonth()]} ${d.getFullYear()} · ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())} ${tzName}`;
}
tick(); setInterval(tick, 1000);

/* ── Traffic chart ── */
const trafficCtx = document.getElementById('trafficChart').getContext('2d');
let trafficData = [8,5,4,3,6,9,14,22,31,28,19,15,18,24,30,38,42,55,68,80,95,82,71,60];

const grad = trafficCtx.createLinearGradient(0, 0, 0, 130);
grad.addColorStop(0, 'rgba(26,95,168,0.15)');
grad.addColorStop(1, 'rgba(26,95,168,0)');

function drawTrafficChart() {
  const canvas = trafficCtx.canvas;
  const W = canvas.offsetWidth || 600;
  const H = 130;
  canvas.width = W;
  canvas.height = H;

  const max = Math.max(...trafficData);
  const pad = { top: 10, right: 8, bottom: 2, left: 32 };
  const iW = W - pad.left - pad.right;
  const iH = H - pad.top - pad.bottom;

  trafficCtx.clearRect(0, 0, W, H);

  /* Grid lines */
  trafficCtx.strokeStyle = 'rgba(0,0,0,0.06)';
  trafficCtx.lineWidth = 0.5;
  [0.25, 0.5, 0.75, 1].forEach(r => {
    const y = pad.top + iH * (1 - r);
    trafficCtx.beginPath();
    trafficCtx.moveTo(pad.left, y);
    trafficCtx.lineTo(W - pad.right, y);
    trafficCtx.stroke();
    trafficCtx.fillStyle = 'rgba(0,0,0,0.35)';
    trafficCtx.font = '9px monospace';
    trafficCtx.textAlign = 'right';
    trafficCtx.fillText(Math.round(max * r), pad.left - 4, y + 3);
  });

  /* Area fill */
  trafficCtx.beginPath();
  trafficData.forEach((v, i) => {
    const x = pad.left + (i / (trafficData.length - 1)) * iW;
    const y = pad.top + iH * (1 - v / max);
    i === 0 ? trafficCtx.moveTo(x, y) : trafficCtx.lineTo(x, y);
  });
  trafficCtx.lineTo(pad.left + iW, pad.top + iH);
  trafficCtx.lineTo(pad.left, pad.top + iH);
  trafficCtx.closePath();
  trafficCtx.fillStyle = grad;
  trafficCtx.fill();

  /* Line */
  trafficCtx.beginPath();
  trafficCtx.strokeStyle = '#1a5fa8';
  trafficCtx.lineWidth = 1.5;
  trafficCtx.lineJoin = 'round';
  trafficData.forEach((v, i) => {
    const x = pad.left + (i / (trafficData.length - 1)) * iW;
    const y = pad.top + iH * (1 - v / max);
    i === 0 ? trafficCtx.moveTo(x, y) : trafficCtx.lineTo(x, y);
  });
  trafficCtx.stroke();

  /* Last dot */
  const lx = pad.left + iW;
  const ly = pad.top + iH * (1 - trafficData[trafficData.length-1] / max);
  trafficCtx.beginPath();
  trafficCtx.arc(lx, ly, 3, 0, Math.PI * 2);
  trafficCtx.fillStyle = '#1a5fa8';
  trafficCtx.fill();
}
drawTrafficChart();

/* ── Service donut chart ── */
const svcCtx = document.getElementById('svcChart').getContext('2d');

// HTTP y HTTPS como entradas separadas (antes se sumaban o mezclaban)
// El orden importa para el donut: de mayor a menor visibilidad habitual
let svcData   = [247, 210, 198, 89, 62, 41, 18];
const svcLabels = ['SSH', 'HTTP', 'HTTPS', 'FTP', 'SMB', 'RDP', 'Otro'];
const svcColors = ['#4a9eff','#0e7a4e','#1fc97a','#f0a030','#f04a4a','#8a90a0','#c0c8d8'];

// updateSvcChartFromStats (llamado desde api.js) rellena svcData con datos reales.
// Se respeta el orden: SSH, HTTP, HTTPS, FTP, SMB, RDP, Otro
function updateSvcChartFromStats(byService) {
  const order = ['ssh', 'http', 'https', 'ftp', 'smb', 'rdp'];
  const known  = order.map(k => byService[k] || 0);
  const otros  = Object.entries(byService)
    .filter(([k]) => !order.includes(k))
    .reduce((s, [, v]) => s + v, 0);
  svcData = [...known, otros];
  drawSvcChart();
}

function drawSvcChart() {
  const canvas = svcCtx.canvas;
  const W = canvas.offsetWidth || 300;
  // Aumentar altura si hay 7 entradas para que la leyenda quepa
  const H = Math.max(160, svcLabels.length * 24 + 20);
  canvas.width  = W;
  canvas.height = H;
  svcCtx.clearRect(0, 0, W, H);

  // Filtrar entradas con valor > 0 para no dibujar slices vacíos
  const activeIdx = svcData.map((v, i) => i).filter(i => svcData[i] > 0);
  const total     = svcData.reduce((a, b) => a + b, 0);

  if (total === 0) {
    // Sin datos — mostrar anillo vacío
    svcCtx.beginPath();
    svcCtx.arc(W / 2 - 55, H / 2, 55, 0, Math.PI * 2);
    svcCtx.strokeStyle = '#e2e8f0';
    svcCtx.lineWidth = 23;
    svcCtx.stroke();
    return;
  }

  const cx = W / 2 - 55, cy = H / 2, r = 55, inner = 33;
  let angle = -Math.PI / 2;

  // Dibujar slices solo de servicios con hits > 0
  activeIdx.forEach(i => {
    const v     = svcData[i];
    const slice = (v / total) * Math.PI * 2;

    svcCtx.beginPath();
    svcCtx.moveTo(cx, cy);
    svcCtx.arc(cx, cy, r, angle, angle + slice);
    svcCtx.closePath();
    svcCtx.fillStyle = svcColors[i];
    svcCtx.fill();

    // Separador entre slices
    svcCtx.beginPath();
    svcCtx.moveTo(cx, cy);
    svcCtx.arc(cx, cy, r, angle, angle + slice);
    svcCtx.strokeStyle = '#fff';
    svcCtx.lineWidth = 1.5;
    svcCtx.stroke();

    angle += slice;
  });

  /* Agujero interior */
  svcCtx.beginPath();
  svcCtx.arc(cx, cy, inner, 0, Math.PI * 2);
  svcCtx.fillStyle = '#ffffff';
  svcCtx.fill();

  /* Etiqueta central */
  svcCtx.fillStyle = '#0f1923';
  svcCtx.font = '600 15px monospace';
  svcCtx.textAlign = 'center';
  svcCtx.fillText(total.toLocaleString(), cx, cy + 2);
  svcCtx.font = '9px monospace';
  svcCtx.fillStyle = '#8a9ab0';
  svcCtx.fillText('hits', cx, cy + 13);

  /* Leyenda — solo servicios con hits > 0 */
  const gap  = 22;
  const lx   = W / 2 + 8;
  const visibles = activeIdx.length;
  const startY = (H - visibles * gap) / 2 + 10;

  activeIdx.forEach((i, row) => {
    const ly  = startY + row * gap;
    const pct = Math.round((svcData[i] / total) * 100);

    // Color box
    svcCtx.fillStyle = svcColors[i];
    svcCtx.beginPath();
    svcCtx.roundRect?.(lx, ly - 6, 8, 8, 2) ?? svcCtx.fillRect(lx, ly - 6, 8, 8);
    svcCtx.fill();

    // Label
    svcCtx.fillStyle = '#4a5568';
    svcCtx.font = '11px monospace';
    svcCtx.textAlign = 'left';
    svcCtx.fillText(svcLabels[i], lx + 13, ly + 1);

    // Hits
    svcCtx.fillStyle = '#8a9ab0';
    svcCtx.font = '10px monospace';
    svcCtx.fillText(svcData[i].toLocaleString(), lx + 52, ly + 1);

    // Porcentaje
    svcCtx.fillStyle = '#b0bac8';
    svcCtx.font = '9px monospace';
    svcCtx.fillText(`${pct}%`, lx + 82, ly + 1);
  });
}
drawSvcChart();

// Alias global para que api.js pueda llamar a la función correcta
window.updateSvcChartFromStats_charts = updateSvcChartFromStats;

window.addEventListener('resize', () => {
  drawTrafficChart();
  drawSvcChart();
});
