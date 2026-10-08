import { createContext, useContext } from 'react';
import { AlertCircle } from 'lucide-react';

// Field-level errors inside the shared add/edit player dialog. The dialog owns the error ({field, message}); the
// event's own fields (hours, windows, troops, gems...) read it here and show the message under the right control.
// An API `field` like "profile.troops.infantry.tier" matches the prefixes "profile.troops.infantry.tier",
// "profile.troops.infantry" and "profile.troops".

export interface DialogErrorState {
  field: string | null;
  message: string;
}

export const DialogErrorContext = createContext<DialogErrorState>({ field: null, message: '' });

export function fieldMatches(field: string | null, ...prefixes: string[]): boolean {
  if (!field) return false;
  return prefixes.some((p) => field === p || field.startsWith(`${p}.`) || field.startsWith(`${p}[`) || p.startsWith(`${field}.`));
}

/** The message when the dialog's error belongs to one of these API field paths, else null. */
export function useDialogError(...prefixes: string[]): string | null {
  const { field, message } = useContext(DialogErrorContext);
  return fieldMatches(field, ...prefixes) ? message : null;
}

/** The message under a control (`id` for aria-describedby). The dialog hides its own alert when one is shown. */
export function InlineError({ id, message }: { id: string; message: string | null }) {
  if (!message) return null;
  return (
    <p id={id} data-field-error="true" data-testid="field-error" className="mt-1 text-sm text-danger flex items-start gap-1.5" role="alert">
      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
      <span>{message}</span>
    </p>
  );
}
