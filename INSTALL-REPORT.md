# تقرير تركيب Horizon-Saas — ٢٤ أغسطس ٢٠٢٦

تنفيذ برومبت `docs/horizon-master-prompt-v3-cloudflare.md` على بنش الإنتاج
`e.horizonerp.cloud` (فرابي v16، عشرة مواقع حية) **حتى اختبار قبول E2E ناجح
بالكامل**، بدون المساس بأي موقع قائم (مقيس بـping قبل وبعد كل خطوة مؤثرة).

## ما نُفِّذ

| المرحلة | الحالة |
|---|---|
| DNS كلاودفلير | ✅ سجلا `*` و`control` → 147.182.194.52 بـ`proxied:false` (شرط البرومبت — تحديد المعدل بالـIP). سجلات @/www/e/demo القائمة لم تُلمس. التوكن مقيد بـIP السيرفر ومحفوظ في `/root/.secrets/cloudflare.ini` |
| شهادة wildcard | ✅ certbot dns-cloudflare، تغطي `*.horizonerp.cloud` + الجذر، وrenew dry-run ناجح |
| nginx | ✅ `dns_multitenant on` + بلوك wildcard مستقل في `/etc/nginx/conf.d/horizon-ssl.conf` (تمرير `X-Frappe-Site-Name $host`) — لم يُستخدم `bench setup nginx` عمدًا كي لا يمسح تخصيصات قائمة (لوكيشن `/alaa`) |
| موقع التحكم | ✅ `control.horizonerp.cloud` + التطبيقان `saas_manager` و`horizon_client`. كلمات السر في `/root/.secrets/control-admin-pw` و`/root/.frappe-db-root-pw` |
| الإعدادات | ✅ `saas_root_domain` · `saas_bench_dir` · `saas_db_root_password` · `saas_reserved_subdomains` · scheduler مفعّل ومهام saas_manager الأربع مسجلة |
| البريد | ✅ **جسر SMTP→Resend** (انظر أدناه) — OTP والترحيب وإشعارات التعليق تصل فعليًا |
| MyFatoorah | ⏸ معلق — لا مفاتيح بعد. الكود يعمل بمسار التحويل البنكي البديل، و`reconcile_pending` مجدولة وستعمل فور ضبط المفاتيح |

## اختبار القبول E2E — كله مقيس فعليًا

1. `request_signup` بساب دومين `e2etest` → OTP وصل بريدًا حقيقيًا عبر الجسر.
2. `verify_otp` → إنشاء Tenant Site → تجهيز تلقائي على طابور long
   (bench new-site + erpnext + horizon_client) → **Active خلال دقيقتين**
   والموقع يفتح 200 وإيميل الترحيب ببيانات الدخول وصل فعليًا.
3. **حدود الباقة بمُطفِرة في الاتجاهين**: 5 مستخدمين نشطين عدّوا،
   والسادس رُفض بـ«تم الوصول لحد المستخدمين». (ملحوظة قياس: مستخدم بلا
   أدوار desk يحوّله فرابي Website User ولا يُحسب مقعدًا — بالتصميم.)
4. `change_plan` Basic→Pro: انعكس في site_config للمستأجر (`saas_max_users` 5→15).
5. `suspend` → الموقع 503 · `resume` → 200.
6. `drop_site`: حارساه اشتغلا فعلًا (رفض موقعًا نشطًا، ورفض تعليقًا أقل من
   ٦٠ يومًا) ثم الحذف بعد باكب نهائي — الموقع في `archived/sites` والساب
   دومين تحرر (`check_subdomain` → available).

## عطبان في الكيت اكتُشفا بالتنفيذ وأُصلحا (ملتزَمان في هذا الريبو)

1. **بنية موديول ناقصة**: `doctype/` كانت تحت `saas_manager/saas_manager/`
   مباشرة بلا حزمة موديول — `install-app` يفشل
   بـ`ModuleNotFoundError: saas_manager.saas_manager`. أُنشئت الحزمة
   ونُقلت `doctype/` داخلها (ومثلها في horizon_client).
2. **`bench` غير موجود في PATH عمال RQ**: أول تجهيز فشل
   بـ`FileNotFoundError: 'bench'`. أُضيفت `bench_bin()` في provisioner
   (site_config ← `shutil.which` ← `~/.local/bin/bench`).

## جسر البريد — بنية تحتية جديدة على السيرفر

منافذ SMTP الصادرة محجوبة على الدروبلت كله (تذكرة DO معلقة)، فكان **كل
بريد النظام ميتًا**. أُنشئت خدمة `horizon-mail-bridge` (systemd):
تستقبل SMTP على `127.0.0.1:2525` فقط وترسل عبر Resend HTTPS.

- الكود: `/opt/horizon-mail-bridge/bridge.py` · الأسرار:
  `/root/.secrets/horizon-mail-bridge.env` (600).
- عطلان اتقاسا أثناء بنائه: systemd يقصّ قيمة `MAIL_FROM` غير المنصصة عند
  أول مسافة، وكلاودفلير أمام api.resend.com يحظر بصمة Python-urllib
  (خطأ 1010) — أُصلحا بالتنصيص وبـUser-Agent مخصص.
- **مؤقت فيه**: المفتاح مفتاح ألاء والمرسل `no-reply@almoaser.cloud` —
  يُستبدلان فور إنشاء حساب Resend مخصص لهورايزون ودومين موثق.
- أي موقع على البنش يستفيد منه بحساب Email Account:
  `127.0.0.1:2525` بلا مصادقة ولا TLS (مضبوط فعليًا على control).

## المعلق — بانتظار المالك

- ريبو GitHub خاص `dreslamat-ai/Horizon-Saas` (ثم push هذا المستودع).
- مفاتيح MyFatoorah التجريبية + `test-mf-webhook.sh` (على درايف).
- حساب Resend مخصص + توثيق دومين horizonerp (ثم تبديل المرسل وإلغاء
  مفتاح almoaser المؤقت).
- سعة السيرفر: 3.8G RAM — كل مستأجر موقع كامل؛ الترقية لازمة قبل أي
  إطلاق فعلي.
