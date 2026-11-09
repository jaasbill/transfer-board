# Transfer portal board: website + weekly updates

This repository publishes the transfer portal board as a website (GitHub Pages) and keeps it current.
Every Monday, and whenever a new EvanMiya file is uploaded, a GitHub Action:

1. downloads this season's Torvik team ratings and player file (keeps last week's copy if Torvik blocks the download),
2. rebuilds the 2027-28 watch list from the newest file in `inputs/evanmiya/`,
3. checks the result, and only then
4. publishes it. If any check fails, the live site is left exactly as it was.

## One-time setup (about 20 minutes)

1. **GitHub account.** As a student you can get GitHub Pro free through the GitHub Student Developer Pack
   (education.github.com). Pro is needed to publish a site from a *private* repository.
2. **Create a new private repository** named `transfer-board` (no README, no .gitignore).
3. **Upload this folder's contents** on the repository page: "Add file" -> "Upload files", then drag in everything
   inside this folder (`pipeline`, `scripts`, `site`, `inputs`, `requirements.txt`, `README.md`, `.gitignore`).
   Note: your computer may hide the `.github` folder because its name starts with a dot. If it doesn't upload,
   create the workflow by hand: "Add file" -> "Create new file", name it `.github/workflows/update-board.yml`,
   and paste in the contents of that file from this package.
4. **Let the workflow save its results:** Settings -> Actions -> General -> "Workflow permissions" ->
   "Read and write permissions" -> Save.
5. **Turn on the website:** Settings -> Pages -> "Build and deployment" -> Source: **GitHub Actions**.
6. **First run:** Actions tab -> "Update the transfer board" -> "Run workflow". It takes about 5 minutes.
   Your site will be at `https://<your-username>.github.io/transfer-board/`.

## Every week (about 2 minutes)

Download EvanMiya's current player-ratings export and upload it to `inputs/evanmiya/` on GitHub
("Add file" -> "Upload files"). That starts an update right away. The newest file is the one used; delete old ones
whenever you like. The "data as of" date on the board is the day you uploaded the file.

## If something goes wrong

- **Actions tab:** each run shows what happened. A red X means the site was not changed; the log says why
  (for example, a file that isn't the EvanMiya export).
- **`/status.json`** on your site shows when it last updated, which EvanMiya file it used, and whether the Torvik
  downloads worked that week.
- **Torvik blocked?** Download `2027_team_results.csv` and the player file yourself and upload them to
  `inputs/torvik/` as `team_results.csv` and `players.csv`.

## Good to know

- **Who can see it:** a GitHub Pages site can be opened by anyone who has the link, even from a private
  repository. The page tells search engines not to list it. It contains EvanMiya-derived numbers, so share the
  link thoughtfully.
- **Next season:** the pipeline is set up for the 2026-27 season (the 2027-28 watch list). Next fall it will need a
  small update (new season numbers, last season's results added to the models).
- **What's in `pipeline/`:** the code and data the weekly rebuild needs. Past portal cycles live inside the board
  itself and are never changed by updates. The research code (fit tests, backtests) is in the separate code zip.
