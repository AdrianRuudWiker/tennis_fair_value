"""
capture_ui.py
Take a screenshot of the running Streamlit app for the README.

Prerequisites (one-time, not in requirements.txt because this is a
maintenance-only utility):
    pip install playwright
    playwright install chromium

Then, with the Streamlit server already running:
    python scripts/capture_ui.py            # default http://localhost:8501
    python scripts/capture_ui.py 8502       # override port

Output: docs/ui-screenshot.png (full-page, 1500px wide).
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main(port: int = 8501):
    url = f"http://localhost:{port}/"
    out = Path(__file__).parent.parent / "docs" / "ui-screenshot.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1500, "height": 2000})
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        # Extra settle time — Streamlit keeps reflowing as widgets mount.
        page.wait_for_timeout(2500)
        page.screenshot(path=str(out), full_page=True)
        browser.close()

    print(f"Saved {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8501
    main(port)
