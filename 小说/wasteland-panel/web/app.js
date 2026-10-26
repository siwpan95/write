/* ==========================================================================
   app.js — 面板工作台前端
   零依赖。DOM 直操，不引框架。
   ========================================================================== */
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const STATE = {
  boot: null,          // bootstrap 数据
  snap: null,          // 面板快照
  pages: {},           // 各页缓存数据
  farm: [],            // 刷怪配置 [{tier, n}]
  matchup: [],         // 配平配置
  sid: 'main',
};

// --------------------------------------------------------------------------
// API
// --------------------------------------------------------------------------

async function api(method, params = {}) {
  const res = await fetch('/api/' + method, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  const j = await res.json();
  if (!res.ok || j.ok === false) {
    throw new Error(j.error?.message || ('HTTP ' + res.status));
  }
  return j;
}

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const pct = (n) => (n === null || n === undefined ? '—' : Math.round(n) + '%');

/** 稳定锚定：只更新变化的数值，不重建已渲染的槽位 */
function setText(sel, val) {
  const el = $(sel);
  if (el && el.textContent !== String(val)) el.textContent = val;
}

// --------------------------------------------------------------------------
// 页面切换
// --------------------------------------------------------------------------

const PAGE_LOADERS = {
  combat:  () => (window.loadCombat ? window.loadCombat() : undefined),
  campaign: () => (window.loadCampaign ? window.loadCampaign() : undefined),
  kill:    loadCodex,
  rules:   loadCodex,
  plot:    loadCodex,
  cost:    loadCodex,
  planes:  loadCodex,
  codex:   loadCodex,
  research:loadCodex,
  health:  loadCodex,
};

function switchPage(name) {
  $$('.page').forEach((p) => { p.style.display = p.id === 'page-' + name ? '' : 'none'; });
  $$('.nav-item').forEach((b) => b.classList.toggle('active', b.dataset.page === name));
  if (PAGE_LOADERS[name]) PAGE_LOADERS[name]();
  try { localStorage.setItem('wp.page', name); } catch { /* 无痕模式 */ }
}

// 战役页要在开完一场后把玩家送到战斗沙盘页，故对外暴露切换入口。
window.switchPage = switchPage;

// --------------------------------------------------------------------------
// 面板渲染
// --------------------------------------------------------------------------

/** 3/4 圈底框：起点 135°，扫 270°，断在最上面（第05章原文） */
function baseFramePath(cx, cy, r) {
  const a0 = 135 * Math.PI / 180;
  const a1 = (135 + 270) * Math.PI / 180;
  const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
  const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 1 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

function attrMod(score) { return Math.floor((score - 4 - 10) / 2); }

function renderPanel() {
  const s = STATE.snap;
  if (!s) return;

  setText('#hLvl', s.level);
  setText('#hState', s.sparkState);

  // 五维（锚定：只在结构变化时重建）
  const aBox = $('#attrs');
  if (aBox.children.length !== 5) {
    aBox.innerHTML = ['体质', '根骨', '灵敏', '精神', '悟性'].map((k) => `
      <div class="attr" data-k="${k}">
        <div class="cap-mark"></div>
        <div class="k">${k}</div><div class="v">4</div><div class="mod">+0</div>
      </div>`).join('');
  }
  for (const k of ['体质', '根骨', '灵敏', '精神', '悟性']) {
    const v = s.attrs[k];
    const el = aBox.querySelector(`[data-k="${k}"]`);
    el.querySelector('.v').textContent = v;
    el.querySelector('.mod').textContent = (attrMod(v) >= 0 ? '+' : '') + attrMod(v);
    const atCap = v >= s.softCap;
    el.classList.toggle('at-cap', atCap);
    el.querySelector('.cap-mark').textContent = atCap ? '上限' : '';
  }

  // 火花圆槽
  const circ = 2 * Math.PI * 50;
  const arc  = circ * 0.75;                 // 3/4 圈
  const fill = $('#arcFill');
  fill.setAttribute('stroke-dasharray', `${arc} ${circ}`);
  fill.setAttribute('stroke-dashoffset', arc * (1 - s.spark / 100));
  if (!$('#baseFrame').getAttribute('d')) {
    $('#baseFrame').setAttribute('d', baseFramePath(60, 60, 50));
  }
  $('#dial').classList.toggle('ignited', s.ignited);
  setText('#dialPct', s.ignited ? '已点燃' : pct(s.spark));

  setText('#siLevel', s.level);
  setText('#siPoints', s.attrPoints);
  setText('#siCap', `${s.softCap} / ${s.breakthroughs} 次`);
  setText('#siVoid', `${s.voidMin} 分钟`);
  setText('#siBlack', `黑×${s.blackMult}`);
  setText('#siPlane', s.planeCoords);

  // 解锁刻度（离散格，可数）
  const ticks = $('#uTicks');
  if (ticks.children.length !== 10) {
    ticks.innerHTML = Array.from({ length: 10 }, () => '<div class="tick"></div>').join('');
  }
  [...ticks.children].forEach((t, i) => {
    t.classList.toggle('on', !s.ignited && s.spark >= (i + 1) * 10);
  });
  const nu = s.nextUnlocks || [];
  setText('#uNames', s.ignited
    ? '已点燃 · 力量增长改走法力路径（R8）'
    : (nu.length ? `下一项：${nu[0].spark}% ${nu[0].name}` : '火花阈值 4% → 100%'));

  // 灰线读条
  const gc = $('#gCells');
  const cap = Math.max(50, s.grayCells);
  if (gc.children.length !== cap) {
    gc.innerHTML = Array.from({ length: cap }, () => '<div class="cell"></div>').join('');
  }
  [...gc.children].forEach((c, i) => c.classList.toggle('filled', i < s.grayCells));
  setText('#gVal', s.grayCells);
  $('#grayBox').classList.toggle('hot', s.grayCells > 30);
  $('#gNote').textContent = s.taxCells
    ? `R13：结构税已征 ${s.taxCells} 次，组合越复杂灰线增长越快。｜R11：越能扛越不像人。`
    : 'R11：耐受上限与代偿档位只能靠位面污染加深 —— 越能扛越不像人。';

  // 五色法力（色块 + 文字双标）
  const COLORS = { 白: 'var(--c-white)', 蓝: 'var(--c-blue)', 黑: 'var(--c-black)', 红: 'var(--c-red)', 绿: 'var(--c-green)' };
  const MEAN = { 白: '秩序/守护', 蓝: '知识/理性', 黑: '野心/代价', 红: '自由/爆发', 绿: '自然/成长' };
  $('#manaRow').innerHTML = Object.keys(COLORS).map((c) => `
    <div class="mana-slot ${s.manaPool[c] ? '' : 'zero'}">
      <span class="swatch" style="background:${COLORS[c]}"></span>
      <span class="cname">${c}</span><span class="n">×${s.manaPool[c]}</span>
      <span class="sm dim">${MEAN[c]}</span>
    </div>`).join('');

  // 天赋 / 技艺
  const un = (s.unlocked || []).map((u) => `<span class="badge">${esc(u)}</span>`).join(' ');
  $('#talents').innerHTML = `
    <div class="t"><span class="badge">天赋</span><span>${esc(s.talent)}</span></div>
    <div class="t"><span class="badge">已解锁 ${(s.unlocked || []).length}</span><span>${un || '<span class="dim">尚无</span>'}</span></div>`;

  // 控件可用性
  const hasAdd = (s.unlocked || []).includes('属性加点');
  const hasBt = (s.unlocked || []).includes('属性突破');
  $('#aGo').disabled = !hasAdd || s.attrPoints <= 0;
  $('#aBt').disabled = !hasBt || s.attrPoints < s.nextBreakthroughCost;
  $('#aBtCost').textContent = s.nextBreakthroughCost;
  $('#iGo').disabled = s.ignited;
  $('#aHint').textContent = hasAdd
    ? `剩 ${s.attrPoints} 点 · 软上限 ${s.softCap}（突破可 +1，消耗已翻倍至 ${s.nextBreakthroughCost}）`
    : '火花 25% 解锁「属性加点」';
  $('#vHint').textContent = s.ignited
    ? `已点燃 · 当前耐受 ${s.voidMin} 分钟 / 代偿 黑×${s.blackMult}`
    : '耐受与代偿按 §3.5 递增表随卷跃迁，唯一途径＝位面污染加深（R11）';

  // 日志
  const log = $('#opLog');
  log.innerHTML = (s.recentLog || []).length
    ? s.recentLog.map((d) => `<div class="line">${
        d.op === 'kill'
          ? `击杀 ${d.count}×${esc(d.tier)} → 火花 ${d.sparkBefore}%→${d.sparkAfter}%${d.newUnlocks.length ? ' · 解锁 <b>' + esc(d.newUnlocks.join('、')) + '</b>' : ''}${d.blockedByIgnite ? ' · <span class="dim">已点燃，不再增长</span>' : ''}`
          : d.op === 'structureTax'
          ? `结构税 +${d.taxCells} → 灰线 ${d.grayBefore}→${d.grayAfter} 格`
          : `${d.op} ${JSON.stringify(d).slice(0, 90)}`
      }</div>`).join('')
    : '<div class="empty">尚无操作</div>';

  renderPanelText();
}

async function renderPanelText() {
  try {
    const r = await api('panel.render', { sid: STATE.sid });
    $('#panelText').textContent = r.text;
  } catch (e) { /* 忽略 */ }
}

async function refresh() {
  STATE.snap = await api('panel.snapshot', { sid: STATE.sid });
  renderPanel();
}

// --------------------------------------------------------------------------
// 面板操作
// --------------------------------------------------------------------------

async function doKill(tier, count) {
  const r = await api('panel.kill', { sid: STATE.sid, tier, count });
  STATE.snap = r.snapshot;
  renderPanel();
  const d = r.diff;
  if (d.blockedByIgnite) flash('#kHint', '已点燃 · 火花不再增长（R8）', 'warn');
  else if (d.newUnlocks.length) flash('#kHint', `新解锁：${d.newUnlocks.join('、')}`, 'ok');
  else flash('#kHint', `火花 ${d.sparkBefore}% → ${d.sparkAfter}%（+${d.gained}）`, 'ok');
}

function flash(sel, msg, kind) {
  const el = $(sel);
  el.textContent = msg;
  el.className = 'sm mt8 ' + (kind === 'ok' ? 'dim' : '');
  el.style.color = kind === 'warn' ? 'var(--warn)' : 'var(--ink-3)';
}

// --------------------------------------------------------------------------
// 表格渲染
// --------------------------------------------------------------------------

function table(el, cols, rows) {
  const t = $(el);
  if (!rows || !rows.length) { t.innerHTML = `<tbody><tr><td class="empty">无数据</td></tr></tbody>`; return; }
  t.innerHTML = `<thead><tr>${cols.map((c) =>
    `<th class="${c.num ? 'num' : ''}">${esc(c.t)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${cols.map((c) =>
      `<td class="${c.num ? 'num' : ''}">${c.f(r)}</td>`).join('')}</tr>`).join('')}</tbody>`;
}

// --------------------------------------------------------------------------
// 码本加载（多页共用）
// --------------------------------------------------------------------------

async function loadCodex() {
  const need = STATE.pages;
  const jobs = [];
  if (!need.tiers)    jobs.push(api('codex.tiers').then((r) => (need.tiers = r.items)));
  if (!need.bestiary) jobs.push(api('codex.bestiary').then((r) => (need.bestiary = r.items)));
  if (!need.rules)    jobs.push(api('codex.rules').then((r) => { need.rules = r.rules; need.leaks = r.leakLines; }));
  if (!need.plots)    jobs.push(api('codex.plot').then((r) => (need.plots = r.items)));
  if (!need.cost)     jobs.push(api('codex.costArc').then((r) => (need.cost = r)));
  if (!need.planes)   jobs.push(api('codex.planes').then((r) => (need.planes = r)));
  if (!need.timeline) jobs.push(api('codex.timeline').then((r) => (need.timeline = r.items)));
  if (!need.chars)    jobs.push(api('codex.characters').then((r) => (need.chars = r.items)));
  if (!need.terms)    jobs.push(api('codex.terms').then((r) => (need.terms = r.items)));
  if (!need.research) jobs.push(api('research.get').then((r) => (need.research = r)));
  if (!jobs.length) return;
  await Promise.all(jobs);

  renderTiers(); renderBestiary(); renderFarm();
  renderRules(); renderPlot(); renderCost(); renderPlanes();
  renderCodex(); renderResearch(); renderHealth();
}

function renderTiers() {
  const T = STATE.pages.tiers || [];
  table('#tierTbl', [
    { t: '级', f: (r) => `<b>${esc(r.tier)}</b>` },
    { t: '名称', f: (r) => esc(r.name) },
    { t: '判据（可校验）', f: (r) => esc(r.criteria) },
    { t: '火花产出', f: (r) => r.sparkRange[0] < 0
        ? `<span class="chip err">${esc(r.sparkRaw)}</span>`
        : `<span class="chip ok">${esc(r.sparkRaw)}</span>`, num: true },
  ], T);
  // 刷怪下拉 + 批量按钮
  const sel = $('#kTier');
  if (sel && !sel.options.length) {
    sel.innerHTML = T.map((r) => `<option value="${esc(r.tier)}">${esc(r.tier)} · ${esc(r.name)}</option>`).join('');
    const row = $('#farmRow');
    if (row && !row.children.length) {
      row.innerHTML = T.map((r) => `
        <button class="sm" data-farm="${esc(r.tier)}">+1 ${esc(r.tier)}</button>`).join('')
        + `<button id="farmRun" class="primary sm">执行刷怪</button>
           <button id="farmClr" class="sm">清空</button>
           <span class="sm dim" id="farmCfg"></span>`;
    }
  }
}

function renderBestiary() {
  const B = STATE.pages.bestiary || [];
  setText('#bioCount', B.length);
  table('#bioTbl', [
    { t: '名称', f: (r) => `<b>${esc(r.name)}</b>` },
    { t: '等级', f: (r) => esc(r.tier) },
    { t: '特征', f: (r) => esc(r.feature) },
    { t: '打法 / 火花', f: (r) => esc(r.sparkRaw) },
    { t: '出处', f: (r) => `<span class="chip mute">${esc(r.source)}</span>` },
  ], B);
}

function renderFarm() {
  const cfg = STATE.farm;
  const T = STATE.pages.tiers || [];
  const byTier = {};
  cfg.forEach((f) => { byTier[f.tier] = (byTier[f.tier] || 0) + f.n; });
  const total = cfg.reduce((a, b) => a + b.n, 0);
  setText('#farmCfg', cfg.length
    ? cfg.map((f) => `${f.tier}×${f.n}`).join(' + ') + `（共 ${total} 只）`
    : '未配置');
  $$('#farmRow [data-farm]').forEach((b) => b.classList.toggle('primary', !!byTier[b.dataset.farm]));
}

function renderRules() {
  const R = STATE.pages.rules || [];
  table('#ruleTbl', [
    { t: '编号', f: (r) => `<span class="chip info">${esc(r.id)}</span>` },
    { t: '规则', f: (r) => `<b>${esc(r.name)}</b>` },
    { t: '可判定形式（条件 → 结果）', f: (r) => esc(r.judgement) },
    { t: '出处', f: (r) => `<span class="chip mute">${esc(r.source)}</span>` },
  ], R);
  const L = STATE.pages.leaks || [];
  table('#leakTbl', [
    { t: '真相', f: (r) => esc(r.truth) },
    { t: '不得早于', f: (r) => `<span class="chip warn">${esc(r.notBefore)}</span>` },
    { t: '解禁章号', f: (r) => r.minChapter, num: true },
  ], L);
}

function renderPlot() {
  const P = STATE.pages.plots || [];
  setText('#nbPlot', P.length);
  const cnt = { 已回收: 0, 推进中: 0, 待回收: 0 };
  P.forEach((p) => { if (cnt[p.status] !== undefined) cnt[p.status]++; });
  $('#plotStats').innerHTML = `
    <div class="stat"><div class="k">总条目</div><div class="v">${P.length}</div></div>
    <div class="stat"><div class="k">已回收</div><div class="v" style="color:var(--ok)">${cnt.已回收}</div></div>
    <div class="stat"><div class="k">推进中</div><div class="v" style="color:var(--info)">${cnt.推进中}</div></div>
    <div class="stat"><div class="k">待回收</div><div class="v" style="color:var(--warn)">${cnt.待回收}</div></div>`;

  const q = ($('#plotQ')?.value || '').trim();
  const f = $('#plotF')?.value || '';
  const list = P.filter((p) =>
    (!f || p.status === f) &&
    (!q || (p.id + p.desc + p.statusRaw).includes(q)));

  $('#plotList').innerHTML = list.length ? list.map((p) => {
    const cls = p.status === '已回收' ? 'ok' : p.status === '推进中' ? 'info' : 'warn';
    const noLanding = (p.status !== '已回收') && !p.plantedAt;
    return `<details>
      <summary>${esc(p.id)} <span class="chip ${cls}">${esc(p.status)}</span>
        ${noLanding ? '<span class="chip warn">缺落点</span>' : ''}</summary>
      <div class="body">
        <div style="margin-bottom:5px">${esc(p.desc)}</div>
        <div class="kv">
          <div class="k">埋于</div><div>${esc(p.plantedAt || '—')}</div>
          <div class="k">状态原文</div><div class="sm">${esc(p.statusRaw)}</div>
        </div>
      </div></details>`;
  }).join('') : '<div class="empty">无匹配条目</div>';
}

function renderCost() {
  const C = STATE.pages.cost || {};
  table('#dimTbl', [
    { t: '维度', f: (r) => `<b>${esc(r.name)}</b>` },
    { t: '定义', f: (r) => esc(r.definition) },
    { t: '年龄段', f: (r) => esc(r.ageRange), num: true },
    { t: '烧掉的记忆（具象画面）', f: (r) => esc(r.memory) },
    { t: '可判定事实', f: (r) => esc(r.judgeFact) },
    { t: '落点', f: (r) => `<span class="chip warn">${esc(r.landing)}</span>` },
  ], C.dimensions || []);
  table('#burnTbl', [
    { t: '序', f: (r) => r.seq, num: true },
    { t: '维度 / 内容', f: (r) => esc(r.content) },
    { t: '章', f: (r) => `<span class="chip mute">${esc(r.chapter)}</span>` },
    { t: '已兑现症状', f: (r) => esc(r.symptom) },
  ], C.burned || []);
}

function renderPlanes() {
  const P = STATE.pages.planes || {};
  table('#plTbl', [
    { t: '层', f: (r) => esc(r.layer) },
    { t: '正式名', f: (r) => `<b>${esc(r.name)}</b>` },
    { t: '后缀', f: (r) => `<span class="chip info">${esc(r.suffix)}</span>` },
    { t: '判据（可校验）', f: (r) => esc(r.criteria) },
    { t: '状态', f: (r) => esc(r.status) },
  ], (P.layers || []).filter((l) => l.name));
  table('#plColorTbl', [
    { t: '色', f: (r) => `<span class="chip mute">${esc(r.color)}</span>` },
    { t: '位面名', f: (r) => `<b>${esc(r.name)}</b>` },
    { t: 'DND 原型', f: (r) => esc(r.dndProto) },
    { t: '阵营', f: (r) => esc(r.faction) },
    { t: '一句判词', f: (r) => esc(r.epigram) },
  ], P.colorPlanes || []);
  table('#tolTbl', [
    { t: '卷', f: (r) => esc(r.volume) },
    { t: '黑暗虚空耐受上限', f: (r) => r.voidRaw, num: true },
    { t: '黑色代偿档位', f: (r) => `黑 ×${r.blackMult}`, num: true },
  ], P.toleranceTable || []);
  setText('#tolNote', '递增的唯一途径 = 位面污染加深（F12）。卷内可有 ±1 分钟波动，卷间跃迁只发生在大事件之后。');
  $('#nrList').innerHTML = (P.namingRules || []).map((r, i) => `
    <details><summary>${i + 1}. ${esc(r.title)}</summary>
    <div class="body">${esc(r.text)}</div></details>`).join('');
}

function renderCodex() {
  const T = STATE.pages.timeline || [];
  setText('#tlCount', T.length);
  const q = ($('#tlQ')?.value || '').trim();
  const list = q ? T.filter((e) => (e.when + e.event + e.source).includes(q)) : T;
  table('#tlTbl', [
    { t: 'ID', f: (r) => `<span class="chip mute">${esc(r.id)}</span>` },
    { t: '时间', f: (r) => esc(r.when) },
    { t: '事件', f: (r) => esc(r.event) },
    { t: '出处', f: (r) => esc(r.source) },
  ], list);

  const C = STATE.pages.chars || [];
  setText('#chCount', C.length);
  $('#chList').innerHTML = C.map((c) => `
    <details><summary>${esc(c.name)} ${c.dead ? '<span class="chip err">已死</span>' : ''}</summary>
    <div class="body sm">${esc(c.excerpt)}…</div></details>`).join('');

  const M = STATE.pages.terms || [];
  table('#tmTbl', [
    { t: '名称', f: (r) => `<b>${esc(r.name)}</b>` },
    { t: '说明', f: (r) => esc(r.note) },
    { t: '常见错写（禁止）', f: (r) => (r.forbidden || []).map((w) => `<span class="chip err">${esc(w)}</span>`).join(' ') },
  ], M);
}

function renderResearch() {
  const R = STATE.pages.research;
  if (!R) return;
  const facts = (arr) => `<div class="scroll-x"><table><thead><tr>
      <th>条目</th><th>结论</th><th>来源</th></tr></thead><tbody>
      ${(arr || []).map((f) => `<tr>
        <td><b>${esc(f.point)}</b></td>
        <td>${esc(f.text)}</td>
        <td class="sm dim">${esc(f.src)}</td></tr>`).join('')}
    </tbody></table></div>`;
  const ul = (arr) => `<ul style="padding-left:18px">${(arr || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`;

  const C = R.radiation?.conflict;
  $('#researchBody').innerHTML = `
    ${C ? `<div class="card" style="border-color:var(--err)">
      <h3>${esc(C.title)} <span class="tag">影响 ${esc(C.affectsChapters)}</span></h3>
      <div style="margin-bottom:10px">${esc(C.detail)}</div>
      <table><thead><tr><th>方案</th><th>做法</th><th>代价</th></tr></thead><tbody>
        ${C.options.map((o) => `<tr><td><b>${esc(o.key)} · ${esc(o.name)}</b></td>
          <td>${esc(o.do)}</td><td class="dim">${esc(o.cost)}</td></tr>`).join('')}
      </tbody></table>
      <div class="sm dim mt8">状态：<b>待拍板</b>。这三条是本次调研最重要的产出。</div>
    </div>` : ''}

    <div class="card"><h3>一、MTG 火花与鹏洛克 <span class="tag">世界合理性背书</span></h3>
      ${facts(R.mtg?.facts)}
      <div class="mt12"><b>对本书的三条支撑</b>${ul(R.mtg?.support)}</div>
      <div class="mt12 sm" style="color:var(--err)"><b>⚠️ 版权红线：</b>${esc(R.mtg?.redline || '')}</div>
    </div>

    <div class="card"><h3>二、辐射变异生物学 <span class="tag">现实对照</span></h3>
      ${facts(R.radiation?.facts)}
      <div class="mt12"><b>可反向利用的科学设定</b>${ul(R.radiation?.usable)}</div>
    </div>

    <div class="card"><h3>四、科幻 UI 面板范式 <span class="tag">视觉复刻依据</span></h3>
      ${facts(R.ui?.principles)}
      <div class="mt12"><b>本书面板的复刻决策</b>
        <div class="scroll-x"><table><thead><tr><th>决策</th><th>依据</th></tr></thead><tbody>
        ${(R.ui?.designDecisions || []).map((d) => `<tr><td><b>${esc(d.decision)}</b></td>
          <td class="sm">${esc(d.basis)}</td></tr>`).join('')}
        </tbody></table></div>
      </div>
      <div class="mt12 sm"><b>毛刺彩蛋：</b>${esc(R.ui?.mohair?.detail || '')}
        <div class="dim mt8">${esc(R.ui?.mohair?.idea || '')}</div></div>
    </div>

    <div class="card"><h3>六、待拍板的开放项</h3>
      <table><thead><tr><th>#</th><th>问题</th><th>影响</th><th>选项</th></tr></thead><tbody>
      ${(R.openItems || []).map((o) => `<tr><td class="num">${o.id}</td>
        <td><b>${esc(o.q)}</b></td><td class="sm">${esc(o.impact)}</td>
        <td class="sm dim">${esc(o.options)}</td></tr>`).join('')}
      </tbody></table>
    </div>

    <div class="card"><h3>三、TRPG 机制（数值部分见「TRPG 机制库」页）</h3>
      <div class="dim sm">群遭遇 n^1.5 配平、DC 难度档、属性修正公式等已内置到机制库页，可直接掷骰。</div>
    </div>`;
}

function renderHealth() {
  const b = STATE.boot;
  if (!b) return;
  const q = b.dataset?.quality || {};
  const rep = b.dataset?.parseReport || [];
  const LEVEL = { ok: 'ok', degraded: 'warn', failed: 'err', skipped: 'mute' };
  table('#parseTbl', [
    { t: '步骤', f: (r) => esc(r.step) },
    { t: '状态', f: (r) => `<span class="chip ${LEVEL[r.status] || 'mute'}">${esc(r.status)}</span>` },
    { t: '条目', f: (r) => (r.count ?? '—'), num: true },
    { t: '说明', f: (r) => `<span class="sm dim">${esc(r.detail || '')}</span>` },
  ], rep);

  const iss = b.selfcheck?.issues || [];
  setText('#issueCount', iss.length + ' 项');
  $('#issueList').innerHTML = iss.length ? iss.map((i) => `
    <details><summary><span class="chip ${
      i.level === 'error' ? 'err' : i.level === 'warn' ? 'warn' : 'info'
    }">${esc(i.level)}</span> ${esc(i.msg)}</summary>
    <div class="body sm dim">${
      i.level === 'warn' ? '建议核对 bible 对应章节后修正；若是刻意设计可忽略。'
      : i.level === 'error' ? '解析层失败，机扫会漏规则，请重跑解析。'
      : '提示性信息，无需处理。'}</div></details>`).join('')
    : '<div class="empty">无问题</div>';

  const c = b.selfcheck?.counts || {};
  $('#srcInfo').innerHTML = `
    <div class="k">源工程根</div><div class="mono sm">${esc(b.dataset?.sourceRoot || '—')}</div>
    <div class="k">数据层生成</div><div class="mono sm">${esc(b.dataset?.generatedAt || '—')}</div>
    <div class="k">解析质量</div><div class="mono sm">ok ${q.ok ?? 0} · degraded ${q.degraded ?? 0} · failed ${q.failed ?? 0}</div>
    <div class="k">条目统计</div><div class="mono sm">${
      Object.entries(c).map(([k, v]) => `${k}=${v}`).join(' · ')}</div>
    <div class="k">引擎</div><div class="mono sm">Python ${esc(b.engine?.python || '—')} · 端口 ${b.engine?.port}</div>`;
}

// --------------------------------------------------------------------------
// 机扫
// --------------------------------------------------------------------------

function renderScanResult(r) {
  const V = { PASS: ['ok', 'PASS · 无硬冲突'], FAIL: ['err', 'FAIL · 有硬冲突'] }[r.verdict] || ['mute', r.verdict];
  const box = $('#scanResult');
  box.innerHTML = `
    <div class="card">
      <h3>机扫结果 <span class="chip ${V[0]}">${V[1]}</span></h3>
      <div class="stat-row">
        <div class="stat"><div class="k">字数</div><div class="v">${r.words}</div></div>
        <div class="stat"><div class="k">章号</div><div class="v">${r.chapter}</div></div>
        <div class="stat"><div class="k">硬冲突</div><div class="v" style="color:${r.error ? 'var(--err)' : 'var(--ok)'}">${r.error}</div></div>
        <div class="stat"><div class="k">疑似</div><div class="v" style="color:var(--warn)">${r.warn}</div></div>
        <div class="stat"><div class="k">提醒</div><div class="v" style="color:var(--info)">${r.info}</div></div>
      </div>
      ${r.file ? `<div class="sm dim">文件：${esc(r.file)}</div>` : ''}
    </div>
    ${r.issues.length ? r.issues.map((i) => `
      <div class="card" style="padding:11px 14px">
        <div class="row tight" style="margin-bottom:5px">
          <span class="chip ${i.severity === 'error' ? 'err' : i.severity === 'warn' ? 'warn' : 'info'}">${
            i.severity === 'error' ? '硬冲突' : i.severity === 'warn' ? '疑似' : '提醒'}</span>
          <b class="sm">${esc(i.rule)}</b>
          <span class="sm dim">第 ${i.line} 行</span>
        </div>
        <div class="sm">${esc(i.message)}</div>
        ${i.snippet ? `<div class="mono sm dim" style="background:var(--bg-2);padding:5px 7px;border-radius:2px;margin-top:5px">${esc(i.snippet)}</div>` : ''}
        ${i.fix ? `<div class="sm mt8" style="color:var(--ok)">修法：${esc(i.fix)}</div>` : ''}
      </div>`).join('') : '<div class="card"><div class="empty">未发现任何违例</div></div>'}`;
}

// --------------------------------------------------------------------------
// TRPG 页
// --------------------------------------------------------------------------

function renderToolbox() {
  const T = STATE.boot?.toolbox;
  if (!T) return;
  if (!$('#ckDc').options.length) {
    $('#ckDc').innerHTML = T.dcTable.map((d) =>
      `<option value="${d.dc}" ${d.dc === 15 ? 'selected' : ''}>DC ${d.dc} · ${d.label}（${d.base}%）</option>`).join('');
    $('#ckAttr').innerHTML = Object.keys(T.attrMap).map((k) =>
      `<option value="${k}">${k}（${T.attrMap[k]}）</option>`).join('');
    $('#aAttr').innerHTML = ['体质', '根骨', '灵敏', '精神', '悟性'].map((k) => `<option>${k}</option>`).join('');
    $('#bnMode').innerHTML = T.burnModes.map((m) =>
      `<option value="${m.key}">${m.name}（${m.speed}·${m.risk}）</option>`).join('');
    table('#stTbl', [
      { t: '状态', f: (r) => `<b>${esc(r.name)}</b>` },
      { t: '属性', f: (r) => esc(r.attr) },
      { t: '惩罚', f: (r) => r.penalty, num: true },
      { t: '触发条件', f: (r) => esc(r.condition) },
      { t: '表现', f: (r) => esc(r.desc) },
      { t: '叠加', f: (r) => esc(r.stacking) },
    ], T.statusEffects);
    $('#stCtl').innerHTML = T.statusEffects.map((s) =>
      `<button class="sm" data-st="${esc(s.key)}">+ ${esc(s.name)}</button>`).join('')
      + `<button class="sm" id="stClr">清空状态</button>`;
    $('#muCtl').innerHTML = T.tierTable.map((t) =>
      `<button class="sm" data-mu="${esc(t.tier)}">+ ${esc(t.tier)}</button>`).join('')
      + `<button class="sm" id="muClr">清空</button>`;
    $('#fxList').innerHTML = Object.entries(T.formulas)
      .map(([k, v]) => `<div class="k">${esc(k)}</div><div class="mono sm">${esc(v)}</div>`).join('');
  }
  if (!$('#muList').children.length) $('#muList').innerHTML = '<div class="dim sm">未配置</div>';
}

async function doMatchup() {
  if (!STATE.matchup.length) { $('#muOut').innerHTML = '<div class="dim sm">先点上方按钮加入怪物</div>'; return; }
  const r = await api('trpg.matchup', { tiers: STATE.matchup });
  $('#muOut').innerHTML = `
    <div class="stat-row">
      <div class="stat"><div class="k">怪物数</div><div class="v">${r.count}</div></div>
      <div class="stat"><div class="k">单体预算</div><div class="v">${r.monsterBudget}</div></div>
      <div class="stat"><div class="k">合成难度</div><div class="v">${r.encounterBudget}</div></div>
      <div class="stat"><div class="k">建议 DC</div><div class="v">${r.suggestDC}</div></div>
      <div class="stat"><div class="k">危险度</div><div class="v" style="font-size:14px">${esc(r.dangerLabel)}</div></div>
    </div>
    <div class="sm dim">${esc(r.note)}</div>`;
}

function renderMatchupCfg() {
  const box = $('#muList');
  if (!STATE.matchup.length) { box.innerHTML = '<div class="dim sm">未配置</div>'; return; }
  const c = {};
  STATE.matchup.forEach((t) => { c[t] = (c[t] || 0) + 1; });
  box.innerHTML = Object.entries(c).map(([t, n]) =>
    `<span class="chip info" style="margin:0 4px 4px 0">${esc(t)} × ${n}</span>`).join('');
}

// --------------------------------------------------------------------------
// 事件绑定
// --------------------------------------------------------------------------

function bind() {
  // 导航
  $$('.nav-item').forEach((b) =>
    b.addEventListener('click', () => switchPage(b.dataset.page)));

  // 面板
  $('#kGo').addEventListener('click', () => doKill($('#kTier').value, Number($('#kCount').value) || 1));
  $('#aGo').addEventListener('click', async () => {
    try { const r = await api('panel.allocate', { sid: STATE.sid, attr: $('#aAttr').value });
          STATE.snap = r.snapshot; renderPanel();
          flash('#aHint', r.ok ? `已加点：${r.before} → ${r.after}（剩 ${r.attrPointsLeft} 点）` : r.error, r.ok ? 'ok' : 'warn');
        } catch (e) { flash('#aHint', e.message, 'warn'); }
  });
  $('#aBt').addEventListener('click', async () => {
    try { const r = await api('panel.breakthrough', { sid: STATE.sid, attr: $('#aAttr').value });
          STATE.snap = r.snapshot; renderPanel();
          flash('#aHint', r.ok ? `突破成功：${r.before} → ${r.after}（消耗 ${r.costPaid} 点，下次 ${r.nextCost}）` : r.error, r.ok ? 'ok' : 'warn');
        } catch (e) { flash('#aHint', e.message, 'warn'); }
  });
  $('#gGo').addEventListener('click', async () => {
    try { const r = await api('panel.grayline', { sid: STATE.sid, cells: Number($('#gCellsIn').value) });
          STATE.snap = r.snapshot; renderPanel();
          flash('#aHint', r.ok ? `灰线 ${r.before} → ${r.after} 格（+${r.delta}）` : r.error, r.ok ? 'ok' : 'warn');
        } catch (e) { flash('#aHint', e.message, 'warn'); }
  });
  $('#gTax').addEventListener('click', async () => {
    const r = await api('panel.structureTax', { sid: STATE.sid, cells: 1 });
    STATE.snap = r.snapshot; renderPanel();
    flash('#aHint', `结构税累计 ${r.taxCells} 次 → 灰线 ${r.grayBefore}→${r.grayAfter} 格`, 'warn');
  });
  $('#vGo').addEventListener('click', async () => {
    try { const r = await api('panel.volume', { sid: STATE.sid, volume: Number($('#vVol').value) });
          STATE.snap = r.snapshot; renderPanel();
          flash('#vHint', r.ok ? `跃迁至${r.source}：耐受 ${r.before.voidMin}→${r.after.voidMin} 分，代偿 黑×${r.before.blackMult}→黑×${r.after.blackMult}` : r.error, 'ok');
        } catch (e) { flash('#vHint', e.message, 'warn'); }
  });
  $('#iGo').addEventListener('click', async () => {
    try { const r = await api('panel.ignite', { sid: STATE.sid });
          STATE.snap = r.snapshot; renderPanel();
          flash('#vHint', r.ok ? '已点燃 · 火花封顶，改走法力路径（R8）' : r.error, r.ok ? 'ok' : 'warn');
        } catch (e) { flash('#vHint', e.message, 'warn'); }
  });
  $('#pReset').addEventListener('click', async () => {
    const r = await api('panel.reset', { sid: STATE.sid });
    STATE.snap = r.snapshot; renderPanel();
    flash('#aHint', '已重置为初始状态（全 4 / 火花 0%）', 'ok');
  });
  $('#copyText').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('#panelText').textContent);
          $('#copyText').textContent = '已复制'; setTimeout(() => ($('#copyText').textContent = '复制'), 1400);
    } catch { $('#copyText').textContent = '复制失败'; }
  });

  // 刷怪
  $('#farmRow').addEventListener('click', async (e) => {
    const t = e.target.dataset?.farm;
    if (t) { STATE.farm.push({ tier: t, n: 1 }); renderFarm(); return; }
    if (e.target.id === 'farmClr') { STATE.farm = []; renderFarm(); return; }
    if (e.target.id === 'farmRun') {
      if (!STATE.farm.length) { alert('先点上面的等级按钮加入怪物'); return; }
      for (const f of STATE.farm) await doKill(f.tier, f.n);
      STATE.farm = []; renderFarm();
    }
  });

  // 机扫
  $('#scanGo').addEventListener('click', async () => {
    const t = $('#scanText').value;
    if (!t.trim()) { alert('先粘贴章节正文'); return; }
    try {
      const r = await api('scan.chapter', { text: t, chapter: Number($('#scanCh').value) || 999 });
      renderScanResult(r);
    } catch (e) { alert('机扫失败：' + e.message); }
  });
  $('#scanClear').addEventListener('click', () => { $('#scanText').value = ''; $('#scanResult').innerHTML = ''; });
  $('#pickFile').addEventListener('click', () => $('#fileInput').click());
  $('#fileInput').addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const rd = new FileReader();
    rd.onload = () => { $('#scanText').value = rd.result; };
    rd.readAsText(f, 'utf-8');
  });

  // 台账筛选
  $('#plotQ').addEventListener('input', renderPlot);
  $('#plotF').addEventListener('change', renderPlot);
  $('#tlQ').addEventListener('input', renderCodex);

  // TRPG
  $('#ckGo').addEventListener('click', async () => {
    const r = await api('trpg.check', {
      attrName: $('#ckAttr').value,
      score: Number($('#ckScore').value),
      dc: Number($('#ckDc').value),
      advantage: $('#ckAdv').checked,
      disadvantage: $('#ckDis').checked,
    });
    $('#ckOut').innerHTML = `
      <div class="stat-row">
        <div class="stat"><div class="k">掷骰</div><div class="v">${r.d20.join('d20')}</div></div>
        <div class="stat"><div class="k">修正</div><div class="v">${r.mod >= 0 ? '+' : ''}${r.mod}</div></div>
        <div class="stat"><div class="k">总值</div><div class="v">${r.total}</div></div>
        <div class="stat"><div class="k">DC</div><div class="v">${r.dc}</div></div>
        <div class="stat"><div class="k">结果</div><div class="v" style="color:${r.success ? 'var(--ok)' : 'var(--err)'}">${r.success ? '成功' : '失败'}</div></div>
      </div>
      <div class="sm dim">${esc(r.attrName)} ${r.attrScore} → 修正 ${r.mod}（${esc(r.mode)}）· 成功率 ${r.rate}%${
        r.crit ? ' · <b style="color:var(--warn)">大成功（天然 20）</b>' : ''}${
        r.fumble ? ' · <b style="color:var(--err)">大失败（天然 1）</b>' : ''}</div>`;
    $('#ckMod').textContent = `成功率 ${r.rate}%（优势/劣势不叠加，互相抵消）`;
  });
  $('#ckRate').addEventListener('click', async () => {
    const r = await api('trpg.rate', {
      score: Number($('#ckScore').value), dc: Number($('#ckDc').value),
      advantage: $('#ckAdv').checked, disadvantage: $('#ckDis').checked });
    $('#ckOut').innerHTML = `<div class="stat-row">
      <div class="stat"><div class="k">修正</div><div class="v">${r.mod >= 0 ? '+' : ''}${r.mod}</div></div>
      <div class="stat"><div class="k">DC</div><div class="v">${r.dc}</div></div>
      <div class="stat"><div class="k">成功率</div><div class="v">${r.rate}%</div></div></div>`;
  });
  $('#ckScore').addEventListener('input', () => {
    const m = attrMod(Number($('#ckScore').value));
    $('#ckMod').textContent = `当前修正 ${m >= 0 ? '+' : ''}${m}（公式：floor((属性−4−10)/2)）`;
  });

  $('#muCtl').addEventListener('click', (e) => {
    const t = e.target.dataset?.mu;
    if (t) { STATE.matchup.push(t); renderMatchupCfg(); doMatchup(); }
    if (e.target.id === 'muClr') { STATE.matchup = []; renderMatchupCfg(); $('#muOut').innerHTML = ''; }
  });
  $('#stCtl').addEventListener('click', async (e) => {
    const k = e.target.dataset?.st;
    if (k) {
      const r = await api('trpg.status', { sid: STATE.sid, key: k });
      if (r.ok) {
        $('#stOut').innerHTML = `<div class="sm"><b>${esc(r.status)}</b> ×${r.count} → ${esc(r.attr)} ${r.totalPenalty} 点
          <div class="dim mt8">${esc(r.desc)}</div>
          <div class="mono sm mt8">有效属性：${Object.entries(r.effectiveAttrs).map(([a, v]) => `${a}${v}`).join(' / ')}</div></div>`;
        STATE.snap = r.snapshot; renderPanel();
      } else { $('#stOut').innerHTML = `<div class="sm" style="color:var(--err)">${esc(r.error)}</div>`; }
    }
    if (e.target.id === 'stClr') { $('#stOut').innerHTML = ''; }
  });
  $('#bnGo').addEventListener('click', async () => {
    const r = await api('trpg.burn', {
      volume: Number($('#bnVol').value), blackMult: Number($('#bnMult').value), mode: $('#bnMode').value });
    if (!r.ok) { $('#bnOut').innerHTML = `<div class="sm" style="color:var(--err)">${esc(r.error)}</div>`; return; }
    $('#bnOut').innerHTML = `
      <div class="row tight" style="margin-bottom:6px">
        <span class="chip info">${esc(r.mode)}</span>
        <span class="chip warn">深度 ${r.depth}</span>
        <span class="chip mute">黑×${r.blackMult}</span>
      </div>
      <div class="sm">${esc(r.modeDesc)}</div>
      <ul style="padding-left:18px;margin-top:6px">${r.symptoms.map((s) => `<li class="sm">${esc(s)}</li>`).join('')}</ul>
      <div class="sm mt8" style="color:var(--warn)">${esc(r.rule)}</div>
      ${r.example !== '（禁术，正文不得使用）'
        ? `<div class="sm dim mt8">已用先例：${esc(r.example)}</div>` : ''}`;
  });

  // 毛刺彩蛋
  $('#holo').addEventListener('dblclick', () => {
    $('#holo').classList.toggle('burr');
    const on = $('#holo').classList.contains('burr');
    $('#holo').title = on ? '毛刺在（他还记得那晚的细节）' : '毛刺被抹掉了（他不再记得）';
  });

  // 体检
  $('#reloadBtn').addEventListener('click', async () => {
    $('#reloadMsg').textContent = '重载中 …';
    try {
      const r = await fetch('/api/dataset.get', { method: 'POST', body: '{}' });
      await r.json();
      location.reload();
    } catch (e) { $('#reloadMsg').textContent = '重载失败：' + e.message; }
  });
}

// --------------------------------------------------------------------------
// 启动
// --------------------------------------------------------------------------

(async function boot() {
  try {
    const res = await fetch('/api/bootstrap');
    const b = await res.json();
    if (b.ok === false) throw new Error(b.error?.message || 'bootstrap 失败');
    STATE.boot = b;

    const snap = await api('panel.snapshot', { sid: STATE.sid });
    STATE.snap = snap.snapshot;

    $('#app').style.display = '';
    $('#boot').remove();
    $('#brandSub').textContent =
      (b.selfcheck?.generatedAt || '').slice(0, 16) + ' · py' + (b.engine?.python || '');

    renderPanel();
    renderToolbox();
    await loadCodex();
    bind();

    const last = localStorage.getItem('wp.page');
    if (last) switchPage(last);
  } catch (e) {
    $('#boot').innerHTML = `<div style="color:var(--err);max-width:520px;text-align:center">
      <b>启动失败</b><div class="sm mt8">${esc(e.message)}</div>
      <div class="sm dim mt12">确认已运行 <span class="mono">python engine/bible_parser.py</span></div></div>`;
    console.error(e);
  }
})();
