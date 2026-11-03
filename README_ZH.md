# Citi Bike 需求预测与调运优化

本项目研究完成骑行预测、历史状态证据缺口和运输延迟如何影响受约束调运。方法包括时间顺序计数预测、整数规划、三期随机MPC、配对骑行事件及货车取送仿真。

[英文入口](README.md) · [两页研究摘要](application/RESEARCH_BRIEF.pdf) · [十页技术报告](reports/technical_report.pdf) · **[贡献与工具使用](CONTRIBUTIONS.md)**

## 主要结果

| 评估 | 样本 | 结果 |
|---|---|---|
| 2025年11–12月预测 | 43,950站点小时 | XGBoost借车MAE 3.418，对照上一小时4.476，降低23.6% |
| 冻结模型后的2026年1月外部评估 | 22,320站点小时 | MAE 2.705，对照3.235，降低16.4%，无重新训练 |
| 15分钟初态证据不支持的测试子集 | 10,819行 | XGBoost MAE 1.621，对照1.480，模型排序反转 |
| 道路货车服务情景 | 48小时、30站、181条已核验路线 | 不调运服务代理94.776%，道路MILP 94.498%，保留负结果 |

2026年1月方案、站点和模型哈希在下载目标数据前已公开冻结。2025年的证据分层、天气、时长、MPC、路线和扩容敏感性为已查看测试集上的探索性分析，分别报告。

## 数据与验证

2025年官方骑行45,771,102行，经审计保留45,588,101条；训练期筛选30站，构建262,800行小时面板。1–8月训练、9–10月验证、11–12月测试，全部lag/rolling来自目标小时前。完整计数与配对回放覆盖1,465个测试小时；60项自动测试及远程CI通过。

新增历史证据包括291万条状态变化、120个官方容量点和180个状态点。原19,634个未知小时仅2个满足声明的12个五分钟箱标准，19,632个保留未知；采样支持不等于连续营业证明。该全年标准与预测测试的15分钟初态标准不同。

## 复现

Python 3.12、Linux；安装精确依赖并检查：

```bash
./scripts/install.sh
.venv/bin/python -m pytest -q
# 独立重跑冻结的跨年评估：
.venv/bin/python scripts/external_202601.py
```

仓库已含小型冻结模型与此前168小时上下文，该外部评估只需下载353.83MB的2026年1月数据。

全年复现入口：

```bash
.venv/bin/python -m src.download --year 2025
.venv/bin/python -m src.prepare --config configs/official_counts.json
./scripts/official_pipeline.sh
./scripts/all_research.sh
```

原2025骑行ZIP约8.93GB，历史状态原文件约0.53GB；大数据不提交到Git。组合脚本的组成研究命令已逐项执行，未宣称已验证全新机器上的整段重跑。严格营业小时研究需要可靠运营日历；`recorded_event_counts`明确研究保留档案计数，不将原始未知营业标记改为已知。

## 方法与解释

优化使用相同场景请求和资源条件进行策略比较。配对事件拒借后取消对应归还，并记录客户在途、外部边界、暂存和货车携货。道路情景采用当前OSRM驾驶代理、虚拟车库及初始实测可用容量冻结等假设。模型误差、人工权重和服务代理不是现实缺车损失或美元成本。

持续采集的目标为本地60秒、GitHub五分钟。实际时间戳、缺口与触发类型见[采集审计](reports/validation/monitoring_audit.json)，不从配置推断长期连续性；当前采集也不倒补2025状态。

## 阅读入口

[历史证据](reports/historical_evidence_and_extensions.md) · [道路服务与采集](reports/operations_completion.md) · [逐项状态](reports/task_status.md) · [结果表](reports/results/) · [数学模型](reports/optimization_formulation.md) · [数据字典](DATA_DICTIONARY.md) · [申请材料](application/README.md)

数据遵循原运营方条款；CityBikes衍生数据库的ODbL说明见[data/historical/DATABASE_NOTICE.md](data/historical/DATABASE_NOTICE.md)，道路与天气来源亦附带注明。
