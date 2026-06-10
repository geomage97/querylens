"""Phase 4 verification: charts in chat, pin to dashboard on both engines,
dashboard refresh. Captures chat-chart.png and dashboard.png.

Needs backend :8000 + frontend :3000 + both demo connections.
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:3000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
ANSWER_TIMEOUT = 120_000


def pick_connection(page, name: str):
    page.get_by_label("Active connection").click()
    page.get_by_role("option", name=name).click()
    page.wait_for_timeout(300)


def ask(page, question: str):
    box = page.get_by_placeholder("Ask", exact=False)
    box.fill(question)
    box.press("Enter")
    expect(page.get_by_text("Query inspector").last).to_be_visible(timeout=ANSWER_TIMEOUT)
    page.wait_for_timeout(600)


def pin(page, title: str):
    page.get_by_role("button", name="Pin", exact=True).last.click()
    field = page.get_by_label("Card title")
    field.fill(title)
    page.get_by_role("button", name="Pin card").click()
    expect(page.get_by_text("Pinned to dashboard")).to_be_visible(timeout=10_000)
    page.wait_for_timeout(400)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE)
        expect(page.get_by_text("Ask your database anything")).to_be_visible(timeout=15_000)

        # -- Chart in chat (MongoDB) + pin --
        pick_connection(page, "demo-ecommerce")
        ask(page, "Show me total revenue per product category as a chart")
        expect(page.locator("svg.recharts-surface").last).to_be_visible(timeout=10_000)
        page.screenshot(path=str(OUT / "chat-chart.png"))
        print("ok chat-chart.png (recharts svg rendered)")
        pin(page, "Revenue by category")
        print("ok pinned mongo card")

        # -- Chart on PostgreSQL + pin --
        page.get_by_role("button", name="New chat").click()
        pick_connection(page, "demo-hr")
        ask(page, "How many employees were hired each year? Show it as a trend.")
        pin(page, "Hiring trend")
        print("ok pinned postgres card")

        # -- Dashboard: cards render with fresh data, refresh works --
        page.goto(f"{BASE}/dashboard")
        expect(page.get_by_text("Revenue by category")).to_be_visible(timeout=30_000)
        expect(page.get_by_text("Hiring trend")).to_be_visible(timeout=30_000)
        expect(page.locator("svg.recharts-surface").first).to_be_visible(timeout=30_000)
        expect(page.get_by_text(re.compile(r"refreshed \d"))).to_have_count(2, timeout=30_000)

        page.get_by_label("Refresh card").first.click()
        page.wait_for_timeout(1500)  # refetch round-trip
        expect(page.locator("svg.recharts-surface").first).to_be_visible(timeout=15_000)
        page.screenshot(path=str(OUT / "dashboard.png"))
        print("ok dashboard.png (2 cards, refresh exercised)")

        browser.close()
    print("phase 4 drive complete ->", OUT)


if __name__ == "__main__":
    sys.exit(main())
