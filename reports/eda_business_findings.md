# EDA: operational hypotheses from actual archive counts

These are descriptive associations across the full year. They were not used to tune test models. Zero archive records are not verified station operation.

## Morning outflow: largest negative mean netflow
```csv
station_id,station_name,morning_net
6756.01,W 43 St & 10 Ave,-19.69476372924649
6726.01,11 Ave & W 41 St,-10.853128991060025
6765.01,12 Ave & W 40 St,-9.831417624521073
6197.08,E 33 St & 1 Ave,-4.763729246487867
5763.03,Carmine St & 6 Ave,-4.201787994891443

```
## Evening inflow: largest mean netflow
```csv
station_id,station_name,evening_net
6756.01,W 43 St & 10 Ave,14.116219667943806
6765.01,12 Ave & W 40 St,12.233716475095786
6726.01,11 Ave & W 41 St,8.624521072796934
6364.07,6 Ave & W 33 St,7.670498084291188
6602.03,W 41 St & 8 Ave,7.430395913154534

```
## Interpretation
Morning station netflows range from -19.69 to 27.22 recorded bikes/hour; evening from -25.79 to 14.12. Opposite-signed sites are candidate complements, subject to radius and inventory constraints. This supports testing rebalancing during commuting peaks; it does not identify real shortages. Weekday/weekend profiles show timing differences without claiming statistical significance or attributing differences to weather.