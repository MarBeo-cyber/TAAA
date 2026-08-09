"""
TAAA — AR Display Server

Serves a live AR-glasses HUD and drives it from the real TAAA pipeline over
Server-Sent Events.

Routes:
  GET  /ar                    → AR glasses HUD (HTML)
  GET  /ar/stream             → SSE stream of AR events
  POST /ar/scenario/<name>    → run a scenario through the real agent; each
                                pipeline cycle is pushed to /ar/stream

HISTORY — why this file was rewritten
  The previous version served a 660-line HTML storyboard. Its `SCENARIOS` object
  held {delay, action} steps replayed with setTimeout, and the "pipeline output"
  it displayed was typed constants: gap "INTERFERENCE (conf=0.72)", stress
  "0.82 | HRV=22ms", and gap "PARTIAL (conf=0.68)" — a value the pipeline could
  not produce at all. The client contained zero EventSource and zero fetch calls.
  register_ar_routes() was never called from create_app(), push_ar_event() had no
  call sites, and GET /ar returned 404. Nothing rendered there came from the
  agent. Everything rendered now does; the HUD has no scenario constants left.

  The standalone TAAA_AR_Display_8_1.html at the repository root is the original
  storyboard. It is kept, and labelled, as a non-functional design mock-up.
"""

from __future__ import annotations

import json
import queue
import time
import logging

from flask import Flask, Response, jsonify, stream_with_context

logger = logging.getLogger("taaa.ar_display")

# SSE event queue
_ar_event_queue: queue.Queue = queue.Queue(maxsize=100)


def push_ar_event(event_type: str, data: dict):
    """Push an AR event to connected displays.

    Wired up by register_ar_routes(): it sets agent.event_sink to this function,
    so TAAAAgent.process() emits one event per completed cycle.
    """
    try:
        _ar_event_queue.put_nowait({"type": event_type, "data": data, "ts": time.time()})
    except queue.Full:
        # Not silent: a full queue means the display is behind and is now
        # showing stale state, which a demo operator needs to know about.
        logger.warning("[AR] event queue full — dropping %s event", event_type)


def ar_display_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>TAAA — AR Glasses Display (live)</title>
<style>
  :root {
    --bg: #0a0c14;
    --hud-green: #00ff88;
    --hud-red: #ff3344;
    --hud-amber: #ffaa00;
    --hud-blue: #44aaff;
    --hud-white: rgba(255,255,255,0.92);
    --hud-dim: rgba(255,255,255,0.35);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--hud-white);
    font-family: 'SF Mono', 'Fira Code', monospace;
    min-height: 100vh; padding: 24px;
    display: flex; flex-direction: column; align-items: center; gap: 16px;
  }
  h1 { font-size: 13px; letter-spacing: 0.2em; color: var(--hud-dim); }
  .conn { font-size: 11px; letter-spacing: 0.1em; }
  .conn.up { color: var(--hud-green); }
  .conn.down { color: var(--hud-red); }
  .glass {
    width: min(920px, 100%); aspect-ratio: 16/7; position: relative;
    border: 1px solid rgba(255,255,255,0.10); border-radius: 90px;
    background: radial-gradient(circle at 50% 40%, #0d1220 0%, #05070d 100%);
    overflow: hidden;
  }
  .corner { position: absolute; font-size: 10px; letter-spacing: 0.12em;
            color: var(--hud-dim); }
  #cornerTL { top: 22px; left: 60px; } #cornerTR { top: 22px; right: 60px; }
  #cornerBL { bottom: 22px; left: 60px; } #cornerBR { bottom: 22px; right: 60px; }
  .centre { position: absolute; inset: 0; display: flex; flex-direction: column;
            align-items: center; justify-content: center; gap: 14px; padding: 0 90px; }
  .mbadge { font-size: 34px; font-weight: 700; letter-spacing: 0.1em; opacity: 0.25; }
  .mbadge.M0 { color: var(--hud-red); opacity: 1; }
  .mbadge.M1 { color: var(--hud-amber); opacity: 1; }
  .mbadge.M2 { color: var(--hud-blue); opacity: 1; }
  .ar-line { font-size: 15px; color: var(--hud-green); text-align: center; }
  .ar-line.stop { color: var(--hud-red); }
  .voice { font-size: 13px; color: var(--hud-white); text-align: center;
           border: 1px solid rgba(255,255,255,0.12); border-radius: 20px;
           padding: 7px 18px; }
  .voice:empty { display: none; }
  .haptic { font-size: 11px; color: var(--hud-amber); letter-spacing: 0.1em; }
  .haptic:empty { display: none; }
  .controls { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
  .btn { background: rgba(255,255,255,0.05); color: var(--hud-white);
         border: 1px solid rgba(255,255,255,0.14); border-radius: 8px;
         padding: 9px 14px; font-family: inherit; font-size: 12px; cursor: pointer; }
  .btn:hover { background: rgba(255,255,255,0.11); }
  .panel { width: min(920px, 100%); border: 1px solid rgba(255,255,255,0.08);
           border-radius: 10px; padding: 14px 16px; font-size: 12px; }
  .panel h2 { font-size: 10px; letter-spacing: 0.14em; color: var(--hud-dim);
              margin-bottom: 8px; font-weight: 400; }
  .kv { display: flex; gap: 8px; padding: 2px 0; }
  .kv span { color: var(--hud-dim); min-width: 190px; }
  pre { font-size: 11px; color: var(--hud-dim); white-space: pre-wrap;
        max-height: 220px; overflow: auto; }
  .note { width: min(920px,100%); font-size: 11px; color: var(--hud-dim);
          line-height: 1.6; }
</style>
</head>
<body>

<h1>TAAA — AR GLASSES DISPLAY</h1>
<div class="conn down" id="conn">● STREAM: connecting…</div>

<div class="glass">
  <div class="corner" id="cornerTL">TAAA</div>
  <div class="corner" id="cornerTR">M-LEVEL: —</div>
  <div class="corner" id="cornerBL">SCHEMA: IDLE</div>
  <div class="corner" id="cornerBR"></div>
  <div class="centre">
    <div class="mbadge" id="mBadge">—</div>
    <div class="ar-line" id="arLine"></div>
    <div class="voice" id="voice"></div>
    <div class="haptic" id="haptic"></div>
  </div>
</div>

<div class="controls">
  <button class="btn" onclick="runScenario('shinjuku')">Scenario 1 — Shinjuku (emergency)</button>
  <button class="btn" onclick="runScenario('negotiation')">Scenario 2 — David / Tanaka</button>
  <button class="btn" onclick="runScenario('medical')">Scenario 3 — Lin Mei / Dr. Chen</button>
  <button class="btn" onclick="runScenario('contract')">Scenario 4 — Contract / M2 queue</button>
</div>

<div class="panel">
  <h2>LAST PIPELINE CYCLE — VALUES AS RETURNED BY TAAAAgent.process()</h2>
  <div id="kvs"><span style="color:rgba(255,255,255,0.25)">No cycle received yet.</span></div>
</div>

<div class="panel">
  <h2>RAW EVENT</h2>
  <pre id="raw">—</pre>
</div>

<p class="note">
  Everything above is rendered from <code>/ar/stream</code>. There are no scenario
  constants in this page: if the pipeline reports <code>gap=none</code>, this HUD
  shows <code>none</code>. The rule-based gap detector reports a
  <code>rule_id</code> rather than a confidence number, because it is a keyword
  classifier with no calibration data.
</p>

<script>
function el(id) { return document.getElementById(id); }

function kv(k, v) {
  return '<div class="kv"><span>' + k + '</span><strong>' +
         (v === null || v === undefined ? '—' : String(v)) + '</strong></div>';
}

function render(d) {
  const g = d.gap, t = d.timing, i = d.intervention;

  el('mBadge').className = 'mbadge ' + t.m_level;
  el('mBadge').textContent = t.m_level;
  el('cornerTL').textContent = 'TAAA ' + d.domain.toUpperCase();
  el('cornerTR').textContent = 'M-LEVEL: ' + t.m_level;
  el('cornerBL').textContent = 'GAP: ' + g.type.toUpperCase();
  el('cornerBR').textContent = 'stress: ' + t.stress.toFixed(2);

  const line = el('arLine');
  line.textContent = i.ar_active ? i.ar_instruction : '';
  line.className = 'ar-line' + (i.suppression_first ? ' stop' : '');

  el('voice').textContent = i.voice_active && i.voice_message ? i.voice_message : '';
  el('haptic').textContent = i.haptic_active ? '⚡ ' + i.haptic_pattern : '';

  const gapDetail = g.detector === 'llm'
      ? 'llm_confidence=' + g.llm_confidence
      : 'rule=' + g.rule_id;

  let rows = '';
  rows += kv('tick / latency', d.tick + '  ·  ' + d.latency_ms + ' ms');
  rows += kv('subject', d.subject_id);
  rows += kv('domain', d.domain);
  rows += kv('gap.type', g.type);
  rows += kv('gap.detector', g.detector + '  ·  ' + gapDetail);
  rows += kv('gap.evidence', (g.evidence || []).join(', '));
  rows += kv('gap.suppression_required', g.suppression_required);
  rows += kv('timing.m_level', t.m_level);
  rows += kv('timing.stress (smoothed)', t.stress);
  rows += kv('timing.output_type', t.output_type);
  rows += kv('timing.paaa_used', t.paaa_used);
  if (d.interference) {
    rows += kv('interference.strength', d.interference.strength);
    rows += kv('interference.timing_ms', d.interference.timing_ms);
  }
  rows += kv('intervention.strategy', i.strategy);
  rows += kv('intervention.rationale', i.rationale);
  if (d.m2_update_proposal) {
    rows += kv('m2.sars', d.m2_update_proposal.sars);
    rows += kv('m2.trigger_state', d.m2_update_proposal.trigger_state);
    rows += kv('m2.risk_class', d.m2_update_proposal.risk_class);
    rows += kv('m2.recommendation', d.m2_update_proposal.recommendation);
    rows += kv('m2.operational_update_allowed', d.m2_update_proposal.operational_update_allowed);
  } else {
    rows += kv('m2 proposal', 'none queued for this cycle');
  }
  el('kvs').innerHTML = rows;
}

const es = new EventSource('/ar/stream');
es.onopen = function () {
  el('conn').className = 'conn up';
  el('conn').textContent = '● STREAM: connected to /ar/stream';
};
es.onerror = function () {
  el('conn').className = 'conn down';
  el('conn').textContent = '● STREAM: disconnected';
};
es.onmessage = function (e) {
  const ev = JSON.parse(e.data);
  el('raw').textContent = JSON.stringify(ev, null, 2);
  if (ev.type === 'pipeline_cycle') { render(ev.data); }
};

function runScenario(name) {
  el('conn').textContent = '● STREAM: running ' + name + '…';
  fetch('/ar/scenario/' + name, { method: 'POST' })
    .then(function (r) { return r.json(); })
    .then(function (j) {
      el('conn').className = 'conn up';
      el('conn').textContent = '● STREAM: ' + name + ' → ' + j.cycles + ' cycle(s) pushed';
    })
    .catch(function (err) {
      el('conn').className = 'conn down';
      el('conn').textContent = '● STREAM: ' + err;
    });
}
</script>
</body>
</html>"""


def register_ar_routes(app: Flask, agent):
    """Register AR display routes and connect the agent's event sink.

    `agent` is used: its event_sink is set to push_ar_event, so every cycle of
    TAAAAgent.process() reaches the HUD, and /ar/scenario/<name> runs the real
    demo scenarios against it.
    """
    agent.event_sink = push_ar_event

    @app.get("/ar")
    def ar_display():
        return ar_display_html(), 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/ar/stream")
    def ar_stream():
        def generate():
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    ev = _ar_event_queue.get(timeout=1.0)
                    yield f"data: {json.dumps(ev)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    @app.post("/ar/scenario/<name>")
    def ar_scenario(name):
        from scenarios.demo import (
            scenario_shinjuku, scenario_negotiation, scenario_medical,
            scenario_contract_m2,
        )
        scenarios = {
            "shinjuku":    scenario_shinjuku,
            "negotiation": scenario_negotiation,
            "medical":     scenario_medical,
            "contract":    scenario_contract_m2,
        }
        if name not in scenarios:
            return jsonify({"error": f"unknown scenario '{name}'",
                            "available": sorted(scenarios)}), 400
        before = agent.stats().get("total_cycles", 0)
        scenarios[name](agent)
        after = agent.stats().get("total_cycles", 0)
        return jsonify({"status": "run", "scenario": name,
                        "cycles": after - before})

    return app
