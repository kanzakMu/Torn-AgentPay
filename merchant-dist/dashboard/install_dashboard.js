(async function () {
  var manifestUrl = "/.well-known/aimipay.json";
  var discoverUrl = "/_aimipay/discover";
  var healthUrl = "/_aimipay/ops/health";
  var publicConfigUrl = "/aimipay/assets/website/.generated/merchant.public.json";
  var installConfigUrl = "/aimipay/install/config";
  var installHistoryUrl = "/aimipay/install/config/history";
  var historyDiffBaseUrl = "/aimipay/install/config/history/";

  function safeJson(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) {
        throw new Error(url + " -> " + response.status);
      }
      return response.json();
    });
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (response) {
      if (!response.ok) {
        throw new Error(url + " -> " + response.status);
      }
      return response.json();
    });
  }

  function cardChip(label, value, tone) {
    var background = tone === "good" ? "#dcfce7" : tone === "warn" ? "#fef3c7" : "#e2e8f0";
    var color = tone === "good" ? "#166534" : tone === "warn" ? "#92400e" : "#334155";
    return "<div style='padding:10px 14px;border-radius:999px;background:" + background + ";color:" + color + ";font-weight:700;'>" + label + ": " + value + "</div>";
  }

  function setHtml(id, html) {
    var node = document.getElementById(id);
    if (node) {
      node.innerHTML = html;
    }
  }

  function escapeHtml(value) {
    return String(value === undefined || value === null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function statusBadge(label, tone) {
    var colors = {
      good: ["#dcfce7", "#166534"],
      warn: ["#fef3c7", "#92400e"],
      bad: ["#fee2e2", "#991b1b"],
      neutral: ["#e2e8f0", "#334155"]
    };
    var tuple = colors[tone] || colors.neutral;
    return "<span style='display:inline-block;padding:6px 10px;border-radius:999px;background:" + tuple[0] + ";color:" + tuple[1] + ";font-weight:700;'>" + label + "</span>";
  }

  function money(value) {
    if (value === null || value === undefined) {
      return "n/a";
    }
    return String(value);
  }

  function routeCard(route) {
    return "<div style='padding:14px 16px;border-radius:16px;border:1px solid #dbeafe;background:#f8fafc;'>" +
      "<div style='font-weight:700;color:#0f172a;'>" + (route.path || "unknown route") + "</div>" +
      "<div style='margin-top:6px;color:#475569;line-height:1.6;'>" + (route.description || "No description") + "</div>" +
      "<div style='margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;'>" +
      "<span style='padding:6px 10px;border-radius:999px;background:#e0f2fe;color:#075985;font-weight:700;'>" + (route.capability_type || "capability") + "</span>" +
      "<span style='padding:6px 10px;border-radius:999px;background:#ecfccb;color:#3f6212;font-weight:700;'>price " + money(route.price_atomic) + "</span>" +
      statusBadge(route.enabled === false ? "paused" : "enabled", route.enabled === false ? "warn" : "good") +
      "</div>" +
      "<div style='margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;'>" +
      "<button type='button' data-edit-route='" + encodeURIComponent(route.path) + "' data-edit-method='" + encodeURIComponent(route.method || "POST") + "' style='border:none;border-radius:999px;background:#0f766e;color:#ecfeff;padding:10px 14px;font-weight:700;cursor:pointer;'>Edit</button>" +
      "<button type='button' data-toggle-route='" + encodeURIComponent(route.path) + "' data-toggle-method='" + encodeURIComponent(route.method || "POST") + "' data-toggle-enabled='" + (route.enabled === false ? "false" : "true") + "' style='border:none;border-radius:999px;background:#92400e;color:#fef3c7;padding:10px 14px;font-weight:700;cursor:pointer;'>" + (route.enabled === false ? "Enable" : "Pause") + "</button>" +
      "<button type='button' data-delete-route='" + encodeURIComponent(route.path) + "' data-delete-method='" + encodeURIComponent(route.method || "POST") + "' style='border:none;border-radius:999px;background:#991b1b;color:#fee2e2;padding:10px 14px;font-weight:700;cursor:pointer;'>Delete</button>" +
      "</div>" +
      "</div>";
  }

  function planCard(plan) {
    return "<div style='padding:14px 16px;border-radius:16px;border:1px solid #e2e8f0;background:#f8fafc;'>" +
      "<div style='font-weight:700;color:#0f172a;'>" + (plan.name || plan.plan_id || "plan") + "</div>" +
      "<div style='margin-top:6px;color:#475569;line-height:1.6;'>amount " + money(plan.amount_atomic) + "</div>" +
      "<div style='margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;'>" +
      statusBadge(plan.enabled === false ? "paused" : "enabled", plan.enabled === false ? "warn" : "good") +
      "</div>" +
      "<div style='margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;'>" +
      "<button type='button' data-edit-plan='" + encodeURIComponent(plan.plan_id || "") + "' style='border:none;border-radius:999px;background:#0f766e;color:#ecfeff;padding:10px 14px;font-weight:700;cursor:pointer;'>Edit</button>" +
      "<button type='button' data-toggle-plan='" + encodeURIComponent(plan.plan_id || "") + "' data-toggle-enabled='" + (plan.enabled === false ? "false" : "true") + "' style='border:none;border-radius:999px;background:#92400e;color:#fef3c7;padding:10px 14px;font-weight:700;cursor:pointer;'>" + (plan.enabled === false ? "Enable" : "Pause") + "</button>" +
      "<button type='button' data-delete-plan='" + encodeURIComponent(plan.plan_id || "") + "' style='border:none;border-radius:999px;background:#991b1b;color:#fee2e2;padding:10px 14px;font-weight:700;cursor:pointer;'>Delete</button>" +
      "</div>" +
      "</div>";
  }

  function historyCard(item) {
    return "<div style='padding:14px 16px;border-radius:16px;border:1px solid #e2e8f0;background:#f8fafc;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;'>" +
      "<div><strong>Revision " + item.revision + "</strong><br><span style='color:#64748b;'>reason: " + item.reason + "</span></div>" +
      "<div style='display:flex;gap:10px;flex-wrap:wrap;'>" +
      "<button type='button' data-preview-revision='" + item.revision + "' style='border:none;border-radius:999px;background:#0f766e;color:#ecfeff;padding:10px 14px;font-weight:700;cursor:pointer;'>Preview diff</button>" +
      "<button type='button' data-rollback-revision='" + item.revision + "' style='border:none;border-radius:999px;background:#111827;color:#ecfeff;padding:10px 14px;font-weight:700;cursor:pointer;'>Rollback</button>" +
      "</div>" +
      "</div>";
  }

  function runtimeProfileCard(runtime) {
    return "<div style='display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));'>" +
      [
        ["Network Profile", runtime.network_profile || "custom"],
        ["Network Name", runtime.network_name || "n/a"],
        ["Chain ID", runtime.chain_id || "n/a"],
        ["Settlement Backend", runtime.settlement_backend || "n/a"],
        ["Resolved RPC", runtime.resolved_chain_rpc || "n/a"],
        ["Contract", runtime.contract_address || "n/a"],
        ["Token", runtime.token_address || "n/a"],
        ["Seller", runtime.seller_address || "n/a"]
      ].map(function (item) {
        return "<div style='padding:14px 16px;border-radius:16px;background:#f8fafc;border:1px solid #e2e8f0;'>" +
          "<div style='font-size:12px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;color:#0f766e;'>" + escapeHtml(item[0]) + "</div>" +
          "<div style='margin-top:8px;color:#0f172a;font-weight:700;word-break:break-all;line-height:1.6;'>" + escapeHtml(item[1]) + "</div>" +
          "</div>";
      }).join("") +
      "</div>";
  }

  function renderChangeCard(title, tone, lines) {
    var palette = {
      add: ["#ecfccb", "#3f6212"],
      remove: ["#fee2e2", "#991b1b"],
      change: ["#dbeafe", "#1d4ed8"],
      neutral: ["#f1f5f9", "#334155"]
    };
    var tuple = palette[tone] || palette.neutral;
    return "<div style='padding:14px 16px;border-radius:16px;border:1px solid " + tuple[0] + ";background:" + tuple[0] + "55;'>" +
      "<div style='font-weight:700;color:" + tuple[1] + ";'>" + escapeHtml(title) + "</div>" +
      "<div style='margin-top:8px;display:grid;gap:6px;color:#475569;line-height:1.6;'>" +
      lines.map(function (line) { return "<div>" + escapeHtml(line) + "</div>"; }).join("") +
      "</div></div>";
  }

  function summarizeDiff(diff) {
    return [
      { label: "Routes Added", count: (diff.routes_added || []).length, tone: "good" },
      { label: "Routes Removed", count: (diff.routes_removed || []).length, tone: "warn" },
      { label: "Routes Changed", count: (diff.routes_changed || []).length, tone: "neutral" },
      { label: "Plans Added", count: (diff.plans_added || []).length, tone: "good" },
      { label: "Plans Removed", count: (diff.plans_removed || []).length, tone: "warn" },
      { label: "Plans Changed", count: (diff.plans_changed || []).length, tone: "neutral" }
    ];
  }

  function renderDiffPreview(revision, payload) {
    var panel = document.getElementById("diff-preview-panel");
    var title = document.getElementById("diff-preview-title");
    var message = document.getElementById("diff-preview-message");
    var summary = document.getElementById("diff-preview-summary");
    var cards = document.getElementById("diff-preview-cards");
    if (!panel || !title || !message || !summary || !cards) {
      return;
    }
    var diff = payload.diff || {};
    title.textContent = "Diff Preview";
    message.textContent = "Revision " + revision + " would change the merchant config in these ways.";
    summary.innerHTML = summarizeDiff(diff).map(function (item) {
      return statusBadge(item.label + ": " + item.count, item.count ? item.tone : "neutral");
    }).join("");

    var cardHtml = [];
    if (diff.service_changed) {
      cardHtml.push(renderChangeCard("Service Metadata", "change", ["Service name or description would change."]));
    }
    if (diff.branding_changed) {
      cardHtml.push(renderChangeCard("Branding", "change", ["Display title, accent color, or support email would change."]));
    }
    (diff.routes_added || []).forEach(function (item) {
      cardHtml.push(renderChangeCard("Route Added", "add", [item.path + " (" + (item.capability_type || "capability") + ")", "price " + item.price_atomic]));
    });
    (diff.routes_removed || []).forEach(function (item) {
      cardHtml.push(renderChangeCard("Route Removed", "remove", [item.path + " (" + (item.capability_type || "capability") + ")", "price " + item.price_atomic]));
    });
    (diff.routes_changed || []).forEach(function (item) {
      cardHtml.push(
        renderChangeCard(
          "Route Changed",
          "change",
          [
            (item.after.path || item.before.path) + " (" + ((item.after.capability_type || item.before.capability_type) || "capability") + ")",
            "before: " + item.before.price_atomic + " / " + (item.before.enabled === false ? "paused" : "enabled"),
            "after: " + item.after.price_atomic + " / " + (item.after.enabled === false ? "paused" : "enabled")
          ]
        )
      );
    });
    (diff.plans_added || []).forEach(function (item) {
      cardHtml.push(renderChangeCard("Plan Added", "add", [item.plan_id + " - " + item.name, "amount " + item.amount_atomic]));
    });
    (diff.plans_removed || []).forEach(function (item) {
      cardHtml.push(renderChangeCard("Plan Removed", "remove", [item.plan_id + " - " + item.name, "amount " + item.amount_atomic]));
    });
    (diff.plans_changed || []).forEach(function (item) {
      cardHtml.push(
        renderChangeCard(
          "Plan Changed",
          "change",
          [
            (item.after.plan_id || item.before.plan_id) + " - " + (item.after.name || item.before.name),
            "before: " + item.before.amount_atomic + " / " + (item.before.enabled === false ? "paused" : "enabled"),
            "after: " + item.after.amount_atomic + " / " + (item.after.enabled === false ? "paused" : "enabled")
          ]
        )
      );
    });
    cards.innerHTML = cardHtml.length ? cardHtml.join("") : renderChangeCard("No Differences", "neutral", ["This revision matches the current config."]);
    panel.style.display = "block";
  }

  function hideDiffPreview() {
    var panel = document.getElementById("diff-preview-panel");
    if (panel) {
      panel.style.display = "none";
    }
  }

  function showOperationBanner(titleText, messageText, diff) {
    var banner = document.getElementById("operation-banner");
    var title = document.getElementById("operation-banner-title");
    var message = document.getElementById("operation-banner-message");
    var summary = document.getElementById("operation-banner-summary");
    if (!banner || !title || !message || !summary) {
      return;
    }
    title.textContent = titleText;
    message.textContent = messageText;
    summary.innerHTML = summarizeDiff(diff || {}).map(function (item) {
      return item.count ? statusBadge(item.label + ": " + item.count, item.tone) : "";
    }).join("");
    banner.style.display = "block";
  }

  function hideOperationBanner() {
    var banner = document.getElementById("operation-banner");
    if (banner) {
      banner.style.display = "none";
    }
  }

  function setCopyButton(snippet) {
    var button = document.getElementById("copy-embed-button");
    var status = document.getElementById("copy-status");
    if (!button) {
      return;
    }
    button.onclick = async function () {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(snippet);
        } else {
          var area = document.createElement("textarea");
          area.value = snippet;
          document.body.appendChild(area);
          area.select();
          document.execCommand("copy");
          document.body.removeChild(area);
        }
        if (status) {
          status.textContent = "Snippet copied.";
        }
      } catch (error) {
        if (status) {
          status.textContent = "Copy failed. Select and copy manually.";
        }
      }
    };
  }

  function setRouteDraftBuilder(refresh, currentConfig) {
    var button = document.getElementById("route-draft-button");
    var saveButton = document.getElementById("route-save-button");
    var preview = document.getElementById("route-draft-preview");
    if (!button || !preview || !saveButton) {
      return;
    }
    button.onclick = function () {
      var payload = {
        path: document.getElementById("route-path-input").value,
        capability_type: document.getElementById("route-capability-input").value,
        price_atomic: Number(document.getElementById("route-price-input").value || "0"),
        description: document.getElementById("route-description-input").value,
        pricing_model: "fixed_per_call",
        usage_unit: "request",
        delivery_mode: "sync"
      };
      preview.textContent = JSON.stringify(payload, null, 2);
    };
    saveButton.onclick = async function () {
      var payload = {
        path: document.getElementById("route-path-input").value,
        capability_type: document.getElementById("route-capability-input").value,
        price_atomic: Number(document.getElementById("route-price-input").value || "0"),
        description: document.getElementById("route-description-input").value,
        pricing_model: "fixed_per_call",
        usage_unit: "request",
        delivery_mode: "sync"
      };
      var existing = ((currentConfig && currentConfig.routes) || []).find(function (item) {
        return item.path === payload.path && (item.method || "POST") === "POST";
      });
      await postJson("/aimipay/install/config/route", payload);
      preview.textContent = JSON.stringify(payload, null, 2);
      showOperationBanner(
        existing ? "Route Updated" : "Route Saved",
        existing ? "The route was updated and republished locally." : "A new route was added to the merchant config.",
        {
          routes_added: existing ? [] : [payload],
          routes_removed: [],
          routes_changed: existing ? [{ before: existing, after: payload }] : [],
          plans_added: [],
          plans_removed: [],
          plans_changed: []
        }
      );
      if (typeof refresh === "function") {
        await refresh();
      }
    };
  }

  function bindRouteActions(config, refresh) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-edit-route]"), function (button) {
      button.onclick = function () {
        var path = decodeURIComponent(button.getAttribute("data-edit-route"));
        var method = decodeURIComponent(button.getAttribute("data-edit-method") || "POST");
        var route = (config.routes || []).find(function (item) {
          return item.path === path && (item.method || "POST") === method;
        });
        if (!route) {
          return;
        }
        document.getElementById("route-path-input").value = route.path || "";
        document.getElementById("route-capability-input").value = route.capability_type || "api";
        document.getElementById("route-price-input").value = route.price_atomic || 0;
        document.getElementById("route-description-input").value = route.description || "";
        var preview = document.getElementById("route-draft-preview");
        if (preview) {
          preview.textContent = JSON.stringify(route, null, 2);
        }
      };
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-delete-route]"), function (button) {
      button.onclick = async function () {
        var route = (config.routes || []).find(function (item) {
          return item.path === decodeURIComponent(button.getAttribute("data-delete-route")) &&
            (item.method || "POST") === decodeURIComponent(button.getAttribute("data-delete-method") || "POST");
        });
        await fetch("/aimipay/install/config/route", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            path: decodeURIComponent(button.getAttribute("data-delete-route")),
            method: decodeURIComponent(button.getAttribute("data-delete-method") || "POST")
          })
        });
        showOperationBanner("Route Deleted", "The route was removed from the merchant config.", {
          routes_added: [],
          routes_removed: route ? [route] : [],
          routes_changed: [],
          plans_added: [],
          plans_removed: [],
          plans_changed: []
        });
        await refresh();
      };
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-toggle-route]"), function (button) {
      button.onclick = async function () {
        var currentlyEnabled = button.getAttribute("data-toggle-enabled") !== "false";
        var route = (config.routes || []).find(function (item) {
          return item.path === decodeURIComponent(button.getAttribute("data-toggle-route")) &&
            (item.method || "POST") === decodeURIComponent(button.getAttribute("data-toggle-method") || "POST");
        });
        await postJson("/aimipay/install/config/route/toggle", {
          path: decodeURIComponent(button.getAttribute("data-toggle-route")),
          method: decodeURIComponent(button.getAttribute("data-toggle-method") || "POST"),
          enabled: !currentlyEnabled
        });
        showOperationBanner(
          currentlyEnabled ? "Route Paused" : "Route Enabled",
          currentlyEnabled ? "The route stays in config but is hidden from manifest discovery." : "The route is active again and will appear in manifest discovery.",
          {
            routes_added: [],
            routes_removed: [],
            routes_changed: route ? [{ before: route, after: Object.assign({}, route, { enabled: !currentlyEnabled }) }] : [],
            plans_added: [],
            plans_removed: [],
            plans_changed: []
          }
        );
        await refresh();
      };
    });
  }

  function bindPlanActions(config, refresh) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-edit-plan]"), function (button) {
      button.onclick = function () {
        var planId = decodeURIComponent(button.getAttribute("data-edit-plan"));
        var plan = (config.plans || []).find(function (item) {
          return item.plan_id === planId;
        });
        if (!plan) {
          return;
        }
        document.getElementById("plan-id-input").value = plan.plan_id || "";
        document.getElementById("plan-name-input").value = plan.name || "";
        document.getElementById("plan-amount-input").value = plan.amount_atomic || 0;
        document.getElementById("plan-subscribe-input").value = plan.subscribe_path || "";
        var preview = document.getElementById("plan-draft-preview");
        if (preview) {
          preview.textContent = JSON.stringify(plan, null, 2);
        }
      };
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-delete-plan]"), function (button) {
      button.onclick = async function () {
        var plan = (config.plans || []).find(function (item) {
          return item.plan_id === decodeURIComponent(button.getAttribute("data-delete-plan"));
        });
        await fetch("/aimipay/install/config/plan/" + encodeURIComponent(decodeURIComponent(button.getAttribute("data-delete-plan"))), {
          method: "DELETE"
        });
        showOperationBanner("Plan Deleted", "The plan was removed from the merchant config.", {
          routes_added: [],
          routes_removed: [],
          routes_changed: [],
          plans_added: [],
          plans_removed: plan ? [plan] : [],
          plans_changed: []
        });
        await refresh();
      };
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-toggle-plan]"), function (button) {
      button.onclick = async function () {
        var currentlyEnabled = button.getAttribute("data-toggle-enabled") !== "false";
        var plan = (config.plans || []).find(function (item) {
          return item.plan_id === decodeURIComponent(button.getAttribute("data-toggle-plan"));
        });
        await postJson("/aimipay/install/config/plan/" + encodeURIComponent(decodeURIComponent(button.getAttribute("data-toggle-plan"))) + "/toggle", {
          enabled: !currentlyEnabled
        });
        showOperationBanner(
          currentlyEnabled ? "Plan Paused" : "Plan Enabled",
          currentlyEnabled ? "The plan stays in config but is hidden from manifest discovery." : "The plan is active again and will appear in manifest discovery.",
          {
            routes_added: [],
            routes_removed: [],
            routes_changed: [],
            plans_added: [],
            plans_removed: [],
            plans_changed: plan ? [{ before: plan, after: Object.assign({}, plan, { enabled: !currentlyEnabled }) }] : []
          }
        );
        await refresh();
      };
    });
  }

  function bindHistoryActions(refresh) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-rollback-revision]"), function (button) {
      button.onclick = async function () {
        var revision = button.getAttribute("data-rollback-revision");
        var diffPayload = await safeJson(historyDiffBaseUrl + revision + "/diff");
        await postJson("/aimipay/install/config/rollback/" + revision, {});
        showOperationBanner(
          "Rollback Applied",
          "The merchant config was restored from revision " + revision + ".",
          diffPayload.diff || {}
        );
        await refresh();
      };
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-preview-revision]"), function (button) {
      button.onclick = async function () {
        var revision = button.getAttribute("data-preview-revision");
        var payload = await safeJson(historyDiffBaseUrl + revision + "/diff");
        renderDiffPreview(revision, payload);
      };
    });
  }

  function setPlanDraftBuilder(refresh, currentConfig) {
    var button = document.getElementById("plan-draft-button");
    var saveButton = document.getElementById("plan-save-button");
    var preview = document.getElementById("plan-draft-preview");
    if (!button || !preview || !saveButton) {
      return;
    }
    button.onclick = function () {
      var payload = {
        plan_id: document.getElementById("plan-id-input").value,
        name: document.getElementById("plan-name-input").value,
        amount_atomic: Number(document.getElementById("plan-amount-input").value || "0"),
        subscribe_path: document.getElementById("plan-subscribe-input").value
      };
      preview.textContent = JSON.stringify(payload, null, 2);
    };
    saveButton.onclick = async function () {
      var payload = {
        plan_id: document.getElementById("plan-id-input").value,
        name: document.getElementById("plan-name-input").value,
        amount_atomic: Number(document.getElementById("plan-amount-input").value || "0"),
        subscribe_path: document.getElementById("plan-subscribe-input").value
      };
      var existing = ((currentConfig && currentConfig.plans) || []).find(function (item) {
        return item.plan_id === payload.plan_id;
      });
      await postJson("/aimipay/install/config/plan", payload);
      preview.textContent = JSON.stringify(payload, null, 2);
      showOperationBanner(
        existing ? "Plan Updated" : "Plan Saved",
        existing ? "The plan was updated locally." : "A new plan was added to the merchant config.",
        {
          routes_added: [],
          routes_removed: [],
          routes_changed: [],
          plans_added: existing ? [] : [payload],
          plans_removed: [],
          plans_changed: existing ? [{ before: existing, after: payload }] : []
        }
      );
      if (typeof refresh === "function") {
        await refresh();
      }
    };
  }

  function setBrandingPreview(initialBrand, refresh, currentPublicConfig) {
    var button = document.getElementById("branding-preview-button");
    var saveButton = document.getElementById("branding-save-button");
    var colorInput = document.getElementById("brand-color-input");
    var titleInput = document.getElementById("brand-title-input");
    var supportInput = document.getElementById("brand-support-input");
    var titleNode = document.getElementById("branding-preview-title");
    var supportNode = document.getElementById("branding-preview-support");
    var cardNode = document.getElementById("branding-preview-card");
    if (!button || !saveButton || !colorInput || !titleInput || !supportInput || !titleNode || !supportNode || !cardNode) {
      return;
    }

    if (initialBrand && initialBrand.accent_color) {
      colorInput.value = initialBrand.accent_color;
    }
    if (initialBrand && initialBrand.support_email) {
      supportInput.value = initialBrand.support_email;
    }

    button.onclick = function () {
      var color = colorInput.value || "#0f766e";
      var title = titleInput.value || "Pay with AimiPay";
      var support = supportInput.value || "support@example.com";
      titleNode.textContent = title;
      supportNode.textContent = support;
      supportNode.style.color = color;
      cardNode.style.boxShadow = "0 12px 40px " + color + "22";
      cardNode.style.borderColor = color + "55";
    };
    saveButton.onclick = async function () {
      var payload = {
        display_title: titleInput.value || "Pay with AimiPay",
        accent_color: colorInput.value || "#0f766e",
        support_email: supportInput.value || "support@example.com"
      };
      await postJson("/aimipay/install/config/branding", {
        display_title: payload.display_title,
        accent_color: payload.accent_color,
        support_email: payload.support_email
      });
      showOperationBanner(
        "Branding Saved",
        "Merchant branding was updated for the install dashboard and public config.",
        {
          service_changed: false,
          branding_changed: true,
          routes_added: [],
          routes_removed: [],
          routes_changed: [],
          plans_added: [],
          plans_removed: [],
          plans_changed: []
        }
      );
      if (typeof refresh === "function") {
        await refresh();
      }
    };
  }

  async function renderDashboard() {
    hideDiffPreview();
    var results = await Promise.allSettled([
      safeJson(manifestUrl),
      safeJson(discoverUrl),
      safeJson(healthUrl),
      safeJson(publicConfigUrl),
      safeJson(installConfigUrl),
      safeJson(installHistoryUrl)
    ]);

    var manifest = results[0].status === "fulfilled" ? results[0].value : null;
    var discover = results[1].status === "fulfilled" ? results[1].value : null;
    var health = results[2].status === "fulfilled" ? results[2].value : null;
    var publicConfig = results[3].status === "fulfilled" ? results[3].value : null;
    var installConfig = results[4].status === "fulfilled" ? results[4].value : null;
    var history = results[5].status === "fulfilled" ? results[5].value : { versions: [] };
    var brand = publicConfig && publicConfig.brand ? publicConfig.brand : {};
    var runtimeProfile = installConfig && installConfig.runtime ? installConfig.runtime : null;

    var summary = [];
    summary.push(cardChip("Manifest", manifest ? "live" : "unavailable", manifest ? "good" : "warn"));
    summary.push(cardChip("Discover", discover ? "live" : "unavailable", discover ? "good" : "warn"));
    summary.push(cardChip("Health", health && health.ok ? "green" : "needs review", health && health.ok ? "good" : "warn"));
    summary.push(cardChip("Embed", "website starter ready", "neutral"));
    setHtml("hero-summary", summary.join(""));

    setHtml(
      "health-status",
      health
        ? "<strong>" + (health.ok ? "Healthy" : "Needs review") + "</strong><br>Checks: " + ((health.config_checks || []).length) + "<br>Metrics keys: " + Object.keys(health.metrics || {}).length
        : "Health endpoint unavailable."
    );
    setHtml(
      "health-diagnostics",
      health && (health.config_checks || []).length
        ? health.config_checks.slice(0, 6).map(function (item) {
            return "<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:14px;background:#f8fafc;border:1px solid #e2e8f0;'>" +
              "<div><strong>" + item.name + "</strong><br><span style='color:#64748b;'>" + (item.detail || "") + "</span></div>" +
              statusBadge(item.ok ? "ok" : "review", item.ok ? "good" : "warn") +
              "</div>";
          }).join("")
        : "<div style='color:#64748b;'>No health diagnostics available yet.</div>"
    );
    setHtml(
      "manifest-status",
      manifest
        ? "<strong>" + manifest.service_name + "</strong><br>Routes: " + (manifest.routes || []).length + "<br>Plans: " + (manifest.plans || []).length
        : "Manifest unavailable."
    );
    setHtml(
      "manifest-diagnostics",
      manifest
        ? [
            "<div style='display:flex;gap:8px;flex-wrap:wrap;'>" +
              statusBadge((manifest.routes || []).length + " routes", (manifest.routes || []).length ? "good" : "warn") +
              statusBadge((manifest.plans || []).length + " plans", (manifest.plans || []).length ? "good" : "neutral") +
              statusBadge(manifest.primary_chain && manifest.primary_chain.chain ? manifest.primary_chain.chain : "tron", "neutral") +
            "</div>"
          ].join("")
        : "<div style='color:#64748b;'>Manifest checks could not be loaded.</div>"
    );
    setHtml(
      "discover-status",
      discover
        ? "<strong>" + (discover.chain || "tron") + "</strong><br>Seller: " + (discover.seller || "n/a") + "<br>Settlement: " + (discover.settlement_backend || "n/a")
        : "Discovery unavailable."
    );
    setHtml(
      "discover-diagnostics",
      discover
        ? "<div style='display:flex;gap:8px;flex-wrap:wrap;'>" +
            statusBadge(discover.channel_scheme || "tron-contract", "neutral") +
            statusBadge(discover.settlement_backend || "unknown backend", discover.settlement_backend ? "good" : "warn") +
            statusBadge(discover.default_deposit_atomic ? "deposit ready" : "deposit missing", discover.default_deposit_atomic ? "good" : "warn") +
          "</div>"
        : "<div style='color:#64748b;'>Discovery diagnostics unavailable.</div>"
    );
    setHtml(
      "runtime-profile",
      runtimeProfile
        ? runtimeProfileCard(runtimeProfile)
        : "<div style='color:#64748b;'>Runtime profile unavailable.</div>"
    );

    var nextStep = "";
    if (!health || !health.ok) {
      nextStep = "<div style='padding:14px 16px;border-radius:18px;background:#1e293b;color:#e2e8f0;line-height:1.7;'>Review <code>/_aimipay/ops/health</code> before exposing traffic.</div>";
    } else if (!manifest || !(manifest.routes || []).length) {
      nextStep = "<div style='padding:14px 16px;border-radius:18px;background:#1e293b;color:#e2e8f0;line-height:1.7;'>Publish your first paid route so agents have something to buy.</div>";
    } else {
      nextStep = "<div style='padding:14px 16px;border-radius:18px;background:#1e293b;color:#e2e8f0;line-height:1.7;'>Runtime looks healthy. Copy the embed starter and share the manifest URL with partner agents.</div>" +
        "<a href='#embed' style='display:inline-block;margin-top:10px;text-decoration:none;padding:12px 16px;border-radius:999px;background:#14b8a6;color:#042f2e;font-weight:700;'>View embed starter</a>";
    }
    setHtml("next-step-card", nextStep);

    var merchantBaseUrl = publicConfig && publicConfig.merchant_base_url ? publicConfig.merchant_base_url : window.location.origin;
    var links = [
      { label: "Manifest", href: merchantBaseUrl + "/.well-known/aimipay.json" },
      { label: "Discover", href: merchantBaseUrl + "/_aimipay/discover" },
      { label: "Protocol Reference", href: merchantBaseUrl + "/_aimipay/protocol/reference" },
      { label: "Ops Health", href: merchantBaseUrl + "/_aimipay/ops/health" }
    ];
    setHtml(
      "merchant-links",
      links.map(function (item) {
        return "<div style='padding:14px 16px;border-radius:16px;border:1px solid #cbd5e1;background:#f8fafc;'>" +
          "<a href='" + item.href + "' style='color:#0f172a;text-decoration:none;font-weight:600;'>" + item.label + "</a><br>" +
          "<span style='font-weight:400;color:#475569;'>" + item.href + "</span>" +
          "</div>";
      }).join("")
    );

    setHtml(
      "routes-list",
      installConfig && (installConfig.routes || []).length
        ? installConfig.routes.map(routeCard).join("")
        : "No paid routes published yet."
    );
    setHtml(
      "plans-list",
      installConfig && (installConfig.plans || []).length
        ? installConfig.plans.map(planCard).join("")
        : "No plans published yet."
    );
    setHtml(
      "brand-config",
      "<div style='font-size:12px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;color:#0f766e;'>Brand config</div>" +
      "<div style='margin-top:10px;display:grid;gap:8px;color:#475569;line-height:1.7;'>" +
      "<div><strong>Service:</strong> " + (publicConfig && publicConfig.service_name ? publicConfig.service_name : "n/a") + "</div>" +
      "<div><strong>Accent color:</strong> <span style='display:inline-block;width:12px;height:12px;border-radius:999px;background:" + (brand.accent_color || "#0f766e") + ";margin-right:8px;vertical-align:middle;'></span>" + (brand.accent_color || "#0f766e") + "</div>" +
      "<div><strong>Support:</strong> " + (brand.support_email || "n/a") + "</div>" +
      "</div>"
    );
    setHtml(
      "history-list",
      history && (history.versions || []).length
        ? history.versions.map(historyCard).join("")
        : "No saved versions yet."
    );

    var snippet =
      "<div\\n" +
      "  data-aimipay-checkout\\n" +
      "  data-merchant-base-url=\\"" + merchantBaseUrl + "\\"\\n" +
      "  data-title=\\"Pay with AimiPay\\"\\n" +
      "  data-description=\\"Turn your website or SaaS tool into an agent-native paid capability.\\"\\n" +
      "  data-accent-color=\\"" + (brand.accent_color || "#0f766e") + "\\"></div>\\n\\n" +
      "<script src=\\"" + merchantBaseUrl + "/aimipay/assets/website/aimipay.checkout.js\\"><\\/script>";
    var snippetNode = document.getElementById("embed-snippet");
    if (snippetNode) {
      snippetNode.textContent = snippet;
    }
    setCopyButton(snippet);
    setRouteDraftBuilder(renderDashboard, installConfig || { routes: [] });
    setPlanDraftBuilder(renderDashboard, installConfig || { plans: [] });
    setBrandingPreview(brand, renderDashboard, publicConfig || {});
    bindRouteActions(installConfig || { routes: [] }, renderDashboard);
    bindPlanActions(installConfig || { plans: [] }, renderDashboard);
    bindHistoryActions(renderDashboard);

    var assetLinks = [
      { label: "Website starter script", href: "/aimipay/assets/website/aimipay.checkout.js" },
      { label: "Website embed example", href: "/aimipay/assets/website/embed.checkout.html" },
      { label: "Public merchant config", href: "/aimipay/assets/website/.generated/merchant.public.json" },
      { label: "Merchant install kit README", href: "/aimipay/assets/README.md" }
    ];
    setHtml(
      "asset-links",
      assetLinks.map(function (item) {
        return "<a href='" + item.href + "' style='padding:14px 16px;border-radius:16px;border:1px solid #cbd5e1;background:#f8fafc;color:#0f172a;text-decoration:none;font-weight:600;'>" + item.label + "</a>";
      }).join("")
    );
  }

  try {
    var closeBanner = document.getElementById("operation-banner-close");
    if (closeBanner) {
      closeBanner.onclick = hideOperationBanner;
    }
    var closeDiff = document.getElementById("diff-preview-close");
    if (closeDiff) {
      closeDiff.onclick = hideDiffPreview;
    }
    await renderDashboard();
  } catch (error) {
    setHtml("health-status", "Failed to load merchant dashboard data.");
    setHtml("manifest-status", String(error));
    setHtml("discover-status", "Check whether the merchant runtime is running and public config exists.");
  }
})();
