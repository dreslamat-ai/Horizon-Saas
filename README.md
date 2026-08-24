# Horizon-Saas

منصة Horizon SaaS — تحويل bench فرابي v16 إلى منصة اشتراك ذاتي (Site-per-Tenant):
تسجيل عام بثلاث خطوات (بيانات ← OTP ← تجهيز آلي) على `control.horizonerp.cloud`،
تطبيقان: `saas_manager` (التحكم والتجهيز ودورة الحياة والدفع MyFatoorah)
و`horizon_client` (يُركَّب على موقع كل مستأجر لفرض حدود الباقة).

- الوثيقة المعمارية: `docs/frappe-saas-architecture-horizon.md`
- برومبت التنفيذ الكامل: `docs/horizon-master-prompt-v3-cloudflare.md`
- المصدر: حزمة v3-core + صفحة تسجيل مدموجة (تحققت بصمات MD5 عند النقل)
