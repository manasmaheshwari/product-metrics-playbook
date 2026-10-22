"""Generate a synthetic product dataset and load it into SQLite.

Everything here is synthetic. The parameters are deliberately chosen so that
Simpson's paradox appears in conversion-by-source (see README).

Tables
------
users(user_id, signup_date, source, device)
events(user_id, event_name, event_date)   -- view_product, add_to_cart, checkout, purchase
activity(user_id, activity_date)          -- one row per active day (any session)
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

FIRST_SIGNUP = date(2026, 1, 5)
LAST_SIGNUP = date(2026, 5, 10)
DATA_END = date(2026, 5, 31)  # newest cohorts are right-censored on purpose

# source -> (share of users, share on mobile, conversion multiplier)
SOURCES = {
    "organic": (0.35, 0.20, 1.00),
    "paid_search": (0.25, 0.50, 0.90),
    "social": (0.20, 0.70, 0.80),
    "partner": (0.20, 0.85, 1.50),  # best within each device, worst overall
}
BASE_CONVERSION = {"desktop": 0.20, "mobile": 0.07}
P_VIEW, P_CART, P_CHECKOUT = 0.85, 0.60, 0.75


def generate(n_users: int = 6000, seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n_days = (LAST_SIGNUP - FIRST_SIGNUP).days + 1
    names = list(SOURCES)
    shares = np.array([SOURCES[s][0] for s in names])
    source = rng.choice(names, size=n_users, p=shares / shares.sum())
    mobile_share = np.array([SOURCES[s][1] for s in source])
    device = np.where(rng.random(n_users) < mobile_share, "mobile", "desktop")
    signup_offset = rng.integers(0, n_days, size=n_users)
    signup = np.array([FIRST_SIGNUP + timedelta(days=int(o)) for o in signup_offset])

    users = pd.DataFrame(
        {
            "user_id": np.arange(1, n_users + 1),
            "signup_date": [d.isoformat() for d in signup],
            "source": source,
            "device": device,
        }
    )

    # Funnel events: nested steps, each within 14 days of signup.
    p_final = np.array(
        [BASE_CONVERSION[d] * SOURCES[s][2] for d, s in zip(device, source)]
    )
    p_purchase_given_checkout = p_final / (P_VIEW * P_CART * P_CHECKOUT)
    u = rng.random((n_users, 4))
    did_view = u[:, 0] < P_VIEW
    did_cart = did_view & (u[:, 1] < P_CART)
    did_checkout = did_cart & (u[:, 2] < P_CHECKOUT)
    did_purchase = did_checkout & (u[:, 3] < p_purchase_given_checkout)

    rows = []
    for name, mask in [
        ("view_product", did_view),
        ("add_to_cart", did_cart),
        ("checkout", did_checkout),
        ("purchase", did_purchase),
    ]:
        for i in np.flatnonzero(mask):
            lag = int(rng.integers(0, 15))
            d = signup[i] + timedelta(days=lag)
            if d <= DATA_END:
                rows.append((int(users.user_id[i]), name, d.isoformat()))
    events = pd.DataFrame(rows, columns=["user_id", "event_name", "event_date"])

    # Weekly activity: purchasers retain better; retention decays by week.
    act = []
    for i in range(n_users):
        s = signup[i]
        act.append((i + 1, s.isoformat()))  # signup day counts as active
        p0 = 0.55 if did_purchase[i] else 0.30
        week = 1
        while s + timedelta(days=7 * week) <= DATA_END:
            if rng.random() < p0 * (0.82 ** (week - 1)):
                d = s + timedelta(days=7 * week + int(rng.integers(0, 7)))
                if d <= DATA_END:
                    act.append((i + 1, d.isoformat()))
            week += 1
    activity = pd.DataFrame(act, columns=["user_id", "activity_date"])
    return {"users": users, "events": events, "activity": activity}


def write_sqlite(tables: dict[str, pd.DataFrame], db_path: Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, index=False)
        conn.execute("CREATE INDEX idx_events_user ON events(user_id)")
        conn.execute("CREATE INDEX idx_activity_user ON activity(user_id)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--users", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--db", default="data/playbook.db")
    ap.add_argument("--csv-dir", default="data")
    args = ap.parse_args()
    tables = generate(args.users, args.seed)
    write_sqlite(tables, Path(args.db))
    out = Path(args.csv_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
    print({k: len(v) for k, v in tables.items()}, "->", args.db)


if __name__ == "__main__":
    main()
