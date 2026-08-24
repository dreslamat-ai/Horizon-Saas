/* عدّاد الاشتراك — شريط ثابت أعلى الرئيسية دايمًا (طلب المالك):
   أزرق كحلي أثناء التجربة، كهرماني آخر ٧ أيام، أحمر بعد الانتهاء.
   الضغط عليه يفتح /subscription. ألوان هوية Horizon. */
(function () {
  if (!window.frappe || frappe.session.user === "Guest") return;

  frappe.call({
    method: "horizon_client.api.subscription_info",
    callback: function (r) {
      var d = r.message || {};
      if (d.days_left === null || d.days_left === undefined) return;

      var expired = d.days_left < 0;
      var closing = !expired && d.days_left <= 7;
      var bg = expired ? "#B04A3F" : closing ? "#B8860B" : "#1D2D44";
      var txt = expired
        ? "انتهى اشتراكك (" + (d.plan || "Horizon") + ") — اضغط للتجديد الآن"
        : closing
          ? "باقتك (" + (d.plan || "Horizon") + ") تنتهي خلال " + d.days_left + " يوم — اضغط للتجديد"
          : "الفترة التجريبية: باقي " + d.days_left + " يوم · إدارة الاشتراك";

      var bar = document.createElement("div");
      bar.id = "h-trial-bar";
      bar.setAttribute("dir", "rtl");
      bar.style.cssText =
        "position:fixed;top:var(--navbar-height,48px);right:0;left:0;z-index:900;" +
        "background:" + bg + ";color:#fff;font-family:Cairo,sans-serif;font-weight:700;" +
        "cursor:pointer;text-align:center;padding:9px 14px;font-size:13.5px;" +
        "box-shadow:0 2px 8px rgba(29,45,68,.18)";
      bar.textContent = txt;
      bar.addEventListener("click", function () { window.location.href = "/subscription"; });
      document.body.appendChild(bar);

      // شبكة كروت الرئيسية (الثيم) fixed من أعلى الشاشة — نزود حشوتها
      // العلوية بارتفاع الشريط عشان أول صف مايتغطاش
      var st = document.createElement("style");
      st.textContent =
        ".h-desktop-launcher{padding-top:calc(var(--navbar-height,48px) + 16px + 38px)!important}" +
        "body:not(.h-has-launcher) .page-head{top:calc(var(--navbar-height,48px) + 38px)!important}";
      document.head.appendChild(st);

      // الشريط في الرئيسية بس (طلب المالك) لو الثيم موجود؛
      // لو الثيم مش متركب يفضل ظاهر في كل الصفحات
      function sync() {
        var launcher = document.querySelector(".h-desktop-launcher");
        if (!launcher) { bar.style.display = "block"; document.body.classList.remove("h-has-launcher"); return; }
        document.body.classList.add("h-has-launcher");
        // offsetParent بيرجع null دايمًا مع position:fixed — القياس الصحيح
        // هو computed display + أبعاد فعلية (بلاغ حقيقي: الشريط كان بيختفي
        // بعد اكتمال تحميل الرئيسية)
        var cs = getComputedStyle(launcher);
        var rect = launcher.getBoundingClientRect();
        var visible = cs.display !== "none" && cs.visibility !== "hidden" && rect.width > 0;
        bar.style.display = visible ? "block" : "none";
      }
      sync();
      setInterval(sync, 800);
    },
  });
})();
