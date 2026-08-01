from five_day_low_train_gate import assess
from test_five_day_low_train_gate import cell


def test_limit_open_uses_same_strict_corrected_baseline_gate():
    assert assess(cell(3, .9), cell(1, .4), cell(2, .6))["pass"]
    assert not assess(cell(3, .9, trim=-.1), cell(1, .4), cell(2, .6))["pass"]
