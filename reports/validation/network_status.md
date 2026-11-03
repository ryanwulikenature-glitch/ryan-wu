> 历史失败观察，已由 network_recovered.md 的成功下载证据取代。

# Observed network constraint

Official URL probes used inherited HTTPS proxy, with TLS verification enabled:

- https://s3.amazonaws.com/tripdata/202501-citibike-tripdata.zip — proxy CONNECT HTTP 403 Forbidden.
- https://citibikenyc.com/system-data — proxy CONNECT HTTP 403 Forbidden.

`git ls-remote origin` succeeded (empty repository); this is not missing GitHub authentication. Python package installation succeeded through allowed package-manager destinations. The ordinary command sandbox blocks proxy connections, so authorized external checks/installations used the escalation mechanism; official-destination denial persisted there. No route/proxy bypass was used.

Draft network additions saved: citibikenyc.com, s3.amazonaws.com, gbfs.citibikenyc.com. Saving does not apply or publish. No official rides were downloaded; all experiment results under outputs/demo are synthetic.
