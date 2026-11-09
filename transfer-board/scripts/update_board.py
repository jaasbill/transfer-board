"""Weekly update: newest EvanMiya file + fresh Torvik files -> rebuilt board in site/index.html.
The new board only replaces the live one if it passes the checks below."""
import json, re, subprocess, sys, datetime, pathlib, shutil
ROOT = pathlib.Path(__file__).resolve().parent.parent
PIPE, SITE, EVAN, TORV = ROOT / "pipeline", ROOT / "site", ROOT / "inputs" / "evanmiya", ROOT / "inputs" / "torvik"
sys.path.insert(0, str(ROOT / "scripts"))

def newest_evanmiya():
    files = sorted(EVAN.glob("*.csv"))
    if not files: sys.exit("No EvanMiya file in inputs/evanmiya/. Upload the current player-ratings export there.")
    def committed(f):      # when the file was last added or changed in the repository (fallback: file time)
        try:
            out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(f)], cwd=ROOT, capture_output=True, text=True).stdout.strip()
            if out: return datetime.date.fromisoformat(out)
        except Exception: pass
        return datetime.date.fromtimestamp(f.stat().st_mtime)
    f = max(files, key=lambda x: (committed(x), x.stat().st_mtime))
    return f, committed(f)

def board_data(html):
    tag = '<script id="data" type="application/json">'
    i = html.index(tag) + len(tag); j = html.index("</script>", i)
    return json.loads(html[i:j].replace("<\\/", "</"))

def audit(new, old):
    """Basic checks. Returns a list of problems (empty = OK)."""
    p, W = [], new["seasons"].get("2028")
    if not W: return ["the watch list is missing"]
    FI = {f: k for k, f in enumerate(new["fields"])}
    rows = W["rows"]
    if len(rows) < 1000: p.append(f"only {len(rows)} players on the watch list")
    if any(r[FI["class"]] == "SR" for r in rows): p.append("seniors on the watch list")
    if any(not r[FI["name"]] for r in rows): p.append("players with no name")
    if len(new["teams"]["2028"]) < 350: p.append(f"only {len(new['teams']['2028'])} teams")
    if len(new["choice"]["2028"]["players"]) != len(rows): p.append("destination data doesn't line up with the player list")
    for k in ["prior_bpr", "land_q50"]:
        bad = sum(1 for r in rows if r[FI[k]] is None or not (-30 < r[FI[k]] < 60)) if k == "land_q50" else sum(1 for r in rows if r[FI[k]] is None)
        if bad: p.append(f"{bad} players missing or out-of-range {k}")
    old_n = len(old["seasons"].get("2028", {}).get("rows", []))
    if old_n and len(rows) < 0.7 * old_n: p.append(f"watch list shrank from {old_n} to {len(rows)} players")
    for s in [s for s in old["seasons"] if s != "2028"]:
        if len(new["seasons"].get(s, {}).get("rows", [])) != len(old["seasons"][s]["rows"]): p.append(f"past season {s} changed size")
    return p

REQUIRED = ["Name", "Team", "Class", "Player ID", "Poss", "BPR", "OBPR", "DBPR", "Position", "Role"]

def check_evanmiya(f):
    import pandas as pd
    try: d = pd.read_csv(f)
    except Exception as e: sys.exit(f"Couldn't read {f.name} as a CSV ({e}). The live board was NOT changed.")
    missing = [c for c in REQUIRED if c not in d.columns]
    if missing: sys.exit(f"{f.name} is missing columns {missing}. Is it EvanMiya's player-ratings export? The live board was NOT changed.")
    if len(d) < 3000: sys.exit(f"{f.name} has only {len(d)} players; the full D-I export has 5,000+. The live board was NOT changed.")

def main():
    evan, as_of = newest_evanmiya()
    check_evanmiya(evan)
    asof_txt = f"{as_of:%b} {as_of.day}, {as_of.year}"
    print(f"EvanMiya file: {evan.name} (as of {asof_txt})")
    if "--skip-fetch" not in sys.argv:
        import fetch_torvik; fetch_torvik.main()
    cmd = [sys.executable, "refresh_board.py", str(SITE / "index.html"), str(evan), asof_txt, "--out", str(SITE / "index.new.html")]
    if (TORV / "team_results.csv").exists(): cmd += ["--torvik", str(TORV / "team_results.csv")]
    if (TORV / "players.csv").exists(): cmd += ["--torvik-players", str(TORV / "players.csv")]
    if subprocess.run(cmd, cwd=PIPE).returncode != 0:
        (SITE / "index.new.html").unlink(missing_ok=True)
        sys.exit("The rebuild failed (see the error above). The live board was NOT changed.")
    old_html, new_html = (SITE / "index.html").read_text(encoding="utf-8"), (SITE / "index.new.html").read_text(encoding="utf-8")
    problems = audit(board_data(new_html), board_data(old_html))
    if problems:
        (SITE / "index.new.html").unlink()
        sys.exit("Checks failed; the live board was NOT changed:\n  - " + "\n  - ".join(problems))
    shutil.move(SITE / "index.new.html", SITE / "index.html")
    n = len(board_data(new_html)["seasons"]["2028"]["rows"])
    fetch = json.loads((TORV / "fetch_status.json").read_text()) if (TORV / "fetch_status.json").exists() else {}
    (SITE / "status.json").write_text(json.dumps({"updated": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z",
        "evanmiya_file": evan.name, "data_as_of": asof_txt, "watch_list_players": n, "torvik": fetch}, indent=2))
    print(f"Board updated: {n} players on the watch list, data as of {asof_txt}.")

if __name__ == "__main__":
    main()
