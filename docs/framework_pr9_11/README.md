# Практические работы 9–11: система управления консультациями

Студент: Алиев Никита, ЭФБО-01-24. Дисциплина: «Технологии разработки приложений на базе фреймворков».

## Материалы

- [Отчёт ПР9: модели и ORM](report_pr9.md)
- [Отчёт ПР10: админка и запросы](report_pr10.md)
- [Отчёт ПР11: формы](report_pr11.md)
- [Памятка для защиты](defense.md)
- Скриншоты работающего приложения: каталог `images`.

## Запуск из корня проекта

```powershell
cd D:\consult_managing
.\tools\run_python.ps1 webapp/manage.py migrate
.\tools\run_python.ps1 webapp/manage.py collectstatic --noinput
.\tools\run_python.ps1 webapp/manage.py runserver 127.0.0.1:8000
```

`run_python.ps1` использует рабочий Python виртуального окружения, а при отсутствии его базового интерпретатора — установленный Python Codex и существующие пакеты `.venv`. Для переноса на другой компьютер установите Python 3.12, создайте окружение и установите `requirements-web.txt` и `requirements-dev.txt`. Секреты берутся из существующего `.env`.

Откройте `/`, перейдите в «Журнал записей»; для создания записи нужен аккаунт студента. На `/accounts/login/` используется обычная Django-форма входа. Админка находится на `/admin/`; административный доступ автоматически никому не выдаётся. При необходимости создайте отдельного администратора командой `webapp/manage.py createsuperuser`.

Для добавления актуальных демонстрационных консультаций выполните `webapp/manage.py seed_demo`. Существующие пользователи и пароли сохраняются; если демонстрационных аккаунтов ещё нет, команда требует `DEMO_STUDENT_PASSWORD` и `DEMO_TEACHER_PASSWORD`.

## Проверки

```powershell
.\tools\run_python.ps1 webapp/manage.py check
.\tools\run_python.ps1 webapp/manage.py showmigrations schedule
.\tools\run_python.ps1 webapp/manage.py makemigrations --check --dry-run
.\tools\run_python.ps1 webapp/manage.py test schedule --noinput
.\tools\run_python.ps1 -m pytest -q
.\tools\run_python.ps1 webapp/manage.py inspect_orm
```

Проверены 48 Django-тестов и 53 теста консольной части. Миграционный тест проверяет сохранение активных и отменённых записей, идентификаторов и связей. Интерфейс проверен в Edge: неверная длительность, создание, редактирование, отмена, фильтры, статистика, мобильная форма и SQL-панель.

## Django Debug Toolbar

Пакет указан в `requirements-dev.txt`. Панель включается только при явном включении режима разработки:

```powershell
$env:DJANGO_DEBUG='1'
$env:DJANGO_DEBUG_TOOLBAR='1'
.\tools\run_python.ps1 webapp/manage.py runserver 127.0.0.1:8000
```

На странице `/bookings/` откройте вкладку SQL. В обычном режиме и при тестировании панель выключена. Команда `inspect_orm` выполняет 18 примеров чтения и печатает SQL; сравнение N+1 на одной записи дало 4 запроса без оптимизации и 1 с `select_related()`.

## Границы выполнения

Предметная область методичек адаптирована: помещение → консультация, бронирование → запись студента. Изображения помещений, `GeneratedField` и дополнительный контекстный процессор не добавлялись: в данной модели они не требуются, а соответствующие пункты методичек условные. Прохождение уроков Яндекс Практикума подтверждается отдельно в личном аккаунте студента.

Исходный код, миграции, тесты и отчёты включены в Git-репозиторий проекта. Локальные секреты, базы данных, виртуальное окружение и резервные копии исключены через .gitignore.

## Сценарий трёх заданий

[Пошаговая демонстрация ORM, slug и формы с Bootstrap](defense_three_tasks.md). Bootstrap теперь подключён локально. Для Windows PowerShell с отключёнными сценариями используйте команды запуска из этой памятки.

## Git-репозиторий

[Исходный код проекта](https://github.com/NikiVence/consult_managing) · [История коммитов](https://github.com/NikiVence/consult_managing/commits/main/) · [Отчёты ПР9–11](https://github.com/NikiVence/consult_managing/tree/main/docs/framework_pr9_11).
