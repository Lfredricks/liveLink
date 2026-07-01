# 🔗 Link Checker

A simple tool that checks whether the links in your spreadsheet still work.
Upload your Excel file, pick the column with the links, and get back a list of
which ones are working and which are broken.

---

## 👉 How to check your links (for everyday use)

**No installing anything. No accounts. Just a webpage.**

### Open the tool
**[Click here to open the Link Checker](https://YOUR-APP-NAME.streamlit.app)**

> _(If the page says it's "waking up," just wait about 30 seconds — that only
> happens the first time after it's been sitting idle.)_

### Then follow these 5 steps

1. **Upload your file.** Click **Browse files** and choose your Excel
   (`.xlsx`) spreadsheet.
2. **Pick the links column.** A dropdown appears listing your column headings.
   Choose the one that contains the links.
3. **Click "Check links."** A progress bar shows how many have been checked.
   For a few thousand links this takes a few minutes — you can leave the tab open.
4. **Read the summary.** You'll see three numbers:
   - ✅ **Working** — the link opened fine
   - ❌ **Broken** — the link is dead, errored, or shows a "page not found"
   - ➖ **Skipped** — the cell was empty or wasn't actually a link
5. **Download your results.** Click **Download results** to get back a single
   spreadsheet — your original file with two new columns, `Status` and `Reason`
   (the reason explains *why* a link was marked broken). **Every broken row is
   shaded red**, so the failures are easy to spot at a glance.

That's it. You can close the page when you're done.

### Tips
- The **Reason** column tells you *why* a link failed (for example
  `HTTP 404 Not Found`, `Timed out`, or `Page loaded but says 'page not found'`).
  A few "broken" results may be false alarms from picky websites — the reason
  helps you spot those, so it's worth a quick glance before deleting anything.
- Empty cells and non-link text are safely ignored (marked **Skipped**), not
  counted as broken.

---

## 🛠️ For the maintainer (one-time setup & updates)

This section is for whoever manages the tool — not needed for everyday use.

### What this is
A small [Streamlit](https://streamlit.io) web app (`app.py`). It reads the
uploaded spreadsheet with `pandas`, checks each link with `requests`, and checks
many links at once so large files finish quickly.

### Deploy it for free on Streamlit Community Cloud
1. Push this repository to GitHub (files: `app.py`, `requirements.txt`,
   `README.md`, `.gitignore`, and the optional `sample_links.xlsx`).
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with
   GitHub.
3. Click **New app**, select this repository, set the main file to **`app.py`**,
   and click **Deploy**.
4. Copy the resulting `https://….streamlit.app` URL and paste it into the
   **"Click here to open the Link Checker"** link near the top of this README.

That's the whole setup. After this, **any change you push to GitHub redeploys
the app automatically** — no extra steps.

### Test it before sending it out
Use the included **`sample_links.xlsx`** — it has a mix of working and broken
links (column heading: `Website`) so you can confirm everything works end to end.

### Common adjustments (all in `app.py`, near the top)
- **`SOFT_404_PHRASES`** — the phrases that flag a "loads but says not found"
  page. Add or remove phrases here (lowercase, one per line) if you see false
  alarms or misses.
- **`REQUEST_TIMEOUT`** — seconds to wait per link before calling it broken
  (default 10).
- **`MAX_WORKERS`** — how many links are checked at the same time (default 30).
  Higher is faster but heavier; 30 is a safe balance.

### Run it locally (optional, for testing changes)
```bash
pip install -r requirements.txt
streamlit run app.py
```
