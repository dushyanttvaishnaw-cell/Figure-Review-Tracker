import pandas as pd

from figreview.checks import check_caption_numbers, check_claims, check_labels, compare_values

SRC = pd.DataFrame({"model": ["A", "B"], "task": ["x", "x"], "score_pct": [50.0, 70.0]})


def checks(findings):
    return [f.check for f in findings]


def test_matching_values_pass():
    plotted = SRC.to_dict("records")
    assert compare_values(plotted, SRC, ["model", "task"], ["score_pct"], 1) == []


def test_rounding_within_precision_passes():
    plotted = [{"model": "A", "task": "x", "score_pct": 50.04}, {"model": "B", "task": "x", "score_pct": 70.0}]
    assert compare_values(plotted, SRC, ["model", "task"], ["score_pct"], 1) == []


def test_typo_is_caught():
    plotted = [{"model": "A", "task": "x", "score_pct": 55.0}, {"model": "B", "task": "x", "score_pct": 70.0}]
    f = compare_values(plotted, SRC, ["model", "task"], ["score_pct"], 1)
    assert checks(f) == ["value_mismatch"]
    assert f[0].details == {"row": "A, x", "column": "score_pct", "chart": 55.0, "source": 50.0}


def test_missing_and_extra_rows():
    plotted = [{"model": "A", "task": "x", "score_pct": 50.0}, {"model": "C", "task": "x", "score_pct": 10.0}]
    assert sorted(checks(compare_values(plotted, SRC, ["model", "task"], ["score_pct"], 1))) == ["extra_row", "missing_row"]


def test_caption_numbers():
    assert check_caption_numbers("B reached 70.0% while A got 50%.", SRC, ["score_pct"], 1) == []
    assert checks(check_caption_numbers("B reached 72%.", SRC, ["score_pct"], 1)) == ["caption_number"]
    assert check_caption_numbers("95% intervals; B reached 70%.", SRC, ["score_pct"], 1, allow=[95]) == []


def test_claims():
    good = {"type": "max", "column": "score_pct", "group_by": "task", "entity_col": "model", "entity": "B", "text": "B is best"}
    bad = {**good, "entity": "A", "text": "A is best"}
    assert check_claims([good], SRC) == []
    assert checks(check_claims([bad], SRC)) == ["claim"]
    assert checks(check_claims([{"type": "all_above", "column": "score_pct", "threshold": 60, "text": "all over 60"}], SRC)) == ["claim"]


def test_labels_need_units():
    fig = {"title": "T", "x_label": "Model (name)", "y_label": "Score", "caption": "Figure 1. X."}
    assert checks(check_labels(fig)) == ["units"]
