"""Audit actual poll cadence without turning snapshots into an uptime claim."""
from datetime import datetime,timezone
import statistics

def poll_cadence(polls,expected_seconds=60,grace_factor=1.5,minimum_window_hours=24):
    if expected_seconds<=0 or grace_factor<1 or minimum_window_hours<=0:raise ValueError('Invalid cadence thresholds')
    if len({p['poll_id'] for p in polls})!=len(polls):raise ValueError('Duplicate poll IDs')
    times=[]
    for p in polls:
        stamp=datetime.fromisoformat(p['started_utc'].replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError('Timezone required')
        times.append(stamp.astimezone(timezone.utc))
    times.sort();gaps=[(b-a).total_seconds() for a,b in zip(times,times[1:])];span=(times[-1]-times[0]).total_seconds() if times else 0
    long_gaps=[dict(start=a.isoformat(),end=b.isoformat(),seconds=(b-a).total_seconds()) for a,b in zip(times,times[1:]) if (b-a).total_seconds()>expected_seconds*grace_factor]
    return dict(polls=len(polls),first_poll_utc=times[0].isoformat() if times else None,last_poll_utc=times[-1].isoformat() if times else None,observed_span_hours=span/3600,expected_seconds=expected_seconds,gap_threshold_seconds=expected_seconds*grace_factor,median_gap_seconds=statistics.median(gaps) if gaps else None,max_gap_seconds=max(gaps) if gaps else None,long_gaps=long_gaps,failed_polls=sum(p['status']!='ok' for p in polls),minimum_window_hours=minimum_window_hours,minimum_window_observed=span>=minimum_window_hours*3600,all_observed_gaps_within_threshold=bool(gaps) and not long_gaps,continuous_uptime_verified=False,interpretation='Dated snapshots only. Gap compliance is a polling diagnostic, not proof of continuous station operation, latent demand or future service availability.')
