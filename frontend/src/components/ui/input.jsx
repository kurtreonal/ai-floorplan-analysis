import { cn } from '../../lib/utils.js'

export function Input({ className, type, ...props }) {
  return <input data-slot="input" type={type} className={cn('h-10 w-full min-w-0 rounded-md border border-[var(--paper-line)] bg-[var(--white)] px-3 text-sm text-[var(--ink)] placeholder:text-[var(--ink-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--line-cyan-dim)] disabled:opacity-50', className)} {...props} />
}
