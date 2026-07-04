# The People's Design Library — auto-updating site

A website generated from the [community Google Sheet](https://docs.google.com/spreadsheets/d/13GStMRQfbn5glWVkUPqFtW1oovyKhMDdRKD3m5cstBg/). It rebuilds itself automatically on the **1st and 15th of every month** (roughly every two weeks) via GitHub Actions and is hosted free on GitHub Pages.

## One-time setup (~5 minutes)

1. **Create a GitHub account** (if you don't have one) and create a new **public** repository, e.g. `peoples-design-library`.
2. **Upload everything in this folder** to the repository (drag-and-drop on github.com works: "Add file → Upload files"). Make sure the `.github/workflows/update.yml` file keeps its folder path — if drag-and-drop skips the hidden folder, create the file manually with "Add file → Create new file" and type `.github/workflows/update.yml` as the name, then paste its contents.
3. In the repo, go to **Settings → Pages** and set **Source: GitHub Actions**.
4. Go to the **Actions** tab, open "Rebuild library from Google Sheet", and press **Run workflow** to build the first version.
5. Your site is live at `https://YOUR-USERNAME.github.io/peoples-design-library/` after a minute or two.

That's it. From now on you only edit the spreadsheet — the site refreshes itself twice a month. You can also force an immediate refresh any time from the Actions tab ("Run workflow").

## Requirements

- The Google Sheet must remain **"Anyone with the link can view"** — the robot downloads it through Google's public export link.
- Note: GitHub pauses scheduled workflows on repos with no activity for 60 days. Pushing any small change (or pressing Run workflow) re-enables them.

## Extra features

- **NEW badges**: each rebuild compares against the live site and stamps newly added links with a NEW badge plus a "🆕 New" filter in the toolbar.
- **Shareable links**: every filter combination lives in the URL — copy the address bar to share any drawer, section, or search.
- **🎲 Surprise me**: opens a random resource from whatever is currently filtered.
- **Monthly dead-link report**: on the 3rd of each month a second workflow checks all links and commits `dead-links-report.md` for you to prune the spreadsheet. It never deletes anything automatically — checkers get fooled by bot-blocking sites, so you stay in control.

## How it works

- `build.py` downloads the sheet as a zipped web page (the only export that keeps every hyperlink, including several per cell), extracts every link (including multi-link cells) with its section and subheader, captures the Tips & Tricks sidebars and the Buy Me a Coffee link, and cleans the data (🔥 marks become "staff picks", duplicates removed), and injects it into `shell.html` to produce `index.html`.
- `shell.html` is the site's design template — edit this to change the look.
- `.github/workflows/update.yml` is the schedule + deployment robot.

## If you add or rename a tab in the spreadsheet

Open `build.py` and update the `COLLECTIONS` list at the top (tab name, display name, two-letter code, color). Unknown tabs are skipped with a warning rather than breaking the build. The `MENU` and `COMMUNITY` tabs are intentionally excluded.

## Running locally

```
pip install beautifulsoup4 lxml
python build.py             # downloads the sheet and builds index.html
python build.py export.zip  # or build from a local File > Download > Web page zip
```
