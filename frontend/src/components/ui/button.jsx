// shadcn/ui composition pattern (MIT), adapted to VED's existing tokens.
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils.js'

const buttonVariants = cva(
  'inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--line-cyan-dim)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-[var(--accent)] text-[var(--ink)] hover:bg-[var(--navy)] hover:text-[var(--white)]',
        outline: 'border border-[var(--paper-line)] bg-[var(--white)] text-[var(--ink)] hover:bg-[var(--paper)]',
        secondary: 'bg-[var(--navy)] text-[var(--white)] hover:bg-[var(--ink)]',
        ghost: 'text-[var(--ink-soft)] hover:bg-[var(--paper)] hover:text-[var(--ink)]',
      },
      size: { default: 'h-10 px-4', sm: 'h-9 px-3', icon: 'size-10' },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export function Button({ className, variant, size, asChild = false, type, ...props }) {
  const Component = asChild ? Slot : 'button'
  return <Component data-slot="button" type={asChild ? type : type ?? 'button'} className={cn(buttonVariants({ variant, size, className }))} {...props} />
}
