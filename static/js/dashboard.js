(function () {
  "use strict";

  var API = "/api/v1";
  var STORE = {
    access: "aisales_access",
    refresh: "aisales_refresh",
    org: "aisales_org",
    orgName: "aisales_org_name"
  };
  var RANK = { operator: 1, manager: 2, owner: 3, super: 4 };
  var MIN_ROLE = {
    overview: 1,
    conversations: 1,
    analytics: 1,
    products: 1,
    orders: 1,
    knowledge: 2,
    settings: 2,
    integrations: 3,
    team: 2,
    billing: 3,
    platform: 4
  };
  var TITLES = {
    overview: ["Umumiy ko'rinish", "Ish maydoni"],
    conversations: ["Suhbatlar", "Mijozlar bilan muloqot"],
    analytics: ["Analitika", "Sotuv ko'rsatkichlari"],
    products: ["Mahsulotlar", "Katalog"],
    orders: ["Buyurtmalar", "Sotuvlar"],
    knowledge: ["Bilimlar bazasi", "AI manbalari"],
    settings: ["AI agent sozlamalari", "Bilim va AI"],
    integrations: ["Integratsiyalar", "Telegram va sayt widgeti"],
    team: ["Jamoa", "Xodimlar va rollar"],
    billing: ["Tarif va to'lovlar", "Obuna"],
    platform: ["Platforma", "Super admin"]
  };
  var CHANNEL = {
    widget: { label: "Sayt", icon: "🌐" },
    telegram: { label: "Telegram", icon: "✈️" }
  };
  var ORDER_STATUS = {
    pending: ["Yangi", "amber"],
    confirmed: ["Tasdiqlandi", "blue"],
    processing: ["Yetkazilmoqda", "blue"],
    delivered: ["Yetkazildi", ""],
    cancelled: ["Bekor qilindi", "red"]
  };
  var ICONS = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    chat: '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.7 8.7 0 0 1-4-.9L3 21l1.9-4.9a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 8.5-8.5 8.4 8.4 0 0 1 8.5 7.7z"/>',
    chart: '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-7"/>',
    box: '<path d="m21 8-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
    cart: '<circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/><path d="M2 3h3l2.6 12.4a2 2 0 0 0 2 1.6h8.7a2 2 0 0 0 2-1.6L22 7H6"/>',
    book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    bot: '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V4"/><circle cx="9" cy="14" r="1"/><circle cx="15" cy="14" r="1"/><path d="M9 17h6"/>',
    plug: '<path d="M9 2v6"/><path d="M15 2v6"/><path d="M6 8h12v4a6 6 0 0 1-12 0V8z"/><path d="M12 18v4"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 21a6.5 6.5 0 0 1 13 0"/><path d="M17 5a3 3 0 0 1 0 6"/><path d="M19 21a5.5 5.5 0 0 0-3-5"/>',
    card: '<rect x="2" y="5" width="20" height="14" rx="2.5"/><path d="M2 10h20"/>',
    shield: '<path d="M12 2 20 5v6c0 5-3.4 8.7-8 11-4.6-2.3-8-6-8-11V5l8-3z"/><path d="m8.5 12 2.5 2.5 4.5-4.5"/>'
  };

  var state = {
    token: localStorage.getItem(STORE.access) || "",
    refresh: localStorage.getItem(STORE.refresh) || "",
    orgId: localStorage.getItem(STORE.org) || "",
    user: null,
    me: null,
    role: "operator",
    view: "",
    timer: null,
    conversations: [],
    activeConversation: "",
    products: [],
    analyticsDays: 30
  };

  var $ = function (selector, root) { return (root || document).querySelector(selector); };
  var $$ = function (selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); };

  function h(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function money(value, currency) {
    var amount = Number(value) || 0;
    var formatted = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.round(amount));
    return formatted + " " + (currency || "so'm");
  }

  function num(value) {
    return new Intl.NumberFormat("ru-RU").format(Number(value) || 0);
  }

  function dt(iso) {
    if (!iso) return "—";
    var date = new Date(iso);
    return date.toLocaleString("uz-UZ", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
    });
  }

  function ago(iso) {
    if (!iso) return "";
    var diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60) return "hozir";
    if (diff < 3600) return Math.floor(diff / 60) + " daq";
    if (diff < 86400) return Math.floor(diff / 3600) + " soat";
    return Math.floor(diff / 86400) + " kun";
  }

  function initials(name) {
    return (name || "?").trim().split(/\s+/).slice(0, 2).map(function (part) {
      return part.charAt(0).toUpperCase();
    }).join("") || "?";
  }

  function badge(text, tone) {
    return '<span class="badge ' + (tone || "") + '">' + h(text) + "</span>";
  }

  function rank(role) { return RANK[role] || 0; }
  function can(role) { return rank(state.role) >= rank(role); }

  function toast(message, isError) {
    var stack = $("#toast-stack");
    var item = document.createElement("div");
    item.className = "toast" + (isError ? " error" : "");
    item.textContent = message;
    stack.appendChild(item);
    setTimeout(function () { item.remove(); }, 4200);
  }

  function errorText(data, fallback) {
    if (!data) return fallback;
    var detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map(function (item) { return item.msg || String(item); }).join(", ");
    if (detail && typeof detail === "object") return detail.message || fallback;
    return fallback;
  }

  function saveSession(data) {
    state.token = data.access_token;
    state.refresh = data.refresh_token;
    localStorage.setItem(STORE.access, state.token);
    localStorage.setItem(STORE.refresh, state.refresh);
    if (data.role) state.role = data.role;
    if (data.org) {
      state.orgId = data.org.id;
      localStorage.setItem(STORE.org, data.org.id);
      localStorage.setItem(STORE.orgName, data.org.name);
    }
  }

  function logout() {
    var refresh = state.refresh;
    if (refresh) {
      fetch(API + "/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh })
      }).catch(function () {});
    }
    localStorage.removeItem(STORE.access);
    localStorage.removeItem(STORE.refresh);
    localStorage.removeItem(STORE.org);
    localStorage.removeItem(STORE.orgName);
    window.location.href = "/login";
  }

  async function rawRequest(path, options) {
    options = options || {};
    var headers = Object.assign({ Authorization: "Bearer " + state.token }, options.headers || {});
    if (state.orgId) headers["X-Org-Id"] = state.orgId;
    if (options.body !== undefined && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    var response = await fetch(API + path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body instanceof FormData
        ? options.body
        : options.body !== undefined ? JSON.stringify(options.body) : undefined
    });
    var data = null;
    if (response.status !== 204) {
      try { data = await response.json(); } catch (error) { data = null; }
    }
    return { ok: response.ok, status: response.status, data: data };
  }

  async function api(path, options) {
    options = options || {};
    var result = await rawRequest(path, options);
    if (result.status === 401 && state.refresh) {
      var refreshed = await fetch(API + "/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: state.refresh })
      });
      if (refreshed.ok) {
        saveSession(await refreshed.json());
        result = await rawRequest(path, options);
      } else {
        logout();
        throw new Error("Sessiya tugadi. Qaytadan kiring.");
      }
    }
    if (!result.ok) {
      var failure = new Error(errorText(result.data, "Xatolik (" + result.status + ")"));
      failure.status = result.status;
      failure.data = result.data;
      throw failure;
    }
    return result.data;
  }

  /* ------------------------------------------------------------------ */
  /* Layout helpers                                                      */
  /* ------------------------------------------------------------------ */
  function kpi(label, value, hint, icon, highlight) {
    return '<div class="kpi' + (highlight ? " hl" : "") + '">' +
      '<div class="label">' + h(label) + "</div>" +
      '<div class="value">' + h(value) + "</div>" +
      '<div class="delta">' + h(hint || "") + "</div>" +
      '<div class="ico">' + (icon || "◆") + "</div>" +
      "</div>";
  }

  function empty(icon, title, text, action) {
    return '<div class="empty"><div class="big">' + icon + "</div><p><strong>" + h(title) +
      "</strong></p><p>" + h(text || "") + "</p>" + (action || "") + "</div>";
  }

  function loading() {
    return '<div class="empty"><div class="loader" style="margin:0 auto"></div><p>Yuklanmoqda...</p></div>';
  }

  function errorState(error) {
    return empty("⚠️", "Ma'lumot yuklanmadi", error.message || String(error),
      '<button class="btn" data-retry>Qayta urinish</button>');
  }

  function pageHead(title, text, actions) {
    return '<div class="page-head"><div><h2>' + h(title) + "</h2><p>" + h(text || "") +
      "</p></div><div class=\"row\">" + (actions || "") + "</div></div>";
  }

  function statusBadge(status) {
    var entry = ORDER_STATUS[status];
    return entry ? badge(entry[0], entry[1]) : badge(status, "muted");
  }

  function docBadge(status) {
    if (status === "ready") return badge("Tayyor", "");
    if (status === "processing") return badge("Ishlanmoqda", "amber");
    return badge("Xato", "red");
  }

  /* ------------------------------------------------------------------ */
  /* Chart                                                               */
  /* ------------------------------------------------------------------ */
  function chart(series) {
    if (!series || !series.length) return empty("📈", "Ma'lumot yo'q", "Tanlangan davrda suhbatlar bo'lmagan.");
    var width = 680, height = 220, left = 34, right = 12, top = 14, bottom = 26;
    var innerW = width - left - right, innerH = height - top - bottom;
    var maxConv = Math.max.apply(null, series.map(function (item) { return item.conversations; }).concat([1]));
    var maxOrders = Math.max.apply(null, series.map(function (item) { return item.orders; }).concat([1]));
    var stepX = innerW / Math.max(1, series.length - 1);
    var barW = Math.max(2, Math.min(18, innerW / series.length * 0.55));
    var points = series.map(function (item, index) {
      return {
        x: left + index * stepX,
        y: top + innerH - (item.orders / maxOrders) * innerH,
        c: item.conversations
      };
    });
    var line = points.map(function (point) { return point.x.toFixed(1) + "," + point.y.toFixed(1); }).join(" ");
    var area = left + "," + (top + innerH) + " " + line + " " + (left + innerW) + "," + (top + innerH);
    var grid = "";
    for (var i = 0; i <= 4; i += 1) {
      var y = top + (innerH / 4) * i;
      grid += '<line class="grid-line" x1="' + left + '" y1="' + y + '" x2="' + (width - right) + '" y2="' + y + '"/>';
      grid += '<text class="axis-text" x="' + (left - 7) + '" y="' + (y + 3) + '" text-anchor="end">' +
        Math.round(maxConv - (maxConv / 4) * i) + "</text>";
    }
    var bars = points.map(function (point, index) {
      var value = series[index].conversations;
      var barH = (value / maxConv) * innerH;
      return '<rect class="bar" x="' + (point.x - barW / 2).toFixed(1) + '" y="' + (top + innerH - barH).toFixed(1) +
        '" width="' + barW.toFixed(1) + '" height="' + barH.toFixed(1) + '" rx="2"><title>' +
        h(series[index].date + ": " + value + " suhbat") + "</title></rect>";
    }).join("");
    var labelEvery = Math.max(1, Math.ceil(series.length / 7));
    var labels = series.map(function (item, index) {
      if (index % labelEvery !== 0 && index !== series.length - 1) return "";
      return '<text class="axis-text" x="' + (left + index * stepX).toFixed(1) + '" y="' + (height - 8) +
        '" text-anchor="middle">' + h(item.date.slice(5)) + "</text>";
    }).join("");
    return '<div class="chart"><svg viewBox="0 0 ' + width + " " + height + '" preserveAspectRatio="none">' +
      '<defs><linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1">' +
      '<stop offset="0%" stop-color="#2dd4a7" stop-opacity=".28"/><stop offset="100%" stop-color="#2dd4a7" stop-opacity="0"/>' +
      "</linearGradient></defs>" + grid + bars +
      '<polygon class="area" points="' + area + '"/>' +
      '<polyline class="line" points="' + line + '"/>' +
      points.map(function (point) {
        return '<circle cx="' + point.x.toFixed(1) + '" cy="' + point.y.toFixed(1) + '" r="2.4" fill="#2dd4a7"/>';
      }).join("") + labels + "</svg></div>" +
      '<div class="chart-legend"><span><i style="background:#2dd4a7"></i>Suhbatlar</span>' +
      '<span><i style="background:#5b9dff;border-radius:50%"></i>Buyurtmalar</span></div>';
  }

  /* ------------------------------------------------------------------ */
  /* Modal                                                               */
  /* ------------------------------------------------------------------ */
  function openModal(title, bodyHtml, footerHtml, wide) {
    closeModal();
    var root = $("#modal-root");
    root.innerHTML = '<div class="modal-backdrop"><div class="modal" style="max-width:' +
      (wide ? "760px" : "520px") + '">' +
      '<div class="modal-head"><h3>' + h(title) + '</h3><button class="close-x" data-close>×</button></div>' +
      '<div class="modal-body">' + bodyHtml + "</div>" +
      (footerHtml ? '<div class="modal-foot">' + footerHtml + "</div>" : "") +
      "</div></div>";
    root.querySelector(".modal-backdrop").addEventListener("click", function (event) {
      if (event.target.classList.contains("modal-backdrop")) closeModal();
    });
    $$("[data-close]", root).forEach(function (button) {
      button.addEventListener("click", closeModal);
    });
    return root.querySelector(".modal");
  }

  function closeModal() {
    $("#modal-root").innerHTML = "";
  }

  function confirmModal(title, text, onConfirm, danger) {
    var modal = openModal(title, '<p class="muted" style="margin:0;line-height:1.6">' + h(text) + "</p>",
      '<button class="btn" data-close>Bekor qilish</button>' +
      '<button class="btn ' + (danger ? "danger" : "primary") + '" data-confirm>Tasdiqlash</button>');
    $("[data-confirm]", modal).addEventListener("click", async function () {
      try { await onConfirm(); closeModal(); } catch (error) { toast(error.message, true); }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Overview                                                            */
  /* ------------------------------------------------------------------ */
  async function renderOverview() {
    var view = $("#view");
    view.innerHTML = loading();
    try {
      var data = await api("/analytics/overview?days=30");
      var maxChannel = Math.max.apply(null, Object.values(data.by_channel).concat([1]));
      view.innerHTML = pageHead("Umumiy ko'rinish", "Oxirgi 30 kun natijalari",
        '<a class="btn sm" href="#conversations">Suhbatlarni ochish →</a>') +
        '<div class="kpis">' +
        kpi("Suhbatlar", num(data.conversations), data.range_days + " kun", "💬") +
        kpi("Buyurtmalar", num(data.orders), "konversiya " + data.conversion_rate + "%", "🛒", true) +
        kpi("Tushum", money(data.revenue), "bekor qilinganlarsiz", "💰") +
        kpi("AI javoblari", num(data.ai_messages), "o'rtacha " + (data.avg_response_ms || 0) + " ms", "🤖") +
        kpi("Handoff", num(data.handoffs), "operatorga o'tkazildi", "🙋") +
        "</div>" +
        '<div class="grid-2">' +
        '<div class="card"><div class="card-head"><h3>Suhbatlar va buyurtmalar dinamikasi</h3>' +
        '<span class="hint">30 kun</span></div>' + chart(data.series) + "</div>" +
        '<div class="stack">' +
        '<div class="card"><div class="card-head"><h3>Kanallar</h3></div>' +
        (Object.keys(data.by_channel).length
          ? '<div class="list">' + Object.keys(data.by_channel).map(function (channel) {
              var info = CHANNEL[channel] || { label: channel, icon: "•" };
              var value = data.by_channel[channel];
              return '<div class="list-item"><div class="channel-ico">' + info.icon + "</div>" +
                '<div class="grow"><div class="title">' + h(info.label) + "</div>" +
                '<div class="usage-bar" style="margin-top:6px"><span style="width:' +
                Math.round((value / maxChannel) * 100) + '%"></span></div></div>' +
                '<div class="time">' + num(value) + " ta</div></div>";
            }).join("") + "</div>"
          : '<p class="muted small">Hali suhbat yo\'q</p>') +
        "</div>" +
        '<div class="card"><div class="card-head"><h3>Top mahsulotlar</h3></div>' +
        (data.top_products.length
          ? '<div class="list">' + data.top_products.map(function (product, index) {
              return '<div class="list-item"><div class="channel-ico" style="color:var(--accent)">' +
                (index + 1) + "</div><div class=\"grow\"><div class=\"title\">" + h(product.name) +
                '</div><div class="sub">' + product.qty + " dona</div></div>" +
                '<div class="time mono">' + money(product.revenue) + "</div></div>";
            }).join("") + "</div>"
          : '<p class="muted small">Buyurtmalar hali yo\'q</p>') +
        "</div></div></div>" +
        '<div class="card" style="margin-top:18px"><div class="card-head"><h3>So\'nggi suhbatlar</h3>' +
        '<a class="btn sm ghost" href="#conversations">Barchasi</a></div>' +
        (data.recent_conversations.length
          ? '<div class="list">' + data.recent_conversations.map(function (conversation) {
              var info = CHANNEL[conversation.channel] || { icon: "•" };
              return '<div class="list-item" style="cursor:pointer" data-open-conv="' + h(conversation.id) + '">' +
                '<div class="channel-ico">' + info.icon + "</div>" +
                '<div class="grow"><div class="title">' + h(conversation.customer_name) +
                (conversation.is_handoff ? ' <span class="badge amber">Operator</span>' : "") +
                '</div><div class="sub">' + h(conversation.last_message) + "</div></div>" +
                '<div class="time">' + ago(conversation.last_message_at) + "</div></div>";
            }).join("") + "</div>"
          : empty("💬", "Suhbatlar yo'q", "Birinchi mijoz xabarini kuting yoki demo widgetni sinab ko'ring.")) +
        "</div>";

      $$("[data-open-conv]", view).forEach(function (row) {
        row.addEventListener("click", function () {
          state.activeConversation = row.dataset.openConv;
          location.hash = "#conversations";
        });
      });
    } catch (error) {
      view.innerHTML = errorState(error);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Conversations                                                       */
  /* ------------------------------------------------------------------ */
  async function renderConversations() {
    var view = $("#view");
    view.innerHTML = pageHead("Suhbatlar", "AI va operator muloqoti",
      '<button class="btn sm" data-refresh-conv>↻ Yangilash</button>') +
      '<div class="conv-layout">' +
      '<div class="card conv-list" id="conv-list">' + loading() + "</div>" +
      '<div class="card conv-detail" id="conv-detail">' +
      empty("💬", "Suhbatni tanlang", "Chap tomondagi ro'yxatdan mijozni tanlang.") +
      "</div></div>";

    $("[data-refresh-conv]", view).addEventListener("click", function () { loadConversationList(true); });
    await loadConversationList();

    if (state.activeConversation) {
      loadConversation(state.activeConversation);
    }
  }

  async function loadConversationList(selectFirst) {
    var list = $("#conv-list");
    if (!list) return;
    try {
      var conversations = await api("/conversations?limit=80");
      state.conversations = conversations;
      if (!conversations.length) {
        list.innerHTML = empty("💬", "Suhbatlar yo'q", "Mijozlar yozganda shu yerda paydo bo'ladi.");
        return;
      }
      list.innerHTML = conversations.map(function (conversation) {
        var info = CHANNEL[conversation.channel] || { icon: "•" };
        return '<button class="conv-item' + (conversation.id === state.activeConversation ? " active" : "") +
          '" data-conv="' + h(conversation.id) + '">' +
          '<div class="channel-ico">' + info.icon + "</div>" +
          '<div class="body"><div class="top"><span class="name">' + h(conversation.customer_name) + "</span>" +
          '<span class="stamp">' + ago(conversation.last_message_at) + "</span></div>" +
          '<div class="preview">' + h(conversation.last_message || "Xabar yo'q") + "</div>" +
          '<div style="margin-top:6px" class="row">' +
          (conversation.is_handoff ? badge("Operator", "amber") : badge("AI", "")) +
          (conversation.ai_enabled ? "" : badge("AI o'chirilgan", "muted")) +
          "</div></div></button>";
      }).join("");
      $$("[data-conv]", list).forEach(function (item) {
        item.addEventListener("click", function () {
          state.activeConversation = item.dataset.conv;
          $$(".conv-item", list).forEach(function (node) { node.classList.toggle("active", node === item); });
          loadConversation(item.dataset.conv);
        });
      });
      if (!state.activeConversation && selectFirst !== false) {
        state.activeConversation = conversations[0].id;
        loadConversation(conversations[0].id);
      }
    } catch (error) {
      list.innerHTML = errorState(error);
    }
  }

  async function loadConversation(id, silent) {
    var detail = $("#conv-detail");
    if (!detail) return;
    if (!silent) detail.innerHTML = loading();
    try {
      var data = await api("/conversations/" + encodeURIComponent(id));
      var conversation = data.conversation;
      var channel = CHANNEL[conversation.channel] || { label: conversation.channel, icon: "•" };
      var live = $("#reply-text");
      var draft = live ? live.value : "";
      var focused = live && document.activeElement === live;
      var caret = live ? [live.selectionStart, live.selectionEnd] : null;
      detail.innerHTML =
        '<div class="conv-detail-head">' +
        '<div class="channel-ico">' + channel.icon + "</div>" +
        '<div class="grow"><h3>' + h(conversation.customer_name) + " " +
        (conversation.is_handoff ? badge("Operator", "amber") : badge("AI", "")) + "</h3>" +
        '<div class="sub">' + channel.label + " · " + h(conversation.external_id) + " · " +
        h(conversation.handoff_reason || "AI javob bermoqda") + "</div></div>" +
        (conversation.ai_enabled
          ? '<button class="btn sm" data-handoff>Operatorga topshirish</button>'
          : '<button class="btn sm primary" data-resume>AI ni qayta yoqish</button>') +
        "</div>" +
        '<div class="thread" id="thread">' +
        (data.messages.length
          ? data.messages.map(messageHtml).join("")
          : empty("💬", "Xabar yo'q", "")) +
        "</div>" +
        '<form class="reply-box" id="reply-form">' +
        '<textarea id="reply-text" placeholder="' +
        (conversation.ai_enabled ? "Operator sifatida javob yozing (AI o'chiriladi)..." : "Javobingizni yozing...") +
        '" rows="1"></textarea>' +
        '<button class="btn primary" type="submit">Yuborish</button></form>';

      var restored = $("#reply-text");
      if (restored && draft) restored.value = draft;
      if (restored && focused) {
        restored.focus();
        if (caret) restored.setSelectionRange(caret[0], caret[1]);
      }

      var thread = $("#thread");
      if (thread && !draft) thread.scrollTop = thread.scrollHeight;

      $("#reply-form").addEventListener("submit", async function (event) {
        event.preventDefault();
        var textarea = $("#reply-text");
        var text = textarea.value.trim();
        if (!text) return;
        var button = event.currentTarget.querySelector("button");
        button.disabled = true;
        try {
          await api("/conversations/" + encodeURIComponent(id) + "/reply", {
            method: "POST", body: { text: text }
          });
          textarea.value = "";
          await loadConversation(id);
          loadConversationList(false);
        } catch (error) {
          toast(error.message, true);
        } finally {
          button.disabled = false;
        }
      });

      var handoff = $("[data-handoff]", detail);
      if (handoff) handoff.addEventListener("click", function () {
        confirmModal("Operatorga topshirish", "AI o'chiriladi va suhbat operatorga o'tadi. Davom etasizmi?",
          async function () {
            await api("/conversations/" + encodeURIComponent(id) + "/handoff", {
              method: "POST", body: { reason: "Dashboarddan qo'lda topshirildi" }
            });
            toast("Suhbat operatorga topshirildi");
            loadConversation(id);
            loadConversationList(false);
          });
      });

      var resume = $("[data-resume]", detail);
      if (resume) resume.addEventListener("click", async function () {
        try {
          await api("/conversations/" + encodeURIComponent(id) + "/resume-ai", { method: "POST" });
          toast("AI qayta yoqildi");
          loadConversation(id);
          loadConversationList(false);
        } catch (error) { toast(error.message, true); }
      });
    } catch (error) {
      detail.innerHTML = errorState(error);
    }
  }

  function messageHtml(message) {
    var role = message.role === "user" ? "user" : message.role === "operator" ? "operator" : "assistant";
    var label = role === "user" ? "Mijoz" : role === "operator" ? "OP" : "AI";
    var meta = message.meta || {};
    var extra = "";
    if (meta.order && meta.order.number) {
      extra += '<div class="source-chip">🧾 Buyurtma ' + h(meta.order.number) + " · " + money(meta.order.total) + "</div>";
    }
    if (meta.products && meta.products.length) {
      extra += '<div class="row" style="margin-top:6px">' + meta.products.slice(0, 3).map(function (product) {
        return '<span class="source-chip">📦 ' + h(product.name) + " · " + money(product.price) + "</span>";
      }).join("") + "</div>";
    }
    if (meta.sources && meta.sources.length) {
      extra += '<div class="row" style="margin-top:6px">' + meta.sources.slice(0, 3).map(function (source) {
        return '<span class="source-chip">📄 ' + h(source.document_name) + "</span>";
      }).join("") + "</div>";
    }
    return '<div class="msg ' + role + '"><div class="msg-avatar">' + label + "</div>" +
      '<div><div class="bubble">' + h(message.content) + extra + "</div>" +
      '<div class="stamp">' + dt(message.created_at) +
      (message.latency_ms ? " · " + message.latency_ms + " ms" : "") + "</div></div></div>";
  }

  /* ------------------------------------------------------------------ */
  /* Knowledge                                                           */
  /* ------------------------------------------------------------------ */
  async function renderKnowledge() {
    var view = $("#view");
    view.innerHTML = pageHead("Bilimlar bazasi", "PDF, DOCX, TXT, CSV — AI javoblari shu manbalarga asoslanadi",
      '<button class="btn sm primary" data-pick>+ Hujjat yuklash</button>') +
      '<div class="grid-2"><div class="stack">' +
      '<div class="card"><div class="dropzone" id="dropzone">' +
      '<div class="ico">📚</div><p><strong>Faylni bu yerga tashlang</strong></p>' +
      '<p class="small">yoki tugma orqali tanlang · maksimal 15 MB</p>' +
      '<input type="file" id="file-input" accept=".pdf,.docx,.txt,.csv,.md" hidden>' +
      '</div><div id="upload-status" class="small muted" style="margin-top:10px"></div></div>' +
      '<div class="card"><div class="card-head"><h3>Hujjatlar</h3><span class="hint" id="doc-count"></span></div>' +
      '<div id="doc-list">' + loading() + "</div></div></div>" +
      '<div class="card"><div class="card-head"><h3>AI javobini sinash</h3><span class="hint">RAG</span></div>' +
      '<p class="muted small" style="margin-top:0">Savol bering — AI faqat bilimlar bazasidagi ma\'lumot asosida javob beradi va manbani ko\'rsatadi.</p>' +
      '<form id="rag-form" class="stack" style="gap:10px;margin-top:12px">' +
      '<textarea class="textarea" id="rag-question" placeholder="Masalan: Yetkazib berish qancha vaqt oladi?"></textarea>' +
      '<button class="btn primary" type="submit">Javob olish</button></form>' +
      '<div id="rag-result" style="margin-top:14px"></div></div></div>';

    var input = $("#file-input");
    $("[data-pick]", view).addEventListener("click", function () { input.click(); });
    input.addEventListener("change", function () {
      if (input.files[0]) uploadDocument(input.files[0]);
    });
    var zone = $("#dropzone");
    ["dragenter", "dragover"].forEach(function (event) {
      zone.addEventListener(event, function (e) { e.preventDefault(); zone.classList.add("drag"); });
    });
    ["dragleave", "drop"].forEach(function (event) {
      zone.addEventListener(event, function (e) { e.preventDefault(); zone.classList.remove("drag"); });
    });
    zone.addEventListener("drop", function (event) {
      var file = event.dataTransfer.files[0];
      if (file) uploadDocument(file);
    });

    $("#rag-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      var question = $("#rag-question").value.trim();
      if (!question) return;
      var button = event.currentTarget.querySelector("button");
      button.disabled = true;
      $("#rag-result").innerHTML = '<div class="small muted">Qidirilmoqda...</div>';
      try {
        var result = await api("/knowledge/query", { method: "POST", body: { question: question } });
        $("#rag-result").innerHTML = '<div class="rag-answer">' + h(result.answer) + "</div>" +
          '<div style="margin-top:8px">' + (result.sources.length
            ? result.sources.map(function (source) {
                return '<span class="source-chip">📄 ' + h(source.document_name) + " · §" +
                  (source.chunk_index + 1) + "</span>";
              }).join("")
            : '<span class="small muted">Manba topilmadi</span>') + "</div>" +
          '<div class="small muted" style="margin-top:8px">' + result.latency_ms + " ms</div>";
      } catch (error) {
        $("#rag-result").innerHTML = '<div class="form-error">' + h(error.message) + "</div>";
      } finally {
        button.disabled = false;
      }
    });

    await loadDocuments();
  }

  async function loadDocuments() {
    var list = $("#doc-list");
    try {
      var documents = await api("/knowledge");
      $("#doc-count").textContent = documents.length + " ta";
      if (!documents.length) {
        list.innerHTML = empty("📄", "Hujjat yo'q", "Birinchi faylni yuklang — AI shundan javob beradi.");
        return;
      }
      list.innerHTML = documents.map(function (document) {
        var icon = document.filename.split(".").pop().toLowerCase() === "pdf" ? "📕" :
          document.filename.split(".").pop().toLowerCase() === "csv" ? "📊" : "📄";
        return '<div class="file-row"><div class="file-ico">' + icon + "</div>" +
          '<div class="grow" style="flex:1;min-width:0"><div class="title" style="font-size:13px;font-weight:600">' +
          h(document.filename) + "</div>" +
          '<div class="sub" style="font-size:11.5px;color:var(--muted-2);margin-top:3px">' +
          (document.chunk_count || 0) + " chunk · " + Math.round(document.size_bytes / 1024) + " KB · " +
          dt(document.created_at) + (document.error ? " · " + h(document.error) : "") + "</div></div>" +
          docBadge(document.status) +
          '<button class="icon-btn" data-reindex="' + h(document.id) + '" title="Qayta indekslash">↻</button>' +
          '<button class="icon-btn danger" data-delete-doc="' + h(document.id) + '" title="O\'chirish">🗑</button></div>';
      }).join("");
      $$("[data-delete-doc]", list).forEach(function (button) {
        button.addEventListener("click", function () {
          confirmModal("Hujjatni o'chirish", "Hujjat va uning barcha bo'laklari o'chiriladi. AI endi shu manbadan javob bermaydi.",
            async function () {
              await api("/knowledge/" + button.dataset.deleteDoc, { method: "DELETE" });
              toast("Hujjat o'chirildi");
              loadDocuments();
            }, true);
        });
      });
      $$("[data-reindex]", list).forEach(function (button) {
        button.addEventListener("click", async function () {
          button.disabled = true;
          try {
            await api("/knowledge/" + button.dataset.reindex + "/reindex", { method: "POST" });
            toast("Qayta indekslandi");
            loadDocuments();
          } catch (error) { toast(error.message, true); }
          finally { button.disabled = false; }
        });
      });
    } catch (error) {
      list.innerHTML = errorState(error);
    }
  }

  async function uploadDocument(file) {
    var status = $("#upload-status");
    status.textContent = file.name + " yuklanmoqda...";
    var form = new FormData();
    form.append("file", file);
    try {
      await api("/knowledge/upload", { method: "POST", body: form });
      status.textContent = "Tayyor: " + file.name;
      toast("Hujjat indekslandi");
      loadDocuments();
    } catch (error) {
      status.innerHTML = '<span style="color:var(--red)">' + h(error.message) + "</span>";
      toast(error.message, true);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Products                                                            */
  /* ------------------------------------------------------------------ */
  async function renderProducts() {
    var view = $("#view");
    view.innerHTML = pageHead("Mahsulotlar", "AI katalogdan narx va qoldiqni tekshiradi",
      can("manager") ? '<button class="btn sm primary" data-new-product>+ Mahsulot qo\'shish</button>' : "") +
      '<div class="card"><div class="card-head"><h3>Katalog</h3>' +
      '<input class="input" id="product-search" placeholder="Qidirish: nom, SKU, kategoriya" style="max-width:280px">' +
      "</div><div id=\"product-table\">" + loading() + "</div></div>";

    $("#product-search").addEventListener("input", debounce(function () {
      loadProducts($("#product-search").value.trim());
    }, 280));
    var newButton = $("[data-new-product]");
    if (newButton) newButton.addEventListener("click", function () { productModal(null); });
    await loadProducts("");
  }

  function debounce(fn, delay) {
    var timer;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(null, args); }, delay);
    };
  }

  async function loadProducts(query) {
    var box = $("#product-table");
    try {
      var products = await api("/products?limit=300" + (query ? "&q=" + encodeURIComponent(query) : ""));
      state.products = products;
      if (!products.length) {
        box.innerHTML = empty("📦", "Mahsulot yo'q", "AI faqat katalogdagi mahsulotlarni taklif qiladi.",
          can("manager") ? '<button class="btn primary" data-empty-new>Birinchi mahsulotni qo\'shish</button>' : "");
        var emptyNew = $("[data-empty-new]", box);
        if (emptyNew) emptyNew.addEventListener("click", function () { productModal(null); });
        return;
      }
      box.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
        "<th>Mahsulot</th><th>Kategoriya</th><th>Narx</th><th>Qoldiq</th><th>Holat</th><th></th></tr></thead><tbody>" +
        products.map(function (product) {
          return "<tr><td><div class=\"strong\">" + h(product.name) + "</div><div class=\"sub mono\">" +
            h(product.sku || "SKU yo'q") + "</div></td>" +
            "<td>" + badge(product.category, "muted") + "</td>" +
            '<td class="price-cell">' + money(product.price) +
            (product.old_price ? '<div class="sub" style="text-decoration:line-through">' + money(product.old_price) + "</div>" : "") +
            "</td><td>" + product.stock_qty + " dona</td>" +
            "<td>" + (product.in_stock ? badge("Sotuvda", "") : badge("Tugagan", "red")) + "</td>" +
            '<td><div class="actions-cell">' +
            (can("manager")
              ? '<button class="icon-btn" data-edit-product="' + h(product.id) + '" title="Tahrirlash">✎</button>' +
                '<button class="icon-btn danger" data-del-product="' + h(product.id) + '" title="O\'chirish">🗑</button>'
              : "") +
            "</div></td></tr>";
        }).join("") + "</tbody></table></div>";

      $$("[data-edit-product]", box).forEach(function (button) {
        button.addEventListener("click", function () {
          var product = products.find(function (item) { return item.id === button.dataset.editProduct; });
          if (product) productModal(product);
        });
      });
      $$("[data-del-product]", box).forEach(function (button) {
        button.addEventListener("click", function () {
          confirmModal("Mahsulotni o'chirish", "Mahsulot katalogdan o'chiriladi. AI uni endi taklif qilmaydi.",
            async function () {
              await api("/products/" + button.dataset.delProduct, { method: "DELETE" });
              toast("Mahsulot o'chirildi");
              loadProducts(query);
            }, true);
        });
      });
    } catch (error) {
      box.innerHTML = errorState(error);
    }
  }

  function productModal(product) {
    var editing = Boolean(product);
    var modal = openModal(editing ? "Mahsulotni tahrirlash" : "Yangi mahsulot",
      '<div class="field"><label>Nomi *</label><input class="input" id="p-name" value="' + h(product ? product.name : "") + '"></div>' +
      '<div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Narx (so\'m) *</label>' +
      '<input class="input" id="p-price" type="number" min="0" step="1000" value="' + (product ? product.price : "") + '"></div>' +
      '<div class="field" style="flex:1"><label>Eski narx</label>' +
      '<input class="input" id="p-old" type="number" min="0" step="1000" value="' + (product && product.old_price ? product.old_price : "") + '"></div></div>' +
      '<div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Kategoriya</label>' +
      '<input class="input" id="p-category" value="' + h(product ? product.category : "umumiy") + '"></div>' +
      '<div class="field" style="flex:1"><label>SKU</label>' +
      '<input class="input" id="p-sku" value="' + h(product ? (product.sku || "") : "") + '"></div></div>' +
      '<div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Qoldiq (dona)</label>' +
      '<input class="input" id="p-stock" type="number" min="0" value="' + (product ? product.stock_qty : 0) + '"></div>' +
      '<div class="field" style="flex:1"><label>Holat</label><select class="select" id="p-instock">' +
      '<option value="1"' + (!product || product.in_stock ? " selected" : "") + ">Sotuvda</option>" +
      '<option value="0"' + (product && !product.in_stock ? " selected" : "") + ">Tugagan</option></select></div></div>" +
      '<div class="field"><label>Tavsif</label><textarea class="textarea" id="p-desc">' + h(product ? product.description : "") + "</textarea></div>" +
      '<div class="form-error hidden" data-error></div>',
      '<button class="btn" data-close>Bekor qilish</button><button class="btn primary" data-save>Saqlash</button>');

    $("[data-save]", modal).addEventListener("click", async function () {
      var payload = {
        name: $("#p-name", modal).value.trim(),
        price: Number($("#p-price", modal).value) || 0,
        old_price: $("#p-old", modal).value ? Number($("#p-old", modal).value) : null,
        category: $("#p-category", modal).value.trim() || "umumiy",
        sku: $("#p-sku", modal).value.trim() || null,
        stock_qty: Number($("#p-stock", modal).value) || 0,
        in_stock: $("#p-instock", modal).value === "1",
        description: $("#p-desc", modal).value.trim(),
        currency: "UZS"
      };
      var errorBox = $("[data-error]", modal);
      if (!payload.name) {
        errorBox.textContent = "Nomini kiriting";
        errorBox.classList.remove("hidden");
        return;
      }
      try {
        if (editing) {
          await api("/products/" + product.id, { method: "PATCH", body: payload });
        } else {
          await api("/products", { method: "POST", body: payload });
        }
        closeModal();
        toast(editing ? "Mahsulot yangilandi" : "Mahsulot qo'shildi");
        loadProducts($("#product-search") ? $("#product-search").value.trim() : "");
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.classList.remove("hidden");
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Orders                                                              */
  /* ------------------------------------------------------------------ */
  async function renderOrders() {
    var view = $("#view");
    view.innerHTML = pageHead("Buyurtmalar", "AI va operator tomonidan yaratilgan buyurtmalar",
      '<button class="btn sm primary" data-new-order>+ Qo\'lda buyurtma</button>') +
      '<div class="row" style="margin-bottom:14px">' +
      '<select class="select" id="order-filter" style="max-width:200px">' +
      '<option value="">Barcha holatlar</option>' +
      Object.keys(ORDER_STATUS).map(function (status) {
        return '<option value="' + status + '">' + ORDER_STATUS[status][0] + "</option>";
      }).join("") + "</select>" +
      '<input class="input" id="order-search" placeholder="Mijoz, telefon yoki raqam" style="max-width:280px"></div>' +
      '<div class="card"><div id="order-table">' + loading() + "</div></div>";

    $("#order-filter").addEventListener("change", function () { loadOrders(); });
    $("#order-search").addEventListener("input", debounce(function () { loadOrders(); }, 280));
    $("[data-new-order]").addEventListener("click", newOrderModal);
    await loadOrders();
  }

  async function loadOrders() {
    var box = $("#order-table");
    var status = $("#order-filter") ? $("#order-filter").value : "";
    var query = $("#order-search") ? $("#order-search").value.trim() : "";
    var params = "?limit=200" + (status ? "&status=" + status : "") + (query ? "&q=" + encodeURIComponent(query) : "");
    try {
      var orders = await api("/orders" + params);
      if (!orders.length) {
        box.innerHTML = empty("🛒", "Buyurtmalar yo'q", "AI chatda buyurtma yaratsa yoki qo'lda qo'shsangiz, shu yerda ko'rinadi.");
        return;
      }
      box.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
        "<th>Raqam</th><th>Mijoz</th><th>Mahsulotlar</th><th>Summa</th><th>Manba</th><th>Holat</th><th></th></tr></thead><tbody>" +
        orders.map(function (order) {
          return '<tr><td><div class="strong mono" style="font-size:12px">' + h(order.number) + "</div>" +
            '<div class="sub">' + dt(order.created_at) + "</div></td>" +
            "<td><div>" + h(order.customer_name) + "</div><div class=\"sub\">" + h(order.customer_phone) + "</div></td>" +
            '<td><div style="max-width:220px">' + order.items.length + " pozitsiya</div>" +
            '<div class="sub">' + h(order.items.map(function (item) { return item.name + " ×" + item.qty; }).join(", ").slice(0, 70)) + "</div></td>" +
            '<td class="price-cell">' + money(order.total) + "</td>" +
            "<td>" + badge(order.source === "ai" ? "AI" : "Qo'lda", order.source === "ai" ? "" : "muted") +
            "</td><td>" + statusBadge(order.status) + "</td>" +
            '<td><div class="actions-cell"><button class="icon-btn" data-view-order="' + h(order.id) + '">👁</button></div></td></tr>';
        }).join("") + "</tbody></table></div>";

      $$("[data-view-order]", box).forEach(function (button) {
        button.addEventListener("click", function () {
          var order = orders.find(function (item) { return item.id === button.dataset.viewOrder; });
          if (order) orderDetailModal(order, loadOrders);
        });
      });
    } catch (error) {
      box.innerHTML = errorState(error);
    }
  }

  function orderDetailModal(order, refresh) {
    var items = order.items.map(function (item) {
      return '<div class="list-item"><div class="grow"><div class="title">' + h(item.name) + '</div>' +
        '<div class="sub">' + item.qty + " × " + money(item.price) + "</div></div>" +
        '<div class="price-cell">' + money(item.price * item.qty) + "</div></div>";
    }).join("");
    var options = Object.keys(ORDER_STATUS).map(function (status) {
      return '<option value="' + status + '"' + (order.status === status ? " selected" : "") + ">" +
        ORDER_STATUS[status][0] + "</option>";
    }).join("");
    var modal = openModal("Buyurtma " + order.number,
      '<div class="row" style="justify-content:space-between">' +
      '<div><div class="muted small">Mijoz</div><div class="strong">' + h(order.customer_name) + "</div>" +
      '<div class="sub">' + h(order.customer_phone) + "</div></div>" +
      '<div style="text-align:right"><div class="muted small">Summa</div><div class="strong" style="font-size:19px;color:var(--accent)">' +
      money(order.total) + "</div>" + statusBadge(order.status) + "</div></div>" +
      '<div class="list" style="border:1px solid var(--line);border-radius:10px;padding:4px 12px">' + items + "</div>" +
      (order.note ? '<div class="small muted">Izoh: ' + h(order.note) + "</div>" : "") +
      '<div class="field"><label>Holatni o\'zgartirish</label><select class="select" id="order-status">' + options + "</select></div>",
      '<button class="btn" data-close>Yopish</button><button class="btn primary" data-save-status>Saqlash</button>');
    $("[data-save-status]", modal).addEventListener("click", async function () {
      try {
        await api("/orders/" + order.id + "/status", {
          method: "PATCH", body: { status: $("#order-status", modal).value }
        });
        closeModal();
        toast("Holat yangilandi");
        refresh();
      } catch (error) { toast(error.message, true); }
    });
  }

  async function newOrderModal() {
    try {
      var products = await api("/products?limit=300");
    } catch (error) { toast(error.message, true); return; }
    if (!products.length) { toast("Avval mahsulot qo'shing", true); return; }

    var options = products.map(function (product) {
      return '<option value="' + h(product.id) + '">' + h(product.name) + " — " + money(product.price) + "</option>";
    }).join("");

    var modal = openModal("Qo'lda buyurtma",
      '<div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Mijoz ismi *</label>' +
      '<input class="input" id="o-name" placeholder="Aziz Karimov"></div>' +
      '<div class="field" style="flex:1"><label>Telefon *</label>' +
      '<input class="input" id="o-phone" placeholder="+998 90 123 45 67"></div></div>' +
      '<div class="field"><label>Mahsulotlar</label><div id="o-items" class="stack" style="gap:8px">' +
      '<div class="row" data-item><select class="select" data-product style="flex:1">' + options + "</select>" +
      '<input class="input" data-qty type="number" min="1" value="1" style="width:86px">' +
      '<button class="icon-btn danger" type="button" data-remove-item>×</button></div></div>' +
      '<button class="btn sm ghost" type="button" id="o-add-item">+ Yana mahsulot</button></div>' +
      '<div class="field"><label>Izoh</label><textarea class="textarea" id="o-note" style="min-height:64px"></textarea></div>' +
      '<div class="form-error hidden" data-error></div>',
      '<button class="btn" data-close>Bekor qilish</button><button class="btn primary" data-create>Buyurtma yaratish</button>');

    function bindRemove(row) {
      $("[data-remove-item]", row).addEventListener("click", function () {
        if ($$("[data-item]", modal).length > 1) row.remove();
      });
    }
    $$("[data-item]", modal).forEach(bindRemove);

    $("#o-add-item", modal).addEventListener("click", function () {
      var row = document.createElement("div");
      row.className = "row";
      row.dataset.item = "1";
      row.innerHTML = '<select class="select" data-product style="flex:1">' + options + "</select>" +
        '<input class="input" data-qty type="number" min="1" value="1" style="width:86px">' +
        '<button class="icon-btn danger" type="button" data-remove-item>×</button>';
      $("#o-items", modal).appendChild(row);
      bindRemove(row);
    });

    $("[data-create]", modal).addEventListener("click", async function () {
      var errorBox = $("[data-error]", modal);
      var items = $$("[data-item]", modal).map(function (row) {
        return {
          product_id: $("[data-product]", row).value,
          qty: Number($("[data-qty]", row).value) || 1
        };
      });
      var payload = {
        customer_name: $("#o-name", modal).value.trim(),
        customer_phone: $("#o-phone", modal).value.trim(),
        note: $("#o-note", modal).value.trim(),
        items: items
      };
      if (!payload.customer_name || !payload.customer_phone) {
        errorBox.textContent = "Ism va telefon raqamini kiriting";
        errorBox.classList.remove("hidden");
        return;
      }
      try {
        var order = await api("/orders", { method: "POST", body: payload });
        closeModal();
        toast("Buyurtma " + order.number + " yaratildi");
        loadOrders();
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.classList.remove("hidden");
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Analytics                                                           */
  /* ------------------------------------------------------------------ */
  async function renderAnalytics() {
    var view = $("#view");
    view.innerHTML = pageHead("Analitika", "Sotuv va AI samaradorligi",
      '<div class="row">' + [7, 30, 90].map(function (days) {
        return '<button class="btn sm' + (state.analyticsDays === days ? " primary" : "") +
          '" data-days="' + days + '">' + days + " kun</button>";
      }).join("") + "</div>") +
      '<div id="analytics-body">' + loading() + "</div>";

    $$("[data-days]", view).forEach(function (button) {
      button.addEventListener("click", function () {
        state.analyticsDays = Number(button.dataset.days);
        $$("[data-days]", view).forEach(function (node) { node.classList.toggle("primary", node === button); });
        loadAnalytics();
      });
    });
    await loadAnalytics();
  }

  async function loadAnalytics() {
    var box = $("#analytics-body");
    if (!box) return;
    try {
      var data = await api("/analytics/overview?days=" + state.analyticsDays);
      var channels = Object.keys(data.by_channel);
      box.innerHTML = '<div class="kpis">' +
        kpi("Suhbatlar", num(data.conversations), data.new_customers + " yangi mijoz", "💬") +
        kpi("Buyurtmalar", num(data.orders), "konversiya " + data.conversion_rate + "%", "🛒", true) +
        kpi("Tushum", money(data.revenue), data.range_days + " kun", "💰") +
        kpi("Xabarlar", num(data.messages), num(data.ai_messages) + " AI javobi", "✉️") +
        kpi("O'rtacha javob", (data.avg_response_ms || 0) + " ms", "AI latency", "⚡") +
        kpi("Handoff", num(data.handoffs), "operatorga", "🙋") +
        "</div>" +
        '<div class="grid-2"><div class="card"><div class="card-head"><h3>Dinamika</h3>' +
        '<span class="hint">' + data.range_days + " kun</span></div>" + chart(data.series) + "</div>" +
        '<div class="stack"><div class="card"><div class="card-head"><h3>Kanallar</h3></div>' +
        (channels.length
          ? '<div class="list">' + channels.map(function (channel) {
              var info = CHANNEL[channel] || { label: channel, icon: "•" };
              var total = data.conversations || 1;
              return '<div class="list-item"><div class="channel-ico">' + info.icon + "</div>" +
                '<div class="grow"><div class="title">' + h(info.label) + '</div><div class="sub">' +
                Math.round((data.by_channel[channel] / total) * 100) + "% ulush</div></div>" +
                '<div class="time">' + num(data.by_channel[channel]) + "</div></div>";
            }).join("") + "</div>"
          : '<p class="muted small">Ma\'lumot yo\'q</p>') + "</div>" +
        '<div class="card"><div class="card-head"><h3>Top mahsulotlar</h3></div>' +
        (data.top_products.length
          ? '<div class="list">' + data.top_products.map(function (product, index) {
              return '<div class="list-item"><div class="channel-ico" style="color:var(--accent)">' + (index + 1) +
                '</div><div class="grow"><div class="title">' + h(product.name) + '</div><div class="sub">' +
                product.qty + " dona</div></div><div class=\"time mono\">" + money(product.revenue) + "</div></div>";
            }).join("") + "</div>"
          : '<p class="muted small">Buyurtmalar yo\'q</p>') + "</div></div></div>" +
        '<div class="card" id="audit-card" style="margin-top:18px"></div>';
      if (can("manager")) loadAuditLogs();
    } catch (error) {
      box.innerHTML = errorState(error);
    }
  }

  async function loadAuditLogs() {
    var card = $("#audit-card");
    if (!card) return;
    try {
      var logs = await api("/analytics/audit-logs?limit=30");
      card.innerHTML = '<div class="card-head"><h3>Audit log</h3><span class="hint">oxirgi 30 amal</span></div>' +
        (logs.length
          ? '<div class="table-wrap"><table><thead><tr><th>Vaqt</th><th>Amal</th><th>Obyekt</th><th>Foydalanuvchi</th><th>Meta</th></tr></thead><tbody>' +
            logs.map(function (log) {
              return "<tr><td class=\"small\">" + dt(log.created_at) + "</td>" +
                "<td>" + badge(log.action, "muted") + "</td><td>" + h(log.entity || "—") + "</td>" +
                '<td class="mono small">' + h((log.user_id || "").slice(0, 10) || "tizim") + "</td>" +
                '<td class="small muted">' + h(JSON.stringify(log.meta || {}).slice(0, 90)) + "</td></tr>";
            }).join("") + "</tbody></table></div>"
          : '<p class="muted small">Amallar yo\'q</p>');
    } catch (error) {
      card.innerHTML = '<div class="small muted">Audit log yuklanmadi: ' + h(error.message) + "</div>";
    }
  }

  /* ------------------------------------------------------------------ */
  /* Integrations                                                        */
  /* ------------------------------------------------------------------ */
  async function renderIntegrations() {
    var view = $("#view");
    view.innerHTML = pageHead("Integratsiyalar", "Telegram bot va sayt chat widgeti", "") +
      '<div class="grid-2"><div class="stack">' +
      '<div class="card" id="telegram-card">' + loading() + "</div>" +
      '<div class="card" id="widget-card">' + loading() + "</div>" +
      "</div><div class=\"card\"><div class=\"card-head\"><h3>Qanday ishlaydi?</h3></div>" +
      '<div class="stack" style="gap:16px">' +
      '<div class="integration"><div class="ico">1️⃣</div><div><h3>BotFather</h3><p>Telegramda @BotFather orqali yangi bot yarating va tokenni oling.</p></div></div>' +
      '<div class="integration"><div class="ico">2️⃣</div><div><h3>Tokenni ulang</h3><p>Token shifrlangan holda saqlanadi. Bot username avtomatik aniqlanadi.</p></div></div>' +
      '<div class="integration"><div class="ico">3️⃣</div><div><h3>Avtomatik ulanish</h3><p>Lokalda long polling avtomatik yoqiladi. PUBLIC_BASE_URL https bo\'lsa webhook rejimi ishlatiladi.</p></div></div>' +
      '<div class="integration"><div class="ico">4️⃣</div><div><h3>Widget</h3><p>Script qatorini saytingizga qo\'ying — chat o\'ng pastda paydo bo\'ladi.</p></div></div>' +
      "</div></div></div>";
    await Promise.all([loadTelegram(), loadWidget()]);
  }

  async function loadTelegram() {
    var card = $("#telegram-card");
    try {
      var data = await api("/integrations/telegram");
      if (!data.connected) {
        card.innerHTML = '<div class="integration"><div class="ico">✈️</div><div style="flex:1"><h3>Telegram bot</h3>' +
          '<p>@BotFather tokenini kiriting. Token ulangach bot avtomatik ishga tushadi.</p></div></div>' +
          '<div class="field" style="margin-top:14px"><label>Bot token</label>' +
          '<input class="input mono" id="tg-token" placeholder="123456789:AA..."></div>' +
          '<button class="btn primary" id="tg-connect" style="margin-top:12px">Ulash</button>' +
          '<div class="small muted" style="margin-top:10px">Token <b>shifrlangan</b> holda saqlanadi va hech qachon qaytarilmaydi.</div>';
        $("#tg-connect").addEventListener("click", async function (event) {
          var token = $("#tg-token").value.trim();
          if (!token) return;
          event.currentTarget.disabled = true;
          try {
            var result = await api("/integrations/telegram", { method: "POST", body: { token: token } });
            toast("Bot ulandi: @" + result.bot_username);
            loadTelegram();
          } catch (error) { toast(error.message, true); }
          finally { event.currentTarget.disabled = false; }
        });
        return;
      }
      var polling = data.mode === "polling";
      card.innerHTML = '<div class="integration"><div class="ico">✈️</div><div style="flex:1"><h3>@' +
        h(data.bot_username) + " " + badge(polling ? "Polling faol" : "Webhook", "") +
        '</h3><p>' + (polling
          ? "Lokal long polling rejimi faol — botga Telegramda yozing, AI avtomatik javob beradi."
          : "Webhook URL quyida. Uni Telegramga o'rnatish uchun tugmani bosing.") +
        '</p></div></div>' +
        (polling
          ? '<div class="small muted" style="margin-top:10px">Bot ilova ishlab turganda javob beradi. Ommaviy serverda PUBLIC_BASE_URL ni https qiling — webhook rejimi avtomatik yoqiladi.</div>'
          : '<div class="code-box" style="margin-top:14px">' + h(data.webhook_url) + "</div>") +
        '<div class="row" style="margin-top:12px">' +
        (polling ? "" : '<button class="btn primary" id="tg-webhook">Webhookni o\'rnatish</button>') +
        '<button class="btn danger" id="tg-disconnect">Uzish</button></div>';
      if (!polling) {
        $("#tg-webhook").addEventListener("click", async function (event) {
          event.currentTarget.disabled = true;
          try {
            await api("/integrations/telegram/set-webhook", { method: "POST" });
            toast("Webhook o'rnatildi");
          } catch (error) { toast(error.message, true); }
          finally { event.currentTarget.disabled = false; }
        });
      }
      $("#tg-disconnect").addEventListener("click", function () {
        confirmModal("Botni uzish", "Webhook o'chiriladi va bot integratsiyasi o'chiriladi.", async function () {
          await api("/integrations/telegram", { method: "DELETE" });
          toast("Bot uzildi");
          loadTelegram();
        }, true);
      });
    } catch (error) {
      card.innerHTML = errorState(error);
    }
  }

  async function loadWidget() {
    var card = $("#widget-card");
    try {
      var widget = await api("/integrations/widget");
      card.innerHTML = '<div class="integration"><div class="ico">🌐</div><div style="flex:1"><h3>Sayt chat widgeti ' +
        (widget.active ? badge("Faol", "") : badge("O'chirilgan", "amber")) + '</h3>' +
        '<p>Script qatorini saytingizning &lt;/body&gt; oldiga qo\'ying.</p></div>' +
        '<a class="btn sm" href="/demo" target="_blank" rel="noopener">Sinash ↗</a></div>' +
        '<div class="code-box" style="margin-top:14px" id="embed-code">' + h(widget.embed_code) + "</div>" +
        '<div class="row" style="margin-top:10px"><button class="btn sm" id="copy-embed">Kodni nusxalash</button>' +
        '<span class="small muted">Kalit: <span class="mono">' + h(widget.public_key) + "</span></span></div>" +
        '<div class="stack" style="gap:12px;margin-top:18px">' +
        '<div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Sarlavha</label>' +
        '<input class="input" id="w-title" value="' + h(widget.title) + '"></div>' +
        '<div class="field" style="width:120px"><label>Rang</label>' +
        '<input class="input" id="w-color" type="color" value="' + h(widget.color) + '" style="padding:4px;height:42px"></div></div>' +
        '<div class="field"><label>Salomlashuv</label><textarea class="textarea" id="w-greeting">' + h(widget.greeting) + "</textarea></div>" +
        '<button class="btn primary" id="w-save">Saqlash</button></div>';

      $("#copy-embed").addEventListener("click", async function () {
        try {
          await navigator.clipboard.writeText(widget.embed_code);
          toast("Kod nusxalandi");
        } catch (error) {
          var range = document.createRange();
          range.selectNodeContents($("#embed-code"));
          var selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          document.execCommand("copy");
          toast("Kod nusxalandi");
        }
      });
      $("#w-save").addEventListener("click", async function (event) {
        event.currentTarget.disabled = true;
        try {
          await api("/integrations/widget", {
            method: "PUT",
            body: {
              title: $("#w-title").value.trim(),
              color: $("#w-color").value,
              greeting: $("#w-greeting").value.trim()
            }
          });
          toast("Widget sozlamalari saqlandi");
          loadWidget();
        } catch (error) { toast(error.message, true); }
        finally { event.currentTarget.disabled = false; }
      });
    } catch (error) {
      card.innerHTML = errorState(error);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Team                                                                */
  /* ------------------------------------------------------------------ */
  async function renderTeam() {
    var view = $("#view");
    view.innerHTML = pageHead("Jamoa", "Xodimlar va rollar",
      can("manager") ? '<button class="btn sm primary" data-invite>+ Xodim qo\'shish</button>' : "") +
      '<div class="card"><div id="member-table">' + loading() + "</div></div>" +
      '<div class="card" style="margin-top:16px"><div class="card-head"><h3>Rollar</h3></div>' +
      '<div class="list">' +
      roleRow("Owner", "To'liq nazorat: tarif, integratsiyalar, jamoa, barcha ma'lumotlar.") +
      roleRow("Manager", "Katalog, bilimlar bazasi, jamoa va suhbatlar. Tarifni o'zgartira olmaydi.") +
      roleRow("Operator", "Suhbatlar, buyurtmalar va mijozlarga javob berish.") +
      "</div></div>";

    var invite = $("[data-invite]", view);
    if (invite) invite.addEventListener("click", inviteModal);
    await loadMembers();
  }

  function roleRow(name, text) {
    return '<div class="list-item"><div class="channel-ico">👤</div><div class="grow"><div class="title">' +
      h(name) + '</div><div class="sub">' + h(text) + "</div></div></div>";
  }

  async function loadMembers() {
    var box = $("#member-table");
    try {
      var members = await api("/orgs/members");
      box.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
        "<th>Xodim</th><th>Email</th><th>Rol</th><th>Qo'shilgan</th><th></th></tr></thead><tbody>" +
        members.map(function (member) {
          var isOwner = member.role === "owner";
          var roleCell = can("owner") && !isOwner
            ? '<select class="select" data-role="' + h(member.id) + '" style="padding:6px 9px;font-size:12px;max-width:140px">' +
              ["manager", "operator"].map(function (role) {
                return '<option value="' + role + '"' + (member.role === role ? " selected" : "") + ">" +
                  (role === "manager" ? "Manager" : "Operator") + "</option>";
              }).join("") + "</select>"
            : badge(member.role, member.role === "owner" ? "" : "muted");
          return "<tr><td><div class=\"row\" style=\"gap:9px\"><div class=\"user-avatar\" style=\"width:30px;height:30px;font-size:11px\">" +
            initials(member.full_name || member.email) + '</div><div class="strong">' + h(member.full_name || "—") +
            "</div></div></td><td>" + h(member.email) + "</td><td>" + roleCell + "</td>" +
            '<td class="small">' + dt(member.created_at) + "</td>" +
            '<td><div class="actions-cell">' + (can("owner") && !isOwner
              ? '<button class="icon-btn danger" data-remove-member="' + h(member.id) + '">🗑</button>' : "") +
            "</div></td></tr>";
        }).join("") + "</tbody></table></div>";

      $$("[data-role]", box).forEach(function (select) {
        select.addEventListener("change", async function () {
          try {
            await api("/orgs/members/" + select.dataset.role, {
              method: "PATCH", body: { role: select.value }
            });
            toast("Rol yangilandi");
          } catch (error) {
            toast(error.message, true);
            loadMembers();
          }
        });
      });
      $$("[data-remove-member]", box).forEach(function (button) {
        button.addEventListener("click", function () {
          confirmModal("Xodimni o'chirish", "Xodim tashkilotdan chiqariladi.", async function () {
            await api("/orgs/members/" + button.dataset.removeMember, { method: "DELETE" });
            toast("Xodim chiqarildi");
            loadMembers();
          }, true);
        });
      });
    } catch (error) {
      box.innerHTML = errorState(error);
    }
  }

  function inviteModal() {
    var modal = openModal("Xodim qo'shish",
      '<div class="field"><label>Email *</label><input class="input" id="m-email" type="email" placeholder="xodim@kompaniya.uz"></div>' +
      '<div class="field"><label>Ism</label><input class="input" id="m-name" placeholder="Ism Familiya"></div>' +
      '<div class="field"><label>Rol</label><select class="select" id="m-role">' +
      '<option value="operator">Operator</option><option value="manager">Manager</option></select></div>' +
      '<div class="field"><label>Vaqtinchalik parol (ixtiyoriy)</label>' +
      '<input class="input" id="m-password" placeholder="Bo\'sh qoldirilsa avtomatik yaratiladi"></div>' +
      '<div class="form-error hidden" data-error></div>' +
      '<div class="small muted">Xodim shu email va parol bilan tizimga kiradi.</div>',
      '<button class="btn" data-close>Bekor qilish</button><button class="btn primary" data-invite-save>Qo\'shish</button>');
    $("[data-invite-save]", modal).addEventListener("click", async function () {
      var errorBox = $("[data-error]", modal);
      var email = $("#m-email", modal).value.trim();
      if (!email) {
        errorBox.textContent = "Email kiriting";
        errorBox.classList.remove("hidden");
        return;
      }
      try {
        var result = await api("/orgs/members", {
          method: "POST",
          body: {
            email: email,
            full_name: $("#m-name", modal).value.trim(),
            role: $("#m-role", modal).value,
            password: $("#m-password", modal).value || null
          }
        });
        closeModal();
        toast(result.temporary_password
          ? "Xodim qo'shildi. Vaqtinchalik parol: " + result.temporary_password
          : "Xodim qo'shildi");
        loadMembers();
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.classList.remove("hidden");
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Billing                                                             */
  /* ------------------------------------------------------------------ */
  async function renderBilling() {
    var view = $("#view");
    view.innerHTML = pageHead("Tarif va to'lovlar", "Limitlar va to'lov tarixi", "") +
      '<div id="billing-body">' + loading() + "</div>";
    try {
      var data = await api("/billing");
      var usage = data.usage;
      var plans = data.plans;
      var planKeys = ["starter", "pro", "business"];
      view.innerHTML = pageHead("Tarif va to'lovlar", "Limitlar va to'lov tarixi", "") +
        '<div class="grid-2" style="margin-bottom:18px">' +
        '<div class="card"><div class="card-head"><h3>Joriy tarif: ' + h((plans[data.plan] || {}).title || data.plan) +
        "</h3><span class=\"hint\">" + (data.plan_expires_at ? "tugaydi: " + dt(data.plan_expires_at) : "muddat belgilanmagan") + "</span></div>" +
        '<div class="usage">' +
        usageBar("Suhbatlar", usage.conversations, usage.conversation_limit) +
        usageBar("Hujjatlar", usage.documents, usage.document_limit) +
        usageBar("Xodimlar", usage.team, usage.team_limit) +
        "</div>" +
        '<div class="small muted" style="margin-top:14px">Buyurtmalar: <b>' + num(usage.orders) + "</b> · Limitlar har oy 1-sanada yangilanadi.</div></div>" +
        '<div class="card"><div class="card-head"><h3>To\'lov tarixi</h3></div>' +
        (data.payments.length
          ? '<div class="list">' + data.payments.map(function (payment) {
              return '<div class="list-item"><div class="channel-ico">🧾</div><div class="grow"><div class="title">' +
                h((plans[payment.plan] || {}).title || payment.plan) + " · " + payment.months + " oy</div>" +
                '<div class="sub">' + dt(payment.created_at) + " · " + h(payment.provider) + "</div></div>" +
                '<div class="time mono">' + money(payment.amount) + "</div></div>";
            }).join("") + "</div>"
          : '<p class="muted small">To\'lovlar yo\'q</p>') + "</div></div>" +
        '<div class="plan-grid">' + planKeys.map(function (key) {
          var plan = plans[key];
          var current = key === data.plan;
          return '<div class="plan-card' + (current ? " current" : "") + '">' +
            (current ? '<span class="badge tag">Joriy</span>' : "") +
            "<h3>" + h(plan.title) + '</h3><div class="price">' + money(plan.price) +
            '<small style="font-size:12px">/oy</small></div><ul>' +
            plan.features.map(function (feature) { return "<li>" + h(feature) + "</li>"; }).join("") +
            "<li>" + num(plan.conversations) + " suhbat / oy</li><li>" + plan.documents + " hujjat</li><li>" +
            plan.team + " xodim</li></ul>" +
            '<button class="btn ' + (current ? "" : "primary") + ' block" data-plan="' + key + '">' +
            (current ? "Muddatni uzaytirish" : "Tanlash") + "</button></div>";
        }).join("") + "</div>";

      $$("[data-plan]", view).forEach(function (button) {
        button.addEventListener("click", function () {
          if (!can("owner")) { toast("Faqat tashkilot egasi tarifni o'zgartiradi", true); return; }
          var key = button.dataset.plan;
          confirmModal("Tarifni tanlash", (plans[key].title) + " tarifi 1 oyga faollashtiriladi. To'lov demo rejimida darhol tasdiqlanadi.",
            async function () {
              await api("/billing/subscribe", { method: "POST", body: { plan: key, months: 1 } });
              var org = (state.me.orgs || []).find(function (item) { return item.id === state.orgId; });
              if (org) org.plan = key;
              buildSwitcher();
              toast("Tarif yangilandi: " + plans[key].title);
              renderBilling();
            });
        });
      });
    } catch (error) {
      $("#billing-body").innerHTML = errorState(error);
    }
  }

  function usageBar(label, value, limit) {
    var percent = limit ? Math.min(100, Math.round((value / limit) * 100)) : 0;
    return '<div class="usage-row"><div class="top"><span>' + h(label) + '</span><span>' +
      num(value) + " / " + num(limit) + "</span></div>" +
      '<div class="usage-bar"><span style="width:' + percent + '%' + (percent >= 90 ? ";background:var(--red)" : "") + '"></span></div></div>';
  }

  /* ------------------------------------------------------------------ */
  /* Settings                                                            */
  /* ------------------------------------------------------------------ */
  async function renderSettings() {
    var view = $("#view");
    view.innerHTML = pageHead("Sozlamalar", "Tashkilot va AI agent", "") +
      '<div class="grid-2"><div class="stack">' +
      '<div class="card" id="org-card">' + loading() + "</div>" +
      '<div class="card" id="agent-card">' + loading() + "</div>" +
      '</div><div class="card"><div class="card-head"><h3>Hisob</h3></div>' +
      '<div class="list">' +
      '<div class="list-item"><div class="user-avatar">' + initials(state.user.full_name || state.user.email) +
      '</div><div class="grow"><div class="title">' + h(state.user.full_name || "—") + '</div><div class="sub">' +
      h(state.user.email) + "</div></div>" + badge(state.role, "muted") + "</div>" +
      '<div class="list-item"><div class="grow"><div class="title">Tashkilot</div><div class="sub">' +
      h((state.me.orgs.find(function (org) { return org.id === state.orgId; }) || {}).name || "—") +
      "</div></div></div>" +
      '<div class="list-item"><div class="grow"><div class="title">Xavfsizlik</div>' +
      '<div class="sub">Access token 30 daqiqa, refresh token 14 kun. Parol bcrypt bilan saqlanadi.</div></div></div>' +
      "</div>" +
      '<button class="btn danger" id="logout-2" style="margin-top:16px">Chiqish</button></div></div>';

    $("#logout-2").addEventListener("click", logout);
    await Promise.all([loadOrg(), loadAgentSettings()]);
  }

  async function loadOrg() {
    var card = $("#org-card");
    try {
      var org = await api("/orgs");
      var editable = can("owner");
      card.innerHTML = '<div class="card-head"><h3>Tashkilot</h3><span class="hint">' +
        (editable ? "O'zgartirish mumkin" : "Faqat ko'rish") + "</span></div>" +
        '<div class="stack" style="gap:12px">' +
        '<div class="field"><label>Nomi</label><input class="input" id="org-name" value="' + h(org.name) + '"' +
        (editable ? "" : " disabled") + "></div>" +
        '<div class="field"><label>Slug</label><input class="input mono" value="' + h(org.slug) + '" disabled></div>' +
        '<div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Telefon</label>' +
        '<input class="input" id="org-phone" value="' + h(org.contact_phone) + '"' + (editable ? "" : " disabled") + "></div>" +
        '<div class="field" style="flex:1"><label>Telegram</label>' +
        '<input class="input" id="org-tg" value="' + h(org.contact_telegram) + '"' + (editable ? "" : " disabled") + "></div></div>" +
        '<div class="field"><label>Tavsif</label><textarea class="textarea" id="org-desc"' +
        (editable ? "" : " disabled") + ">" + h(org.description) + "</textarea></div>" +
        (editable ? '<button class="btn primary" id="org-save">Saqlash</button>' : "") + "</div>";
      var save = $("#org-save");
      if (save) save.addEventListener("click", async function (event) {
        event.currentTarget.disabled = true;
        try {
          await api("/orgs", {
            method: "PATCH",
            body: {
              name: $("#org-name").value.trim(),
              contact_phone: $("#org-phone").value.trim(),
              contact_telegram: $("#org-tg").value.trim(),
              description: $("#org-desc").value.trim()
            }
          });
          toast("Tashkilot saqlandi");
        } catch (error) { toast(error.message, true); }
        finally { event.currentTarget.disabled = false; }
      });
    } catch (error) {
      card.innerHTML = errorState(error);
    }
  }

  async function loadAgentSettings() {
    var card = $("#agent-card");
    try {
      var agent = await api("/orgs/agent");
      var editable = can("manager");
      card.innerHTML = '<div class="card-head"><h3>AI agent</h3><span class="hint">' +
        (editable ? "Persona va til" : "Faqat ko'rish") + "</span></div>" +
        '<div class="stack" style="gap:12px">' +
        '<div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Agent ismi</label>' +
        '<input class="input" id="a-name" value="' + h(agent.agent_name) + '"' + (editable ? "" : " disabled") + "></div>" +
        '<div class="field" style="width:150px"><label>Til</label><select class="select" id="a-lang"' +
        (editable ? "" : " disabled") + ">" + ["uz", "ru", "en"].map(function (code) {
          return '<option value="' + code + '"' + (agent.language === code ? " selected" : "") + ">" +
            (code === "uz" ? "O'zbek" : code === "ru" ? "Русский" : "English") + "</option>";
        }).join("") + "</select></div></div>" +
        '<div class="field"><label>Persona</label><textarea class="textarea" id="a-persona"' +
        (editable ? "" : " disabled") + ">" + h(agent.persona) + "</textarea></div>" +
        '<div class="field"><label>Salomlashuv</label><textarea class="textarea" id="a-greeting"' +
        (editable ? "" : " disabled") + ">" + h(agent.greeting) + "</textarea></div>" +
        '<div class="field"><label>Handoff kalit so\'zlari (vergul bilan)</label>' +
        '<input class="input" id="a-keywords" value="' + h(agent.handoff_keywords.join(", ")) + '"' +
        (editable ? "" : " disabled") + "></div>" +
        '<div class="field"><label>Temperature: <span id="a-temp-label">' + agent.temperature + "</span></label>" +
        '<input type="range" id="a-temp" min="0" max="1.5" step="0.1" value="' + agent.temperature + '"' +
        (editable ? "" : " disabled") + "></div>" +
        '<div class="small muted">Model: <span class="mono">' + h(agent.model || "deterministik (LLM kaliti yo'q)") +
        "</span> · oxirgi yangilanish: " + dt(agent.updated_at) + "</div>" +
        (editable ? '<button class="btn primary" id="a-save">Saqlash</button>' : "") + "</div>";

      var range = $("#a-temp");
      if (range) range.addEventListener("input", function () { $("#a-temp-label").textContent = range.value; });
      var save = $("#a-save");
      if (save) save.addEventListener("click", async function (event) {
        event.currentTarget.disabled = true;
        try {
          await api("/orgs/agent", {
            method: "PUT",
            body: {
              agent_name: $("#a-name").value.trim(),
              language: $("#a-lang").value,
              persona: $("#a-persona").value.trim(),
              greeting: $("#a-greeting").value.trim(),
              handoff_keywords: $("#a-keywords").value.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
              temperature: Number($("#a-temp").value)
            }
          });
          toast("AI agent sozlamalari saqlandi");
        } catch (error) { toast(error.message, true); }
        finally { event.currentTarget.disabled = false; }
      });
    } catch (error) {
      card.innerHTML = errorState(error);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Platform (super admin)                                              */
  /* ------------------------------------------------------------------ */
  async function renderPlatform() {
    var view = $("#view");
    view.innerHTML = pageHead("Platforma", "Barcha tashkilotlar (super admin)", "") +
      '<div id="platform-body">' + loading() + "</div>";
    try {
      var stats = await api("/admin/stats");
      var planKeys = ["starter", "pro", "business"];
      view.innerHTML = pageHead("Platforma", "Barcha tashkilotlar (super admin)",
        '<button class="btn sm" data-platform-refresh>↻ Yangilash</button>') +
        '<div class="kpis">' +
        kpi("Tashkilotlar", num(stats.orgs), "SaaS tenant", "🏢") +
        kpi("Foydalanuvchilar", num(stats.users), "barcha rollar", "👥") +
        kpi("Suhbatlar", num(stats.conversations), "jami", "💬") +
        kpi("Buyurtmalar", num(stats.orders), "jami", "🛒") +
        kpi("Tushum", money(stats.revenue), "barcha tenant", "💰", true) +
        "</div>" +
        '<div class="card" style="margin-bottom:18px"><div class="card-head"><h3>Tariflar bo\'yicha</h3></div>' +
        '<div class="row" style="gap:22px">' + planKeys.map(function (key) {
          return '<div><div class="muted small">' + h(key) + '</div><div style="font-size:20px;font-weight:700">' +
            num(stats.by_plan[key] || 0) + "</div></div>";
        }).join("") + "</div></div>" +
        '<div class="card"><div class="card-head"><h3>Tashkilotlar</h3><span class="hint">' +
        stats.recent_orgs.length + " ta</span></div>" +
        '<div class="table-wrap"><table><thead><tr><th>Nomi</th><th>Owner</th><th>Tarif</th>' +
        "<th>Xodim</th><th>Suhbat</th><th>Buyurtma</th><th>Tushum</th><th>Yaratilgan</th><th></th></tr></thead><tbody>" +
        stats.recent_orgs.map(function (org) {
          var options = planKeys.map(function (key) {
            return '<option value="' + key + '"' + (org.plan === key ? " selected" : "") + ">" + key + "</option>";
          }).join("");
          return "<tr><td><div class=\"strong\">" + h(org.name) + '</div><div class="sub mono">' + h(org.slug) +
            "</div></td><td class=\"small\">" + h(org.owner_email) + "</td>" +
            '<td><select class="select" data-org-plan="' + h(org.id) + '" style="padding:5px 8px;font-size:12px;max-width:120px">' +
            options + "</select></td><td>" + num(org.users) + "</td><td>" + num(org.conversations) +
            "</td><td>" + num(org.orders) + '</td><td class="mono">' + money(org.revenue) +
            '</td><td class="small">' + dt(org.created_at) + "</td>" +
            '<td><button class="icon-btn" data-open-org="' + h(org.id) + '" title="Shu tashkilotga kirish">↗</button></td></tr>';
        }).join("") + "</tbody></table></div></div>";

      $("[data-platform-refresh]").addEventListener("click", renderPlatform);
      $$("[data-org-plan]", view).forEach(function (select) {
        select.addEventListener("change", async function () {
          try {
            await api("/admin/orgs/" + select.dataset.orgPlan + "/plan", {
              method: "PATCH", body: { plan: select.value }
            });
            toast("Tarif o'zgartirildi");
          } catch (error) { toast(error.message, true); }
        });
      });
      $$("[data-open-org]", view).forEach(function (button) {
        button.addEventListener("click", function () {
          switchOrg(button.dataset.openOrg);
        });
      });
    } catch (error) {
      $("#platform-body").innerHTML = errorState(error);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Router / bootstrap                                                  */
  /* ------------------------------------------------------------------ */
  function allowed(view) {
    if (view === "platform") return state.user && state.user.is_super_admin;
    if (!state.orgId) return false;
    return can(MIN_ROLE[view] || "owner");
  }

  function setNav(view) {
    $$("#main-nav button").forEach(function (button) {
      button.classList.toggle("active", button.dataset.view === view);
    });
    var title = TITLES[view] || ["Dashboard", ""];
    $("#page-title").textContent = title[0];
    $("#page-crumb").textContent = title[1];
    $("#sidebar").classList.remove("open");
  }

  async function route() {
    var requested = (location.hash || "#overview").replace("#", "").split("/")[0] || "overview";
    if (!TITLES[requested] || !allowed(requested)) {
      requested = state.orgId ? "overview" : (state.user && state.user.is_super_admin ? "platform" : "overview");
      if (requested === "platform" && !allowed("platform")) requested = "overview";
    }
    state.view = requested;
    setNav(requested);
    clearInterval(state.timer);
    closeModal();

    if (!state.orgId && requested !== "platform") {
      $("#view").innerHTML = empty("🏢", "Tashkilot tanlanmagan",
        state.user && state.user.is_super_admin
          ? "Platforma bo'limidan tashkilotga kiring."
          : "Hisobingiz birorta tashkilotga bog'lanmagan. Administrator bilan bog'laning.");
      return;
    }

    var renderers = {
      overview: renderOverview,
      conversations: renderConversations,
      analytics: renderAnalytics,
      products: renderProducts,
      orders: renderOrders,
      knowledge: renderKnowledge,
      settings: renderSettings,
      integrations: renderIntegrations,
      team: renderTeam,
      billing: renderBilling,
      platform: renderPlatform
    };
    try {
      await renderers[requested]();
    } catch (error) {
      $("#view").innerHTML = errorState(error);
    }

    if (requested === "conversations") {
      state.timer = setInterval(function () {
        if (state.view !== "conversations") return;
        loadConversationList(false);
        var textarea = $("#reply-text");
        var typing = textarea && (textarea.value.trim() || document.activeElement === textarea);
        if (state.activeConversation && !typing) loadConversation(state.activeConversation, true);
      }, 12000);
    }
    if (requested === "overview") {
      state.timer = setInterval(function () {
        if (state.view === "overview") loadHandoffBadge();
      }, 30000);
    }
  }

  async function switchOrg(orgId) {
    if (!orgId || orgId === state.orgId) return;
    try {
      var data = await api("/auth/switch-org", { method: "POST", body: { org_id: orgId } });
      saveSession(data);
      state.orgId = orgId;
      state.activeConversation = "";
      toast("Tashkilot almashtirildi");
      $("#org-switcher").value = orgId;
      buildSwitcher();
      applyPermissions();
      await route();
      loadHandoffBadge();
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function loadHandoffBadge() {
    if (!state.orgId) return;
    try {
      var rows = await api("/conversations?handoff=true&limit=100");
      var badgeEl = $("#handoff-badge");
      badgeEl.hidden = rows.length === 0;
      badgeEl.textContent = String(rows.length);
    } catch (error) { /* silent */ }
  }

  function bootIcons() {
    $$("#main-nav button[data-icon]").forEach(function (button) {
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("fill", "none");
      svg.setAttribute("stroke", "currentColor");
      svg.setAttribute("stroke-width", "1.8");
      svg.setAttribute("stroke-linecap", "round");
      svg.setAttribute("stroke-linejoin", "round");
      svg.innerHTML = ICONS[button.dataset.icon] || ICONS.grid;
      button.insertBefore(svg, button.firstChild);
    });
  }

  function applyPermissions() {
    $$("#main-nav button").forEach(function (button) {
      if (button.id === "platform-nav") {
        button.classList.toggle("hidden", !(state.user && state.user.is_super_admin));
        return;
      }
      var need = MIN_ROLE[button.dataset.view] || 4;
      button.classList.toggle("hidden", !state.orgId || !can(need));
    });
  }

  function buildSwitcher() {
    var select = $("#org-switcher");
    var orgs = state.me.orgs || [];
    if (!orgs.length) {
      select.innerHTML = '<option value="">Tashkilot yo\'q</option>';
      select.disabled = true;
      return;
    }
    select.innerHTML = (state.orgId ? "" : '<option value="" selected>Tashkilot tanlash</option>') +
      orgs.map(function (org) {
        return '<option value="' + h(org.id) + '"' + (org.id === state.orgId ? " selected" : "") + ">" +
          h(org.name) + " · " + h(org.plan) + "</option>";
      }).join("");
    select.disabled = false;
    select.onchange = function () { switchOrg(select.value); };
  }

  async function boot() {
    if (!state.token) { window.location.href = "/login"; return; }
    bootIcons();
    try {
      state.me = await api("/auth/me");
    } catch (error) {
      if (error.status === 401 || /Sessiya/.test(error.message)) { logout(); return; }
      $("#view").innerHTML = errorState(error);
      return;
    }
    state.user = state.me.user;
    state.role = state.me.role || (state.user.is_super_admin ? "super" : "operator");
    var savedOrg = localStorage.getItem(STORE.org);
    var validOrg = state.me.orgs.some(function (org) { return org.id === savedOrg; });
    state.orgId = validOrg
      ? savedOrg
      : (state.me.active_org_id || (state.user.is_super_admin ? "" : (state.me.orgs[0] || {}).id) || "");

    $("#user-name").textContent = state.user.full_name || state.user.email;
    $("#user-email").textContent = state.user.email;
    $("#user-avatar").textContent = initials(state.user.full_name || state.user.email);
    buildSwitcher();
    applyPermissions();

    $("#logout-btn").addEventListener("click", logout);
    $("#refresh-btn").addEventListener("click", route);
    $("#menu-btn").addEventListener("click", function () { $("#sidebar").classList.toggle("open"); });
    $("#main-nav").addEventListener("click", function (event) {
      var button = event.target.closest("button[data-view]");
      if (!button) return;
      var target = button.dataset.view;
      if (!allowed(target)) { toast("Bu bo'limga ruxsat yo'q", true); return; }
      if (state.view === target) { route(); } else { location.hash = "#" + target; }
    });
    window.addEventListener("hashchange", route);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeModal();
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 860) $("#sidebar").classList.remove("open");
    });

    await route();
    loadHandoffBadge();
  }

  boot();
})();
