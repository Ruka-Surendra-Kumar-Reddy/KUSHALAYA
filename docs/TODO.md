# KushAlaya — open work

One list of what is still open, in order. Done items move to the bottom with a date.
History of the 6 Oct fix programme (items 1–121): [FIX_TODO.md](FIX_TODO.md).

Status: `ready` = agreed, can start · `waiting` = needs something from the owner/team · `idea` = to decide.

## 0. Fix first (from the 11 Oct site review)

| # | Task | Status | Notes |
|---|---|---|---|
| 0.1 | **Remove the six 5-star testimonials on family.kushalaya.com/login** ("Ravi K., Dubai", "Priyanka R., London"…) — not real families; the home page says "Family stories, coming soon" | done 11 Oct (example stories) | Made-up reviews are a legal risk under India's consumer-protection rules on fake reviews. Put real ones back when families agree. |
| 0.2 | **Legal pages**: Privacy Policy, Terms, Refund & cancellation — linked in every footer | live 11 Oct — placeholders + owner decisions open | We collect health data and take wallet payments. I can draft; needs company details + a lawyer's read. |
| 0.3 | **Family portal wording fixes**: "Independence Score™" still shown (should be KushAlaya Safety Score); "Kushalaya" spelling; "Hello" with no name; literal " - " on Updates; findings shown as done ("Toilet grab bar installed · Urgent"); "from ₹3,658" beside "We'll quote"; "?" button covers WhatsApp on phone; every page titled "KushAlaya — Family"; visit report has no photos though the site promises them | done 11 Oct (visit photos still open) | |
| 0.4 | Small tap targets on phone (home "Build your own plan", Safe Homes sources, Vision partner links, Contact buttons) | done 11 Oct | |
| 0.5 | Clean demo data shown to prospects ("test", "hii" messages, 1 am visits) | done 11 Oct (2 messages removed; backup /tmp/demo-msg-backup-20261011-060723.json on VM) | |

## 1. Now — website (one rebuild)

| # | Task | Status | Notes |
|---|---|---|---|
| 1.1 | **India-wide wording** — home headline, plans/KushLife/blog descriptions, blog end box, WhatsApp message, family invite, PIN-code message, privacy notice (+ version bump), Hyderabad post FAQ answer | done 11 Oct | 10 changes listed 11 Oct. Hyderabad blog post stays as a city article. Any Indian PIN accepted. |
| 1.2 | **AI on the website** — Safe Homes "See it before we fit it" before/after slider, 3 steps (photo → AI check reviewed by care manager → preview with prices), home page card, FAQ, privacy line | done 11 Oct | Demo bathroom from the Gemini test; always labelled Illustration; no "finds every hazard" claims. |
| 1.3 | **About us page** — story, how we work, team (Surendra, Krishna, Bharani only), values, company details | live 11 Oct — photos, address, CIN/GSTIN to add | Need: photos + roles of the three, office address, CIN, GSTIN, any real numbers. |

## 2. Next — growth

| # | Task | Status | Notes |
|---|---|---|---|
| 2.1 | **Competitor comparison** — Anvayaa vs KushAlaya on one 10-point rubric + enhancement list | done 11 Oct | Both 64/100. We lead on clarity, mobile, family portal; they lead on trust, service breadth, content. |
| 2.2 | **Website chat "Hi, I'm Surendra"** — step 1 live 11 Oct (auto-opens on laptop, bubble on phone); step 2 AI answers next · — step 1 scripted quick replies + lead capture into Enquiries (~1 day); step 2 AI answers from our own content, prices from the system, emergency words show the number (~2 days) | waiting | Need Surendra's photo; confirm WhatsApp number for hand-off. Persona is Surendra only. |
| 2.3 | **caregiver.kushalaya.com** — caregiver app on its own address (like family.kushalaya.com): host routing in middleware, own install icon/PWA, login straight into the field app | done 11 Oct (install-as-app icon later) | Need DNS record for `caregiver` → VM; TLS cert + nginx on the VM. |
| 2.4 | **More blog posts** — 3–5 SEO posts with images, incl. more city articles (Bengaluru, Chennai, Pune…) | ready | Topics from owner welcome. |
| 2.6 | **SEO pages**: /faq page, one page per service (home safety, KushLife visits, NRI care, emergency), city pages | ready | Anvayaa has 23 city pages; we have 1 blog post. |
| 2.5 | **Full live test** — marketing, ops, family, caregiver on laptop + phone: links, images, flows | ready | Run after 1.x is live. |

## 3. Ideas from the Anvayaa review (decide which)

| # | Idea | Status |
|---|---|---|
| 3.1 | Annual plans in ₹ with a "worth ₹X" line, and a working ₹/USD switch | idea |
| 3.2 | Visit reports with photos after every visit, scheduled video calls (our edge for families abroad) | idea |
| 3.3 | Plans for specific needs: dementia, post-surgery, dialysis escort | idea |
| 3.4 | Parent expense wallet: prepaid, receipt for every spend in the app | idea |
| 3.5 | SOS / fall-detection watch bundled with the home safety audit | idea |
| 3.6 | US/UK phone number; pre-filled WhatsApp on every page | done 11 Oct: US +1 (678) 481-8252 in footer, Contact, About, chat |
| 3.7 | Published emergency response time, measured from our own logs | idea |
| 3.8 | Clear cancellation and refund rules in the FAQ | idea |
| 3.9 | Employer plan ("care for your employees' parents") | idea |

## 4. Waiting on the owner / team

| # | Item | Who |
|---|---|---|
| 4.1 | Prices: fold-up toilet rail, adult bed rail (show "Price on request" now) | Owner / Bharani |
| 4.2 | Per-visit prices for care plans | Owner |
| 4.3 | Legal pages, company address, CIN, GSTIN | Owner |
| 4.4 | Regenerate the Azure OpenAI key (exposed on GitHub); optional: deploy gpt-image-1-mini | Krishna |
| 4.5 | Wearables passwords and timezone | Owner |
| 4.6 | KushLife app screenshots | Owner |
| 4.7 | Cloudflare decision for the domains | Owner |
| 4.8 | Connect email (SMTP) and SMS (MSG91) in Settings | Owner |
| 4.9 | What "PMS" means (asked by the field team) | Owner |
| 4.10 | Replace demo1234 passwords before the marketing launch | Owner |

## Done

- 11 Oct (batch 2) — Chat AI answers (Gemini, prices from plans.ts, emergency first) + auto-open on every page until closed; family visit photos; 4 blog posts published with covers; SEO pages (/faq, 4 services, 8 cities) + footer links; ₹/USD switch on plans; caregiver install icon; menu cut to 5 links; legal: Grievance Officer Krish Posa / contact@kushalaya.com; full live test passed

- 11 Oct — India-wide wording; About us; Privacy/Terms/Refund pages; AI section on Safe Homes + home card + FAQ; Surendra chat (step 1); US number; family portal fixes; caregiver.kushalaya.com live with TLS

- 11 Oct — Blog article layout, new blog editor with Preview, blog list cards
- 11 Oct — AI room preview: before/after room-change check; Gemini renderer live (flash, pro on retry, fal backup); GPT Image ready but off
- 11 Oct — Live AI tests: hazard check 5 hazards in 13 s; Gemini preview 3/3 products, room unchanged
