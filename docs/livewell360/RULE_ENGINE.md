# Kushalaya Configuration-Driven Rule Engines — Spec

## Vision

Business rules are **not** hardcoded. They are maintained in Excel
(`Kushalaya_Configuration.xlsx`), imported and versioned into PostgreSQL
(`workflow_config.livewell_rule_engine`), then executed by focused **engines**.
Excel is never read at runtime.

## Principles

1. Business rules shall not be hardcoded  
2. Business rules shall be maintained in Excel  
3. Excel is the master configuration source, not the runtime DB  
4. Application logic reads PostgreSQL (and cache)  
5. Every configuration change is version controlled  
6. Every assessment is reproducible with the **rule version** active at assessment time  
7. Prefer **Finding → Solution → Product → Vendor** (never Finding → Product)

## Engine map (one workbook, multiple readers)

Logical engines share the same versioned config. They are modules, not separate deployables.

```
                 Kushalaya Assessment (KAA)
                            │
                            ▼
                  Finding Engine          ← 21_AssessmentFindings (+ vision map 14)
                            │
                            ▼
                   Risk Engine            ← 25_RiskRules
                            │
                            ▼
              Recommendation Engine       ← 03–04 Solutions / SolutionTriggers
                            │
        ┌──────────┬──────────┬──────────┬──────────┐
        ▼          ▼          ▼          ▼
   Product     Service    Membership     ECM
    Engine      Engine      Engine      Engine
   (05–08)    (catalog)   (19)         (20)
        │
        ▼
    Quote Engine                          ← 26_QuoteRules (+ 09_Pricing)
        │
        ▼
 Notification Engine                      ← 27_NotificationRules
        │
        ▼
 Follow-up Engine                         ← 28_FollowUpRules
        │
        ▼
    AI Prompt Engine                      ← 12–18 (templates / vision / workflow)
        │
        ▼
   Report Generator
```

Generic scaffolding (cross-cutting): **22–24** RuleMaster / Conditions / Actions  
(`DependsOnRuleID` on Rule Master for rule chains).

## Spreadsheet sheets

| Sheet | Engine | In spreadsheet? | Runtime |
|-------|--------|-----------------|---------|
| 01–02 Rubric | Assessment | Yes | Live |
| 03–04 Solutions / Triggers | Recommendation | Yes | Live |
| 05–08 Products / Suppliers | Product / Vendor | Yes | Live |
| 09 Pricing | Quote base | Yes | Live |
| 10–11 Packages | Membership content | Yes | Live |
| 12–18 AI* | AI Prompt | Yes | Live |
| **19 MembershipRules** | Membership | Yes — multi-factor | Evaluated on assessment complete |
| **20 EcmRules** | ECM | Yes — incl. event conditions | Partial (signals + future events) |
| **21 AssessmentFindings** | Finding | Yes — domain catalog | Stored; map Q→finding grows |
| **22–24 RuleMaster*** | Generic | Yes — scaffold | Not full interpreter yet |
| **25 RiskRules** | Risk | Yes | Band stamped on complete |
| **26 QuoteRules** | Quote | Yes — discounts | Config only until quote applies % |
| **27 NotificationRules** | Notification | Yes — ops vs customer | Config only until channels wired |
| **28 FollowUpRules** | Follow-up | Yes — event delays | Config only until job scheduler |

### 19_MembershipRules columns

Score **+** family **+** clinical complexity:

`RuleID`, `MinIndependenceScore`, `MaxIndependenceScore`, `LivesAlone`, `FamilyAbroad`,
`MobilityRisk`, `CognitiveRisk`, `HealthComplexity`, `RecommendedMembershipID`, `Priority`, `Notes`

Risk cells: blank = ignore; `none` / `Yes` / `mild`|`moderate`|`high`|`severe` (minimum match).

Example: Score 88 + Lives Alone + Mild cognitive → **Assisted** (not Independent).

### What stays out of the spreadsheet (for now)

| Concern | Why |
|---------|-----|
| Rule Simulation UI | Admin feature — reads same config |
| Full condition language parser for ECM event streams | Needs visit/emergency tables first |
| Separate AI_RULES tab | Covered by sheets 14–17 |
| Finding → Product short-circuit | Forbidden; keep Solution layer |

## Runtime pipeline

Upload → Validate → Preview → Approve → `livewell_rule_engine` versioned in `workflow_config` → assessments stamp recommendations + `configuration_version_id`.

## Implementation status

| Capability | Status |
|------------|--------|
| Excel import / stage / approve / versions | Shipped |
| Rubric / solutions / products / pricing / AI | Shipped |
| `rule_engine` persist + seed from xlsx | Shipped |
| Multi-factor membership evaluation | Shipped (defaults + tenant rules) |
| Risk band stamp on complete | Shipped |
| Findings / quote / notify / follow-up tables | In spreadsheet; executors incremental |
| Rule simulation UI | Planned |
| DependsOn evaluation | Column shipped; interpreter planned |
