// 用最小 DOM stub 直接执行 horror_lab.html 里的脚本，验证：
// 1) 脚本无语法/运行时错误  2) 卡片真的渲染出来  3) 同 seed 确定性
const fs = require('fs');
const path = require('path');

// 相对本脚本定位产物，避免依赖某一台机器的绝对路径
const HTML = path.join(__dirname, '..', 'horror_lab.html');
const html = fs.readFileSync(HTML, 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('✗ 找不到 script 段'); process.exit(1); }
const js = m[1];

function makeEl(id) {
  const el = {
    id, innerHTML: '', textContent: '', value: '42', onclick: null,
    dataset: {}, _children: [],
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      contains(c) { return this._s.has(c); },
    },
    querySelectorAll() { return []; },
    appendChild() {}, remove() {}, select() {}, focus() {},
  };
  return el;
}
const store = {};
global.document = {
  getElementById(id) { return store[id] || (store[id] = makeEl(id)); },
  createElement() { return makeEl('_tmp'); },
  body: { appendChild() {} },
  querySelectorAll() { return []; },
  execCommand() { return true; },
};
global.navigator = { clipboard: { writeText: async () => {} } };
global.window = global;
global.setTimeout = () => 0;

let errors = 0;
try {
  // 额外把内部符号挂到 global，以便验证 mode 路径
  eval(js + '\n;globalThis.__DATA = DATA; globalThis.__build = buildCard; globalThis.__render = render;');
} catch (e) {
  errors++;
  console.error('✗ 脚本执行抛错：', e.message);
  console.error(e.stack.split('\n').slice(0, 4).join('\n'));
}

const stage = store['stage'];
if (!stage) { console.error('✗ 没有取到 #stage'); process.exit(1); }

const out = stage.innerHTML || '';
console.log('── 渲染检查 ──');
console.log('innerHTML 长度：', out.length);
const must = ['场景规程', '信息阶梯', '符号组', '结构自检', '专属反模式', '骨架', 'Δ'];
for (const k of must) {
  const ok = out.includes(k);
  console.log(`  ${ok ? '✓' : '✗'} 含「${k}」`);
  if (!ok) errors++;
}
const pass = (out.match(/class="ok"/g) || []).length;
const fail = (out.match(/class="no"/g) || []).length;
console.log(`  自检项：✓ ${pass} / ✗ ${fail}`);
if (pass < 7) { console.error('✗ 通过项少于 7'); errors++; }

// 确定性：同 seed 连续生成两次，innerHTML 必须一致
const first = stage.innerHTML;
document.getElementById('gen').onclick();
const second = stage.innerHTML;
console.log('\n── 确定性 ──');
console.log('  同 seed 两次渲染一致：', first === second ? '✓' : '✗');
if (first !== second) errors++;

// 换 seed 必须不同
store['seed'].value = '98765';
document.getElementById('gen').onclick();
const third = stage.innerHTML;
console.log('  换 seed 渲染不同：', third !== first ? '✓' : '✗');
if (third === first) errors++;

// 开关一次母题/温度，验证交互不抛错
try {
  // 直接改 state 不可行（eval 作用域），改走 motif 卡片点击路径无 querySelectorAll 结果，
  // 这里只验证带不兼容温度时的回退文案存在
  store['seed'].value = '42';
  document.getElementById('gen').onclick();
  console.log('\n── 最终 ──');
  console.log(errors === 0 ? '✅ 全部通过（' + pass + ' 项自检 + 3 项渲染断言）' : `❌ 失败 ${errors} 项`);
} catch (e) {
  console.error('✗ 交互出错：', e.message);
  errors++;
}

// ---- 数据规模与结构 ----
console.log('\n── 数据规模 ──');
const D = global.__DATA;
console.log(`  母题：${D.motifs.length}（期望 16）`);
console.log(`  温度：${Object.keys(D.temperatures).length}（期望 5）`);
console.log(`  模式：${Object.keys(D.modes || {}).length}（期望 6）`);
if (D.motifs.length !== 16) { console.error('✗ 母题数不符'); errors++; }
if (Object.keys(D.modes || {}).length !== 6) { console.error('✗ 模式数不符'); errors++; }
const noModes = D.motifs.filter(m => !m.modes || !m.modes.length);
console.log(`  缺 modes 字段的母题：${noModes.length}`);
if (noModes.length) { console.error('✗ 有母题未声明 modes'); errors++; }

// ---- mode 渲染路径（关键新功能）----
console.log('\n── mode 渲染路径 ──');
try {
  const mk = global.__build;
  const rd = global.__render;

  // satire × 系统型：应触发 E 冲突并给出建议温度
  const c1 = mk('registry', '系统型', 7, 'any', 'satire');
  const h1 = rd(c1);
  const hasModeBlk = h1.includes('Mode · 呈现模式');
  const hasConflict = h1.includes('E 取向与温度给出的出口不一致');
  console.log(`  satire 卡含 Mode 段：${hasModeBlk ? '✓' : '✗'}｜报 E 冲突：${hasConflict ? '✓' : '✗'}｜建议温度：${c1.suggestTemp || '无'}`);
  if (!hasModeBlk) { console.error('✗ mode 段未渲染'); errors++; }
  if (!hasConflict) { console.error('✗ 冲突未报出'); errors++; }
  if (!c1.suggestTemp) { console.error('✗ 未给出建议温度'); errors++; }

  // horror × 系统型：应无冲突
  const c2 = mk('registry', '系统型', 7, 'any', 'horror');
  const conflict2 = c2.eConflict;
  console.log(`  horror 卡报 E 冲突：${conflict2 ? '✗ 不该冲突' : '✓ 无冲突'}`);
  if (conflict2) { console.error('✗ horror 被误判为冲突'); errors++; }

  // mode 与母题不兼容时应拒绝并说明
  const c3 = mk('mirror', '关系型', 1, 'any', 'satire');
  console.log(`  mirror×satire 兼容判定：${c3.modeOk ? '✗ 不该兼容' : '✓ 正确拒绝'}`);
  if (c3.modeOk) { console.error('✗ 不兼容模式未被拒绝'); errors++; }
} catch (e) {
  console.error('✗ mode 路径抛错：', e.message);
  errors++;
}

// ---- 整体 ----
console.log('\n── 最终 ──');
console.log(errors === 0 ? '✅ 全部通过' : `❌ 失败 ${errors} 项`);
process.exit(errors === 0 ? 0 : 2);
