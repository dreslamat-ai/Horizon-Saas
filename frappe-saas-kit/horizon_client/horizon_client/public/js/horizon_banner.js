/* Horizon subscription banner + رابط «اشتراكي» الدائم في قائمة المستخدم.
   Colors follow Horizon identity: navy #1D2D44, pending #B8860B, error #B04A3F. */
(function () {
  if (!window.frappe || frappe.session.user === "Guest") return;

  // «اشتراكي» في قائمة المستخدم دايمًا — العميل لازم يلاقي حسابه من غير ما يحفظ رابطًا
  var tries = 0;
  var addMenuItem = setInterval(function () {
    tries++;
    var menu = document.querySelector(".dropdown-navbar-user .dropdown-menu");
    if (menu && !menu.querySelector(".horizon-sub-link")) {
      var a = document.createElement("a");
      a.className = "dropdown-item horizon-sub-link";
      a.href = "/subscription";
      a.textContent = "اشتراكي والفواتير";
      menu.prepend(a);
      clearInterval(addMenuItem);
    }
    if (tries > 20) clearInterval(addMenuItem);
  }, 500);

  frappe.call({
    method: "horizon_client.api.subscription_info",
    callback: function (r) {
      var d = r.message || {};
      if (d.days_left === null || d.days_left === undefined || d.days_left > 7) return;
      var expired = d.days_left < 0;
      var bg = expired ? "#B04A3F" : "#B8860B";
      var txt = expired
        ? "انتهى اشتراكك في باقة " + (d.plan || "Horizon") + " — اضغط للتجديد الآن"
        : "باقتك (" + (d.plan || "Horizon") + ") تنتهي خلال " + d.days_left + " يوم — اضغط للتجديد";
      var bar = document.createElement("div");
      bar.setAttribute("dir", "rtl");
      bar.style.cssText =
        "position:sticky;top:0;z-index:1030;background:" + bg +
        ";color:#fff;font-family:Cairo,sans-serif;font-weight:700;cursor:pointer;" +
        "text-align:center;padding:8px 14px;font-size:13.5px";
      bar.textContent = txt;
      bar.addEventListener("click", function () { window.location.href = "/subscription"; });
      document.body.prepend(bar);
    },
  });
})();
