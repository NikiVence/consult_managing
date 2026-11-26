# Три задания для защиты

Основной проект: `D:\consult_managing`. Все команды выполняются из его корня.

## Запуск Windows PowerShell

Первое окно — сервер:

```powershell
cd D:\consult_managing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\run_python.ps1 webapp/manage.py runserver 127.0.0.1:8000
```

Второе окно — Django Shell:

```powershell
cd D:\consult_managing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\run_python.ps1 webapp/manage.py shell
```

## 1. Создание объекта ORM

В Shell, по очереди:

```python
from schedule.models import User, Consultation
from django.utils import timezone
from datetime import timedelta
teacher = User.objects.filter(role="teacher").first()
print(teacher)
slot = Consultation(teacher=teacher, topic="Защита практической", starts_at=timezone.now() + timedelta(days=3), location="Онлайн")
print(slot.pk)  # None: пока объект только в памяти
slot.location = "Аудитория 312"
slot.save()
saved = Consultation.objects.get(pk=slot.pk)
print(saved.pk, saved.topic, saved.location)
```

Сказать: «Конструктор модели создал объект в памяти. Я изменил поле до save. В базу сохранилось значение “Аудитория 312”, что подтверждает повторное чтение через get. objects.create, в отличие от конструктора, сразу сохраняет объект».

## 2. Slug и адрес страницы

Показать `webapp/schedule/models.py`: поле slug, генерацию в save и get_absolute_url. В `webapp/config/urls.py` показать маршрут `consultations/<slug:slug>/` с именем `consultation_detail`.

```python
print(slot.slug)
print(slot.get_absolute_url())
print("http://127.0.0.1:8000" + slot.get_absolute_url())
```

Открыть напечатанный URL. Сказать: «reverse собирает адрес по имени маршрута и параметру slug. Если изменить префикс пути, сохранив имя и параметры, ссылки продолжат работать без переписывания адресов в коде». В админке консультации ссылка «Смотреть на сайте» использует get_absolute_url.

## 3. Поля, виджеты и настоящий Bootstrap

Открыть `webapp/schedule/forms.py`, класс BookingForm. Показать Meta.model, fields, labels и widgets. IntegerField проверяет число, NumberInput создаёт input type=number; Select создаёт выпадающий список. min_value/max_value — проверка Django, min/max в attrs — атрибуты HTML.

Открыть `/bookings/new/`, войдя студентом. В attrs виджета NumberInput временно добавить `"placeholder": "Например, 45"`, сохранить файл и обновить страницу. В пустом поле появится подсказка. Затем удалить атрибут и снова сохранить.

Для демонстрации Bootstrap временно заменить класс `form-control` на `form-control form-control-lg`. После обновления числовое поле станет крупнее. Вернуть `form-control`.

Bootstrap 5.3.3 реально подключён локально в `webapp/templates/schedule/base.html`, файл `webapp/static/vendor/bootstrap/bootstrap.min.css`. Числовое поле использует form-control, список — form-select. Откройте инструменты разработчика: в HTML видны классы, в Styles — правила bootstrap.min.css. Интернет на защите не нужен.

Сказать: «Поле определяет данные и валидацию, виджет — HTML-представление, attrs задаёт HTML-атрибуты, Bootstrap оформляет элементы через CSS-классы. Изменение placeholder не меняет базу и не требует миграции».

Если изменения Python не подхватились, перезапустить сервер. Изменения только формы не требуют collectstatic. После изменения CSS при выключенном DEBUG нужно выполнить collectstatic --noinput и обновить страницу без кэша.
