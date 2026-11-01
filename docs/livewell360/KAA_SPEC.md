# Kushalaya Assessment (KAA) — Product Spec v2.1

**Owner:** Tek Matrix · **Platform:** Kushalaya (repo folder: SafeHomeOps)  
**Status:** Authoritative product constitution for `develop`

## Principle

The Kushalaya Assessment (KAA) is the foundation of the platform. Every recommendation, AI visualization, product, service, quote, membership, and Elder Care Manager (ECM) suggestion originates from KAA results.

## Workflow

Customer Registration → KAA → Scoring → AI Image Analysis → Rule Engine → Recommendation Engine → Product Engine → Service Engine → Membership Recommendation → ECM Assignment → Customer Report

## Twelve domains

| # | Domain ID | Name |
|---|-----------|------|
| 1 | `home_safety` | Home Safety |
| 2 | `mobility` | Mobility & Accessibility |
| 3 | `health_wellness` | Health & Wellness |
| 4 | `adl` | Activities of Daily Living (ADL) |
| 5 | `iadl` | Instrumental Activities of Daily Living (IADL) |
| 6 | `cognitive_emotional` | Cognitive & Emotional Wellness |
| 7 | `emergency` | Emergency Preparedness |
| 8 | `home_condition` | Home Condition & Maintenance |
| 9 | `technology` | Technology Readiness |
| 10 | `family_support` | Family & Caregiver Support |
| 11 | `financial_benefits` | Financial & Government Benefits |
| 12 | `lifestyle` | Lifestyle & Social Engagement |

## Content notes (v2.1)

- ~83 scored items (weights still sum to 100)
- Home Safety aligned with AARP HomeFit staples (smoke/CO, rugs, zero-step entry, scald control)
- Health includes CDC STEADI–style fall-risk items (positive framing for excellent/unsafe ratings)
- Family includes advance directive / decision-maker

## Outputs

- **Kushalaya Independence Score™** (primary; weighted across all 12 domains)
- Domain sub-scores (all 12; customer-facing highlight may emphasize a subset)
- AI before/after images (approved findings only)
- Personalized Living Improvement Plan
- Product + service + membership recommendations
- Dedicated ECM recommendation
- Estimated project cost

## Independence Score™ bands

| Score | Band | Meaning |
|------:|------|---------|
| 90–100 | Excellent | Fully independent |
| 75–89 | Good | Minor improvements recommended |
| 60–74 | Moderate Risk | Several improvements recommended |
| 40–59 | High Risk | Comprehensive intervention recommended |
| &lt;40 | Critical | Immediate safety, healthcare, and care coordination required |

## Memberships

1. Independent Living  
2. Assisted Living at Home  
3. Premium Living360  
4. NRI Family Peace of Mind  

## Related docs

- [RULE_ENGINE.md](./RULE_ENGINE.md) — configuration-driven rules  
- [CONTENT_ROADMAP.md](./CONTENT_ROADMAP.md) — questions / solutions / catalog plan  
- Assessor & family URLs: [../home-safety/README.md](../home-safety/README.md) (paths migrate to `/livewell`)
