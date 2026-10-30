import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import './accounts.css'

export function AccountDialog({ title, description, children, onClose, busy = false }) {
  return <Dialog.Root open onOpenChange={open => { if (!open && !busy) onClose() }}>
    <Dialog.Portal><Dialog.Overlay className="account-dialog-overlay"/>
      <Dialog.Content className="account-dialog" onEscapeKeyDown={event => { if (busy) event.preventDefault() }} onInteractOutside={event => { if (busy) event.preventDefault() }}>
        <Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description>
        <Dialog.Close className="account-dialog-close" aria-label="Close dialog" disabled={busy}><X size={18}/></Dialog.Close>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
