/* QuantPlay browser bridge — makes the trainer's `fetch('/api/...')` calls run on the VISITOR's machine.
   Loaded first in <head> (web/build.py injects it), so it replaces window.fetch before the page's own
   script runs. Every /api/* request is posted to the Pyodide worker (worker.js), which runs the identical
   Python trainer; the answer is wrapped in a real Response, so training.html needs no change.
   Everything else (images, other origins) goes to the native fetch. */
(function () {
  'use strict';
  const BUILD = (window.QP_BUILD && window.QP_BUILD.v) || 'dev';
  const nativeFetch = window.fetch.bind(window);
  const pending = new Map();
  let nextId = 1;
  let readyResolve, readyReject;
  const ready = new Promise((res, rej) => { readyResolve = res; readyReject = rej; });
  let failed = null;

  /* ── loading overlay: the engine (~14 MB once, cached afterwards) needs a few seconds ── */
  const overlay = document.createElement('div');
  overlay.id = 'qp-boot';
  overlay.innerHTML =
    '<style>#qp-boot{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;' +
    'background:radial-gradient(ellipse at 50% 30%,#0a1020,#060a14);color:#eaf2ff;font-family:"Segoe UI",system-ui,sans-serif}' +
    '#qp-boot .box{max-width:560px;padding:32px 40px;border:1px solid #1a2740;border-radius:16px;background:#0f1830;text-align:center}' +
    '#qp-boot h1{margin:0 0 6px;font-size:26px;color:#f0c860}#qp-boot .sub{color:#8aa0b8;font-size:14px;margin-bottom:18px}' +
    '#qp-boot .bar{height:6px;background:#1a2740;border-radius:3px;overflow:hidden;margin:14px 0}' +
    '#qp-boot .bar i{display:block;height:100%;width:0;background:#37e0c8;transition:width .4s}' +
    '#qp-boot .msg{font-size:14px;min-height:20px}#qp-boot .err{color:#ff5d52;white-space:pre-wrap;text-align:left;font-size:12px;margin-top:12px}' +
    '#qp-boot a{color:#37e0c8}</style>' +
    '<div class="box"><h1>♠ QuantPlay</h1><div class="sub">6-max No-Limit Hold\'em Trainer — läuft komplett in deinem Browser, ' +
    'kein Server, keine Daten verlassen deinen Rechner.</div>' +
    '<div class="bar"><i id="qp-bar"></i></div><div class="msg" id="qp-msg">Starte …</div><div class="err" id="qp-err"></div></div>';
  const STAGES = { pyodide: 25, packages: 55, wheels: 70, bundle: 85, import: 95, ready: 100 };
  function progress(stage, text) {
    const bar = document.getElementById('qp-bar'), msg = document.getElementById('qp-msg');
    if (bar && STAGES[stage] != null) bar.style.width = STAGES[stage] + '%';
    if (msg && text) msg.textContent = text;
  }
  function showError(text) {
    failed = text;
    const err = document.getElementById('qp-err');
    if (err) err.textContent = 'Fehler beim Start:\n' + text + '\n\nSeite neu laden hilft meist. Der Trainer braucht einen ' +
      'aktuellen Browser (WebAssembly + Web Worker).';
    readyReject(new Error(text));
  }
  function mountOverlay() { if (!document.getElementById('qp-boot')) document.body.appendChild(overlay); }
  if (document.body) mountOverlay(); else document.addEventListener('DOMContentLoaded', mountOverlay);

  /* ── the worker: one Python interpreter per tab ── */
  const worker = new Worker('worker.js?v=' + BUILD);
  worker.onmessage = (ev) => {
    const m = ev.data || {};
    if (m.type === 'progress') { progress(m.stage, m.text); return; }
    if (m.type === 'ready') {
      progress('ready', 'Bereit.');
      readyResolve();
      setTimeout(() => overlay.remove(), 250);
      return;
    }
    if (m.type === 'fatal') { showError(m.text); return; }
    if (m.type === 'reply') {
      const p = pending.get(m.id);
      if (!p) return;
      pending.delete(m.id);
      p.resolve(m);
    }
  };
  worker.onerror = (ev) => showError(String(ev.message || ev));
  worker.postMessage({ type: 'boot', build: BUILD, base: location.href.replace(/[^/]*$/, '') });

  function call(method, path, body) {
    return new Promise((resolve) => {
      const id = nextId++;
      pending.set(id, { resolve });
      worker.postMessage({ type: 'request', id, method, path, body });
    });
  }

  window.fetch = async function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (!url.startsWith('/api/')) return nativeFetch(input, init);
    if (failed) return new Response(JSON.stringify({ error: 'Trainer nicht gestartet: ' + failed }),
      { status: 503, headers: { 'Content-Type': 'application/json' } });
    await ready;
    const method = ((init && init.method) || 'GET').toUpperCase();
    const body = init && init.body != null ? String(init.body) : null;
    const r = await call(method, url, body);
    return new Response(r.body, { status: r.status, headers: { 'Content-Type': 'application/json' } });
  };
})();
