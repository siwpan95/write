/**
 * 插件 17 · checker-prose-style —— 正文文风红线检查器
 *
 * 校验各项目连载正文是否符合《通用模板包》05 文风卡与 06 §8.3 的红线。
 *
 * 与其它检查器的分工：
 *   doc-review    查错别字/时间矛盾/数字口径/术语/重复/结构
 *   consistency   查章号/字数/标点/项目结构一致性
 *   prose-style   查**文风红线**：禁用词、比喻词、招牌句式密度、破折号连用
 *
 * 口径说明（重要）：
 *   本检查器只把**模板包红线项**计入汇总。human-writing 技能的硬禁令
 *   （中文冒号/破折号/翻案句/硬停词/绝对禁词）适用对象是「论坛散文成稿」，
 *   套到网文正文上大量是假阳性——网文里冒号用于引出感知与列举、破折号用于
 *   语义掉头，均为 05 §1.1 明文允许的修辞。故这些项不进汇总报告，
 *   需要时用 `python tools/checkers/prose_style_check.py --root .` 单独查看。
 *
 *   另：各项目自带更细的风格口径（如《小说/设定与参考/叙事风格修正手册.md》），
 *   项目级口径优先于通用模板包。本检查器只兜底通用红线。
 */
export const CheckerProseStyle = {
  name: 'checker-prose-style',
  inject: ['config', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const adapter = config.adapter || './tools/checkers/prose_style_check.py'

    async function run() {
      // 文风红线是全仓维度（正文散在多个项目），不按项目切分
      return await ctx.runner.run(
        'prose-style',
        adapter,
        ['--root', '.', '--protocol'],
        { cwd: ctx.config.root }
      )
    }

    ctx.checkers.register({
      id: 'prose-style',
      name: '正文文风红线（05 文风卡禁用词/比喻词/招牌句式/破折号连用）',
      run,
    })
  },
}

export default CheckerProseStyle
