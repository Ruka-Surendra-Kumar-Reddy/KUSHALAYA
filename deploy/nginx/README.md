# LiveWell360 / SafeHomeOps — production hostnames & TLS
#
# Marketing: https://livewell.tekmatrix.ai     (public homepage → /marketing)
# Ops:       https://livewellops.tekmatrix.ai  (portal / assessor / API)
# Legacy:    https://safehome.tekmatrix.ai     → 301 to livewellops
# Legacy:    https://family.tekmatrix.ai       → 301 to livewell (when redirect installed)
#
# Automation: `sudo bash scripts/deploy/start-livewell-services.sh`
#   - installs livewellops (APP_DOMAIN) + livewell (MARKETING_DOMAIN) nginx
#   - certbot for both (+ legacy redirect hosts when enabled)
#   - promotes APP_DOMAIN to livewellops even if /etc/workforceos/safehome.env still says livewell/safehome
#     (override with KEEP_APP_DOMAIN=1)
#   - updates NEXT_PUBLIC_API_URL + CORS_ORIGINS
#
# Nginx templates:
#   livewellops.tekmatrix.ai.conf (+ http-only)        — full ops app
#   livewell.tekmatrix.ai.conf (+ http-only)           — marketing host
#   safehome.tekmatrix.ai-redirect.conf (+ http-only)  — 301 → livewellops
#   family.tekmatrix.ai-redirect.conf (+ http-only)    — 301 → livewell
#
# Recommended /etc/workforceos/safehome.env:
#   APP_DOMAIN=livewellops.tekmatrix.ai
#   MARKETING_DOMAIN=livewell.tekmatrix.ai
#   LEGACY_APP_DOMAIN=safehome.tekmatrix.ai
#   INSTALL_LEGACY_REDIRECT=1
#   INSTALL_FAMILY_REDIRECT=0
# Optional only — set INSTALL_FAMILY_REDIRECT=1 if family.tekmatrix.ai still has DNS
#   CERTBOT_EMAIL=you@tekmatrix.ai
# Frontend .env.local (family marketing CTAs):
#   NEXT_PUBLIC_FAMILY_WHATSAPP=9198XXXXXXXX   # digits for wa.me
#   NEXT_PUBLIC_FAMILY_PHONE=+91 40 XXXX XXXX
#   NEXT_PUBLIC_PARENT_CARE_CHECK_URL=/parent-care-check
#   NEXT_PUBLIC_PARENT_CARE_CHECK_EMBED_URL=https://docs.google.com/forms/d/e/.../viewform?embedded=true
#   NEXT_PUBLIC_FAMILY_PORTAL_URL=https://livewellops.tekmatrix.ai/livewell/family/login
# (If WhatsApp is unset, CTAs open /parent-care-check with the embedded Google Form.)
#
# Marketing preview on ops host: https://livewellops.tekmatrix.ai/marketing
#
# Verify:
#   curl -I https://livewell.tekmatrix.ai/              # marketing
#   curl -I https://livewellops.tekmatrix.ai/health/ready
#   curl -I https://safehome.tekmatrix.ai/              # expect 301 → livewellops

## Optional: edge rate limit for sign-in (not applied)

The API already throttles sign-in in the database (5 failures / 15 min per email,
30 / 15 min per IP, 5 reset requests / hour per email). An extra nginx layer can
shed floods before they reach uvicorn:

```nginx
# http {} block (e.g. /etc/nginx/conf.d/limits.conf)
limit_req_zone $binary_remote_addr zone=kushalaya_auth:10m rate=10r/m;

# each server {} that proxies /api/ — place before the generic /api/ location
location ~ ^/api/v1/auth/(login|forgot-password|reset-password)$ {
    limit_req zone=kushalaya_auth burst=10 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8010;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The API trusts `X-Real-IP` only when the peer is 127.0.0.1 (the local nginx).
