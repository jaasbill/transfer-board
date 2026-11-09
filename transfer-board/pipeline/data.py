"""Load and assemble the tables the recommender needs."""
import re, numpy as np, pandas as pd
from teams import team_mapper

D = "./"
PORTAL = {2022: "21-22TransferPortal.csv", 2023: "22-23TransferPortal.csv", 2024: "23-24TransferPortal.csv",
          2025: "24-25TransferPortal.csv", 2026: "25-26Transfers.csv"}
PLAYERS = {s: f"{str(s-1)[2:]}-{str(s)[2:]}FullPlayerData.csv" for s in range(2021, 2027)}
SAME_SCHOOL = {"Dixie St.": "Utah Tech", "Houston Baptist": "Houston Christian", "IUPUI": "IU Indy",
               "UMKC": "Kansas City", "Texas A&M Commerce": "East Texas A&M", "St. Francis PA": "Saint Francis",
               "Cal St. Northridge": "CSUN", "McNeese St.": "McNeese", "Nicholls St.": "Nicholls",
               "SIU Edwardsville": "SIUE", "Southeast Missouri St.": "Southeast Missouri"}
POS_LETTER = {"PG": 1.0, "SG": 2.0, "SF": 3.0, "PF": 4.0, "C": 5.0}

def norm_name(x):
    return re.sub(r"[^a-z0-9]", "", str(x).lower())

kenpom = pd.read_csv(D + "KenPom Data - MAT395 - Master Sheet.csv")
adjem = kenpom.set_index(["Season", "TeamName"])["AdjEM"].to_dict()
tiers = pd.read_csv(D + "Team_Conference_By_Season_with_Tiers.csv")

def load_players(season):
    p = pd.read_csv(D + PLAYERS[season])
    m = team_mapper(kenpom, season)
    p["kp_team"] = p["team"].map(m)
    p["pid"] = pd.to_numeric(p["players"], errors="coerce").astype("Int64")
    p["nkey"] = p["name"].map(norm_name) + "|" + p["team"].astype(str)
    return p

players = {s: load_players(s) for s in PLAYERS}

def portal_pool(season):
    """Every portal entrant for `season` with pre-transfer inputs attached (all from season-1)."""
    p = pd.read_csv(D + PORTAL[season]).copy()
    prev = players[season - 1]
    cur = players[season]
    mo, md = team_mapper(kenpom, season - 1), team_mapper(kenpom, season)
    p["season"] = season
    p["origin_kp"] = p["team"].map(mo)
    p["dest_kp"] = p["new_team"].map(md)
    p["pid"] = pd.to_numeric(p["players"], errors="coerce").astype("Int64")
    p["nkey"] = p["name"].map(norm_name) + "|" + p["team"].astype(str)

    # Prior-season row: by ID, then by name + old team (IDs changed in the early files)
    cols = ["pid", "nkey", "bpr", "obpr", "dbpr", "poss", "position", "role", "players", "team"]
    by_id = prev[cols].dropna(subset=["pid"]).drop_duplicates("pid").set_index("pid")
    by_nm = prev[cols].drop_duplicates("nkey").set_index("nkey")
    rows = []
    for _, r in p.iterrows():
        hit = by_id.loc[r["pid"]] if pd.notna(r["pid"]) and r["pid"] in by_id.index else (
              by_nm.loc[r["nkey"]] if r["nkey"] in by_nm.index else None)
        rows.append(hit)
    pr = pd.DataFrame([h if h is not None else pd.Series(dtype=float) for h in rows]).reset_index(drop=True)
    p["prior_bpr"] = pd.to_numeric(pr.get("bpr"), errors="coerce").fillna(p["bpr_prev"]).values
    p["prior_obpr"] = pd.to_numeric(pr.get("obpr"), errors="coerce").fillna(p["obpr_prev"]).values
    p["prior_dbpr"] = pd.to_numeric(pr.get("dbpr"), errors="coerce").fillna(p["dbpr_prev"]).values
    p["prior_poss"] = pd.to_numeric(pr.get("poss"), errors="coerce").fillna(p["possessions"]).values
    p["prior_position"] = pd.to_numeric(pr.get("position"), errors="coerce").values
    p["prior_position"] = p["prior_position"].fillna(p["position"].map(POS_LETTER))
    p["prior_role"] = pd.to_numeric(pr.get("role"), errors="coerce").values
    p["prior_role"] = p["prior_role"].where(p["prior_role"] > 0).fillna(p["role"].where(p["role"] > 0))
    p["player_file_id"] = pd.to_numeric(pr.get("players"), errors="coerce").values
    p["prior_team_file"] = pr.get("team").values if "team" in pr else None

    p["origin_prior_AdjEM"] = [adjem.get((season - 1, t), np.nan) for t in p["origin_kp"]]
    p["dest_prior_AdjEM"] = [adjem.get((season - 1, SAME_SCHOOL.get(t, t)), adjem.get((season - 1, t), np.nan))
                             if t else np.nan for t in p["dest_kp"]]

    # Outcome (backtest only): season row by player-file ID, else name + new team
    c_id = cur.dropna(subset=["pid"]).drop_duplicates("pid").set_index("pid")
    cur_nm = cur.assign(nk2=cur["name"].map(norm_name) + "|" + cur["team"].astype(str)).drop_duplicates("nk2").set_index("nk2")
    act_bpr, act_poss, act_team = [], [], []
    for _, r in p.iterrows():
        key = r["player_file_id"]
        hit = c_id.loc[int(key)] if pd.notna(key) and int(key) in c_id.index else None
        if hit is None:
            k2 = norm_name(r["name"]) + "|" + str(r["new_team"])
            hit = cur_nm.loc[k2] if k2 in cur_nm.index else None
        act_bpr.append(hit["bpr"] if hit is not None else np.nan)
        act_poss.append(hit["poss"] if hit is not None else np.nan)
        act_team.append(hit["team"] if hit is not None else None)
    p["actual_bpr"], p["actual_poss"], p["actual_team_miya"] = act_bpr, act_poss, act_team
    # A few players appear twice in one cycle (two moves); keep the row that starts from last season's team
    p["_origin_match"] = (p["team"] == p["prior_team_file"]).astype(int)
    p["_key"] = p["player_file_id"].fillna(-1).astype(int).astype(str) + "|" + p["name"].map(norm_name)
    p = p.sort_values("_origin_match", ascending=False).drop_duplicates("_key").sort_index()
    keep = ["season", "name", "team", "origin_kp", "new_team", "dest_kp", "class", "position", "height",
            "prior_bpr", "prior_obpr", "prior_dbpr", "prior_poss", "prior_position", "prior_role",
            "origin_prior_AdjEM", "dest_prior_AdjEM", "bpr_predicted", "actual_bpr", "actual_poss"]
    return p[keep]

def roster_departures(season):
    """Players on each team in season-1 who are not on the same team in `season` (canonical KenPom names)."""
    prev, cur = players[season - 1].copy(), players[season].copy()
    prev["kpc"] = prev["kp_team"].replace(SAME_SCHOOL)
    cur["kpc"] = cur["kp_team"].replace(SAME_SCHOOL)
    stay = set(zip(cur["pid"].astype("float"), cur["kpc"]))
    prev["departed"] = [(float(i), t) not in stay for i, t in zip(prev["pid"].astype("float"), prev["kpc"])]
    return prev[["kp_team", "name", "position", "role", "poss", "bpr", "departed"]]
