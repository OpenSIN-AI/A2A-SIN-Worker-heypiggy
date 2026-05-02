# HeyPiggy Sitepack v1

This sitepack centralizes runtime selectors, flows, and page signatures for `heypiggy.com`.

## Selectors

| Key                        | Selector                                            |
| -------------------------- | --------------------------------------------------- |
| `login_email`              | `input[type='email']`                               |
| `login_password`           | `input[type='password']`                            |
| `login_submit`             | `button[type='submit']`                             |
| `consent_next`             | `#submit-button-cpx`                                |
| `survey_card`              | `div.survey-item`                                   |
| `survey_card_alt`          | `.survey-card`                                      |
| `survey_clickable`         | `[style*='cursor: pointer']`                        |
| `primary_buttons`          | `button, a, [role='button']`                        |
| `survey_submit`            | `button[type='submit']`                             |
| `captcha_presence`         | composite selector for visible captcha surfaces     |
| `captcha_checkbox_targets` | composite selector for clickable captcha checkboxes |

## Verification Notes

- Current selectors are derived from the existing production worker paths and HeyPiggy-specific runtime assumptions already in use.
- This file is intentionally structured so live DevTools evidence and screenshots can be appended without changing the runtime contract.
