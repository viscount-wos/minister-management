#!/usr/bin/env node
// Translation completeness check for wos-events.
//
// English (src/i18n/locales/en) is the reference. For every other language and
// every namespace this reports, and exits 1 on, any of:
//   - a namespace file that en has but the language lacks (or vice versa)
//   - a key en has that the language is missing
//   - a key the language has that en does not (extra / stale)
//   - an empty (or non-string) value, in any language including en
//   - {{placeholders}} that differ from en's for the same key
// It also scans src/ for static t('ns:key') calls and reports keys that do not
// exist in en, so a typo in a component cannot ship silently.
//
// Usage: node scripts/check-i18n.mjs        (from frontend/)
//        npm run check:i18n
// Plain Node (>=18), no dependencies, so it also runs in the Docker build stage.

import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');
const LOCALES = join(FRONTEND, 'src', 'i18n', 'locales');
const SRC = join(FRONTEND, 'src');
const REF = 'en';
const EXPECTED_LANGS = ['en', 'es', 'fr', 'de', 'pl', 'ko', 'zh', 'tr', 'ar'];
const EXPECTED_NS = ['common', 'profile', 'ministry', 'tyrant', 'svs', 'tal', 'admin', 'guide', 'changelog'];

const problems = [];
const report = (lang, ns, msg) => problems.push({ lang, ns, msg });

function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}

function placeholders(value) {
  if (typeof value !== 'string') return [];
  return [...value.matchAll(/\{\{\s*([^}\s,]+)[^}]*\}\}/g)].map((m) => m[1]).sort();
}

function load(lang, ns) {
  const file = join(LOCALES, lang, `${ns}.json`);
  try {
    return flatten(JSON.parse(readFileSync(file, 'utf8')));
  } catch (err) {
    report(lang, ns, `cannot parse ${relative(FRONTEND, file)}: ${err.message}`);
    return null;
  }
}

const listDirs = (d) => readdirSync(d).filter((n) => statSync(join(d, n)).isDirectory()).sort();
const listNs = (lang) =>
  readdirSync(join(LOCALES, lang)).filter((n) => n.endsWith('.json')).map((n) => n.slice(0, -5)).sort();

if (!existsSync(join(LOCALES, REF))) {
  console.error(`check-i18n: reference locale folder missing: ${join(LOCALES, REF)}`);
  process.exit(1);
}

const langs = listDirs(LOCALES);
for (const l of EXPECTED_LANGS) if (!langs.includes(l)) report(l, '-', 'language folder missing');
for (const l of langs) if (!EXPECTED_LANGS.includes(l)) report(l, '-', 'unexpected language folder');

const refNs = listNs(REF);
for (const ns of EXPECTED_NS) if (!refNs.includes(ns)) report(REF, ns, 'namespace file missing in en');
for (const ns of refNs) if (!EXPECTED_NS.includes(ns)) report(REF, ns, 'unexpected namespace (not in SPEC list)');

const ref = {};
for (const ns of refNs) ref[ns] = load(REF, ns) || {};

let keyCount = 0;
for (const ns of refNs) {
  keyCount += Object.keys(ref[ns]).length;
  for (const [k, v] of Object.entries(ref[ns])) {
    if (typeof v !== 'string' || v.trim() === '') report(REF, ns, `empty or non-string value: ${k}`);
  }
}

for (const lang of langs) {
  if (lang === REF) continue;
  const have = listNs(lang);
  for (const ns of have) if (!refNs.includes(ns)) report(lang, ns, 'extra namespace file (en has none)');
  for (const ns of refNs) {
    if (!have.includes(ns)) {
      report(lang, ns, 'namespace file missing');
      continue;
    }
    const cur = load(lang, ns);
    if (!cur) continue;
    for (const k of Object.keys(ref[ns])) {
      if (!(k in cur)) {
        report(lang, ns, `missing key: ${k}`);
        continue;
      }
      const v = cur[k];
      if (typeof v !== 'string' || v.trim() === '') {
        report(lang, ns, `empty or non-string value: ${k}`);
        continue;
      }
      const a = placeholders(ref[ns][k]).join(',');
      const b = placeholders(v).join(',');
      if (a !== b) report(lang, ns, `placeholder mismatch: ${k} (en: {{${a || '-'}}} vs ${lang}: {{${b || '-'}}})`);
    }
    for (const k of Object.keys(cur)) if (!(k in ref[ns])) report(lang, ns, `extra key: ${k}`);
  }
}

// Static usages: t('ns:key') / labelKey: 'ns:key' must exist in en.
function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|jsx?)$/.test(name)) out.push(p);
  }
  return out;
}
const nsAlt = refNs.join('|');
const usageRe = new RegExp(`['"\`](${nsAlt}):([A-Za-z0-9_.]+)['"\`]`, 'g');
let usageCount = 0;
for (const file of walk(SRC)) {
  const text = readFileSync(file, 'utf8');
  for (const m of text.matchAll(usageRe)) {
    usageCount++;
    const [, ns, key] = m;
    if (!(key in ref[ns])) {
      const line = text.slice(0, m.index).split('\n').length;
      report(REF, ns, `used in ${relative(FRONTEND, file)}:${line} but not defined: ${ns}:${key}`);
    }
  }
}

if (problems.length) {
  console.error(`check-i18n: FAILED with ${problems.length} problem(s)\n`);
  const byLang = {};
  for (const p of problems) (byLang[p.lang] ??= []).push(p);
  for (const [lang, list] of Object.entries(byLang)) {
    console.error(`  [${lang}]`);
    for (const p of list) console.error(`    ${p.ns}: ${p.msg}`);
  }
  console.error(`\nReference: src/i18n/locales/${REF}. Fix the files above (or add the key to en first).`);
  process.exit(1);
}

console.log(
  `check-i18n: OK — ${langs.length} languages x ${refNs.length} namespaces, ${keyCount} keys each, ` +
    `${usageCount} static key usages verified`,
);
