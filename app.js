/* Shared helpers used by all planner pages. */
window.PocketSmart = (function () {
  function showError(msg) {
    const box = document.getElementById("form-error");
    if (!box) return alert(msg);
    box.textContent = msg;
    box.hidden = false;
    box.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  function clearError() {
    const box = document.getElementById("form-error");
    if (box) box.hidden = true;
  }
  function setLoading(on) {
    const btn = document.getElementById("submit-btn");
    if (!btn) return;
    if (on) { btn.dataset.label = btn.textContent; btn.textContent = "Thinking… this can take up to 30 seconds"; }
    else if (btn.dataset.label) { btn.textContent = btn.dataset.label; }
    btn.disabled = on;
  }
  /* Turn FastAPI error payloads into a readable sentence. */
  function errorMessage(data, status) {
    if (status === 401) return "Your session expired. Please sign in again.";
    if (data && Array.isArray(data.detail)) {
      return data.detail.map(d => {
        const field = (d.loc || []).filter(x => x !== "body").join(" › ");
        return field ? field + ": " + d.msg : d.msg;
      }).join("; ");
    }
    if (data && typeof data.detail === "string") return data.detail;
    return "Something went wrong (" + status + "). Please try again.";
  }
  /* POST helper. `body` is either a plain object (sent as JSON) or FormData. */
  async function submit(url, body) {
    clearError();
    setLoading(true);
    try {
      const opts = { method: "POST", credentials: "same-origin" };
      if (body instanceof FormData) opts.body = body;
      else { opts.headers = { "Content-Type": "application/json" }; opts.body = JSON.stringify(body); }
      const res = await fetch(url, opts);
      let data = null;
      try { data = await res.json(); } catch (_) { /* non-JSON error */ }
      if (res.status === 401) { window.location.href = "/login"; return; }
      if (!res.ok) throw new Error(errorMessage(data, res.status));
      window.location.href = data.redirect;
    } catch (err) {
      showError(err.message || "Network error. Is the server running?");
      setLoading(false);
    }
  }
  return { showError, submit };
})();
