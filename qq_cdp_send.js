/**
 * qq_cdp_send.js  -  CDP-based QQ chat-input sender (handle-precise)
 *
 * QQ's chat input is a Chromium-rendered DOM element with NO Win32 HWND, so the
 * classic "find Edit HWND + WM_SETTEXT" cannot work. This talks to QQ over the
 * Chrome DevTools Protocol instead: it locates the input element inside the
 * renderer, focuses it, and injects text via Input.insertText + Enter.
 *
 * PREREQUISITE: QQ must be launched with --remote-debugging-port=9222
 *   (use qq_remote_debug.ps1 -Launch AFTER fully exiting QQ).
 *
 * Modes:
 *   node qq_cdp_send.js probe                 # list targets + locate input (no send)
 *   node qq_cdp_send.js send                  # send payload_sample_30.txt (2s gap)
 *   node qq_cdp_send.js send <file> <ms> <urlFilter>
 *   node qq_cdp_send.js dry                   # list what WOULD be sent (no connection)
 *
 * Run with:  NODE_PATH=<workspace>/node_modules node qq_cdp_send.js probe
 */

const http = require('http');
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

const PORT = process.env.CDP_PORT || 9222;
const BASE = `http://127.0.0.1:${PORT}`;

function httpGet(p) {
  return new Promise((resolve, reject) => {
    http.get(BASE + p, (res) => {
      let d = '';
      res.on('data', (c) => (d += c));
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

class CDP {
  constructor(url) { this.ws = new WebSocket(url); this.id = 0; this.pending = new Map(); this.onEvent = null; }
  open() {
    return new Promise((resolve, reject) => {
      this.ws.on('open', resolve);
      this.ws.on('message', (m) => {
        const msg = JSON.parse(m);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) reject(new Error(msg.error.message)); else resolve(msg.result);
        } else if (msg.method && this.onEvent) {
          this.onEvent(msg);
        }
      });
      this.ws.on('error', reject);
    });
  }
  send(method, params) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params: params || {} }));
    });
  }
  async eval(expr) {
    const r = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return r && r.result ? r.result.value : undefined;
  }
  close() { try { this.ws.close(); } catch (e) {} }
}

// Focus the first visible editable element; returns a status string.
const FIND_INPUT = `(function(){
  function vis(el){return !!el && el.offsetParent!==null && el.offsetWidth>0 && el.offsetHeight>0;}
  var sels=['textarea','input[type=text]','input[type=search]','[contenteditable=true]','[contenteditable=""]','div[contenteditable]'];
  for(var i=0;i<sels.length;i++){
    var els=document.querySelectorAll(sels[i]);
    for(var j=0;j<els.length;j++){ if(vis(els[j])){ els[j].focus(); return 'FOUND|'+els[j].tagName+'|'+(els[j].className||''); } }
  }
  return 'NONE';
})()`;

const TARGETS = (async () => (await httpGet('/json')).filter((t) => t.type === 'page'));

async function probe() {
  let pages;
  try { pages = await TARGETS(); } catch (e) { console.log('Cannot connect to ' + BASE + ' — is QQ running with --remote-debugging-port=' + PORT + '?'); return; }
  console.log('=== Page targets: ' + pages.length + ' ===');
  pages.forEach((t) => console.log('  ' + (t.id || '').slice(0, 14) + '  ' + (t.url || '').slice(0, 90)));
  console.log('=== Probe input on each page ===');
  for (const t of pages) {
    try {
      const cdp = new CDP(t.webSocketDebuggerUrl);
      await cdp.open();
      await cdp.send('Runtime.enable');
      const r = await cdp.eval(FIND_INPUT);
      console.log('  ' + (t.url || '').slice(0, 50) + '  =>  ' + r);
      cdp.close();
    } catch (e) { console.log('  ' + (t.url || '').slice(0, 50) + '  =>  ERR ' + e.message); }
  }
}

async function send(file, delay, filter) {
  const payloads = fs.readFileSync(file, 'utf8').split('\n').map((s) => s.trim()).filter(Boolean);
  const pages = await TARGETS();
  let target = filter ? pages.find((t) => (t.url || '').includes(filter)) : null;
  if (!target) {
    for (const t of pages) {
      try {
        const cdp = new CDP(t.webSocketDebuggerUrl);
        await cdp.open();
        await cdp.send('Runtime.enable');
        const r = await cdp.eval(FIND_INPUT);
        cdp.close();
        if (r && r.startsWith('FOUND')) { target = t; console.log('Using target: ' + (t.url || '').slice(0, 60) + ' (' + r + ')'); break; }
      } catch (e) {}
    }
  }
  if (!target) { console.log('No target with an editable input found. Run probe first.'); process.exit(1); }

  const cdp = new CDP(target.webSocketDebuggerUrl);
  await cdp.open();
  await cdp.send('Runtime.enable');
  await cdp.send('Input.enable');
  await cdp.eval(FIND_INPUT); // focus

  for (let i = 0; i < payloads.length; i++) {
    const p = payloads[i];
    console.log('[' + i + '] inserting: ' + p.slice(0, 70));
    await cdp.send('Input.insertText', { text: p });
    await new Promise((r) => setTimeout(r, 350));
    await cdp.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', windowsVirtualKeyCode: 13, key: 'Enter', code: 'Enter' });
    await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', windowsVirtualKeyCode: 13, key: 'Enter', code: 'Enter' });
    await new Promise((r) => setTimeout(r, delay));
  }
  cdp.close();
  console.log('Done. Sent ' + payloads.length + ' payloads via CDP.');
}

const mode = process.argv[2] || 'probe';
const file = process.argv[3] || path.join(__dirname, 'payload_sample_30.txt');
const delay = parseInt(process.argv[4] || '2000', 10);
const filter = process.argv[5] || '';

if (mode === 'probe') {
  probe().catch((e) => { console.error(e); process.exit(1); });
} else if (mode === 'send') {
  send(file, delay, filter).catch((e) => { console.error(e); process.exit(1); });
} else if (mode === 'dry') {
  const payloads = fs.readFileSync(file, 'utf8').split('\n').map((s) => s.trim()).filter(Boolean);
  console.log('Would send ' + payloads.length + ' payloads from ' + file + ':');
  payloads.forEach((p, i) => console.log('  [' + i + '] ' + p.slice(0, 80)));
} else {
  console.log('Usage: node qq_cdp_send.js probe|send|dry [file] [delayMs] [urlFilter]');
}
