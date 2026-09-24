/* QuantPlay Pyodide worker — runs the Python trainer (pokerbot.web.six_server via browser_bridge) in a
   Web Worker so the table stays responsive. Boot: Pyodide from the jsDelivr CDN -> the pure-Python deps
   (pydantic & co. from Pyodide's own repo, fastapi/starlette/treys as vendored wheels) -> the trainer
   bundle (pokerbot/ + knowledge files, one zip) -> import. Then every message {id, method, path, body}
   is answered with {id, status, body} from browser_bridge.dispatch — no HTTP anywhere. */
'use strict';
const PYODIDE_VERSION = '0.28.3';
const CDN = 'https://cdn.jsdelivr.net/pyodide/v' + PYODIDE_VERSION + '/full/';
const PYODIDE_PACKAGES = ['micropip', 'pydantic', 'anyio', 'sniffio', 'idna', 'typing-extensions', 'annotated-types'];
const VENDORED_WHEELS = ['annotated_doc-0.0.5-py3-none-any.whl', 'fastapi-0.141.1-py3-none-any.whl', 'starlette-1.7.0-py3-none-any.whl', 'treys-0.1.8-py3-none-any.whl', 'typing_inspection-0.4.4-py3-none-any.whl'];
const BUNDLE = 'pokerbot_bundle.zip';

let dispatch = null;          // PyProxy of browser_bridge.dispatch once booted
const queue = [];             // requests that arrive before boot finishes

function post(type, extra) { self.postMessage(Object.assign({ type }, extra || {})); }
function progress(stage, text) { post('progress', { stage, text }); }

async function boot(build, base) {
  progress('pyodide', 'Lade Python-Laufzeit (WebAssembly, ~10 MB, einmalig) …');
  importScripts(CDN + 'pyodide.js');
  const py = await loadPyodide({ indexURL: CDN });
  progress('packages', 'Lade Bibliotheken …');
  await py.loadPackage(PYODIDE_PACKAGES, { messageCallback: () => {} });
  progress('wheels', 'Installiere Web-Framework (pydantic-Modelle) …');
  const micropip = py.pyimport('micropip');
  // deps=false: every dependency is either in PYODIDE_PACKAGES or vendored — no PyPI round-trip at boot
  await micropip.install.callKwargs(VENDORED_WHEELS.map((w) => base + 'wheels/' + w), { deps: false });
  progress('bundle', 'Lade Poker-Engine und Wissensbasis …');
  const resp = await fetch(base + BUNDLE + '?v=' + build);
  if (!resp.ok) throw new Error('Bundle-Download fehlgeschlagen: HTTP ' + resp.status);
  py.FS.mkdir('/app');
  py.unpackArchive(await resp.arrayBuffer(), 'zip', { extractDir: '/app' });
  progress('import', 'Starte Trainer …');
  py.runPython([
    'import sys, os',
    'sys.path.insert(0, "/app")',
    'os.chdir("/app")',
    'from pokerbot.web import browser_bridge',
    'dispatch = browser_bridge.dispatch',
  ].join('\n'));
  dispatch = py.globals.get('dispatch');
  post('ready');
  while (queue.length) handle(queue.shift());
}

function handle(m) {
  let status = 500, body = JSON.stringify({ error: 'unbekannter Fehler' });
  try {
    const out = JSON.parse(dispatch(m.method, m.path, m.body));
    status = out.status; body = out.body;
  } catch (e) {
    body = JSON.stringify({ error: 'Python-Fehler: ' + String(e).slice(0, 600) });
  }
  post('reply', { id: m.id, status, body });
}

self.onmessage = (ev) => {
  const m = ev.data || {};
  if (m.type === 'boot') {
    boot(m.build, m.base).catch((e) => post('fatal', { text: String(e && e.stack ? e.stack : e).slice(0, 1200) }));
  } else if (m.type === 'request') {
    if (dispatch) handle(m); else queue.push(m);
  }
};
