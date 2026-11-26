# Ответы к защите: маршруты, шаблоны, SQL

## 1. Маршрут и view-функция

Пример из вопроса (помещения):

```python
path("rooms/<int:room_id>/", views.room_detail, name="room_detail")

def room_detail(request, room_id):
    ...
```

При запросе `/rooms/7/` Django вызывает `room_detail(request, room_id=7)`.
Конвертер int преобразует часть URL в целое число. Имя параметра функции
должно совпадать с именем в маршруте.

Если функцию переименовать в show_room, изменится только ссылка на обработчик:

```python
path("rooms/<int:room_id>/", views.show_room, name="room_detail")
```

Путь сохраняется. name — независимое имя маршрута для построения адреса:

```django
{% url 'room_detail' room_id=7 %}
```

```python
reverse("room_detail", kwargs={"room_id": 7})
```

Коротко: «Путь задаёт адрес, view обрабатывает запрос, конвертер передаёт
параметр, а name позволяет не прописывать URL вручную».

В нашем проекте помещений как отдельной модели нет. Реальный аналог —
`path("bookings/<int:booking_id>/", api.booking_detail, name="booking_detail")`
в webapp/config/urls.py. Обработчик расположен в webapp/schedule/api.py.

## 2. Условное отображение

Реальный файл webapp/templates/booking_detail.html:

```django
{% if booking.is_cancelled %}
    <p>Отменена</p>
{% else %}
    <p>Подтверждена</p>
{% endif %}
```

Демонстрация: войти студентом → записаться → «Мои записи» → «Открыть страницу
записи». Статус — «Подтверждена». Вернуться, отменить запись и снова открыть
её страницу: статус станет «Отменена». Сервер изменяет is_cancelled на True.

Учебный пример через Django shell (подставить ID своей записи):

```python
from schedule.models import Booking
booking = Booking.objects.get(pk=1)
booking.is_cancelled = True
booking.save(update_fields=["is_cancelled"])
```

Тег if выполняется на сервере при формировании HTML. Для изменения уже
открытой страницы нужен новый запрос. Основные карточки кабинета обновляются
через JavaScript/API; они не являются примером Django-тега if.

Обратное изменение флага в рабочем приложении допустимо только после проверки
свободного слота и отсутствия пересечений. Для повторной записи используйте интерфейс.

## 3. Фильтрация SQL по состоянию

```sql
SELECT id, student_id, consultation_id, is_cancelled
FROM schedule_booking
WHERE is_cancelled = FALSE
ORDER BY id;
```

Включены неотменённые записи, исключены отменённые. Прошедшая встреча тоже
может быть неотменённой: состояние и время — разные признаки.

Меняем условие, получаем только отменённые записи:

```sql
SELECT id, student_id, consultation_id, is_cancelled
FROM schedule_booking
WHERE is_cancelled = TRUE
ORDER BY id;
```

Предстоящие неотменённые встречи:

```sql
SELECT b.id, b.student_id, c.topic, c.starts_at
FROM schedule_booking AS b
JOIN schedule_consultation AS c ON c.id = b.consultation_id
WHERE b.is_cancelled = FALSE
  AND c.starts_at > CURRENT_TIMESTAMP
ORDER BY c.starts_at;
```

Оба условия AND обязательны. Замена на OR включила бы, в частности,
отменённые будущие встречи. Поле is_cancelled обязательное, NULL отсутствует.

Эквивалент на ORM и просмотр SQL:

```python
from django.utils import timezone
Booking.objects.filter(is_cancelled=False).order_by("id")
Booking.objects.filter(is_cancelled=True).order_by("id")
Booking.objects.filter(is_cancelled=False, consultation__starts_at__gt=timezone.now())
print(Booking.objects.filter(is_cancelled=False).query)
```

SQL-консоль: `docker compose exec db psql -U consultations -d consultations`.
Прикладное API дополнительно ограничивает выборку текущим пользователем,
чтобы студенты не могли получить чужие записи.
