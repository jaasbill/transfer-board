import re, numpy as np, pandas as pd, geonamescache
gc = geonamescache.GeonamesCache()
W = pd.DataFrame(gc.get_cities().values())[["name", "latitude", "longitude", "countrycode", "admin1code", "population", "alternatenames"]]
countries = {v["name"].lower(): k for k, v in gc.get_countries().items()}
countries.update({"england": "GB", "scotland": "GB", "wales": "GB", "northern ireland": "GB", "united kingdom": "GB",
                  "bosnia and herzegovina": "BA", "bosnia": "BA", "czech republic": "CZ", "ivory coast": "CI", "cote d'ivoire": "CI",
                  "democratic republic of the congo": "CD", "dr congo": "CD", "congo": "CG", "republic of the congo": "CG",
                  "the bahamas": "BS", "bahamas": "BS", "south korea": "KR", "korea": "KR", "russia": "RU", "turkey": "TR",
                  "cape verde": "CV", "macedonia": "MK", "north macedonia": "MK", "u.s. virgin islands": "VI", "virgin islands": "VI",
                  "the netherlands": "NL", "netherlands": "NL", "russian federation": "RU",
                  "congo, the democratic republic of the": "CD", "virgin islands, u.s.": "VI", "korea, republic of": "KR",
                  "iran, islamic republic of": "IR", "tanzania, united republic of": "TZ", "venezuela, bolivarian republic of": "VE", "holland": "NL", "taiwan": "TW", "the gambia": "GM", "gambia": "GM", "usa": "US"})
CA_PROV = {"AB": "01", "BC": "02", "MB": "03", "NB": "04", "NL": "05", "NS": "07", "ON": "08", "PE": "09", "QC": "10", "SK": "11"}
us = pd.read_csv("us_cities.csv")
norm = lambda x: re.sub(r"[^a-z]", "", str(x).lower().replace("saint ", "st").replace("st. ", "st").replace("ft. ", "fort ").replace("mt. ", "mount "))
us["k"] = us.CITY.map(norm) + "|" + us.STATE_CODE
US_C = us.drop_duplicates("k").set_index("k")[["LATITUDE", "LONGITUDE"]]
US_STATE = us.groupby("STATE_CODE")[["LATITUDE", "LONGITUDE"]].median()
STATE_NAME = {n.lower(): c for n, c in zip(us.STATE_NAME, us.STATE_CODE)}
W["k"] = W.name.map(norm)
W_by = {}
for r in W.sort_values("population", ascending=False).itertuples():
    for nm in [r.name] + [a for a in r.alternatenames if a.isascii()][:15]:
        W_by.setdefault((norm(nm), r.countrycode), (r.latitude, r.longitude))
        W_by.setdefault((norm(nm), r.countrycode, r.admin1code), (r.latitude, r.longitude))
COUNTRY_C = W.groupby("countrycode").apply(lambda g: g.nlargest(1, "population")[["latitude", "longitude"]].iloc[0])
def locate(h):
    """Returns (lat, lon, precision, is_international)."""
    if pd.isna(h): return (np.nan, np.nan, None, None)
    parts = [p.strip() for p in str(h).split(",")]
    city, tail = (parts[0], parts[-1]) if len(parts) > 1 else ("", parts[0])
    if len(parts) > 2 and ", ".join(parts[1:]).lower() in countries: tail = ", ".join(parts[1:])
    if tail.lower() in STATE_NAME: tail = STATE_NAME[tail.lower()]
    if re.fullmatch(r"[A-Z]{2}", tail) and tail in US_STATE.index:            # U.S. state
        k = norm(city) + "|" + tail
        if k in US_C.index: return (*US_C.loc[k].tolist(), "city", False)
        return (*US_STATE.loc[tail].tolist(), "state", False)
    if tail in CA_PROV:                                                         # Canadian province
        hit = W_by.get((norm(city), "CA", CA_PROV[tail]))
        return (*(hit or COUNTRY_C.loc["CA"].tolist()), "city" if hit else "country", True)
    if tail == "PR": tail = "puerto rico"
    cc = countries.get(tail.lower())
    if cc is None: return (np.nan, np.nan, None, None)
    if cc == "US": return (np.nan, np.nan, None, False)
    hit = W_by.get((norm(city), cc)) if city else None
    if hit: return (*hit, "city", True)
    return (*COUNTRY_C.loc[cc].tolist(), "country", True) if cc in COUNTRY_C.index else (np.nan, np.nan, None, True)
if __name__ == "__main__":
    tv = pd.read_pickle("tv.pkl")
    hs = pd.Series(tv.hometown.dropna().unique())
    L = pd.DataFrame([locate(h) for h in hs], columns=["lat", "lon", "precision", "international"]); L["hometown"] = hs
    L.to_csv("hometown_locations.csv", index=False)
    w = tv.hometown.map(L.set_index("hometown").precision).fillna("not found")
    print("players by precision:", w.value_counts(normalize=True).round(3).to_dict())
    print("unfound sample:", L[L.lat.isna()].hometown.head(12).tolist())
    for h in ["Mars, PA", "Newport, ME", "Toronto, ON", "Melbourne, Australia", "Dakar, Senegal", "Charlotte, NC", "Pennsauken, NJ"]:
        print(h, L[L.hometown == h][["lat", "lon", "precision"]].round(2).values.tolist())
