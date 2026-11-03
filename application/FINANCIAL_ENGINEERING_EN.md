# Financial engineering application — project positioning

This is an urban operations project with transferable quantitative methods. Do not label it a derivatives-pricing, portfolio-return or trading-backtest project.

## CV entry

**Decision-Making under Uncertain Demand: Citi Bike Forecasting & Allocation — Research Project**  
Python · Statistical Learning · Integer Optimization · Stochastic MPC · Scenario Simulation

- Developed an AI-assisted forecasting/allocation research pipeline on 45.6M retained rides, combining chronological model evaluation with capacity-, distance- and budget-constrained integer decisions.
- Evaluated three-period stochastic MPC using correlated validation-residual scenarios and paired-event simulation; compared predictive error, service penalties and transport use under common requests.
- Validated unchanged models on a separately frozen January 2026 period (22,320 station-hours), with departure MAE 2.705 versus 3.235 for last-hour, without refitting.
- Audited incomplete state evidence and delayed execution: pooled departure MAE improved 23.6% over last-hour, while model ranking reversed on unsupported-start rows and road MILP failed to improve service in one scenario; preserved these limitations with 60 tests and successful CI.

## SOP connection — editable

The quantitative theme of my AI-assisted Citi Bike project was the interaction between uncertain forecasts, constrained resource allocation and delayed execution. I examined fixed point forecasts alongside scenario-based stochastic MPC, and evaluated decisions through explicit inventory and fleet accounting. The results showed why lower prediction error or an optimized surrogate objective is insufficient to establish better realized outcomes. Evidence-stratified testing also revealed a reversal in model ranking when fresh state information was unavailable. These questions connect naturally to graduate study in financial engineering, data science and operations research: statistical estimation, stochastic optimization, model risk and decisions under incomplete information. The application is urban mobility; the claimed evidence is predictive and simulated, not financial profit, pricing accuracy or market impact.

The scenarios use four correlated residual blocks and expected penalties. They do not estimate a full probability law or implement a risk measure such as CVaR. “Cost” in the experiments is an artificial weighted proxy, not measured dollars. Personal contribution and AI assistance should match CONTRIBUTIONS.md.
