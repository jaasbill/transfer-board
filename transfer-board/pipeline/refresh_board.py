"""Refresh the 2027-28 watch list on the board from a new EvanMiya player-ratings export.

    python refresh_board.py transfer_portal_board.html player-ratings.csv "Dec 1, 2026"
    python refresh_board.py transfer_portal_board.html player-ratings.csv "Dec 1, 2026" --torvik 2027_team_results.csv

--torvik (optional): Torvik's current-season team ratings, used for team strength instead of last season's KenPom.
--torvik-players (optional): Torvik's current-season player file (getadvstats.php?year=2027&csv=1), for newcomers' hometowns and heights.

Writes transfer_portal_board.html with the watch list rebuilt (every past season is kept as is).
Run run_all.py once first, so the model files it needs (pools.pkl, links.pkl, tv_feat.pkl) exist."""
import sys, json, subprocess
args = sys.argv[1:]
torvik = args[args.index("--torvik") + 1] if "--torvik" in args else None
torvik_players = args[args.index("--torvik-players") + 1] if "--torvik-players" in args else None
out = args[args.index("--out") + 1] if "--out" in args else "transfer_portal_board.html"
board, ratings, asof = args[0], args[1], args[2]
h = open(board, encoding="utf-8").read()
tag = '<script id="data" type="application/json">'; i = h.index(tag) + len(tag); j = h.index("</script>", i)
template = h[:i] + "__DATA__" + h[j:]
D = json.loads(h[i:j].replace("<\\/", "</"))
json.dump(D, open("page_data.json", "w"), separators=(",", ":"))
subprocess.run([sys.executable, "build_watchlist.py", ratings, asof, torvik or "-"] + ([torvik_players] if torvik_players else []), check=True)
W = json.load(open("watch_2028.json"))
for s, block in D["seasons"].items():            # keep every season's rows the same width as the field list
    for row in block["rows"]: row.extend([None] * (len(W["fields"]) - len(row)))
D["fields"] = W["fields"]
D["seasons"]["2028"] = W["season"]; D["teams"]["2028"] = W["teams"]; D["choice"]["2028"] = W["choice"]; D["rosters"]["2028"] = W["rosters"]
js = json.dumps(D, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
open(out, "w", encoding="utf-8").write(template.replace("__DATA__", js))
print(f"Board written to {out}: watch list has {len(W['season']['rows'])} players, data as of {asof}.")
