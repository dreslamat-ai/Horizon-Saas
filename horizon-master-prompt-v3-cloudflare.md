# البرومبت الموحد v3 — Claude Code يبني منصة Horizon SaaS كاملة (Frappe v16 + Cloudflare)
> الصق الكتلة التالية في Claude Code على السيرفر (مستخدم frappe). هو هيعمل كل حاجة: يسحب الحزمة v2 بنفسه من Google Drive، DNS wildcard على Cloudflare، شهادة SSL، nginx، الكيت (بالحدود والخصائص وMyFatoorah)، واختبار قبول حقيقي.
>
> ⚠️ **قبل التشغيل (30 ثانية):** افتح الملفين دول على درايف → Share → غيّر لـ **Anyone with the link — Viewer**، وإلا التحميل من السيرفر هيفشل:
> - `frappe-saas-kit-horizon-v3-core.zip` → https://drive.google.com/file/d/1OYcbLUVxfU61quajKohZwKthw4yh7AB7/view
> - `horizon-signup-page.zip` → https://drive.google.com/file/d/1Zs6JoOITHGOg5iFif4LTsEwxEvQuvJAv/view
> - `test-mf-webhook.sh` → https://drive.google.com/file/d/1ooaC-ZOlAoFjlf7bCLZIpAwsMwPBfEUB/view

---

```
أنت مهندس DevOps خبير في Frappe v16. حوّل هذا السيرفر إلى منصة SaaS كاملة (Horizon) من الصفر حتى اختبار قبول ناجح، بدون مقاطعتي إلا لرسالة المدخلات الأولى أو عند خطر حقيقي (فقدان بيانات / كسر موقع production شغال).

## مدخلات مني (اطلبها كلها دفعة واحدة في أول رسالة ثم لا تسألني شيئًا)
1. CF_API_TOKEN: توكن Cloudflare **مقيّد** — أنشئه من My Profile → API Tokens → Create Token → Custom:
   الصلاحيات: Zone → DNS → Edit، والنطاق: Include → Specific zone → horizonerp.cloud فقط.
   (لا تستخدم Global API Key أبدًا — هو مكافئ لكلمة مرور الحساب كله.)
   CF_ZONE_ID: من صفحة Overview للدومين في Cloudflare (العمود الأيمن)
2. بيانات SMTP (host, port, user, pass) — إن لم تتوفر استخدم backend مؤقت وسجّلها كخطوة معلّقة
3. MF_API_KEY + MF_BASE_URL لـ MyFatoorah (ابدأ بـ https://apitest.myfatoorah.com والتوكن التجريبي من بورتال MyFatoorah) — إن لم تتوفر جهّز كل شيء واترك مفاتيح config فارغة وسجّلها كخطوة معلّقة؛ الكود يعمل بدونها (fallback تحويل بنكي)

## ثوابت
- الدومين: horizonerp.cloud — IP: 147.182.194.52 — موقع التحكم: control.horizonerp.cloud
- قواعد إلزامية: قبل أي أمر bench شغّل --help وتحقق من flags الفعلية على v16. لا shell=True. لا secrets في اللوج أو git. لا تلمس أي موقع موجود. نفّذ للنهاية.

## المراحل بالترتيب

A0) سحب الحزمة من Google Drive (لا تطلب مني مسارًا — الملفات جاهزة على درايف):
   - أنشئ مجلد عمل ~/horizon-saas-install وحمّل فيه:
     curl -L "https://drive.google.com/uc?export=download&id=1OYcbLUVxfU61quajKohZwKthw4yh7AB7" -o kit.zip
     curl -L "https://drive.google.com/uc?export=download&id=1Zs6JoOITHGOg5iFif4LTsEwxEvQuvJAv" -o signup.zip
     curl -L "https://drive.google.com/uc?export=download&id=1ooaC-ZOlAoFjlf7bCLZIpAwsMwPBfEUB" -o test-mf-webhook.sh && chmod +x test-mf-webhook.sh
   - تحقق إلزامي من السلامة: `file kit.zip` يجب أن يقول Zip archive و `unzip -t kit.zip` ينجح.
     لو الناتج HTML (صفحة تسجيل دخول جوجل) توقف وأخبرني: "فعّل Anyone with link للملف على درايف" ثم أعد.
   - fallback للملفات الكبيرة (confirm token): لو curl رجّع صفحة تأكيد استخدم
     curl -Lb /tmp/gc "https://drive.google.com/uc?export=download&confirm=$(curl -sc /tmp/gc 'https://drive.google.com/uc?export=download&id=1wnmzj1pisy01_4_AiIjeUe4uZBEbfLw4' | grep -o 'confirm=[^&"]*' | head -1 | cut -d= -f2)&id=1wnmzj1pisy01_4_AiIjeUe4uZBEbfLw4" -o kit.zip
     أو ثبّت gdown (pip install gdown --break-system-packages) واستخدم: gdown 1wnmzj1pisy01_4_AiIjeUe4uZBEbfLw4 -O kit.zip
   - فك الضغط ودمج صفحة التسجيل (خطوة إلزامية — الصفحة مفصولة عن الحزمة):
     unzip -q kit.zip && unzip -q signup.zip
     mv signup-index.html frappe-saas-kit/saas_manager/saas_manager/www/signup/index.html
     تحقق: الملف موجود وحجمه ~44KB وأول سطر فيه <!DOCTYPE html>، وأن مجلد signup فيه index.py و index.html معًا.
   - الناتج: مجلد frappe-saas-kit فيه التطبيقين saas_manager و horizon_client.

A) DNS عبر Cloudflare API:
   - تحقق أولًا أن الـ nameservers محوّلة لـ Cloudflare فعليًا:
     dig NS horizonerp.cloud +short   → يجب أن تظهر nameservers بتاعة Cloudflare.
     لو لسه ما اتحوّلتش، توقف وأخبرني: "غيّر الـ nameservers عند NameSilo لقيم Cloudflare ثم أعد التشغيل".
   - تحقق من صلاحية التوكن: GET https://api.cloudflare.com/client/v4/user/tokens/verify
     بترويسة Authorization: Bearer $CF_API_TOKEN → يجب "status":"active".
   - جرد السجلات الحالية: GET /client/v4/zones/$CF_ZONE_ID/dns_records?per_page=100
   - أنشئ (أو حدّث) سجلات A، **كلها proxied:false — DNS only، السحابة رمادية**:
       *          → 147.182.194.52
       @          → 147.182.194.52
       control    → 147.182.194.52
     POST /client/v4/zones/$CF_ZONE_ID/dns_records
     بجسم: {"type":"A","name":"<الاسم>","content":"147.182.194.52","ttl":300,"proxied":false}
     لو السجل موجود مسبقًا استخدم PUT على معرّفه بدل POST.
   - ⚠️ لا تفعّل الـ proxy (proxied:true) على أي سجل. السبب: Frappe يعتمد على
     frappe.local.request_ip في الـ rate limiting داخل api/signup.py، وخلف البروكسي
     ستصل كل الطلبات من عناوين Cloudflare فيصبح التحديد بلا معنى — إضافةً إلى
     مشاكل WebSockets (socketio) وحد رفع الملفات. البروكسي قرار لاحق منفصل.
   - احذف أي سجلات A فردية قديمة لعملاء (تتعارض مع الـ wildcard).
   - تأكد أن وضع SSL/TLS في Cloudflare = Full (strict) — نحن نقدّم شهادة حقيقية من الأصل.
   - انتظر بحلقة polling على dig حتى يرجع اسم عشوائي بالـ IP (Cloudflare عادة ثوانٍ).

B) SSL عبر certbot + plugin كلاودفلير (أبسط وأسرع من acme.sh):
   - ثبّت: apt-get install -y certbot python3-certbot-dns-cloudflare
   - أنشئ /root/.secrets/cloudflare.ini بمحتوى: dns_cloudflare_api_token = $CF_API_TOKEN
     ثم chmod 600 عليه (إلزامي — certbot يرفض الملف لو صلاحياته أوسع).
   - أصدر الشهادة:
     certbot certonly --dns-cloudflare \
       --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
       --dns-cloudflare-propagation-seconds 30 \
       -d horizonerp.cloud -d '*.horizonerp.cloud' \
       --agree-tos -m <بريد الإدارة> --non-interactive
   - المسار الناتج: /etc/letsencrypt/live/horizonerp.cloud/{fullchain.pem,privkey.pem}
   - التجديد تلقائي عبر مؤقّت certbot؛ أضف hook لإعادة تحميل nginx:
     --deploy-hook "systemctl reload nginx"، وتحقق بـ certbot renew --dry-run.

C) nginx + bench: dns_multitenant on، bench setup nginx، بلوك SSL في ملف مستقل
   /etc/nginx/conf.d/horizon-ssl.conf يشمل الجذر والـ wildcard ويشير لمسار letsencrypt أعلاه، nginx -t ثم reload.

D) الكيت v2 (الحزمة فيها تطبيقين):
   0. جرد v16: bench version، وتحقق --help لكل من new-site / add-system-manager / drop-site.
      إن اختلفت flags عدّل DB_ROOT_FLAG في saas_manager/provisioning/provisioner.py.
      تحقق من long workers في supervisor/Procfile وأضفها إن غابت.
   1. أمان DB: أنشئ يوزر MariaDB مخصص saas_provisioner، جرّب فعليًا new-site بخيار v16
      (--db-user/--db-password) وإلا root flags — سجّل الناجح وعدّل provisioner وفقًا له.
   2. bench get-app لكل من saas_manager و horizon_client من ~/horizon-saas-install/frappe-saas-kit/.
      أنشئ control.horizonerp.cloud وركّب saas_manager عليه (horizon_client لا يُركب على موقع التحكم —
      هو للمواقع المستأجرة ويُركّب آليًا أثناء الـ provisioning).
      أصلح أي أخطاء توافق v16 في الكود مع تسجيل كل تعديل وسببه.
   3. set-config لموقع التحكم: saas_root_domain، saas_bench_dir، اعتماديات DB من الخطوة 1،
      وsaas_mf_api_key/saas_mf_base_url إن توفرت. فعّل scheduler وتأكد ظهور جدولة saas_manager
      (daily ×3 + cron 02:30).
   4. البريد: Email Account من بيانات SMTP، أو backend مؤقت مع تسجيلها معلّقة.
   5. تكامل MyFatoorah: تحقق من مسارات v2/SendPayment و v2/GetPaymentStatus مقابل الـ base_url
      التجريبي قبل الاعتماد (قاعدة التحقق قبل الاستخدام تنطبق على الـ APIs الخارجية أيضًا).
      اضبط webhook URL في بورتال MyFatoorah إن أمكن آليًا وإلا سجّله كخطوة يدوية عليّ:
      https://control.horizonerp.cloud/api/method/saas_manager.payments.myfatoorah.webhook

E) اختبار قبول E2E حقيقي (إلزامي كله):
   1. /signup يرجع 200 ويعرض الباقات الثلاث.
   2. عبر curl: request_signup بـ subdomain=e2etest → OTP من الـ mail backend → verify_otp.
   3. راقب طابور long حتى الاكتمال ثم تحقق: https://e2etest.horizonerp.cloud يفتح 200،
      ERPNext + horizon_client مركّبان، مستخدم العميل System Manager موجود، Active وtrial بعد 14 يوم.
   4. اختبار الحدود (horizon_client): على موقع e2etest حاول إنشاء مستخدمين System فوق حد الباقة
      عبر bench execute — يجب أن يفشل برسالة الحد. ثم نفّذ change_plan لباقة أعلى من موقع التحكم
      وتأكد أن الحد الجديد سرى (set-config انعكس) وأن المحاولة تنجح الآن.
   5. اختبار MyFatoorah (إن توفرت مفاتيح التجربة): شغّل السكريبت الجاهز الذي حمّلته في A0:
      ~/horizon-saas-install/test-mf-webhook.sh e2etest
      وهو يغطي: إنشاء الفاتورة، رفض webhook كاذب قبل الدفع، التفعيل بعد الدفع بالبطاقة
      التجريبية، idempotency، وreconcile_pending. الخطوة التفاعلية الوحيدة (الدفع بالبطاقة)
      سجّلها كخطوة يدوية عليّ إن لم تستطع تنفيذها.
   6. suspend ثم resume فعليًا، ثم نظّف: drop لموقع e2etest بعد باك أب.

F) التسليم: INSTALL-REPORT.md في مجلد الـ bench: إصدارات v16، flags المؤكدة، كل تعديل وسببه،
   نتائج E خطوة بخطوة، مسار ملف الأسرار (root-only)، والخطوات المعلّقة عليّ (SMTP حقيقي /
   مفاتيح MF الحية / webhook في بورتال MF). لا تُنهِ قبل نجاح E-1..4 و6 كاملة (و5 إن توفرت المفاتيح)
   أو توثيق مانع حقيقي خارج سيطرتك.
```

---

## ملاحظات قبل الإرسال
- شغّل Claude Code كمستخدم frappe مع sudo لأوامر nginx/certbot فقط.
- مرحلة B مع Cloudflare بتخلص في أقل من دقيقة (انتشار DNS ثوانٍ) بدل ~30 دقيقة مع NameSilo.
- الدومين يفضل **مسجّلًا عند NameSilo**؛ التحويل هو لإدارة الـ DNS فقط وليس نقل ملكية.
- التوكن المقيّد: لو تسرّب، أقصى ضرر هو تعديل DNS لهذا الدومين وحده — وهذا الفارق الأمني الأساسي عن مفتاح NameSilo.
- مفاتيح MyFatoorah التجريبية والبطاقات التجريبية من بورتال demo.myfatoorah.com — وعند الانتقال للإنتاج السعودي غيّر base_url لـ https://api-sa.myfatoorah.com بمفتاح الحساب الحي.
