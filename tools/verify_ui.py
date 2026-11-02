"""Verify the original LIDMS content, branding and workflows on a temporary local server."""

import json
import os
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PREVIEWS = ROOT.parent / "Documentation" / "Previews"
RESULTS = ROOT / "test-results"
BASE_URL = "http://127.0.0.1:8001"
ADMIN_NAV = [
    "Dashboard",
    "New Registration",
    "Stock Manager",
    "User Details",
    "Post Complaint",
    "Post Stock Request",
    "Reports",
    "FAQs",
    "Contact Us",
]


def database_call(function, *args, **kwargs):
    from django.db import connections

    try:
        return function(*args, **kwargs)
    finally:
        connections.close_all()


def verify_role_workflow(browser, password, checks):
    """Exercise ownership, approval, assignment, resolution and returns through actual forms."""
    from inventory.models import Item

    with ThreadPoolExecutor(max_workers=1) as executor:
        item = executor.submit(database_call, Item.objects.get, asset_code="DEMO-MM-01").result()
    contexts = {}
    pages = {}
    try:
        for role in ["admin", "faculty", "technician"]:
            contexts[role] = browser.new_context(viewport={"width": 1440, "height": 1000})
            pages[role] = contexts[role].new_page()
            page = pages[role]
            page.goto(BASE_URL + "/login/")
            page.get_by_label("Email ID", exact=True).fill(role + "@lidms.example")
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Login", exact=True).click()
            page.wait_for_url("**/dashboard/")
        faculty, admin, technician = (pages[role] for role in ["faculty", "admin", "technician"])
        faculty.goto(BASE_URL + f"/inventory/{item.pk}/request/")
        faculty.get_by_label("Quantity needed").fill("2")
        faculty.get_by_label("Description", exact=False).fill(
            "Browser role workflow: teaching practical"
        )
        faculty.get_by_role("button", name="Post", exact=True).click()
        faculty.wait_for_url("**/requests/")
        request_row = faculty.get_by_role("row").filter(has_text=item.name).first
        request_url = request_row.locator("td").first.get_by_role("link").get_attribute("href")
        request_id = request_url.strip("/").split("/")[-1]
        admin.goto(BASE_URL + request_url + "review/")
        admin.get_by_label("Decision").select_option("approved")
        admin.get_by_role("button", name="Save changes", exact=True).click()
        admin.wait_for_url("**/requests/")
        faculty.goto(BASE_URL + "/updates/")
        faculty.get_by_role("link").filter(has_text=f"Your request #{request_id} for").click()
        assert faculty.url.endswith(request_url)
        assert "2 outstanding" in faculty.locator("main").inner_text()
        assert technician.goto(BASE_URL + request_url + "review/").status == 403
        technician.goto(BASE_URL + f"/issued/{request_id}/return/")
        technician.get_by_label("Quantity returned").fill("1")
        technician.get_by_label("Condition / return note").fill(
            "Checked and returned in working condition"
        )
        technician.get_by_role("button", name="Record return", exact=True).click()
        technician.wait_for_url("**/requests/*/")
        faculty.goto(BASE_URL + request_url)
        assert "1 outstanding" in faculty.locator("main").inner_text()
        checks.append(
            "Faculty equipment request → admin approval → technician partial return → borrower history and notifications"
        )

        subject = "Browser role workflow " + uuid4().hex[:8]
        faculty.goto(BASE_URL + "/complaints/new/")
        faculty.get_by_label("Subject of Complaint").fill(subject)
        faculty.get_by_label("Priority Level").select_option("high")
        faculty.get_by_label("Complaint Type").select_option("hardware")
        faculty.get_by_label("Description", exact=False).fill(
            "Workstation power cable needs replacement."
        )
        faculty.get_by_role("button", name="Post", exact=True).click()
        faculty.wait_for_url("**/complaints/")
        complaint_url = faculty.get_by_role("link", name=subject, exact=True).get_attribute("href")
        admin.goto(BASE_URL + complaint_url)
        admin.get_by_label("Assigned to").select_option(label="demo.technician")
        admin.get_by_label("Status", exact=False).select_option("in_progress")
        admin.get_by_role("button", name="Save update", exact=True).click()
        admin.wait_for_url("**/complaints/*/")
        technician.goto(BASE_URL + "/updates/")
        technician.get_by_role("link").filter(has_text=subject).click()
        technician.get_by_label("Status", exact=False).select_option("resolved")
        technician.get_by_label("Resolution", exact=False).fill(
            "Replaced the cable and checked the workstation."
        )
        technician.get_by_role("button", name="Save update", exact=True).click()
        technician.wait_for_url("**/complaints/*/")
        faculty.goto(BASE_URL + complaint_url)
        assert "Replaced the cable" in faculty.locator("main").inner_text()
        assert faculty.get_by_role("button", name="Save update", exact=True).count() == 0
        faculty.goto(BASE_URL + "/updates/")
        faculty.get_by_role("button", name="Mark all read", exact=True).click()
        faculty.wait_for_url("**/updates/")
        assert faculty.locator(".update-unread").count() == 0
        checks.append(
            "Faculty complaint → admin assignment → technician resolution → private reporter updates and read actions"
        )
    finally:
        for context in contexts.values():
            context.close()


def verify_browser():
    load_dotenv(ROOT / ".env.local")
    password = os.environ["LIDMS_DEMO_PASSWORD"]
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    checks = []
    errors = []
    logo = ROOT / "static/brand/logo.png"
    assert logo.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not (ROOT / "static/brand/robot.svg").exists()
    checks.append(
        "New front-facing 2D robot logo present; retired logo removed from application assets"
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE_URL + "/")
        for section in ["home", "about", "services", "roles", "faq"]:
            assert page.locator("#" + section).count() == 1
        assert page.get_by_role("heading", name="Stock Management", exact=True).count() == 1
        assert page.locator("#team").count() == 0
        assert page.get_by_role("link", name="Team", exact=True).count() == 0
        page.wait_for_function(
            "Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)"
        )
        for image in page.locator("img").all():
            assert image.evaluate("img => img.complete && img.naturalWidth > 0")
            assert "/figma/" not in image.get_attribute("src")
        assert page.locator(".campus-feature").count() == 3
        assert (
            page.get_by_role("link", name="Explore LIDMS", exact=True).get_attribute("href")
            == "#about"
        )
        assert page.locator(".campus-brand img").evaluate_all(
            "images => images.every(image => image.getAttribute('src').endsWith('/brand/logo.png'))"
        )
        assert page.locator("link[rel=icon]").get_attribute("href").endswith("/brand/logo.png")
        assert page.title() == "LIDMS | Lab Information Digitalization and Management Systems"
        assert page.locator(".campus-footer a[href*='github']").count() == 0
        assert (
            page.locator("#dashboard-preview-image")
            .get_attribute("src")
            .endswith("dashboard-admin.jpg")
        )
        assert page.locator(".hero-brand-art img").get_attribute("src").endswith("hero-mascot.png")
        assert page.locator("#contact, .landing-contact-form, main form").count() == 0
        page.locator("[data-preview-open]").click()
        assert page.get_by_role("dialog").is_visible()
        page.get_by_role("button", name="Zoom in", exact=True).click()
        assert page.locator(".dashboard-lightbox-image-area").evaluate(
            "element => element.scrollWidth > element.clientWidth"
        )
        page.keyboard.press("Escape")
        assert not page.get_by_role("dialog").is_visible()
        assert page.locator("#contact, .landing-contact-form, main form").count() == 0
        assert page.get_by_role("link", name="Contact", exact=True).count() == 0
        assert "get in touch" not in page.locator("body").inner_text().lower()
        page.get_by_role("tab", name="Faculty", exact=False).click()
        assert page.locator("#panel-faculty").is_visible()
        page.keyboard.press("ArrowRight")
        assert page.locator("#panel-technician").is_visible()
        page.keyboard.press("Home")
        assert page.locator("#panel-admin").is_visible()
        question = page.locator(".campus-faq-list summary").first
        question.click()
        assert page.locator(".campus-faq-list details").first.get_attribute("open") is not None
        question.click()
        assert page.locator(".visual-orbit, .robot-core, .visual-node").count() == 0
        for link in page.locator(".campus-feature h3 a").all():
            assert link.get_attribute("href").startswith("/")
        for element in page.locator("[data-reveal]").all():
            element.scroll_into_view_if_needed()
            page.wait_for_function(
                "element => element.classList.contains('is-visible')", arg=element.element_handle()
            )
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.screenshot(path=str(PREVIEWS / "home-desktop.png"), full_page=True)
        checks.append(
            "Dark/light landing: new 2D logo, actual dashboard preview and zoom, role tabs, FAQs and simple footer without GitHub or contact details"
        )

        page.goto(BASE_URL + "/login/")
        page.screenshot(path=str(PREVIEWS / "login-desktop.png"), full_page=True)
        page.get_by_role("button", name="Show password", exact=True).click()
        assert page.locator("#id_password").get_attribute("type") == "text"
        page.get_by_role("button", name="Hide password", exact=True).click()
        page.get_by_label("Email ID", exact=True).fill("admin@lidms.example")
        page.get_by_label("Password", exact=True).fill(password)
        page.get_by_role("button", name="Login", exact=True).click()
        page.wait_for_url("**/dashboard/")
        assert page.locator("#navigation nav a").all_text_contents() == ADMIN_NAV
        assert page.locator(".dashboard-metric").count() == 4
        assert page.get_by_role("heading", name="Requests awaiting your decision").is_visible()
        for content in ["Today’s activity", "Live status", "People & access", "Jones Ferdinand"]:
            assert content not in page.locator("body").inner_text()
        page.evaluate("document.fonts.ready")
        assert page.evaluate("document.fonts.check('14px Mulish')")
        page.screenshot(path=str(PREVIEWS / "dashboard-desktop.png"), full_page=True)
        checks.append("Email login, original navigation and live administrator dashboard")

        routes = [
            "stockmanager",
            "inventory",
            "requests",
            "people",
            "registration/new",
            "requests/new",
            "complaints/new",
            "reports",
            "faq",
            "contact",
            "profile",
            "issued",
            "updates",
        ]
        for route in routes:
            response = page.goto(BASE_URL + "/" + route + "/")
            assert response.status == 200, route
            assert page.locator("#navigation nav a").all_text_contents() == ADMIN_NAV
            page.wait_for_function(
                "Array.from(document.querySelectorAll('#navigation img')).every(img => img.complete && img.naturalWidth > 0)"
            )
            for image in page.locator("#navigation img").all():
                assert image.evaluate("img => img.complete && img.naturalWidth > 0")
            if route in ["inventory", "registration/new", "complaints/new", "stockmanager"]:
                name = {
                    "inventory": "inventory",
                    "registration/new": "registration",
                    "complaints/new": "complaint-form",
                    "stockmanager": "stock-manager",
                }[route]
                page.screenshot(path=str(PREVIEWS / (name + "-desktop.png")), full_page=True)
        checks.append("Original project pages plus issued equipment and updates")

        page.goto(BASE_URL + "/requests/new/")
        for label in ["First Name", "Last Name", "Email ID", "Department", "Post"]:
            assert page.get_by_label(label, exact=False).first.is_disabled()
        equipment = "Browser QA new equipment " + uuid4().hex[:8]
        page.get_by_label("Lab Equipment Needed").fill(equipment)
        page.get_by_label("Description", exact=False).fill(
            "Local browser verification of the original equipment request form."
        )
        page.get_by_role("button", name="Post", exact=True).click()
        page.wait_for_url("**/requests/")
        row = page.get_by_role("row").filter(has_text=equipment)
        row.get_by_role("link", name="Review", exact=True).click()
        page.get_by_label("Decision").select_option("approved")
        page.get_by_role("button", name="Save changes", exact=True).click()
        page.wait_for_url("**/requests/")
        assert "approved" in page.get_by_role("row").filter(has_text=equipment).inner_text().lower()
        checks.append("Original free-text equipment request, identity fields and review")

        from inventory.models import Item

        with ThreadPoolExecutor(max_workers=1) as executor:
            item = executor.submit(
                database_call,
                Item.objects.create,
                name="Browser QA returnable equipment " + uuid4().hex[:8],
                asset_code="QA-" + uuid4().hex[:8],
                category="Test instruments",
                laboratory="QA Lab",
                quantity=5,
            ).result()
        page.goto(BASE_URL + f"/inventory/{item.pk}/request/")
        assert page.get_by_label("Lab Equipment Needed").is_disabled()
        page.get_by_label("Quantity needed").fill("2")
        page.get_by_label("Description", exact=False).fill("Local issue and return verification")
        page.get_by_role("button", name="Post", exact=True).click()
        page.wait_for_url("**/requests/")
        page.get_by_role("row").filter(has_text=item.name).get_by_role(
            "link", name="Review", exact=True
        ).click()
        page.get_by_label("Decision").select_option("approved")
        page.get_by_role("button", name="Save changes", exact=True).click()
        page.wait_for_url("**/requests/")
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(database_call, item.refresh_from_db).result()
        assert item.quantity == 3
        page.goto(BASE_URL + "/issued/")
        page.get_by_role("row").filter(has_text=item.name).get_by_role(
            "link", name="Record return", exact=True
        ).click()
        page.get_by_label("Quantity returned").fill("1")
        page.get_by_label("Condition / return note").fill("Checked and working")
        page.get_by_role("button", name="Record return", exact=True).click()
        page.wait_for_url("**/requests/*/")
        assert "1 outstanding" in page.locator("main").inner_text()
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(database_call, item.refresh_from_db).result()
        assert item.quantity == 4
        page.screenshot(path=str(PREVIEWS / "request-return-history.png"), full_page=True)
        checks.append(
            "Existing stock request, approval, partial return and balance/history verified"
        )

        page.goto(BASE_URL + "/reports/")
        page.get_by_role("link", name="Show Stock’s Report", exact=False).click()
        with page.expect_download() as download:
            page.get_by_role("link", name="Download Stock CSV", exact=True).click()
        assert download.value.suggested_filename == "lidms-inventory.csv"
        page.goto(BASE_URL + "/reports/?view=complaints")
        assert page.get_by_role("table").count() == 1
        checks.append("Original stock/complaint report entry points and CSV export")

        for width, height, label in [
            (1024, 768, "tablet-landscape"),
            (768, 1024, "tablet"),
            (390, 844, "mobile"),
            (320, 740, "small-mobile"),
        ]:
            page.set_viewport_size({"width": width, "height": height})
            for route in ["dashboard"] + routes:
                page.goto(BASE_URL + "/" + route + "/")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                    f"Overflow: {label} {route}"
                )
            page.goto(BASE_URL + "/dashboard/")
            page.screenshot(path=str(PREVIEWS / ("dashboard-" + label + ".png")), full_page=True)
            if width < 700:
                page.get_by_role("button", name="Toggle navigation").click()
                assert page.locator("#navigation").is_visible()
                assert page.locator("#navigation nav a").all_text_contents() == ADMIN_NAV
                page.keyboard.press("Escape")
                assert not page.locator("#navigation").is_visible()
            page.goto(BASE_URL + "/")
            if width < 761:
                page.get_by_role("button", name="Open navigation", exact=True).click()
                assert page.locator("#campus-navigation").is_visible()
                page.keyboard.press("Escape")
                assert not page.locator("#campus-navigation").is_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                label + " home"
            )
            for element in page.locator("[data-reveal]").all():
                element.scroll_into_view_if_needed()
                page.wait_for_function(
                    "element => element.classList.contains('is-visible')",
                    arg=element.element_handle(),
                )
            page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            page.screenshot(path=str(PREVIEWS / ("home-" + label + ".png")), full_page=True)
            checks.append(label + ": responsive workspace pages, homepage and mobile navigation")
        context.close()

        verify_role_workflow(browser, password, checks)
        for role in ["faculty", "technician"]:
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.goto(BASE_URL + "/login/")
            page.get_by_label("Email ID", exact=True).fill(role + "@lidms.example")
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Login", exact=True).click()
            page.wait_for_url("**/dashboard/")
            assert page.locator(".dashboard-metric").count() == 4
            page.screenshot(path=str(PREVIEWS / (role + "-dashboard.png")), full_page=True)
            page.goto(BASE_URL + "/updates/")
            assert page.get_by_role("heading", name="Your updates", exact=True).is_visible()
            expected = [
                label for label in ADMIN_NAV if label not in ["New Registration", "User Details"]
            ]
            assert page.locator("#navigation nav a").all_text_contents() == expected
            assert page.goto(BASE_URL + "/people/").status == 403
            context.close()
            checks.append(role + ": original role navigation and administrator access denied")
        assert not errors, errors
        browser.close()
    result = {"passed": len(checks), "checks": checks, "javascript_errors": errors}
    (RESULTS / "browser-verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


def main():
    sys.path.insert(0, str(ROOT))
    load_dotenv(ROOT / ".env.local")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lidms.settings")
    from django.conf import settings
    from django.core.servers.basehttp import WSGIRequestHandler, WSGIServer
    from django.core.wsgi import get_wsgi_application

    if not settings.DEBUG or settings.ON_VERCEL:
        raise RuntimeError("Browser verification requires the local development database.")
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        raise RuntimeError("Browser verification requires local SQLite.")
    # Browser workflows write to an isolated snapshot, keeping the user's preview unchanged.
    with TemporaryDirectory(prefix="lidms-browser-") as temporary:
        database = Path(temporary) / "preview.sqlite3"
        source = sqlite3.connect(str(settings.DATABASES["default"]["NAME"]))
        destination = sqlite3.connect(database)
        source.backup(destination)
        source.close()
        destination.close()
        settings.DATABASES["default"]["NAME"] = database
        server = WSGIServer(("127.0.0.1", 8001), WSGIRequestHandler)
        server.set_app(get_wsgi_application())
        server_thread = threading.Thread(
            target=database_call, args=(server.serve_forever,), daemon=True
        )
        server_thread.start()
        try:
            verify_browser()
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)
            from django.db import connections

            connections.close_all()


if __name__ == "__main__":
    main()
