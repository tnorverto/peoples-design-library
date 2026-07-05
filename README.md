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

## Security notes

**The Firebase apiKey in config.json is not a secret.** GitHub's scanner flags any Google-looking key, but Firebase web API keys are public by design — they ship in every visitor's browser and only *identify* the project. Real security lives in the database rules and the authorized-domains list. You can close the GitHub alert: repo → Security → Secret scanning → the alert → **Close as → False positive**.

That said, two cheap hardening steps are worth doing once:

1. **Restrict the API key** (limits what it can be used for even in theory): console.cloud.google.com → select the project → APIs & Services → Credentials → click the "Browser key (auto created by Firebase)" → under *Application restrictions* choose **Websites** and add `tnorverto.github.io/*` → under *API restrictions* choose **Restrict key** and select *Identity Toolkit API*, *Token Service API*, and *Firebase Installations API* → Save.
2. The site ships a **Content-Security-Policy** meta tag allowlisting exactly the external services it uses (Firebase, GoatCounter, Google Fonts, favicon/screenshot services). If you ever add a new external service to shell.html, add its origin to the CSP too or the browser will block it.

Known accepted risk: the public vote counters have no rate limiting (the rules only constrain votes to ±1 steps), so a determined script could inflate a count. For a community catalog this is a reasonable trade; Firebase App Check could close it later if it ever becomes a problem.

## Your settings: config.json

Your personal settings live in `config.json` (not in shell.html), so updating the site's code never erases them:

```json
{
  "goatcounter": "peoplesdesignlibrary",
  "votes_db": "https://yourproject-default-rtdb.europe-west1.firebasedatabase.app"
}
```

- `goatcounter`: your GoatCounter code (empty string disables the visit counter)
- `votes_db`: your Firebase Realtime Database URL (leave the placeholder or empty to hide vote buttons)

## Visitor counter (2 minutes)

The masthead can show total visits and visits today via [GoatCounter](https://www.goatcounter.com) (free, open-source, privacy-friendly — no cookie banner needed):

1. Sign up at goatcounter.com and set your **Code** to `peoplesdesignlibrary` (or anything you like).
2. If you chose a different code, change `goatcounter` in `config.json`.
3. Push and rebuild. Counters start from zero on setup day.

The counter deliberately doesn't run on localhost or in preview sandboxes, so testing doesn't inflate your numbers. A literal "people online right now" counter isn't possible on a static host without adding a realtime backend — visits-today is the honest static-site equivalent.

## Google sign-in & favorites

Visitors can sign in with Google and save favorites (a ❤ on every card, plus a "❤ Mine" filter). Setup: enable **Authentication → Sign-in method → Google** in Firebase, add your github.io domain under **Authentication → Settings → Authorized domains**, and put your web app config under `"firebase"` in `config.json`. Then make sure your **Realtime Database rules** are the combined version below (votes + private per-user favorites):

```json
{
  "rules": {
    "votes": {
      ".read": true,
      "$id": {
        ".write": true,
        ".validate": "newData.isNumber() && ((!data.exists() && (newData.val() === 1 || newData.val() === -1)) || ((newData.val() - data.val()) >= -2 && (newData.val() - data.val()) <= 2 && newData.val() !== data.val()))"
      }
    },
    "favs": {
      "$uid": {
        ".read": "auth !== null && auth.uid === $uid",
        ".write": "auth !== null && auth.uid === $uid"
      }
    }
  }
}
```

Favorites are private: each user can only read and write their own list.

## "Useful" upvotes (5 minutes)

Visitors can upvote links they found useful. This needs a tiny free database:

1. Go to console.firebase.google.com → **Add project** (any name, Analytics off).
2. In the left menu: **Build → Realtime Database → Create database** (any region, **locked mode**).
3. Open the **Rules** tab, replace everything with the following, and Publish:

```json
{
  "rules": {
    "votes": {
      ".read": true,
      "$id": {
        ".write": true,
        ".validate": "newData.isNumber() && ((!data.exists() && (newData.val() === 1 || newData.val() === -1)) || ((newData.val() - data.val()) >= -2 && (newData.val() - data.val()) <= 2 && newData.val() !== data.val()))"
      }
    }
  }
}
```

   (These rules only allow small ±1/±2 steps — voting, un-voting, and switching between up and down; totals can go negative but nobody can wipe or forge them.)
4. Copy the database URL shown at the top of the Data tab (looks like `https://yourproject-default-rtdb.europe-west1.firebasedatabase.app`).
5. Paste the URL into `votes_db` in `config.json`. Push and rebuild.

Buttons stay hidden until VOTES_DB is set. Visitors vote ▲ or ▼ per link, can undo by clicking again, or switch sides (remembered locally). Counts can go negative. A "Sort: Most useful" option appears in the toolbar so visitors can surface the community's top links in any category. Firebase's free tier comfortably covers hundreds of thousands of votes and reads per month.

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
