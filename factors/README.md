# 拥挤度因子库

[返回仓库首页](../README.md) · [构建方法](../docs/research.md) · [归因与检验](../docs/deep-dive.md) · [来源索引](../docs/sources.md)

[因子字典 CSV](catalog.csv) 共 **23 项**，可用 Excel 筛选。字段包括公式、最低输入、覆盖、单位、研究用途和验证状态。直接日频指标由 [参考计算](calculate.py) 提供。候选因子当前记录定义和检验边界。

## 因子怎么用

| 标识 | 名称 | 角色 | 状态 |
|---|---|---|---|
| H | 相对换手热度 | 主指标 | 可复算 |
| Q | 相对换手 | 主指标 | 可复算 |
| S | 行业成交份额 | 基准 | 可复算 |
| S_joint | 可比样本成交份额 | 中间量 | 可复算 |
| C_joint | 可比样本自由流通份额 | 中间量 | 可复算 |
| G | 头部成交超额 | 结构指标 | 可复算 |
| B | 非头部上涨广度 | 结构指标 | 可复算 |
| D | 无方向成交偏离 | 诊断 | 可复算 |
| U_plus | 上涨成交占比 | 诊断 | 可复算 |
| top5_amount_share | 当日头部成交集中度 | 诊断 | 可复算 |
| Q_rest | 剔除行业后的相对换手 | 候选 | 待检验 |
| effective_names | 有效成交股数 | 候选 | 待检验 |
| sector_rotation | 全市场行业成交换位 | 候选 | 待检验 |
| market_sector_hhi | 市场行业成交集中度 | 候选 | 待检验 |
| breadth_ex_market | 非头部广度相对市场 | 候选 | 待检验 |
| residual_sync | 成分股残差相关 | 候选 | 待检验 |
| market_pc1 | 市场第一主成分吸收率 | 候选 | 待检验 |
| sell_impact | 下跌日价格冲击代理 | 候选 | 待检验 |
| sellability | 受限交易覆盖 | 候选 | 待检验 |
| exit_days | 持仓退出容量 | 候选 | 待检验 |
| margin_intensity | 融资买入强度 | 候选 | 待检验 |
| etf_creation | ETF净申赎估计 | 候选 | 待检验 |
| holding_overlap | 机构共同持仓 | 候选 | 待检验 |

**计算链**。逐股成交额和上日自由流通市值先在同池聚合为 S_joint 和 C_joint，两者相除得到 Q。五个交易日的 Q 平均值按此前历史作中秩，得到 H。独立保留市场分母、原始 S、固定头部 G、非头部 B 和覆盖率。源字段见研究正文。

## 样本合约和单位

- StockDay 每日包含市场期望股票池的一行一股，未分类股行业填 None。停牌成交经确认后填 0。未知值填 None，NaN 和无穷会报错。成交与市值同为元或同为亿元，收益以小数表示。
- cap_eligible 仅在确认期初自由流通值不适用时设 False，例如首个挂牌日。供应商缺数仍为 True，将留在覆盖分母。来源、本地交易日历及当时可得状态由调用方对齐。
- freeze_head 输入当月首日有效名单和此前 20 个交易日的成交序列。输出月度冻结名单或 None。样本统计分母以入选排名的合格成员数为准。daily_factors 只取当日仍有效的行业成员，月内新入组股票进入非头部。
- daily_factors 中 S、D、G、B 和覆盖率都为 0–1 比例或带符号比例。G ×100 转成百分点。Q 输出倍数。H 输出 0–100。
- 通过 trailing_mean 计算五日 Q，再将当日结果及**过去**按交易日排齐的平滑序列传入 historical_midrank。前值、当前值和窗口前的样本不能混入。连续同值分位为 50。

## 最小复算

    python -m unittest discover -s tests
    python scripts/check_examples.py --self-test

下面为四股教学例。金额单位为亿元。A、B 是外部已冻结的示例头部，正式名单可由 freeze_head 构建。

    from factors.calculate import StockDay, daily_factors, historical_midrank, trailing_mean

    rows = [
        StockDay("A", "电子", 40, 10, .02),
        StockDay("B", "电子", 30, 10, -.01),
        StockDay("C", "电子", 20, 10, -.01),
        StockDay("D", "电子", 10, 10, .01),
        StockDay("M", None, 900, 360, .01),
    ]
    result = daily_factors(rows, "电子", head={"A", "B"})
    level = trailing_mean([result["Q"]] * 5)
    heat = historical_midrank(level, [1.0] * 200)

得到 S=10%、Q=1、D=0.20、上涨成交50%、非头部上涨50%、G=+20 个百分点，H=50。若将四股成交改为 10、20、30、40，行业成交与市场分母保持一致，G 变为 −20 个百分点。样例和测试验证计算行为。增量效果仍需真实 A 股样本外检验。
