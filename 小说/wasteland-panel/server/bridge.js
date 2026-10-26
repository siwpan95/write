#!/usr/bin/env node
/**
 * bridge.js — Node 侧 HTTP 桥
 *
 * 职责：
 *   1. 零依赖 http 服务，托管 web/ 静态资源
 *   2. 以子进程拉起 engine/rpc_server.py，转发 JSON-RPC（stdio）
 *   3. /api/<method> POST 透传到引擎，GET /api/bootstrap 拉初始数据
 *   4. 首次启动自动跑 bible_parser.py 刷新数据层
 *
 * 零三方依赖：只用 node:http / node:fs / node:path / node:child_process。
 */

'use strict';

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');

// --------------------------------------------------------------------------
// 路径与配置
// --------------------------------------------------------------------------

const ROOT = path.resolve(__dirname, '..');
const ENGINE = path.join(ROOT, 'engine');
const WEB = path.join(ROOT, 'web');
const DATA = path.join(ENGINE, 'data', 'dataset.json');
const RPC = path.join(ENGINE, 'rpc_server.py');
const PARSER = path.join(ENGINE, 'bible_parser.py');

const PORT = Number(process.env.PORT || 8777);
const HOST = process.env.HOST || '127.0.0.1';

/**
 * 定位 Python 解释器。
 *
 * 注意：这里**不做 spawnSync 版本探测**。在受限沙箱里 spawnSync 会返回
 * EBUSY（文件被占用）而误判成"找不到解释器"，导致服务根本起不来。
 * 改为「文件存在性检查 + 真正 spawn 引擎后由引擎自报版本」。
 */
function findPython() {
  const cands = [
    process.env.PYTHON,
    'C:\\Users\\Administrator\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe',
    'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe',
  ].filter(Boolean);
  for (const c of cands) {
    try { if (fs.existsSync(c)) return { cmd: c, version: '?' }; } catch { /* 试下一个 */ }
  }
  // 退回 PATH 上的命令（可能是 python / python3，或 WindowsApps 别名）
  for (const name of ['python', 'python3', 'py']) {
    return { cmd: name, version: '?' };   // 交给 spawn 决定成败
  }
  return null;
}

const PY = findPython();
if (!PY) {
  console.error('[FATAL] 找不到可用的 Python 解释器。请设置环境变量 PYTHON 指向 python.exe');
  process.exit(1);
}
console.log(`[bridge] Python: ${PY.cmd} (${PY.version})`);

// --------------------------------------------------------------------------
// 数据层：不存在则先解析
// --------------------------------------------------------------------------

function ensureDataset() {
  // 数据层不存在 → 必须先解析
  if (!fs.existsSync(DATA)) return runParser(true);
  // 已存在则比较源文件时间戳
  let srcNewest = 0;
  for (const rel of [
    'C:\\Users\\Administrator\\Desktop\\小说\\bible\\world-bible.md',
    'C:\\Users\\Administrator\\Desktop\\小说\\bible\\plot-board.md',
    'C:\\Users\\Administrator\\Desktop\\小说\\一致性核查\\世界观设定标尺.md',
  ]) {
    try { srcNewest = Math.max(srcNewest, fs.statSync(rel).mtimeMs); } catch { /* 源缺失则跳过 */ }
  }
  const fresh = fs.statSync(DATA).mtimeMs;
  if (fresh >= srcNewest) {
    console.log('[bridge] 数据层已是最新');
    return;
  }
  return runParser(false);
}

function runParser(force) {
  console.log(`[bridge] ${force ? '数据层缺失' : '源文件已更新'}，正在解析 bible …`);
  try {
    const r = spawnSync(PY.cmd, [PARSER], { encoding: 'utf8', cwd: ENGINE, timeout: 60000 });
    const out = (r.stdout || '') + (r.stderr || '');
    const m = out.match(/ok=(\d+)\s+degraded=(\d+)\s+failed=(\d+)/);
    if (m) console.log(`[bridge] 解析完成 ok=${m[1]} degraded=${m[2]} failed=${m[3]}`);
    else console.log('[bridge] 解析器输出：\n' + out.split('\n').slice(-6).join('\n'));
  } catch (e) {
    // 沙箱下 spawnSync 可能被拦；不致命，引擎启动时会报真实错误
    console.warn('[bridge] 解析器无法执行（' + e.message + '），将由引擎启动时报错');
  }
}

// --------------------------------------------------------------------------
// RPC 子进程管理
// --------------------------------------------------------------------------

let child = null;
let rpcReady = false;
let seq = 0;
const pending = new Map();

function startEngine() {
  if (child) return;
  console.log('[bridge] 启动引擎子进程 …');
  child = spawn(PY.cmd, [RPC], {
    cwd: ENGINE,
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true,
  });

  let buf = '';
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', (chunk) => {
    buf += chunk;
    let idx;
    while ((idx = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line) continue;
      let msg;
      try { msg = JSON.parse(line); } catch { continue; }
      if (msg.id != null && pending.has(msg.id)) {
        const { resolve } = pending.get(msg.id);
        pending.delete(msg.id);
        resolve(msg);
      }
    }
  });

  child.stderr.setEncoding('utf8');
  child.stderr.on('data', (d) => {
    String(d).split('\n').filter(Boolean).forEach((l) => console.log('[engine] ' + l));
  });

  child.on('exit', (code) => {
    console.log(`[bridge] 引擎退出 code=${code}`);
    child = null;
    rpcReady = false;
    for (const { reject } of pending.values()) {
      reject(new Error('引擎进程已退出'));
    }
    pending.clear();
  });

  child.on('error', (e) => {
    console.error('[bridge] 引擎启动失败:', e.message);
  });

  // 探测就绪
  rpc('selfcheck', {}).then(() => { rpcReady = true; console.log('[bridge] 引擎就绪'); })
    .catch((e) => console.error('[bridge] 就绪探测失败:', e.message));
}

function rpc(method, params) {
  return new Promise((resolve, reject) => {
    if (!child) startEngine();
    if (!child) return reject(new Error('引擎未启动'));
    const id = ++seq;
    pending.set(id, { resolve, reject });
    const timer = setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error(`RPC 超时: ${method}`)); }
    }, 30000);
    const wrapped = { resolve: (v) => { clearTimeout(timer); resolve(v); },
                      reject: (e) => { clearTimeout(timer); reject(e); } };
    pending.set(id, wrapped);
    try {
      child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    } catch (e) {
      clearTimeout(timer);
      pending.delete(id);
      reject(e);
    }
  });
}

// --------------------------------------------------------------------------
// HTTP
// --------------------------------------------------------------------------

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.md': 'text/markdown; charset=utf-8',
};

function sendJSON(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function serveStatic(req, res, urlPath) {
  let rel = urlPath === '/' ? '/index.html' : urlPath;
  rel = decodeURIComponent(rel.split('?')[0]);
  const file = path.join(WEB, path.normalize(rel).replace(/^([/\\])+/, ''));
  if (!file.startsWith(WEB)) { res.writeHead(403); return res.end('403'); }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
               return res.end('404 Not Found: ' + rel); }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(buf);
  });
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let b = '';
    req.on('data', (c) => {
      b += c;
      if (b.length > 8 * 1024 * 1024) { reject(new Error('请求体过大（上限 8MB）')); req.destroy(); }
    });
    req.on('end', () => {
      if (!b) return resolve({});
      try { resolve(JSON.parse(b)); } catch (e) { reject(new Error('请求体不是合法 JSON')); }
    });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = req.url || '/';
  if (!url.startsWith('/api/')) return serveStatic(req, res, url);

  const route = url.slice(5).split('?')[0];

  try {
    if (req.method === 'GET' && route === 'bootstrap') {
      const [ds, sc, toolbox, research] = await Promise.all([
        rpc('dataset.get', {}),
        rpc('selfcheck', {}),
        rpc('trpg.toolbox', {}),
        rpc('research.get', {}),
      ]);
      return sendJSON(res, 200, {
        ok: true,
        dataset: ds.result || ds,
        selfcheck: sc.result || sc,
        toolbox: toolbox.result || toolbox,
        research: (research.result || research),
        engine: { python: PY.version, port: PORT },
      });
    }

    if (req.method === 'POST') {
      const params = await readBody(req);
      const msg = await rpc(route, params);
      if (msg.error) return sendJSON(res, 400, { ok: false, error: msg.error });
      return sendJSON(res, 200, msg.result);
    }

    if (req.method === 'GET') {
      const msg = await rpc(route, {});
      if (msg.error) return sendJSON(res, 400, { ok: false, error: msg.error });
      return sendJSON(res, 200, msg.result);
    }

    return sendJSON(res, 404, { ok: false, error: { message: `未知路由 /api/${route}` } });
  } catch (e) {
    return sendJSON(res, 500, { ok: false, error: { message: e.message } });
  }
});

server.listen(PORT, HOST, () => {
  console.log('');
  console.log('  ╔══════════════════════════════════════════════╗');
  console.log('  ║   废土旅法师 · 面板工作台                      ║');
  console.log('  ╚══════════════════════════════════════════════╝');
  console.log(`     → http://${HOST}:${PORT}`);
  console.log('');
  startEngine();
});

server.on('error', (e) => {
  if (e.code === 'EADDRINUSE') {
    console.error(`[FATAL] 端口 ${PORT} 已被占用。换端口：set PORT=8899 && node server/bridge.js`);
  } else {
    console.error('[FATAL]', e.message);
  }
  process.exit(1);
});

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    console.log('\n[bridge] 关闭中 …');
    try { if (child) child.kill(); } catch { /* 已退出 */ }
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 1500);
  });
}
