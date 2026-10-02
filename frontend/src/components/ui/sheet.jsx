// JavaScript adaptation of shadcn/ui Sheet; Radix owns focus and dismissal.
import * as SheetPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils.js'

export function Sheet(props) { return <SheetPrimitive.Root {...props} /> }
export function SheetTrigger(props) { return <SheetPrimitive.Trigger {...props} /> }
export function SheetTitle(props) { return <SheetPrimitive.Title {...props} /> }
export function SheetDescription(props) { return <SheetPrimitive.Description {...props} /> }
export function SheetContent({ className, children, ...props }) {
  return <SheetPrimitive.Portal>
    <SheetPrimitive.Overlay className="studio-sheet-overlay" />
    <SheetPrimitive.Content className={cn('studio-sheet-content', className)} {...props}>
      {children}
      <SheetPrimitive.Close className="studio-sheet-close" aria-label="Close navigation"><X size={20} aria-hidden="true" /></SheetPrimitive.Close>
    </SheetPrimitive.Content>
  </SheetPrimitive.Portal>
}
