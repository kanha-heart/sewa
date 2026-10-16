/* Sewa front end. Plain JavaScript, no build step.
   One page: login, then Requests / Alerts / Me for everyone, plus an Admin tab for admins. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------- small helpers ---------- */
  const tokenStore = {
    get() { try { return localStorage.getItem("sewa_token"); } catch { return null; } },
    set(v) { try { v ? localStorage.setItem("sewa_token", v) : localStorage.removeItem("sewa_token"); } catch { /* private mode */ } },
  };
  const hm = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
  const fmtMin = (m) => { m = Math.round(m); const h = Math.floor(m / 60) % 24, mm = m % 60; return `${(h + 11) % 12 + 1}:${String(mm).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`; };
  const fmtDate = (iso) => new Date(iso + "T00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  const num = (x) => String(Math.round(x * 10) / 10);
  const dur = (h) => `${num(h)} ${h === 1 ? "hour" : "hours"}`;
  const isoDate = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const tomorrow = () => { const d = new Date(); d.setDate(d.getDate() + 1); return isoDate(d); };
  const endOf = (r) => hm(r.start_time) + Math.round(r.duration_hours * 60);
  const mapsUrl = (r) => `https://www.google.com/maps?q=${r.lat},${r.lng}`;

  const state = {
    me: null, depts: [], reqs: [], notifs: [], subs: [], stats: null, admins: [],
    view: "req", adminTab: "post", filter: 0, sheet: null,
    loginStep: 1, phone: "", devCode: "", busy: false,
  };

  let toastTimer;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
  }

  async function api(path, { method = "GET", body } = {}) {
    const headers = { "Content-Type": "application/json" };
    const token = tokenStore.get();
    if (token) headers.Authorization = "Bearer " + token;
    const res = await fetch("/api" + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    if (res.status === 401 && token) {
      tokenStore.set(null); state.me = null; state.loginStep = 1; render();
      throw new Error("Please sign in again");
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = data.detail;
      throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join(", ") : "Something went wrong");
    }
    return data;
  }

  const canManageDept = (id) => state.me && state.me.is_admin && (state.me.admin_dept_id === null || state.me.admin_dept_id === id);
  const manageableDepts = () => state.depts.filter((d) => canManageDept(d.id));

  /* ---------- data loading ---------- */
  async function loadAll() {
    const q = state.me.is_admin ? "?include_inactive=true" : "";
    const [depts, reqs, notifs, subs] = await Promise.all([
      api("/departments"), api("/requests" + q), api("/me/notifications"), api("/me/subscriptions"),
    ]);
    state.depts = depts; state.reqs = reqs; state.notifs = notifs; state.subs = subs.dept_ids;
  }
  async function refresh() { await loadAll(); render(); }

  /* ---------- views ---------- */
  function statusPill(r) {
    if (!r.active) return '<span class="pill p-off">Paused</span>';
    if (r.full) return '<span class="pill p-full">Full</span>';
    return '<span class="pill p-open">Open</span>';
  }

  function viewLogin() {
    if (state.loginStep === 1) {
      return `<form class="card" data-form="otp">
        <h2>Welcome to Sewa</h2>
        <p class="note">Enter your phone number. We send you a one-time code.</p>
        <div class="field"><label for="l-phone">Phone number</label><input id="l-phone" inputmode="tel" autocomplete="tel" placeholder="10 digit mobile number" required value="${esc(state.phone)}"></div>
        <button class="btn block" type="submit">Send code</button></form>`;
    }
    return `<form class="card" data-form="verify">
      <h2>Enter your code</h2>
      <p class="note">Sent to ${esc(state.phone)}.</p>
      ${state.devCode ? `<div class="banner">Test mode: your code is ${esc(state.devCode)}</div>` : ""}
      <div class="field"><label for="l-code">Code</label><input id="l-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required value="${esc(state.devCode)}"></div>
      <div class="field"><label for="l-name">Your name (first time only)</label><input id="l-name" autocomplete="name"></div>
      <div class="field"><label for="l-group">I am (first time only)</label><select id="l-group"><option value="">Choose</option><option>Brothers</option><option>Sisters</option></select></div>
      <button class="btn block" type="submit">Sign in</button>
      <button class="btn ghost block" type="button" data-a="loginback">Use a different number</button></form>`;
  }

  function requestCard(r) {
    const my = r.my_slot, s = hm(r.start_time);
    const pct = Math.min(100, Math.round((r.covered_hours / r.target_hours) * 100));
    return `<article class="card">
      <div class="row"><span class="pill p-dept">${esc(r.dept_name)}</span>${my ? '<span class="pill p-open">You joined</span>' : r.full ? '<span class="pill p-full">Full</span>' : ""}</div>
      <h3>${esc(r.work)}</h3>
      <dl class="meta">
        <dt>Date</dt><dd>${fmtDate(r.day)}</dd>
        <dt>Time</dt><dd>${fmtMin(s)} to ${fmtMin(endOf(r))}</dd>
        <dt>Duration</dt><dd>${dur(r.duration_hours)}</dd>
        <dt>Needed</dt><dd>${r.people_needed} ${esc(r.group)}</dd>
        <dt>Where</dt><dd>${esc(r.place)}<br><a class="link" href="${mapsUrl(r)}" target="_blank" rel="noopener">${Number(r.lat).toFixed(4)}, ${Number(r.lng).toFixed(4)} (open map)</a></dd>
      </dl>
      <div class="bar" aria-hidden="true"><i style="width:${pct}%"></i></div>
      <p class="note">${r.full ? "All hours are covered" : `${num(r.target_hours - r.covered_hours)} of ${num(r.target_hours)} person-hours still needed`}</p>
      ${my ? `<div class="mine">Your slot: ${fmtMin(my.from_min)} to ${fmtMin(my.to_min)} (${dur((my.to_min - my.from_min) / 60)})</div>` : ""}
      <div class="acts">${my
        ? `<button class="btn sm ghost" data-a="join" data-id="${r.id}">Change hours</button><button class="btn sm ghost" data-a="leave" data-id="${r.id}">Cancel my slot</button>`
        : `<button class="btn sm" data-a="join" data-id="${r.id}" ${r.full ? "disabled" : ""}>Join</button>`}</div>
    </article>`;
  }

  function viewRequests() {
    const list = state.reqs.filter((r) => r.active && (state.filter === 0 || r.dept_id === state.filter));
    return `<div class="chips"><button class="chip" data-a="filter" data-id="0" aria-pressed="${state.filter === 0}">All</button>
      ${state.depts.map((d) => `<button class="chip" data-a="filter" data-id="${d.id}" aria-pressed="${state.filter === d.id}">${esc(d.name)}</button>`).join("")}</div>
      ${list.length ? list.map(requestCard).join("") : `<div class="empty">No open requests${state.me.is_admin ? "" : ` for ${esc(state.me.group)}`} right now. Switch on alerts to hear when new ones come.</div>`}`;
  }

  function viewAlerts() {
    return `<div class="card"><h2>Alerts by department</h2>
      <p class="note">Switch on a department to get a message when a new request is posted or more hands are needed.</p>
      <div>${state.depts.map((d) => `<div class="switch"><span>${esc(d.name)}</span><button data-a="sub" data-id="${d.id}" aria-pressed="${state.subs.includes(d.id)}" aria-label="Alerts for ${esc(d.name)}"></button></div>`).join("")}</div></div>
      <div class="card"><h2>Recent alerts</h2>
      ${state.notifs.length ? state.notifs.map((n) => `<div class="bubble">${esc(n.text)}<small>${new Date(n.created_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</small></div>`).join("") : '<div class="empty">No alerts yet.</div>'}</div>`;
  }

  function viewMe() {
    const m = state.me;
    return `<form class="card" data-form="profile"><h2>My details</h2>
      <div class="field"><label for="m-name">Name</label><input id="m-name" value="${esc(m.name)}" required></div>
      <div class="field"><label>Phone</label><input value="${esc(m.phone)}" disabled></div>
      <div class="field"><label for="m-group">I am</label><select id="m-group">${["Brothers", "Sisters"].map((g) => `<option ${m.group === g ? "selected" : ""}>${g}</option>`).join("")}</select></div>
      <div class="field"><span class="label">When I am usually free</span><div class="chips" style="flex-wrap:wrap">${["Morning", "Afternoon", "Evening"].map((k) => `<button type="button" class="chip" data-a="av" data-k="${k}" aria-pressed="${m.availability.includes(k)}">${k}</button>`).join("")}</div></div>
      <button class="btn block" type="submit">Save</button></form>
      <button class="btn ghost block" data-a="logout">Sign out</button>`;
  }

  /* ----- admin ----- */
  function reqFields(r) {
    const depts = manageableDepts();
    const d = r || { dept_id: depts[0] ? depts[0].id : 0, work: "", day: tomorrow(), start_time: "07:00", duration_hours: 2, people_needed: 4, group: "Brothers" };
    const dd = state.depts.find((x) => x.id === d.dept_id) || { place: "", lat: "", lng: "" };
    const place = r ? r.place : dd.place, lat = r ? r.lat : dd.lat, lng = r ? r.lng : dd.lng;
    return `<div class="form">
      <div class="field wide"><label for="f-dept">Department</label><select id="f-dept">${depts.map((x) => `<option value="${x.id}" ${x.id === d.dept_id ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>
      <div class="field wide"><label for="f-work">Work</label><input id="f-work" required maxlength="120" placeholder="e.g. Weeding the herb beds" value="${esc(d.work)}"></div>
      <div class="field"><label for="f-day">Date</label><input id="f-day" type="date" required value="${esc(d.day)}"></div>
      <div class="field"><label for="f-time">Start time</label><input id="f-time" type="time" required value="${esc(d.start_time)}"></div>
      <div class="field"><label for="f-dur">Hours</label><input id="f-dur" type="number" inputmode="decimal" min="0.5" max="12" step="0.5" required value="${d.duration_hours}"></div>
      <div class="field"><label for="f-need">People needed</label><input id="f-need" type="number" inputmode="numeric" min="1" max="500" required value="${d.people_needed}"></div>
      <div class="field wide"><label for="f-group">Brothers or Sisters</label><select id="f-group">${["Brothers", "Sisters"].map((g) => `<option ${d.group === g ? "selected" : ""}>${g}</option>`).join("")}</select></div>
      <details class="wide"><summary>Location</summary><div class="form">
        <div class="field wide"><label for="f-place">Place name</label><input id="f-place" value="${esc(place)}"></div>
        <div class="field"><label for="f-lat">Latitude</label><input id="f-lat" type="number" step="any" inputmode="decimal" value="${lat}"></div>
        <div class="field"><label for="f-lng">Longitude</label><input id="f-lng" type="number" step="any" inputmode="decimal" value="${lng}"></div>
        <button class="btn ghost wide" type="button" data-a="geo">Use my current location</button></div></details>
    </div>`;
  }

  function readReqForm() {
    return {
      dept_id: Number($("#f-dept").value), work: $("#f-work").value.trim(), day: $("#f-day").value, start_time: $("#f-time").value,
      duration_hours: Number($("#f-dur").value), people_needed: Number($("#f-need").value), group: $("#f-group").value,
      place: $("#f-place").value.trim(), lat: Number($("#f-lat").value), lng: Number($("#f-lng").value),
    };
  }

  function manageCard(r) {
    const off = r.can_manage ? "" : "disabled";
    return `<article class="card">
      <div class="row"><span class="pill p-dept">${esc(r.dept_name)}</span>${statusPill(r)}</div>
      <h3>${esc(r.work)}</h3>
      <p class="note">${fmtDate(r.day)}, ${fmtMin(hm(r.start_time))} to ${fmtMin(endOf(r))}, ${esc(r.group)}</p>
      <div class="row"><span class="step"><button data-a="need" data-id="${r.id}" data-d="-1" aria-label="Need one fewer" ${off}>−</button><b>${r.people_needed}</b><button data-a="need" data-id="${r.id}" data-d="1" aria-label="Need one more" ${off}>+</button></span>
        <span class="note">${num(r.covered_hours)} of ${num(r.target_hours)} h covered, ${r.signups_count} sign-ups</span></div>
      <div class="acts"><button class="btn sm ghost" data-a="edit" data-id="${r.id}" ${off}>Edit</button><button class="btn sm ghost" data-a="copy" data-id="${r.id}" ${off}>Copy</button>
        <button class="btn sm ${r.active ? "ghost" : ""}" data-a="toggle" data-id="${r.id}" ${off}>${r.active ? "Deactivate" : "Activate"}</button></div>
    </article>`;
  }

  function adminPost() {
    if (!manageableDepts().length) return '<div class="empty">You are not an admin of any department yet.</div>';
    return `<form class="card" data-form="post"><h2>Post a new request</h2>${reqFields(null)}<button class="btn block" type="submit">Post request</button></form>`;
  }
  function adminManage() {
    const list = state.reqs;
    return `<p class="note">Use − and + to change how many people are needed. Copy makes a new request from an old one: you only change the date, time or number.</p>
      ${list.length ? list.map(manageCard).join("") : '<div class="empty">No requests yet. Post the first one.</div>'}`;
  }
  function adminStats() {
    const s = state.stats;
    if (!s) return '<div class="empty">Loading numbers...</div>';
    const maxH = Math.max(1, ...s.by_dept.map((d) => d.requested));
    const maxD = Math.max(1, ...s.by_day.map((d) => d.requested));
    return `<div class="kpis">
        <div class="kpi"><b>${s.open_requests}</b><span>Open of ${s.total_requests} requests</span></div>
        <div class="kpi"><b>${num(s.person_hours_requested)}</b><span>Person-hours requested</span></div>
        <div class="kpi"><b>${s.signups} / ${s.people_needed}</b><span>Sign-ups / people needed</span></div>
        <div class="kpi"><b>${s.fill_rate}%</b><span>Hours covered</span></div></div>
      <div class="card"><h3>Hours covered vs requested, by department</h3><div class="hb">
        ${s.by_dept.map((d) => `<span>${esc(d.name)}</span><div class="bar" aria-hidden="true" style="position:relative"><i style="width:${d.requested / maxH * 100}%;background:var(--line)"></i><i style="position:absolute;left:0;top:0;width:${d.covered / maxH * 100}%"></i></div><em>${num(d.covered)}/${num(d.requested)}</em>`).join("")}</div></div>
      <div class="card"><h3>Busiest days (person-hours requested)</h3><div class="hb">
        ${s.by_day.length ? s.by_day.map((d) => `<span>${fmtDate(d.day)}</span><div class="bar" aria-hidden="true"><i style="width:${d.requested / maxD * 100}%"></i></div><em>${num(d.requested)}</em>`).join("") : '<span class="note">No data yet</span>'}</div></div>`;
  }
  function adminPeople() {
    const isSuper = state.me.is_super;
    return `<div class="card"><h3>Departments</h3>${state.depts.map((d) => `<div class="li"><span><b>${esc(d.name)}</b><br><span class="note">In-charge: ${esc(d.incharge_name)}</span></span><span class="note" style="text-align:right">${esc(d.place)}<br>${Number(d.lat).toFixed(4)}, ${Number(d.lng).toFixed(4)}</span></div>`).join("")}</div>
      ${isSuper ? `<form class="card" data-form="dept"><h3>Add a department</h3><div class="form">
        <div class="field wide"><label for="d-name">Department</label><input id="d-name" required></div>
        <div class="field"><label for="d-inc">In-charge name</label><input id="d-inc" required></div>
        <div class="field"><label for="d-phone">In-charge phone</label><input id="d-phone" inputmode="tel" required></div>
        <div class="field wide"><label for="d-place">Location name</label><input id="d-place"></div>
        <div class="field"><label for="d-lat">Latitude</label><input id="d-lat" type="number" step="any" inputmode="decimal"></div>
        <div class="field"><label for="d-lng">Longitude</label><input id="d-lng" type="number" step="any" inputmode="decimal"></div></div>
        <button class="btn block" type="submit">Add department and make in-charge admin</button></form>` : ""}
      <div class="card"><h3>Admins</h3>${state.admins.map((a) => `<div class="li"><span><b>${esc(a.name)}</b><br><span class="note">${esc(a.phone)}</span></span><span class="acts"><span class="pill p-dept">${esc(a.dept_name)}</span>${a.id !== state.me.id ? `<button class="btn sm ghost" data-a="rmadmin" data-id="${a.id}">Remove</button>` : ""}</span></div>`).join("") || '<p class="note">No admins yet.</p>'}</div>
      <form class="card" data-form="admin"><h3>Make a helper admin</h3><div class="form">
        <div class="field"><label for="a-name">Name</label><input id="a-name"></div>
        <div class="field"><label for="a-phone">Phone</label><input id="a-phone" inputmode="tel" required></div>
        ${isSuper ? `<div class="field wide"><label for="a-dept">Department</label><select id="a-dept">${state.depts.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("")}</select></div>` : `<p class="note wide">They become admins of your department only.</p>`}</div>
        <button class="btn block" type="submit">Make admin</button></form>`;
  }
  function viewAdmin() {
    const tabs = [["post", "Post"], ["manage", "Manage"], ["stats", "Numbers"], ["people", "People"]];
    const body = { post: adminPost, manage: adminManage, stats: adminStats, people: adminPeople }[state.adminTab]();
    return `<div class="chips">${tabs.map(([k, l]) => `<button class="chip" data-a="atab" data-k="${k}" aria-selected="${state.adminTab === k}">${l}</button>`).join("")}</div>${body}`;
  }

  /* ----- sheets ----- */
  function stepsList(a, b) { const out = []; for (let m = a; m < b; m += 30) out.push(m); return out; }
  function joinSheet(r) {
    const s = hm(r.start_time), e = endOf(r), my = r.my_slot;
    const fromList = stepsList(s, e);
    const toList = [...stepsList(s + 30, e), e].filter((v, i, arr) => arr.indexOf(v) === i);
    const sel = (list, v) => list.map((m) => `<option value="${m}" ${m === v ? "selected" : ""}>${fmtMin(m)}</option>`).join("");
    return `<form data-form="join"><h2>${my ? "Change hours" : "Join"}: ${esc(r.work)}</h2>
      <p class="note" style="margin:6px 0 12px">${fmtDate(r.day)}, ${fmtMin(s)} to ${fmtMin(e)}. Pick the hours you can give. You can stay for the whole shift or only part of it.</p>
      <div class="form"><div class="field"><label for="j-from">From</label><select id="j-from">${sel(fromList, my ? my.from_min : s)}</select></div>
      <div class="field"><label for="j-to">To</label><select id="j-to">${sel(toList, my ? my.to_min : e)}</select></div></div>
      <p class="note" id="j-sum" style="margin:12px 0"></p>
      <div class="acts"><button class="btn ghost" type="button" data-a="closesheet">Back</button><button class="btn" type="submit" id="j-ok">Confirm</button></div></form>`;
  }
  function editSheet(r) {
    return `<form data-form="edit"><h2>Edit request</h2><p class="note" style="margin:6px 0 12px">Existing sign-ups move with the start time. Followers get an alert if the day or time changes.</p>${reqFields(r)}
      <div class="acts" style="margin-top:14px"><button class="btn ghost" type="button" data-a="closesheet">Back</button><button class="btn" type="submit">Save changes</button></div></form>`;
  }
  function copySheet(r) {
    return `<form data-form="copy"><h2>Copy request</h2><p class="note" style="margin:6px 0 12px">${esc(r.work)} in ${esc(r.dept_name)}. Change only what is different.</p>
      <div class="form"><div class="field"><label for="c-day">Date</label><input id="c-day" type="date" required value="${esc(r.day)}"></div>
      <div class="field"><label for="c-time">Start time</label><input id="c-time" type="time" required value="${esc(r.start_time)}"></div>
      <div class="field wide"><label for="c-need">People needed</label><input id="c-need" type="number" inputmode="numeric" min="1" max="500" required value="${r.people_needed}"></div></div>
      <div class="acts" style="margin-top:14px"><button class="btn ghost" type="button" data-a="closesheet">Back</button><button class="btn" type="submit">Post copy</button></div></form>`;
  }
  function renderSheet() {
    const el = $("#sheet");
    const sh = state.sheet;
    if (!sh) { el.innerHTML = ""; return; }
    const r = state.reqs.find((x) => x.id === sh.id);
    if (!r) { state.sheet = null; el.innerHTML = ""; return; }
    const html = { join: joinSheet, edit: editSheet, copy: copySheet }[sh.type](r);
    el.innerHTML = `<div class="overlay" data-a="overlay"><div class="sheet" role="dialog" aria-modal="true">${html}</div></div>`;
    if (sh.type === "join") updateJoinSum();
  }
  function updateJoinSum() {
    const f = $("#j-from"), t = $("#j-to");
    if (!f || !t) return;
    const a = Number(f.value), b = Number(t.value), ok = b > a;
    $("#j-sum").textContent = ok ? `You will give ${dur((b - a) / 60)}, ${fmtMin(a)} to ${fmtMin(b)}.` : "Choose an end time after the start time.";
    $("#j-ok").disabled = !ok;
  }

  /* ---------- render ---------- */
  function render() {
    const nav = $("#nav"), app = $("#app");
    if (!state.me) {
      $("#hello").textContent = "Volunteer requests";
      nav.hidden = true; app.innerHTML = viewLogin(); renderSheet(); return;
    }
    $("#hello").textContent = `Hari Om, ${state.me.name}`;
    const items = [["req", "Requests"], ["alerts", "Alerts"], ["me", "Me"]];
    if (state.me.is_admin) items.push(["admin", "Admin"]);
    nav.hidden = false;
    nav.innerHTML = items.map(([k, l]) => `<button data-a="go" data-k="${k}" aria-selected="${state.view === k}">${l}</button>`).join("");
    app.innerHTML = { req: viewRequests, alerts: viewAlerts, me: viewMe, admin: viewAdmin }[state.view]();
    renderSheet();
  }

  /* ---------- actions ---------- */
  async function run(fn) {
    try { await fn(); } catch (e) { toast(e.message || "Something went wrong"); }
  }

  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-a]");
    if (!el) return;
    const a = el.dataset.a, id = Number(el.dataset.id);
    if (a === "overlay") { if (e.target === el) { state.sheet = null; renderSheet(); } return; }
    run(async () => {
      if (a === "go") {
        state.view = el.dataset.k; render();
        if (state.view === "admin") await openAdminTab(state.adminTab);
      }
      else if (a === "atab") { await openAdminTab(el.dataset.k); }
      else if (a === "filter") { state.filter = id; render(); }
      else if (a === "join") { state.sheet = { type: "join", id }; renderSheet(); }
      else if (a === "edit") { state.sheet = { type: "edit", id }; renderSheet(); }
      else if (a === "copy") { state.sheet = { type: "copy", id }; renderSheet(); }
      else if (a === "closesheet") { state.sheet = null; renderSheet(); }
      else if (a === "leave") { await api(`/requests/${id}/join`, { method: "DELETE" }); await refresh(); toast("Your slot was cancelled and the hours are open again"); }
      else if (a === "sub") {
        const set = new Set(state.subs); set.has(id) ? set.delete(id) : set.add(id);
        const res = await api("/me/subscriptions", { method: "PUT", body: { dept_ids: [...set] } });
        state.subs = res.dept_ids; render();
        toast(set.has(id) ? "Alerts on" : "Alerts off");
      }
      else if (a === "av") { el.setAttribute("aria-pressed", el.getAttribute("aria-pressed") !== "true"); }
      else if (a === "need") {
        const r = state.reqs.find((x) => x.id === id), n = r.people_needed + Number(el.dataset.d);
        if (n < 1) return;
        const res = await api(`/admin/requests/${id}`, { method: "PATCH", body: { people_needed: n } });
        await refresh(); toast(`People needed is now ${n}${res.alerted ? `. Alert sent to ${res.alerted}` : ""}`);
      }
      else if (a === "toggle") {
        const r = state.reqs.find((x) => x.id === id);
        await api(`/admin/requests/${id}`, { method: "PATCH", body: { active: !r.active } });
        await refresh(); toast(r.active ? "Request deactivated" : "Request activated");
      }
      else if (a === "geo") {
        if (!navigator.geolocation) { toast("Location is not available on this device"); return; }
        navigator.geolocation.getCurrentPosition(
          (p) => { $("#f-lat").value = p.coords.latitude.toFixed(6); $("#f-lng").value = p.coords.longitude.toFixed(6); toast("Location filled in"); },
          () => toast("Could not get your location. Allow location access, and use https."),
          { enableHighAccuracy: true, timeout: 10000 });
      }
      else if (a === "rmadmin") { await api(`/admin/admins/${id}`, { method: "DELETE" }); state.admins = await api("/admin/admins"); render(); toast("Admin removed"); }
      else if (a === "loginback") { state.loginStep = 1; state.devCode = ""; render(); }
      else if (a === "logout") { try { tokenStore.set(null); } finally { state.me = null; state.loginStep = 1; state.view = "req"; render(); } }
    });
  });

  async function openAdminTab(tab) {
    state.adminTab = tab; render();
    if (tab === "stats") { state.stats = await api("/admin/analytics"); render(); }
    if (tab === "people") { state.admins = await api("/admin/admins"); render(); }
  }

  document.addEventListener("change", (e) => {
    if (e.target.id === "f-dept") {
      const d = state.depts.find((x) => x.id === Number(e.target.value));
      if (d && !state.sheet) { $("#f-place").value = d.place; $("#f-lat").value = d.lat; $("#f-lng").value = d.lng; }
    }
    if (e.target.id === "j-from" || e.target.id === "j-to") updateJoinSum();
  });

  document.addEventListener("submit", (e) => {
    const form = e.target.closest("[data-form]");
    if (!form) return;
    e.preventDefault();
    const kind = form.dataset.form;
    run(async () => {
      if (kind === "otp") {
        state.phone = $("#l-phone").value.trim();
        const res = await api("/auth/request-otp", { method: "POST", body: { phone: state.phone } });
        state.devCode = res.dev_code || ""; state.loginStep = 2; render();
      } else if (kind === "verify") {
        const res = await api("/auth/verify", { method: "POST", body: { phone: state.phone, code: $("#l-code").value.trim(), name: $("#l-name").value.trim(), group: $("#l-group").value } });
        tokenStore.set(res.token); state.me = res.me; state.view = "req"; state.devCode = "";
        await loadAll(); render();
      } else if (kind === "profile") {
        const avail = [...document.querySelectorAll('[data-a="av"]')].filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.dataset.k);
        state.me = await api("/me", { method: "PUT", body: { name: $("#m-name").value.trim(), group: $("#m-group").value, availability: avail } });
        await refresh(); toast("Saved");
      } else if (kind === "join") {
        const a = Number($("#j-from").value), b = Number($("#j-to").value), id = state.sheet.id;
        await api(`/requests/${id}/join`, { method: "POST", body: { from_min: a, to_min: b } });
        state.sheet = null; await refresh(); toast(`You will give ${dur((b - a) / 60)}. Thank you!`);
      } else if (kind === "post") {
        const res = await api("/admin/requests", { method: "POST", body: readReqForm() });
        await loadAll(); state.adminTab = "manage"; render();
        toast(res.alerted ? `Posted. WhatsApp alert sent to ${res.alerted} volunteers` : "Posted. Nobody follows this department yet");
      } else if (kind === "edit") {
        const res = await api(`/admin/requests/${state.sheet.id}`, { method: "PATCH", body: readReqForm() });
        state.sheet = null; await refresh(); toast(`Saved${res.alerted ? `. Alert sent to ${res.alerted}` : ""}`);
      } else if (kind === "copy") {
        const res = await api(`/admin/requests/${state.sheet.id}/copy`, { method: "POST", body: { day: $("#c-day").value, start_time: $("#c-time").value, people_needed: Number($("#c-need").value) } });
        state.sheet = null; await refresh(); toast(res.alerted ? `Copy posted. Alert sent to ${res.alerted}` : "Copy posted");
      } else if (kind === "dept") {
        await api("/admin/departments", { method: "POST", body: { name: $("#d-name").value.trim(), incharge_name: $("#d-inc").value.trim(), incharge_phone: $("#d-phone").value.trim(), place: $("#d-place").value.trim(), lat: Number($("#d-lat").value || 0), lng: Number($("#d-lng").value || 0) } });
        await loadAll(); state.admins = await api("/admin/admins"); render(); toast("Department added. The in-charge can now sign in as admin");
      } else if (kind === "admin") {
        const dept = $("#a-dept");
        await api("/admin/admins", { method: "POST", body: { name: $("#a-name").value.trim(), phone: $("#a-phone").value.trim(), dept_id: dept ? Number(dept.value) : null } });
        state.admins = await api("/admin/admins"); render(); toast("Admin added");
      }
    });
  });

  /* ---------- start ---------- */
  (async function start() {
    if (tokenStore.get()) {
      try { state.me = await api("/me"); await loadAll(); } catch { state.me = null; }
    }
    render();
  })();
})();
