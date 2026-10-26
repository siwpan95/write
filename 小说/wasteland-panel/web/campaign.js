/* ==========================================================================
   campaign.js — 战役推进前端
   零依赖。只发指令 + 渲染，不自己算任何战斗数值（规则与结算全在 Python 侧）。

   与战斗沙盘的分工：
     本页负责「战役」——跨场状态（HP/法力/灰线/火花）与遭遇序列；
     具体的回合制对轰在战斗沙盘页打（两边共用 ENCOUNTERS[default]）。
     点了「开始这一场」会直接把玩家送到战斗沙盘页。
   ========================================================================== */
'use strict';

(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const CP = {
    chains: null,   // campaign.chains
    catalog: null,  // combat.catalog（自由插入用）
    snap: null,     // campaign.state
    roster: [],     // 自由插入的 [{name, count}]
    ready: false,
    busy: false,
  };

  async function api(method, params = {}) {
    const res = await fetch('/api/' + method, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    const j = await res.json();
    if (!res.ok || j.ok === false) {
      throw new Error(j.error && j.error.message ? j.error.message : 'HTTP ' + res.status);
    }
    return j;
  }

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function msg(text, kind) {
    const el = $('#cpMsg');
    if (!el) return;
    el.textContent = text || '';
    el.style.color = kind === 'warn' ? 'var(--warn)'
      : kind === 'ok' ? 'var(--ok, var(--ink-3))' : 'var(--ink-3)';
  }

  // ------------------------------------------------------------------------
  // 载入
  // ------------------------------------------------------------------------

  async function loadCampaign() {
    if (CP.ready) { await refresh(); return; }
    try {
      const [ch, cat] = await Promise.all([
        api('campaign.chains'), api('combat.catalog'),
      ]);
      CP.chains = ch.chains || [];
      CP.catalog = cat || { tiers: [], named: [] };
      CP.ready = true;
      renderChainSelect();
      renderManaColors();
      renderNamedChips();
      bind();
      await refresh();
    } catch (e) {
      msg('战役层初始化失败：' + e.message
        + '（若提示缺少 allin-engine，见 README「运行依赖」）', 'warn');
    }
  }

  function renderChainSelect() {
    const sel = $('#cpChain');
    sel.innerHTML = CP.chains
      .map((c) => `<option value="${esc(c.key)}">${esc(c.label)}（${c.count} 场）</option>`)
      .join('');
    sel.onchange = () => {
      const c = CP.chains.find((x) => x.key === sel.value);
      $('#cpChainNote').textContent = c ? c.note : '';
      renderChainList(c);
    };
    if (CP.chains.length) {
      sel.value = CP.chains[CP.chains.length - 1].key;   // 默认第三卷链
      sel.onchange();
    }
  }

  function renderChainList(c) {
    const box = $('#cpChainList');
    if (!c) { box.innerHTML = ''; return; }
    box.innerHTML = '<div class="roster">'
      + c.encounters.map((e, i) => `
        <div class="frow">
          <span class="k">${i + 1}. ${esc(e.name)}</span>
          <span class="v">${(e.enemies || [])
            .map((x) => `${esc(x.name)}×${x.count}`).join('、')}</span>
        </div>
        ${e.note ? `<div class="sm dim">${esc(e.note)}</div>` : ''}
        ${e.winrate ? `<div class="sm dim">实测胜率 ${esc(e.winrate)}</div>` : ''}`).join('')
      + '</div>';
  }

  function renderManaColors() {
    const sel = $('#cpColor');
    // 黑色不可汲取（R9：烧的是记忆/情感碎片，不可复原）
    const colors = ['白', '蓝', '红', '绿'];
    sel.innerHTML = colors.map((c) => `<option value="${c}">${c}</option>`).join('');
  }

  function renderNamedChips() {
    const box = $('#cpNamed');
    const named = (CP.catalog.named || []).map((n) => n.name);
    const tiers = (CP.catalog.tiers || [])
      .filter((t) => !t.unkillable).map((t) => t.tier);
    box.innerHTML = [...named, ...tiers]
      .map((n) => `<button class="chip" data-n="${esc(n)}">${esc(n)}</button>`).join('');
    $$('.chip', box).forEach((b) => b.addEventListener('click', () => {
      addRoster(b.dataset.n);
    }));
  }

  function addRoster(name) {
    const hit = CP.roster.find((r) => r.name === name);
    if (hit) hit.count += 1;
    else CP.roster.push({ name, count: 1 });
    renderRoster();
  }

  function renderRoster() {
    const box = $('#cpRoster');
    if (!CP.roster.length) { box.innerHTML = '<div class="sm dim">还没选异族。</div>'; return; }
    box.innerHTML = CP.roster.map((r, i) => `
      <div class="frow">
        <span class="k">${esc(r.name)}</span>
        <span class="v">
          <button class="sm" data-i="${i}" data-d="-1">−</button>
          <b style="margin:0 6px">${r.count}</b>
          <button class="sm" data-i="${i}" data-d="1">+</button>
        </span>
      </div>`).join('');
    $$('button[data-i]', box).forEach((b) => b.addEventListener('click', () => {
      const i = Number(b.dataset.i);
      CP.roster[i].count += Number(b.dataset.d);
      if (CP.roster[i].count <= 0) CP.roster.splice(i, 1);
      renderRoster();
    }));
  }

  // ------------------------------------------------------------------------
  // 状态渲染
  // ------------------------------------------------------------------------

  async function refresh() {
    let s;
    try {
      s = await api('campaign.state');
    } catch (e) {
      // 没有进行中的战役 → 显示新建卡片
      $('#cpSetup').style.display = '';
      $('#cpRun').style.display = 'none';
      return;
    }
    CP.snap = s;
    renderRun(s);
  }

  function renderRun(s) {
    $('#cpSetup').style.display = 'none';
    $('#cpRun').style.display = '';
    $('#cpChainLabel').textContent = (s.chain && s.chain.label) || '战役';

    const tag = $('#cpStatusTag');
    tag.textContent = s.status === 'complete' ? '已通关'
      : s.status === 'dead' ? '已阵亡' : '进行中';

    const pct = s.maxHp ? Math.max(0, Math.round((s.hp / s.maxHp) * 100)) : 0;
    $('#cpStatRow').innerHTML = `
      <div class="kpi"><span class="k">生命</span><span class="v">${s.hp} / ${s.maxHp}</span></div>
      <div class="kpi"><span class="k">火花</span><span class="v">${s.spark}%${s.ignited ? '（已点燃）' : ''}</span></div>
      <div class="kpi"><span class="k">灰线</span><span class="v">${s.grayCells} 格</span></div>
      <div class="kpi"><span class="k">进度</span><span class="v">${s.cursor} / ${s.total}</span></div>`;

    $('#cpBar').innerHTML = `
      <div class="hpbar"><div class="fill ${pct > 60 ? 'ok' : pct > 30 ? 'warn' : 'crit'}"
           style="width:${pct}%"></div></div>
      <div class="sm dim mt8">生命 ${pct}% · 灰线只增不回退（R11）·
        火花${s.ignited ? '已封顶（R8）' : '只涨不落'}</div>`;

    const pool = s.manaPool || {};
    $('#cpNote').innerHTML = '五色法力：'
      + Object.keys(pool).map((c) => `${c} ${pool[c]}`).join(' · ')
      + '　|　虚空耐受 ' + (s.voidMin || 0) + ' 分钟 · 黑色代偿 ×' + (s.blackMult || 1);

    $('#cpProgress').textContent = `第 ${Math.min(s.cursor + 1, s.total)} / ${s.total} 场`;

    const nx = s.next;
    $('#cpNext').innerHTML = nx ? `
      <div class="frow"><span class="k">遭遇</span><span class="v">${esc(nx.name)}</span></div>
      <div class="frow"><span class="k">异族</span><span class="v">${
        (nx.enemies || []).map((e) => `${esc(e.name)}×${e.count}`).join('、')}</span></div>
      ${nx.note ? `<div class="sm dim mt8">${esc(nx.note)}</div>` : ''}`
      : '<div class="sm dim">链已走完。</div>';

    // 日志
    $('#cpLog').innerHTML = (s.history || []).map((h, i) => `
      <div class="cbline">${i + 1}. ${esc(h.name)} —
        ${h.status === 'victory' ? '胜' : h.status === 'defeat' ? '败' : esc(h.status)}
        （${h.round} 回合）· 剩 ${h.hpAfter}/${h.maxHp} ·
        火花 ${h.sparkAfter}% · 灰线 ${h.grayAfter}</div>`).join('')
      || '<div class="sm dim">还没有战斗记录。</div>';

    const over = s.status !== 'ongoing';
    $('#cpGo').disabled = over || !nx;
    $('#cpApply').disabled = over;
    $('#cpRest').disabled = over;
    $('#cpHeal').disabled = over;
    $('#cpDraw').disabled = over;
    $('#cpInsert').disabled = over;
    $('#cpBattleHint').textContent = over
      ? '战役已结束，可点「结束战役」另开一条。'
      : '开完这一场会跳到战斗沙盘页；打完回来点「结算并推进」。';
  }

  // ------------------------------------------------------------------------
  // 动作
  // ------------------------------------------------------------------------

  async function guard(fn) {
    if (CP.busy) return;
    CP.busy = true;
    try { await fn(); } catch (e) { msg('失败：' + e.message, 'warn'); }
    finally { CP.busy = false; }
  }

  function bind() {
    $('#cpNew').onclick = () => guard(async () => {
      const seed = $('#cpSeed').value;
      const p = { chain: $('#cpChain').value };
      if (seed) p.seed = Number(seed);
      await api('campaign.new', p);
      msg('战役已开始', 'ok');
      await refresh();
    });

    $('#cpGo').onclick = () => guard(async () => {
      const r = await api('campaign.next');
      msg('已开局：' + (r.encounterName || '遭遇') + '，去战斗沙盘页开打', 'ok');
      if (window.switchPage) window.switchPage('combat');
    });

    $('#cpApply').onclick = () => guard(async () => {
      const r = await api('campaign.apply');
      const rec = r.record || {};
      msg(`已回收：剩余生命 ${r.hp}/${r.maxHp}，火花 ${r.spark}%`, 'ok');
      await refresh();
      if (r.status === 'complete') msg('战役链走完了', 'ok');
      if (r.status === 'dead') msg('旅法师倒下了——灰线不会因此回退', 'warn');
    });

    $('#cpRest').onclick = () => guard(async () => {
      const r = await api('campaign.rest');
      msg(`休整：生命 ${r.rest.hpBefore} → ${r.rest.hpAfter}/${r.rest.maxHp}，灰线不变`, 'ok');
      await refresh();
    });

    $('#cpHeal').onclick = () => guard(async () => {
      const r = await api('campaign.heal');
      msg(`治疗言灵：+${r.heal.heal} 生命 → ${r.heal.hpAfter}/${r.heal.maxHp}`, 'ok');
      await refresh();
    });

    $('#cpDraw').onclick = () => guard(async () => {
      const r = await api('campaign.draw', { color: $('#cpColor').value });
      const p = r.draw.pool[$('#cpColor').value];
      msg(`汲取：该色 ${p} 点，灰线 ${r.draw.grayCells} 格（R11）`, 'ok');
      await refresh();
    });

    $('#cpInsert').onclick = () => guard(async () => {
      if (!CP.roster.length) { msg('先选至少一只异族', 'warn'); return; }
      const r = await api('campaign.insert', {
        enemies: CP.roster.map((x) => ({ name: x.name, count: x.count })),
      });
      msg('已插入并开局：' + (r.encounterName || '遭遇'), 'ok');
      if (window.switchPage) window.switchPage('combat');
    });

    $('#cpRosterClear').onclick = () => { CP.roster = []; renderRoster(); };

    $('#cpEnd').onclick = () => guard(async () => {
      await api('campaign.end');
      CP.snap = null;
      $('#cpSetup').style.display = '';
      $('#cpRun').style.display = 'none';
      msg('战役已结束', 'ok');
    });
  }

  // 暴露给 app.js 的 PAGE_LOADERS
  window.loadCampaign = loadCampaign;
})();
