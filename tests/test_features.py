import numpy as np
from app.ml.features import EMPTY, feats


def D(s):
    return np.datetime64(s, "D")


def ev(corrective=(), preventive=()):
    return {"c": np.array([D(x) for x in corrective], dtype="datetime64[D]"),
            "cd": np.array([100] * len(corrective), dtype=int),
            "p": np.array([D(x) for x in preventive], dtype="datetime64[D]")}


def test_event_on_snapshot_day_is_not_visible():
    e = ev(corrective=["2026-01-10"])
    same_day = feats(D("2024-01-01"), 2, "Robot", 90, e, D("2026-01-10"))
    assert same_day["n_fail_30"] == 0 and same_day["days_since_fail"] == 365
    next_day = feats(D("2024-01-01"), 2, "Robot", 90, e, D("2026-01-11"))
    assert next_day["n_fail_30"] == 1 and next_day["days_since_fail"] == 1


def test_pm_ratio_and_days_since_pm():
    f = feats(D("2020-01-01"), 3, "Presse", 60, ev(preventive=["2026-01-01"]), D("2026-03-02"))
    assert f["days_since_pm"] == 60
    assert abs(f["pm_ratio"] - 1.0) < 1e-9


def test_machine_without_history():
    f = feats(D("2025-01-01"), 1, "Visseuse", 30, EMPTY, D("2025-01-31"))
    assert f["days_since_fail"] == 365 and f["n_fail_365"] == 0 and f["downtime_90"] == 0
    assert f["days_since_pm"] == 30