import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pebble_shipping.db"
OUT_PATH = Path(__file__).parent / "shipping.html"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM orders ORDER BY order_date ASC, batch ASC")
rows = [dict(r) for r in cur.fetchall()]
conn.close()

# Derive status label for each row
for r in rows:
    if r["delivered"]:
        r["status"] = "Delivered"
    elif r["shipped_date"]:
        r["status"] = "In Transit"
    elif r["confirmation_date"]:
        r["status"] = "Confirmed"
    else:
        r["status"] = "Waiting"

data_json = json.dumps(rows)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pebble Shipping Tracker</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --text: #e2e4ed;
    --muted: #7b7f96;
    --accent: #5b6af0;
    --green: #22c55e;
    --blue: #3b82f6;
    --yellow: #eab308;
    --grey: #6b7280;
  }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 14px;
    line-height: 1.5;
  }}

  header {{
    padding: 28px 32px 0;
    border-bottom: 1px solid var(--border);
    padding-bottom: 20px;
  }}

  header h1 {{ font-size: 20px; font-weight: 600; letter-spacing: -0.3px; }}
  header p {{ color: var(--muted); font-size: 12px; margin-top: 3px; }}

  .stats {{
    display: flex;
    gap: 12px;
    padding: 20px 32px;
    flex-wrap: wrap;
  }}

  .stat {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 20px;
    min-width: 130px;
    flex: 1;
  }}

  .stat-value {{
    font-size: 28px;
    font-weight: 700;
    line-height: 1;
  }}

  .stat-label {{
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
  }}

  .stat.delivered .stat-value {{ color: var(--green); }}
  .stat.transit   .stat-value {{ color: var(--blue); }}
  .stat.confirmed .stat-value {{ color: var(--yellow); }}
  .stat.waiting   .stat-value {{ color: var(--grey); }}

  .controls {{
    display: flex;
    gap: 10px;
    padding: 0 32px 16px;
    flex-wrap: wrap;
    align-items: center;
  }}

  .controls select, .controls input {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 7px;
    padding: 7px 12px;
    font-size: 13px;
    outline: none;
    appearance: none;
    -webkit-appearance: none;
  }}

  .controls select:focus, .controls input:focus {{
    border-color: var(--accent);
  }}

  .controls input {{ min-width: 180px; }}

  #count {{
    margin-left: auto;
    color: var(--muted);
    font-size: 12px;
    white-space: nowrap;
  }}

  .pivot-wrap {{
    padding: 0 32px 28px;
    overflow-x: auto;
  }}

  .pivot-wrap h2 {{
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
  }}

  .pivot {{
    border-collapse: collapse;
    font-size: 13px;
  }}

  .pivot th, .pivot td {{
    padding: 9px 18px;
    text-align: right;
    white-space: nowrap;
    border-bottom: 1px solid var(--border);
  }}

  .pivot th:first-child, .pivot td:first-child {{
    text-align: left;
    padding-left: 0;
  }}

  .pivot thead th {{
    background: transparent;
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    font-weight: 500;
    cursor: default;
    position: static;
    border-bottom: 1px solid var(--border);
  }}

  .pivot thead th.shipped-group {{
    color: var(--blue);
  }}

  .pivot tfoot td {{
    font-weight: 600;
    border-top: 1px solid var(--border);
    border-bottom: none;
    color: var(--text);
  }}

  .pivot tbody tr:hover {{ background: var(--surface); }}

  .pivot .n-delivered {{ color: var(--green); }}
  .pivot .n-transit   {{ color: var(--blue); }}
  .pivot .n-confirmed {{ color: var(--yellow); }}
  .pivot .n-waiting   {{ color: var(--grey); }}
  .pivot .n-total     {{ font-weight: 600; }}
  .pivot .pct         {{ color: var(--muted); font-size: 12px; }}

  .divider {{
    height: 1px;
    background: var(--border);
    margin: 4px 32px 24px;
  }}

  .table-wrap {{
    padding: 0 32px 40px;
    overflow-x: auto;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}

  thead th {{
    background: var(--surface);
    color: var(--muted);
    font-weight: 500;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.4px;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    position: sticky;
    top: 0;
    z-index: 1;
  }}

  thead th:hover {{ color: var(--text); }}
  thead th.sorted {{ color: var(--accent); }}
  thead th .sort-arrow {{ opacity: 0.4; margin-left: 4px; }}
  thead th.sorted .sort-arrow {{ opacity: 1; }}

  tbody tr {{
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }}

  tbody tr:hover {{ background: var(--surface); }}

  td {{
    padding: 9px 14px;
    vertical-align: middle;
    white-space: nowrap;
  }}

  .badge {{
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
  }}

  .badge-delivered {{ background: #14532d; color: var(--green); }}
  .badge-transit   {{ background: #1e3a5f; color: var(--blue); }}
  .badge-confirmed {{ background: #422006; color: var(--yellow); }}
  .badge-waiting   {{ background: #1f2937; color: var(--grey); }}

  .null {{ color: var(--muted); }}

  td.batch {{ text-align: center; }}
</style>
</head>
<body>

<header>
  <h1>Pebble Shipping Tracker</h1>
  <p>r/pebble Shipping Mega Thread — data refreshed from Reddit</p>
</header>

<div class="stats">
  <div class="stat delivered">
    <div class="stat-value" id="s-delivered">—</div>
    <div class="stat-label">Delivered</div>
  </div>
  <div class="stat transit">
    <div class="stat-value" id="s-transit">—</div>
    <div class="stat-label">In Transit</div>
  </div>
  <div class="stat confirmed">
    <div class="stat-value" id="s-confirmed">—</div>
    <div class="stat-label">Confirmed</div>
  </div>
  <div class="stat waiting">
    <div class="stat-value" id="s-waiting">—</div>
    <div class="stat-label">Waiting</div>
  </div>
</div>

<div class="pivot-wrap">
  <h2>By Batch</h2>
  <table class="pivot" id="pivot">
    <thead>
      <tr>
        <th>Batch</th>
        <th class="shipped-group">Delivered</th>
        <th class="shipped-group">In Transit</th>
        <th>Confirmed</th>
        <th>Waiting</th>
        <th>Total</th>
        <th>% Shipped</th>
      </tr>
    </thead>
    <tbody id="pivot-body"></tbody>
    <tfoot id="pivot-foot"></tfoot>
  </table>
</div>

<div class="divider"></div>

<div class="controls">
  <select id="f-model">
    <option value="">All models</option>
  </select>
  <select id="f-batch">
    <option value="">All batches</option>
  </select>
  <select id="f-status">
    <option value="">All statuses</option>
    <option>Delivered</option>
    <option>In Transit</option>
    <option>Confirmed</option>
    <option>Waiting</option>
  </select>
  <input id="f-search" type="search" placeholder="Search destination or color…">
  <span id="count"></span>
</div>

<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th data-col="model">Model <span class="sort-arrow">↕</span></th>
      <th data-col="batch" class="batch">Batch <span class="sort-arrow">↕</span></th>
      <th data-col="order_date">Ordered <span class="sort-arrow">↕</span></th>
      <th data-col="destination">Destination <span class="sort-arrow">↕</span></th>
      <th data-col="color">Color <span class="sort-arrow">↕</span></th>
      <th data-col="confirmation_date">Confirmed <span class="sort-arrow">↕</span></th>
      <th data-col="shipped_date">Shipped <span class="sort-arrow">↕</span></th>
      <th data-col="delivered_date">Delivered <span class="sort-arrow">↕</span></th>
      <th data-col="status">Status <span class="sort-arrow">↕</span></th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>
</div>

<script>
const DATA = {data_json};

const BADGE = {{
  "Delivered": "badge-delivered",
  "In Transit": "badge-transit",
  "Confirmed":  "badge-confirmed",
  "Waiting":    "badge-waiting",
}};

const STATUS_ORDER = {{"Delivered":0,"In Transit":1,"Confirmed":2,"Waiting":3}};

let sortCol = "order_date", sortAsc = true;

function val(v) {{
  return v == null ? '<span class="null">—</span>' : escHtml(String(v));
}}

function escHtml(s) {{
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}}

function render() {{
  const model  = document.getElementById("f-model").value;
  const batch  = document.getElementById("f-batch").value;
  const status = document.getElementById("f-status").value;
  const search = document.getElementById("f-search").value.toLowerCase();

  let rows = DATA.filter(r => {{
    if (model  && r.model !== model) return false;
    if (batch  && String(r.batch ?? "Unknown") !== batch) return false;
    if (status && r.status !== status) return false;
    if (search && !((r.destination||"").toLowerCase().includes(search) ||
                    (r.color||"").toLowerCase().includes(search))) return false;
    return true;
  }});

  rows.sort((a, b) => {{
    let av = a[sortCol], bv = b[sortCol];
    if (sortCol === "status") {{ av = STATUS_ORDER[av]; bv = STATUS_ORDER[bv]; }}
    if (sortCol === "batch")  {{ av = av ?? 999; bv = bv ?? 999; }}
    av = av ?? ""; bv = bv ?? "";
    if (av < bv) return sortAsc ? -1 :  1;
    if (av > bv) return sortAsc ?  1 : -1;
    return 0;
  }});

  // stats from filtered rows
  const counts = {{Delivered:0,"In Transit":0,Confirmed:0,Waiting:0}};
  rows.forEach(r => counts[r.status]++);
  document.getElementById("s-delivered").textContent = counts["Delivered"];
  document.getElementById("s-transit").textContent   = counts["In Transit"];
  document.getElementById("s-confirmed").textContent = counts["Confirmed"];
  document.getElementById("s-waiting").textContent   = counts["Waiting"];
  document.getElementById("count").textContent = rows.length + " orders";

  const tbody = document.getElementById("tbody");
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${{val(r.model)}}</td>
      <td class="batch">${{val(r.batch)}}</td>
      <td>${{val(r.order_date)}}</td>
      <td>${{val(r.destination)}}</td>
      <td>${{val(r.color)}}</td>
      <td>${{val(r.confirmation_date)}}</td>
      <td>${{val(r.shipped_date)}}</td>
      <td>${{val(r.delivered_date)}}</td>
      <td><span class="badge ${{BADGE[r.status]}}">${{r.status}}</span></td>
    </tr>
  `).join("");
}}

function populateFilters() {{
  const models  = [...new Set(DATA.map(r => r.model).filter(Boolean))].sort();
  const batches = [...new Set(DATA.map(r => r.batch == null ? "Unknown" : String(r.batch)))];
  batches.sort((a,b) => a === "Unknown" ? 1 : b === "Unknown" ? -1 : Number(a)-Number(b));

  const mSel = document.getElementById("f-model");
  models.forEach(m => mSel.insertAdjacentHTML("beforeend", `<option>${{escHtml(m)}}</option>`));

  const bSel = document.getElementById("f-batch");
  batches.forEach(b => bSel.insertAdjacentHTML("beforeend", `<option>${{b}}</option>`));
}}

document.querySelectorAll("thead th[data-col]").forEach(th => {{
  th.addEventListener("click", () => {{
    const col = th.dataset.col;
    if (sortCol === col) sortAsc = !sortAsc;
    else {{ sortCol = col; sortAsc = true; }}
    document.querySelectorAll("thead th").forEach(h => {{
      h.classList.remove("sorted");
      h.querySelector(".sort-arrow").textContent = "↕";
    }});
    th.classList.add("sorted");
    th.querySelector(".sort-arrow").textContent = sortAsc ? "↑" : "↓";
    render();
  }});
}});

["f-model","f-batch","f-status","f-search"].forEach(id =>
  document.getElementById(id).addEventListener("input", render)
);

function buildPivot() {{
  const batches = [...new Set(DATA.map(r => r.batch))];
  batches.sort((a, b) => a == null ? 1 : b == null ? -1 : a - b);

  const totals = {{ delivered: 0, transit: 0, confirmed: 0, waiting: 0 }};

  const rows = batches.map(batch => {{
    const group = DATA.filter(r => r.batch === batch);
    const d = group.filter(r => r.status === "Delivered").length;
    const t = group.filter(r => r.status === "In Transit").length;
    const c = group.filter(r => r.status === "Confirmed").length;
    const w = group.filter(r => r.status === "Waiting").length;
    const total = group.length;
    const shipped = d + t;
    const pct = total ? Math.round(shipped / total * 100) : 0;
    totals.delivered += d; totals.transit += t;
    totals.confirmed += c; totals.waiting += w;
    const label = batch == null ? "<span style='color:var(--muted)'>Unknown</span>" : `Batch ${{batch}}`;
    return `<tr>
      <td>${{label}}</td>
      <td class="n-delivered">${{d || '<span class="pct">—</span>'}}</td>
      <td class="n-transit">${{t || '<span class="pct">—</span>'}}</td>
      <td class="n-confirmed">${{c || '<span class="pct">—</span>'}}</td>
      <td class="n-waiting">${{w || '<span class="pct">—</span>'}}</td>
      <td class="n-total">${{total}}</td>
      <td class="pct">${{pct}}%</td>
    </tr>`;
  }});

  document.getElementById("pivot-body").innerHTML = rows.join("");

  const gt = totals.delivered + totals.transit + totals.confirmed + totals.waiting;
  const gshipped = totals.delivered + totals.transit;
  const gpct = gt ? Math.round(gshipped / gt * 100) : 0;
  document.getElementById("pivot-foot").innerHTML = `<tr>
    <td>Total</td>
    <td class="n-delivered">${{totals.delivered}}</td>
    <td class="n-transit">${{totals.transit}}</td>
    <td class="n-confirmed">${{totals.confirmed}}</td>
    <td class="n-waiting">${{totals.waiting}}</td>
    <td class="n-total">${{gt}}</td>
    <td class="pct">${{gpct}}%</td>
  </tr>`;
}}

populateFilters();
buildPivot();
render();
</script>
</body>
</html>
"""

OUT_PATH.write_text(html, encoding="utf-8")
print(f"Written to {OUT_PATH}")
