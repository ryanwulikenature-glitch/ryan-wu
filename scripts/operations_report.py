"""Generate the final engineering supplement from executed transport/collector evidence."""
import base64,html,json,shutil,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.common import ROOT,save_json
reports=ROOT/'reports';out=ROOT/'outputs/transport_service';fig=reports/'figures/operations';fig.mkdir(parents=True,exist_ok=True)
s=pd.read_csv(out/'summary.csv');h=pd.read_csv(out/'hourly.csv');protocol=json.loads((out/'protocol.json').read_text())
snapshot=json.loads((reports/'validation/telemetry_snapshot.json').read_text());runs=json.loads((reports/'validation/github_collection_runs.json').read_text());restored=json.loads((reports/'validation/github_archive_restoration.json').read_text());checks=json.loads((reports/'validation/transport_reconciled.json').read_text())
xml=ET.parse(reports/'validation/pytest.xml').getroot();suites=xml.findall('testsuite') if xml.tag=='testsuites' else [xml];tests=sum(int(x.attrib['tests']) for x in suites);assert all(int(x.attrib['failures'])+int(x.attrib['errors'])==0 for x in suites)
names={'none':'No intervention','road_greedy':'Road Greedy','road_milp':'Road MILP','instant_milp_relaxation':'Instant MILP (relaxed)'}
plot=s.set_index('strategy').loc[['none','road_greedy','road_milp','instant_milp_relaxation']]
figobj,ax=plt.subplots(1,2,figsize=(10,3.8));labels=[names[x] for x in plot.index]
ax[0].bar(range(4),plot.unmet_departures,color=['#455a64','#27ae60','#2980b9','#bdc3c7']);ax[0].set_ylabel('Unserved recorded departures');ax[0].set_title('48-hour paired-event scenario')
ax[1].bar(range(4),plot.truck_km,color=['#455a64','#27ae60','#2980b9','#bdc3c7']);ax[1].set_ylabel('Truck km (empty legs included)');ax[1].set_title('Instant reference relaxes truck resources')
for axis in ax:axis.set_xticks(range(4),labels,rotation=20,ha='right');axis.grid(axis='y',alpha=.2)
figobj.tight_layout();figobj.savefig(fig/'service_transport.png',dpi=160);plt.close(figobj)
g=h.pivot(index='timestamp',columns='strategy',values='unmet_departures');g.index=pd.to_datetime(g.index,utc=True)
plt.figure(figsize=(10,3));
for policy in ['road_greedy','road_milp']:plt.plot(g.index,g[policy]-g['none'],label=names[policy])
plt.axhline(0,c='grey',lw=.8);plt.ylabel('Unserved difference vs no intervention');plt.xlabel('UTC');plt.legend();plt.tight_layout();plt.savefig(fig/'hourly_service_difference.png',dpi=160);plt.close()
table=s[['strategy','unmet_departures','blocked_arrivals','picked_bikes','delivered_bikes','truck_km','driver_hours','proxy_service_rate']].copy()
table['proxy_service_percent']=(100*table.pop('proxy_service_rate')).round(4);table[['truck_km','driver_hours']]=table[['truck_km','driver_hours']].round(3)
def mdtable(frame):
    cols=list(frame.columns);lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
    return '\n'.join(lines+['| '+' | '.join(str(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None)])
schedule_runs=[r for r in runs if r['event']=='schedule' and r['conclusion']=='success']
schedule_note=(f"已核验 {len(schedule_runs)} 次 schedule 事件成功；实际运行收据见 validation/github_collection_runs.json。" if schedule_runs else '已核验 push 触发成功、归档实际存在并可恢复；目前保存的收据尚无 schedule 事件成功记录，不能据此宣称定时连续性已获长期验证。')
text=f'''# 最后工程补充：道路运输服务联立与持续库存采集

原项目指南中的数据、预测、整数优化、配对事件、天气、随机多期、网络扩展均已有实际结果。本轮补齐道路货车和服务联立，以及可持续运行的库存采集部署。**{tests} 项测试通过**，并独立核对 {checks['routes']} 条运输路线。原十页英文研究报告仍保留基线；本补充记录新增工程和不利结果。

## 道路卡车已经接入客户事件仿真

固定 {protocol['hours']} 小时、30 站、{protocol['paired_rides']:,} 条跨研究边界相关的真实已完成行程；窗口 {protocol['start_utc']} 至 {protocol['stop_utc']}。起点按预先定义的新鲜、有效、启用且最多15分钟旧的共同历史状态，选择测试期首个合格小时，未按结果挑日期。

- 有向 OSRM driving 路网的道路距离和行驶时间，最大站点吸附偏移约21.91米。© OpenStreetMap contributors，ODbL；请求URL、站点顺序和原始矩阵保留。
- 两辆容量6的卡车，允许同时装载多个任务；每辆每次装卸90秒，先取后送，回虚拟车库，每条路线不超过60分钟。每个固定UTC八小时班段内每车活动工时不超过8小时，假设班段间可换司机。每小时新调车上限12辆。
- 取车时检查当时真实模拟库存；运输中的车辆记在卡车账。卸车结束才增加站点库存；满桩时留在原卡车，下轮强制重送。客户提前用光库存会取车失败，不会凭空完成配送。
- 原Greedy/MILP决定供需调车目标，OR-Tools联合装载取送启发式选择可行任务与顺序；不宣称全局路径最优。瞬时MILP单列为运输资源放宽参照。
- 客户拒绝借车会取消相应归还，在途、区域外进出、客户暂存及卡车在途均入总账。每个事件断言库存/卡车容量和完整车队守恒。

{mdtable(table)}

**本场景负结果保留**：不调运的服务代理优于两种道路策略。小时末平衡目标、固定需求预测、库存和客户时序不保证多小时服务提升；没有因不利结果再调参数或删除场景。服务代理按已记录行程请求计算，不是真实潜在需求满足率；两天场景不支持总体因果结论。

道路为当前OSM驾驶代理，不是2025实时交通或经过核实的卡车限高限重路线。虚拟车库假设位于ID排序首站，可用容量固定为初始实测bikes+free，未推断随后48小时容量或营业标记一直不变。这些是反事实场景设定。

## 持续采集已部署，未来数据按实际时间积累

本地独立进程每60秒目标采集官方 station_information/status；云机器停止后本地进程不再工作。GitHub公开仓库 Actions 每5分钟目标调度，源码工作流已部署，结果写入独立 [gbfs-history 分支](https://github.com/ryanwulikenature-glitch/ryan-wu/tree/gbfs-history)。{schedule_note}

GitHub 首轮实际归档下载后恢复出 {restored['polls']} 个poll、{restored['observations']} 条站点观察，SQLite integrity_check={restored['integrity_check']}。Actions正常启用且仓库公开时使用公开runner免费额度；cron可能排队、延迟或停用，不保证严格五分钟间隔。健康检查应看真实时间戳，不能把YAML声明当作长期运行证据。

截至静态快照 {snapshot['snapshot_created_utc']}，本地保存 **{snapshot['polls']} 个实际poll、{snapshot['observations']} 条站点观察**，首末采集 {snapshot['first_poll_utc']} → {snapshot['last_poll_utc']}，实际跨度 {snapshot['observed_span_minutes']:.2f} 分钟，最大间隔 {snapshot['max_poll_gap_seconds']:.2f} 秒。这是当前实采窗口，不是全年或长年库存。

所有站点每次poll均保留，包括数量未变、只改标记、已移除/未匹配站点、陈旧源报告与获取失败。当前质量计数：`{json.dumps(snapshot['quality_counts'],ensure_ascii=False)}`；未知站点绝不当作关闭或零需求。

归档保存源更新时间、抓取时间、源体SHA256、标准化库存/容量/全部运营标记和选中站点原始字段。原始全网JSON保留7天；SQLite工作集保留30天，旧数据写入持久每日gzip JSONL，重读核对每个字段/数量/完整内容SHA256后才清理。损坏、少行或同ID改值都拒绝清理。静态可恢复副本为 reports/evidence/telemetry/inventory.sqlite 和 archive/；使用SQLite backup在活跃写入时取得一致快照。

采集启动阶段出现数据库列名语法错误；修复后将6份已真实保存的原始feed对恢复为标准化poll，保留原文件时间证据。后续重启运行及归档维护正常；恢复收据在 reports/validation/telemetry_recovery.json。没有制造历史poll或填补停采间隙。

## 已执行的验证与复现

- {tests} pytest通过；新增测试覆盖装载/先取后送、原卡车持货、不可行丢单、客户先取走库存、道路延迟、满桩后携货重送、标记变化保留、失败心跳、幂等恢复与防损坏清理。
- scripts/check_transport.py 从已保存路线/真实货物事件独立重算道路时间、装卸时点、容量、工时、预算、truck-km及随载bike-km，核对同请求/基线预测/过去初态与车队总账；{checks['routes']} 条路线全部通过。
- 原全年官方结果和历史/天气/六个时长/MPC/60站结果已再次独立核验，原始基线保留；已有三份执行后的notebook。

```bash
./scripts/install.sh
.venv/bin/python -m pytest -q
# 全年清洗分片在当前云环境已存在：
.venv/bin/python scripts/transport_experiment.py
# 交付ZIP中另含核验过的48小时真实行程切片，无需重下8.93GB即可重跑本实验：
.venv/bin/python scripts/transport_experiment.py --reuse-rides
.venv/bin/python scripts/check_transport.py
# 本地采集的启停状态；只管理本项目进程：
.venv/bin/python services/collectorctl.py status
.venv/bin/python services/collectorctl.py start
.venv/bin/python services/collectorctl.py stop
# 从gbfs-history检出的档案重建：
.venv/bin/python scripts/import_telemetry_archive.py --archive /path/to/archive --db /tmp/restored.sqlite
```

有时限的路径启发式可能随硬件/版本产生不同可行路线；不承诺逐bit复现路线。随机种子、完整输入、路网、原始输出、限制和求解状态均保留。自动采集不会自动运行昂贵的全年模型训练。没有连接或控制任何真实运营车辆。

## 仍无法由代码补成事实的内容

2025原19,634个运营未知站点小时中，仅2个满足声明的全部12个五分钟箱标准，**19,632个仍不满足强证据标准**。CityBikes历史变化去重会压掉数量未变和只改标记的心跳；所查公开档案不包含这些被丢弃的更新。需要运营方或归档方原始连续日志/维护记录，不能由当前实时数据或骑行次数反推。精确缺口CSV和数据申请草稿已交付，未擅自对外发信。

因此：所要求的工程模块、运行测试、道路服务实验与采集部署已完成；未观测历史状态、尚未经过的未来采集时间、实际运营效果与长期无人值守SLA不冒充已证明事实。
'''
(reports/'operations_completion.md').write_text(text)
sections=['<h1>道路运输服务与持续库存采集</h1>',table.to_html(index=False),'<img src="data:image/png;base64,'+base64.b64encode((fig/'service_transport.png').read_bytes()).decode()+'">','<img src="data:image/png;base64,'+base64.b64encode((fig/'hourly_service_difference.png').read_bytes()).decode()+'">','<pre>'+html.escape(text)+'</pre>']
(reports/'operations_completion.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>道路运输与持续采集：最终补充</title><style>body{font-family:system-ui;max-width:1200px;margin:32px auto;padding:0 20px;line-height:1.7}table{border-collapse:collapse;font-size:12px}td,th{padding:8px;border:1px solid #ddd}img{max-width:100%}pre{font-family:inherit;white-space:pre-wrap;overflow-wrap:anywhere}</style>'+''.join(sections)+'</html>')
dest=reports/'results/operations';dest.mkdir(parents=True,exist_ok=True)
for name in ['summary.csv','hourly.csv','closing.csv','initial_state.csv','protocol.json']:shutil.copyfile(out/name,dest/name)
save_json(dest/'completion.json',dict(pytest_passed=tests,route_checks=checks,telemetry_snapshot=snapshot,github_runs=runs,github_archive_restoration=restored,schedule_success_observed=bool(schedule_runs),historical_hours_still_below_strong_criterion=19632))
print('Generated operations supplement and reviewable tables from actual saved artifacts.')
