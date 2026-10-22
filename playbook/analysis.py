"""Run the SQL files against the SQLite DB and write CSV + PNG outputs."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def run_sql(conn: sqlite3.Connection, name: str) -> pd.DataFrame:
    return pd.read_sql_query((SQL_DIR / f"{name}.sql").read_text(), conn)


def retention_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df.pivot(index="cohort_week", columns="week_offset", values="retention")


def plot_funnel(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(df["step"][::-1], df["users"][::-1], color="#3b6ea5")
    for y, (u, p) in enumerate(zip(df["users"][::-1], df["pct_of_signups"][::-1])):
        ax.text(u, y, f" {u} ({p:.0%})", va="center", fontsize=9)
    ax.set_xlabel("Users (synthetic data)")
    ax.set_title("Signup-to-purchase funnel, 14-day window")
    ax.set_xlim(0, df["users"].max() * 1.2)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_retention(mat: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(mat.values, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(mat.shape[1]), [f"W{c}" for c in mat.columns])
    ax.set_yticks(range(mat.shape[0]), mat.index, fontsize=7)
    ax.set_title("Weekly retention by signup cohort (blank = not yet observable)")
    fig.colorbar(im, ax=ax, label="Retention")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_source(agg: pd.DataFrame, strat: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    order = list(agg.sort_values("conversion", ascending=False)["source"])
    axes[0].bar(order, agg.set_index("source").loc[order, "conversion"], color="#888")
    axes[0].set_title("Aggregate")
    axes[0].set_ylabel("14-day purchase conversion")
    p = strat.pivot(index="source", columns="device", values="conversion").loc[order]
    p.plot.bar(ax=axes[1], rot=0)
    axes[1].set_title("Stratified by device")
    for ax in axes:
        ax.tick_params(axis="x", labelrotation=20)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def run(db: str, out_dir: str) -> dict[str, pd.DataFrame]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        funnel = run_sql(conn, "funnel")
        retention = run_sql(conn, "retention")
        agg = run_sql(conn, "conversion_by_source")
        strat = run_sql(conn, "conversion_by_source_device")
    mat = retention_matrix(retention)
    funnel.to_csv(out / "funnel.csv", index=False)
    retention.to_csv(out / "retention_long.csv", index=False)
    mat.to_csv(out / "retention_matrix.csv")
    agg.to_csv(out / "conversion_by_source.csv", index=False)
    strat.to_csv(out / "conversion_by_source_device.csv", index=False)
    plot_funnel(funnel, out / "funnel.png")
    plot_retention(mat, out / "retention_heatmap.png")
    plot_source(agg, strat, out / "conversion_by_source.png")
    return {"funnel": funnel, "retention": retention, "agg": agg, "strat": strat}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/playbook.db")
    ap.add_argument("--out", default="outputs")
    args = ap.parse_args()
    res = run(args.db, args.out)
    print(res["funnel"].to_string(index=False))
    print(res["agg"].to_string(index=False))
    print(res["strat"].to_string(index=False))


if __name__ == "__main__":
    main()
