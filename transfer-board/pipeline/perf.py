"""Player performance model: expected BPR at a destination, from pre-transfer info only."""
import numpy as np, pandas as pd

def add_features(df, dest_col="destination_prior_AdjEM"):
    d = df.copy()
    d["log_prior_poss"] = np.log1p(d["prior_poss"].clip(lower=0))
    d["offense_lean"] = d["prior_obpr"] - d["prior_dbpr"]
    d["strength_change"] = d[dest_col] - d["origin_prior_AdjEM"]
    d["strength_change_sq"] = d["strength_change"] ** 2
    d["bpr_x_log_poss"] = d["prior_bpr"] * d["log_prior_poss"]
    d["prior_bpr_sq"] = d["prior_bpr"] ** 2
    d["bpr_x_strength_change"] = d["prior_bpr"] * d["strength_change"]
    d["destination_prior_AdjEM"] = d[dest_col]
    return d

BASE = ["prior_bpr", "log_prior_poss", "origin_prior_AdjEM", "destination_prior_AdjEM",
        "offense_lean", "prior_position", "prior_role", "strength_change_sq"]
SPECS = {
    "Forrest full model": BASE,
    "+ BPR confidence": BASE + ["bpr_x_log_poss", "prior_bpr_sq"],
    "+ BPR confidence + move": BASE + ["bpr_x_log_poss", "prior_bpr_sq", "bpr_x_strength_change"],
}

def fit(train, features, y="actual_bpr"):
    """OLS on raw features; medians from training rows fill gaps. Returns dict usable in Python and JS."""
    med = train[features].median()
    X = train[features].fillna(med).to_numpy(float)
    X = np.column_stack([np.ones(len(X)), X])
    beta = np.linalg.lstsq(X, train[y].to_numpy(float), rcond=None)[0]
    resid = train[y].to_numpy(float) - X @ beta
    return {"features": features, "intercept": beta[0], "coef": dict(zip(features, beta[1:])),
            "medians": med.to_dict()}

def predict(model, df):
    X = df[model["features"]].fillna(pd.Series(model["medians"]))
    return model["intercept"] + X.to_numpy(float) @ np.array([model["coef"][f] for f in model["features"]])
