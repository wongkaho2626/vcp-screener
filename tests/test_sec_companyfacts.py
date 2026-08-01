import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
from sec_companyfacts import as_filed_growth_events, comparable_growth, latest_event_before


def row(end, val, accn="a", form="10-Q", start=None):
    if start is None:
        year=int(end[:4]); start=f"{year}-01-01"
    return {"start":start,"end":end,"val":val,"accn":accn,"form":form}


def test_same_accession_quarterly_yoy_growth_only():
    rows=[row("2020-03-31",1,start="2020-01-01"),
          row("2021-03-31",1.5,start="2021-01-01"),
          row("2021-03-31",99,accn="future",start="2021-01-01")]
    assert comparable_growth(rows,"a","10-Q") == .5


def test_nonpositive_prior_is_not_a_growth_rate():
    rows=[row("2020-03-31",-1,start="2020-01-01"),
          row("2021-03-31",1,start="2021-01-01")]
    assert comparable_growth(rows,"a","10-Q") is None


def test_filing_is_available_strictly_after_filed_date():
    events=[{"filed":"2021-04-20"},{"filed":"2021-07-20"}]
    assert latest_event_before(events,"2021-04-20") is None
    assert latest_event_before(events,"2021-04-21")["filed"] == "2021-04-20"


def test_same_accession_margin_delta_uses_matching_revenue_periods():
    def facts(values):
        return {"units": {"USD": values}}
    prior = {**row("2020-03-31", 1, start="2020-01-01"),
             "filed": "2021-04-20"}
    current = {**row("2021-03-31", 2, start="2021-01-01"),
               "filed": "2021-04-20"}
    payload = {"facts": {"us-gaap": {
        "EarningsPerShareDiluted": facts([prior, current]),
        "Revenues": facts([{**prior, "val": 100}, {**current, "val": 120}]),
        "GrossProfit": facts([{**prior, "val": 40}, {**current, "val": 60}]),
        "OperatingIncomeLoss": facts([
            {**prior, "val": 10}, {**current, "val": 18},
        ]),
    }}}
    event = as_filed_growth_events(payload)[0]
    assert event["gross_margin"] == .5
    assert round(event["gross_margin_delta"], 10) == .1
    assert event["operating_margin"] == .15
    assert round(event["operating_margin_delta"], 10) == .05


def test_annual_cash_conversion_is_strictly_same_accession():
    def annual(end, val):
        year = int(end[:4])
        return {"start": f"{year}-01-01", "end": end, "val": val,
                "accn": "k", "form": "10-K", "filed": "2022-02-15"}
    def facts(values):
        return {"units": {"USD": values}}
    prior, current = annual("2020-12-31", 1), annual("2021-12-31", 2)
    payload = {"facts": {"us-gaap": {
        "EarningsPerShareDiluted": facts([prior, current]),
        "Revenues": facts([{**prior, "val": 100}, {**current, "val": 120}]),
        "NetCashProvidedByUsedInOperatingActivities": facts([
            {**prior, "val": 12}, {**current, "val": 30},
        ]),
        "NetIncomeLoss": facts([{**prior, "val": 10}, {**current, "val": 20}]),
    }}}
    event = as_filed_growth_events(payload)[0]
    assert event["cash_conversion"] == 1.5
