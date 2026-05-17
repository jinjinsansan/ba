'use client'

type Props = {
  action: (formData: FormData) => void | Promise<void>
  confirmText: string
  children: React.ReactNode
  className?: string
}

export default function ConfirmForm({ action, confirmText, children, className }: Props) {
  return (
    <form
      action={action}
      className={className}
      onSubmit={(e) => {
        if (!confirm(confirmText)) e.preventDefault()
      }}
    >
      {children}
    </form>
  )
}
