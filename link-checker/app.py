"""
Link Checker — a simple web app that checks whether the links in a
spreadsheet are still working.

For non-technical users: you don't need to read or edit this file.
Just open the web app (see the README) and follow the steps on screen.

For maintainers: the only thing you'll likely ever want to change is the
SOFT_404_PHRASES list just below. See the comment there.
"""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# EDIT ME IF NEEDED:
# A link can return "200 OK" but still show a "page not found" message.
# These are the phrases we look for in the page text to catch those cases.
# Add or remove phrases here (keep them lowercase, one per line).
# ---------------------------------------------------------------------------
SOFT_404_PHRASES = [
    "page not found",
    "404 not found",
    "404 error",
    "not found",
    "no longer exists",
    "no longer available",
    "page you requested",
    "page cannot be found",
    "page doesn't exist",
    "page does not exist",
    "sorry, we couldn't find",
    "this page isn't available",
]

# How each link is checked. These are safe defaults; you rarely need to touch them.
REQUEST_TIMEOUT = 10          # seconds to wait for a single link before giving up
MAX_WORKERS = 30              # how many links to check at the same time
BYTES_TO_SCAN = 20000         # how much of the page text to scan for soft-404 phrases
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def normalize_url(raw):
    """Return a clean URL string, or None if the cell isn't a usable link."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None
    # Add a scheme if the user pasted "example.com" without http(s)://
    if not text.lower().startswith(("http://", "https://")):
        text = "https://" + text
    # A bare "https://" or something with no dot isn't a real web address
    if "." not in text.split("://", 1)[-1]:
        return None
    return text


def check_one(url):
    """
    Check a single URL. Returns (status, reason).
    status is "Working" or "Broken".
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        # Try a lightweight HEAD first (fast — no page body downloaded).
        resp = requests.head(
            url, allow_redirects=True, timeout=REQUEST_TIMEOUT, headers=headers
        )
        # Some servers don't support HEAD; fall back to GET.
        if resp.status_code >= 400 or resp.status_code == 405:
            resp = requests.get(
                url, allow_redirects=True, timeout=REQUEST_TIMEOUT,
                headers=headers, stream=True,
            )
    except requests.exceptions.SSLError:
        return "Broken", "Security certificate error"
    except requests.exceptions.ConnectionError:
        return "Broken", "Could not connect (dead domain or network error)"
    except requests.exceptions.Timeout:
        return "Broken", f"Timed out after {REQUEST_TIMEOUT}s"
    except requests.exceptions.RequestException as exc:
        return "Broken", f"Request error: {exc.__class__.__name__}"

    code = resp.status_code
    if code >= 400:
        return "Broken", f"HTTP {code} {_reason_phrase(resp)}"

    # We have a 2xx/3xx-followed-to-2xx response. Scan the page text for
    # "not found" style messages (soft-404s) — but only for pages that look
    # like HTML, so we don't scan PDFs/images.
    content_type = resp.headers.get("Content-Type", "").lower()
    if "html" in content_type or content_type == "":
        try:
            if resp.request.method == "HEAD":
                # HEAD has no body; do a small GET to read the page text.
                resp = requests.get(
                    url, allow_redirects=True, timeout=REQUEST_TIMEOUT,
                    headers=headers, stream=True,
                )
            body = resp.raw.read(BYTES_TO_SCAN, decode_content=True) if resp.raw else b""
            text = body.decode(resp.encoding or "utf-8", errors="ignore").lower()
            for phrase in SOFT_404_PHRASES:
                if phrase in text:
                    return "Broken", f"Page loaded but says '{phrase}'"
        except requests.exceptions.RequestException:
            # If we can't read the body, don't fail the link on that alone —
            # the status code was fine.
            pass

    return "Working", f"OK (HTTP {code})"


def _reason_phrase(resp):
    try:
        return resp.reason or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# The web page
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Link Checker", page_icon="🔗", layout="centered")

st.title("🔗 Link Checker")
st.write(
    "Upload your spreadsheet, choose the column that holds the links, "
    "and click **Check links**. When it finishes, download your results."
)

uploaded = st.file_uploader("Step 1 — Upload your Excel file (.xlsx)", type=["xlsx"])

if uploaded is not None:
    try:
        df = pd.read_excel(uploaded, engine="openpyxl")
    except Exception as exc:
        st.error(f"Sorry, that file couldn't be read. ({exc})")
        st.stop()

    if df.empty or len(df.columns) == 0:
        st.error("That spreadsheet appears to be empty.")
        st.stop()

    st.success(f"Loaded {len(df):,} rows.")

    column = st.selectbox(
        "Step 2 — Which column has the links?", options=list(df.columns)
    )

    if st.button("Step 3 — Check links", type="primary"):
        # Build the list of URLs to check, remembering blanks/non-URLs.
        raw_values = df[column].tolist()
        normalized = [normalize_url(v) for v in raw_values]

        # Check each unique URL only once (big speedup on files with repeats).
        unique_urls = sorted({u for u in normalized if u})
        results_cache = {}

        if not unique_urls:
            st.warning("No usable links were found in that column.")
            st.stop()

        st.write(f"Checking {len(unique_urls):,} unique links…")
        progress = st.progress(0.0)
        status_line = st.empty()
        done = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_to_url = {pool.submit(check_one, u): u for u in unique_urls}
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    results_cache[url] = future.result()
                except Exception as exc:
                    results_cache[url] = ("Broken", f"Unexpected error: {exc}")
                done += 1
                progress.progress(done / len(unique_urls))
                status_line.write(f"Checked {done:,} of {len(unique_urls):,}")

        # Map results back to every row (including blanks/duplicates).
        statuses, reasons = [], []
        for url in normalized:
            if url is None:
                statuses.append("Skipped")
                reasons.append("Not a link")
            else:
                s, r = results_cache[url]
                statuses.append(s)
                reasons.append(r)

        annotated = df.copy()
        annotated["Status"] = statuses
        annotated["Reason"] = reasons

        broken_mask = [s == "Broken" for s in statuses]
        broken = pd.DataFrame(
            {
                "Row": [i + 2 for i, b in enumerate(broken_mask) if b],  # +2 = header + 1-based
                "URL": [raw_values[i] for i, b in enumerate(broken_mask) if b],
                "Reason": [reasons[i] for i, b in enumerate(broken_mask) if b],
            }
        )

        working_count = statuses.count("Working")
        broken_count = statuses.count("Broken")
        skipped_count = statuses.count("Skipped")

        st.subheader("Results")
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Working", f"{working_count:,}")
        c2.metric("❌ Broken", f"{broken_count:,}")
        c3.metric("➖ Skipped", f"{skipped_count:,}")

        if broken_count:
            st.write("Broken links:")
            st.dataframe(broken, use_container_width=True)
        else:
            st.success("Every link is working. 🎉")

        # Build downloadable Excel files in memory.
        annotated_bytes = io.BytesIO()
        with pd.ExcelWriter(annotated_bytes, engine="openpyxl") as writer:
            annotated.to_excel(writer, index=False)
        annotated_bytes.seek(0)

        broken_bytes = io.BytesIO()
        with pd.ExcelWriter(broken_bytes, engine="openpyxl") as writer:
            broken.to_excel(writer, index=False)
        broken_bytes.seek(0)

        st.download_button(
            "⬇️ Download full results (annotated copy)",
            data=annotated_bytes,
            file_name="link_check_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "⬇️ Download broken links only",
            data=broken_bytes,
            file_name="broken_links.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
