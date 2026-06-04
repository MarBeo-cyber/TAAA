"""
TAAA — AR Display Server
Serves the AR glasses simulation and connects it to the TAAA pipeline
via Server-Sent Events (SSE) for real-time updates.

Routes:
  GET /ar                    → AR glasses simulation (HTML)
  GET /ar/stream             → SSE stream of AR events
  POST /ar/scenario/<name>   → trigger a scenario and stream to AR display
"""

from __future__ import annotations

import json
import time
import queue
import threading
from flask import Flask, Response, stream_with_context

# SSE event queue
_ar_event_queue: queue.Queue = queue.Queue(maxsize=100)


def push_ar_event(event_type: str, data: dict):
    """Push an AR event to connected displays."""
    try:
        _ar_event_queue.put_nowait({"type": event_type, "data": data, "ts": time.time()})
    except queue.Full:
        pass


def ar_display_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>TAAA — AR Glasses Display</title>
<style>
  :root {
    --bg: #050810;
    --glass-bg: rgba(5,8,16,0.85);
    --hud-green: #00ff88;
    --hud-red: #ff3344;
    --hud-amber: #ffaa00;
    --hud-blue: #44aaff;
    --hud-white: rgba(255,255,255,0.92);
    --hud-dim: rgba(255,255,255,0.35);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0a0c14;
    color: var(--hud-white);
    font-family: 'SF Mono', 'Fira Code', monospace;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px;
  }
  h1 { font-size: 13px; letter-spacing: 0.2em; color: var(--hud-dim);
       text-transform: uppercase; margin-bottom: 20px; }

  /* ── AR Glasses Frame ── */
  .glasses-frame {
    width: 780px; height: 420px;
    border: 2px solid rgba(68,170,255,0.3);
    border-radius: 24px;
    position: relative;
    overflow: hidden;
    background: linear-gradient(135deg, #0a0f1a 0%, #060910 100%);
    box-shadow: 0 0 60px rgba(68,170,255,0.08), inset 0 0 80px rgba(0,0,0,0.6);
  }

  /* Simulated street/environment background */
  .env-bg {
    position: absolute; inset: 0;
    background:
      linear-gradient(180deg, rgba(20,25,40,0.7) 0%, rgba(10,12,20,0.9) 100%);
  }
  .env-lines {
    position: absolute; inset: 0;
    background-image:
      linear-gradient(rgba(68,170,255,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(68,170,255,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
  }

  /* Bridge of glasses (center divider) */
  .bridge {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 32px; height: 8px;
    background: rgba(68,170,255,0.15);
    border-radius: 4px;
    z-index: 20;
  }

  /* ── HUD Elements ── */
  .hud-corner-tl, .hud-corner-tr, .hud-corner-bl, .hud-corner-br {
    position: absolute; font-size: 10px; color: var(--hud-dim);
    letter-spacing: 0.1em; padding: 10px 14px;
  }
  .hud-corner-tl { top: 0; left: 0; }
  .hud-corner-tr { top: 0; right: 0; text-align: right; }
  .hud-corner-bl { bottom: 0; left: 0; }
  .hud-corner-br { bottom: 0; right: 0; text-align: right; }

  /* Status bar */
  .status-bar {
    position: absolute; bottom: 14px; left: 50%; transform: translateX(-50%);
    display: flex; gap: 20px; align-items: center;
    font-size: 10px; color: var(--hud-dim); letter-spacing: 0.12em;
  }
  .status-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--hud-green); animation: pulse-dot 2s infinite;
  }

  /* ── Overlays ── */

  /* M0 STOP overlay */
  .overlay-stop {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    pointer-events: none; opacity: 0; transition: opacity 0.15s;
    z-index: 10;
  }
  .overlay-stop.active { opacity: 1; }
  .stop-ring {
    width: 140px; height: 140px; border-radius: 50%;
    border: 4px solid var(--hud-red);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 40px rgba(255,51,68,0.5), inset 0 0 30px rgba(255,51,68,0.15);
    animation: stop-pulse 0.4s ease-out;
  }
  .stop-text {
    color: var(--hud-red); font-size: 32px; font-weight: 700;
    letter-spacing: 0.1em; text-shadow: 0 0 20px rgba(255,51,68,0.8);
  }

  /* M0 PATH arrow */
  .overlay-path {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    pointer-events: none; opacity: 0; transition: opacity 0.3s;
    z-index: 9;
  }
  .overlay-path.active { opacity: 1; }
  .path-arrow {
    position: relative; display: flex; flex-direction: column; align-items: center; gap: 8px;
  }
  .arrow-body {
    width: 8px; height: 120px;
    background: linear-gradient(180deg, var(--hud-green), rgba(0,255,136,0.3));
    border-radius: 4px;
    box-shadow: 0 0 20px rgba(0,255,136,0.6);
    animation: arrow-flow 1.2s ease-in-out infinite;
  }
  .arrow-head {
    width: 0; height: 0;
    border-left: 20px solid transparent;
    border-right: 20px solid transparent;
    border-bottom: 36px solid var(--hud-green);
    filter: drop-shadow(0 0 12px rgba(0,255,136,0.8));
    order: -1;
  }
  .distance-tag {
    position: absolute; right: -80px; top: 50%;
    transform: translateY(-50%);
    background: rgba(0,255,136,0.12); border: 1px solid rgba(0,255,136,0.4);
    border-radius: 6px; padding: 4px 10px;
    font-size: 11px; color: var(--hud-green); white-space: nowrap;
  }

  /* Danger zone overlay */
  .overlay-danger {
    position: absolute; left: 0; top: 0; bottom: 0; width: 45%;
    pointer-events: none; opacity: 0; transition: opacity 0.25s;
    z-index: 8;
  }
  .overlay-danger.active { opacity: 1; }
  .danger-fill {
    position: absolute; inset: 0;
    background: repeating-linear-gradient(
      45deg, rgba(255,51,68,0.08) 0px, rgba(255,51,68,0.08) 8px,
      transparent 8px, transparent 16px);
    border-right: 2px solid rgba(255,51,68,0.5);
    animation: danger-flicker 2s infinite;
  }
  .danger-label {
    position: absolute; top: 30px; left: 20px;
    background: rgba(255,51,68,0.15); border: 1px solid rgba(255,51,68,0.5);
    border-radius: 4px; padding: 3px 8px;
    font-size: 9px; color: var(--hud-red); letter-spacing: 0.15em;
    text-transform: uppercase;
  }

  /* Voice message overlay */
  .overlay-voice {
    position: absolute; bottom: 48px; left: 50%; transform: translateX(-50%);
    pointer-events: none; opacity: 0; transition: opacity 0.2s;
    z-index: 15; white-space: nowrap;
  }
  .overlay-voice.active { opacity: 1; }
  .voice-bubble {
    background: rgba(5,8,16,0.88); border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px; padding: 8px 18px;
    font-size: 15px; color: var(--hud-white); letter-spacing: 0.04em;
    box-shadow: 0 4px 20px rgba(0,0,0,0.6);
  }

  /* Haptic indicator */
  .haptic-indicator {
    position: absolute; top: 14px; right: 14px;
    width: 28px; height: 28px; border-radius: 50%;
    border: 2px solid transparent; font-size: 14px;
    display: flex; align-items: center; justify-content: center;
    opacity: 0; transition: opacity 0.2s; z-index: 16;
  }
  .haptic-indicator.active { opacity: 1; }
  .haptic-indicator.sharp_stop { border-color: var(--hud-red); animation: haptic-stop 0.3s ease-out; }
  .haptic-indicator.directional_pulse { border-color: var(--hud-green); animation: haptic-pulse 0.8s infinite; }
  .haptic-indicator.warning_pulse { border-color: var(--hud-amber); animation: haptic-pulse 0.5s infinite; }

  /* ── M1 Cultural Bridge overlay (subtle, daily domain) ── */
  .overlay-cultural {
    position: absolute; top: 16px; left: 16px; right: 16px;
    pointer-events: none; opacity: 0; transition: opacity 0.4s;
    z-index: 12;
  }
  .overlay-cultural.active { opacity: 1; }
  .cultural-card {
    background: rgba(5,8,16,0.82);
    border-left: 3px solid var(--hud-amber);
    border-radius: 0 8px 8px 0;
    padding: 10px 14px; max-width: 340px;
  }
  .cultural-label {
    font-size: 9px; color: var(--hud-amber); letter-spacing: 0.18em;
    text-transform: uppercase; margin-bottom: 4px;
  }
  .cultural-main { font-size: 12px; color: var(--hud-white); line-height: 1.5; }
  .cultural-sub  { font-size: 10px; color: var(--hud-dim); margin-top: 4px; line-height: 1.4; }
  .schema-map {
    display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 10px;
  }
  .schema-tag {
    background: rgba(255,170,0,0.12); border: 1px solid rgba(255,170,0,0.3);
    border-radius: 4px; padding: 2px 7px; color: var(--hud-amber);
  }
  .schema-arrow { color: var(--hud-dim); }

  /* ── M2 Deep Translation (medical) ── */
  .overlay-translation {
    position: absolute; top: 16px; right: 16px;
    pointer-events: none; opacity: 0; transition: opacity 0.4s;
    z-index: 12; max-width: 280px;
  }
  .overlay-translation.active { opacity: 1; }
  .translation-card {
    background: rgba(5,8,16,0.84);
    border-left: 3px solid var(--hud-blue);
    border-radius: 0 8px 8px 0; padding: 10px 14px;
  }
  .translation-label { font-size: 9px; color: var(--hud-blue); letter-spacing: 0.18em;
    text-transform: uppercase; margin-bottom: 6px; }
  .translation-row { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px; font-size: 11px; }
  .tcm-term { color: var(--hud-amber); font-weight: 600; min-width: 100px; }
  .bio-equiv { color: var(--hud-white); line-height: 1.4; }

  /* M-level badge */
  .m-badge {
    position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
    font-size: 10px; letter-spacing: 0.15em; padding: 3px 12px;
    border-radius: 12px; font-weight: 700; opacity: 0;
    transition: opacity 0.3s; z-index: 20;
  }
  .m-badge.active { opacity: 1; }
  .m-badge.M0 { background: rgba(255,51,68,0.15); border: 1px solid var(--hud-red);
                 color: var(--hud-red); }
  .m-badge.M1 { background: rgba(255,170,0,0.12); border: 1px solid var(--hud-amber);
                 color: var(--hud-amber); }
  .m-badge.M2 { background: rgba(68,170,255,0.10); border: 1px solid var(--hud-blue);
                 color: var(--hud-blue); }

  /* ── Controls ── */
  .controls {
    margin-top: 24px; display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;
  }
  .btn {
    padding: 10px 22px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.05); color: var(--hud-white);
    font-family: inherit; font-size: 12px; letter-spacing: 0.08em; cursor: pointer;
    transition: all 0.2s;
  }
  .btn:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.25); }
  .btn.emergency { border-color: rgba(255,51,68,0.5); color: var(--hud-red); }
  .btn.daily     { border-color: rgba(255,170,0,0.5); color: var(--hud-amber); }
  .btn.medical   { border-color: rgba(68,170,255,0.5); color: var(--hud-blue); }
  .btn.reset     { border-color: rgba(255,255,255,0.08); color: var(--hud-dim); }

  /* ── Info panel ── */
  .info-panel {
    margin-top: 20px; width: 780px;
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; padding: 14px 20px;
    font-size: 11px; color: var(--hud-dim); line-height: 1.7;
  }
  .info-panel strong { color: var(--hud-white); }
  .info-row { display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 6px; }
  .info-item { display: flex; gap: 6px; }
  .info-key { color: rgba(255,255,255,0.25); }

  /* ── Animations ── */
  @keyframes pulse-dot { 0%,100%{opacity:1}50%{opacity:0.3} }
  @keyframes stop-pulse { from{transform:scale(1.3);opacity:0.5} to{transform:scale(1);opacity:1} }
  @keyframes arrow-flow { 0%,100%{opacity:1} 50%{opacity:0.6} }
  @keyframes danger-flicker { 0%,100%{opacity:1} 50%{opacity:0.7} }
  @keyframes haptic-stop { 0%{transform:scale(1.4)} 100%{transform:scale(1)} }
  @keyframes haptic-pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.2)} }
</style>
</head>
<body>
<h1>⬡ TAAA — AR Glasses Simulation</h1>

<div class="glasses-frame" id="glassesFrame">
  <div class="env-bg"></div>
  <div class="env-lines"></div>
  <div class="bridge"></div>

  <!-- HUD corners -->
  <div class="hud-corner-tl" id="cornerTL">TAAA v0.4<br>SIM MODE</div>
  <div class="hud-corner-tr" id="cornerTR">M-LEVEL: —</div>
  <div class="hud-corner-bl" id="cornerBL">SCHEMA: IDLE</div>
  <div class="hud-corner-br" id="cornerBR"></div>

  <!-- M-level badge -->
  <div class="m-badge" id="mBadge">M0</div>

  <!-- Haptic indicator -->
  <div class="haptic-indicator" id="hapticInd">⚡</div>

  <!-- Danger zone (left side = wrong direction) -->
  <div class="overlay-danger" id="overlayDanger">
    <div class="danger-fill"></div>
    <div class="danger-label">⚠ Pericolo</div>
  </div>

  <!-- STOP ring -->
  <div class="overlay-stop" id="overlayStop">
    <div class="stop-ring">
      <div class="stop-text">STOP</div>
    </div>
  </div>

  <!-- SAFE PATH arrow -->
  <div class="overlay-path" id="overlayPath">
    <div class="path-arrow">
      <div class="arrow-head"></div>
      <div class="arrow-body"></div>
      <div class="distance-tag" id="distanceTag">Uscita 8m →</div>
    </div>
  </div>

  <!-- Voice bubble -->
  <div class="overlay-voice" id="overlayVoice">
    <div class="voice-bubble" id="voiceBubble">…</div>
  </div>

  <!-- M1 Cultural Bridge (daily domain) -->
  <div class="overlay-cultural" id="overlayCultural">
    <div class="cultural-card">
      <div class="cultural-label" id="culturalLabel">Schema Gap — M1</div>
      <div class="cultural-main" id="culturalMain">…</div>
      <div class="cultural-sub" id="culturalSub">…</div>
      <div class="schema-map" id="schemaMap">
        <div class="schema-tag" id="schemaFrom">schema A</div>
        <div class="schema-arrow">→</div>
        <div class="schema-tag" id="schemaTo">schema B</div>
      </div>
    </div>
  </div>

  <!-- M2 Deep Translation (medical) -->
  <div class="overlay-translation" id="overlayTranslation">
    <div class="translation-card">
      <div class="translation-label">Schema Translation — M2</div>
      <div id="translationRows"></div>
    </div>
  </div>

  <!-- Status bar -->
  <div class="status-bar">
    <div class="status-dot"></div>
    <span id="statusText">In attesa — seleziona uno scenario</span>
  </div>
</div>

<div class="controls">
  <button class="btn emergency" onclick="runScenario('shinjuku')">
    🚨 Scenario 1 — Shinjuku (M0 Emergenza)
  </button>
  <button class="btn daily" onclick="runScenario('negotiation')">
    🤝 Scenario 2 — David / Tanaka (M1 Quotidiano)
  </button>
  <button class="btn medical" onclick="runScenario('medical')">
    🏥 Scenario 3 — Lin Mei / Dr. Chen (M2 Medico)
  </button>
  <button class="btn reset" onclick="resetAll()">
    ○ Reset
  </button>
</div>

<div class="info-panel" id="infoPanel">
  <div style="color:rgba(255,255,255,0.4);margin-bottom:8px;font-size:10px;letter-spacing:0.12em">
    PIPELINE OUTPUT
  </div>
  <div class="info-row" id="infoRow">
    <span style="color:rgba(255,255,255,0.2)">Seleziona uno scenario per vedere l'output del pipeline TAAA</span>
  </div>
</div>

<script>
// ── Scenario Definitions ──────────────────────────────────────────────────────
const SCENARIOS = {
  shinjuku: {
    label: "Shinjuku — Emergenza Incendio",
    domain: "EMERGENCY",
    mLevel: "M0",
    gap: "INTERFERENCE",
    steps: [
      {
        delay: 0,
        action: () => {
          setStatus("Mark (US) in stazione Shinjuku — rilevazione schema attivo...");
          setInfo("domain","EMERGENCY","gap","INTERFERENCE (conf=0.72)",
                  "schema_attivo","Uscita = direzione opposta al flusso (schema US)",
                  "stress","0.82 | HRV=22ms");
          setMBadge("M0");
          setCorners("TAAA EMERGENZA","M0 ACTIVE","SCHEMA: INTERFERENZA","stress: 0.82");
        }
      },
      {
        delay: 1000,
        action: () => {
          setStatus("Interferenza attiva: Mark si gira verso uscita SBAGLIATA");
          showDanger();
        }
      },
      {
        delay: 2200,
        action: () => {
          setStatus("⛔ INTERRUZIONE CALIBRATA — segnale aptico pre-verbale");
          showStop();
          showHaptic("sharp_stop");
          speak("STOP");
        }
      },
      {
        delay: 3400,
        action: () => {
          setStatus("✓ Schema interrotto — redirect AR verso uscita corretta");
          hideStop();
          showPath("Uscita 8m →");
          speak("Fermati. Segui la freccia verde.");
        }
      },
      {
        delay: 6000,
        action: () => {
          setStatus("✓ Percorso sicuro — canale M0, nessuna traduzione culturale");
          hideVoice();
        }
      }
    ]
  },

  negotiation: {
    label: "David / Tanaka — Negoziazione (Dominio Quotidiano)",
    domain: "DAILY",
    mLevel: "M1",
    steps: [
      {
        delay: 0,
        action: () => {
          setStatus("David (US) / Tanaka-san (JP) — rilevazione gap schema silenZIO");
          setInfo("domain","DAILY","gap","INTERFERENCE (conf=0.72)",
                  "M1_risk","HIGH 0.83 — 5 dimensioni conflitto",
                  "schema","silence_as_absence vs silence_as_respect");
          setMBadge("M1");
          setCorners("TAAA QUOTIDIANO","M1 CULTURAL","SCHEMA: GAP SILENZIO","stress: 0.15");
        }
      },
      {
        delay: 1200,
        action: () => {
          setStatus("Gap M1 rilevato: silenzio interpretato come assenza (schema US)");
        }
      },
      {
        delay: 2000,
        action: () => {
          setStatus("Cultural Bridge attivato — overlay sottile sugli occhiali di David");
          showCultural(
            "SCHEMA GAP — COMUNICAZIONE",
            "Il 'sì' di Tanaka = «Ho capito la tua proposta»",
            "Il silenzio = spazio rispettoso prima di una risposta indiretta.",
            "silence_as_absence",
            "silence_as_respect"
          );
          speak("Aspetta. Il silenzio è risposta.");
        }
      },
      {
        delay: 5500,
        action: () => {
          setStatus("Bridge attivo — David vede il contesto, Tanaka mantiene il proprio schema");
          hideVoice();
        }
      }
    ]
  },

  medical: {
    label: "Lin Mei / Dr. Chen — Consulto Medico (M2)",
    domain: "DAILY",
    mLevel: "M2",
    steps: [
      {
        delay: 0,
        action: () => {
          setStatus("Lin Mei descrive sintomi in medicina tradizionale cinese (MTC)");
          setInfo("domain","DAILY","gap","PARTIAL (conf=0.68)",
                  "schema","MTC vs Biomedicina — ontologie incompatibili",
                  "m2","topologia personale Dr. Chen in costruzione");
          setMBadge("M2");
          setCorners("TAAA QUOTIDIANO","M2 TRANSLATION","SCHEMA: ONTOLOGICO","stress: 0.20");
        }
      },
      {
        delay: 1400,
        action: () => {
          setStatus("Gap ontologico: due sistemi incompatibili per descrivere il corpo");
        }
      },
      {
        delay: 2200,
        action: () => {
          setStatus("Deep Translation M2 — mappatura MTC → biomedicina sugli occhiali del medico");
          showTranslation([
            ["Fuoco nel fegato", "Possibile: infiammazione epatica, transaminasi elevate"],
            ["Energia bloccata", "Possibile: ostruzione biliare, dolore addominale cronico"],
            ["Troppo calore", "Possibile: stato febbrile, processo infiammatorio sistemico"],
          ]);
          speak("Correlati biomedicali disponibili.");
        }
      },
      {
        delay: 5500,
        action: () => {
          setStatus("Traduzione bidirezionale — entrambi gli schemi preservati");
          hideVoice();
        }
      }
    ]
  }
};

// ── State ─────────────────────────────────────────────────────────────────────
let _timers = [];
let _activeOverlays = [];

function clearTimers() { _timers.forEach(clearTimeout); _timers = []; }
function later(fn, ms) { _timers.push(setTimeout(fn, ms)); }

// ── Run scenario ──────────────────────────────────────────────────────────────
function runScenario(name) {
  resetAll(false);
  const s = SCENARIOS[name];
  if (!s) return;
  document.getElementById('infoPanel').style.borderColor = 'rgba(255,255,255,0.06)';
  s.steps.forEach(step => later(step.action, step.delay));
}

// ── Overlay controls ──────────────────────────────────────────────────────────
function show(id, cls='') {
  const el = document.getElementById(id);
  el.classList.add('active');
  if (cls) el.classList.add(cls);
  _activeOverlays.push({id, cls});
}
function hide(id, cls='') {
  const el = document.getElementById(id);
  el.classList.remove('active');
  if (cls) el.classList.remove(cls);
}

function showStop()    { show('overlayStop'); }
function hideStop()    { hide('overlayStop'); }
function showDanger()  { show('overlayDanger'); }
function hideDanger()  { hide('overlayDanger'); }

function showPath(label) {
  document.getElementById('distanceTag').textContent = label;
  show('overlayPath');
  hideDanger();
}

function showHaptic(pattern) {
  const el = document.getElementById('hapticInd');
  el.className = 'haptic-indicator active ' + pattern;
  el.textContent = pattern === 'sharp_stop' ? '⚡' : '〜';
  later(() => hide('hapticInd', pattern), 2000);
}

function speak(msg) {
  document.getElementById('voiceBubble').textContent = msg;
  show('overlayVoice');
  later(() => hide('overlayVoice'), 3500);
}

function showCultural(label, main, sub, from, to) {
  document.getElementById('culturalLabel').textContent = label;
  document.getElementById('culturalMain').textContent = main;
  document.getElementById('culturalSub').textContent = sub;
  document.getElementById('schemaFrom').textContent = from;
  document.getElementById('schemaTo').textContent = to;
  show('overlayCultural');
}

function showTranslation(rows) {
  const container = document.getElementById('translationRows');
  container.innerHTML = rows.map(([tcm, bio]) =>
    `<div class="translation-row">
       <div class="tcm-term">${tcm}</div>
       <div class="bio-equiv">${bio}</div>
     </div>`
  ).join('');
  show('overlayTranslation');
}

function hideVoice() { hide('overlayVoice'); }

function setMBadge(level) {
  const el = document.getElementById('mBadge');
  el.className = 'active m-badge ' + level;
  el.textContent = level;
}

function setStatus(msg) {
  document.getElementById('statusText').textContent = msg;
}

function setCorners(tl, tr, bl, br) {
  document.getElementById('cornerTL').innerHTML = tl;
  document.getElementById('cornerTR').innerHTML = tr;
  document.getElementById('cornerBL').innerHTML = bl;
  document.getElementById('cornerBR').innerHTML = br;
}

function setInfo(...pairs) {
  const row = document.getElementById('infoRow');
  const items = [];
  for (let i = 0; i < pairs.length; i += 2) {
    items.push(`<div class="info-item">
      <span class="info-key">${pairs[i]}:</span>
      <strong>${pairs[i+1]}</strong>
    </div>`);
  }
  row.innerHTML = items.join('');
}

function resetAll(full=true) {
  clearTimers();
  ['overlayStop','overlayPath','overlayDanger','overlayVoice',
   'overlayCultural','overlayTranslation','hapticInd','mBadge'].forEach(id => {
    const el = document.getElementById(id);
    el.className = el.className.replace(/\bactive\b/g,'').replace(/\bM[012]\b/g,'').trim();
  });
  if (full) {
    setStatus("In attesa — seleziona uno scenario");
    setCorners("TAAA v0.4","M-LEVEL: —","SCHEMA: IDLE","");
    document.getElementById('infoRow').innerHTML =
      '<span style="color:rgba(255,255,255,0.2)">Seleziona uno scenario per vedere l\'output del pipeline TAAA</span>';
  }
}
</script>
</body>
</html>"""


def register_ar_routes(app: Flask, agent):
    """Register AR display routes on an existing Flask app."""

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

    return app
