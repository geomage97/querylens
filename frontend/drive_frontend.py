"""Drive the running QueryLens frontend end-to-end and capture screenshots.

Needs: backend on :8000, frontend on :3000, both demo connections live.
Usage: python drive_frontend.py
"""

import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:3000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

ANSWER_TIMEOUT = 120_000


def pick_connection(page, name: str):
    page.get_by_label("Active connection").click()
    page.get_by_role("option", name=name).click()
    page.wait_for_timeout(300)


def ask(page, question: str):
    box = page.get_by_placeholder("Ask", exact=False)
    box.fill(question)
    box.press("Enter")
    # The query inspector only appears once the final result event lands
    expect(page.get_by_text("Query inspector").last).to_be_visible(timeout=ANSWER_TIMEOUT)
    page.wait_for_timeout(500)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE)
        expect(page.get_by_text("Ask your database anything")).to_be_visible(timeout=15_000)

        # -- Chat on MongoDB --
        pick_connection(page, "demo-ecommerce")
        ask(page, "What are the top 5 product categories by revenue?")
        page.get_by_text("Query inspector").last.click()  # open the inspector
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "chat-mongodb.png"))
        print("ok chat-mongodb.png")

        # -- Chat on PostgreSQL --
        page.get_by_role("button", name="New chat").click()
        pick_connection(page, "demo-hr")
        ask(page, "What is the average salary per department?")
        page.get_by_text("Query inspector").last.click()
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "chat-postgresql.png"))
        print("ok chat-postgresql.png")

        # -- Connections page --
        page.goto(f"{BASE}/connections")
        expect(page.get_by_text("demo-ecommerce")).to_be_visible(timeout=15_000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "connections.png"))
        print("ok connections.png")

        # -- Schema explorer (demo-hr is the active connection) --
        import re
        page.goto(f"{BASE}/schema")
        expect(
            page.get_by_role("button", name=re.compile(r"^employees ")),
        ).to_be_visible(timeout=30_000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "schema.png"))
        print("ok schema.png")

        browser.close()
    print("all screenshots captured ->", OUT)


if __name__ == "__main__":
    sys.exit(main())
