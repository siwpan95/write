const fs = require('fs');
const { Graphviz } = require('@hpcc-js/wasm');

const dot = fs.readFileSync('graph.dot', 'utf8');

Graphviz.load().then(gv => {
  const svg = gv.layout(dot, 'svg', 'dot');
  fs.writeFileSync('graph.svg', svg);

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>通用模板包 ↔ 二十一世纪奇门遁甲 结构映射图</title>
<style>
  body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0; background: #fafafa; color: #222; }
  .header { padding: 16px 24px; background: #1a237e; color: #fff; }
  .header h1 { margin: 0; font-size: 18px; font-weight: 600; }
  .legend { padding: 12px 24px; background: #fff; border-bottom: 1px solid #e0e0e0; font-size: 13px; line-height: 1.8; }
  .legend b { color: #1a237e; }
  .svgwrap { padding: 16px; overflow: auto; }
  .foot { padding: 10px 24px; color: #777; font-size: 12px; }
  code { background: #eee; padding: 1px 5px; border-radius: 3px; font-family: Consolas, monospace; }
</style>
</head>
<body>
  <div class="header"><h1>通用模板包 v3.0 ↔ 《二十一世纪奇门遁甲》结构映射图</h1></div>
  <div class="legend">
    <b>左（蓝）</b>：通用模板包 00–12 —— 规范 / 工序 / 空白骨架，三书共享复用。<br>
    <b>右（橙）</b>：《二十一世纪奇门遁甲》实例，含 <b>规划集</b>（工作文档 00–12）/ <b>bible/</b>（单一事实源 SSOT）/ <b>落地正文</b> / <b>素材归档</b>。<br>
    <b>蓝色实线</b>：模板 → 实例 的派生映射；多模板汇聚点（如 <code>00_新书立项书</code>、<code>bible/长弧规划</code>、<code>11/12</code>）表示多个模板共同作用于同一样本。<br>
    <b>绿色虚线</b>：SSOT 纪律「正文为准 · 回填设定」—— 落地正文是最终基准，bible/ 与其保持一致。<br>
    <b>指令⑦ 归位</b>：原 <code>02_世界观设定集</code> / <code>03_人物设计书</code> / <code>05_节拍表</code> 经 <code>git mv</code> 落入 <code>bible/</code>（节点已标注「←原XX」）。
  </div>
  <div class="svgwrap">__SVG__</div>
  <div class="foot">Graphviz (WASM / @hpcc-js/wasm) 渲染 · 数据源：D:\projects\repos\write 仓库现状（HEAD 含 commit 7515e29 / be66219）</div>
</body>
</html>`.replace('__SVG__', svg);

  fs.writeFileSync('index.html', html);
  console.log('SVG bytes =', svg.length, '| index.html written');
}).catch(e => { console.error(e); process.exit(1); });
