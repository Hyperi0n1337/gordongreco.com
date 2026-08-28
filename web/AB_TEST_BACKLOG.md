# A/B test backlog

Expected value and cost use relative `High / Medium / Low` bands; they are hypotheses, not observed effects.

| Rank | Test | Primary metric | Expected value | Cost | Guardrail |
|---:|---|---|---|---|---|
| 1 | Home hero CTA: “Schedule an intro call” vs. “Bring one decision” | Qualified scheduler clicks | High | Low | Keep pre-registration disclosure in first viewport. |
| 2 | Business-owner section immediately after hero vs. after services | Business-owner scheduler clicks | High | Low | No audience exclusion language. |
| 3 | Contact entry: scheduler-first vs. balanced scheduler/form split | Completed scheduling route clicks | High | Medium | Track no scheduler notes or personal data. |
| 4 | Services default view: business owner vs. no preselected view | Service detail visits and scheduler clicks | Medium | Low | Full service list always reachable. |
| 5 | Fee placement: home middle vs. directly after process | Qualified call rate; bounce around fee section | Medium | Low | Fee contingency language unchanged. |
| 6 | Process proof: sample decision memo structure vs. methodology principles | Contact conversion | Medium | Medium | Label all samples illustrative. |
| 7 | US/Greece phrase in hero vs. audience chips only | Cross-border service visits | Medium | Low | Avoid implying tax/legal credentials. |
| 8 | FAQ open by default on mobile vs. collapsed | FAQ engagement and contact conversion | Low | Low | Preserve native details semantics. |
| 9 | Service-page CTA after questions vs. only at hero/end | Scheduler clicks | Low | Low | Avoid more than two visible CTAs per viewport. |
| 10 | External scheduler opens same tab vs. new tab | Scheduler completion proxy | Low | Low | Maintain clear external-destination label. |

Run one change at a time until traffic supports a factorial design. Segment only by coarse public page/referrer data; do not use sensitive financial or client attributes.
