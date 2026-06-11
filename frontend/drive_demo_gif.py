"""Record the README demo: ask a question -> chart streams in -> pin it ->
dashboard shows the card. Playwright captures video; convert to GIF after.

Needs backend :8000 + frontend :3000 + seeded demos.
Prints the recorded .webm path on success.
"""

import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:3000"
VIDEO_DIR = Path(__file__).resolve().parent.parent / "docs" / "video"
SIZE = {"width": 1280, "height": 720}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport=SIZE, record_video_dir=str(VIDEO_DIR), record_video_size=SIZE
        )
        page = ctx.new_page()
        page.goto(BASE)
        expect(page.get_by_text("Ask your database anything")).to_be_visible(timeout=15_000)

        page.get_by_label("Active connection").click()
        page.get_by_role("option", name="demo-ecommerce").click()
        page.wait_for_timeout(700)

        box = page.get_by_placeholder("Ask", exact=False)
        box.click()
        # type with a small delay so the question is readable in the GIF
        box.type("Show me total revenue per product category as a chart", delay=30)
        page.wait_for_timeout(400)
        box.press("Enter")

        chart = page.locator("svg.recharts-surface").last
        expect(chart).to_be_visible(timeout=120_000)
        chart.scroll_into_view_if_needed()
        page.wait_for_timeout(2800)  # dwell so the chart reads clearly in the GIF

        page.get_by_role("button", name="Pin", exact=True).last.click()
        page.wait_for_timeout(900)
        page.get_by_role("button", name="Pin card").click()
        expect(page.get_by_text("Pinned to dashboard")).to_be_visible(timeout=10_000)
        page.wait_for_timeout(700)

        page.get_by_role("link", name="Dashboard").click()
        expect(page.locator("svg.recharts-surface").first).to_be_visible(timeout=30_000)
        page.wait_for_timeout(2500)

        video = page.video
        ctx.close()  # flushes the recording to disk
        browser.close()
        print(video.path())


if __name__ == "__main__":
    sys.exit(main())
