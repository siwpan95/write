# 1. 修一致性（半天）
python tools/lint/check_docs.py --root docs

# 2. 收尾 M13（半天）
python tools/lint/blind_rank.py ranks.csv --expect base=1,cross_axis=5

建议把 lint 接进流程：FAIL 归零才允许更新 00 台账的 ✅。这是项目最缺的一道校验环节——一天五轮迭代，台账更新快于文档收敛，这本来就是当前问题的成因。