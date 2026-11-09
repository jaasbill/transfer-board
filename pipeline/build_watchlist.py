"""Build the 2027-28 watch list from the latest EvanMiya player-ratings export.
Usage: python build_watchlist.py <player-ratings.csv> "<as-of date>"   -> writes watch_2028.json"""
import sys, re, json, numpy as np, pandas as pd
from sklearn.linear_model import QuantileRegressor
from data import players, kenpom, tiers, SAME_SCHOOL
from teams import team_mapper
from recommend import _pred_at
from torvik_join import MAIN
RATINGS, ASOF = sys.argv[1], sys.argv[2]
TEAM_FILE = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
PLAYER_FILE = sys.argv[4] if len(sys.argv) > 4 else None      # Torvik current-season player file (hometowns and heights for newcomers)
canon = lambda t: SAME_SCHOOL.get(t, t) if isinstance(t, str) else t
GRID = np.round(np.arange(1, 5.01, 0.25), 2)
D = json.load(open("page_data.json"))
pm = {**D["seasons"]["2027"]["model"]}; mm = {**D["seasons"]["2027"]["mins"]}     # trained on all five past cycles
for m in (pm, mm): m["features"] = list(m["coef"])
# ---------- current rosters, linked to 2025-26 by EvanMiya player ID
R = pd.read_csv(RATINGS); m26 = team_mapper(kenpom, 2026)
R["kp"] = R.Team.map(m26); R["c"] = R.kp.map(canon); R["pid"] = R["Player ID"].astype("int64")
# most recent season with D-I possessions, by EvanMiya ID (usually 2025-26; earlier for players who sat out)
lastrows = []
for season in sorted(players):
    p = players[season].dropna(subset=["pid"]); p = p[p.poss > 0].copy(); p["pid"] = p.pid.astype("int64"); p["season"] = season
    lastrows.append(p[["pid", "season", "bpr", "obpr", "dbpr", "poss", "position", "role", "team"]])
LR = pd.concat(lastrows).sort_values(["season", "poss"]).drop_duplicates("pid", keep="last").set_index("pid")
for col, src in [("bpr", "bpr"), ("obpr", "obpr"), ("dbpr", "dbpr"), ("poss", "poss"), ("pos", "position"), ("role", "role"), ("team", "team"), ("season", "season")]:
    R[f"last_{col}"] = R.pid.map(LR[src])
R["stats_from"] = R.last_season.map(lambda y: None if pd.isna(y) or y == 2026 else f"{int(y)-1}–{str(int(y))[2:]}")
R.loc[R.last_season.isna() & (R.Poss > 0), "stats_from"] = "this season only"
adj26 = kenpom[kenpom.Season == 2026].set_index("TeamName").AdjEM.to_dict()
TEAM_SOURCE = "2025–26 KenPom ratings"
if TEAM_FILE:      # optional: Torvik <year>_team_results.csv for the current season (tracks KenPom at r = 0.995)
    raw = pd.read_csv(TEAM_FILE, header=None, skiprows=1)
    tv_now = pd.DataFrame({"team": raw[1], "adjem": raw[4] - raw[6]})
    ALIAS = {"McNeese St.": ["McNeese", "McNeese St."], "Cal St. Northridge": ["CSUN", "Cal St. Northridge"],
             "Southeast Missouri St.": ["Southeast Missouri", "Southeast Missouri St."], "Nicholls St.": ["Nicholls", "Nicholls St."],
             "UMKC": ["Kansas City", "UMKC"], "Detroit Mercy": ["Detroit Mercy", "Detroit"], "Saint Francis": ["Saint Francis", "St. Francis PA"]}
    tv_now["kp"] = [m26(t) or next((c for c in ALIAS.get(t, []) if c in adj26), None) for t in tv_now.team]
    cur = dict(zip(tv_now.kp.dropna(), tv_now.adjem[tv_now.kp.notna()]))
    print(f"current Torvik ratings matched for {len(cur)} of {len(adj26)} teams")
    adj26 = {t: cur.get(t, a) for t, a in adj26.items()}
    TEAM_SOURCE = "Torvik 2026–27 ratings"
R["team_adj"] = R.kp.map(adj26)
# ---------- each player's inputs: last season blended with this season so far (last season counts half per possession)
has_last = R.last_poss.fillna(0) > 0
w_last = (R.last_poss.fillna(0) * 0.5).where(has_last, 0.0); w_cur = R.Poss.clip(lower=0)
blend = lambda last, cur: ((w_last * R[last].fillna(0) + w_cur * R[cur]) / (w_last + w_cur).replace(0, np.nan))
R["prior_bpr"], R["prior_obpr"], R["prior_dbpr"] = blend("last_bpr", "BPR"), blend("last_obpr", "OBPR"), blend("last_dbpr", "DBPR")
R["prior_poss"] = np.maximum(R.last_poss.fillna(0), R.Poss)
# position and role are estimated from play, so early-season values are noisy: blend them the same way as BPR
def blend_est(last, cur):
    cur_ok = (R[cur] > 0) & (R.Poss > 0); wc = w_cur.where(cur_ok, 0.0); wl = w_last.where(R[last].notna(), 0.0)
    out = (wl * R[last].fillna(0) + wc * R[cur].where(cur_ok, 0)) / (wl + wc).replace(0, np.nan)
    return out.fillna(R[cur].where(R[cur] > 0))
R["prior_position"], R["prior_role"] = blend_est("last_pos", "Position"), blend_est("last_role", "Role")
R["origin_prior_AdjEM"] = R.team_adj
# Torvik style, hometown, archetype from the most recent season he appears in
links = pd.read_pickle("links.pkl"); tv = pd.read_pickle("tv_feat.pkl")
lk = links.dropna(subset=["torvik_pid", "miya_pid"]).sort_values("season").drop_duplicates("miya_pid", keep="last")
tvl = tv.sort_values("year").drop_duplicates("torvik_pid", keep="last").set_index("torvik_pid")
tpid = R.pid.map(dict(zip(lk.miya_pid.astype("int64"), lk.torvik_pid)))
for c in MAIN + ["hometown", "archetype"]: R[c] = tpid.map(tvl[c])
# Current-season Torvik player file: hometown and height for players we don't have them for (mostly newcomers).
# Style stats after a few games are too noisy, so only these two are taken.
R["hometown_source"] = np.where(R.hometown.notna(), "past", None)
if PLAYER_FILE:
    from load_torvik import PCOLS
    SUF = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
    nkey = lambda x: re.sub(r"[^a-z]", "", SUF.sub("", re.sub(r"[.\-']", " ", str(x).lower().replace("’", "'"))))
    def ikey(x):
        w = [p for p in SUF.sub("", re.sub(r"[.\-']", " ", str(x).lower())).split() if p]
        return (w[0][:1] + w[-1]) if len(w) >= 2 else nkey(x)
    cur = pd.read_csv(PLAYER_FILE, header=None, low_memory=False).iloc[:, :len(PCOLS)]; cur.columns = PCOLS
    cur["ht_in"] = cur.ht.astype(str).str.extract(r"(\d+)-(\d+)").astype(float).pipe(lambda x: x[0] * 12 + x[1])
    ALIAS_T = {"McNeese St.": "McNeese", "Cal St. Northridge": "CSUN", "Southeast Missouri St.": "Southeast Missouri",
               "Nicholls St.": "Nicholls", "UMKC": "Kansas City", "Detroit Mercy": "Detroit Mercy"}
    cur["kp"] = [m26(t) or ALIAS_T.get(t) for t in cur.team]
    full = cur.drop_duplicates(["kp", "player"]).assign(k=lambda x: x.player.map(nkey)).drop_duplicates(["kp", "k"], keep=False).set_index(["kp", "k"])
    ini = cur.assign(k=cur.player.map(ikey)).drop_duplicates(["kp", "k"], keep=False).set_index(["kp", "k"])
    def look(name, team, col):
        for tab, key in ((full, nkey(name)), (ini, ikey(name))):
            if (team, key) in tab.index: return tab.at[(team, key), col]
        return np.nan
    need_home = R.hometown.isna(); need_ht = R.ht_in.isna()
    R.loc[need_home, "hometown"] = [look(n, t, "hometown") for n, t in zip(R.Name[need_home], R.kp[need_home])]
    R.loc[need_ht, "ht_in"] = [look(n, t, "ht_in") for n, t in zip(R.Name[need_ht], R.kp[need_ht])]
    R.loc[need_home & R.hometown.notna(), "hometown_source"] = "current Torvik"
    print(f"current Torvik file: hometowns added for {int((need_home & R.hometown.notna()).sum())} players, heights for {int((need_ht & R.ht_in.notna()).sum())}")
    # geocode any hometown we haven't seen before, and remember it
    HLc = pd.read_csv("hometown_locations.csv")
    new = sorted(set(R.hometown.dropna()) - set(HLc.hometown))
    if new:
        from hometowns import locate
        add = pd.DataFrame([locate(h) for h in new], columns=["lat", "lon", "precision", "international"]); add["hometown"] = new
        pd.concat([HLc, add], ignore_index=True).to_csv("hometown_locations.csv", index=False)
        print(f"geocoded {len(new)} new hometowns ({int(add.lat.notna().sum())} located)")
# Newcomers' raw possessions mostly reflect how few games have been played. For the landing model (which reads minutes as
# a sign of role and market), project them to a full season from their share of the team's possessions so far.
team_poss = R.groupby("Team").Poss.transform("sum").clip(lower=1)
R["pace_poss"] = (R.Poss / team_poss * 5 * 2100).clip(upper=2300)      # ~2,100 team possessions in a season, 5 players on the floor
R["landing_poss"] = np.where(R.last_season.isna(), R.pace_poss, R.prior_poss)
# eligible for the watch list: not a senior, on a rated D-I team, and enough college track record
R["eligible"] = (R.Class != "SR") & R.team_adj.notna() & (has_last | (R.Poss > 0))
pool = R[R.eligible].reset_index(drop=True)
print("players using stats from before 2025-26:", int(pool.stats_from.notna().sum()) if "stats_from" in pool else 0)
print(f"current players: {len(R)} | non-seniors: {(R.Class != 'SR').sum()} | on the watch list: {len(pool)}"
      f" (haven't played a college possession yet: {int(((R.Class != 'SR') & R.team_adj.notna() & ~(has_last | (R.Poss > 0))).sum())})")
# ---------- landing ranges (trained on all past cycles)
pools = pd.read_pickle("pools.pkl")
lt = pools[pools.prior_bpr.notna() & (pools.prior_poss > 0) & pools.origin_prior_AdjEM.notna() & pools.dest_prior_AdjEM.notna()].copy()
F = ["prior_bpr", "log_poss", "bpr_x_lp", "origin_prior_AdjEM", "prior_position", "lean"]
for d in (lt, pool):
    pp = d.landing_poss if "landing_poss" in d else d.prior_poss
    d["log_poss"] = np.log1p(pp); d["bpr_x_lp"] = d.prior_bpr * d.log_poss; d["lean"] = d.prior_obpr - d.prior_dbpr
med = lt[F].median(); Q = [0.1, 0.25, 0.5, 0.75, 0.9]
L = np.sort(np.column_stack([QuantileRegressor(quantile=q, alpha=0, solver="highs").fit(lt[F].fillna(med), lt.dest_prior_AdjEM)
                             .predict(pool[F].fillna(med)) for q in Q]), axis=1)
for i, q in enumerate(Q): pool[f"land_q{int(q*100)}"] = L[:, i]
# ---------- teams: next season's openings = minutes held by this season's seniors
trow = tiers[tiers.Season == 2026].set_index("TeamName")
R["weight"] = R.Poss.clip(lower=0)      # roster roles use this season's possessions
teams, rosters, spots = [], {}, {}
for t, g in R[R.kp.notna()].groupby("kp"):
    if t not in adj26: continue
    tot, lost = np.zeros_like(GRID, float), np.zeros_like(GRID, float)
    for pos, w, sr in zip(g.prior_position, g.weight, g.Class == "SR"):
        if pd.isna(pos) or w <= 0: continue
        k = np.exp(-0.5 * ((GRID - pos) / 0.5) ** 2); tot += w * k; lost += w * k * sr
    wsum = g.weight.clip(lower=0).sum()
    teams.append({"team": t, "adjem": round(adj26[t], 2), "conf": trow.Conference.get(t), "tier": trow.Conference_Tier.get(t),
                  "need": np.round(lost / np.maximum(tot, 1e-9), 3).tolist(),
                  "returning": round(1 - g.weight[g.Class == "SR"].sum() / max(wsum, 1), 3), "signed": []})
    rosters[t] = [[n, round(float(p), 2), int(w), bool(sr)] for n, p, w, sr in zip(g.Name, g.prior_position, g.weight, g.Class == "SR")
                  if pd.notna(p) and w > 0]
    spots[canon(t)] = int(((g.Class == "SR") & (g.weight >= 0.02 * max(wsum, 1))).sum())
teams = sorted(teams, key=lambda x: x["team"])
# ---------- destination-choice inputs (coefficients from the all-season fit)
C27 = D["choice"]["2027"]; b = C27["b"]
SL = pd.read_csv("school_locations.csv").set_index("kp_team")
HL = pd.read_csv("hometown_locations.csv").drop_duplicates("hometown").set_index("hometown")
TT = pd.DataFrame(teams); TT["c"] = TT.team.map(canon)
TT["lat"] = TT.team.map(SL.lat).fillna(TT.c.map(SL.lat)); TT["lon"] = TT.team.map(SL.lon).fillna(TT.c.map(SL.lon))
TT["state"] = TT.team.map(SL.venue_address_state).fillna(TT.c.map(SL.venue_address_state))
TT["pull"] = TT.c.map({c: v["pull"] for c, v in C27["teams"].items()}).fillna(0.0); TT["spots"] = TT.c.map(spots).fillna(0).astype(int)
TT = TT[TT.lat.notna()].reset_index(drop=True)
conf_of = dict(zip(TT.c, TT.conf))
pool["o_c"] = pool.kp.map(canon)
pool["h_lat"], pool["h_lon"] = pool.hometown.map(HL.lat), pool.hometown.map(HL.lon)
pool["h_dom"] = pool.hometown.map(HL.international).map(lambda v: v is False or v == 0 or str(v) == "False")
pool["h_state"] = pool.hometown.astype(str).str.extract(r",\s*([A-Z]{2})$")[0]
pool["o_lat"], pool["o_lon"] = pool.kp.map(SL.lat).fillna(pool.o_c.map(SL.lat)), pool.kp.map(SL.lon).fillna(pool.o_c.map(SL.lon))
pool["o_conf"] = pool.o_c.map(conf_of)
def km(a1, o1, a2, o2):
    p = np.pi / 180; a = np.sin((a2 - a1) * p / 2) ** 2 + np.cos(a1 * p) * np.cos(a2 * p) * np.sin((o2 - o1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))
tl, tn = TT.lat.to_numpy()[None, :], TT.lon.to_numpy()[None, :]
DH = np.log1p(km(pool.h_lat.to_numpy(float)[:, None], pool.h_lon.to_numpy(float)[:, None], tl, tn))
DO = np.log1p(km(pool.o_lat.to_numpy(float)[:, None], pool.o_lon.to_numpy(float)[:, None], tl, tn))
fill_dh, fill_do = float(np.nanmean(DH)), float(np.nanmean(DO))
domDH = np.where(pool.h_dom.to_numpy()[:, None] & ~np.isnan(DH), DH, np.nan)
team_fill = np.nanmean(domDH, axis=0)                      # each school's average distance from players' hometowns
team_fill = np.where(np.isnan(team_fill), fill_dh, team_fill)
adjT = TT.adjem.to_numpy()[None, :]
z = (adjT - pool.land_q50.to_numpy()[:, None]) / np.maximum((pool.land_q90 - pool.land_q10).to_numpy()[:, None], 5)
pos = pool.prior_position.fillna(3).to_numpy()
needM = np.stack([np.interp(pos, GRID, np.array(n)) for n in TT.need], axis=1)
X = {"z": z, "z2": z ** 2, "z_pos2": np.maximum(z, 0) ** 2, "pull": TT.pull.to_numpy()[None, :], "pull_x_z": TT.pull.to_numpy()[None, :] * z / 10,
     "same_conf": (pool.o_conf.to_numpy()[:, None] == TT.conf.to_numpy()[None, :]) & pool.o_conf.notna().to_numpy()[:, None],
     "high_tier": (TT.tier.to_numpy() == "High")[None, :], "need": needM, "open_spots": np.log1p(TT.spots.to_numpy())[None, :],
     # known domestic hometown: real distance; known international hometown: the overall average (as in training);
     # unknown hometown (mostly newcomers): that school's own average, so a missing hometown is neutral rather than an advantage
     "dist_home": np.where(pool.h_dom.to_numpy()[:, None] & ~np.isnan(DH), DH,
                           np.where(pool.hometown.notna().to_numpy()[:, None], fill_dh, team_fill[None, :])) / 7,
     "dist_origin": np.where(np.isnan(DO), fill_do, DO) / 7,
     "home_state": (pool.h_state.to_numpy()[:, None] == TT.state.to_numpy()[None, :]), "followed_coach": np.zeros((len(pool), len(TT)))}
U = sum(b[k] * np.asarray(X[k], float) for k in b)
U = np.where(pool.o_c.to_numpy()[:, None] == TT.c.to_numpy()[None, :], -np.inf, U)
mx = U.max(1, keepdims=True); lse = np.log(np.exp(U - mx).sum(1)) + mx[:, 0]
# ---------- assemble in the page's format
letter = lambda p: None if pd.isna(p) else "PG" if p < 1.6 else "SG" if p < 2.4 else "SF" if p < 3.4 else "PF" if p < 4.3 else "C"
pool["name"] = pool.Name
pool["team"], pool["origin_kp"], pool["position"], pool["class"] = pool.Team, pool.kp, pool.prior_position.map(letter), pool.Class
pool["new_team"] = pool["dest_kp"] = pool["dest_prior_AdjEM"] = pool["actual_bpr"] = pool["actual_poss"] = None
pool["cur_bpr"], pool["cur_poss"] = pool.BPR, pool.Poss
pool["last_bpr_raw"], pool["last_poss_raw"] = pool.last_bpr, pool.last_poss
FIELDS = D["fields"] + [f for f in ["cur_bpr", "cur_poss", "stats_from", "last_bpr_raw", "last_poss_raw"] if f not in D["fields"]]
def r_(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return None
    if isinstance(v, (bool, np.bool_)): return bool(v)
    return round(float(v), 3) if isinstance(v, (float, np.floating, int, np.integer)) else v
rows = [[r_(row[f]) if f in pool.columns else None for f in FIELDS] for _, row in pool.iterrows()]
f4 = lambda v: None if pd.isna(v) else round(float(v), 4)
s_ = lambda v: v if isinstance(v, str) else None
out = {"fields": FIELDS,
       "season": {"model": {k: D["seasons"]["2027"]["model"][k] for k in ["intercept", "coef", "medians", "lo", "hi"]},
                  "mins": {k: D["seasons"]["2027"]["mins"][k] for k in ["intercept", "coef", "medians", "lo", "hi"]},
                  "rows": rows, "live": True, "mode": "watch", "asof": ASOF, "team_source": TEAM_SOURCE},
       "teams": teams, "rosters": rosters,
       "choice": {"b": b, "fill_dh": fill_dh, "fill_do": fill_do, "N": len(TT), "follow": {},
                  "players": [[round(float(l), 5), f4(a), f4(o), bool(dm), s_(hs), f4(oa), f4(oo), s_(oc), s_(h)]
                              for l, a, o, dm, hs, oa, oo, oc, h in zip(lse, pool.h_lat, pool.h_lon, pool.h_dom, pool.h_state, pool.o_lat, pool.o_lon, pool.o_conf, pool.hometown)],
                  "teams": {c: {"pull": round(float(p), 4), "spots": int(s), "lat": round(float(la), 4), "lon": round(float(lo), 4), "state": s_(st), "conf": s_(cf), "fill_dh": round(float(fd), 5)}
                            for c, p, s, la, lo, st, cf, fd in zip(TT.c, TT.pull, TT.spots, TT.lat, TT.lon, TT.state, TT.conf, team_fill)}}}
json.dump(out, open("watch_2028.json", "w"), separators=(",", ":"), allow_nan=False)
# short summary for the run log
print(f"teams: {len(teams)} | style found: {pool.usg.notna().mean():.1%} | hometown found: {pool.h_lat.notna().mean():.1%}")
