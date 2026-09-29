# Valora3D launch-readiness scorecard

Audited 2026-09-28 on `site/valora3d-preview` @ 7cb4ccd by three read-only reviewers. Full reports
(evidence with file:line) are kept outside the repo, in the session scratchpad (`audit-A-growth.md`,
`audit-B-product.md`, `audit-C-ops.md`).
Legend: ✅ done · 🟡 partial · 🔴 missing · ⛔ owner-only. "Lane" = where the fix is being built.

| Area | Status (audit) | Main gap found | Fix | Lane |
|---|---|---|---|---|
| SEO | 🟡 | no title template, no keyword H1, robots blocks /r/ | titles, H1, JSON-LD, sitemap dates, robots | convert |
| Programmatic SEO | 🔴 | 8 help articles only | /examples, /tools/glb-checker, verified export guides | growth-pages (next) |
| Schema / structured data | 🟡 | FAQ only | Organization, WebSite, SoftwareApplication, VideoObject | convert / growth-pages |
| Open Graph / social cards | 🟡 | /r/ blocked for unfurlers, one generic image | robots fix, per-page OG | convert |
| Clean / shareable URLs | ✅ | UTM lost through `next=` | attribution cookie | analytics |
| CRO | 🔴 | "Start a project" → login, not signup; plan choice lost | signup routing, plan carry-through to checkout | convert |
| UX / UI | 🟡 | nav hidden on the first screen, truncated status line | nav + fixes | convert |
| Information architecture | 🟡 | no Log in on /, Settings tab for a non-existent agent | header/nav cleanup | convert |
| Progressive disclosure | ✅ | tiny "…" on phone | 44px labelled button | convert |
| Cognitive load | 🟡 | legal notice above plans, contradictory empty state | reorder/copy | convert |
| Visual hierarchy | 🟡 | hero kerning gap, misaligned pricing header | fixes | convert |
| Onboarding | 🟡 | no example prompts, no welcome email | prompt chips, welcome email | convert / lifecycle |
| Activation | 🟡 | real path unmeasured (needs accounts) | activation KPI + funnel | analytics |
| Retention | 🔴 | only "render ready" mail; no expiry warning | lifecycle emails | lifecycle (next) |
| Churn | 🔴 | cancel only in Paddle portal, no reason, no dunning UI | cancel flow, past-due banner/emails | lifecycle (next) |
| Product analytics | 🔴 | pageviews only | first-party events | analytics |
| Funnel analysis | 🟡 | SQL-only | admin funnel | analytics |
| Cohort analysis | 🟡 | SQL-only | admin cohorts | analytics |
| North-star / KPIs | 🔴 | none | Weekly Delivered Renders + KPIs in admin | analytics |
| A/B testing | 🔴 | none (no traffic yet) | bucketing helper + exposure events | analytics |
| Feature flags | 🔴 | no kill switches | flags + kill switches + global caps | analytics |
| Growth loops | 🟡 | share CTA untracked, watermark lacks URL | ?ref tracking; watermark "valora3d.com" (worker) | analytics / worker |
| Affiliate / referrals | 🔴 | none | credit referrals paid on the referee's first purchase | growth-pages (next) |
| Acquisition | 🔴 | no UTM/source capture | first-touch attribution → profile + checkout | analytics |
| Brand trust | 🔴 | legal placeholders, fake "Most popular", wrong world copy | trust copy pass (placeholders ⛔) | convert |
| i18n | 🟡 | USD hardcoded vs Paddle local prices; mixed locales | US English sweep now; local prices ⛔ | convert |
| Performance / CWV | 🟡 | mobile LCP 6.7 s (hero fade), 170 KB unneeded JS | visible hero, lazy services | convert |
| Lazy loading / splitting | 🟡 | zod + supabase-js on marketing pages | lazy services | convert |
| Caching / CDN | 🟡 | public/ media max-age=0 | `_headers` long cache | convert |
| Responsive | ✅ | — | — | — |
| Accessibility / WCAG | 🟡 | canvas unlabeled, phone focus ring | fixes | convert |
| Security | 🟡 | residuals: scene pricing (L10), loose CSP, AI key in GPU box; leaked Supabase key ⛔ | nonce CSP; engine `--script` (renderer track) | ops (next) |
| Privacy | 🟡 | Anthropic/Google missing from providers, no data export | provider list, data export | convert / lifecycle |
| Legal / compliance / IP | 🟡 | placeholders, DMCA agent, Porsche crest in hero, no disclaimer | disclaimer + AI disclosure (built); rest ⛔ | convert |
| Payments / billing | 🟡 | $5 pack below Paddle minimum, no failed-payment UI | dunning (lifecycle); prices ⛔ | lifecycle |
| Unit economics | 🔴 | every render estimated to lose money | reprice ⛔ + cost cuts (renderer track) + cost tracking | analytics + ⛔ |
| Observability | 🟡 | 3–7 day logs, no alerts | daily digest + alerts | analytics |
| Error monitoring | 🔴 | client errors carry no context | contextual reports + admin Errors tab | analytics |
| Email deliverability | 🟡 | **no MX (support@ bounces)**, DMARC p=none, no List-Unsubscribe | headers/reply-to/bounces (lifecycle); DNS ⛔ | lifecycle + ⛔ |
| Queues / workers | 🟡 | final-tier limit 120 min < estimated 2.9 h | measure; finals off via flag until then | analytics (flag) + ⛔ measure |
| Autoscaling | ⛔/🔴 | no global spend/concurrency cap | global caps + GPU budget guard | analytics |
| Backups / DR | 🔴 | Supabase Free has no backups; **no git remote** | nightly dump Action + runbook; remote ⛔ | ops (next) |
| Support / feedback | 🟡 | no in-app bug/feature report | in-app feedback | lifecycle (next) |
| Caching of costs / KPIs | — | per-job cost not stored | cost_usd_estimate per job | analytics |
