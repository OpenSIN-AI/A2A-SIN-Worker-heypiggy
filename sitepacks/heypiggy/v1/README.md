# HeyPiggy Sitepack v1.0.0

Site-specific selector pack for `heypiggy.com` browser automation.

## Selector Inventory

| Name | Selector | Status | Purpose |
|------|----------|--------|---------|
| `login_email` | `input[type='email']` | pending-verification | Email input on login page |
| `login_password` | `input[type='password']` | pending-verification | Password input on login page |
| `login_submit` | `button[type='submit']` | pending-verification | Submit button on login form |
| `consent_next` | `#submit-button-cpx` | **verified** (DevTools 2026-04-11) | Consent modal "Nächste" button |
| `survey_list_item` | `.survey-card` | pending-verification | Individual survey card on dashboard |
| `survey_start` | `button.start-survey` | pending-verification | "Start Survey" button |
| `survey_next` | `button.next-question, button[data-action='next']` | pending-verification | Next question button (multi-selector fallback) |
| `survey_submit` | `button.submit-survey, button[type='submit'].final` | pending-verification | Final survey submit button |
| `completion_indicator` | `.survey-complete, .thank-you, .completion-message` | pending-verification | Completion confirmation elements |

## Verification Protocol

Each selector must be verified using Chrome DevTools before moving to `verified` status:

1. Open heypiggy.com in Chrome DevTools → Elements tab
2. Run: `document.querySelector('<selector>')` in Console → must NOT return `null`
3. Run: `element.offsetParent !== null` → must be `true` (visible)
4. Screenshot the DevTools proof and link it here

## Flows

- **login**: Navigate → fill email → fill password → click submit
- **onboard**: Click consent "Nächste" button
- **survey_execute**: Click start → answer loop → click submit

## Page Signatures

Used by `SitepackLoader.match_page_type()` to deterministically identify the current page
by checking which signature selectors are present in the DOM.
