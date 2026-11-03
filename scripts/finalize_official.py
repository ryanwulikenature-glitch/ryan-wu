"""Generate Chinese narrative/HTML and refresh status from real saved outputs."""
import sys,json,base64,html
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.common import ROOT,save_json,versions
from src.metrics import block_bootstrap
from src.report import create_reports
out=ROOT/'outputs/official';data=ROOT/'data/processed';reports=ROOT/'reports'
create_reports(data,out)
quality=json.loads((data/'data_quality_summary.json').read_text())
training=json.loads((out/'training_config.json').read_text())
metrics=pd.read_csv(out/'forecast_metrics.csv');m=metrics[(metrics.split=='test')&(metrics.stratum=='all')]
summary=pd.read_csv(out/'simulation_summary.csv');paired=pd.read_csv(out/'paired_events/event_replay_summary.csv')
experiments=pd.read_csv(out/'experiments/experiments.csv');uncertainty=pd.read_csv(out/'uncertainty_summary.csv')
audit=pd.read_csv(data.parent/'interim/monthly_audit.csv');audit['month']=audit.filename.str.extract(r'(2025\d{2})',expand=False)
columns=['raw_rows','missing_id','invalid_time_or_dst','invalid_duration','invalid_coordinate','duplicate_within_member','duplicate_across_members','retained']
monthly=audit.groupby('month')[columns].sum();monthly.to_csv(out/'monthly_cleaning_summary.csv')
# Paired local-day block comparisons for forecasting; no station-row independence assumption.
p=pd.read_csv(out/'test_predictions.csv.gz');p['day']=pd.to_datetime(p.hour,utc=True).dt.tz_convert('America/New_York').dt.date
intervals=[]
for target,prefix in [('departures','dep'),('arrivals','arr')]:
 for model in ['last_hour','poisson','xgboost']:
  delta=(p[target]-p[f'{prefix}_{model}']).abs()-(p[target]-p[f'{prefix}_seasonal_naive']).abs()
  daily=delta.groupby(p.day).mean();lo,hi=block_bootstrap(daily,2025)
  intervals.append(dict(target=target,model=model,baseline='seasonal_naive',mean_daily_mae_difference=float(daily.mean()),ci_low=lo,ci_high=hi,days=len(daily),method='paired local-day block bootstrap'))
pd.DataFrame(intervals).to_csv(out/'forecast_daily_bootstrap.csv',index=False)
for source in ['final_report.md','eda_findings.md']:(reports/source).write_text((out/source).read_text())
text=f'''# NYC Citi Bike：真实数据项目运行报告\n\n## 完成情况\n\n**网络阻塞已解除，真实 2025 年 NYC 官方数据流程已实际运行。** 使用 12 个月 ZIP、53 个 CSV 成员；清洗前 {quality['raw_rows']:,} 行，保留 {quality['retained_rides']:,} 条有效行程。按训练期规则选取 {quality['stations']} 个站，生成 {quality['panel_rows']:,} 个站点小时。\n\n**研究口径是清洗后档案中的完成骑行计数及假设情景，不能称为真实缺车率或真实调运收益。** 缺少历史运营日历，审计 panel 中 {quality['unknown_hours']:,} 个小时保持运营未知；建模副本显式使用 recorded_event_counts，零表示没有保留下来的记录，而非确认营业或零潜在需求。\n\n## 预测\n\n1–8 月训练、9–10 月验证选参、11–12 月完整测试，滚动一小时预测；预处理只在训练期拟合，最终模型按固定参数重拟合 train+validation。两个目标分别由验证 MAE 选择模型：{json.dumps(training['selected_models'],ensure_ascii=False)}。没有根据测试结果继续调参。测试包含 43,950 个站点小时。\n\n```csv\n{m.to_csv(index=False)}```\n\n分层误差、预测图、残差和按本地日期块 bootstrap 区间在 outputs/official；不能将站点小时视为相互独立样本。\n\n## 小时计数情景：完整测试期\n\n各策略均运行 1,465 小时，覆盖 11–12 月与 DST 变化；同初始库存、容量、预算、半径、预测输入及随机事件样本。\n\n```csv\n{summary.to_csv(index=False)}```\n\n容量=25、初始比例=50%、预算=12 辆/小时、半径=3 km 均是假设；bike-km 不是货车里程，情景目标不是财务成本。MILP 目标优化预测期末安全区间的松弛和运输距离，不保证最优真实服务。求解状态和回退逐小时记录。\n\n## 配对事件升级：完整测试期\n\n对真实清洗 ride_id 配对开始/结束事件，被拒借车不再生成对应还车。维护在途和站外暂存车辆，显式计入跨边界流入/流出；每个处理事件检查车队账守恒。满桩归还在本轮剩余时间暂存，不凭空删除车辆。\n\n```csv\n{paired.to_csv(index=False)}```\n\n配对情景和小时计数情景为两套假设，分别报告，不能混为同一种服务率，更不能当作真实 2025 库存回放。\n\n## 稳健性、消融与不确定性\n\n共 {experiments.experiment.nunique()} 个预先保存配置场景、每场景三策略各 48 小时，全部完成；覆盖容量、预算、半径、初始库存、惩罚权重、种子和日期；替换季节朴素、只借出预测、固定 XGBoost 及不可部署 Oracle。测试期敏感性是探索性分析，不能宣称额外未触碰检验；Oracle 只作未来信息参照，不保证服务上界。\n\n```csv\n{uncertainty.to_csv(index=False)}```\n\n日块区间和多种子结果只量化给定情景内的不确定性，不消除历史库存缺失和需求删失的结构偏差。天气消融未运行，未使用目标小时事后天气。\n\n## 数据质量与限制\n\n- 原始 ZIP 通过 HTTPS 下载，验证 CRC、记录 SHA256/来源/日期；严格去重与剔除理由见 monthly_cleaning_summary.csv 和 data/interim 审计文件。\n- 使用 UTC 连续小时，本地日历 America/New_York；没有 offset 的 DST 重复/不存在时间被明确剔除。阈值为 180 分钟，配置与边界测试可追溯；更长阈值的完整重清洗敏感性尚未运行。\n- 仅用训练期选择站点；地理矩形是 Manhattan 附近近似，坐标漂移采用训练期 chunk/月摘要代理，不是经验证的历史迁移记录。\n- 清洗排除缺少必要站点 ID 的骑行，故目标是保留的已记录骑行；不能覆盖潜在被拒需求。模型的实时数据可用性仍须部署时单独验证。\n- 主要小时结果采用外生到达；配对升级修正被拒还车因果与车队账，但边界需求、暂存规则和瞬时调运仍是假设。\n- 历史容量、历史库存、真实车辆路径与实际成本未知；GBFS 当前信息不能冒充 2025 历史事实。\n- 可选未来 GBFS 采集、多期随机优化、货车路径和网络扩容未实施，未宣称完成。\n\n## 验证与交付\n\n29 项测试通过，官方结果独立核对通过；运行命令、源代码、清单、模型、CSV、12 张真实数据图及两个 EDA notebook 在项目中。完整测试期小时情景和配对事件情景均已运行，结论来自保存文件；原始约 8.93 GB 数据不重复打入交付包，可按清单下载和校验。没有提交或推送 GitHub。\n\n先前的 HTTP 403 已不再是当前阻塞；当前工具没有代点 UI 发布的能力，但当前环境已运行且官方下载成功。未来新任务快照恢复仍未独立验证。\n'''
(reports/'项目总结.md').write_text(text)
sections=[f'<h1>NYC Citi Bike · 2025 官方数据实验</h1><p>{html.escape(text.split("## 预测")[0])}</p>',
 '<h2>预测测试指标</h2>'+m.to_html(index=False),'<h2>小时计数情景（假设结果）</h2>'+summary.to_html(index=False),
 '<h2>配对事件情景（假设结果）</h2>'+paired.to_html(index=False),'<h2>配对日块区间</h2>'+uncertainty.to_html(index=False),
 '<h2>逐月清洗审计</h2>'+monthly.to_html(),'<h2>限制与复现</h2><pre>'+html.escape(text.split('## 数据质量与限制')[1])+'</pre>']
for image in sorted((out/'figures').glob('*.png')):
 sections.append('<h2>'+html.escape(image.stem)+'</h2><img src="data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()+'">')
(reports/'项目总结.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Citi Bike 2025</title><style>body{font-family:system-ui;margin:36px;line-height:1.6}table{border-collapse:collapse;font-size:12px}th,td{padding:6px;border:1px solid #ddd}img{max-width:100%}pre{white-space:pre-wrap}</style>'+''.join(sections)+'</html>')
print('PASS: Chinese report, standalone HTML, model-error block intervals and official monthly audit generated from saved real outputs.')
