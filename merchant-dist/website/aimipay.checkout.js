(function () {
  function renderCard(target, options) {
    var baseUrl = (options.merchantBaseUrl || "").replace(/\/$/, "");
    var title = options.title || "Pay with AimiPay";
    var description = options.description || "Expose agent-native paid capabilities on your site or SaaS product.";
    var accent = options.accentColor || "#0f766e";
    var card = document.createElement("section");
    card.setAttribute("data-aimipay-widget", "card");
    card.style.border = "1px solid #d1d5db";
    card.style.borderRadius = "16px";
    card.style.padding = "20px";
    card.style.background = "linear-gradient(180deg, #f8fffd 0%, #ffffff 100%)";
    card.style.boxShadow = "0 8px 30px rgba(15, 118, 110, 0.08)";
    card.style.maxWidth = "520px";
    card.style.fontFamily = "'Segoe UI', Arial, sans-serif";
    card.innerHTML =
      "<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;'>" +
      "<div>" +
      "<div style='font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:" + accent + ";'>AimiPay</div>" +
      "<h2 style='margin:8px 0 6px;font-size:28px;line-height:1.1;color:#111827;'>" + title + "</h2>" +
      "<p style='margin:0;color:#4b5563;line-height:1.6;'>" + description + "</p>" +
      "</div>" +
      "<div style='min-width:88px;text-align:right;color:" + accent + ";font-weight:700;'>Agent Ready</div>" +
      "</div>" +
      "<div style='display:flex;gap:12px;flex-wrap:wrap;margin-top:18px;'>" +
      "<a href='" + baseUrl + "/.well-known/aimipay.json' style='text-decoration:none;padding:12px 16px;border-radius:999px;background:" + accent + ";color:white;font-weight:600;'>Manifest</a>" +
      "<a href='" + baseUrl + "/_aimipay/discover' style='text-decoration:none;padding:12px 16px;border-radius:999px;border:1px solid #cbd5e1;color:#0f172a;font-weight:600;background:#ffffff;'>Discover</a>" +
      "<a href='" + baseUrl + "/_aimipay/protocol/reference' style='text-decoration:none;padding:12px 16px;border-radius:999px;border:1px solid #cbd5e1;color:#0f172a;font-weight:600;background:#ffffff;'>Protocol</a>" +
      "</div>" +
      "<div style='margin-top:18px;padding:12px 14px;border-radius:12px;background:#f1f5f9;color:#334155;line-height:1.6;'>" +
      "Website starter card for merchants. Agents still complete checkout through the buyer-side AimiPay lifecycle." +
      "</div>";
    target.innerHTML = "";
    target.appendChild(card);
  }

  function mount(selector, options) {
    var target = typeof selector === "string" ? document.querySelector(selector) : selector;
    if (!target) {
      return null;
    }
    renderCard(target, options || {});
    return target;
  }

  function autoMount() {
    var nodes = document.querySelectorAll("[data-aimipay-checkout]");
    Array.prototype.forEach.call(nodes, function (node) {
      mount(node, {
        merchantBaseUrl: node.getAttribute("data-merchant-base-url") || "",
        title: node.getAttribute("data-title") || "Pay with AimiPay",
        description: node.getAttribute("data-description") || "",
        accentColor: node.getAttribute("data-accent-color") || "#0f766e"
      });
    });
  }

  window.AimiPayMerchantWidget = {
    mount: mount
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoMount);
  } else {
    autoMount();
  }
})();
