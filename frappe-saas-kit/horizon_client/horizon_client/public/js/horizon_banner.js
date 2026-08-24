/* Horizon subscription banner — shows only in the last 7 days of the subscription.
   Colors follow Horizon identity: navy #1D2D44, pending #B8860B, error #B04A3F. */
(function () {
  if (!window.frappe || frappe.session.user === "Guest") return;
  frappe.call({
    method: "horizon_client.api.subscription_info",
    callback: function (r) {
      var d = r.message || {};
      if (d.days_left === null || d.days_left === undefined || d.days_left > 7) return;
      var expired = d.days_left < 0;
      var bg = expired ? "#B04A3F" : "#B8860B";
      var txt = expired
        ? "انتهى اشتراكك في باقة " + (d.plan || "Horizon") + " — جدّد الآن لتجنب إيقاف النظام"
        : "باقتك (" + (d.plan || "Horizon") + ") تنتهي خلال " + d.days_left + " يوم — جدّد الآن";
      var bar = document.createElement("div");
      bar.setAttribute("dir", "rtl");
      bar.style.cssText =
        "position:sticky;top:0;z-index:1030;background:" + bg +
        ";color:#fff;font-family:Cairo,sans-serif;font-weight:700;" +
        "text-align:center;padding:8px 14px;font-size:13.5px";
      bar.textContent = txt;
      document.body.prepend(bar);
    },
  });
})();
