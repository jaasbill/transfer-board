import re, pandas as pd

TEAM_FIXES = {
    "Alabama State": "Alabama St.", "Alcorn State": "Alcorn St.", "Appalachian State": "Appalachian St.",
    "Arizona State": "Arizona St.", "Arkansas State": "Arkansas St.", "Ball State": "Ball St.",
    "Bethune-Cookman": "Bethune Cookman", "Cal State Fullerton": "Cal St. Fullerton",
    "Cleveland State": "Cleveland St.", "Colorado State": "Colorado St.",
    "East Tennessee State": "East Tennessee St.", "Florida International": "FIU",
    "Florida State": "Florida St.", "Georgia State": "Georgia St.", "Grambling": "Grambling St.",
    "Illinois-Chicago": "Illinois Chicago", "Indiana State": "Indiana St.", "Iowa State": "Iowa St.",
    "Jacksonville State": "Jacksonville St.", "Kansas State": "Kansas St.", "Kennesaw State": "Kennesaw St.",
    "Kent State": "Kent St.", "Long Beach State": "Long Beach St.", "Louisiana-Lafayette": "Louisiana",
    "Louisiana-Monroe": "Louisiana Monroe", "Loyola Maryland": "Loyola MD",
    "Maryland-Eastern Shore": "Maryland Eastern Shore", "McNeese State": ["McNeese", "McNeese St."],
    "Miami (Fla.)": "Miami FL", "Mississippi State": "Mississippi St.", "Missouri State": "Missouri St.",
    "Montana State": "Montana St.", "Morehead State": "Morehead St.", "Murray State": "Murray St.",
    "NC State": "N.C. State", "New Mexico State": "New Mexico St.", "Nicholls State": ["Nicholls", "Nicholls St."],
    "Norfolk State": "Norfolk St.", "North Dakota State": "North Dakota St.",
    "Northwestern State": "Northwestern St.", "Ohio State": "Ohio St.", "Oklahoma State": "Oklahoma St.",
    "Ole Miss": "Mississippi", "Oregon State": "Oregon St.", "Portland State": "Portland St.",
    "Prairie View": "Prairie View A&M", "Sacramento State": "Sacramento St.",
    "Sam Houston State": "Sam Houston St.", "San Diego State": "San Diego St.", "San Jose State": "San Jose St.",
    "South Carolina State": "South Carolina St.",
    "Southeast Missouri State": ["Southeast Missouri", "Southeast Missouri St."],
    "Southern Mississippi": "Southern Miss", "St. Thomas (MN)": "St. Thomas", "Tarleton State": "Tarleton St.",
    "Tennessee-Martin": "Tennessee Martin", "Tennessee State": "Tennessee St.",
    "Texas A&M-Corpus Christi": "Texas A&M Corpus Chris", "Texas State": "Texas St.",
    "Texas-Rio Grande Valley": "UT Rio Grande Valley", "Utah State": "Utah St.",
    "Washington State": "Washington St.", "Weber State": "Weber St.", "Wichita State": "Wichita St.",
    "Youngstown State": "Youngstown St.", "Arkansas-Little Rock": "Little Rock",
    "Cal State Northridge": ["CSUN", "Cal St. Northridge"], "California Baptist": "Cal Baptist",
    "College of Charleston": "Charleston", "Detroit": "Detroit Mercy", "Fort Wayne": "Purdue Fort Wayne",
    "Long Island": "LIU", "Omaha": "Nebraska Omaha", "SIU Edwardsville": ["SIUE", "SIU Edwardsville"],
    "Saint Bonaventure": "St. Bonaventure", "South Carolina Upstate": "USC Upstate", "Miami (OH)": "Miami OH",
    "Missouri-Kansas City": ["Kansas City", "UMKC"], "Saint Francis (PA)": ["Saint Francis", "St. Francis PA"],
    "IU Indy": ["IU Indy", "IUPUI"], "IUPUI": ["IU Indy", "IUPUI"], "Utah Tech": ["Utah Tech", "Dixie St."],
    "Houston Christian": ["Houston Christian", "Houston Baptist"],
    "East Texas A&M": ["East Texas A&M", "Texas A&M Commerce"],
    "Texas A&M–Commerce": ["East Texas A&M", "Texas A&M Commerce"],
    "Texas A&M-Commerce": ["East Texas A&M", "Texas A&M Commerce"],
}

def _norm(x):
    x = str(x).lower().replace("&", "and")
    x = re.sub(r"\bsaint\b", "st", x)
    x = re.sub(r"\bstate\b", "st", x)
    return re.sub(r"[^a-z0-9]", "", x)

def team_mapper(kenpom, season):
    """Return a function mapping an EvanMiya team name to that season's KenPom name (or None)."""
    kp = set(kenpom.loc[kenpom["Season"] == season, "TeamName"].dropna().astype(str))
    norm = {_norm(x): x for x in kp}
    cache = {}
    def f(name):
        if pd.isna(name) or str(name).strip() == "":
            return None
        name = str(name).strip()
        if name in cache:
            return cache[name]
        cands = TEAM_FIXES.get(name, [])
        cands = [cands] if isinstance(cands, str) else list(cands)
        hit = next((c for c in cands if c in kp), None)
        if hit is None and name in kp:
            hit = name
        if hit is None:
            hit = norm.get(_norm(name))
        cache[name] = hit
        return hit
    return f
