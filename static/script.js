// SRD Admin JS
/* async function fetchJSON(url, opts={}) {
  const res = await fetch(url, Object.assign({headers: {'Content-Type': 'application/json'}}, opts));
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res.text();
} */

async function fetchJSON(url, opts = {}) {
  // Include CSRF token for POSTs
  const tokenEl = document.querySelector('meta[name="csrf-token"]');
  const token = tokenEl ? tokenEl.getAttribute('content') : '';
  const headers = Object.assign(
    {'Content-Type': 'application/json'},
    (opts.headers || {}),
    token ? {'X-CSRFToken': token} : {}
  );
  const res = await fetch(url, Object.assign({}, opts, {headers}));
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}


async function refreshStatus() {
  const ps = document.getElementById('prom-status');
  const gs = document.getElementById('graf-status');
  if (!ps || !gs) return;
  try {
    const s = await fetchJSON('/api/status');
    ps.textContent = s.prometheus ? 'OK' : 'DOWN';
    gs.textContent = s.grafana ? 'OK' : 'DOWN';
  } catch (e) {
    ps.textContent = 'error'; gs.textContent = 'error';
    console.error('Error in refreshStatus:', e);
  }
}

/*async function refreshStatus() {
  try {
    const s = await fetchJSON('/api/status');
    document.getElementById('prom-status').textContent = s.prometheus ? 'OK' : 'DOWN';
    document.getElementById('graf-status').textContent = s.grafana ? 'OK' : 'DOWN';
  } catch (e) {
    const ps = document.getElementById('prom-status'); if (ps) ps.textContent = 'error';
    const gs = document.getElementById('graf-status'); if (gs) gs.textContent = 'error';
  }
} */

/* async function provision() {
  const btn = document.getElementById('btn-provision');
  const out = document.getElementById('provision-result');
  if (!btn || !out) return;
  btn.disabled = true; btn.textContent = 'Provisioning…';
  try {
    const data = await fetchJSON('/admin/provision', {method:'POST', body: '{}'});
    out.style.display = 'block';
    out.textContent = JSON.stringify(data, null, 2);
    btn.textContent = 'Provisioned ✓';
  } catch (e) {
    out.style.display = 'block';
    out.textContent = 'Error: ' + e.message;
    btn.textContent = 'Provision (retry)';
  } finally {
    btn.disabled = false;
  }
} */



// script.js

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-provision");
  const out = document.getElementById("provision-result");

  async function provision() {
    // UI state
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Provisioning…";
    out.style.display = "block";
    out.textContent = "Starting provisioning…";

    try {
      // Adjust payload as needed for your backend
      const res = await fetch("/api/provision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          // You can customize these or capture from inputs if you add them in HTML
          datasource: {
            name: "Prometheus",
            type: "prometheus",
            url: "http://prometheus:9090",
            access: "proxy",
            isDefault: true
          },
          folder: { title: "SRD Monitoring" },
          dashboard: {
            uid: "srd-api",               // change if you need a different UID
            title: "SRD HTTP API Dashboard",
            panels: []                    // add panels later or on the server
          }
        })
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status} ${res.statusText}\n${text}`);
      }

      const data = await res.json();
      out.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      out.textContent = "❌ Provision failed:\n" + (err?.message || String(err));
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  }

  btn.addEventListener("click", provision);
});

// Example: call backend to provision a new dashboard
/* function provisionDashboard() {
    fetchJSON('/admin/provision', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: '{}'
    }).then(response => {
        alert("Dashboard provisioned: " + JSON.stringify(response));
    }).catch(err => console.error(err));
} */

// Provision dashboard
/* async function provisionDashboard() {
  try {
    const response = await fetchJSON('/admin/provision', {method: 'POST', body: '{}'});
    alert("Dashboard provisioned: " + JSON.stringify(response));
  } catch (err) {
    console.error(err);
    alert("Error provisioning dashboard: " + err.message);
  }
} */

// Provision dashboard with friendly message + link
async function provisionDashboard() {
  const btn = document.getElementById('btn-provision');
  const out = document.getElementById('provision-result');
  if (!btn) return;

  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = 'Provisioning…';

  try {
    const data = await fetchJSON('/admin/provision', {method:'POST', body:'{}'});

    // Link to Grafana if URL returned
    const link = data.grafana_dashboard_url
      ? `<a class="btn" href="${data.grafana_dashboard_url}" target="_blank">Open in Grafana</a>`
      : '';

    setToast(true, `
      <strong>✅ ${data.message}</strong><br>
      Folder: <code>${data.grafana_folder}</code> — Dashboard: <code>${data.grafana_dashboard_title}</code><br>
      ${link}
    `);

    // Show raw JSON (optional)
    if (out) {
      out.style.display = 'block';
      out.textContent = JSON.stringify(data.raw || data, null, 2);
    }

    btn.textContent = 'Provisioned ✓';
  } catch (err) {
    console.error(err);
    setToast(false, `<strong>❌ Provision failed.</strong><br><code>${(err && err.message) || err}</code>`);
    if (out) { out.style.display = 'block'; out.textContent = String(err); }
    btn.textContent = 'Provision (retry)';
  } finally {
    btn.disabled = false;
  }
}

// Update alert thresholds
async function updateAlerts(newRules) {
  try {
    const response = await fetchJSON('/api/alerts/update', {
      method: 'POST',
      body: JSON.stringify(newRules)
    });
    alert("Alerts updated: " + JSON.stringify(response));
  } catch (err) {
    console.error(err);
    alert("Error updating alerts: " + err.message);
  }
}    

// Example: update alert rules
/*function updateAlerts(newRules) {
    fetchJSON('/api/alerts/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(newRules)
    }).then(response => {
        alert("Alerts updated: " + JSON.stringify(response));
    }).catch(err => console.error(err));
}*/


async function grafInfo() {
  const btn = document.getElementById('btn-graf-info');
  const out = document.getElementById('graf-info');
  if (!btn || !out) return;
  try {
    const data = await fetchJSON('/admin/grafana-info');
    out.style.display = 'block';
    out.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    out.style.display = 'block';
    out.textContent = 'Error: ' + e.message;
  }
}

async function saveAlertsAjax() {
  const out = document.getElementById('ajax-alert-out');
  const cpu = parseInt(document.getElementById('cpu')?.value || '80', 10);
  const memory = parseInt(document.getElementById('memory')?.value || '80', 10);
  const disk = parseInt(document.getElementById('disk')?.value || '80', 10);
  try {
    const data = await fetchJSON('/api/alerts/update', {
      method:'POST',
      body: JSON.stringify({cpu, memory, disk})
    });
    out.style.display = 'block';
    out.textContent = 'Updated: ' + JSON.stringify(data);
  } catch (e) {
    out.style.display = 'block';
    out.textContent = 'Error: ' + e.message;
  }
}

document.addEventListener('DOMContentLoaded', ()=>{
  refreshStatus();
  setInterval(refreshStatus, 10000);
  const p = document.getElementById('btn-provision'); if (p) p.addEventListener('click', provisionDashboard);
  const gi = document.getElementById('btn-graf-info'); if (gi) gi.addEventListener('click', grafInfo);
  const sa = document.getElementById('btn-alert-save-ajax'); if (sa) sa.addEventListener('click', saveAlertsAjax);
});

document.addEventListener('DOMContentLoaded', ()=>{
  // Status polling
  function paintStatus(ok, el){ el.textContent = ok ? 'OK' : 'DOWN'; el.className = ok ? 'status-ok' : 'status-bad'; }
  async function refreshStatus(){
    const ps = document.getElementById('prom-status');
    const gs = document.getElementById('graf-status');
    if (!ps || !gs) return;
    try{
      const s = await fetchJSON('/api/status');
      paintStatus(!!s.prometheus, ps);
      paintStatus(!!s.grafana, gs);
    }catch(e){
      paintStatus(false, ps); paintStatus(false, gs);
    }
  }
  refreshStatus(); setInterval(refreshStatus, 10000);

  // Buttons
  const p = document.getElementById('btn-provision');
  if (p) p.addEventListener('click', provisionDashboard);

  const gi = document.getElementById('btn-graf-info');
  if (gi) gi.addEventListener('click', async ()=>{
    const out = document.getElementById('graf-info');
    try {
      const data = await fetchJSON('/admin/grafana-info');
      out.style.display='block';
      out.textContent = JSON.stringify(data, null, 2);
    } catch(e) {
      out.style.display='block';
      out.textContent = 'Error: ' + e.message;
    }
  });

  const sa = document.getElementById('btn-alert-save-ajax');
  if (sa) sa.addEventListener('click', saveAlertsAjax);
});

// Back button logic (works on all pages that include #btn-back)
document.addEventListener('DOMContentLoaded', () => {
  const back = document.getElementById('btn-back');
  if (back) {
    back.addEventListener('click', () => {
      if (window.history.length > 1) window.history.back();
      else window.location.href = '/';
    });
  }
});