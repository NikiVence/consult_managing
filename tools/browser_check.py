"""End-to-end checks and real screenshots of the local application."""
import json
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import dotenv_values
from playwright.sync_api import expect, sync_playwright

root = Path(__file__).resolve().parent.parent
out = root / "docs/framework_pr5_7"
(out / "images").mkdir(parents=True, exist_ok=True)
secrets = dotenv_values(root / ".env")
base = "http://127.0.0.1:8088"
errors = []
checks = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=True,
        args=["--no-proxy-server"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1080}, timezone_id="Europe/Moscow")
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_default_timeout(15000)

    def shot(name):
        page.screenshot(path=str(out / "images" / (name + ".png")), full_page=True)

    def sign_in(username, key):
        page.locator("#login-open").click()
        page.locator('#auth-form input[name="username"]').fill(username)
        page.locator('#auth-form input[name="password"]').fill(secrets[key])
        page.locator("#auth-submit").click()
        expect(page.locator("#signed-in")).to_be_visible()
        expect(page.locator("#auth-dialog")).not_to_be_visible()

    page.goto(base)
    expect(page.locator(".card").first).to_be_visible()
    shot("01_schedule")
    page.locator("#search").fill("БАЗЫ")
    expect(page.locator(".card")).to_have_count(1)
    expect(page.locator(".card h3")).to_have_text("Базы данных и ORM")
    page.locator("#search").fill("неттакойтемы927")
    expect(page.locator("#schedule .empty")).to_be_visible()
    page.locator("#search").fill("")
    expect(page.locator(".card").first).to_be_visible()
    checks.append("Поиск, кириллица и пустой результат")
    sign_in("student", "DEMO_STUDENT_PASSWORD")
    expect(page.locator("#account-role")).to_have_text("Студент")
    page.locator(".card button").filter(has_text="Записаться").first.click()
    page.locator("#duration").select_option("45")
    page.locator("#booking-submit").click()
    expect(page.locator("#booking-dialog")).not_to_be_visible()
    expect(page.locator("#notice")).to_contain_text("подтверждена")
    page.locator("#nav-bookings").click()
    row = page.locator(".booking-row").filter(has=page.locator("button", has_text="Отменить запись")).first
    expect(row).to_be_visible()
    shot("02_student_bookings")
    detail_url = row.locator("a").get_attribute("href")
    page.goto(base + detail_url)
    expect(page.locator("#booking-status")).to_have_text("Подтверждена")
    shot("03_status_confirmed")
    page.goto(base)
    page.locator("#nav-bookings").click()
    page.once("dialog", lambda dialog: dialog.accept())
    row = page.locator(".booking-row").filter(has=page.locator(f'a[href="{detail_url}"]'))
    row.get_by_role("button", name="Отменить запись").click()
    expect(page.locator("#notice")).to_contain_text("отменена")
    page.goto(base + detail_url)
    expect(page.locator("#booking-status")).to_have_text("Отменена")
    shot("04_status_cancelled")
    checks.append("Вход, запись на 45 минут, серверный шаблон if и отмена")
    page.goto(base)
    expect(page.locator("#logout")).to_be_visible()
    page.locator("#logout").click()
    expect(page.locator("#login-open")).to_be_visible()
    sign_in("teacher", "DEMO_TEACHER_PASSWORD")
    page.locator("#create-open").click()
    page.locator('#create-form input[name="topic"]').fill("Разбор REST API · практика")
    when = (datetime.now() + timedelta(days=7)).replace(second=0, microsecond=0)
    page.locator('#create-form input[name="starts_at"]').fill(when.isoformat(timespec="minutes"))
    page.locator('#create-form input[name="location"]').fill("Онлайн")
    page.locator("#create-submit").click()
    expect(page.locator("#create-dialog")).not_to_be_visible()
    expect(page.locator("#notice")).to_contain_text("добавлена")
    shot("05_teacher")
    checks.append("Преподаватель создаёт консультацию через форму и API")
    page.goto(base + "/api/docs/")
    expect(page.get_by_role("heading", name="API консультаций")).to_be_visible()
    shot("06_api_docs")
    mobile = browser.new_context(viewport={"width":390,"height":844}, is_mobile=True, device_scale_factor=1)
    phone = mobile.new_page()
    phone.goto(base)
    expect(phone.locator(".card").first).to_be_visible()
    assert phone.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal overflow"
    phone.screenshot(path=str(out / "images/07_mobile.png"), full_page=True)
    checks.append("Мобильный интерфейс 390px без горизонтальной прокрутки")
    mobile.close()
    browser.close()

assert not errors, errors
result = {"checks": checks, "javascript_errors": errors, "status": "passed"}
(out / "evidence/browser.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
