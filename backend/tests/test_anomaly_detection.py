from services.anomaly_detector import _check_series, detect_tenant_anomalies


def test_spike_detected_with_zscore():
    stable = [10.0] * 14 + [100.0]
    result = _check_series(stable, "sales_spike", owner_id=1, item_id=5, item_name="Milk", date_key="2026-01-01")
    assert result is not None
    assert result.severity in ("medium", "high", "critical")
    assert result.explanation and "standard deviation" in result.explanation
    assert result.detected_value == 100.0


def test_stable_series_no_anomaly():
    stable = [10.0] * 20
    assert _check_series(stable, "waste_spike", owner_id=1, item_id=5, item_name="X", date_key="2026-01-01") is None


def test_insufficient_data_is_conservative():
    assert _check_series([1.0, 2.0, 3.0], "sales_spike", 1, 5, "X", "2026-01-01") is None
    assert _check_series([], "sales_spike", 1, 5, "X", "2026-01-01") is None


def test_tenant_anomalies_no_data_returns_empty(db):
    assert detect_tenant_anomalies(db, 99999, "2026-01-01") == []