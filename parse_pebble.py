import json
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
COOKIES = BASE / "cookies.txt"
JSON_FILE = BASE / "pebble_thread.json"
DB_PATH = BASE / "pebble_shipping.db"
THREAD_URL = "https://www.reddit.com/r/pebble/comments/1sjk3c7/shipping_mega_thread/.json?limit=500&sort=new"


# --- Normalization --------------------------------------------------------

DESTINATION_MAP = {
    # United States variants
    "us": "USA",
    "usa": "USA",
    "united states": "USA",
    "united states of america": "USA",
    # US states with country suffix
    "oklahoma, usa": "USA",
    "ohio, usa": "USA",
    "north carolina, usa": "USA",
    "new york, usa": "USA",
    "nyc, usa": "USA",
    "michigan, usa": "USA",
    "maryland, usa": "USA",
    "kentucky, usa": "USA",
    "georgia, usa": "USA",
    "connecticut, usa": "USA",
    "california, usa": "USA",
    # United Kingdom variants
    "uk": "UK",
    "england": "UK",
    # Canada variants
    "ca": "Canada",
    "bc, canada": "Canada",
    "toronto, canada": "Canada",
    "ontario, canada": "Canada",
    "ontario canada": "Canada",
    # Netherlands variants
    "nl": "Netherlands",
    "the netherlands": "Netherlands",
    # New Zealand variants
    "nz": "New Zealand",
    # Hong Kong
    "hk": "Hong Kong",
    # France
    "fr": "France",
    # Strip parenthetical qualifiers
    "romania (europe)": "Romania",
    "italy (europe)": "Italy",
    "australia, melbourne": "Australia",
}


def normalize_destination(s):
    if not s:
        return s
    key = s.strip().lower()
    return DESTINATION_MAP.get(key, s.strip())


MODEL_MAP = {
    "pt2": "Pebble Time 2",
    "time 2": "Pebble Time 2",
    "pebble time 2": "Pebble Time 2",
    "pebble time 2 (x2)": "Pebble Time 2",
    "pebble time 2 - black/grey": "Pebble Time 2",
    "pt2 (switched from duo2 black due to shortage)": "Pebble Time 2",
    "2x pebble time 2 (1x grey 1x red)": "Pebble Time 2",
    "2 x pt2": "Pebble Time 2",
    "pebble index 01": "Pebble Index",
}


def normalize_model(s):
    if not s:
        return s
    key = s.strip().lower()
    return MODEL_MAP.get(key, s.strip())


# --------------------------------------------------------------------------


def all_comments(node):
    results = []
    if isinstance(node, list):
        for item in node:
            results.extend(all_comments(item))
    elif isinstance(node, dict):
        if node.get("kind") == "t1":
            results.append(node["data"])
        replies = node.get("data", {}).get("replies", "")
        if replies and isinstance(replies, dict):
            results.extend(all_comments(replies))
        elif node.get("kind") == "Listing":
            for child in node["data"].get("children", []):
                results.extend(all_comments(child))
    return results


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    # strip timezone labels
    s = re.sub(r"\s*(UTC|BST|CEST|CET|IST|PST|EST|CST|MST|GMT[+-]?\d*)\s*", " ", s, flags=re.I).strip()
    # strip AM/PM + time so date-only remains
    s = re.sub(r"\s+\d{1,2}:\d{2}(:\d{2})?(\s*(AM|PM))?", "", s, flags=re.I).strip()
    # normalize dots/spaces used as separators in dates like 2026-05.30 or 2026.05.30
    s = re.sub(r"(\d{4})[-.](\d{2})[-.](\d{2})", r"\1-\2-\3", s)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


NOT_YET_PATTERN = re.compile(
    r"^\s*(not yet|waiting|n/?a|no|none|pending|-+|tbd|\?+|unknown|soon|unsure)\s*!?\s*$",
    re.I,
)


def is_not_yet(s):
    return not s or bool(NOT_YET_PATTERN.match(s.strip()))


def extract_field(body, *labels):
    for label in labels:
        escaped = re.escape(label)
        # colon/dash separator (required)
        m = re.search(
            rf"(?:^|\n)\*?\s*{escaped}\s*[:\-]\s*(.+?)(?:\n|$)",
            body,
            re.IGNORECASE | re.MULTILINE,
        )
        if m:
            return m.group(1).strip().rstrip("*").strip()
        # no separator — value immediately follows label (e.g. "* Batch 2")
        m = re.search(
            rf"(?:^|\n)\*?\s*{escaped}\s+([^\n:]+?)(?:\n|$)",
            body,
            re.IGNORECASE | re.MULTILINE,
        )
        if m:
            val = m.group(1).strip().rstrip("*").strip()
            if val:
                return val
    return None


def parse_batch(s):
    if not s:
        return None
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None


def split_orders(body):
    """Split comments that embed multiple orders separated by --- or ***."""
    parts = re.split(r"\n\s*(?:\*{3,}|-{3,}|={3,})\s*\n", body)
    return [p.strip() for p in parts if p.strip()]


def parse_order(block):
    model = extract_field(
        block, "Model", "Device ordered", "Device", "Watch model", "Watch", "Product"
    )
    if not model:
        return None
    # Filter out garbage matches that are clearly not model names
    if len(model) > 60 or "\n" in model:
        return None

    order_date_raw = extract_field(
        block, "Ordered", "Order date and time", "Order date", "Date ordered", "Order time", "Purchase date"
    )
    batch_raw = extract_field(block, "Batch", "Wave")
    destination = extract_field(
        block, "Destination", "Country", "Location", "Region", "Ship to", "Shipping to", "Shipping country"
    )
    color = extract_field(block, "Color", "Color variant", "Colour", "Colour variant", "Color/variant")
    confirmation_raw = extract_field(
        block, "Confirmation Email", "Confirmation email", "Confirmation", "Confirm email", "Confirm date", "Confirmation date"
    )
    shipped_raw = extract_field(
        block, "Shipped", "Ship date", "Shipping date", "Tracking", "Dispatched"
    )
    arrived_raw = extract_field(
        block, "Arrived", "Delivered", "Received", "Delivery date", "Arrival date"
    )

    confirmation_date = None if is_not_yet(confirmation_raw) else parse_date(confirmation_raw)
    shipped_date = None if is_not_yet(shipped_raw) else parse_date(shipped_raw)
    delivered_date = None if is_not_yet(arrived_raw) else parse_date(arrived_raw)
    delivered = delivered_date is not None

    return {
        "model": normalize_model(model),
        "order_date": parse_date(order_date_raw),
        "batch": parse_batch(batch_raw),
        "destination": normalize_destination(destination),
        "color": color,
        "confirmation_date": confirmation_date,
        "shipped_date": shipped_date,
        "delivered": delivered,
        "delivered_date": delivered_date,
    }


print("Fetching thread from Reddit...")
subprocess.run([
    "curl", "-s",
    "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "-b", str(COOKIES),
    "-o", str(JSON_FILE),
    THREAD_URL,
], check=True)

with open(JSON_FILE) as f:
    data = json.load(f)

comments = all_comments(data[1])
print(f"Total comments: {len(comments)}")

orders = []
for c in comments:
    body = c.get("body", "")
    for block in split_orders(body):
        order = parse_order(block)
        if order:
            orders.append(order)

print(f"Parsed orders: {len(orders)}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS orders")
cur.execute("""
CREATE TABLE orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model           TEXT,
    order_date      TEXT,
    batch           INTEGER,
    destination     TEXT,
    color           TEXT,
    confirmation_date TEXT,
    shipped_date    TEXT,
    delivered       INTEGER NOT NULL DEFAULT 0,
    delivered_date  TEXT
)
""")

for o in orders:
    cur.execute("""
        INSERT INTO orders
            (model, order_date, batch, destination, color, confirmation_date, shipped_date, delivered, delivered_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        o["model"], o["order_date"], o["batch"], o["destination"], o["color"],
        o["confirmation_date"], o["shipped_date"], int(o["delivered"]), o["delivered_date"],
    ))

conn.commit()

# Quick summary
print("\n--- Summary ---")
cur.execute("SELECT COUNT(*) FROM orders")
print(f"Total rows: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM orders WHERE delivered = 1")
print(f"Delivered: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM orders WHERE shipped_date IS NOT NULL AND delivered = 0")
print(f"Shipped, not yet delivered: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM orders WHERE confirmation_date IS NOT NULL AND shipped_date IS NULL")
print(f"Confirmed, not yet shipped: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM orders WHERE confirmation_date IS NULL")
print(f"Not yet confirmed: {cur.fetchone()[0]}")
cur.execute("SELECT batch, COUNT(*) as n FROM orders GROUP BY batch ORDER BY batch")
print("\nBy batch:")
for row in cur.fetchall():
    print(f"  Batch {row[0]}: {row[1]}")
cur.execute("SELECT destination, COUNT(*) as n FROM orders GROUP BY destination ORDER BY n DESC LIMIT 10")
print("\nTop destinations:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
print(f"\nDatabase written to {DB_PATH}")
