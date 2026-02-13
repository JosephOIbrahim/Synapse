"""
Synapse Monitoring Dashboard

Embedded web dashboard served via hwebserver at /dashboard.
Single HTML page with inline CSS/JS — no external dependencies.
Connects to Synapse WebSocket for live metric updates.

Design: Houdini 21 dark theme, SIGNAL cyan accents, 4-panel grid.
"""

import logging
from typing import Optional

logger = logging.getLogger("synapse.dashboard")


# =========================================================================
# Dashboard HTML (complete page — under 50KB)
# =========================================================================

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SYNAPSE Monitor</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a1a;color:#e0e0e0;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.4}
.header{display:flex;align-items:center;justify-content:space-between;padding:12px 20px;background:#222;border-bottom:1px solid #333}
.header h1{font-size:18px;font-weight:600;letter-spacing:0.5px}
.header h1 span{color:#00D4FF}
.controls{display:flex;align-items:center;gap:12px}
.controls label{font-size:12px;color:#999}
.controls select,.controls button{background:#333;color:#e0e0e0;border:1px solid #444;border-radius:4px;padding:4px 8px;font-size:12px;cursor:pointer}
.controls button:hover{background:#444}
.controls button.active{background:#00D4FF;color:#1a1a1a;border-color:#00D4FF}
.status{display:flex;align-items:center;gap:6px;font-size:12px;color:#999}
.dot{width:8px;height:8px;border-radius:50%;background:#666}
.dot.ok{background:#4CAF50}
.dot.warn{background:#FFB800}
.dot.err{background:#FF4444}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px 20px}
.card{background:#252525;border:1px solid #333;border-radius:6px;padding:16px}
.card h2{font-size:13px;font-weight:600;color:#00D4FF;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #333}
.row{display:flex;justify-content:space-between;align-items:center;padding:4px 0}
.row .label{color:#999;font-size:12px}
.row .value{font-size:14px;font-weight:500;font-variant-numeric:tabular-nums}
.value.accent{color:#00D4FF}
.value.warn{color:#FFB800}
.value.err{color:#FF4444}
.value.ok{color:#4CAF50}
.bar-row{margin:6px 0}
.bar-label{font-size:11px;color:#999;margin-bottom:2px;display:flex;justify-content:space-between}
.bar{height:6px;background:#333;border-radius:3px;overflow:hidden}
.bar-fill{height:100%;background:#00D4FF;border-radius:3px;transition:width 0.3s ease}
.tier-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
.tier-chip{background:#333;border-radius:3px;padding:2px 8px;font-size:11px;font-variant-numeric:tabular-nums}
.tier-chip .tn{color:#999}
.tier-chip .tv{color:#e0e0e0;margin-left:4px}
.footer{padding:8px 20px;text-align:center;font-size:11px;color:#666;border-top:1px solid #333}
@media(max-width:640px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>

<div class="header">
  <h1><span>SYNAPSE</span> Monitor</h1>
  <div class="controls">
    <div class="status">
      <div class="dot" id="statusDot"></div>
      <span id="statusText">connecting...</span>
    </div>
    <label>Interval</label>
    <select id="intervalSelect">
      <option value="1000">1s</option>
      <option value="2000" selected>2s</option>
      <option value="5000">5s</option>
      <option value="10000">10s</option>
    </select>
    <button id="pauseBtn">Pause</button>
  </div>
</div>

<div class="grid">
  <!-- Scene -->
  <div class="card">
    <h2>Scene</h2>
    <div class="row"><span class="label">HIP File</span><span class="value" id="hipFile">-</span></div>
    <div class="row"><span class="label">Frame</span><span class="value" id="frame">-</span></div>
    <div class="row"><span class="label">FPS</span><span class="value" id="fps">-</span></div>
    <div class="row"><span class="label">Total Nodes</span><span class="value accent" id="totalNodes">-</span></div>
    <div class="row"><span class="label">SOP / LOP / OBJ</span><span class="value" id="nodeBreakdown">-</span></div>
    <div class="row"><span class="label">Warnings</span><span class="value" id="warnings">0</span></div>
    <div class="row"><span class="label">Errors</span><span class="value" id="errors">0</span></div>
  </div>

  <!-- Routing -->
  <div class="card">
    <h2>Routing</h2>
    <div class="row"><span class="label">Total Requests</span><span class="value accent" id="totalRequests">0</span></div>
    <div class="bar-row">
      <div class="bar-label"><span>Cache Hit Rate</span><span id="cacheRate">0%</span></div>
      <div class="bar"><div class="bar-fill" id="cacheBar" style="width:0%"></div></div>
    </div>
    <div class="row"><span class="label">Avg Latency</span><span class="value" id="avgLatency">-</span></div>
    <div class="row"><span class="label">Knowledge Entries</span><span class="value" id="knowledgeEntries">0</span></div>
    <div class="row"><span class="label">Tier Distribution</span></div>
    <div class="tier-row" id="tierDist"></div>
  </div>

  <!-- Resilience -->
  <div class="card">
    <h2>Resilience</h2>
    <div class="row"><span class="label">Circuit Breaker</span><span class="value" id="cbState">closed</span></div>
    <div class="row"><span class="label">Trip Count</span><span class="value" id="cbTrips">0</span></div>
    <div class="row"><span class="label">Rate Limiter</span><span class="value" id="rlActive">inactive</span></div>
    <div class="row"><span class="label">Rejections</span><span class="value" id="rlRejects">0</span></div>
    <div class="row"><span class="label">Health</span><span class="value" id="health">-</span></div>
    <div class="row"><span class="label">Uptime</span><span class="value accent" id="uptime">-</span></div>
  </div>

  <!-- Sessions -->
  <div class="card">
    <h2>Sessions</h2>
    <div class="row"><span class="label">Active Sessions</span><span class="value accent" id="activeSessions">0</span></div>
    <div class="row"><span class="label">Total Commands</span><span class="value" id="totalCommands">0</span></div>
    <div class="row"><span class="label">Commands/min</span><span class="value" id="cmdsPerMin">0</span></div>
    <div class="row"><span class="label">RBAC</span><span class="value" id="rbac">off</span></div>
    <div class="row"><span class="label">Deploy Mode</span><span class="value" id="deployMode">local</span></div>
  </div>
</div>

<div class="footer">SYNAPSE v5.4.0 &mdash; Sprint E: Real-Time Monitoring</div>

<script>
(function(){
  const $ = id => document.getElementById(id);
  let ws = null;
  let paused = false;
  let interval = 2000;
  let timer = null;
  let msgId = 0;

  function connect(){
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const port = location.port || (location.protocol === 'https:' ? '443' : '80');
    // Default to 9999 if served from a different port (e.g. hwebserver on 8080)
    const wsPort = 9999;
    const url = proto + '//localhost:' + wsPort + '/synapse';

    try { ws = new WebSocket(url); } catch(e){ setStatus('err', 'connect failed'); return; }

    ws.onopen = function(){
      setStatus('ok', 'connected');
      poll();
    };
    ws.onclose = function(){
      setStatus('err', 'disconnected');
      clearTimeout(timer);
      setTimeout(connect, 3000);
    };
    ws.onerror = function(){
      setStatus('err', 'error');
    };
    ws.onmessage = function(e){
      try{
        const msg = JSON.parse(e.data);
        if(msg.data) update(msg.data);
      }catch(ex){}
    };
  }

  function poll(){
    if(paused || !ws || ws.readyState !== 1) return;
    msgId++;
    const cmd = JSON.stringify({type:'get_live_metrics',id:'dash-'+msgId,payload:{}});
    try{ ws.send(cmd); }catch(e){}
    timer = setTimeout(poll, interval);
  }

  function setStatus(level, text){
    $('statusDot').className = 'dot ' + level;
    $('statusText').textContent = text;
  }

  function update(d){
    // Scene
    if(d.scene){
      const s = d.scene;
      $('hipFile').textContent = s.hip_file ? s.hip_file.split('/').pop().split('\\').pop() : '-';
      $('frame').textContent = s.current_frame;
      $('fps').textContent = s.fps;
      $('totalNodes').textContent = s.total_nodes;
      $('nodeBreakdown').textContent = s.sop_nodes + ' / ' + s.lop_nodes + ' / ' + s.obj_nodes;

      const wEl = $('warnings');
      wEl.textContent = s.warnings;
      wEl.className = 'value' + (s.warnings > 0 ? ' warn' : '');

      const eEl = $('errors');
      eEl.textContent = s.errors;
      eEl.className = 'value' + (s.errors > 0 ? ' err' : '');
    }

    // Routing
    if(d.routing){
      const r = d.routing;
      $('totalRequests').textContent = r.total_requests;
      $('cacheRate').textContent = r.cache_hit_rate.toFixed(1) + '%';
      $('cacheBar').style.width = Math.min(r.cache_hit_rate, 100) + '%';
      $('avgLatency').textContent = r.avg_latency_ms.toFixed(1) + 'ms';
      $('knowledgeEntries').textContent = r.knowledge_entries;

      // Tier chips
      const container = $('tierDist');
      container.innerHTML = '';
      const tc = r.tier_counts;
      if(tc && typeof tc === 'object'){
        const entries = Array.isArray(tc) ? tc : Object.entries(tc);
        entries.forEach(function(pair){
          const name = pair[0], count = pair[1];
          const chip = document.createElement('span');
          chip.className = 'tier-chip';
          chip.innerHTML = '<span class="tn">' + name + '</span><span class="tv">' + count + '</span>';
          container.appendChild(chip);
        });
      }
    }

    // Resilience
    if(d.resilience){
      const re = d.resilience;
      const cbEl = $('cbState');
      cbEl.textContent = re.circuit_state;
      cbEl.className = 'value' + (re.circuit_state === 'open' ? ' err' : re.circuit_state === 'half_open' ? ' warn' : ' ok');
      $('cbTrips').textContent = re.circuit_trip_count;

      const rlEl = $('rlActive');
      rlEl.textContent = re.rate_limiter_active ? 'active' : 'inactive';
      rlEl.className = 'value' + (re.rate_limiter_active ? ' warn' : '');
      $('rlRejects').textContent = re.rate_limit_rejects;

      const hEl = $('health');
      hEl.textContent = re.health_status;
      hEl.className = 'value' + (re.health_status === 'healthy' ? ' ok' : re.health_status === 'critical' ? ' err' : ' warn');

      $('uptime').textContent = formatUptime(re.uptime_seconds);
    }

    // Sessions
    if(d.session){
      const se = d.session;
      $('activeSessions').textContent = se.active_sessions;
      $('totalCommands').textContent = se.total_commands;
      $('cmdsPerMin').textContent = se.commands_per_minute.toFixed(1);
      $('rbac').textContent = se.rbac_enabled ? 'on' : 'off';
      $('deployMode').textContent = se.deploy_mode;
    }
  }

  function formatUptime(s){
    if(!s || s <= 0) return '-';
    const h = Math.floor(s/3600);
    const m = Math.floor((s%3600)/60);
    if(h > 0) return h + 'h ' + m + 'm';
    if(m > 0) return m + 'm ' + Math.floor(s%60) + 's';
    return Math.floor(s) + 's';
  }

  // Controls
  $('pauseBtn').addEventListener('click', function(){
    paused = !paused;
    this.textContent = paused ? 'Resume' : 'Pause';
    this.classList.toggle('active', paused);
    if(!paused) poll();
  });

  $('intervalSelect').addEventListener('change', function(){
    interval = parseInt(this.value, 10);
    clearTimeout(timer);
    if(!paused) poll();
  });

  connect();
})();
</script>
</body>
</html>"""


# =========================================================================
# Route registration
# =========================================================================

def register_dashboard_route(port: int = 9999) -> bool:
    """Register GET /dashboard on hwebserver. No-op if hwebserver unavailable.

    Args:
        port: WebSocket port (embedded in dashboard HTML for WS connection).

    Returns:
        True if route registered, False if hwebserver unavailable.
    """
    try:
        import hou
        webserver = hou.ui.webServer()
    except (ImportError, AttributeError):
        logger.info("Dashboard route skipped -- hwebserver not available")
        return False

    try:
        def _serve_dashboard(request):
            """Serve the monitoring dashboard HTML."""
            return hou.ui.WebServerResponse(
                body=DASHBOARD_HTML.encode("utf-8"),
                content_type="text/html; charset=utf-8",
                status_code=200,
            )

        webserver.addRoute("/dashboard", _serve_dashboard)
        logger.info("Dashboard registered at /dashboard")
        return True
    except Exception:
        logger.debug("Failed to register dashboard route", exc_info=True)
        return False
