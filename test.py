from schedule.models import Consultation

slot = Consultation.objects.first()
print(slot)

print(slot.slug)

print(slot.get_absolute_url())

print("http://127.0.0.1:8000" + slot.get_absolute_url())
