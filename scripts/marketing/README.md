# Eldercare customer discovery survey (Google Forms)

| File | Use |
|------|-----|
| [`eldercare-survey-short.gs`](./eldercare-survey-short.gs) | **Preferred for distribution** — ~3–5 min |
| [`eldercare-survey.gs`](./eldercare-survey.gs) | Full discovery instrument — longer |
| [`eldercare-contact-form.gs`](./eldercare-contact-form.gs) | **About Your Parent** lead / contact form (2 sections) |

## Contact form — About Your Parent

Use a **separate** Apps Script project from the survey (different Script Properties).

| Function | When |
|----------|------|
| **`createEldercareContactForm`** | First time — form + Sheet |
| **`updateEldercareContactForm`** | Rebuild same URL + same Sheet |
| **`createEldercareContactFormForceNew`** | New URL |
| **`logEldercareContactFormUrls`** | Print links |

Fields: Google email collection · Parent's name · Age · City · Lives alone · Family outside Hyderabad · Primary contact · Advisor contact Yes/No · Preferred time.

### Setup

1. [script.google.com](https://script.google.com) → **New project**
2. Paste `eldercare-contact-form.gs` into `Code.gs`
3. Run **`createEldercareContactForm`** once → approve Forms + Spreadsheets
4. Copy Edit / Published / Sheet URLs from Executions

## Short version — create once, update in place

Use **one Apps Script project** for the short survey (IDs are stored in that project’s Script Properties).

| Function | When |
|----------|------|
| **`createEldercareSurveyShort`** | First time only — new form + linked Sheet + saves IDs |
| **`updateEldercareSurveyShort`** | After you change the `.gs` file — rebuilds **same form** (same URL) + keeps **same Sheet** |
| **`createEldercareSurveyShortForceNew`** | Rare — new form URL (overwrites saved IDs) |
| **`logEldercareSurveyShortUrls`** | Print current Edit / published / Sheet URLs |

### Setup

1. [script.google.com](https://script.google.com) → **New project** (keep this project forever for this survey)
2. Paste `eldercare-survey-short.gs` into `Code.gs`
3. Run **`createEldercareSurveyShort`** once → approve Forms + Spreadsheets
4. Copy **Edit URL**, **Published URL**, and **Sheet URL** from Executions  
5. Share the **published** link for distribution  

### After you edit questions in the repo

1. Paste the updated `Code.gs` into the **same** Apps Script project  
2. Run **`updateEldercareSurveyShort`** (not create)  
3. Public survey URL stays the same; responses keep going to the same Sheet  

**Note:** Changing questions can add/reorder columns in the Sheet. Old response rows remain.

### Responses in Sheets

Create/update always links:

`form.setDestination(FormApp.DestinationType.SPREADSHEET, sheetId)`

Each submission appends a row to **Eldercare Survey Short — Responses**.

## Full version

Run **`createEldercareSurvey`** from `eldercare-survey.gs` (still creates a new form each run — use short+update for a stable URL).

### What the long form adds (vs short)

Early path extras (trimmed in short):

- Hyderabad locality detail
- Hours of paid caregiving / hire follow-ups
- Visit frequency, broad concern checkboxes, fall narrative text
- “ONE problem” duplicate of top concern
- Trust multi-select + open security text + Parent Care Check intent + “anything else”

Short survey instead asks for: top concern · fall Y/N · paid support (12 months) · **ONE safety product** · **ONE service to buy first** · timing · **ONE package** · payer · assessment price · membership · optional contact. Parent Care Check is offered on the thank-you page (track clicks, not stated intent).

**8.1 vs 8.2:** not redundant — product = what to stock/install (grab bars, SOS, etc.); service = which care line to lead with (assessment, accompaniment, etc.).

Entire sections only in the long form:

| Section | Extra questions |
|---------|-----------------|
| **8 — Health & home** | Full diagnostic (needs, mobility, home type, floor, elevator, stairs, toilet, devices, overnight) — short keeps a single product priority |
| **9 — Service menus** | 9.1–9.7 long category checklists |
| **10 extras** | Additional service to add later; short uses purchase-first + timing only |
| **11 — Packages** | Package structure preference; short keeps one “most appealing package” |
| **12 extras** | Frequency grid, pay preference, purchase influence, income, provider criteria |
| **13–16** | Past-12-months grid, alternatives, referral source, open final thoughts |

Roughly **~40+** additional questions — most of the length difference.

## Branching

| Screener | Alone on page? | Exit path |
|----------|----------------|-----------|
| 1.1 Audience | Yes | Family → family path; Senior → senior path |
| 2.1 Relatives 60+? | Yes | **No** → not eligible |
| 5.1 Age | Yes | **Under 60** → not eligible |

## Known limits

- Checkbox “None of these…” cannot be mutually exclusive in Forms
- Product copy currently says **Eldercare**; Parent Care Check links use `www.kushalaya.com`
