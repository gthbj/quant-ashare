#!/usr/bin/env python3
"""Read-only probe: does the cross-sectional alpha survive in large-cap, and is it
long-only-harvestable? Compares size buckets (large / mid / small) on the SAME panel.

Motivation: v1 long-window Sharpe is stuck ~0.67. The Sharpe attribution showed the
binding constraint is the long-only structure on CSI1000 small-caps — most of the edge
is short-side (unharvestable long-only). This probe tests whether moving toward large-cap
recovers long-only-harvestable alpha, and where the long-short ceiling is by size.

Method (identical across buckets, PIT-safe):
- Universe: main board (SSE_MAIN/SZSE_MAIN), is_tradable_hard, 2021-01-04..2026-06-09.
- Size buckets per day by total_mv_cny rank: large=top 300, mid=301-800, small=801-1800.
- Per-feature signed daily cross-sectional Spearman rank IC vs raw fwd_ret (label panel).
- Composite = equal-weight z-score of features with UNAMBIGUOUS economic priors
  (reversal -ret_5d, low-risk -vol_20d / -turnover_z, value +ep_ttm/+bp/+divyield);
  fixed prior signs (no in-sample sign fitting).
- Long-short ceiling: NON-OVERLAPPING rebalance every h trading days; within bucket rank
  by composite; top-decile minus bottom-decile period fwd_ret -> annualized Sharpe;
  long-only-excess = top-decile minus bucket-mean (the realizable long-only active series).

Caveats (read RELATIVE, not absolute): equal-weight composite is a crude proxy — a trained
model is materially stronger (CSI1000 model L/S Sharpe ~3.4 vs this composite ~0.9), so
absolute Sharpes here are lower bounds. In-sample, zero-cost, no securities-borrow (融券) fee.

Strictly read-only BigQuery SELECT. No writes.
> 文档维护：Claude Opus 4.8（2026-06-13）
"""
from __future__ import annotations
import argparse, warnings
import numpy as np, pandas as pd
from google.cloud import bigquery

warnings.filterwarnings("ignore")
PROJECT = "data-aquarium"
FEAT_V = "strategy1_pv_v0_20260601"
LAB_V = "open_to_close_h1_5_10_20_v20260601"
START, END = "2021-01-04", "2026-06-09"
# feature -> economic-prior sign (higher signed value => predicted higher return)
SIGNED = {"ret_5d": -1.0, "vol_20d": -1.0, "turnover_rate_zscore_60d": -1.0,
          "ep_ttm": 1.0, "bp": 1.0, "dividend_yield_ttm": 1.0}
REPORT_FEATURES = list(SIGNED) + ["ret_10d", "mom_60_20"]  # extra reported, not in composite
BUCKETS = ["large(top300)", "mid(301-800)", "small(801-1800)"]


def fetch(client):
    cols = ",".join(f"f.{c}" for c in REPORT_FEATURES)
    sql = f"""
    SELECT f.trade_date, f.sec_code, f.total_mv_cny, {cols}, l.fwd_ret_5d, l.fwd_ret_20d
    FROM `{PROJECT}.ashare_dws.dws_stock_feature_daily_v0` f
    JOIN `{PROJECT}.ashare_dws.dws_stock_label_daily` l
      ON l.trade_date=f.trade_date AND l.sec_code=f.sec_code
     AND l.label_version=@lab AND l.trade_date BETWEEN @s AND @e
    WHERE f.feature_version=@feat AND f.trade_date BETWEEN @s AND @e
      AND f.board IN ('SSE_MAIN','SZSE_MAIN') AND f.is_tradable_hard
      AND f.total_mv_cny IS NOT NULL
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("feat", "STRING", FEAT_V),
        bigquery.ScalarQueryParameter("lab", "STRING", LAB_V),
        bigquery.ScalarQueryParameter("s", "DATE", START),
        bigquery.ScalarQueryParameter("e", "DATE", END)])
    df = client.query(sql, job_config=cfg).to_dataframe()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def assign_bucket(df):
    r = df.groupby("trade_date")["total_mv_cny"].rank(ascending=False, method="first")
    b = pd.Series(np.where(r <= 300, BUCKETS[0], np.where(r <= 800, BUCKETS[1],
                  np.where(r <= 1800, BUCKETS[2], None))), index=df.index)
    return b


def daily_rank_ic(g, feat, ret):
    s = g[[feat, ret]].dropna()
    return s[feat].rank().corr(s[ret].rank()) if len(s) >= 20 else np.nan


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-csv", default="docs/analysis_largecap_alpha_survival_20260613.csv")
    args = ap.parse_args(argv)
    client = bigquery.Client(project=PROJECT)
    df = fetch(client)
    df["bucket"] = assign_bucket(df)
    df = df[df["bucket"].notna()].copy()
    print(f"rows={len(df)} days={df['trade_date'].nunique()} names/day~{len(df)//df['trade_date'].nunique()}")

    rows = []
    # per-feature signed IC (5d)
    for feat in REPORT_FEATURES:
        rec = {"metric": f"IC_5d:{feat}"}
        for b in BUCKETS:
            sub = df[df["bucket"] == b]
            rec[b] = sub.groupby("trade_date").apply(lambda g: daily_rank_ic(g, feat, "fwd_ret_5d")).mean()
        rows.append(rec)

    # composite (fixed prior signs)
    def zc(g):
        acc = pd.Series(0.0, index=g.index); k = 0
        for feat, sgn in SIGNED.items():
            v = g[feat].astype(float); sd = v.std()
            if sd and sd > 0:
                acc = acc + ((v - v.mean()) / sd) * sgn; k += 1
        return acc / max(k, 1)
    df["composite"] = df.groupby(["trade_date", "bucket"], group_keys=False).apply(zc)

    for ret, h in [("fwd_ret_5d", 5), ("fwd_ret_20d", 20)]:
        rec = {"metric": f"composite_IC_{h}d"}
        for b in BUCKETS:
            sub = df[df["bucket"] == b]
            rec[b] = sub.groupby("trade_date").apply(lambda g: daily_rank_ic(g, "composite", ret)).mean()
        rows.append(rec)

    # non-overlapping decile L/S and long-only-excess Sharpe
    all_days = np.sort(df["trade_date"].unique())
    for ret, h in [("fwd_ret_5d", 5), ("fwd_ret_20d", 20)]:
        d = df[df["trade_date"].isin(all_days[::h])]
        ls_rec = {"metric": f"LS_decile_Sharpe_{h}d"}; lo_rec = {"metric": f"long_only_excess_Sharpe_{h}d"}
        for b in BUCKETS:
            sub = d[d["bucket"] == b]; ls, lo = [], []
            for _, g in sub.groupby("trade_date"):
                gg = g[["composite", ret]].dropna()
                if len(gg) < 50:
                    continue
                q = gg["composite"].rank(pct=True)
                top, bot, uni = gg[ret][q >= 0.9].mean(), gg[ret][q <= 0.1].mean(), gg[ret].mean()
                if pd.notna(top) and pd.notna(bot): ls.append(top - bot)
                if pd.notna(top): lo.append(top - uni)
            ann = np.sqrt(252 / h)
            ls_rec[b] = np.mean(ls) / np.std(ls) * ann if len(ls) > 5 and np.std(ls) > 0 else np.nan
            lo_rec[b] = np.mean(lo) / np.std(lo) * ann if len(lo) > 5 and np.std(lo) > 0 else np.nan
        rows.append(ls_rec); rows.append(lo_rec)

    out = pd.DataFrame(rows)[["metric"] + BUCKETS]
    pd.set_option("display.float_format", lambda x: f"{x:.4f}", "display.width", 160)
    print("\n" + out.to_string(index=False))
    out.to_csv(args.out_csv, index=False)
    print(f"\nwrote {args.out_csv}")


if __name__ == "__main__":
    main()
