"""
Renewals journey screenshotter (requires login).

Logs in to the live account, walks the renewals journey exactly as recorded,
and screenshots each screen. On every page it also reads Optimizely's on-page
data layer and flags any page the visitor was bucketed into an A/B test for.

Login details are read from environment variables (never hard-coded). Set:
    RENEWAL_USERNAME   your test account username
    RENEWAL_PASSWORD   your test account password

Saves full-page screenshots into screenshots/renewals/<date>/, writes a per-run
index.html, and rebuilds screenshots/renewals/catalogue.html linking every run.
"""

import os
import json
import html
import datetime as dt
from pathlib import Path
from playwright.sync_api import sync_playwright

# --------------------------------------------------------------------------
# Settings (override with environment variables)
# --------------------------------------------------------------------------
SIGNIN_URL = os.environ.get("RENEWAL_SIGNIN_URL",
                            "https://my.staysure.co.uk/signin")

# Login credentials - provided at run time, NOT stored in this file.
USERNAME = os.environ.get("RENEWAL_USERNAME", "")
PASSWORD = os.environ.get("RENEWAL_PASSWORD", "")

VIEWPORT    = {"width": 1440, "height": 900}
OUTPUT_ROOT = Path("screenshots") / "renewals"   # renewals journey in its own folder

# Set HEADED=1 to watch the browser work (useful for debugging a stuck step).
HEADED = os.environ.get("HEADED") == "1"

# The recording ends by clicking the final SUBMIT button. On the LIVE site that
# would actually complete the renewal and change the test account's state, which
# would break the following week's run. So it is OFF by default. Set
# COMPLETE_RENEWAL=1 only if you deliberately want the script to submit.
COMPLETE_RENEWAL = os.environ.get("COMPLETE_RENEWAL") == "1"

RUN_DATE    = dt.date.today().isoformat()
RUN_DIR     = OUTPUT_ROOT / RUN_DATE


# --------------------------------------------------------------------------
# Optimizely A/B test detection
# Reads Optimizely's on-page data layer to find which experiments the visitor
# is bucketed into on the current page, and which variation they are seeing.
# Returns [] if Optimizely isn't present or hasn't initialised.
# --------------------------------------------------------------------------
OPTIMIZELY_PROBE = """
() => {
  try {
    if (!window.optimizely || typeof window.optimizely.get !== 'function') return [];
    const state = window.optimizely.get('state');
    const data  = window.optimizely.get('data') || {};
    if (!state || typeof state.getVariationMap !== 'function') return [];
    const vmap = state.getVariationMap();
    const out = [];
    Object.keys(vmap || {}).forEach(function (expId) {
      const v = vmap[expId] || {};
      const exp = (data.experiments && data.experiments[expId]) || {};
      out.push({
        experimentId: expId,
        experiment: exp.name || expId,
        variation: v.name || (v.id ? String(v.id) : 'unknown'),
        variationId: v.id || null
      });
    });
    return out;
  } catch (e) { return []; }
}
"""


def read_active_experiments(page):
    """Return a list of active Optimizely experiments/variations on this page."""
    try:
        # give Optimizely a brief moment to load and apply
        page.wait_for_function(
            "() => window.optimizely && typeof window.optimizely.get === 'function'",
            timeout=2500,
        )
    except Exception:
        return []
    try:
        return page.evaluate(OPTIMIZELY_PROBE) or []
    except Exception:
        return []


# --------------------------------------------------------------------------
class Shotter:
    def __init__(self, page, run_dir):
        self.page = page
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.n = 0
        self.manifest = []

    def shot(self, label, section):
        """Take a full-page screenshot and record it in the manifest."""
        self.n += 1
        slug = label.lower().replace(" ", "-").replace("/", "-")
        filename = f"{self.n:02d}_{section}_{slug}.png"
        # let the page settle; don't hang forever on chatty sites
        try:
            self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        self.page.wait_for_timeout(800)
        experiments = read_active_experiments(self.page)
        self.page.screenshot(path=str(self.run_dir / filename), full_page=True)
        self.manifest.append({
            "order": self.n,
            "section": section,
            "label": label,
            "file": filename,
            "url": self.page.url,
            "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
            "experiments": experiments,
        })
        if experiments:
            tags = ", ".join(f"{e['experiment']} -> {e['variation']}" for e in experiments)
            print(f"  captured {filename}   [A/B: {tags}]")
        else:
            print(f"  captured {filename}")


def goto_with_retry(page, url, attempts=3, pause_ms=6000):
    """Open a URL, retrying a few times if the connection is reset/refused."""
    for i in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return
        except Exception as e:
            print(f"  connection attempt {i} of {attempts} failed: {e}")
            if i == attempts:
                raise
            page.wait_for_timeout(pause_ms)


def accept_cookies(page):
    """Click the cookie banner if it's showing; do nothing if it isn't.

    The banner can reappear when moving between pages and sometimes not at all,
    so this is best-effort and never blocks the journey.
    """
    try:
        page.get_by_role("button", name="Accept All Cookies").click(timeout=4000)
    except Exception:
        pass


# --------------------------------------------------------------------------
# THE RENEWALS JOURNEY  (requires login)
# Steps are a literal trace of the recorded live journey. A screenshot is taken
# at each point marked "shotter" in the recording. Login comes from environment
# variables, never hard-coded.
# --------------------------------------------------------------------------
def capture_renewals_journey(shotter):
    page = shotter.page

    # Sign in page - fill credentials, screenshot, then sign in
    goto_with_retry(page, SIGNIN_URL)
    accept_cookies(page)
    page.get_by_role("textbox", name="Username").click()
    page.get_by_role("textbox", name="Username").fill(USERNAME)
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(PASSWORD)
    shotter.shot("Sign in", "renewal")                       # shotter 1
    page.get_by_role("button", name="Sign in").click()
    accept_cookies(page)

    # Account menu pages
    page.get_by_role("link", name="Renewals").click()
    shotter.shot("Renewals", "renewal")                      # shotter 2

    page.get_by_role("link", name="Quotes").click()
    shotter.shot("Quotes", "renewal")                        # shotter 3

    page.get_by_role("link", name="Account Details").click()
    shotter.shot("Account Details", "renewal")               # shotter 4

    page.get_by_role("link", name="Refer a Friend").click()
    shotter.shot("Refer a Friend", "renewal")                # shotter 5

    page.get_by_role("link", name="My Messages").click()
    shotter.shot("My Messages", "renewal")                   # shotter 6

    page.get_by_role("link", name="Policies").click()
    page.get_by_role("button", name="View my policy").click()
    shotter.shot("View my policy", "renewal")                # shotter 7

    page.get_by_role("link", name="My Current Policies").click()
    shotter.shot("My Current Policies", "renewal")           # shotter 8

    page.get_by_role("button", name="My policy documents").click()
    shotter.shot("My policy documents", "renewal")           # shotter 9

    # Into the renewal itself
    page.get_by_role("link", name="My Current Policies").click()
    page.get_by_role("link", name="View renewal").click()
    page.get_by_role("button", name="I agree").click()
    shotter.shot("Renewal summary", "renewal")               # shotter 10

    # Expand each summary section in turn
    page.get_by_text("TravellersParty").click()
    page.get_by_text("Medical conditionsIf any").click()
    page.get_by_text("Policy extrasThere’s no").click()
    page.get_by_text("Contact details lucy583@").click()
    shotter.shot("Renewal sections expanded", "renewal")     # shotter 11

    page.get_by_role("button", name="Don’t want to renew?").click()
    shotter.shot("Don't want to renew", "renewal")           # shotter 12

    page.get_by_test_id("single-type-modal-close-button").click()
    page.get_by_role("button", name="Continue").click()
    shotter.shot("Continue", "renewal")                      # shotter 13

    page.get_by_test_id("confirmation-modal-primary-button").click()
    shotter.shot("Final review", "renewal")                  # shotter 14

    # FINAL SUBMIT - off by default (see COMPLETE_RENEWAL note at top).
    # Submitting on the live site completes the renewal and would change the
    # test account's state, breaking next week's run. The page as it sits ready
    # to submit is already captured above as "Final review".
    if COMPLETE_RENEWAL:
        page.get_by_test_id("renewal-page-submit-button").click()
        shotter.shot("Submitted", "renewal")                 # shotter 15


# --------------------------------------------------------------------------
# Catalogue generation
# --------------------------------------------------------------------------
PAGE_CSS = """
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       margin:0;background:#0f1115;color:#e8eaed}
  header{padding:24px 32px;border-bottom:1px solid #262a33}
  h1{margin:0;font-size:20px}
  .sub{color:#9aa0aa;font-size:13px;margin-top:4px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
        gap:20px;padding:24px 32px}
  figure{margin:0;background:#1a1d24;border:1px solid #262a33;border-radius:10px;
         overflow:hidden}
  figure img{width:100%;display:block;border-bottom:1px solid #262a33}
  figcaption{padding:12px 14px;display:flex;flex-direction:column;gap:4px}
  figcaption strong{font-size:14px}
  figcaption small{color:#7d828c;font-size:11px;word-break:break-all}
  .tag{display:inline-block;font-size:10px;text-transform:uppercase;
       letter-spacing:.5px;padding:2px 8px;border-radius:99px;width:fit-content}
  .tag.quote{background:#16331f;color:#5fd98a}
  .tag.renewal{background:#1c2740;color:#7aa7ff}
  .exp{display:block;font-size:11px;background:#3a2a12;color:#ffcf6b;
       border:1px solid #5c4418;border-radius:6px;padding:4px 8px;margin-top:2px}
  .exp b{color:#ffe3a3}
  .noexp{display:block;font-size:11px;color:#5fd98a;margin-top:2px}
  figure.has-exp{border-color:#5c4418}
  .summary{background:#3a2a12;color:#ffcf6b;border:1px solid #5c4418;
           border-radius:8px;padding:10px 14px;margin:0 32px 0;font-size:13px}
  ul.runs{list-style:none;padding:24px 32px;margin:0}
  ul.runs li{padding:12px 0;border-bottom:1px solid #262a33}
  a{color:#7aa7ff;text-decoration:none}
  a:hover{text-decoration:underline}
"""


def write_run_index(run_dir, manifest, run_date):
    cards = []
    ab_pages = 0
    for item in manifest:
        exps = item.get("experiments") or []
        exp_html = ""
        cls = ""
        if exps:
            ab_pages += 1
            cls = " has-exp"
            for e in exps:
                exp_html += (
                    '<span class="exp">&#9888; A/B test: '
                    f'<b>{html.escape(str(e["experiment"]))}</b> &rarr; '
                    f'{html.escape(str(e["variation"]))}</span>'
                )
        else:
            # mark clean pages too, so it's clear the page was checked
            exp_html = '<span class="noexp">&#10003; No A/B test detected</span>'
        cards.append(
            f'<figure class="card{cls}">'
            f'<a href="{item["file"]}" target="_blank">'
            f'<img src="{item["file"]}" loading="lazy" alt="{html.escape(item["label"])}"></a>'
            '<figcaption>'
            f'<span class="tag {item["section"]}">{item["section"]}</span>'
            f'<strong>{item["order"]:02d}. {html.escape(item["label"])}</strong>'
            f'<small>{html.escape(item["url"])}</small>'
            f'{exp_html}'
            '</figcaption></figure>'
        )
    summary = (
        f"<div class='summary'>A/B check complete: {ab_pages} of {len(manifest)} "
        "screenshots were in an active A/B test"
        + (" &mdash; see the amber flags before using any as a baseline frame."
           if ab_pages else " &mdash; all pages were clean this run.")
        + "</div>"
    )
    doc = (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>Journey screenshots {run_date}</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Journey screenshots</h1>"
        f"<div class='sub'>Run: {run_date} &middot; {len(manifest)} pages &middot; "
        "<a href='../catalogue.html'>&larr; all runs</a></div></header>"
        + summary +
        "<div class='grid'>" + "".join(cards) + "</div>"
    )
    (run_dir / "index.html").write_text(doc, encoding="utf-8")


def write_master_catalogue():
    runs = sorted((p for p in OUTPUT_ROOT.iterdir() if p.is_dir()), reverse=True)
    items = []
    for r in runs:
        count = 0
        mf = r / "manifest.json"
        if mf.exists():
            try:
                count = len(json.loads(mf.read_text()))
            except Exception:
                pass
        items.append(
            f"<li><a href='{r.name}/index.html'>{r.name}</a> "
            f"&mdash; {count} screenshots</li>"
        )
    doc = (
        "<!doctype html><meta charset='utf-8'><title>Screenshot catalogue</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Screenshot catalogue</h1>"
        f"<div class='sub'>{len(runs)} weekly runs</div></header>"
        "<ul class='runs'>" + "".join(items) + "</ul>"
    )
    (OUTPUT_ROOT / "catalogue.html").write_text(doc, encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    if not (USERNAME and PASSWORD):
        print("ERROR: login not set. Run with the test credentials, e.g.:\n"
              "  RENEWAL_USERNAME='you@example.com' RENEWAL_PASSWORD='secret' "
              "python3 renewals_journey.py")
        return

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not HEADED,
            slow_mo=500 if HEADED else 0,  # slow down so you can watch each step
        )
        context = browser.new_context(
            viewport=VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        shotter = Shotter(page, RUN_DIR)

        print("Capturing renewals journey...")
        try:
            capture_renewals_journey(shotter)
        except Exception as e:
            print(f"  renewals journey error: {e}")
            # capture whatever page we got stuck on, so we can see why
            try:
                shotter.shot("STUCK - where it stopped", "renewal")
            except Exception:
                pass

        browser.close()

    (RUN_DIR / "manifest.json").write_text(
        json.dumps(shotter.manifest, indent=2), encoding="utf-8"
    )
    write_run_index(RUN_DIR, shotter.manifest, RUN_DATE)
    write_master_catalogue()
    print(f"\nDone. {len(shotter.manifest)} screenshots in {RUN_DIR}")
    print(f"Open {OUTPUT_ROOT / 'catalogue.html'} to browse.")


if __name__ == "__main__":
    main()
