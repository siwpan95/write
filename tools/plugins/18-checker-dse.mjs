/**
 * 插件 18 · checker-dse —— 叙事内容包校验（dse-core 三道门）
 *
 * 把 dse-core 的 check / traverse / coverage 接进全仓闸门。
 *
 * 为什么是「增强层」而不是核心内核
 * ------------------------------
 * 核心内核（doc_review / pkm / metrics / rules / prose-style）只用标准库，
 * 换机即跑。dse-core 需要 PyYAML + jsonschema，故归为增强层：
 *   · 依赖由 tools/bootstrap.sh / .ps1 按 requirements.txt 安装；
 *   · 适配器以**子进程调用 dse CLI**实现，检查器进程不 import dse_core；
 *   · 依赖缺失时适配器报 ERROR 并给安装指引 —— **不静默跳过**
 *     （廓者未名夜的教训：不在扫描视角内的「通过」等于闸门失效）。
 */
export const CheckerDse = {
  name: 'checker-dse',
  inject: ['config', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const adapter = config.adapter || './tools/checkers/dse_check.py'
    // 内容包工程目录（相对仓根）；内容包是仓内资产，不按项目切分
    const project = config.project || './dse-content'

    async function run(projectIds = []) {
      // 内容包是**仓级**维度，与具体小说项目无关 —— projectIds 一律忽略
      // runner 会把 args 当作脚本的 argv 传给 Python：
      //   argv[1] = 仓根，argv[2] = 内容包工程目录（相对仓根）
      // 注意：不能只传 project —— 那会被适配器当成仓根，
      // 导致 root="./dse-content" 再拼一次变成 "./dse-content/dse-content"。
      return ctx.runner.run('dse', adapter, [ctx.config.root, project], { cwd: ctx.config.root })
    }

    ctx.checkers.register({ id: 'dse', name: '叙事内容包校验（dse-core 三道门）', run })
  },
}

export default CheckerDse
