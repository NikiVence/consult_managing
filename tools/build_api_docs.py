"""Generate a portable OpenAPI 3 document and its human-readable reference."""

import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
schema = {
    "openapi": "3.0.3",
    "info": {
        "title": "Консультант API",
        "version": "1.0.0",
        "description": "Session authentication; obtain CSRF token before any POST. Dates use ISO 8601 with timezone.",
    },
    "servers": [{"url": "/"}],
    "paths": {},
    "components": {
        "securitySchemes": {
            "session": {"type": "apiKey", "in": "cookie", "name": "sessionid"},
            "csrf": {"type": "apiKey", "in": "header", "name": "X-CSRFToken"},
        }
    },
}
operations = [
    ("/api/csrf/", "get", "Получить CSRF-токен", None, False, 200),
    (
        "/api/auth/register/",
        "post",
        "Регистрация студента",
        {"username": "string", "name": "string", "password": "string"},
        False,
        201,
    ),
    (
        "/api/auth/login/",
        "post",
        "Вход и создание сессии",
        {"username": "string", "password": "string"},
        False,
        200,
    ),
    ("/api/auth/logout/", "post", "Выход из аккаунта", {}, True, 200),
    ("/api/auth/me/", "get", "Текущий пользователь или null", None, False, 200),
    (
        "/api/consultations/",
        "get",
        "Будущие консультации: до 200, по дате",
        None,
        False,
        200,
    ),
    (
        "/api/consultations/",
        "post",
        "Создать свой слот (только преподаватель)",
        {"topic": "string", "location": "string", "starts_at": "string"},
        True,
        201,
    ),
    (
        "/api/bookings/",
        "get",
        "Свои записи; преподаватель видит записи к себе (до 200)",
        None,
        True,
        200,
    ),
    (
        "/api/bookings/",
        "post",
        "Записаться (только студент)",
        {"consultation_id": "integer", "duration_minutes": "integer"},
        True,
        201,
    ),
    (
        "/api/bookings/{booking_id}/cancel/",
        "post",
        "Отменить свою запись; повторная отмена безопасна",
        {},
        True,
        200,
    ),
    ("/health/live/", "get", "Процесс отвечает", None, False, 200),
    ("/health/ready/", "get", "Проверить БД и кэш", None, False, 200),
]
rows = []
for path, method, title, body, auth, status in operations:
    op = {
        "summary": title,
        "responses": {
            str(status): {
                "description": "Успешно",
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "400": {"description": "Ошибка полей или JSON"},
            "403": {"description": "CSRF или недостаточно прав"},
            "409": {"description": "Слот или участник занят, либо дубликат"},
            "429": {"description": "Слишком много попыток входа/регистрации"},
            "503": {"description": "Сервис не готов"},
        },
    }
    if auth:
        op["responses"]["401"] = {"description": "Необходим вход"}
    requirements = {}
    if auth:
        requirements["session"] = []
    if method == "post":
        requirements["csrf"] = []
    if requirements:
        op["security"] = [requirements]
    if body is not None:
        props = {name: {"type": kind} for name, kind in body.items()}
        if "starts_at" in props:
            props["starts_at"]["format"] = "date-time"
        if "password" in props:
            props["password"].update({"format": "password", "maxLength": 128})
        if "duration_minutes" in props:
            props["duration_minutes"].update({"minimum": 15, "maximum": 90})
        op["requestBody"] = {
            "required": bool(body),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    }
                }
            },
        }
    if "{booking_id}" in path:
        op["parameters"] = [
            {
                "name": "booking_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer", "minimum": 1},
            }
        ]
    if path == "/api/consultations/" and method == "get":
        op["parameters"] = [
            {"name": "q", "in": "query", "schema": {"type": "string", "maxLength": 100}}
        ]
    schema["paths"].setdefault(path, {})[method] = op
    rows.append(
        f"<tr><td><b>{method.upper()}</b></td><td><code>{path}</code></td><td>{title}</td></tr>"
    )
(root / "webapp/openapi.json").write_text(
    json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
html = """{% load static %}<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Консультант — API</title><link rel="stylesheet" href="{% static 'app.css' %}"></head><body><main class="docs"><a href="/">← К расписанию</a><h1>API консультаций</h1><p>Версия 1.0 · JSON · UTF-8</p><p>Вход создаёт серверную сессию с cookie <code>sessionid</code>. Перед POST получите <code>/api/csrf/</code> и передайте <code>csrfToken</code> в заголовке <code>X-CSRFToken</code>. После входа токен меняется — получите новый.</p><p>Длительность — целое число 15–90. Время — ISO 8601 с часовым поясом. Один слот принимает одну активную запись. Пересечения встреч студента или преподавателя запрещены.</p><p>Регистрация создаёт только студента. Преподавателя назначает администратор. Доступ к записям ограничен участниками. Кэш списка: 15 секунд, сброс после изменения; доступность повторно проверяется при бронировании.</p><p><a href="/api/openapi.json">Скачать OpenAPI 3.0 JSON</a></p><table><thead><tr><th>Метод</th><th>Путь</th><th>Назначение</th></tr></thead><tbody>ROWS</tbody></table><h2>Пример записи</h2><pre><code>POST /api/bookings/
Content-Type: application/json
X-CSRFToken: токен из /api/csrf/

{"consultation_id": 1, "duration_minutes": 45}</code></pre><p>Успех: 201 с объектом записи. Ошибки: 400 — поля; 401 — вход; 403 — права/CSRF; 404 — объект не найден; 409 — конфликт; 415 — тип содержимого; 429 — лимит попыток; 503 — сервис недоступен. Формат: <code>{"error": "Сообщение"}</code>.</p></main></body></html>"""
(root / "webapp/templates/api_docs.html").write_text(
    html.replace("ROWS", "\n".join(rows)), encoding="utf-8"
)
print("OpenAPI JSON and API reference generated.")
