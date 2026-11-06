(function () {
  "use strict";

  var API = "/api/v1";
  var STORE = {
    access: "aisales_access",
    refresh: "aisales_refresh",
    org: "aisales_org",
    orgName: "aisales_org_name"
  };

  var $ = function (selector) { return document.querySelector(selector); };

  function setError(container, message) {
    var box = container.querySelector("[data-error]");
    if (!box) return;
    box.textContent = message || "";
    box.classList.toggle("hidden", !message);
  }

  function saving(form, value) {
    var button = form.querySelector('button[type="submit"]');
    if (!button) return;
    button.disabled = value;
    if (value) {
      button.dataset.label = button.textContent;
      button.textContent = "Kuting...";
    } else if (button.dataset.label) {
      button.textContent = button.dataset.label;
    }
  }

  function detailMessage(data, fallback) {
    if (!data) return fallback;
    var detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail.map(function (item) { return item.msg || String(item); }).join(", ");
    }
    if (detail && typeof detail === "object") return detail.message || fallback;
    return fallback;
  }

  async function request(path, options) {
    options = options || {};
    var response = await fetch(API + path, {
      method: options.method || "GET",
      headers: Object.assign({ "Content-Type": "application/json" }, options.headers || {}),
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    var data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    if (!response.ok) {
      var failure = new Error(detailMessage(data, "So'rov bajarilmadi (" + response.status + ")"));
      failure.status = response.status;
      throw failure;
    }
    return data;
  }

  function storeSession(data) {
    localStorage.setItem(STORE.access, data.access_token);
    localStorage.setItem(STORE.refresh, data.refresh_token);
    if (data.org) {
      localStorage.setItem(STORE.org, data.org.id);
      localStorage.setItem(STORE.orgName, data.org.name);
    } else {
      localStorage.removeItem(STORE.org);
      localStorage.removeItem(STORE.orgName);
    }
  }

  function showTab(name) {
    document.querySelectorAll(".tabs button").forEach(function (button) {
      button.classList.toggle("active", button.dataset.tab === name);
    });
    $("#login-view").classList.toggle("hidden", name !== "login");
    $("#register-view").classList.toggle("hidden", name !== "register");
    $("#forgot-view").classList.add("hidden");
  }

  function showForgot() {
    $("#login-view").classList.add("hidden");
    $("#register-view").classList.add("hidden");
    $("#forgot-view").classList.remove("hidden");
  }

  function redirect() {
    window.location.href = "/dashboard";
  }

  document.querySelectorAll(".tabs button").forEach(function (button) {
    button.addEventListener("click", function () {
      showTab(button.dataset.tab);
      if (window.location.hash !== "#" + button.dataset.tab) {
        history.replaceState(null, "", button.dataset.tab === "login" ? "/login" : "/login#register");
      }
    });
  });

  if (window.location.hash === "#register") showTab("register");
  var forgotButton = document.querySelector("[data-forgot]");
  if (forgotButton) forgotButton.addEventListener("click", showForgot);
  var backButton = document.querySelector("[data-back]");
  if (backButton) backButton.addEventListener("click", function () { showTab("login"); });

  $("#login-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var form = event.currentTarget;
    setError(form, "");
    saving(form, true);
    try {
      var data = await request("/auth/login", {
        method: "POST",
        body: {
          email: $("#login-email").value.trim(),
          password: $("#login-password").value
        }
      });
      storeSession(data);
      redirect();
    } catch (error) {
      setError(form, error.message);
      saving(form, false);
    }
  });

  $("#register-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var form = event.currentTarget;
    setError(form, "");
    saving(form, true);
    try {
      var data = await request("/auth/register", {
        method: "POST",
        body: {
          org_name: $("#reg-org").value.trim(),
          full_name: $("#reg-name").value.trim(),
          email: $("#reg-email").value.trim(),
          password: $("#reg-password").value
        }
      });
      storeSession(data);
      redirect();
    } catch (error) {
      setError(form, error.message);
      saving(form, false);
    }
  });

  $("#forgot-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var form = event.currentTarget;
    setError(form, "");
    saving(form, true);
    try {
      var data = await request("/auth/forgot-password", {
        method: "POST",
        body: { email: $("#forgot-email").value.trim() }
      });
      form.classList.add("hidden");
      $("#reset-form").classList.remove("hidden");
      if (data.reset_token) {
        $("#reset-token").value = data.reset_token;
      }
      var previous = form.parentNode.querySelector(".forgot-note");
      if (previous) previous.remove();
      var note = document.createElement("div");
      note.className = "form-error forgot-note";
      note.style.cssText = "background:rgba(45,212,167,.08);border-color:rgba(45,212,167,.25);color:#8fe8d0";
      note.textContent = data.reset_token
        ? "Dev rejim: tiklash kodi avtomatik to'ldirildi. Yangi parolni kiriting."
        : (data.message || "Kod yuborildi.");
      form.parentNode.insertBefore(note, $("#reset-form"));
    } catch (error) {
      setError(form, error.message);
      saving(form, false);
    }
  });

  $("#reset-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var form = event.currentTarget;
    saving(form, true);
    try {
      await request("/auth/reset-password", {
        method: "POST",
        body: {
          token: $("#reset-token").value.trim(),
          password: $("#reset-password").value
        }
      });
      alert("Parol yangilandi. Endi yangi parol bilan kiring.");
      window.location.href = "/login";
    } catch (error) {
      alert(error.message);
      saving(form, false);
    }
  });

  (async function boot() {
    var token = localStorage.getItem(STORE.access);
    if (!token) return;
    try {
      var response = await fetch(API + "/auth/me", {
        headers: { Authorization: "Bearer " + token }
      });
      if (response.ok) redirect();
      else localStorage.removeItem(STORE.access);
    } catch (error) { /* offline: stay on login */ }
  })();
})();
