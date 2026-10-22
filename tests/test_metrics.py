import pandas as pd
import pytest

from playbook import analysis, generate_data


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    d = tmp_path_factory.mktemp("pb")
    tables = generate_data.generate(n_users=4000, seed=7)
    db = d / "t.db"
    generate_data.write_sqlite(tables, db)
    res = analysis.run(str(db), str(d / "out"))
    return tables, res, d


def test_generator_is_deterministic():
    a = generate_data.generate(500, seed=1)["events"]
    b = generate_data.generate(500, seed=1)["events"]
    pd.testing.assert_frame_equal(a, b)


def test_funnel_is_monotonic_and_starts_at_100pct(env):
    f = env[1]["funnel"]
    assert f["users"].is_monotonic_decreasing
    assert f.loc[0, "pct_of_signups"] == 1.0
    assert (f["pct_of_prev_step"].dropna() <= 1).all()


def test_funnel_matches_pandas(env):
    tables, res, _ = env
    users, ev = tables["users"], tables["events"]
    end = pd.to_datetime(tables["activity"]["activity_date"]).max()
    users = users.assign(s=pd.to_datetime(users.signup_date))
    mature = users[users.s + pd.Timedelta(days=14) <= end]
    e = ev.merge(mature[["user_id", "s"]], on="user_id")
    e = e[pd.to_datetime(e.event_date) <= e.s + pd.Timedelta(days=14)]
    buyers = e[e.event_name == "purchase"].user_id.nunique()
    assert res["funnel"].iloc[-1]["users"] == buyers
    assert res["funnel"].iloc[0]["users"] == len(mature)


def test_retention_week0_is_full_and_in_range(env):
    r = env[1]["retention"]
    assert (r[r.week_offset == 0]["retention"] == 1.0).all()
    assert r["retention"].between(0, 1).all()
    assert (r["retained_users"] <= r["cohort_users"]).all()


def test_retention_censoring_drops_unobservable_cells(env):
    m = analysis.retention_matrix(env[1]["retention"])
    # newest cohort cannot have observed late weeks; oldest cohort has all of them
    assert m.iloc[-1].isna().any()
    assert m.iloc[0].notna().all()


def test_simpson_paradox_is_present(env):
    agg, strat = env[1]["agg"].set_index("source"), env[1]["strat"]
    assert agg["conversion"].idxmax() == "organic"
    assert agg.loc["partner", "conversion"] < agg.loc["organic", "conversion"]
    for dev, g in strat.groupby("device"):
        assert g.set_index("source")["conversion"].idxmax() == "partner", dev


def test_outputs_written(env):
    out = env[2] / "out"
    for name in ["funnel.csv", "retention_matrix.csv", "conversion_by_source.csv",
                 "funnel.png", "retention_heatmap.png", "conversion_by_source.png"]:
        assert (out / name).stat().st_size > 0
