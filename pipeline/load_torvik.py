import glob, re, numpy as np, pandas as pd
U = "./"
PCOLS = ["player","team","conf","gp","min_pct","ortg","usg","efg","ts","orb_pct","drb_pct","ast_pct","to_pct",
         "ftm","fta","ft_pct","two_m","two_a","two_pct","three_m","three_a","three_pct","blk_pct","stl_pct","ftr",
         "yr","ht","num","porpag","adjoe","pfr","year","torvik_pid","hometown","rec_rank","ast_tov",
         "rim_m","rim_a","mid_m","mid_a","rim_pct","mid_pct","dunk_m","dunk_a","dunk_pct","pick","drtg","adrtg",
         "dporpag","stops","bpm","obpm","dbpm","gbpm","mpg","ogbpm","dgbpm","oreb","dreb","treb","ast","stl","blk",
         "pts","torvik_role","unknown_65","birthdate"]
def height_in(h):
    m = re.match(r"(\d+)-(\d+)", str(h)); return int(m[1]) * 12 + int(m[2]) if m else np.nan
def load_players():
    out = []
    for f in sorted(glob.glob(U + "trank_data*.csv")):
        d = pd.read_csv(f, header=None, names=PCOLS, low_memory=False)
        d["file"] = f.split("/")[-1]; out.append(d)
    p = pd.concat(out, ignore_index=True)
    p["ht_in"] = p["ht"].map(height_in)
    p["fga"] = p["two_a"] + p["three_a"]
    p["three_rate"] = p["three_a"] / p["fga"].where(p["fga"] > 0)
    p["rim_rate"] = p["rim_a"] / p["fga"].where(p["fga"] > 0)
    p["mid_rate"] = p["mid_a"] / p["fga"].where(p["fga"] > 0)
    p["dunk_rate"] = p["dunk_a"] / p["fga"].where(p["fga"] > 0)
    return p
TCOLS_KEEP = {"team":"team","conf":"conf","adjoe":"t_adjoe","adjde":"t_adjde","barthag":"t_barthag","adjt":"t_tempo"}
def load_teams():
    out = []
    for f in sorted(glob.glob(U + "*_team_results.csv")):
        y = int(re.search(r"(\d{4})_team", f)[1])
        raw = pd.read_csv(f, header=None, skiprows=1)      # header row is inconsistent across years; use positions
        d = pd.DataFrame({"team": raw[1], "conf": raw[2], "t_adjoe": raw[4], "t_adjde": raw[6],
                          "t_barthag": raw[8], "t_tempo": raw[raw.columns[-1]]})
        d["year"] = y; out.append(d)
    return pd.concat(out, ignore_index=True)
