const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = s => esc(s).replace(/\n/g, "<br>");
const badge = (t, cls) => `<span class="badge ${cls}">${esc(t)}</span>`;

async function api(path, opts = {}) {
  const headers = opts.body && !(opts.body instanceof FormData) ? {"Content-Type": "application/json"} : {};
  const res = await fetch(path, {credentials: "same-origin", ...opts, headers});
  let data = null;
  try { data = await res.json(); } catch {}
  if (!res.ok) {
    const d = data && data.detail;
    const err = new Error(typeof d === "string" ? d : "Something went wrong");
    err.status = res.status;
    throw err;
  }
  return data;
}

function setupLogin(portal, onOk) {
  $("#loginForm").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await api("/api/login", {method: "POST", body: JSON.stringify({username: $("#u").value, password: $("#p").value, portal})});
      $("#p").value = ""; $("#loginErr").textContent = ""; onOk();
    } catch (err) { $("#loginErr").textContent = err.message; }
  });
  $("#logout").onclick = async () => { await api("/api/logout", {method: "POST"}); location.reload(); };
}

function setupTabs(onTab) {
  const btns = document.querySelectorAll(".tabs button");
  btns.forEach(b => b.onclick = () => {
    btns.forEach(x => x.classList.toggle("on", x === b));
    document.querySelectorAll("main > section").forEach(s => s.classList.toggle("hidden", s.id !== b.dataset.tab));
    onTab(b.dataset.tab);
  });
}

async function boot(kind, show) {
  try {
    const me = await api("/api/me");
    if (me.kind !== kind) throw new Error("wrong portal");
    $("#login").classList.add("hidden"); $("#app").classList.remove("hidden");
    show(me);
  } catch { $("#login").classList.remove("hidden"); $("#app").classList.add("hidden"); }
}
