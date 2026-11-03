"""Build application-facing research artifacts from verified project outputs."""
import html,json,shutil,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.common import ROOT,save_json

app=ROOT/'application';app.mkdir(exist_ok=True);fig=ROOT/'reports/figures/application';fig.mkdir(parents=True,exist_ok=True)
metrics=pd.read_csv(ROOT/'outputs/official/forecast_metrics.csv');metrics=metrics[(metrics.split=='test')&(metrics.stratum=='all')]
lookup=metrics.set_index(['target','model']);dep=lookup.loc[('departures','xgboost'),'mae'];last=lookup.loc[('departures','last_hour'),'mae'];arr=lookup.loc[('arrivals','xgboost'),'mae'];gain=100*(1-dep/last)
audit=ROOT/'outputs/coverage_audit';coverage=pd.read_csv(audit/'threshold_coverage.csv');strata=pd.read_csv(audit/'forecast_metrics.csv');strata=strata[strata.max_age_minutes==15]
u=strata[(strata.target=='departures')&(strata.stratum=='start_state_unsupported')].set_index('model');supported=strata[(strata.target=='departures')&(strata.stratum=='start_state_supported')].set_index('model')
protocol=json.loads((audit/'protocol.json').read_text());road=pd.read_csv(ROOT/'outputs/transport_service/summary.csv').set_index('strategy')
testsuites=ET.parse(ROOT/'reports/validation/pytest.xml').getroot().findall('testsuite');tests=sum(int(x.attrib['tests']) for x in testsuites);assert all(int(x.attrib['failures'])+int(x.attrib['errors'])==0 for x in testsuites)
runs=json.loads((ROOT/'reports/validation/github_research_runs.json').read_text());ci=next(x for x in runs if x['name']=='Research checks' and x['conclusion']=='success')
monitor=json.loads((ROOT/'reports/validation/monitoring_audit.json').read_text())
external=pd.read_csv(ROOT/'outputs/external_202601/forecast_metrics.csv');external=external[external.stratum=='all'].set_index(['target','model'])
edep=external.loc[('departures','xgboost'),'mae'];elast=external.loc[('departures','last_hour'),'mae'];egain=100*(1-edep/elast)
claims=[
 ('data_scale','45,588,101 retained NYC rides; 30 training-selected sites; 262,800 station-hours','Global cleaning scale; modeling targets are selected-network recorded counts','reports/validation/official_run_evidence.json'),
 ('pooled_forecast',f'Pooled test departure MAE {dep:.6f} vs last-hour {last:.6f}; reduction {gain:.4f}%','43,950 chronological test station-hours; recorded completed rides, not latent requests','reports/results/forecast_metrics.csv'),
 ('conditional_reversal',f'Unsupported-start departure MAE: XGBoost {u.loc["xgboost","mae"]:.6f} vs last-hour {u.loc["last_hour","mae"]:.6f}, n={int(u.loc["xgboost","n"])}','Post-hoc 15-minute evidence criterion; different stratum composition, not a causal missingness effect','reports/results/application/coverage_forecast_metrics.csv'),
 ('historical_evidence','2,907,502 historical status changes; 120 official capacity and 180 official status points','Change events are not continuous operating history','reports/results/extensions/completion_evidence.json'),
 ('remaining_gap',f'19,632 unsupported historical station-hours ({100*protocol["remaining_fraction"]:.4f}% of panel)','12 five-minute-bin sampling criterion; remaining unknowns preserved','reports/results/application/coverage_protocol.json'),
 ('transport',f'48-hour road scenario: no intervention {100*road.loc["none","proxy_service_rate"]:.4f}% vs road MILP {100*road.loc["road_milp","proxy_service_rate"]:.4f}%','Recorded-ride counterfactual; current driving proxy, frozen capacity and virtual depot; negative result retained','reports/results/operations/summary.csv'),
 ('testing',f'{tests} local tests passed; remote Research checks success','Unit/synthetic research checks, not proof of real operational benefit',ci['html_url']),
 ('collection',f'Collection deployed; scheduled trigger success observed={monitor["schedule_trigger_verified"]}','Actual dated samples only; no claim of long-term cadence or backfilled 2025 state','reports/validation/monitoring_audit.json'),
 ('external_2026',f'Frozen January 2026 departure MAE {edep:.6f} vs last-hour {elast:.6f}; reduction {egain:.4f}%','22,320 new station-hours; protocol/model hashes frozen in Git before acquiring records; no refit; rolling archived-count evaluation','reports/results/external_202601/validation.json')]
pd.DataFrame(claims,columns=['id','claim','scope','evidence']).to_csv(app/'CLAIMS_AND_EVIDENCE.csv',index=False)
dest=ROOT/'reports/results/application';dest.mkdir(parents=True,exist_ok=True)
for name,new in [('forecast_metrics.csv','coverage_forecast_metrics.csv'),('threshold_coverage.csv','coverage_thresholds.csv'),('paired_daily_comparisons.csv','coverage_paired_comparisons.csv'),('by_month.csv','coverage_by_month.csv'),('by_station.csv','coverage_by_station.csv'),('by_hour.csv','coverage_by_hour.csv'),('protocol.json','coverage_protocol.json')]:shutil.copyfile(audit/name,dest/new)
data=metrics.pivot(index='model',columns='target',values='mae').reindex(['last_hour','seasonal_naive','poisson','xgboost']).round(3)
conditional=strata[strata.target=='departures'].pivot(index='stratum',columns='model',values='mae').reindex(['all_recorded_counts','start_state_supported','start_state_unsupported'])[['last_hour','xgboost']]
figobj,ax=plt.subplots(1,2,figsize=(10,3.4));ax[0].plot(coverage.max_age_minutes,coverage.supported_fraction*100,'o-',color='#2874a6');ax[0].set_xlabel('Maximum past-state age (minutes)');ax[0].set_ylabel('Test start states supported (%)');ax[0].set_ylim(0,100);ax[0].set_title('Evidence coverage changes with threshold')
conditional.rename(index={'all_recorded_counts':'All','start_state_supported':'Supported','start_state_unsupported':'Unsupported'}).plot.bar(ax=ax[1],color=['#7f8c8d','#2874a6'],rot=0);ax[1].set_ylabel('Departure MAE');ax[1].set_xlabel('15-minute evidence criterion');ax[1].set_title('Pooled ranking hides a weaker stratum');figobj.tight_layout();figobj.savefig(fig/'coverage_and_ranking.png',dpi=160);plt.close(figobj)
brief=f'''# Evidence-Aware Citi Bike Demand Forecasting and Rebalancing

**Computational research project | Python, XGBoost, MILP, stochastic MPC, pickup-delivery routing**

## Research question

Can next-hour forecasts of completed-ride counts improve simulated rebalancing service, and how do incomplete station-state evidence and delayed vehicle movement change the conclusions?

## Data and methods

The pipeline processed 45,771,102 official 2025 NYC trip rows and retained 45,588,101 after auditable cleaning. Thirty stable sites were selected on January–August only, yielding 262,800 station-hours. January–August training, September–October validation and November–December testing avoid random temporal splits. Last-hour, seasonal naive, Poisson and XGBoost models predict departures and arrivals; lag/rolling features precede the forecast hour. The test contains 43,950 station-hours.

Separate integer rebalancing and stochastic three-period MPC policies are evaluated with shared requests. Count and paired-ride simulations cover 1,465 test hours; the paired replay suppresses returns after rejected departures and tracks transit, external boundaries and held bikes. A 48-hour extension combines co-loaded trucks with directed OSRM driving times, handling delays, depot returns and capacity/driver constraints; 181 saved routes reconcile with actual cargo events.

## Findings

1. **Predictive performance:** pooled departure MAE is {dep:.3f}, compared with {last:.3f} for last-hour ({gain:.1f}% lower); arrival MAE is {arr:.3f}. These are completed-ride count errors, not recovered latent demand.
2. **Evidence matters:** 2,907,502 historical status changes plus dated official snapshots improve calibration. At the 15-minute criterion, 33,131/43,950 test start states have valid enabled historical point support. XGBoost departure MAE is {supported.loc['xgboost','mae']:.3f} versus {supported.loc['last_hour','mae']:.3f} on that subset. On the other 10,819 rows, ranking reverses: {u.loc['xgboost','mae']:.3f} versus {u.loc['last_hour','mae']:.3f}. This is a conditional descriptive result; evidence coverage and activity are associated, and missingness is not assumed random.
3. **Optimization has limits:** in the delayed-road scenario, no intervention serves {100*road.loc['none','proxy_service_rate']:.3f}% of recorded departure requests versus {100*road.loc['road_milp','proxy_service_rate']:.3f}% for road MILP. A forecast-end balance objective does not guarantee improved pathwise service. The unfavorable comparison is retained.
4. **Frozen cross-year validation:** before downloading new January 2026 records, the station list, cleaning rules, fitted model hashes and evaluation plan were frozen in Git. On all 744 hours / 22,320 station-hours, unchanged XGBoost achieves departure MAE {edep:.3f} versus {elast:.3f} for last-hour ({egain:.1f}% lower). No fitting or tuning occurs. This is retrospective rolling one-step evaluation, not an online deployment.

## Evidence boundary and reproducibility

The 19,632 remaining unsupported station-hours ({100*protocol['remaining_fraction']:.2f}% of the annual panel) stay unknown. This annual strong-sampling mask differs from the 10,819 test rows failing the 15-minute start-state criterion. Change-filtered archives cannot prove continuous opening states or identify all rejected requests. The evidence-age audit is exploratory on an already examined test set; it is not a fresh holdout. Current driving roads, frozen capacity and an assumed depot are scenario inputs. Prospective collection is deployed, while long-term cadence is assessed only from actual dated receipts. {tests} local tests passed and [remote CI succeeded]({ci['html_url']}). Source, exact dependencies, executed notebooks, manifests, reports and integrity-checked delivery are available in the [repository](https://github.com/ryanwulikenature-glitch/ryan-wu).

Implementation and experiment execution were AI-assisted. No peer-reviewed publication, real operator deployment, causal service improvement or sole manual authorship is claimed.
'''
(app/'RESEARCH_BRIEF.md').write_text(brief)
cv=f'''# English CV project entries

Use a version matching your actual contribution and target program. Project dates, supervisor and institution are deliberately omitted because they have not been established. This is a research project, not a publication. Implementation and execution were AI-assisted; see CONTRIBUTIONS.md.

## General / data science

**NYC Citi Bike Demand Forecasting & Rebalancing — Research Project**  
Python · Pandas/PyArrow · XGBoost · SciPy MILP · OR-Tools

- Developed an AI-assisted, reproducible pipeline processing 45.6M 2025 NYC rides into a 262,800-row, 30-station hourly panel; evaluated four next-hour count models with chronological train/validation/test splits.
- Achieved pooled test departure MAE of {dep:.3f} versus {last:.3f} for a last-hour baseline ({gain:.1f}% lower); audited 2.91M historical state changes and identified a model-ranking reversal on 10,819 test rows lacking fresh start-state evidence.
- Froze model hashes and protocol before acquiring January 2026 records; evaluated unchanged models on 22,320 new station-hours, with departure MAE {edep:.3f} versus {elast:.3f} for last-hour ({egain:.1f}% lower).
- Evaluated integer/stochastic rebalancing and delayed truck routing with paired-event fleet accounting; retained negative service results and validated the implementation with {tests} tests and GitHub CI.

## Operations research / applied mathematics

**Evidence-Aware Bike-Share Rebalancing — Computational Research Project**

- Formulated constrained integer rebalancing and three-period stochastic MPC, benchmarking against no-intervention and distance-greedy policies on shared recorded-ride scenarios.
- Integrated co-loaded pickup-delivery routing, directed road travel, handling times and truck/driver limits into paired-event simulation; independently reconciled 181 routes and full fleet accounting.
- Showed that improved forecast-end inventory balance need not improve delayed service; quantified evidence coverage and preserved unsupported historical states rather than imputing operational certainty.

Keep “simulated”, “pooled” and named baselines when shortening. Do not turn a forecast error reduction into a claim of reduced real NYC stockouts.
'''
(app/'CV_EN.md').write_text(cv)
(app/'FINANCIAL_ENGINEERING_EN.md').write_text(f'''# Financial engineering application — project positioning

This is an urban operations project with transferable quantitative methods. Do not label it a derivatives-pricing, portfolio-return or trading-backtest project.

## CV entry

**Decision-Making under Uncertain Demand: Citi Bike Forecasting & Allocation — Research Project**  
Python · Statistical Learning · Integer Optimization · Stochastic MPC · Scenario Simulation

- Developed an AI-assisted forecasting/allocation research pipeline on 45.6M retained rides, combining chronological model evaluation with capacity-, distance- and budget-constrained integer decisions.
- Evaluated three-period stochastic MPC using correlated validation-residual scenarios and paired-event simulation; compared predictive error, service penalties and transport use under common requests.
- Validated unchanged models on a separately frozen January 2026 period (22,320 station-hours), with departure MAE {edep:.3f} versus {elast:.3f} for last-hour, without refitting.
- Audited incomplete state evidence and delayed execution: pooled departure MAE improved {gain:.1f}% over last-hour, while model ranking reversed on unsupported-start rows and road MILP failed to improve service in one scenario; preserved these limitations with {tests} tests and successful CI.

## SOP connection — editable

The quantitative theme of my AI-assisted Citi Bike project was the interaction between uncertain forecasts, constrained resource allocation and delayed execution. I examined fixed point forecasts alongside scenario-based stochastic MPC, and evaluated decisions through explicit inventory and fleet accounting. The results showed why lower prediction error or an optimized surrogate objective is insufficient to establish better realized outcomes. Evidence-stratified testing also revealed a reversal in model ranking when fresh state information was unavailable. These questions connect naturally to graduate study in financial engineering, data science and operations research: statistical estimation, stochastic optimization, model risk and decisions under incomplete information. The application is urban mobility; the claimed evidence is predictive and simulated, not financial profit, pricing accuracy or market impact.

The scenarios use four correlated residual blocks and expected penalties. They do not estimate a full probability law or implement a risk measure such as CVaR. “Cost” in the experiments is an artificial weighted proxy, not measured dollars. Personal contribution and AI assistance should match CONTRIBUTIONS.md.
''')
(app/'CV_ZH.md').write_text(f'''# 中文项目经历草稿

**纽约 Citi Bike 需求预测与调运优化｜计算研究项目（AI辅助实现）**

- 清洗处理约4,559万条有效骑行，构建30站、262,800行小时面板；采用时间顺序训练/验证/测试，比较四种借还车预测模型。
- 2025年全测试集借车MAE由上一小时基线{last:.3f}降至{dep:.3f}（降低{gain:.1f}%）；结合291万条历史状态变化记录开展证据分层，发现10,819条缺少新鲜初态支持的测试样本中模型排序反转。
- 下载新数据前在Git冻结模型哈希与方案；2026年1月22,320个站点小时上不重新训练，借车MAE为{edep:.3f}，对照上一小时基线{elast:.3f}，降低{egain:.1f}%。
- 建立整数规划、随机多期优化及考虑道路行驶/装卸/货车容量的配对事件仿真，独立核对181条路线与车队守恒；{tests}项测试及GitHub CI通过，保留不利结果和未观测状态。

以上是可由成果核验的项目内容。个人动词、日期和角色应匹配实际参与；未提供的学校、导师、论文或奖项不补写。个人贡献见CONTRIBUTIONS.md。
''')
(app/'SOP_PARAGRAPH_EN.md').write_text(f'''# Statement-of-purpose project paragraph — editable draft

This paragraph describes verified project work. Use it after reviewing the methods and adjusting personal-contribution verbs to your actual role; it does not establish your motivation or learning history.

In an AI-assisted computational project on NYC Citi Bike, I investigated how demand forecasts translate into rebalancing decisions under imperfect operational evidence. The pipeline processed 45.6 million retained rides and compared four next-hour count predictors using chronological validation. XGBoost reduced pooled departure MAE from {last:.3f} to {dep:.3f}, but an evidence-stratified audit revealed a more instructive limitation: the last-hour baseline performed better on 10,819 test station-hours lacking fresh start-state support. A separately frozen January 2026 evaluation then tested unchanged models on 22,320 new station-hours, achieving departure MAE {edep:.3f} against {elast:.3f} for last-hour. The project also connected integer and stochastic optimization with paired-ride simulation and delayed truck routing. In the road-constrained scenario, optimized rebalancing did not outperform no intervention. These results exposed the distinction between predictive accuracy, a mathematical proxy objective and realized service under modeling assumptions. The resulting code, source manifests, negative results and {tests} tests form a reproducible basis for further study of uncertainty-aware urban operations. A natural next step is prospective inventory validation and policy evaluation on a genuinely untouched period, rather than treating unobserved historical states as known.
''')
(app/'CONTRIBUTIONS.md').write_text('''# Project provenance and personal contribution

The project artifacts, computations and results exist and are linked to evidence. The conversation records the user supplying the project guide, choosing scope and requesting implementation/validation. An AI coding assistant wrote substantial code and documentation and executed the experiments. No supervisor, institutional affiliation, publication, award, multi-week work history or entirely manual implementation is established by those records.

Present this as an AI-assisted computational research project, and describe only your actual role. Before claiming experimental design, implementation or interpretation as personal contributions, review the corresponding code, reproduce the relevant results and be able to explain the decisions and limitations. CV entries supplied here are editable drafts, not certification of sole authorship. Follow the target institution's rules where it asks about assistance.

Concrete review targets: src/prepare.py (cleaning/selection), src/features.py and src/train.py (temporal models), src/optimize.py (integer constraints), src/event_replay.py (paired returns), src/transport_sim.py (delayed cargo), src/coverage_audit.py (evidence strata), tests/ (invariants), and reports/optimization_formulation.md. Check actual filenames before use; README and scripts provide entry points.
''')
(app/'INTERVIEW_GUIDE_ZH.md').write_text(f'''# 项目面试准备

1. **研究问题是什么？** 完成骑行数量的下一小时预测如何支持调运；缺失初态证据与运输延迟如何改变评价。不要把已完成骑行等同全部需求。
2. **为什么按时间切分？** 1–8月训练、9–10月验证、11–12月测试；随机切分可能泄漏未来模式。只用过去lag/shifted rolling，变换在训练拟合。
3. **预测结果是什么？** 全测试借车MAE：last-hour {last:.3f}，XGBoost {dep:.3f}，同43,950行，改善{gain:.1f}%。WAPE分母为实际保留记录数总和，不是潜在请求数。
4. **最大的新增发现？** 15分钟初态支持子集XGBoost更好；10,819条无支持子集XGBoost {u.loc['xgboost','mae']:.3f}、last-hour {u.loc['last_hour','mae']:.3f}。这是事后分层的条件描述，不证明证据缺失导致模型退化。
5. **19,632小时为什么不能填上？** 旧归档按车辆/空桩变化去重，压掉数量未变或只改标记的记录。缺记录既不能证明关闭，也不能证明正常营业；占年度理论面板约{100*protocol['remaining_fraction']:.2f}%。申请项目允许存在且严谨处理这个局限。
6. **优化变量与约束？** x_ij为整数调车量；库存/容量、预算、半径、供给/接收边界、禁止转运；安全区间松弛加运输代理成本。能用三站例子说明并看穷举测试。
7. **为什么最优模型不保证服务最好？** 最优仅针对给定可行域及代理目标。道路延迟、事件顺序和预测误差会改变实际路径服务；道路场景MILP未胜过不调运。
8. **如何保证公平？** 同一场景初态、同一请求与边界处理；把瞬时MILP标为资源放宽参照。基线、历史重置和道路场景不可混合比较成因果改善。
9. **如何保证车队守恒？** 站内+客户在途+客户暂存+卡车携货=初始车队+边界流入−边界流出。拒借取消对应还车；满桩货物留在卡车。
10. **统计区间有什么限制？** 日块配对bootstrap只描述情景及采样天条件下不确定性；新增分层在已看过测试后完成，2025分层是事后分析；2026年1月则在下载前冻结方案与模型后另作评估，两者分开报告。
11. **采集验证到什么程度？** 能证明实际时间戳、获取内容、归档及恢复；看monitoring_audit.json的schedule字段和间隔。不能从cron配置宣称长期连续运行。
12. **本人做了什么？** 依据真实参与回答，并说明AI辅助。不要背诵“全部独立手写”。从数据清洗、一个时间泄漏测试、一个MILP约束和一个负结果入手，亲自复跑并解释。

演示顺序：RESEARCH_BRIEF.pdf → pooled/分层误差 → 一个三站MILP例子 → 路线/库存账 → pytest/远程CI。源码和结果定位见CLAIMS_AND_EVIDENCE.csv。
''')
(app/'README.md').write_text('''# 研究生申请项目材料

本项目可以作为有代码、实际结果和局限分析的计算研究项目展示。剩余历史状态不需要被伪造为完整；研究质量来自可核验的方法与结论，而不是声称数据完美或保证调运提升。

- RESEARCH_BRIEF.pdf / .md / .html：两页英文研究摘要与完整文字版。
- CV_EN.md：数据科学、运筹应用数学等英文项目经历。
- FINANCIAL_ENGINEERING_EN.md：面向金融工程的项目经历与文书衔接，保留真实的城市运营研究定位。
- CV_ZH.md：中文经历。
- SOP_PARAGRAPH_EN.md：可调整的申请文书研究段落。
- INTERVIEW_GUIDE_ZH.md：关键方法、负结果及答辩准备。
- CLAIMS_AND_EVIDENCE.csv：申请中每项数字的来源和限定范围。
- CONTRIBUTIONS.md：AI辅助实现与个人贡献边界。

2026跨年评估可单独复现：安装requirements-lock.txt后运行 scripts/external_202601.py；它使用仓库 models/frozen_2025 中的小型冻结模型/过去上下文，只需下载约353.83MB的新月份原始档案。其他全年分析需完整项目数据。

正式研究报告见 ../reports/technical_report.pdf，完整方法和运行记录见仓库README。没有代填学校/导师/日期，没有虚构论文发表或真实运营影响。申请者应理解并能复现自己声称参与的部分；AI助手完成的代码不能自动变成“本人完全独立手写”。
''')
import base64
body='<h1>Evidence-Aware Citi Bike Forecasting and Rebalancing</h1>'+data.to_html()+'<img src="data:image/png;base64,'+base64.b64encode((fig/'coverage_and_ranking.png').read_bytes()).decode()+'"><pre>'+html.escape(brief)+'</pre>'
(app/'RESEARCH_BRIEF.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Citi Bike research brief</title><style>body{font-family:system-ui;max-width:1000px;margin:36px auto;line-height:1.6;padding:0 20px}img{max-width:100%}pre{font-family:inherit;white-space:pre-wrap}td,th{padding:8px;border:1px solid #ddd}table{border-collapse:collapse}</style>'+body+'</html>')

# Two-page English brief, separate from the ten-page technical report.
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
fontdir=Path(matplotlib.get_data_path())/'fonts/ttf'
for name,file in [('AppSans','DejaVuSans.ttf'),('AppBold','DejaVuSans-Bold.ttf')]:pdfmetrics.registerFont(TTFont(name,str(fontdir/file)))
styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='AppBody',fontName='AppSans',fontSize=9,leading=12,spaceAfter=8));styles.add(ParagraphStyle(name='AppHead',fontName='AppBold',fontSize=15,leading=19,spaceAfter=12));styles.add(ParagraphStyle(name='AppSmall',fontName='AppSans',fontSize=7.6,leading=10,spaceAfter=5))
story=[]
def p(text,style='AppBody'):story.append(Paragraph(escape(text),styles[style]))
def tab(frame):
    rows=[list(frame.columns)]+frame.astype(str).values.tolist();items=[[Paragraph(escape(str(v)),styles['AppSmall']) for v in row] for row in rows]
    table=Table(items,colWidths=[505/len(frame.columns)]*len(frame.columns),repeatRows=1);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2edf4')),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.extend([table,Spacer(1,9)])
p('Evidence-Aware Citi Bike Forecasting and Rebalancing','AppHead');p('Computational research project | 2025 NYC data | Reproducible, AI-assisted implementation','AppSmall')
p('Question: can next-hour recorded-ride forecasts improve simulated rebalancing service when historical station-state evidence is incomplete and truck movements take time?')
p('Data/method: 45.6M retained rides; 30 training-selected sites and 262,800 station-hours. Train Jan–Aug, validate Sep–Oct, test Nov–Dec; 43,950 test rows. Four fixed count models use past-only features. Metrics measure completed records, not all latent requests.')
tab(data.reset_index().rename(columns={'model':'Model','departures':'Departure MAE','arrivals':'Arrival MAE'}))
p(f'Pooled XGBoost departure MAE is {gain:.1f}% below last-hour. Historical evidence includes 2.91M state changes and dated official snapshots. The new post-hoc audit conditions on enabled, consistent source states known before the hour, with maximum age 5/15/30/60 minutes; no models are refitted or retuned.')
p(f'Frozen external evaluation: protocol and fitted model hashes were committed before acquiring January 2026 records. On 22,320 new station-hours, unchanged XGBoost departure MAE is {edep:.3f} versus {elast:.3f} for last-hour ({egain:.1f}% lower). All outcomes are retained; no refitting or tuning occurs.')
story.append(Image(str(fig/'coverage_and_ranking.png'),width=505,height=172))
p(f'At 15 minutes, 33,131 starts are supported and 10,819 are unsupported. On the latter, XGBoost departure MAE {u.loc["xgboost","mae"]:.3f} exceeds last-hour {u.loc["last_hour","mae"]:.3f}. Conditional performance is heterogeneous; differences in activity and evidence sampling preclude a causal explanation. Start-state support does not verify continuous operation through the future hour.')
story.append(PageBreak());p('Decision models, validation and limits','AppHead')
p('Methods: constrained integer rebalancing, three-period/four-scenario stochastic MPC, shared-request count simulation and paired recorded-ride replay. The full paired test spans 1,465 hours and handles rejected departures, cancelled returns, transit, external boundaries and held bikes.')
p('Delayed road experiment: 48 hours from the first eligible common historical anchor; two capacity-six co-loaded pickup-delivery trucks, directed OSRM driving times, 90 s/bike loading/unloading, hourly depot returns and driver/budget limits. Cargo changes inventory only at modeled pickup/delivery times. Independent checks reconcile 181 routes and actual cargo ledgers.')
small=road.loc[['none','road_greedy','road_milp'],['unmet_departures','truck_km','proxy_service_rate']].copy();small['proxy_service_rate']=(100*small.proxy_service_rate).round(3);small.truck_km=small.truck_km.round(2);tab(small.reset_index().rename(columns={'strategy':'Policy','unmet_departures':'Unserved records','truck_km':'Truck km','proxy_service_rate':'Service proxy %'}))
p('Finding: road MILP does not beat no intervention in this scenario. Optimal forecast-end balance under a proxy objective does not imply improved realized service. Current driving times, assumed depot, frozen usable capacity and blocked-return rules are scenario assumptions; this is not a measured operator effect.')
p(f'Unresolved evidence: 19,632 station-hours ({100*protocol["remaining_fraction"]:.2f}% of the annual grid) do not meet the strong historical sampling criterion. This is a different criterion/time scope from the 10,819 unsupported test starts. Change-filtered archives suppress unchanged-count and possibly flag-only updates. Missing observations remain unknown. Complete inventories would still not reveal every rejected request.')
p('Inference limits: the 2025 age audit is post-hoc; the separate January 2026 evaluation freezes protocol before data acquisition. Both use archived-count rolling one-step inputs, not a deployed online forecast. Comparisons are fair within the same rows/scenario. Different strata, dates or capacities are not interchangeable treatment groups. Daily bootstrap intervals are conditional, not causal guarantees.')
p(f'Engineering: {tests} local tests pass; public Research checks CI succeeded. Prospective GBFS collection stores unchanged counts, flag-only changes and failure heartbeats, with verified archives/restoration. Scheduling and cadence are audited from actual receipts; no long-term uptime claim is made.')
p('Reproduce: install exact requirements-lock.txt; run python -m pytest. Full research commands and data manifests are in README. scripts/missingness_experiment.py regenerates this audit; scripts/check_transport.py validates saved road results. The portable delivery contains the road window inputs and supports --reuse-rides.')
p('Repository: https://github.com/ryanwulikenature-glitch/ryan-wu','AppSmall');p('Sources: Citi Bike System Data; CityBikes historical archives (ODbL); official GBFS captures via Internet Archive; OpenStreetMap/OSRM driving proxy. Full attribution and empirical claim sources accompany the repository.','AppSmall');p('Implementation/experimental execution were AI-assisted. This is a computational project, not a peer-reviewed publication or live Citi Bike dispatch deployment. Personal contribution should be stated accurately.','AppSmall')
def footer(canvas,doc):canvas.setFont('AppSans',7);canvas.drawString(45,24,'Citi Bike research brief | complete methods and evidence in the linked repository');canvas.drawRightString(A4[0]-45,24,str(doc.page))
SimpleDocTemplate(str(app/'RESEARCH_BRIEF.pdf'),pagesize=A4,leftMargin=45,rightMargin=45,topMargin=38,bottomMargin=40,title='Evidence-Aware Citi Bike Forecasting and Rebalancing',author='Computational research project').build(story,onFirstPage=footer,onLaterPages=footer)
save_json(app/'portfolio_evidence.json',dict(tests=tests,remote_ci=ci,departure_mae=dep,last_hour_mae=last,pooled_relative_reduction_percent=gain,external_202601_departure_mae=edep,external_202601_last_hour_mae=elast,external_202601_relative_reduction_percent=egain,external_202601_rows=22320,unsupported_start_mae_xgboost=float(u.loc['xgboost','mae']),unsupported_start_mae_last_hour=float(u.loc['last_hour','mae']),unsupported_test_rows=int(u.loc['xgboost','n']),remaining_unknown_station_hours=19632,schedule_trigger_verified=monitor['schedule_trigger_verified'],provenance='AI-assisted implementation and experimental execution; personal role not independently certified'))
print('Generated research brief, bilingual CV drafts, SOP paragraph, interview guide and scoped evidence ledger.')
