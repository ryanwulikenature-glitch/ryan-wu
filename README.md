# 当前交付状态（历史证据与扩展版）

**54 项测试通过，所有下列代码和实验均已实际执行。** 原 2025 Trip Histories 全年基线保留；另已接入 CityBikes 12 个月、30 站 2,907,502 条历史状态变化样本，及 4 份信息/6 份状态官方存档。

- [10 页英文报告](reports/technical_report.pdf)
- [历史证据、来源和全部扩展结果](reports/historical_evidence_and_extensions.md) · [离线 HTML](reports/historical_evidence_and_extensions.html)
- [道路运输、持续采集与最后验收](reports/operations_completion.md) · [离线HTML](reports/operations_completion.html)
- [逐项验收表](reports/task_status.md) · [所有核心/扩展结果小表](reports/results/)

库存、容量和营业状态现已有**真实历史点证据**，但不能声称全年连续无缺口。原 19,634 个未知小时中 3,406 个有较弱营业点证据，只有 2 个满足声明的12个五分钟箱支持标准；其余不伪造为已知。15,222 个内部容量不一致样本被排除，历史状态校准最终覆盖 260 个共同测试小时。

新增已运行：24小时前 GFS 预报天气消融；6 个时长阈值全原始数据重算；3小时/4场景随机 MPC；两卡车容量/行驶/装卸/工时约束的原子取送路径可行性审计；60站网络实验；官方26c多边形核验；第三个已执行 notebook。另已完成有向OSRM道路、共同装载卡车与客户事件的48小时联立服务实验，独立核对181条路线；本场景不调运优于道路策略，负结果保留。库存采集已在本地60秒目标进程和GitHub五分钟目标工作流部署，实际成功归档已下载重建；目标调度不等于已证明长期连续覆盖。

## 扩展复现

当前实例已有全部运行结果，无需重跑。若从头复现，在仓库根目录安装依赖后执行：

```bash
./scripts/install.sh
./scripts/all_research.sh
```

该组合脚本的组成命令均已逐项执行；原始约8.93GB骑行ZIP及约0.53GB历史状态原文件不重复打入交付ZIP，完整重跑会按来源清单下载。原始清洗较耗时，已有匹配缓存可复用。历史数据库衍生部分遵循ODbL-1.0，见data/historical/DATABASE_NOTICE.md；软件和独立官方快照不因此被重授权。

要消除剩余连续状态证据缺口，需未去重的原始GBFS心跳、只改营业标记的更新或维护记录。精确请求草稿见reports/data_request_draft.md，**未擅自对外发送**。

---

# NYC Citi Bike Demand Forecasting & Optimization

基于上传的《CitiBike 项目步骤与实施细节》实现的 Python 研究工程。

**当前状态：代码、环境、合成验证及真实 2025 全年档案计数实验均已实际运行。** 当前网络访问已恢复，之前的 HTTP 403 已解除。`outputs/demo` 全部是合成数据结果，不能用于声称 Citi Bike 真实缺车率或实际运营改善。详见 [任务验收表](reports/task_status.md)。

## 环境与快速复现

Python 3.12，Linux，建议 4 CPU / 8 GB 以上内存；全年原始数据处理建议留出 40 GB 磁盘，实际取决于官方文件大小。当前环境使用现有 `/workspace/ryan-wu` 检出，不需要新建 worktree。

```bash
cd /workspace/ryan-wu
./scripts/install.sh
./scripts/validate.sh
.venv/bin/python scripts/event_demo.py
```

`install.sh` 创建隔离虚拟环境并安装精确版本的 `requirements-lock.txt`，保留 TLS/包完整性校验。`validate.sh` 启用 pipefail，依次运行 pytest、全年合成预测、336 小时三策略仿真、21 个敏感性/消融场景（各 48 小时）、报告及独立输出核对。重复运行会对不含求解耗时的仿真结果计算指纹，检查可复现性。数据生成固定 seed=2025，30 个合成站点、2025 全年 8760 UTC 小时。

可分别执行：

```bash
.venv/bin/python -m src.make_demo
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python -m src.train --data data/demo --out outputs/demo --config data/demo/config.json
.venv/bin/python -m src.simulate --predictions outputs/demo/test_predictions.csv.gz --stations data/demo/stations.csv --config data/demo/config.json --out outputs/demo --hours 336
```

原始数据、模型和大输出在 `.gitignore` 中排除；当前工作区与交付压缩包保留已运行的 demo 结果。已按新增清单要求提交并推送至 GitHub main。

## 真实数据流程

官方介绍：https://citibikenyc.com/system-data 。下载路径模板：`https://s3.amazonaws.com/tripdata/2025MM-citibike-tripdata.zip`。只使用 NYC，不使用 `JC` 数据。数据须遵守官方使用条款；本工程不附第三方原始数据。

环境设置中需允许 `citibikenyc.com`、`s3.amazonaws.com`；可选当前 GBFS 需 `gbfs.citibikenyc.com`。当前环境已可访问官方源；先前域名草稿与网络阻塞记录仅为历史诊断。下载器验证 HTTPS、ZIP CRC、记录 SHA256/URL/时间，并原子落盘，可断点至文件级重新执行。

```bash
.venv/bin/python -m src.download --year 2025 --months 1 2 3
# 核对 ZIP 内多个 CSV 的列名后补齐全年：
.venv/bin/python -m src.download --year 2025
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MPLCONFIGDIR=/tmp/citibike-mpl \
  .venv/bin/python -m src.run --calendar /path/to/verified_operating_calendar.csv
```

运营日历 CSV 格式：`station_id,hour,active_flag`，hour 必须带时区，active_flag 为 0/1，只填写有证据的运营小时，不可为了跑通制造“营业”事实。未提供日历时，panel 仅将有观测事件的小时视为可观测，其他小时目标保留缺失。观察到零行程不自动证明站点正常运营；严格的仿真拒绝不完整的站点小时与不连续时段。没有运营证据时，仍可清洗与在可观测子集上预测，但须如实说明选择偏差；不能强制补零后声称严格通过全年验收。

`src.run` 为严格全流程入口，仿真前置条件不满足时会明确失败；独立清洗/训练命令如下，可保留独立进展：

```bash
.venv/bin/python -m src.prepare --calendar /path/to/verified_operating_calendar.csv
.venv/bin/python -m src.train
```

`--allow-incomplete` 仅用于明确标注的探索性处理，不是完整年度验收。时长阈值默认 180 分钟；30/60/90/120/180/360 分钟的真实原始数据重算与预测/仿真敏感性均已运行。站点坐标框是 Manhattan 附近矩形，不是官方行政边界；同一 ID 的训练期小时坐标漂移超过 0.5 km 会排除。容量统一假设 25，不使用当前 GBFS 冒充历史容量。

## 实验协议

- **预测**：Jan–Aug Train，Sep–Oct Validation，Nov–Dec Test；按 NYC 本地月份分段、UTC 连续 lag。分别预测 departures/arrivals，Last Hour、Seasonal Naive、正则化 Poisson GLM、XGBoost。lag/rolling 全部来自目标小时前，encoder/imputer/scaler 仅训练期拟合；验证选参、train+validation 最终重拟合。测试滚动一小时预测可读取过去已观测测试小时，不使用未来。
- **指标**：MAE、RMSE、WAPE；总计、早晚高峰、工作日/周末、高低训练需求站、11/12 月。WAPE 分母为零时输出空值。train 指标仅为拟合诊断。
- **调运**：No Rebalancing、Distance Greedy、MILP。相同库存、容量、预算、距离半径、初始比例与预测信息。只允许供给→需求单向边，不允许站内转运或中转。MILP 未成功会记录原状态并回退 Greedy，单独统计。
- **主仿真**：明确标为 **hourly count-based scenario simulation**，小时边界瞬时调运，小时内随机交错借/还。相同 seed 和样本 hash 跨策略共享。独立到达是外生供给，只检查站点库存账，不宣称全车队因果守恒。
- **配对事件升级**：`src.event_replay` 通过 ride_id 取消被拒骑行的到达，维护在途及站外暂存车辆；外来骑行是边界流入，区域外归还是边界流出，初始在途骑行计入初始车队。满桩归还在本轮始终暂存、不重新分配。固定同一时间先归还后借出。与主小时模型分开存储。
- **敏感性**：容量、预算、半径、初始库存、惩罚权重、种子、测试日期；预测替换为季节朴素、仅借出预测、固定 XGBoost、不可部署 Oracle。所有场景运行前保存配置。Oracle 只提供未来信息参照，因目标是代理目标，不能当作精确服务率上界。测试期敏感性是探索性结果，不是新的未触碰测试集。
- **不确定性**：按本地日期做配对块 bootstrap，报告日级情景目标差的 95% 区间；不将站点小时当独立样本。随机种子重复量化事件顺序敏感性，不能消除历史库存不可观测的偏差。

## 结构和交付

```text
configs/base.json           预先固定的假设与约束
src/download.py             官方下载、CRC、SHA256 清单
src/prepare.py              分块清洗、SQLite 全局去重、选站、panel
src/features.py             时间切分与严格滞后特征
src/train.py                四模型、验证选参、模型保存与分层指标
src/optimize.py             MILP / Greedy / 约束校验
src/simulate.py             小时情景、移动记录、库存追踪、配对区间
src/event_replay.py         ride_id 因果配对升级
src/experiments.py          固定场景与消融
src/report.py               EDA、图表、自动生成技术报告
notebooks/01_eda.ipynb      已运行的合成 EDA
notebooks/02_eda_official.ipynb 已运行的官方数据 EDA
reports/                    方法说明、验收表、验证记录
outputs/demo/               合成数据的完整运行产物
outputs/official/           已生成的真实数据实验、模型和全部结果
tests/                     清洗、泄漏、MILP、仿真守恒及失败状态测试
```

[数据字典](DATA_DICTIONARY.md) · [数学模型](reports/optimization_formulation.md) · [运行报告](reports/final_report.md) · [逐项状态](reports/task_status.md)

## 解释边界与后续

历史已完成骑行不包含所有潜在需求。新增版本已找到并接入 2025 年历史库存/容量/状态变化记录，但归档去重导致连续运营证据不完整，仍不能识别全部真实被拒需求。服务代理、人工惩罚与 bike-km 都只属于给定情景，不是实际用户损失、美元成本或货车路程。可选天气需要带预测发布时间的可用特征；本工程没有使用事后天气。新增版本已实现历史证据接入、24小时前天气预报消融、三期随机MPC、受限卡车取送路径审计、官方多边形核验与60站扩展；当前GBFS采集器也已实采。道路代理与服务联立、定时采集部署已完成；真实运营车辆调度、2025交通、长期无间断监测和所有历史状态仍未被证明。

## 明确的档案计数实验模式

在缺少历史运营日历时，可使用 **recorded_event_counts** 配置，研究清洗后档案中的完成骑行计数。审计 panel 保留未知运营标记；仅在此模式的建模副本中，目标及历史特征改用 observed_departures/observed_arrivals。零表示没有保留下来的骑行记录，不能解释成确认营业、零潜在需求或真实无缺车。该口径和严格运营小时目标不同，结果须单独标注。

```bash
# 首次：分块清洗 + 全测试期建模与仿真
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MPLCONFIGDIR=/tmp/citibike-mpl \
 .venv/bin/python -m src.run --config configs/official_counts.json --hours 1465
# 若清洗结果与该配置一致，可复用：
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MPLCONFIGDIR=/tmp/citibike-mpl \
 .venv/bin/python -m src.run --config configs/official_counts.json --prepared --hours 1465
# 配对事件升级，读清洗分区并独立验证车队账：
.venv/bin/python scripts/official_event_replay.py
.venv/bin/python scripts/check_official_outputs.py
.venv/bin/python scripts/execute_notebook.py notebooks/02_eda_official.ipynb
```

预处理将所有小时事件分区落盘，只在内存合并选定的 30 个站点；训练期按 chunk/月压缩坐标中位数及 min/min、max/max 对角点，使用这些代理点检查漂移，避免全城 station-hour 数据一次性加载。该规则对零星坐标错误比较保守，也不等于经过验证的历史站点迁移记录。

正式验证：54 项测试通过；官方 12 月份清单、45,588,101 条有效行程、30 个站、43,950 测试站点小时、三策略各 1,465 小时计数及配对回放、21 场景均经实际运行和独立核对。查看 reports/项目总结.md 或可离线打开的 reports/项目总结.html。运行报告中的服务指标均是假设情景代理。

## 新清单补充交付

- 英文 8 页报告：[technical_report.pdf](reports/technical_report.pdf)，由 scripts/english_report.py 从真实结果生成。
- 具体高峰站点与工作日/周末解读：reports/eda_business_findings.md；对应额外两张图在 outputs/official/figures。
- 英文复现入口 README_EN.md；关键结果的小文件已同步到 reports/results，便于在 GitHub 直接查看。
- 持续GBFS采集已部署：`.venv/bin/python services/collectorctl.py status` 查看本地60秒目标进程；[GitHub工作流](.github/workflows/collect-gbfs.yml) 以5分钟为目标，独立写入 [gbfs-history](https://github.com/ryanwulikenature-glitch/ryan-wu/tree/gbfs-history)。实际时间窗/成功运行/恢复收据见 [最后工程补充](reports/operations_completion.md)，没有宣称已积累长年库存。原两轮全网试采仍保留在 data/gbfs。
- 原受限原子取送与三期随机MPC保留；新增两辆容量6、道路行驶/装卸/司机工时/携货重送的共同装载取送启发式已联立服务仿真。当前OSM驾驶代理、虚拟车库与固定容量是场景假设，不是实际运营调度。

GitHub 已发布：https://github.com/ryanwulikenature-glitch/ryan-wu （main）；英文报告和结果小表在仓库内可直接查看。
