#!/usr/bin/env python3
"""Build the self-contained HTML trade-log page (interactive ledger).

Renders every trade from one or more ``vcp_trades_*.json`` reports into a
single sortable/filterable HTML file with live-recomputed summary KPIs, plus
a static "exit-rule experiments" panel documenting the 2026-07-10 exit study
(stop-only / strict 3-tier / asymmetric cull-ride — none beat the baseline;
see scripts/exit_stress_experiments.py to reproduce those numbers).

Usage:
    python3 scripts/build_trade_log_page.py \\
        SP500=backtests/csv_full/vcp_trades_X.json \\
        R2K=backtests/r2k/vcp_trades_merged.json \\
        -o backtests/trade_log.html

The first label gets the accent chip colour. Output is fully self-contained
(no external requests) and renders in light and dark themes.
"""

from __future__ import annotations

import argparse
import json
import os


def build_rows(sources: list[tuple[str, str]]) -> list[list]:
    rows = []
    for label, path in sources:
        payload = json.load(open(path))
        for t in payload["trades"]:
            rows.append([
                label, t["symbol"], t["entry_date"], t["entry_price"],
                t["stop_price"], t["exit_date"], t["exit_price"],
                t["hold_bars"], t["exit_reason"], t["ret_pct"],
                t.get("spy_ret_pct"), t.get("excess_vs_spy_pct"),
            ])
    return rows


def render(sources: list[tuple[str, str]]) -> str:
    rows = build_rows(sources)
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    sources_desc = "; ".join(
        f"{label} &mdash; {counts.get(label, 0)} trades ({os.path.basename(path)})"
        for label, path in sources
    )
    unibuttons = "\n".join(
        f'    <button data-u="{label}">{label}</button>' for label, _ in sources
    )
    page = TEMPLATE
    page = page.replace("__COUNT__", f"{len(rows):,}")
    page = page.replace("__SOURCES__", sources_desc)
    page = page.replace("__UNIBUTTONS__", unibuttons)
    page = page.replace("__FIRST_LABEL__", json.dumps(sources[0][0]))
    page = page.replace("__DATA__", json.dumps(rows, separators=(",", ":")))
    return page


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the HTML trade-log page")
    ap.add_argument("sources", nargs="+", metavar="LABEL=TRADES_JSON",
                    help="e.g. SP500=backtests/csv_full/vcp_trades_X.json")
    ap.add_argument("--output", "-o", default="backtests/trade_log.html")
    args = ap.parse_args()

    sources = []
    for s in args.sources:
        if "=" not in s:
            ap.error(f"source must be LABEL=path, got: {s}")
        label, path = s.split("=", 1)
        if not os.path.isfile(path):
            ap.error(f"trades JSON not found: {path}")
        sources.append((label, path))

    page = render(sources)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write(page)
    print(f"wrote {args.output} ({len(page) // 1024} KB, "
          f"{sum(1 for _ in build_rows(sources))} trades)")


TEMPLATE = """<title>VCP Backtest Trade Log</title>
<style>
:root{
  --bg:#FAFAF7; --surface:#FFFFFF; --ink:#1C2024; --muted:#6E6A5E;
  --line:#E3E0D6; --accent:#B7791F; --accent-ink:#8A5A12;
  --pos:#1A7F4B; --neg:#C03A2B; --chip:#F0EDE4; --head:#F5F3EC;
}
@media (prefers-color-scheme: dark){:root{
  --bg:#15181B; --surface:#1D2126; --ink:#E8E6E1; --muted:#9A958A;
  --line:#2E333A; --accent:#D9A441; --accent-ink:#E5B95C;
  --pos:#4CC38A; --neg:#E5654E; --chip:#262B31; --head:#22262C;
}}
:root[data-theme="dark"]{
  --bg:#15181B; --surface:#1D2126; --ink:#E8E6E1; --muted:#9A958A;
  --line:#2E333A; --accent:#D9A441; --accent-ink:#E5B95C;
  --pos:#4CC38A; --neg:#E5654E; --chip:#262B31; --head:#22262C;
}
:root[data-theme="light"]{
  --bg:#FAFAF7; --surface:#FFFFFF; --ink:#1C2024; --muted:#6E6A5E;
  --line:#E3E0D6; --accent:#B7791F; --accent-ink:#8A5A12;
  --pos:#1A7F4B; --neg:#C03A2B; --chip:#F0EDE4; --head:#F5F3EC;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  font-size:13px; line-height:1.5;
}
.wrap{max-width:1180px; margin:0 auto; padding:28px 20px 60px; display:flex; flex-direction:column; gap:18px}
header .eyebrow{font-size:11px; letter-spacing:.18em; text-transform:uppercase; color:var(--accent-ink)}
header h1{margin:.2em 0 .1em; font-size:26px; font-weight:700; letter-spacing:-.01em; text-wrap:balance}
header .sub{color:var(--muted); max-width:72ch}
.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px}
.kpi{background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:10px 14px}
.kpi .lbl{font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted)}
.kpi .val{font-size:20px; font-weight:700; font-variant-numeric:tabular-nums; margin-top:2px}
.kpi .val.pos{color:var(--pos)} .kpi .val.neg{color:var(--neg)}
.controls{display:flex; flex-wrap:wrap; gap:10px; align-items:center}
.seg{display:inline-flex; border:1px solid var(--line); border-radius:6px; overflow:hidden}
.seg button{
  background:var(--surface); color:var(--muted); border:0; padding:7px 14px;
  font:inherit; cursor:pointer; border-right:1px solid var(--line)
}
.seg button:last-child{border-right:0}
.seg button.on{background:var(--accent); color:var(--bg); font-weight:700}
select,input[type=search]{
  background:var(--surface); color:var(--ink); border:1px solid var(--line);
  border-radius:6px; padding:7px 10px; font:inherit
}
input[type=search]{width:150px}
select:focus,input:focus,button:focus-visible{outline:2px solid var(--accent); outline-offset:1px}
.count{color:var(--muted); margin-left:auto}
details.exp{background:var(--surface); border:1px solid var(--line); border-radius:6px}
details.exp>summary{
  cursor:pointer; padding:12px 16px; font-weight:700; list-style:none;
  display:flex; align-items:center; gap:10px
}
details.exp>summary::before{content:"+"; color:var(--accent-ink); font-weight:700}
details.exp[open]>summary::before{content:"\\2212"}
.expbody{padding:0 16px 16px; display:flex; flex-direction:column; gap:14px}
.expgrid{display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:14px}
.expcard{border:1px solid var(--line); border-radius:6px; overflow-x:auto}
.expcard h3{
  margin:0; padding:8px 12px; font-size:11px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); background:var(--head);
  border-bottom:1px solid var(--line)
}
.expcard table{min-width:340px; width:100%}
.expcard td,.expcard th{padding:4px 10px; font-size:12px}
.expcard thead th{position:static; cursor:default}
.expcard tr.base td{background:var(--chip); font-weight:700}
.expnote{color:var(--muted); font-size:12px; max-width:88ch}
.expnote strong{color:var(--ink)}
.flag{color:var(--neg); font-weight:700}
.tablebox{background:var(--surface); border:1px solid var(--line); border-radius:6px; overflow:auto; max-height:72vh}
table{border-collapse:collapse; width:100%; min-width:980px; font-variant-numeric:tabular-nums}
thead th{
  position:sticky; top:0; background:var(--head); color:var(--muted);
  font-size:10px; letter-spacing:.12em; text-transform:uppercase; font-weight:600;
  text-align:right; padding:9px 10px; border-bottom:1px solid var(--line);
  cursor:pointer; user-select:none; white-space:nowrap
}
thead th.l{text-align:left}
thead th .arr{color:var(--accent-ink)}
tbody td{padding:5px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap}
tbody td.l{text-align:left}
tbody tr:hover{background:var(--chip)}
.chip{display:inline-block; padding:1px 7px; border-radius:4px; background:var(--chip); color:var(--muted); font-size:11px}
.chip.sp{color:var(--accent-ink)}
.pill{display:inline-block; padding:1px 7px; border-radius:9px; font-size:11px; background:var(--chip)}
.pill.stop{color:var(--neg)} .pill.timeout{color:var(--muted)} .pill.open{color:var(--accent-ink)}
td.pos{color:var(--pos)} td.neg{color:var(--neg)}
.sym{font-weight:700}
footer{color:var(--muted); font-size:12px; max-width:80ch}
footer strong{color:var(--ink)}
@media (prefers-reduced-motion: no-preference){
  tbody tr{transition:background .12s ease}
}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">vcp-screener &middot; research ledger &middot; 2016&ndash;2026</div>
  <h1>Backtest Trade Log &mdash; __COUNT__ simulated trades</h1>
  <div class="sub">Every accepted breakout trade from: __SOURCES__.
  Entry at breakout close, stop at max(contraction low, entry &minus;8%), 60-bar
  timeout. Click a column to sort; filters recompute the summary live.</div>
</header>

<div class="kpis" id="kpis"></div>

<details class="exp">
<summary>Exit-rule experiments &mdash; every alternative tested against the baseline (2026-07-10)</summary>
<div class="expbody">
<div class="expnote">
Same entries as the ledger below, exits re-simulated per config. Mean/median are
excess vs SPY over each leg's own holding period (pp). <strong>No config robustly
beats the boring baseline</strong>; the one shiny number (stop-only S&amp;P +23.97)
is a top-10-trade survivorship lottery &mdash; drop its 10 best trades and it flips
to <span class="flag">&minus;7.8 (t &minus;2.7)</span> on S&amp;P and
<span class="flag">&minus;9.2 (t &minus;8.1)</span> on R2K.
</div>
<div class="expgrid">
<div class="expcard">
<h3>S&amp;P 500 &middot; 326 trades &middot; offline CSV</h3>
<table><thead><tr><th class="l">Config</th><th>MeanExc</th><th>t</th><th>MedExc</th><th>Win%</th><th>Hold</th></tr></thead>
<tbody>
<tr class="base"><td class="l">baseline stop+60d</td><td>-0.53</td><td>-0.86</td><td>-2.84</td><td>37.4</td><td>39.8</td></tr>
<tr><td class="l">stop-only (no timeout)</td><td class="pos">+23.97</td><td>2.04</td><td class="neg">-8.31</td><td>19.6</td><td>319.6</td></tr>
<tr><td class="l">strict PT20%/MA50</td><td>-0.29</td><td>-0.60</td><td>-2.55</td><td>32.2</td><td>29.2</td></tr>
<tr><td class="l">strict PT25%/MA50</td><td>-0.22</td><td>-0.44</td><td>-2.55</td><td>32.2</td><td>29.2</td></tr>
<tr><td class="l">cull d10 ret&lt;0</td><td>-0.25</td><td>-0.49</td><td>-2.33</td><td>33.7</td><td>30.6</td></tr>
<tr><td class="l">cull d15 ret&lt;5</td><td>-0.50</td><td>-1.07</td><td>-1.54</td><td>39.0</td><td>23.0</td></tr>
<tr><td class="l">ride120</td><td>-0.61</td><td>-0.91</td><td>-2.84</td><td>37.1</td><td>41.1</td></tr>
<tr><td class="l">ride-trail25</td><td>-0.60</td><td>-0.91</td><td>-2.97</td><td>37.1</td><td>41.8</td></tr>
<tr><td class="l">cull+ride-trail</td><td>-0.32</td><td>-0.57</td><td>-2.36</td><td>33.4</td><td>32.7</td></tr>
</tbody></table>
</div>
<div class="expcard">
<h3>Russell 2000 &middot; ~905 trades &middot; yfinance</h3>
<table><thead><tr><th class="l">Config</th><th>MeanExc</th><th>t</th><th>MedExc</th><th>Win%</th><th>Hold</th></tr></thead>
<tbody>
<tr class="base"><td class="l">baseline stop+60d</td><td>-0.41</td><td>-0.81</td><td>-4.63</td><td>34.8</td><td>38.5</td></tr>
<tr><td class="l">stop-only (no timeout)</td><td>+0.23</td><td>0.06</td><td class="neg">-9.36</td><td>15.5</td><td>231.1</td></tr>
<tr><td class="l">strict PT20%/MA50</td><td>-0.46</td><td>-1.24</td><td>-3.36</td><td>31.3</td><td>26.8</td></tr>
<tr><td class="l">strict PT25%/MA50</td><td>-0.44</td><td>-1.14</td><td>-3.39</td><td>30.7</td><td>26.8</td></tr>
<tr><td class="l">cull d10 ret&lt;0</td><td>-0.46</td><td>-1.06</td><td>-2.94</td><td>29.3</td><td>29.4</td></tr>
<tr><td class="l">cull d15 ret&lt;5</td><td>-0.48</td><td>-1.18</td><td>-2.43</td><td>33.5</td><td>23.1</td></tr>
<tr><td class="l">ride120</td><td class="neg">-0.79</td><td>-1.63</td><td>-4.67</td><td>34.4</td><td>40.9</td></tr>
<tr><td class="l">ride-trail25</td><td>-0.59</td><td>-1.10</td><td>-4.65</td><td>34.4</td><td>41.0</td></tr>
<tr><td class="l">cull+ride-trail</td><td>-0.68</td><td>-1.45</td><td>-3.04</td><td>28.7</td><td>31.6</td></tr>
</tbody></table>
</div>
</div>
<div class="expnote">
<strong>Verdicts.</strong>
Strict 3-tier (Minervini sell framework) degenerates to a faster, shallower stop:
2/3 of trades exit via MA50-break at median day 18&ndash;19 and only 10&ndash;15%
ever reach the +20&ndash;25% scale-out. Asymmetric exits fail because day-10
strength has zero forward predictive power (R2K conditional means: &minus;0.01 vs
&minus;0.02) &mdash; riding surges catches mean reversion in both universes, and
culling laggards sign-flips between universes. Earlier grids (8&ndash;45% trails,
ATR&times;2&ndash;5, full profit targets, MA10/20/50-break) were equally null;
MA10/20-break is significantly harmful on R2K (t &minus;3.4/&minus;3.6).
What actually survives validation lives on the buy side: MA20 pullback entry
(+1.36pp paired, t 3.13) and Edge Rank sizing. Reproduce with
scripts/exit_stress_experiments.py.
</div>
</div>
</details>

<div class="controls">
  <div class="seg" id="uniseg" role="group" aria-label="Universe">
    <button data-u="ALL" class="on">All</button>
__UNIBUTTONS__
  </div>
  <select id="year" aria-label="Entry year"><option value="">All years</option></select>
  <select id="reason" aria-label="Exit reason"><option value="">All exits</option></select>
  <select id="outcome" aria-label="Outcome">
    <option value="">Win &amp; loss</option>
    <option value="win">Beat SPY</option>
    <option value="loss">Lagged SPY</option>
  </select>
  <input type="search" id="sym" placeholder="Symbol&hellip;" aria-label="Symbol search">
  <span class="count" id="count"></span>
</div>

<div class="tablebox" tabindex="0">
<table id="tbl">
<thead><tr>
  <th class="l" data-k="0">Univ</th>
  <th class="l" data-k="1">Symbol</th>
  <th class="l" data-k="2">Entry date</th>
  <th data-k="3">Entry $</th>
  <th data-k="4">Stop $</th>
  <th class="l" data-k="5">Exit date</th>
  <th data-k="6">Exit $</th>
  <th data-k="7">Hold</th>
  <th class="l" data-k="8">Exit via</th>
  <th data-k="9">Ret %</th>
  <th data-k="10">SPY %</th>
  <th data-k="11">Excess %</th>
</tr></thead>
<tbody id="tb"></tbody>
</table>
</div>

<footer>
  <strong>Read with the caveats:</strong> close-based fills, no transaction costs or slippage;
  both universes carry survivorship bias (R2K lost 26% of names to delistings), so these
  figures are an optimistic ceiling. Mean excess vs SPY is statistically zero in every
  dataset &mdash; this ledger documents beta, not alpha. Sources:
  vcp_trades_2026-07-10_003110.json (S&amp;P, offline CSV) and vcp_trades_merged.json
  (R2K batches 1+2, yfinance).
</footer>
</div>

<script>
const DATA = __DATA__;
const DATA_FIRST_LABEL = __FIRST_LABEL__;
const tb = document.getElementById('tb');
const fmt = (v,d=2) => v==null ? '\\u2014' : v.toFixed(d);
let uni='ALL', sortK=2, sortDir=1;

const years = [...new Set(DATA.map(r=>r[2].slice(0,4)))].sort();
const yearSel = document.getElementById('year');
years.forEach(y=>yearSel.insertAdjacentHTML('beforeend',`<option>${y}</option>`));
const reasons = [...new Set(DATA.map(r=>r[8]))].sort();
const reasonSel = document.getElementById('reason');
reasons.forEach(r=>reasonSel.insertAdjacentHTML('beforeend',`<option>${r}</option>`));

function filtered(){
  const y=yearSel.value, re=reasonSel.value,
        oc=document.getElementById('outcome').value,
        q=document.getElementById('sym').value.trim().toUpperCase();
  return DATA.filter(r=>
    (uni==='ALL'||r[0]===uni) &&
    (!y||r[2].startsWith(y)) &&
    (!re||r[8]===re) &&
    (!oc|| (oc==='win' ? r[11]>0 : r[11]<=0)) &&
    (!q||r[1].includes(q)));
}
function median(v){ if(!v.length) return null;
  const s=[...v].sort((a,b)=>a-b), m=s.length>>1;
  return s.length%2 ? s[m] : (s[m-1]+s[m])/2; }
function kpis(rows){
  const exc=rows.map(r=>r[11]).filter(v=>v!=null);
  const ret=rows.map(r=>r[9]);
  const mean=a=>a.length?a.reduce((x,y)=>x+y,0)/a.length:null;
  const win=exc.length?100*exc.filter(v=>v>0).length/exc.length:null;
  const hold=mean(rows.map(r=>r[7]));
  const cells=[
    ['Trades', rows.length.toLocaleString(), ''],
    ['Mean return', fmt(mean(ret))+'%', mean(ret)>0?'pos':'neg'],
    ['Mean excess vs SPY', fmt(mean(exc))+'%', mean(exc)>0?'pos':'neg'],
    ['Median excess', fmt(median(exc))+'%', median(exc)>0?'pos':'neg'],
    ['Beat-SPY rate', win==null?'\\u2014':fmt(win,1)+'%', ''],
    ['Avg hold (bars)', hold==null?'\\u2014':fmt(hold,1), ''],
  ];
  document.getElementById('kpis').innerHTML = cells.map(([l,v,c])=>
    `<div class="kpi"><div class="lbl">${l}</div><div class="val ${c}">${v}</div></div>`).join('');
}
function render(){
  const rows=filtered().sort((a,b)=>{
    const x=a[sortK], y=b[sortK];
    if(x==null) return 1; if(y==null) return -1;
    return (x<y?-1:x>y?1:0)*sortDir;
  });
  kpis(rows);
  document.getElementById('count').textContent =
    rows.length.toLocaleString()+' / '+DATA.length.toLocaleString()+' trades';
  tb.innerHTML = rows.map(r=>{
    const exc=r[11], cls=exc==null?'':exc>0?'pos':'neg';
    const rcls=r[8]==='stop'?'stop':r[8]==='timeout'?'timeout':'open';
    const uchip=`<span class="chip ${r[0]===DATA_FIRST_LABEL?'sp':''}">${r[0]}</span>`;
    return `<tr><td class="l">${uchip}</td><td class="l sym">${r[1]}</td>`+
      `<td class="l">${r[2]}</td><td>${fmt(r[3])}</td><td>${fmt(r[4])}</td>`+
      `<td class="l">${r[5]}</td><td>${fmt(r[6])}</td><td>${r[7]}</td>`+
      `<td class="l"><span class="pill ${rcls}">${r[8]}</span></td>`+
      `<td class="${r[9]>0?'pos':'neg'}">${fmt(r[9])}</td><td>${fmt(r[10])}</td>`+
      `<td class="${cls}">${exc==null?'\\u2014':(exc>0?'+':'')+fmt(exc)}</td></tr>`;
  }).join('');
  document.querySelectorAll('thead th').forEach(th=>{
    const base=th.textContent.replace(/[\\u25B2\\u25BC]\\s*$/,'').trim();
    th.innerHTML = base + (Number(th.dataset.k)===sortK
      ? ` <span class="arr">${sortDir>0?'\\u25B2':'\\u25BC'}</span>` : '');
  });
}
document.getElementById('uniseg').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(!b) return;
  uni=b.dataset.u;
  document.querySelectorAll('#uniseg button').forEach(x=>x.classList.toggle('on',x===b));
  render();
});
document.querySelectorAll('#year,#reason,#outcome').forEach(el=>el.addEventListener('change',render));
document.getElementById('sym').addEventListener('input',render);
document.querySelector('thead').addEventListener('click',e=>{
  const th=e.target.closest('th'); if(!th) return;
  const k=Number(th.dataset.k);
  if(k===sortK) sortDir*=-1; else {sortK=k; sortDir = k>=3 && k!==5 && k!==8 ? -1 : 1;}
  render();
});
render();
</script>
"""


if __name__ == "__main__":
    main()
