# Minimal conversion-event plan

No analytics code is changed by this implementation. The existing GA4 measurement ID is preserved because analytics changes and credential verification are outside authority.

## Recommended public-site events

| Event | Trigger | Fields | Why |
|---|---|---|---|
| `intro_call_click` | Click from any public page to the contact scheduling section or external Cal.com route | `source_page`, `placement` | Measures high-intent navigation without collecting form content. |
| `contact_submit_attempt` | Native submit of the public contact form | `source_page`, `situation_selected` (boolean only) | Measures intent; never send name, email, message, category value, or validation text. |
| `service_view` | Open a service detail page | `service_slug`, `source_page` | Shows which decision areas attract qualified attention. |
| `decision_view_change` | Change the one-click services situation view | `view_id` (`owner`, `retirement`, `crossborder`) | Validates whether situation-led navigation helps. |
| `client_help_click` | Click the mail link on client access | `reason="access_help"` | Detects routing friction without exposing client identity. |

## Explicit exclusions

Do not instrument portal invitation URLs, authentication steps, report/document access, uploads, client identifiers, account or tax data, free-text form content, calendar notes, or advisor-client requests. Do not use session replay on the client-access route. Keep event retention and access limited to the minimum needed for public-site decisions.

## Validation

Before implementation, verify the existing GA4 property and consent/privacy configuration in the owner account. Use browser debug mode with synthetic test traffic, confirm parameter allowlists, then publish only after inspecting the receiving event payloads.
