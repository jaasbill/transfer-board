"""Attach last-season Torvik style (and archetype, hometown) to portal pool players and the training panel."""
import re, numpy as np, pandas as pd
from data import SAME_SCHOOL, kenpom
from teams import team_mapper
tv = pd.read_pickle("./tv_feat.pkl")
ts = pd.read_pickle("./team_style.pkl")
MAIN = ["usg", "three_rate", "rim_rate", "ftr", "ast_pct", "to_pct", "reb_pct", "blk_pct", "stl_pct", "ht_in"]
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
nkey = lambda x: re.sub(r"[^a-z]", "", SUFFIX.sub("", re.sub(r"[.\-']", " ", str(x).lower().replace("’", "'"))))
def ikey(x):
    w = [p for p in SUFFIX.sub("", re.sub(r"[.\-']", " ", str(x).lower())).split() if p]
    return w[0][:1] + w[-1] if len(w) >= 2 else nkey(x)
canon = lambda t: SAME_SCHOOL.get(t, t) if isinstance(t, str) else t
tv["nk"], tv["ik"] = tv.player.map(nkey), tv.player.map(ikey)

def attach_style(df, season_col, name_col, team_kp_col):
    """Match on name + team in the PRIOR season (season_col - 1)."""
    out = df.copy(); cols = MAIN + ["archetype", "hometown", "torvik_role"]
    vals = []
    for s, nm, tm in zip(out[season_col], out[name_col], out[team_kp_col]):
        t = tv[(tv.year == s - 1) & (tv.kpc == canon(tm))]
        hit = t[t.nk == nkey(nm)]
        if hit.empty: hit = t[t.ik == ikey(nm)]
        vals.append(hit.iloc[0][cols] if len(hit) == 1 or (len(hit) > 1 and hit.nk.nunique() == 1) else pd.Series(index=cols, dtype=object))
    v = pd.DataFrame(vals).reset_index(drop=True)
    for c in cols: out[c] = v[c].values
    for c in MAIN: out[c] = pd.to_numeric(out[c], errors="coerce")
    return out
