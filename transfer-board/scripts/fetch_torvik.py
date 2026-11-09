"""Download this season's Torvik team ratings and player file into inputs/torvik/.
A download only replaces the saved copy if it passes basic checks, so a blocked or broken
request leaves last week's good file in place (and says so)."""
import io, json, sys, datetime, pathlib
import pandas as pd, requests

SEASON = 2027                     # Torvik's year = the season's ending year (2027 = 2026-27)
OUT = pathlib.Path(__file__).resolve().parent.parent / "inputs" / "torvik"
SOURCES = {
    "team_results.csv": f"https://barttorvik.com/{SEASON}_team_results.csv",
    "players.csv": f"https://barttorvik.com/getadvstats.php?year={SEASON}&csv=1",
}

def check(name, content):
    """Return (ok, note). The content must be a real CSV, not an HTML block page."""
    if len(content) < 10_000 or b"<html" in content[:2000].lower():
        return False, "looks like a web page or an empty response, not a CSV"
    try:
        if name == "team_results.csv":
            d = pd.read_csv(io.BytesIO(content))
            if len(d) < 300 or not any("adjoe" in c.lower() for c in d.columns):
                return False, f"unexpected team file ({len(d)} rows)"
        else:
            d = pd.read_csv(io.BytesIO(content), header=None, low_memory=False)
            if len(d) < 1000 or d.shape[1] < 60 or int(d[31].mode()[0]) != SEASON:
                return False, f"unexpected player file ({len(d)} rows, {d.shape[1]} columns)"
    except Exception as e:
        return False, f"could not read it as a CSV ({e})"
    return True, f"{len(d)} rows"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    status = {}
    for name, url in SOURCES.items():
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (transfer-board weekly update)"}, timeout=60)
            ok, note = (check(name, r.content) if r.ok else (False, f"HTTP {r.status_code}"))
        except Exception as e:
            ok, note = False, f"download failed ({e.__class__.__name__})"
        if ok:
            (OUT / name).write_bytes(r.content)
            status[name] = {"updated": True, "note": note, "date": datetime.date.today().isoformat()}
            print(f"{name}: downloaded ({note})")
        else:
            kept = (OUT / name).exists()
            status[name] = {"updated": False, "note": note, "kept_previous": kept}
            print(f"{name}: NOT updated ({note}); {'keeping the previous copy' if kept else 'no previous copy available'}")
    (OUT / "fetch_status.json").write_text(json.dumps(status, indent=2))
    return status

if __name__ == "__main__":
    main()
