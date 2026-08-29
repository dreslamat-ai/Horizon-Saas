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
      // نص مختصر للشاشات الضيقة — الكامل كان بيلزق في الزرار (بلاغ لقطة)
      var narrow = window.innerWidth < 560;
      var txt = expired
        ? (narrow ? "انتهى اشتراكك" : "انتهى اشتراكك (" + (d.plan || "Horizon") + ")")
        : closing
          ? (narrow ? "باقتك تنتهي خلال " + d.days_left + " يوم" : "باقتك (" + (d.plan || "Horizon") + ") تنتهي خلال " + d.days_left + " يوم")
          : (narrow ? "التجربة: باقي " + d.days_left + " يوم" : "الفترة التجريبية: باقي " + d.days_left + " يوم");
      var btnLabel = expired || closing ? "جدّد الآن" : "إدارة الاشتراك";

      // بلاغ حقيقي (٢٩ أغسطس): ٤٨بكسل كانت مقاس رايل الثيم القديم
      // (horizon_command) — لما الثيم اتحوّل لشريط تابات علوي (٤٤بكسل،
      // horizon_tab_theme)، الرقم الثابت فضل زي ما هو وعمل فجوة بيضا
      // فوق كل صفحة. القياس الحقيقي بدل الرقم المفترَض — يشتغل صح مع
      // أي ثيم مستقبلي بلا ما يحتاج تعديل هنا تاني.
      function topBarHeight() {
        var tab = document.querySelector(".h-tab-bar");
        if (tab) return tab.getBoundingClientRect().height;
        var nav = document.querySelector(".navbar");
        if (nav) return nav.getBoundingClientRect().height;
        return 48; // لا ثيم هوريزون ولا نافبار فرابي القياسي — افتراض أخير فقط
      }

      var bar = document.createElement("div");
      bar.id = "h-trial-bar";
      bar.setAttribute("dir", "rtl");
      bar.style.cssText =
        "position:fixed;top:" + topBarHeight() + "px;right:0;left:0;z-index:900;" +
        "background:" + bg + ";color:#fff;font-family:Cairo,sans-serif;font-weight:700;" +
        "cursor:pointer;text-align:right;padding:7px 16px;font-size:13.5px;" +
        "display:flex;align-items:center;justify-content:space-between;gap:12px;" +
        "box-shadow:0 2px 8px rgba(29,45,68,.18)";

      var label = document.createElement("span");
      label.textContent = txt;

      // زرار «إدارة الاشتراك» بستروك أبيض + لمسة 3D (طلب المالك)
      var btn = document.createElement("span");
      btn.textContent = btnLabel;
      btn.style.cssText =
        "display:inline-block;border:1.5px solid rgba(255,255,255,.95);" +
        "border-radius:999px;padding:3px 16px;font-weight:800;font-size:12.5px;" +
        "background:linear-gradient(180deg,rgba(255,255,255,.22),rgba(255,255,255,.06));" +
        "box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 2px 5px rgba(0,0,0,.25);" +
        "white-space:nowrap";

      bar.appendChild(label);
      bar.appendChild(btn);
      bar.addEventListener("click", function () { window.location.href = "/subscription"; });
      document.body.appendChild(bar);

      // ── تاريخ الإصلاحات الثلاثة على نفس المشكلة — ليه اتوحّدت هنا ──────
      // ١) شجرة الحسابات (٢٩ أغسطس): topBarHeight()+bannerHeight على
      //    .page-head كان بيعدّ شريط التابات مرّتين (body أصلاً معاه
      //    padding-top بارتفاعه) → فجوة بيضا. الإصلاح وقتها: bannerHeight
      //    وحده على .page-head{top}.
      // ٢) صفحة "إنشاء" Workspace (٣٠ أغسطس): .page-head مخفي بالكامل
      //    هناك (`body.h-ws-page .page-head{display:none}`)، فإصلاح (١)
      //    مالوش أي أثر — مفيش حاجة كانت بتدفع محتوى الـWorkspace نفسه
      //    لتحت. الإصلاح وقتها: body.h-ws-page تاخد padding-top إضافي.
      // ٣) قائمة DocType (٣٠ أغسطس، بلاغ لقطة حقيقي): إصلاح (١) عمل عطل
      //    تاني مختلف — `.page-head` sticky بيحجز ارتفاعه الطبيعي (بلا
      //    أي إزاحة) في تدفّق الصفحة، لكن بيترسم بصريًا مُزاحًا لتحت
      //    بـbannerHeight (٨٤.٧٥ بدل ٤٤ الطبيعي). العنصر اللي بعده في
      //    التدفّق (.container.page-body وجوّاه .filter-selector) بيتحسب
      //    مكانه من الارتفاع الطبيعي المحجوز (بيبدأ عند ١١٣ = ٤٤+٦٩)، مش
      //    من الموضع البصري الفعلي (اللي بينتهي عند ١٥٣.٧٥) — فرق ٤٠.٧٥
      //    بكسل تراكب حقيقي بين آخر .page-head البصري وأول عنصر بعده.
      //
      // الحل الموحّد: بدل ما نعوّض إزاحة البانر مرّتين في مكانين مختلفين
      // (top على .page-head + padding على body.h-ws-page)، بنخلّي body
      // نفسه (كل الصفحات، مش بس Workspace) ياخد الإزاحة الكاملة
      // (شريط التابات + البانر) دايمًا، ونسيب .page-head{top:0} —
      // بكده موضعه الطبيعي في التدفّق يبقى مطابق تمامًا لموضعه البصري،
      // وأي عنصر بعده في التدفّق يتحسب صح تلقائيًا بلا أي فجوة ولا تراكب.
      var st = document.createElement("style");
      document.head.appendChild(st);
      function updateOffsets() {
        bar.style.top = topBarHeight() + "px";
        var bannerHeight = bar.getBoundingClientRect().height;
        var totalOffset = topBarHeight() + bannerHeight;
        st.textContent =
          ".h-desktop-launcher{padding-top:calc(" + totalOffset + "px + 16px)!important}" +
          "body:not(.h-has-launcher) .page-head{top:0!important}" +
          "html.h-tabs-ready body[class]{padding-top:" + totalOffset + "px!important}";
      }
      updateOffsets();

      // الشريط في الرئيسية بس (طلب المالك) لو الثيم موجود؛
      // لو الثيم مش متركب يفضل ظاهر في كل الصفحات
      function sync() {
        // رايل الثيم عمود ثابت 68px على يمين الشاشة (فيزيائيًا) — الشريط
        // كان بيمتد تحته فأول النص يتقص (بلاغ لقطة حقيقي). JS مش بيتقلب
        // RTL فالقيمة فيزيائية مباشرة.
        bar.style.right = document.querySelector(".h-rail") ? "68px" : "0";
        var launcher = document.querySelector(".h-desktop-launcher");
        if (!launcher) { bar.style.display = "flex"; document.body.classList.remove("h-has-launcher"); return; }
        document.body.classList.add("h-has-launcher");
        // offsetParent بيرجع null دايمًا مع position:fixed — القياس الصحيح
        // هو computed display + أبعاد فعلية (بلاغ حقيقي: الشريط كان بيختفي
        // بعد اكتمال تحميل الرئيسية)
        var cs = getComputedStyle(launcher);
        var rect = launcher.getBoundingClientRect();
        var visible = cs.display !== "none" && cs.visibility !== "hidden" && rect.width > 0;
        // بلاغ لقطة حقيقي (٣٠ أغسطس): "block" هنا كانت بتلغي display:flex
        // اللي اتحط وقت إنشاء الشريط (cssText الأصلي)، فالنص والزرار كانوا
        // بيتكوّموا شمال الشريط بدل ما يتوزعوا على طرفيه (justify-content:
        // space-between ملهوش أي أثر غير مع flex/grid).
        bar.style.display = visible ? "flex" : "none";
      }
      sync();
      updateOffsets();
      setInterval(function () { sync(); updateOffsets(); }, 800);
    },
  });
})();
