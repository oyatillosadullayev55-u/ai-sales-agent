(function () {
  "use strict";

  var script = document.currentScript || document.querySelector("script[data-ai-widget]");
  var key = script && script.getAttribute("data-ai-widget");
  if (!key) return;
  if (window.__aiSalesWidgetLoaded === key) return;
  window.__aiSalesWidgetLoaded = key;

  var origin = new URL(script.src, window.location.href).origin;
  var API = origin + "/api/v1/public/widget/" + encodeURIComponent(key);
  var categoryEmoji = {
    laptop: "💻", phone: "📱", audio: "🎧", tablet: "📓", watch: "⌚", accessory: "🖱️"
  };

  var state = {
    config: null,
    visitorId: localStorage.getItem("ai_widget_visitor_" + key) || "",
    open: false,
    loaded: false,
    busy: false,
    unread: 0,
    aiEnabled: true
  };
  if (!state.visitorId) {
    state.visitorId = (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : "v-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("ai_widget_visitor_" + key, state.visitorId);
  }

  var host = document.createElement("div");
  host.setAttribute("data-ai-sales-widget", key);
  document.body.appendChild(host);
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  var css = `
    :host, * { box-sizing: border-box; }
    .root { font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif; }
    button { font-family: inherit; cursor: pointer; }
    .launcher {
      position: fixed; right: 22px; bottom: 22px; width: 62px; height: 62px; border-radius: 50%;
      border: none; background: linear-gradient(135deg, var(--accent), #1799e8); color: #032019;
      display: grid; place-items: center; box-shadow: 0 14px 34px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.08) inset;
      transition: transform .2s ease, opacity .2s ease; z-index: 2147483000;
    }
    .launcher:hover { transform: translateY(-2px) scale(1.03); }
    .launcher svg { width: 27px; height: 27px; }
    .launcher .dot {
      position: absolute; top: -3px; right: -3px; min-width: 20px; height: 20px; padding: 0 5px;
      background: #ff5c5c; color: #fff; border-radius: 99px; font-size: 11px; font-weight: 700;
      display: grid; place-items: center; border: 2px solid #0b121c;
    }
    .panel {
      position: fixed; right: 22px; bottom: 96px; width: 382px; height: 620px; max-height: calc(100vh - 130px);
      background: #0b121c; border: 1px solid #1e2c3f; border-radius: 20px; overflow: hidden;
      display: flex; flex-direction: column; box-shadow: 0 30px 80px rgba(0,0,0,.6), 0 0 0 1px rgba(255,255,255,.03) inset;
      z-index: 2147483000; opacity: 0; transform: translateY(16px) scale(.98); pointer-events: none;
      transition: opacity .2s ease, transform .2s ease;
    }
    .panel.open { opacity: 1; transform: none; pointer-events: auto; }
    .header {
      padding: 15px 16px; display: flex; align-items: center; gap: 11px;
      background: linear-gradient(160deg, rgba(255,255,255,.05), transparent), #0e1622;
      border-bottom: 1px solid #1b2739; flex: none;
    }
    .avatar {
      width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center;
      background: linear-gradient(135deg, var(--accent), #2596f0); color: #032019; font-weight: 800; font-size: 15px;
      box-shadow: 0 6px 16px rgba(45,212,167,.25);
    }
    .head-info { flex: 1; min-width: 0; }
    .head-info strong { display: block; font-size: 13.5px; color: #eef5fc; letter-spacing: -.1px; }
    .head-info span { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #8497ad; margin-top: 3px; }
    .head-info i { width: 6px; height: 6px; border-radius: 50%; background: #2dd4a7; box-shadow: 0 0 7px rgba(45,212,167,.8); display: inline-block; }
    .head-info i.off { background: #f5b544; box-shadow: none; }
    .close {
      border: none; background: rgba(255,255,255,.04); color: #8497ad; width: 30px; height: 30px;
      border-radius: 9px; font-size: 18px; line-height: 1; display: grid; place-items: center;
    }
    .close:hover { background: rgba(255,255,255,.09); color: #eef5fc; }
    .messages {
      flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px;
      background: radial-gradient(520px 260px at 60% 0%, rgba(45,212,167,.05), transparent 70%), #0a111a;
      scroll-behavior: smooth;
    }
    .messages::-webkit-scrollbar { width: 7px; }
    .messages::-webkit-scrollbar-thumb { background: #223044; border-radius: 99px; }
    .row { display: flex; gap: 8px; max-width: 88%; }
    .row.user { align-self: flex-end; flex-direction: row-reverse; }
    .bubble {
      background: #131d2b; border: 1px solid #1e2b3d; color: #dbe7f3; padding: 10px 12px;
      border-radius: 13px; font-size: 12.8px; line-height: 1.55; white-space: pre-wrap; word-break: break-word;
    }
    .row.user .bubble {
      background: linear-gradient(135deg, rgba(45,212,167,.22), rgba(45,212,167,.1));
      border-color: rgba(45,212,167,.3); color: #dcfff6;
    }
    .row.operator .bubble { background: rgba(91,157,255,.1); border-color: rgba(91,157,255,.28); }
    .msg-avatar {
      width: 26px; height: 26px; border-radius: 8px; flex: none; display: grid; place-items: center;
      font-size: 10px; font-weight: 700; background: #182535; color: #8fa1b8; margin-top: 2px;
    }
    .meta { font-size: 9.5px; color: #5f7188; margin-top: 4px; }
    .products { display: flex; flex-direction: column; gap: 8px; margin-top: 9px; }
    .product {
      display: flex; gap: 9px; background: #101a27; border: 1px solid #1e2b3d; border-radius: 11px; padding: 9px;
      align-items: center;
    }
    .product .thumb {
      width: 40px; height: 40px; border-radius: 9px; display: grid; place-items: center;
      background: #172435; font-size: 19px; flex: none;
    }
    .product .info { flex: 1; min-width: 0; }
    .product .pname { font-size: 11.8px; font-weight: 600; color: #e7f0fa; line-height: 1.3; }
    .product .pprice { font-size: 11px; color: #2dd4a7; font-weight: 650; margin-top: 3px; }
    .product .pold { color: #5f7188; text-decoration: line-through; font-weight: 400; margin-left: 4px; }
    .product button {
      border: 1px solid rgba(45,212,167,.35); background: rgba(45,212,167,.12); color: #52e6be;
      font-size: 10.5px; font-weight: 650; padding: 6px 8px; border-radius: 7px; white-space: nowrap;
    }
    .product button:hover { background: rgba(45,212,167,.2); }
    .sources { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 9px; }
    .source {
      font-size: 9.5px; color: #7f93aa; background: #101a27; border: 1px solid #1c293a;
      border-radius: 6px; padding: 3px 6px; max-width: 100%; overflow: hidden; text-overflow: ellipsis;
      white-space: nowrap;
    }
    .order-card {
      margin-top: 9px; border: 1px solid rgba(45,212,167,.3); background: rgba(45,212,167,.07);
      border-radius: 10px; padding: 9px 11px; font-size: 11px; color: #b9e9dc;
    }
    .order-card b { color: #52e6be; }
    .quick { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 14px 2px; flex: none; background: #0a111a; }
    .quick button {
      border: 1px solid #223145; background: #101a27; color: #a8bacd; font-size: 10.8px;
      padding: 6px 9px; border-radius: 99px;
    }
    .quick button:hover { border-color: rgba(45,212,167,.4); color: #52e6be; }
    .composer {
      display: flex; gap: 7px; align-items: flex-end; padding: 10px 12px 8px; background: #0a111a; flex: none;
    }
    .composer textarea {
      flex: 1; resize: none; background: #101a27; border: 1px solid #223145; border-radius: 11px;
      color: #e8f1fb; padding: 10px 11px; font-size: 12.5px; line-height: 1.4; outline: none;
      min-height: 40px; max-height: 110px; font-family: inherit;
    }
    .composer textarea:focus { border-color: rgba(45,212,167,.45); }
    .composer textarea::placeholder { color: #5f7188; }
    .send {
      width: 40px; height: 40px; border-radius: 11px; border: none; display: grid; place-items: center;
      background: linear-gradient(135deg, var(--accent), #1aa9e0); color: #032019; flex: none;
    }
    .send:disabled { opacity: .45; cursor: not-allowed; }
    .send svg { width: 17px; height: 17px; }
    .foot {
      text-align: center; font-size: 9.5px; color: #4d5f75; padding: 0 0 8px; background: #0a111a;
      letter-spacing: .2px;
    }
    .typing { display: flex; gap: 4px; padding: 4px 2px; }
    .typing i {
      width: 6px; height: 6px; border-radius: 50%; background: #4f647c; animation: bounce 1.1s infinite;
    }
    .typing i:nth-child(2) { animation-delay: .15s; }
    .typing i:nth-child(3) { animation-delay: .3s; }
    @keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-4px); opacity: 1; } }
    .notice { text-align: center; font-size: 10.5px; color: #f5b544; background: rgba(245,181,68,.08); border: 1px solid rgba(245,181,68,.2); padding: 7px 10px; border-radius: 9px; }
    @media (max-width: 520px) {
      .panel { right: 0; bottom: 0; width: 100%; height: 100%; max-height: 100%; border-radius: 0; border: none; }
      .launcher { right: 16px; bottom: 16px; }
    }
  `;

  var style = document.createElement("style");
  style.textContent = css;
  root.appendChild(style);

  var wrap = document.createElement("div");
  wrap.className = "root";
  wrap.innerHTML =
    '<button class="launcher" aria-label="Chatni ochish">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.7 8.7 0 0 1-4-.9L3 21l1.9-4.9a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 8.5-8.5 8.4 8.4 0 0 1 8.5 7.7z"/></svg>' +
    '<span class="dot" hidden>0</span></button>' +
    '<div class="panel" role="dialog" aria-label="AI chat">' +
    '  <div class="header">' +
    '    <div class="avatar">N</div>' +
    '    <div class="head-info"><strong class="h-title">AI yordamchi</strong>' +
    '      <span><i></i><span class="h-sub">onlayn</span></span></div>' +
    '    <button class="close" aria-label="Yopish">×</button>' +
    "  </div>" +
    '  <div class="messages"></div>' +
    '  <div class="quick"></div>' +
    '  <form class="composer"><textarea rows="1" placeholder="Xabar yozing..."></textarea>' +
    '    <button class="send" type="submit" aria-label="Yuborish"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/></svg></button>' +
    "  </form>" +
    '  <div class="foot">AI Sales Agent</div>' +
    "</div>";
  root.appendChild(wrap);

  var els = {
    launcher: wrap.querySelector(".launcher"),
    dot: wrap.querySelector(".launcher .dot"),
    panel: wrap.querySelector(".panel"),
    title: wrap.querySelector(".h-title"),
    sub: wrap.querySelector(".h-sub"),
    statusDot: wrap.querySelector(".head-info i"),
    close: wrap.querySelector(".close"),
    messages: wrap.querySelector(".messages"),
    quick: wrap.querySelector(".quick"),
    form: wrap.querySelector(".composer"),
    input: wrap.querySelector("textarea"),
    send: wrap.querySelector(".send")
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function money(value) {
    return String(Math.round(Number(value) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function scrollDown() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function productHtml(product) {
    var old = product.old_price
      ? '<span class="pold">' + money(product.old_price) + "</span>" : "";
    return (
      '<div class="product">' +
      '<div class="thumb">' + (categoryEmoji[product.category] || "📦") + "</div>" +
      '<div class="info"><div class="pname">' + escapeHtml(product.name) + "</div>" +
      '<div class="pprice">' + money(product.price) + " so'm " + old + "</div></div>" +
      '<button data-buy="' + escapeHtml(product.name) + '">Sotib olish</button>' +
      "</div>"
    );
  }

  function addMessage(role, text, extra) {
    extra = extra || {};
    var row = document.createElement("div");
    row.className = "row " + role;
    var avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = role === "user" ? "Siz" : role === "operator" ? "OP" : "AI";
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    var html = escapeHtml(text);
    if (extra.products && extra.products.length) {
      html += '<div class="products">' + extra.products.map(productHtml).join("") + "</div>";
    }
    if (extra.sources && extra.sources.length) {
      html += '<div class="sources">' + extra.sources.map(function (source) {
        var label = source.document_name || "Hujjat";
        return '<span class="source" title="' + escapeHtml(label) + '">📄 ' +
          escapeHtml(label) + (source.chunk_index != null ? " · §" + (source.chunk_index + 1) : "") + "</span>";
      }).join("") + "</div>";
    }
    if (extra.order && extra.order.number) {
      html += '<div class="order-card">Buyurtma <b>' + escapeHtml(extra.order.number) +
        "</b> qabul qilindi · " + money(extra.order.total) + " so'm</div>";
    }
    bubble.innerHTML = html;
    var meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    bubble.appendChild(meta);
    row.appendChild(avatar);
    row.appendChild(bubble);
    els.messages.appendChild(row);
    scrollDown();
  }

  function showQuick(items) {
    els.quick.innerHTML = "";
    (items || []).slice(0, 4).forEach(function (label) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", function () { send(label); });
      els.quick.appendChild(button);
    });
  }

  function showTyping() {
    var row = document.createElement("div");
    row.className = "row";
    row.dataset.typing = "1";
    row.innerHTML = '<div class="msg-avatar">AI</div><div class="bubble"><div class="typing"><i></i><i></i><i></i></div></div>';
    els.messages.appendChild(row);
    scrollDown();
  }

  function removeTyping() {
    var node = els.messages.querySelector('[data-typing="1"]');
    if (node) node.remove();
  }

  function setBusy(value) {
    state.busy = value;
    els.send.disabled = value;
  }

  function setAiEnabled(value) {
    state.aiEnabled = value;
    els.input.disabled = !value;
    els.send.disabled = !value || state.busy;
    els.input.placeholder = value ? "Xabar yozing..." : "Operator javob bermoqda...";
    els.statusDot.className = value ? "" : "off";
    els.sub.textContent = value ? (state.config ? state.config.org_name + " · AI onlayn" : "AI onlayn") : "Operator rejimida";
  }

  async function sha() {
    try {
      return await fetch(API + "/history?visitor_id=" + encodeURIComponent(state.visitorId)).then(function (r) {
        return r.ok ? r.json() : { messages: [] };
      });
    } catch (error) {
      return { messages: [] };
    }
  }

  async function loadHistory() {
    state.loaded = true;
    var data = await sha();
    if (data.messages && data.messages.length) {
      data.messages.forEach(function (message) {
        var meta = message.meta || {};
        if (message.role === "user") addMessage("user", message.content);
        else addMessage(message.role === "operator" ? "operator" : "assistant", message.content, {
          products: meta.products || [],
          sources: meta.sources || []
        });
      });
      if (typeof data.ai_enabled === "boolean") setAiEnabled(data.ai_enabled);
    } else {
      addMessage("assistant", state.config ? state.config.greeting : "Assalomu alaykum! Sizga qanday yordam beraman?");
      showQuick(["Noutbuk kerak", "Narxlar", "Yetkazib berish", "Operator"]);
    }
    scrollDown();
  }

  async function send(text) {
    if (state.busy || !state.aiEnabled) return;
    text = (text || "").trim();
    if (!text) return;
    addMessage("user", text);
    els.input.value = "";
    els.input.style.height = "auto";
    showQuick([]);
    setBusy(true);
    showTyping();
    try {
      var response = await fetch(API + "/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_id: state.visitorId, text: text })
      });
      var data = await response.json().catch(function () { return {}; });
      removeTyping();
      if (!response.ok) {
        var detail = data.detail;
        if (typeof detail === "object" && detail) detail = detail.message || "Xatolik yuz berdi";
        addMessage("assistant", detail || "Xatolik yuz berdi. Qayta urinib ko'ring.");
        return;
      }
      addMessage("assistant", data.text, {
        products: data.products || [],
        sources: data.sources || [],
        order: data.order || null
      });
      showQuick(data.quick || []);
      if (data.ai_enabled === false) setAiEnabled(false);
      if (!state.open) {
        state.unread += 1;
        els.dot.hidden = false;
        els.dot.textContent = String(state.unread);
      }
    } catch (error) {
      removeTyping();
      addMessage("assistant", "Aloqa xatosi. Internetni tekshirib, qayta urinib ko'ring.");
    } finally {
      setBusy(false);
      if (!state.aiEnabled) els.input.disabled = true;
    }
  }

  function openPanel() {
    state.open = true;
    els.panel.classList.add("open");
    els.launcher.hidden = true;
    els.dot.hidden = true;
    state.unread = 0;
    if (!state.loaded) loadHistory();
    setTimeout(function () { els.input.focus(); }, 180);
  }

  function closePanel() {
    state.open = false;
    els.panel.classList.remove("open");
    els.launcher.hidden = false;
  }

  els.launcher.addEventListener("click", openPanel);
  els.close.addEventListener("click", closePanel);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && state.open) closePanel();
  });
  els.form.addEventListener("submit", function (event) {
    event.preventDefault();
    send(els.input.value);
  });
  els.input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send(els.input.value);
    }
  });
  els.input.addEventListener("input", function () {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(110, els.input.scrollHeight) + "px";
  });
  els.messages.addEventListener("click", function (event) {
    var button = event.target.closest("[data-buy]");
    if (button) send(button.getAttribute("data-buy") + " ni sotib olmoqchiman");
  });

  window.AISalesWidget = window.AISalesWidget || {};
  window.AISalesWidget[key] = {
    open: openPanel,
    close: closePanel,
    send: send,
    prefill: function (text) {
      openPanel();
      els.input.value = text || "";
      els.input.focus();
    }
  };

  fetch(API + "/config")
    .then(function (response) { return response.ok ? response.json() : null; })
    .then(function (config) {
      if (!config) return;
      state.config = config;
      els.title.textContent = config.title || "AI yordamchi";
      els.sub.textContent = (config.org_name || "") + " · AI onlayn";
      els.panel.style.setProperty("--accent", config.color || "#2dd4a7");
      if (!state.loaded) {
        setTimeout(function () {
          if (!state.loaded) loadHistory();
        }, 300);
      }
    })
    .catch(function () {});
})();
