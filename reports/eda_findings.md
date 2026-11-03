# EDA findings (official)

Observed completed rides; simulated service outcomes under assumptions

The figures use saved panel values. Largest daily totals:

```csv
hour,departures,arrivals,total
2025-09-11 00:00:00+00:00,16196.0,16211.0,32407.0
2025-09-30 00:00:00+00:00,16117.0,16020.0,32137.0
2025-09-26 00:00:00+00:00,15803.0,15652.0,31455.0
2025-09-18 00:00:00+00:00,15751.0,15533.0,31284.0
2025-09-19 00:00:00+00:00,15720.0,15543.0,31263.0
2025-10-07 00:00:00+00:00,15528.0,15614.0,31142.0
2025-09-09 00:00:00+00:00,15593.0,15317.0,30910.0
2025-07-16 00:00:00+00:00,15566.0,15308.0,30874.0
2025-06-11 00:00:00+00:00,15402.0,15468.0,30870.0
2025-06-04 00:00:00+00:00,15435.0,15348.0,30783.0

```

Station netflow range: -1.335 to 0.157 counts/hour. Persistent positive and negative netflow motivates moving bikes between complementary stations. Hour/weekday heatmap shows when that imbalance occurs.

For synthetic data, commute peaks and seasonal variation were imposed by the generator; they are not discoveries about NYC. For official data, peaks alone cannot establish weather effects or closures. The top dates are diagnostic candidates, not proven anomalies. Coordinates use an approximate Manhattan rectangle, not official borough membership.
