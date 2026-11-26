"use strict";
const $ = id => document.getElementById(id);
let user = null, slots = [], myBookings = [], token = "", selected = null, mode = "login", generation = 0;
const date = value => new Intl.DateTimeFormat("ru-RU", {day:"numeric", month:"long", timeZone:"Europe/Moscow"}).format(new Date(value));
const time = value => new Intl.DateTimeFormat("ru-RU", {hour:"2-digit", minute:"2-digit", timeZone:"Europe/Moscow"}).format(new Date(value));
function el(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; }
function notice(message, bad = false) { $("notice").textContent = message; $("notice").className = bad ? "error" : ""; $("notice").hidden = false; }
async function api(path, method = "GET", data) {
  const response = await fetch(path, {method, credentials:"same-origin", headers: method === "GET" ? {} : {"Content-Type":"application/json", "X-CSRFToken":token}, body:data === undefined ? undefined : JSON.stringify(data)});
  const json = await response.json().catch(() => ({error:"Сервер временно недоступен."}));
  if (!response.ok) throw new Error(json.error || "Не удалось выполнить запрос.");
  return json;
}
async function csrf() { token = (await api("/api/csrf/")).csrfToken; }
function account() {
  $("login-open").hidden = !!user; $("signed-in").hidden = !user;
  $("create-open").hidden = user?.role !== "teacher";
  if (user) { $("account-name").textContent = user.name; $("account-role").textContent = user.role === "teacher" ? "Преподаватель" : "Студент"; }
  $("bookings-heading").textContent = user?.role === "teacher" ? "Записи на мои консультации" : "Мои записи";
}
function openAuth() { $("auth-error").textContent = ""; $("auth-dialog").showModal(); }
function setMode(next) {
  mode = next; const register = next === "register";
  $("auth-title").textContent = register ? "Создать аккаунт" : "Войти в кабинет";
  $("auth-submit").textContent = register ? "Зарегистрироваться" : "Войти";
  $("name-label").hidden = !register; $("password-hint").hidden = !register;
  $("auth-form").elements.name.required = register;
  $("auth-form").elements.password.autocomplete = register ? "new-password" : "current-password";
  $("tab-login").classList.toggle("selected", !register); $("tab-register").classList.toggle("selected", register);
  $("auth-error").textContent = "";
}
function switchView(view) {
  const bookings = view === "bookings";
  $("schedule-section").hidden = bookings; $("bookings-section").hidden = !bookings;
  $("nav-schedule").classList.toggle("active", !bookings); $("nav-bookings").classList.toggle("active", bookings);
  $("page-title").textContent = bookings ? "Всё по плану." : "Время разобраться.";
  $("page-subtitle").textContent = bookings ? "Ваши встречи, время и статусы записей." : "Выберите тему и удобное время для встречи с преподавателем.";
  if (bookings && !user) { renderBookings(); openAuth(); }
}
function renderSchedule() {
  const list = $("schedule"); list.replaceChildren();
  const filtered = slots.filter(s => !$("only-free").checked || s.available);
  if (!filtered.length) { list.append(el("p", "empty", "Консультации не найдены. Измените поиск или обновите расписание.")); return; }
  for (const slot of filtered) {
    const card = el("article", "card"); const top = el("div", "card-top");
    top.append(el("span", "date-badge", date(slot.starts_at)), el("span", "pill" + (slot.available ? "" : " busy"), slot.available ? "● Доступна" : "Занята"));
    const teacher = el("div", "teacher"); teacher.append(el("span", "avatar", slot.teacher.split(" ").map(s => s[0]).slice(0,2).join("")), el("span", "", slot.teacher));
    const meta = el("div", "card-meta"); meta.append(el("span", "", "◷ 15–90 минут"), el("span", "", "⌖ " + slot.location));
    const bottom = el("div", "card-bottom"); const clock = el("span", "card-time", time(slot.starts_at)); clock.append(el("small", "", "МСК"));
    const button = el("button", "button" + (!slot.available || user?.role === "teacher" ? " secondary" : ""), !slot.available ? "Нет мест" : user?.role === "teacher" ? "Свободный слот" : "Записаться ↗");
    button.disabled = !slot.available || user?.role === "teacher";
    button.addEventListener("click", () => {
      if (!user) { openAuth(); return; }
      selected = slot; $("booking-topic").textContent = slot.topic;
      $("booking-detail").textContent = `${slot.teacher} · ${date(slot.starts_at)}, ${time(slot.starts_at)} МСК · ${slot.location}`;
      $("booking-error").textContent = ""; $("booking-dialog").showModal();
    });
    bottom.append(clock, button); card.append(top, el("h3", "", slot.topic), teacher, meta, bottom); list.append(card);
  }
}
function renderBookings() {
  const list = $("bookings"); list.replaceChildren();
  if (!user) { list.append(el("p", "empty", "Войдите, чтобы увидеть свои записи.")); return; }
  if (!myBookings.length) { list.append(el("p", "empty", "Пока нет записей. Выберите встречу в расписании.")); return; }
  for (const item of myBookings) {
    const row = el("article", "booking-row"); const content = el("div");
    content.append(el("h3", "", item.topic), el("p", "", `${date(item.starts_at)} · ${time(item.starts_at)}–${time(item.ends_at)} МСК · ${item.location}`), el("p", "", user.role === "teacher" ? "Студент: " + item.student : "Преподаватель: " + item.teacher));
    const detail = el("a", "text-button", "Открыть страницу записи ↗"); detail.href = `/bookings/${item.id}/`; content.append(detail);
    const actions = el("div", "booking-actions"); const cancelled = item.status === "cancelled";
    actions.append(el("span", "pill" + (cancelled ? " busy" : ""), cancelled ? "Отменена" : item.status === "completed" ? "Завершена" : "Подтверждена"));
    if (item.status === "confirmed") {
      const button = el("button", "button secondary", "Отменить запись");
      button.addEventListener("click", async () => {
        if (!confirm("Отменить эту запись? Время станет доступно другим студентам.")) return;
        button.disabled = true;
        try { await api(`/api/bookings/${item.id}/cancel/`, "POST", {}); notice("Запись отменена. Вы можете выбрать другое время."); await refresh(); }
        catch (error) { notice(error.message, true); button.disabled = false; }
      }); actions.append(button);
    }
    row.append(content, actions); list.append(row);
  }
}
async function loadSchedule() {
  const request = ++generation;
  const data = await api("/api/consultations/?q=" + encodeURIComponent($("search").value));
  if (request !== generation) return;
  slots = data.results; $("stat-total").textContent = slots.length; $("stat-free").textContent = slots.filter(s => s.available).length;
  renderSchedule();
}
async function loadBookings() {
  myBookings = user ? (await api("/api/bookings/")).results : [];
  const count = myBookings.filter(b => b.status === "confirmed" && new Date(b.starts_at) > new Date()).length;
  $("stat-mine").textContent = count; $("nav-count").textContent = count; renderBookings();
}
async function refresh() { await Promise.all([loadSchedule(), loadBookings()]); }
document.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => $(b.dataset.close).close()));
$("login-open").addEventListener("click", openAuth);
$("tab-login").addEventListener("click", () => setMode("login")); $("tab-register").addEventListener("click", () => setMode("register"));
$("nav-schedule").addEventListener("click", () => switchView("schedule")); $("nav-bookings").addEventListener("click", () => switchView("bookings"));
$("only-free").addEventListener("change", renderSchedule);
$("refresh").addEventListener("click", () => refresh().catch(e => notice(e.message, true)));
let debounce;
$("search").addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(() => loadSchedule().catch(e => notice(e.message, true)), 250); });
$("auth-form").addEventListener("submit", async event => {
  event.preventDefault(); $("auth-submit").disabled = true; $("auth-error").textContent = "";
  try {
    const data = Object.fromEntries(new FormData(event.target));
    user = (await api(`/api/auth/${mode === "register" ? "register" : "login"}/`, "POST", data)).user;
    await csrf(); account(); $("auth-dialog").close(); event.target.reset(); await refresh(); notice("Вы вошли в кабинет.");
  } catch (error) { $("auth-error").textContent = error.message; }
  finally { $("auth-submit").disabled = false; }
});
$("logout").addEventListener("click", async () => {
  try { await api("/api/auth/logout/", "POST", {}); user = null; await csrf(); account(); switchView("schedule"); await refresh(); notice("Вы вышли из аккаунта."); }
  catch (error) { notice(error.message, true); }
});
$("booking-form").addEventListener("submit", async event => {
  event.preventDefault(); $("booking-submit").disabled = true;
  try { await api("/api/bookings/", "POST", {consultation_id:selected.id, duration_minutes:Number($("duration").value)}); $("booking-dialog").close(); notice("Запись подтверждена. До встречи!"); await refresh(); }
  catch (error) { $("booking-error").textContent = error.message; }
  finally { $("booking-submit").disabled = false; }
});
$("create-open").addEventListener("click", () => { $("create-error").textContent = ""; $("create-dialog").showModal(); });
$("create-form").addEventListener("submit", async event => {
  event.preventDefault(); $("create-submit").disabled = true;
  try { const data = Object.fromEntries(new FormData(event.target)); data.starts_at = new Date(data.starts_at).toISOString(); await api("/api/consultations/", "POST", data); $("create-dialog").close(); event.target.reset(); await refresh(); notice("Консультация добавлена."); }
  catch (error) { $("create-error").textContent = error.message; }
  finally { $("create-submit").disabled = false; }
});
(async () => { try { await csrf(); user = (await api("/api/auth/me/")).user; account(); await refresh(); } catch (error) { notice(error.message, true); $("schedule").replaceChildren(el("p", "empty", "Не удалось загрузить данные. Нажмите «Обновить».")); } })();
