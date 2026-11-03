import pytest
from src.monitoring import poll_cadence

def test_detects_real_gaps_without_filling_missing_heartbeats():
    rows=[dict(poll_id=str(i),started_utc=t,status='ok') for i,t in enumerate(['2026-11-03T00:00:00Z','2026-11-03T00:01:00Z','2026-11-03T00:04:00Z'])]
    r=poll_cadence(rows);assert r['polls']==3 and len(r['long_gaps'])==1 and r['max_gap_seconds']==180
    assert not r['minimum_window_observed'] and not r['continuous_uptime_verified']

def test_long_clean_window_still_does_not_verify_continuous_operation():
    rows=[dict(poll_id='a',started_utc='2026-11-01T00:00:00Z',status='ok'),dict(poll_id='b',started_utc='2026-11-02T00:00:00Z',status='failed')]
    r=poll_cadence(rows,expected_seconds=86400);assert r['minimum_window_observed'] and r['all_observed_gaps_within_threshold']
    assert r['failed_polls']==1 and not r['continuous_uptime_verified']

def test_duplicate_or_naive_poll_time_is_rejected():
    row=dict(poll_id='a',started_utc='2026-11-03T00:00:00Z',status='ok')
    with pytest.raises(ValueError,match='Duplicate'):poll_cadence([row,row])
    with pytest.raises(ValueError,match='Timezone'):poll_cadence([dict(row,started_utc='2026-11-03T00:00:00')])
