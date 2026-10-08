# Translations

All user-visible text lives here, in 9 languages: en es fr de pl ko zh tr ar
(Arabic is RTL). English is the reference.

```
src/i18n/
  index.ts                  i18next setup, LANGUAGES list, isRtl/applyDirection
  locales/<lang>/<ns>.json  one file per language and namespace
```

Namespaces (docs/SPEC.md): `common` (shell, header, home tiles, placeholders,
themes, footer, generic buttons), `profile` (FID, game name, alliance, furnace
level), `ministry` (ministry home, form, update, schedule, `event.*` tile text),
`tyrant`, `svs`, `tal`, `admin`, `guide` (`player.*`, `admin.*`), `changelog`.

Use keys as `t('<ns>:<key>')`, e.g. `t('ministry:form.next')`,
`t('admin:monday')`. Nested objects use dots after the colon.

## Adding or changing a string
1. Add the key to `locales/en/<ns>.json`.
2. Add the same key, with a real translation, to the other 8 languages.
   Keep `{{placeholders}}` identical to English.
3. Run `npm run check:i18n` (also runs as the first step of `npm run build`).

## The checker
`frontend/scripts/check-i18n.mjs` (also reachable as `node scripts/check-i18n.mjs`
from the repo root) exits 1 and lists every problem if any language, compared with
en, is missing a namespace file or key, has an extra key, has an empty value, or
uses different `{{placeholders}}`. It also flags static `t('ns:key')` usages in
`src/` whose key is not in en. Keys built at runtime (template literals such as
`` t(`admin:${day}`) ``) are not checked statically.

It lives inside `frontend/` because the Docker build stage only copies `frontend/`.

## Language and direction
Start language (`detect.ts`): the player's saved choice (`localStorage.preferred_language`,
written by `chooseLanguage()` when they pick one in the header dropdown) > the first
supported language in `navigator.languages`, matched on the base code (`es-MX` -> es,
`zh-TW` -> zh, `ar-SA` -> ar) > English. Never IP/geolocation. `index.html` runs the same
rules inline before the first paint so `<html dir/lang>` are right immediately (keep the
two in step). Changing language sets `<html dir>` (rtl for Arabic) and `<html lang>` via
the `languageChanged` listener in `index.ts`.
