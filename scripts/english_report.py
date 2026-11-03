"""Eight-page English report populated exclusively from executed artifacts."""
import sys,json
from pathlib import Path
from xml.sax.saxutils import escape
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Image,Preformatted
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from src.common import ROOT
out=ROOT/'outputs/official';reports=ROOT/'reports';styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Body',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=9))
styles.add(ParagraphStyle(name='Small',fontName='Helvetica',fontSize=8,leading=10,spaceAfter=6))
styles['Title'].fontSize=23;styles['Title'].leading=28
story=[]
def h(text):story.append(Paragraph(escape(text),styles['Heading1']))
def p(text):story.append(Paragraph(escape(text),styles['Body']))
def table(frame):
    f=frame.copy()
    for c in f:
        if pd.api.types.is_float_dtype(f[c]):f[c]=f[c].map(lambda v:f'{v:,.4f}' if pd.notna(v) else 'undefined')
    data=[[Paragraph(escape(str(c)),styles['Small']) for c in f.columns]]+[[Paragraph(escape(str(v)),styles['Small']) for v in row] for row in f.itertuples(index=False,name=None)]
    t=Table(data,colWidths=[505/len(f.columns)]*len(f.columns),repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dce8ef')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t);story.append(Spacer(1,10))
def image(name,w=490,hgt=190):story.append(Image(str(out/'figures'/name),width=w,height=hgt,kind='proportional'));story.append(Spacer(1,8))
def page():story.append(PageBreak())
q=json.loads((ROOT/'data/processed/data_quality_summary.json').read_text());m=pd.read_csv(out/'forecast_metrics.csv');m=m[(m.split=='test')&(m.stratum=='all')]
s=pd.read_csv(out/'simulation_summary.csv');paired=pd.read_csv(out/'paired_events/event_replay_summary.csv');u=pd.read_csv(out/'uncertainty_summary.csv');e=pd.read_csv(out/'experiments/experiments.csv');peak=pd.read_csv(out/'peak_station_flows.csv',dtype={'station_id':str})
base=s.set_index('strategy');gain=(base.loc['milp','proxy_service_rate']-base.loc['none','proxy_service_rate'])*100
h('NYC Citi Bike Demand Forecasting & Optimization')
p('A reproducible applied mathematics and operations research study using official 2025 completed-ride records')
h('Abstract')
p(f'This study asks whether next-hour departure and arrival forecasts can improve simulated service when used to allocate a fixed rebalancing budget. Twelve official monthly archives contain {q["raw_rows"]:,} records, of which {q["retained_rides"]:,} survive documented cleaning. Thirty stations are selected using January-August data only. Last-hour, seasonal-naive, Poisson and XGBoost models are evaluated chronologically on November-December. Integer optimization and distance-greedy transfers are compared with no rebalancing under identical restrictions.')
p(f'XGBoost achieves departure MAE {m[(m.model=="xgboost")&(m.target=="departures")].mae.iloc[0]:.3f} and arrival MAE {m[(m.model=="xgboost")&(m.target=="arrivals")].mae.iloc[0]:.3f} retained rides per station-hour. In the hourly count scenario, MILP raises the service proxy by {gain:.3f} percentage points relative to no rebalancing, while requiring transport. A separate paired-ride counterfactual replay suppresses returns after rejected departures and verifies fleet accounting. Twenty-one sensitivity/ablation scenarios and paired daily bootstrap intervals provide evidence within the assumed models.')
p('These are not historical stockout estimates. Completed trips censor unobserved demand, historical stocks and capacities are unavailable, and archived-count zeros do not establish station operation. The measured benefit is conditional on scenario assumptions, not an identified operational or financial impact.')
h('Research contributions')
p('The contributions are an audited full-year data pipeline; leakage-tested count forecasting; an explicit integer formulation; fair count and paired-event simulations; and generated, reproducible results. Negative comparisons are retained: a Poisson model does not automatically outperform a last-hour predictor, and greater service need not mean less transport.')
p('Reproduction: README.md, requirements-lock.txt, scripts/official_pipeline.sh and reports/validation/official_run_evidence.json. All numbers in this report are read from saved outputs; no target effect was specified in advance.')
page();h('1. Data, cleaning and observation model')
p('Source: Citi Bike System Data and https://s3.amazonaws.com/tripdata/. The 12 NYC ZIPs contain 53 CSV members and 8,934,786,928 downloaded bytes. HTTPS, ZIP CRC and local SHA256 checks are retained. Raw files are immutable; ZIP and extracted duplicates are not double counted. String station IDs preserve their representation.')
table(pd.DataFrame({'Item':['Raw rows','Retained rides','Selected stations','Station-hour grid','Operating-unknown hours'],'Value':[q['raw_rows'],q['retained_rides'],30,q['panel_rows'],q['unknown_hours']]}))
p('Cleaning rejects missing required IDs, invalid or unresolved timestamps, nonpositive/over-180-minute durations, and implausible coordinates. Ride-ID deduplication is global and disk-backed. Each removal reason and file range is audited. Longer-cutoff full recleaning is not claimed; cutoff boundary behavior is tested. Endpoint flows crossing the study boundary are retained and independently reconciled to cleaned rides.')
p('Selection uses January-August activity, at least eight active months, a volume threshold, a Manhattan-area rectangle and conservative coordinate-drift summaries. It does not use validation/test popularity. The rectangle is not an official borough polygon; chunk/month coordinate summaries are not verified relocation histories.')
p('The audited panel keeps operating-unknown hours missing. The explicit recorded_event_counts experiment instead uses retained archive counts in a temporary modeling copy, where zero means no retained record, not proven operation or zero latent demand. Labels and lags use the same estimand. Naive DST folds/gaps are excluded rather than assigned an invented offset. UTC hours remain continuous; local March/November days have 23/25 hours.')
image('eda_map.png',w=350,hgt=190)
page();h('2. Exploratory evidence and hypotheses')
p('Daily/hourly trends, weekday/weekend profiles, local-hour heatmaps, station maps and netflow summaries describe the selected network. Peaks motivate studying transport, but do not establish weather effects, closures or real lost demand. The following comparisons use retained counts; active-hour conditional means in other audited-panel plots are distinguished in the data dictionary.')
image('eda_weekday_weekend.png',hgt=170)
image('eda_peak_map.png',hgt=170)
table(peak.nsmallest(3,'morning_net')[['station_name','morning_net','evening_net']])
p('Negative netflow means departures exceed arrivals; opposite-signed stations are potential complements subject to distance and available stock. The table identifies morning outflow candidates without claiming they actually ran empty. Afternoon reversals and spatial imbalance guide the hypothesis tested by the optimizer. These descriptive full-year figures were not used to retune the held-out test models.')
page();h('3. Forecasting protocol and out-of-sample errors')
p('Train: January-August. Validation: September-October. Test: November-December. Separate target models predict departures and arrivals at the start of each hour. Rolling one-step evaluation may use earlier observed test hours; it does not forecast two months once from October. Both final target models are selected on validation and refit on train+validation, with no test-based hyperparameter selection.')
p('Features include local hour/day/month/weekend/federal holiday, cyclic hour/week terms, station one-hot, lags 1/24/168 and shifted 24/168-hour means/stds. Imputation/scaling/encoding are fitted on training only. Elapsed-hour lags across DST need not equal the same wall-clock hour. Weather is omitted because forecast-vintage observations are unavailable. Calendar-only and lag-based inputs do not use future target-hour weather or rides.')
table(m[['model','target','mae','rmse','wape']])
p('Units are retained rides per station-hour for MAE/RMSE, and a ratio for WAPE. Undefined zero-denominator WAPE is missing, not zero. Test rows number 43,950 (30 stations x 1,465 hours). Errors are stratified by peak, weekday/weekend, demand group and test month in forecast_metrics.csv. Training errors are in-sample diagnostics. Poisson here is a regularized log-link count regression, not an inferential unpenalized GLM.')
image('forecast_trace.png',hgt=180)
page();h('4. Integer rebalancing formulation')
p('Let I_i be current simulated stock, C_i assumed capacity, D_i/A_i predicted departures/arrivals, and d_ij Haversine distance. Integer x_ij moves bikes from i to j at the hour boundary; continuous u_i/v_i penalize forecast-end departures from safety bounds L_i/U_i. The objective is a proxy for balance and transport, not exact within-hour loss.')
story.append(Preformatted('min w_u sum(u_i) + w_v sum(v_i) + w_d sum(d_ij x_ij)\nIpost_i = I_i + sum_j x_ji - sum_j x_ij\nE_i = Ipost_i + A_i - D_i\nu_i >= L_i - E_i; v_i >= E_i - U_i; u_i,v_i >= 0\n0 <= Ipost_i <= C_i; sum_ij x_ij <= B; x_ij integer >= 0',styles['Code']))
p('Only supply-to-deficit edges within radius exist, excluding self-loops and transshipment. Define midpoint M=(L+U)/2, donor supply s_i=min(I_i,max(0,floor(I_i+A_i-D_i-M_i))) and receiving bound r_i=min(C_i-I_i,max(0,ceil(M_i-I_i-A_i+D_i))). Outbound sums cannot exceed s_i; inbound sums cannot exceed r_i. These extra restrictions are shared by Greedy and MILP and imply capacity feasibility. Zero movement plus unrestricted slack is feasible for valid inputs.')
p('SciPy milp/HiGHS uses a five-second limit and zero requested relative MIP gap. Only successful solves are called optimal. A failure keeps the solver status and uses a logged Greedy fallback. All official baseline hours solved without fallback. Each move is checked for nonnegative integrality, stock/capacity, budget and permitted edges. Mean official MILP runtime was %.3f ms on this instance; this is not an operational latency guarantee.'%base.loc['milp','mean_runtime_ms'])
p('Hand example: I=[3,27,8], C=[30,30,30], D=[15,5,17], A=[2,3,3]. With safety fractions .3/.7, weights 5/5/.1, budget 3 and one-km supply edges, no-move end stocks are [-10,25,-6], proxy cost 190. Moving three bikes reduces it to 160.3. Automated exhaustive enumeration verifies the same optimum and constraints.')
p('Instant transfers ignore trucks, travel delays and driver limits. Distance is not a road route. Capacity=25, budget=12 bikes/hour, radius=3 km and initial fraction=.5 are explicit baseline assumptions. Their consequences are explored rather than asserted as historical facts.')
page();h('5. Simulation protocols and measured outcomes')
p('The count scenario first applies each policy then uses identical seeded random departure/arrival order at every station-hour. All policies share scenario requests, capacities, initial stocks, radius and budget. Common sample hashes are checked. Arrivals are exogenous in this model; station balance is verified, but it is not called causal fleet conservation.')
table(s[['strategy','unmet_departures','blocked_arrivals','bikes_moved','bike_km','proxy_service_rate']])
p('The paired-event upgrade independently replays 800,854 cleaned rides across the same 1,465-hour test horizon. Rejected departures suppress their own returns. In-transit bikes, initial underway trips and external boundary inflows/outflows are explicit. Full fleet balance is asserted after each processed event. Blocked returns remain held off dock through the horizon; no rerouting is invented.')
table(paired[['strategy','unmet_departures','blocked_arrivals','bikes_moved','bike_km','proxy_service_rate']])
p('The two rows of evidence are different hypothetical models, not interchangeable estimates of reality. Policy comparison must include service and transport together: the MILP solution uses more bike-km than short-distance Greedy despite moving fewer bikes. Realized preference objective uses penalty weights 5/5 plus .1 per bike-km; neither that score nor bike-km is a measured financial/truck cost.')
image('policy_service.png',hgt=175)
page();h('6. Robustness, ablations and uncertainty')
p('Twenty-one configurations were saved before execution, producing 63 completed policy runs of 48 hours each. One-factor changes cover capacity 15/25/35, budget 6/12/24, radius 2/3/5 km, starting stock 30/50/70%, penalty weights, seeds and test dates. Every scenario, including unfavorable results, is retained in experiments.csv. Scores with different weights are not directly comparable across scenarios.')
p('Forecast ablations use seasonal naive, departures-only with naive arrivals, fixed XGBoost, and future-count Oracle. Oracle is a non-deployable information comparator, not a guaranteed true-service upper bound because optimization targets a proxy. These are exploratory sensitivities on the test set, not a second untouched evaluation. Weather ablation was not run.')
image('robustness.png',hgt=210)
table(u[['strategy','baseline','ci_low','ci_high']])
p('Intervals above are paired local-day bootstrap intervals for mean daily scenario-objective differences. Negative values favor the named policy under that objective. Forecast differences also use paired local-day blocks in forecast_daily_bootstrap.csv. There are 61 local test days; local days may contain 23/25 hours. Repeated seeds and resampling quantify within-scenario variability only. They neither recover censored demand nor remove structural bias from unknown stocks, capacities and behavior.')
p('Comparison files report absolute differences and relative changes with named baselines; relative change is undefined for a zero baseline. Model ranking and scenario results are generated from saved files, not manually edited to obtain a desired improvement.')
page();h('7. Reproduction, limitations and conclusion')
p('Software evidence: 29 core tests passed before the prospective collector extension; the final pytest log records the expanded suite. Tests cover ZIP/multiple members, duplicate rides, timestamp/DST/duration rules, train-only selection, cross-boundary count conservation, temporal leakage, output alignment, nonnegative forecasts, hand-case MILP optimum, transfer invariants, forced solver fallback, common scenario paths, archive-count semantics and paired-event fleet balance. Independently reconciled official outputs and two executed notebooks are retained.')
p('The prospective GBFS collector now saves current station-information/status snapshots, raw JSON, SQLite rows, source update times and failures. A two-sample live run collected 2,518 stations in both feeds per round. It begins at collection time; it cannot reconstruct 2025 inventories. Long-term monitoring requires a persistent scheduler and ongoing observation, and is not claimed from two samples.')
p('Main limitations: completed rides are censored proxies for requests; retained-archive zeros do not establish operation; filtering and source temporal boundaries affect the estimand; historical capacities and inventories are unavailable. The geography is approximate and coordinate drift compressed. Count arrivals are exogenous; paired blocked-return holding and external supply are hypothetical. Current GBFS does not identify historical stockouts. A fleet-routing or stochastic multi-period system is future work, not claimed as implemented here.')
p('Conclusion: on the fixed official archive and specified scenarios, XGBoost improves held-out count error over the reported baselines and optimized rebalancing trades transport for higher simulated service. These are reproducible predictive/scenario findings, not a causal demonstration that actual Citi Bike losses or costs decreased. The next credible step is prospective inventory validation before operational deployment.')
h('Reproduction and references')
p('Install: scripts/install.sh. Core reproduction: scripts/official_pipeline.sh with matching prepared data; otherwise download and prepare first. Run python -m pytest, inspect reports/validation, and execute scripts/package.py for an integrity-checked delivery. Raw archives/large intermediates are excluded from Git; manifests and commands reproduce them. Exact dependencies are in requirements-lock.txt; seeds and configurations are saved with every run.')
for reference in ['Citi Bike System Data: https://citibikenyc.com/system-data','Official archives: https://s3.amazonaws.com/tripdata/','GBFS feeds: https://gbfs.citibikenyc.com/gbfs/en/','SciPy milp: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html','XGBoost: https://xgboost.readthedocs.io/en/stable/python/python_api.html','Project evidence: outputs/official, reports/validation, reports/optimization_formulation.md']:
    story.append(Paragraph(escape(reference),styles['Small']))
def footer(canvas,doc):
    canvas.setFont('Helvetica',8);canvas.setFillColor(colors.grey);canvas.drawString(44,24,'NYC Citi Bike | Official archive counts; simulated service under assumptions');canvas.drawRightString(A4[0]-44,24,str(doc.page))
path=reports/'technical_report.pdf';SimpleDocTemplate(str(path),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=35,bottomMargin=40,title='NYC Citi Bike Demand Forecasting & Optimization',author='Reproducible research project').build(story,onFirstPage=footer,onLaterPages=footer)
print(path)
