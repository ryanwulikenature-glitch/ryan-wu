# 历史证据与扩展研究：最终核对

## 已找到并接入的历史数据

- CityBikes 2025 年纽约 12 个月历史 Parquet，匹配全部 30 个研究站点，2,907,502 条历史状态变化记录。包含可借车辆、空桩、报告容量、租还车标记及源时间戳。
- 2025 年官方 GBFS 的互联网存档：4 份 station_information、6 份 station_status；所选站点得到 120 条容量点证据和 180 条库存/营业标记点证据。使用官方 short_name → UID 映射并核对坐标，不凭站名猜测。
- 15,222 条记录出现车辆/空桩与报告容量不一致，明确排除出有效校准样本。真实源数据也需要审计，不能直接把字段当无误的物理真值。
- CityBikes 容量与之前一小时内可匹配的官方容量点对照：102/102 相等；未匹配和不等的记录全部保留。不同时间的近邻比对不是同时刻完全一致性的保证。

## 哪些运营缺口能恢复

```csv
evidence_class,station_hours
no_fresh_consistent_point,16198
some_active_points_only,3404
at_least_one_restricted_point,30
all_12_5min_bins_active,2
```

原 19,634 个未知小时中，3,406 个有新鲜、内部一致且未观测到限制的营业点记录；其中只有 2 个满足已声明的全部 12 个五分钟箱采样支持条件。单个营业点不能证明整个小时一直营业；强采样支持也不是连续每秒在线的证明。剩余 19,632 个小时仍不满足这一强标准，保留未知，未伪造零需求。

根本原因是归档只记录 (bikes, free) 变化，数量不变时会过滤记录，可能遗漏只改变营业标记的更新。2025 年初和年末的归档代码版本均可追溯；服务实际部署连续性仍不可独立证明。故“没有新记录”不能被解释为停运或连续正常营业，也不能可靠估计时间加权空站/满站时长。归档以 UTC 月份组织，与 NYC 本地年尾还存在边界覆盖区别。

纽约开放数据 Bike Share Inspections (Historical) 实际日期范围为 2013-05-28 至 2020-03-13，不能证明 2025 状态。市审计长有关可靠性的报告使用 2023 年 6–7 月数据，亦不能冒充 2025。

## 使用历史实测状态的新实验

仅使用决策前且报告年龄不超过 15 分钟、容量一致、租还车启用的共同状态。质量筛查后有 260 个测试小时同时覆盖全部 30 站。每个小时三策略从相同实测库存重置，使用实测 bikes+free 作为当时可用容量；报告物理 slots 另列。不是连续两个月的真实车队反事实。

```csv
strategy,departure_requests,arrival_events,unmet_departures,blocked_arrivals,bikes_moved,bike_km,scenario_objective,proxy_service_rate,hours
greedy,162483,160877,1865,2837,3120,779.2462440491079,23587.92462440491,0.988521876134734,260
milp,162483,160877,1752,2625,3120,1800.0285264649951,22065.0028526465,0.9892173335056592,260
none,162483,160877,1932,3029,0,0.0,24805.0,0.9881095253041856,260
```

这组状态重置、时间子集与旧的 25 容量全测试期压力场景不同，不能直接比较两表服务率来声称现实改善。采样偏向有数量变化和繁忙时段，仍有选择偏差。

## 新增实验均已实际运行

1. **天气消融**：使用 Open-Meteo Previous Runs 的 GFS 24 小时前预报，不使用目标小时实测/再分析。固定原 XGBoost 参数，保持同样目标和随机样本。

```csv
target,mean_daily_MAE_difference,ci_low,ci_high,comparison
departures,-0.0304469083341347,-0.0454029204529997,-0.0163408966956573,with 24-hour-lead GFS forecast minus no-weather; fixed XGBoost parameters
arrivals,-0.0234435648355646,-0.042368886302953,-0.0046844725462659,with 24-hour-lead GFS forecast minus no-weather; fixed XGBoost parameters
```

2. **时长清洗敏感性**：从全部原始 ZIP 重读，比较 30/60/90/120/180/360 分钟；180 分钟结果与原始端点总量及预测指标完全重合。每个阈值固定模型架构、重拟合，并比较同条件策略。阈值改变目标记录集合，误差不能简单跨阈值排名。

```csv
cutoff_minutes,target,retained_selected_rides,test_count,n,mae,rmse,wape
30,departures,6238542,415540,43950,3.25949880007184,4.810565719082324,0.3447441215362116
30,arrivals,6238542,413069,43950,3.268623264427206,4.909466209090672,0.3477772296434148
60,departures,6590169,432232,43950,3.387240044383059,5.00028958778783,0.3444196633998302
60,arrivals,6590169,429078,43950,3.3778024076411883,5.078572287383072,0.345984683008288
90,departures,6636185,434416,43950,3.4090811618765877,5.0391169710624935,0.3448977870623458
90,arrivals,6636185,431107,43950,3.3909564224512776,5.101833470511514,0.3456973205416141
120,departures,6648183,434974,43950,3.417206584087682,5.051373842670489,0.345276336908996
120,arrivals,6648183,431640,43950,3.3946146124960754,5.107391469685587,0.3456429251672748
180,departures,6653970,435223,43950,3.417683828450714,5.056675367195367,0.3451269906700906
180,arrivals,6653970,431868,43950,3.398161859152938,5.111224447587446,0.3458214401385878
360,departures,6656216,435329,43950,3.420004931069885,5.06106031327389,0.3452772884887555
360,arrivals,6656216,431954,43950,3.398938465989084,5.114340680937677,0.3458316060974553
```

3. **随机多期优化**：三小时 MPC、四个相关场景，噪声来自验证期联合残差块。未来多步特征递归生成，未知未来真实值被清空；每轮只执行第一步。共享整数搬运，场景库存连续近似，末端安全区间半权重；请求求解 gap=2%，求解状态与回退明确。测试为 48 小时共同事件路径。

```csv
strategy,requests,unmet,blocked,bikes_moved,bike_km,scenario_objective,fallback,service_proxy
greedy,19339,1620,863,569,255.89640129540024,12440.58964012954,0,0.9162314494027612
milp,19339,1508,746,564,489.2007837155259,11318.920078371551,0,0.9220228553699776
none,19339,1752,1013,0,0.0,13825.0,0,0.9094058637985418
stochastic_mpc,19339,1436,697,563,782.9053634529197,10743.290536345292,0,0.9257459020631884
```

4. **卡车路径**：两车、每车 6 辆、15 km/h、60 分钟班次、每辆每次装/卸 1.5 分钟；对前 48 小时的 Greedy/MILP 订单做原子取送路径 MILP。禁止共同装载多任务，属于受限取送路径模型，不是一般 VRP 或实际路网调度系统。

```csv
strategy,status,hours
greedy,2:The problem is infeasible. (HiGHS Status 8: model_status is Infeasible; primal_status is None),28
greedy,optimal_with_requested_gap_1pct,20
milp,2:The problem is infeasible. (HiGHS Status 8: model_status is Infeasible; primal_status is None),29
milp,optimal_no_jobs,1
milp,optimal_with_requested_gap_1pct,18
```

不可行是这些固定订单在所选受限模型下不能全部完成，不是一般运输问题不可行的证明。没有把失败订单当成功，也没有把瞬时仿真服务收益说成可实际调度执行的收益。

5. **网络扩展**：60 个仅训练期筛选的站点，525,600 panel 行，87,900 测试站点小时，三策略各 336 小时。用官方 26c 行政区多边形（水域包含）作明确分析边界，原 30 站均在内；这不是 2025 库存证据，也不冒充历史版区界。固定每小时预算 12，属于规模和资源压力研究，不能与 30 站不同需求范围当作同样本因果比较。

```csv
strategy,departure_requests,arrival_events,unmet_departures,blocked_arrivals,bikes_moved,bike_km,scenario_objective,proxy_service_rate,mean_runtime_ms,fallback_hours,data_kind,simulation_kind,hours
none,254518,251288,24054,20883,0,0.0,224685.0,0.9054919494888376,0.8727222083334276,0,official,hourly count-based scenario simulation,336
greedy,254518,251288,23490,20329,4026,1111.3766584888808,219206.1376658489,0.9077079027809428,1.307859749980859,0,official,hourly count-based scenario simulation,336
milp,254518,251288,22721,19559,4020,2098.2504909678573,211609.8250490968,0.9107293000887952,25.970305723243808,0,official,hourly count-based scenario simulation,336
```

上述新增分析发生在原测试已查看之后，均如实标为探索性扩展；未宣称有新的未触碰测试集。

## 来源与复现

- https://data.citybik.es/ （2025 分网络档案；ODbL-1.0）
- https://web.archive.org/cdx/search/cdx （官方 GBFS 的 2025 捕获索引与原始 JSON）
- https://github.com/citybikes/analytics/blob/353535785bd70f61e8ef3cadc26ff64211eba95c/collect.py （2025 年初源码）
- https://github.com/citybikes/analytics/blob/5cd7338c9e1502a194857d4956f594a16aecabc3/collect.py （2025 年末源码）
- https://data.cityofnewyork.us/resource/5uei-swth.json （检查记录覆盖范围已实查）
- https://open-meteo.com/en/docs/previous-runs-api （提前 24 小时预报定义）

Bike-share data by CityBikes contributors and available from https://data.citybik.es .
CityBikes contributors. (2026) Bike-share data retrieved from https://data.citybik.es .

CityBikes 衍生数据库按 ODbL-1.0 提供，原运营方数据条款仍适用；天气数据注明 Open-Meteo/NOAA 来源。下载清单、原始快照、SHA256、处理程序和所有结果均保留。已有 40 项测试通过，包括未来信息隔离、历史时间与新鲜度、异常容量拒绝、随机规划穷举检验、路径容量/工时/不可行状态等。

## 仍需外部原始记录的部分

要彻底消除剩余运营证据缺口，需要运营方/归档方提供包含“数量不变”和“仅标记改变”更新的连续原始 GBFS 心跳或维护日志。已准备精确字段与时间范围的数据请求草稿，但未擅自向任何人发送。新的公共证据显著增加了可验证范围，不能因此把未观测状态伪造成事实。即使未来拿到完整库存，也仍不能从库存反推出所有潜在被拒请求数。
