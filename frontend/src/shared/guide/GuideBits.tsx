import { ReactNode, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, LucideIcon } from 'lucide-react';
import { GuideLoading } from './useGuidesReady';

// Shared building blocks for every player and admin guide (same look as the original Minister guide).
// Guides are plain sections of translated text: keys live in the `guide` namespace (docs/GUIDES.md).

/** One card: round icon, heading, body. `id` makes it a link target (/svs/guide#plan). */
export function GuideSection({
  icon: Icon,
  title,
  id,
  testId,
  tone = 'accent',
  children,
}: {
  icon: LucideIcon;
  title: string;
  id?: string;
  testId?: string;
  tone?: 'accent' | 'success' | 'warning';
  children: ReactNode;
}) {
  const ring = tone === 'success' ? 'bg-success/20 text-success' : tone === 'warning' ? 'bg-warning/20 text-warning' : 'bg-accent/20 text-accent';
  return (
    <section
      id={id}
      data-testid={testId}
      className={`bg-dark-card rounded-xl border p-4 sm:p-6 scroll-mt-4 ${tone === 'warning' ? 'border-warning/50' : 'border-theme-border'}`}
    >
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center ${ring}`}>
          <Icon className="w-5 h-5" aria-hidden="true" />
        </div>
        <h2 className="text-xl sm:text-2xl font-bold text-theme-text min-w-0 break-words">{title}</h2>
      </div>
      <div className="text-theme-dim leading-relaxed space-y-3">{children}</div>
    </section>
  );
}

/**
 * A short label, not a sentence: no sentence punctuation or commas, no open bracket, not a Korean sentence ending
 * (…다), at most 5 words, and at most 10 characters when it contains Chinese characters (no spaces between words).
 */
function isLabel(lead: string): boolean {
  const l = lead.trim();
  if (/[.。?？!！,，،]/.test(l) || /다$/.test(l)) return false;
  if ((l.match(/[(（]/g) || []).length !== (l.match(/[)）]/g) || []).length) return false; // "(e.g: …" is not a label
  if (/[\u3400-\u9fff]/.test(l)) return l.length <= 10;
  return l.split(/\s+/).length <= 5;
}

/**
 * "Label: text" -> the label in bold, so a phone reader can skim the steps. Only a short label (see isLabel) followed
 * by ": " (or the full-width "：") counts, so times like 05:00 and sentences ending in a colon stay plain.
 */
export function LeadText({ text }: { text: string }) {
  const m = text.match(/^([^:：]{1,48}?)(: |：)([\s\S]+)$/);
  if (!m || !isLabel(m[1])) return <>{text}</>;
  return (
    <>
      <strong className="font-semibold text-theme-text">
        {m[1]}
        {m[2].trim()}
      </strong>
      {m[2] === '：' ? '' : ' '}
      {m[3]}
    </>
  );
}

/** A bullet list (or numbered steps with `ordered`) of translated keys. */
export function GuideList({ keys, t, ordered }: { keys: string[]; t: (key: string) => string; ordered?: boolean }) {
  if (ordered) {
    return (
      <ol className="space-y-2">
        {keys.map((key, i) => (
          <li key={key} className="flex gap-3">
            <span
              className="shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent text-sm font-bold flex items-center justify-center"
              aria-hidden="true"
            >
              {i + 1}
            </span>
            <span className="min-w-0 pt-0.5">
              <LeadText text={t(key)} />
            </span>
          </li>
        ))}
      </ol>
    );
  }
  return (
    <ul className="list-disc ps-5 space-y-1.5 marker:text-accent">
      {keys.map((key) => (
        <li key={key}>
          <LeadText text={t(key)} />
        </li>
      ))}
    </ul>
  );
}

/** A highlighted note inside a section. */
export function GuideNote({ children, tone = 'accent' }: { children: ReactNode; tone?: 'accent' | 'warning' }) {
  const cls = tone === 'warning' ? 'bg-warning/10 border-warning/40 text-theme-text' : 'bg-accent/10 border-accent/30 text-accent';
  return <p className={`p-3 border rounded-lg text-sm ${cls}`}>{children}</p>;
}

/** The closing "Tips" box. */
export function GuideTips({ title, keys, t }: { title: string; keys: string[]; t: (key: string) => string }) {
  return (
    <section className="bg-accent/10 border border-accent/30 rounded-xl p-4 sm:p-6">
      <h2 className="text-xl sm:text-2xl font-bold text-accent mb-4">{title}</h2>
      <ul className="space-y-2 text-theme-dim">
        {keys.map((key) => (
          <li key={key} className="flex items-start gap-2">
            <span className="text-accent mt-0.5" aria-hidden="true">
              ✦
            </span>
            <span>{t(key)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Scroll to the URL's #hash once the guide has rendered (lazy page: the browser's own jump fires too early). */
export function useScrollToHash(ready = true) {
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash || !ready) return;
    const id = decodeURIComponent(hash.slice(1));
    const timer = window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: 'start' }), 60);
    return () => window.clearTimeout(timer);
  }, [hash, ready]);
}

/** Page frame of a PLAYER guide: back link to the event page, title, subtitle, then the sections. */
export function PlayerGuideFrame({
  testId,
  backTo,
  backLabel,
  title,
  subtitle,
  ready,
  children,
}: {
  ready: boolean;
  testId: string;
  backTo: string;
  backLabel: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  useScrollToHash(ready);
  return (
    <div className="min-h-screen bg-dark-bg py-4 sm:py-8 px-3 sm:px-4" data-testid={testId}>
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => navigate(backTo)}
          data-testid="guide-back"
          className="flex items-center gap-2 min-h-[44px] text-theme-dim hover:text-accent transition-colors mb-4 sm:mb-6"
        >
          <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
          {backLabel}
        </button>
        {ready ? (
          <>
            <h1 className="text-3xl sm:text-4xl font-bold text-accent mb-2 break-words" data-testid="guide-title">
              {title}
            </h1>
            <p className="text-theme-dim mb-6 sm:mb-8">{subtitle}</p>
            <div className="space-y-6 sm:space-y-8">{children}</div>
          </>
        ) : (
          <GuideLoading />
        )}
      </div>
    </div>
  );
}

/** `k('x')` = t('guide:<prefix>.x'). */
export function useGuideT(prefix: string) {
  const { t } = useTranslation();
  return { t, k: (key: string) => t(`guide:${prefix}.${key}`) };
}
