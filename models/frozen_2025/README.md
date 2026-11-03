# Frozen 2025 model/context artifacts

These four fitted pipelines exactly match hashes committed before acquiring January2026 targets. They were fitted/refitted on January–October2025 only. history_tail.parquet contains30x168 preceding recorded-count rows; carryover.parquet preserves independently extracted December-origin arrivals (zero in the captured archive). stations.csv preserves the original training-only site list.

No original raw trip ZIPs are included. All artifacts and context hashes are in MANIFEST.json. scripts/external_202601.py can use these files in a clean checkout, downloading only the353.83MB January2026 archive. The full project bundle remains necessary for the other full-year reproductions. Counts are completed archive records, not latent demand or verified continuous station operation.

Source context is aggregated official Citi Bike trip-history records; underlying operator data-use terms apply. It is independent of the CityBikes historical-state derivative database.
