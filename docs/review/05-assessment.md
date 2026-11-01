# Assessment questions + report
P1 editor (RubricAdminEditor.tsx): reorder ↑/↓, Show/Hide switch (needed for 83→57 without deleting), "Help for caregiver" (item.help exists, assessment.ts:45), read-only "Suggests: Grab bar…" chip; confirm on remove (:257-263); unsaved-changes warning + sticky Save bar.
P1 family safety page: explainer under score ("Out of 100. Higher is safer…"), "What we found" (risks in plain words), "What to fix & cost" with total incl. GST, "After fixes: 62 → 81" (projection exists in AssessmentReportView.tsx:217-222). Ratings shown as Safe/Needs attention/Risk everywhere (AssessmentReportView.tsx:287 prints "unsafe").
P2: "Domain scores" → "Room by room", no decimals for family; "worth X% of score"; move question between sections; "Visit question" tag (Raju's 18); fix wording "100-point", "tenant database", "Kushalaya_Configuration.xlsx…".
P3: Preview as caregiver; CSV import/export; "57 active / 83 total".
