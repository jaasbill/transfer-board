"""recommend(team, season): ranked, realistic transfer targets for one program."""
import numpy as np, pandas as pd

def _pred_at(model, P, dest, need=None, returning=None):
    d = P.copy()
    if need is not None:
        d["need_at_pos"] = need; d["dest_returning"] = returning
    d["log_prior_poss"] = np.log1p(d["prior_poss"].clip(lower=0))
    d["offense_lean"] = d["prior_obpr"] - d["prior_dbpr"]
    d["destination_prior_AdjEM"] = dest
    d["strength_change"] = dest - d["origin_prior_AdjEM"]
    d["strength_change_sq"] = d["strength_change"] ** 2
    d["bpr_x_log_poss"] = d["prior_bpr"] * d["log_prior_poss"]
    d["prior_bpr_sq"] = d["prior_bpr"] ** 2
    d["bpr_x_strength_change"] = d["prior_bpr"] * d["strength_change"]
    f = list(model["coef"])
    X = d[f].astype(float).fillna(pd.Series(model["medians"]))
    return model["intercept"] + X.to_numpy() @ np.array([model["coef"][k] for k in f])

QS = [0.10, 0.25, 0.50, 0.75, 0.90]
QCOLS = ["land_q10", "land_q25", "land_q50", "land_q75", "land_q90"]

def gettability(adjem, row):
    """Estimated share of similar players who landed at a program no stronger than this one
    (CDF of the predicted landing distribution at the team's AdjEM). Tails extrapolated, clipped 2-98%."""
    q = [row[c] for c in QCOLS]
    if adjem <= q[0]:
        slope = (QS[1] - QS[0]) / max(q[1] - q[0], 1e-6)
        return max(0.02, QS[0] - slope * (q[0] - adjem))
    if adjem >= q[-1]:
        slope = (QS[-1] - QS[-2]) / max(q[-1] - q[-2], 1e-6)
        return min(0.98, QS[-1] + slope * (adjem - q[-1]))
    return float(np.interp(adjem, q, QS))

def gettability_vec(adjem, Q):
    """Vectorised gettability for a matrix of landing quantiles (rows = players)."""
    q10, q25, q75, q90 = Q[:, 0], Q[:, 1], Q[:, 3], Q[:, 4]
    out = np.array([np.interp(adjem, row, QS) for row in Q])
    lo = adjem < q10
    out[lo] = np.maximum(0.02, QS[0] - (QS[1] - QS[0]) / np.maximum(q25 - q10, 1e-6)[lo] * (q10[lo] - adjem))
    hi = adjem > q90
    out[hi] = np.minimum(0.98, QS[-1] + (QS[-1] - QS[-2]) / np.maximum(q90 - q75, 1e-6)[hi] * (adjem - q90[hi]))
    return out

def label(p):
    return "Long shot" if p < 0.10 else "Reach" if p < 0.30 else "Realistic" if p < 0.70 else "Very gettable"

def recommend(team, season, seasons_out, teams_out, grid, w_value=0.4, w_get=0.4, w_need=0.2,
              include_long_shots=False, min_poss=300, top=25, value_col="pred_impact", choice=None):
    """Rank portal players for `team` in `season` (the season they'd play for the team).
    Score = weighted mix of: expected BPR at this team (percentile within the pool),
    gettability (0-100), and positional need (share of last year's minutes at his position that left)."""
    S = seasons_out[season]
    T = next(t for t in teams_out[season] if t["team"] == team)
    P = pd.DataFrame(S["players"])
    P = P[P["origin_kp"] != team].copy()
    P["pred_bpr"] = _pred_at(S["model"], P, T["adjem"])
    P["pred_lo"] = P["pred_bpr"] + S["model"]["resid_lo"]
    P["pred_hi"] = P["pred_bpr"] + S["model"]["resid_hi"]
    P["gettability"] = gettability_vec(T["adjem"], P[QCOLS].to_numpy(float))
    P["feasibility"] = P["gettability"].map(label)
    P["need"] = np.interp(P["prior_position"].astype(float), grid, T["need"])
    P["pred_poss"] = np.clip(_pred_at(S["mins"], P, T["adjem"], P["need"], T["returning"]), 50, 2300)
    P["pred_impact"] = P["pred_bpr"] * P["pred_poss"] / 1000
    P["moving_down"] = (P["origin_prior_AdjEM"] - T["adjem"]) >= 5
    P["evidence"] = pd.cut(P["prior_poss"], [-1, 300, 700, 1200, 1e9],
                           labels=["Limited", "Some", "Solid", "Strong"]).astype(str)
    pool = P if include_long_shots else P[P["gettability"] >= 0.10]
    pool = pool[pool["prior_poss"] >= min_poss].copy()
    pool["value_pct"] = pool[value_col].rank(pct=True) * 100
    if choice is not None:   # blend in the geography-aware choice model (load with pd.read_pickle("choice_final.pkl"))
        ch = choice[season]; tc = list(ch["teams"]["team_c"])
        from data import SAME_SCHOOL
        j = tc.index(SAME_SCHOOL.get(team, team))
        pool["lift"] = ch["pr"][pool.index.to_numpy(), j] * len(tc)
        pool["lift_pct"] = np.log(pool["lift"]).rank(pct=True) * 100
        realism = (pool["gettability"] * 100 + pool["lift_pct"]) / 2
    else:
        realism = pool["gettability"] * 100
    tot = w_value + w_get + w_need
    pool["fit_score"] = (w_value * pool["value_pct"] + w_get * realism + w_need * pool["need"] * 100) / tot
    pool = pool.sort_values("fit_score", ascending=False)
    return T, (pool.head(top) if top else pool)
