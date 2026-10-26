/* ==========================================================================
   combat.js — 战斗沙盘前端
   零依赖。DOM 直操，与 app.js 同风格（不引框架）。
   所有规则与结算都在 Python 侧（combat_engine.py），本文件只负责
   发指令、渲染状态、展示日志——前端不自己算任何战斗数值。
   ========================================================================== */
'use strict';

(function () {
  const $ = (s, r = document) => r.querySelector(s);

  const CST = {
    profiles: null,     // pc.profiles
    catalog: null,      // combat.catalog（谱系 + 具名异族）
    snap: null,         // 最近一次 combat 快照
    roster: [],         // [{name, count}]
    target: null,       // 当前目标 uid
    busy: false,
    ready: false,
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
    const el = $('#cbMsg');
    if (!el) return;
    el.textContent = text || '';
    el.style.color = kind === 'warn' ? 'var(--warn)'
      : kind === 'ok' ? 'var(--ok, var(--ink-3))' : 'var(--ink-3)';
  }

  // ------------------------------------------------------------------------
  // 备战
  // ------------------------------------------------------------------------

  async function loadCombat() {
    if (CST.ready) { await refreshBattle(true); return; }
    try {
      const [p, c] = await Promise.all([api('pc.profiles'), api('combat.catalog')]);
      CST.profiles = p.profiles || [];
      CST.catalog = c || { tiers: [], named: [] };
      CST.ready = true;
      renderSetup();
      await refreshBattle(true);
    } catch (e) {
      msg('战斗沙盘初始化失败：' + e.message
        + '（若提示缺少 allin-engine，见 README「运行依赖」）', 'warn');
    }
  }

  function renderSetup() {
    const sel = $('#cbProfile');
    sel.innerHTML = (CST.profiles || []).map((p) =>
      `<option value="${esc(p.key)}">${esc(p.label)}</option>`).join('');
    // 默认落在第三卷：能打二级、三级要搏命，最能体现强弱曲线
    const def = CST.profiles.find((p) => p.key === 'v3-mycelium');
    if (def) sel.value = def.key;
    sel.onchange = () => { renderProfileNote(); };
    renderProfileNote();

    // 具名异族 chips
    const named = (CST.catalog.named || []).filter((n) => !n.unkillable);
    $('#cbNamed').innerHTML = named.map((n) => {
      const tr = (n.traits || []).map((t) => t.label).join('、');
      return `<button class="chip" data-name="${esc(n.name)}" title="${esc(tr || n.name)}">
        ${esc(n.name)}<span class="tier">${esc(n.tier)}</span></button>`;
    }).join('') || '<span class="dim sm">（目录为空）</span>';
    $('#cbNamed').querySelectorAll('.chip').forEach((b) => {
      b.onclick = () => { addToRoster(b.dataset.name); };
    });

    // 谱系兜底：具名之外也允许直接按等级刷
    const tiers = (CST.catalog.tiers || []).filter((t) => !t.unkillable);
    $('#cbNamed').insertAdjacentHTML('beforeend',
      '<span class="dim sm" style="margin-left:8px">按等级：</span>' +
      tiers.map((t) => `<button class="chip ghost" data-name="${esc(t.tier)}"
        title="${esc(t.note || '')}">${esc(t.tier)}</button>`).join(''));
    $('#cbNamed').querySelectorAll('.chip.ghost').forEach((b) => {
      b.onclick = () => { addToRoster(b.dataset.name); };
    });

    renderRoster();
    $('#cbGo').onclick = startBattle;
    $('#cbClear').onclick = () => { CST.roster = []; renderRoster(); };
  }

  function renderProfileNote() {
    const key = $('#cbProfile').value;
    const p = (CST.profiles || []).find((x) => x.key === key);
    $('#cbProfileNote').textContent = p
      ? `${p.note}｜五维 ${Object.entries(p.attrs).map(([k, v]) => k + v).join(' ')}`
        + `｜火花 ${p.spark}%${p.ignited ? '（已点燃）' : ''}`
        + `｜技术 ${(p.techniques || []).join('、') || '无'}`
      : '';
  }

  function addToRoster(name) {
    const hit = CST.roster.find((r) => r.name === name);
    if (hit) hit.count += 1;
    else CST.roster.push({ name, count: 1 });
    renderRoster();
  }

  function renderRoster() {
    const box = $('#cbRoster');
    if (!CST.roster.length) {
      box.innerHTML = '<div class="sm dim">（空）</div>';
      $('#cbRosterHint').textContent = '还没选异族。建议：一级 2–3 只（第一卷）、二级 2 只（第三卷）。';
      return;
    }
    box.innerHTML = CST.roster.map((r, i) => `
      <div class="rost">
        <span class="nm">${esc(r.name)}</span>
        <button class="sm" data-i="${i}" data-d="-1">−</button>
        <span class="ct">×${r.count}</span>
        <button class="sm" data-i="${i}" data-d="1">+</button>
        <button class="sm" data-i="${i}" data-d="0">✕</button>
      </div>`).join('');
    box.querySelectorAll('button').forEach((b) => {
      b.onclick = () => {
        const i = +b.dataset.i, d = +b.dataset.d;
        if (d === 0) CST.roster.splice(i, 1);
        else {
          CST.roster[i].count += d;
          if (CST.roster[i].count <= 0) CST.roster.splice(i, 1);
        }
        renderRoster();
      };
    });
    const total = CST.roster.reduce((a, r) => a + r.count, 0);
    $('#cbRosterHint').textContent = `共 ${total} 只 · 数量越多越危险
      （群遭遇合成难度 ≈ (Σ单体^1.5)^(2/3)，不是简单相加）`;
  }

  // ------------------------------------------------------------------------
  // 开局 / 刷新
  // ------------------------------------------------------------------------

  async function startBattle() {
    if (CST.busy) return;
    if (!CST.roster.length) { msg('先选至少一只异族', 'warn'); return; }
    CST.busy = true;
    msg('正在开局 …');
    try {
      const params = {
        sid: 'default',
        profile: $('#cbProfile').value,
        enemies: CST.roster.map((r) => ({ name: r.name, count: r.count })),
      };
      const seed = $('#cbSeed').value;
      if (seed) params.seed = Number(seed);
      // 勾选「接续上一场」才保留火花/灰线；否则从所选剧情档位的初值重新开局
      if ($('#cbCarry').checked) params.carryOver = true;
      const r = await api('combat.new', params);
      CST.snap = r.snapshot;
      CST.target = (r.snapshot.enemies.find((e) => e.alive) || {}).uid || null;
      if ((r.blocked || []).length) {
        msg('以下异族不可击杀、未加入战斗：' + r.blocked.join('、'), 'warn');
      } else msg('');
      $('#cbSetup').style.display = 'none';
      $('#cbBattle').style.display = '';
      $('#cbResult').style.display = 'none';
      $('#cbNarrateText').style.display = 'none';
      renderBattle();
      await maybeAutoEnemies();
    } catch (e) {
      msg('开局失败：' + e.message, 'warn');
    } finally {
      CST.busy = false;
    }
  }

  async function refreshBattle(silent) {
    try {
      const r = await api('combat.state', { sid: 'default' });
      CST.snap = r.snapshot;
      $('#cbSetup').style.display = 'none';
      $('#cbBattle').style.display = '';
      if (!CST.target || !CST.snap.enemies.some((e) => e.uid === CST.target && e.alive)) {
        CST.target = (CST.snap.enemies.find((e) => e.alive) || {}).uid || null;
      }
      renderBattle();
    } catch (e) {
      if (!silent) msg(e.message, 'warn');
    }
  }

  // ------------------------------------------------------------------------
  // 渲染
  // ------------------------------------------------------------------------

  function hpBar(cur, max) {
    const p = max ? Math.max(0, Math.min(100, (cur / max) * 100)) : 0;
    const cls = p > 60 ? 'ok' : p > 25 ? 'warn' : 'crit';
    return `<div class="hpbar"><div class="fill ${cls}" style="width:${p}%"></div>
      <span class="txt">${cur} / ${max}</span></div>`;
  }

  function renderBattle() {
    const s = CST.snap;
    if (!s) return;
    const pc = s.pc;

    // 顶部状态条
    $('#cbStatRow').innerHTML = [
      kpi('回合', s.round),
      kpi('状态', s.status === 'ongoing' ? '进行中'
        : s.status === 'victory' ? '胜利' : '败北'),
      kpi('当前行动', s.turnName || '—'),
      kpi('火花', (s.spark != null ? s.spark : 0) + '%'),
      kpi('灰线', (s.grayCells || 0) + ' 格'),
    ].join('');

    // PC 卡
    const mana = s.manaPool || {};
    $('#cbPcTag').textContent = `等级 ${pc.level || '—'}`;
    $('#cbPc').innerHTML = `
      <div class="frow"><span class="k">${esc(pc.name)}</span>
        <span class="v">AC ${pc.ac}｜近战 +${pc.atkMelee}｜远程 +${pc.atkRanged}</span></div>
      ${hpBar(pc.hp, pc.maxHp)}
      <div class="frow mt8"><span class="k">豁免</span><span class="v">
        强韧 +${pc.saves.fort}｜反射 +${pc.saves.ref}｜意志 +${pc.saves.will}</span></div>
      <div class="frow"><span class="k">武器</span><span class="v">
        ${esc(pc.weapon)} ${pc.weaponDice ? pc.weaponDice[0] + 'd' + pc.weaponDice[1] : ''}
        （力量 ${pc.strMod >= 0 ? '+' : ''}${pc.strMod}）</span></div>
      <div class="frow"><span class="k">灰线</span><span class="v">${pc.grayCells || 0} 格</span></div>
      <div class="mana-mini mt8">${Object.keys(mana).map((c) =>
        `<span class="mm ${mana[c] ? '' : 'zero'}">${c}×${mana[c]}</span>`).join('')}</div>
      ${Object.keys(pc.statuses || {}).length
        ? `<div class="sm mt8">状态：${Object.values(pc.statuses)
            .map((v) => esc(v.attr || '') + (v.penalty || '')).join('、')}</div>` : ''}`;

    // 敌人卡
    $('#cbEnemies').innerHTML = s.enemies.map((e) => {
      const dead = !e.alive;
      const sel = e.uid === CST.target;
      const tr = (e.traits || []).map((t) => esc(t.label)).join('、');
      return `<div class="foe ${dead ? 'dead' : ''} ${sel ? 'sel' : ''}" data-uid="${esc(e.uid)}">
        <div class="frow"><span class="k">${esc(e.name)}${dead ? ' <span class="dim">（已倒下）</span>' : ''}</span>
          <span class="v">${esc(e.tier || '')}｜AC ${e.ac}｜攻 +${e.atk}</span></div>
        ${hpBar(e.hp, e.maxHp)}
        ${tr ? `<div class="sm dim mt8">${tr}${e.weakpointFound ? ' · <b class="ok">弱点已解析</b>' : ''}</div>` : ''}
      </div>`;
    }).join('') || '<div class="empty">没有异族</div>';
    $('#cbEnemies').querySelectorAll('.foe').forEach((el) => {
      el.onclick = () => {
        const e = s.enemies.find((x) => x.uid === el.dataset.uid);
        if (!e || !e.alive) return;
        CST.target = e.uid;
        renderBattle();
      };
    });

    // 行动按钮
    renderActions();

    // 日志
    const log = $('#cbLog');
    log.innerHTML = (s.log || []).map((l) =>
      `<div class="l ${esc(l.kind)}">${esc(l.text)}</div>`).join('')
      || '<div class="empty">尚无日志</div>';
    log.scrollTop = log.scrollHeight;

    // 结束
    if (s.status !== 'ongoing') showResult();
  }

  function kpi(k, v) {
    return `<div class="kpi"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`;
  }

  function renderActions() {
    const s = CST.snap;
    const pc = s.pc;
    const box = $('#cbActions');
    const myTurn = s.turn === 'pc' && s.status === 'ongoing';
    $('#cbTurnTag').textContent = myTurn ? '轮到你' : (s.turnName + ' 行动中');

    const techs = pc.techniques || [];
    const mana = s.manaPool || {};

    // 战技/动作（与后端 MANEUVERS 保持一致；前端只做"能不能按"的判断，
    // 真正的规则判定在 Python 侧——这里禁用只是提示，不是权威）
    const acts = [
      { key: 'melee_attack', label: '普通攻击', need: null },
      { key: 'ranged_attack', label: '远程攻击', need: null },
      { key: 'analyze', label: '弱点解析', need: null },
      { key: 'power_attack', label: '猛力攻击', need: '猛力攻击' },
      { key: 'deceptive_attack', label: '欺诈攻击', need: '欺诈攻击' },
      { key: 'rapid_strike', label: '连环打击', need: '连环打击' },
      { key: 'allout_strong', label: '全力强击', need: '全力强击' },
      { key: 'allout_determined', label: '精准突击', need: '精准突击' },
      { key: 'whirlwind', label: '旋风切割', need: '旋风切割' },
      { key: 'sneak_attack', label: '偷袭要害', need: '偷袭要害打击' },
      { key: 'defend', label: '举盾防御', need: null },
      { key: 'gray_surge', label: '灰线爆发', need: null },
      { key: 'black_burn', label: '黑色代偿', need: null },
    ];

    const spells = [
      ['火球术', '赤焰爆发', '红'], ['闪电束', '电离长矛', '蓝'],
      ['寒冰锥', '霜蚀锥', '蓝'], ['魔法飞弹', '辉光弹', '白'],
      ['治疗言灵', '生息言灵', '绿'],
    ];

    const btn = (a) => {
      const has = !a.need || techs.includes(a.need);
      const dis = !myTurn || !has;
      return `<button class="act ${dis ? 'dis' : ''}" data-act="${esc(a.key)}"
        ${dis ? 'disabled' : ''}
        title="${has ? (a.desc || a.label) : '未学会「' + esc(a.need) + '」'}">${esc(a.label)}</button>`;
    };

    const sbtn = (tech, label, color) => {
      const has = techs.includes(tech);
      const cost = (tech === '火球术' || tech === '闪电束' || tech === '寒冰锥') ? 2 : 1;
      const enough = (mana[color] || 0) >= cost;
      const dis = !myTurn || !has || !enough;
      return `<button class="act spell ${dis ? 'dis' : ''}" data-act="spell:${esc(tech)}"
        ${dis ? 'disabled' : ''}
        title="${has ? (enough ? label + '（' + color + '色 -' + cost + '，结构税 +1 格）'
          : color + '色法力不足（需 ' + cost + '）') : '未学会「' + esc(tech) + '」'}">
        ${esc(label)}<span class="cost">${color}−${cost}</span></button>`;
    };

    box.innerHTML =
      `<div class="actrow"><span class="grp">战技</span>${acts.map(btn).join('')}</div>
       <div class="actrow"><span class="grp">法术</span>${spells.map((x) => sbtn(x[0], x[1], x[2])).join('')}</div>`;

    box.querySelectorAll('.act').forEach((b) => {
      b.onclick = () => doAction(b.dataset.act);
    });

    const tgt = CST.snap.enemies.find((e) => e.uid === CST.target);
    $('#cbActHint').textContent = myTurn
      ? (tgt ? `当前目标：${tgt.name}` : '没有可选目标')
      : '等待异族行动（可勾掉「自动推进」改为手动）';
  }

  // ------------------------------------------------------------------------
  // 行动
  // ------------------------------------------------------------------------

  async function doAction(action) {
    if (CST.busy || CST.snap.status !== 'ongoing') return;
    CST.busy = true;
    try {
      const params = { sid: 'default', uid: 'pc', action, params: {} };
      if (action === 'gray_surge') params.params = { target: CST.target, cells: 6 };
      else if (action === 'black_burn') params.params = { mode: 'self', to: '蓝', gain: 2 };
      else if (action !== 'defend' && !action.startsWith('spell:治疗')) {
        params.params = { target: CST.target };
      }
      const r = await api('combat.act', params);
      CST.snap = r.snapshot;
      if (!r.ok) msg(r.error || '行动被拒绝', 'warn');
      else msg('');
      // 目标死了就换一个
      const cur = CST.snap.enemies.find((e) => e.uid === CST.target);
      if (!cur || !cur.alive) {
        CST.target = (CST.snap.enemies.find((e) => e.alive) || {}).uid || null;
      }
      renderBattle();
      await maybeAutoEnemies();
    } catch (e) {
      msg('行动失败：' + e.message, 'warn');
    } finally {
      CST.busy = false;
    }
  }

  async function maybeAutoEnemies() {
    if (!$('#cbAutoEnemy').checked) return;
    if (CST.snap.status !== 'ongoing') return;
    if (CST.snap.turn === 'pc') return;
    try {
      const r = await api('combat.enemies', { sid: 'default' });
      CST.snap = r.snapshot;
      const cur = CST.snap.enemies.find((e) => e.uid === CST.target);
      if (!cur || !cur.alive) {
        CST.target = (CST.snap.enemies.find((e) => e.alive) || {}).uid || null;
      }
      renderBattle();
    } catch (e) {
      msg('推进异族回合失败：' + e.message, 'warn');
    }
  }

  // ------------------------------------------------------------------------
  // 结算 / 叙事
  // ------------------------------------------------------------------------

  function showResult() {
    const s = CST.snap;
    const box = $('#cbResult');
    box.style.display = '';
    const win = s.status === 'victory';
    $('#cbResultTag').textContent = win ? '胜利' : '败北';
    $('#cbResultBody').innerHTML = `
      <div class="frow"><span class="k">结果</span><span class="v">${
        win ? '异族已全部倒下' : '旅法师倒下了'}</span></div>
      <div class="frow"><span class="k">回合数</span><span class="v">${s.round}</span></div>
      <div class="frow"><span class="k">剩余生命</span><span class="v">${s.pc.hp} / ${s.pc.maxHp}</span></div>
      <div class="frow"><span class="k">灰线</span><span class="v">${s.grayCells || 0} 格（R11 单调递增，不会回退）</span></div>
      <div class="frow"><span class="k">火花</span><span class="v">${s.spark != null ? s.spark : 0}%</span></div>
      <div class="sm dim mt8">${
        win ? '火花已按变异谱系回写面板（点燃后不再增长，R8）。'
             : '这一场没能活着走出去——灰线不会因此回退。'}</div>`;
    $('#cbNarrate').onclick = narrate;
    $('#cbCopy').onclick = copyNarrate;
    $('#cbAgain').onclick = again;
  }

  async function narrate() {
    try {
      const r = await api('combat.narrate', { sid: 'default' });
      const el = $('#cbNarrateText');
      el.style.display = '';
      el.textContent = r.text || '';
      msg('叙事文本已生成（只写可观测行为，不写独白）', 'ok');
    } catch (e) {
      msg('生成失败：' + e.message, 'warn');
    }
  }

  async function copyNarrate() {
    const t = $('#cbNarrateText').textContent;
    if (!t) { await narrate(); }
    try {
      await navigator.clipboard.writeText($('#cbNarrateText').textContent);
      msg('已复制到剪贴板', 'ok');
    } catch { msg('复制失败，请手动选中文本', 'warn'); }
  }

  async function again() {
    try { await api('combat.end', { sid: 'default' }); } catch { /* 已结束 */ }
    CST.snap = null;
    CST.target = null;
    $('#cbBattle').style.display = 'none';
    $('#cbSetup').style.display = '';
    msg('配置保留，可直接再开一场', 'ok');
  }

  // 暴露给 app.js 的 PAGE_LOADERS
  window.loadCombat = loadCombat;
})();
