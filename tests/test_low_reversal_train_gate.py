from test_five_day_low_train_gate import cell

from five_day_low_train_gate import assess


def test_reversal_uses_same_strict_two_baseline_gate():
    assert assess(cell(3, .9), cell(1, .4), cell(2, .6))["pass"]
    assert not assess(cell(3, .5), cell(1, .4), cell(2, .6))["pass"]
