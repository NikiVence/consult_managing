"""Bounded HTTP load and simultaneous-booking checks on our local demo only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import http.cookiejar
import json
from pathlib import Path
import secrets
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8088"
OUT = ROOT / "docs/framework_pr5_7/evidence"
ENV = dotenv_values(ROOT / ".env")


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.token = self.call("/api/csrf/")[1]["csrfToken"]

    def call(self, path, data=None):
        headers = {} if data is None else {"Content-Type":"application/json", "X-CSRFToken":self.token}
        request = urllib.request.Request(BASE + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response), dict(response.headers)

    def auth(self, username, password, register=False):
        path = "/api/auth/register/" if register else "/api/auth/login/"
        status, body, _ = self.call(path,{"username":username,"password":password,"name":"Проверка конкурентной записи"})
        assert status in (200,201), (status,body)
        self.token = self.call("/api/csrf/")[1]["csrfToken"]
        return body["user"]["id"]


def get_once(_):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE + "/api/consultations/", timeout=20) as response:
            body = json.load(response)
            return (time.perf_counter()-start)*1000, response.status, response.headers.get("X-Cache"), body["count"]
    except Exception:
        return (time.perf_counter()-start)*1000, 0, None, 0


warmup = get_once(0)
start = time.perf_counter()
with ThreadPoolExecutor(max_workers=12) as pool:
    samples = list(pool.map(get_once, range(300)))
elapsed = time.perf_counter()-start
durations = sorted(item[0] for item in samples)
result = {"requests":300,"concurrency":12,"elapsed_seconds":round(elapsed,3),
          "requests_per_second":round(300/elapsed,2),"p50_ms":round(statistics.median(durations),2),
          "p95_ms":round(durations[int(.95*len(durations))-1],2),
          "max_ms":round(max(durations),2), "errors":sum(s[1]!=200 for s in samples),
          "cache_hits":sum(s[2]=="HIT" for s in samples),
          "dataset_slots":warmup[3], "scope":"Local demo, HTTP reads, no production capacity claim"}
assert result["errors"] == 0, result
run_id = secrets.token_hex(4)
clients = [Client(),Client()]
user_ids = [client.auth("probe_"+run_id+str(i), secrets.token_urlsafe(20), register=True) for i,client in enumerate(clients)]
teacher = Client()
teacher.auth("teacher", ENV["DEMO_TEACHER_PASSWORD"])
created_ids = []
when = (datetime.now(timezone.utc) + timedelta(days=5)).replace(second=0,microsecond=0)
for offset in (0,15):
    status, body, _ = teacher.call("/api/consultations/", {"topic":"PROBE-"+run_id, "location":"Тест", "starts_at":(when+timedelta(minutes=offset)).isoformat()})
    assert status == 201, body
    created_ids.append(body["id"])


def race(slot_ids):
    barrier = threading.Barrier(2)

    def book(index):
        barrier.wait(timeout=10)
        status, body, _ = clients[index].call("/api/bookings/", {"consultation_id":slot_ids[index], "duration_minutes":45})
        return index,status,body

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(book,range(2)))
    assert sorted(item[1] for item in responses) == [201,409], responses
    for index,status,body in responses:
        if status == 201:
            assert clients[index].call(f'/api/bookings/{body["id"]}/cancel/', {})[0] == 200
    return [item[1] for item in responses]


result["same_slot_race"] = race([created_ids[0], created_ids[0]])
result["overlapping_teacher_race"] = race(created_ids)
# Delete only the temporary records created above; never touch existing accounts.
cleanup = (
    "from schedule.models import Booking,Consultation,User; "
    f"Booking.objects.filter(student_id__in={user_ids!r}).delete(); "
    f"Consultation.objects.filter(pk__in={created_ids!r},topic='PROBE-{run_id}').delete(); "
    f"User.objects.filter(pk__in={user_ids!r},username__startswith='probe_{run_id}').delete(); "
    "from django.core.cache import cache; cache.delete('schedule:upcoming'); print('Temporary probe data removed')"
)
subprocess.run(["docker","compose","exec","-T","app","python","manage.py","shell","-c",cleanup],cwd=ROOT,check=True,capture_output=True)
(OUT / "load.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
