import { useEffect, useState } from 'react'

/**
 * A control that will not fire on the first press. Rewriting a day discards
 * its to-dos, so the press has to be meant.
 */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  disabled = false,
  className = '',
  idleClassName = 'btn-secondary',
  ariaLabel,
}: {
  label: string
  confirmLabel: string
  onConfirm: () => void
  disabled?: boolean
  className?: string
  /** The unarmed weight; the armed state is always `btn-danger`. */
  idleClassName?: string
  ariaLabel?: string
}) {
  const [armed, setArmed] = useState(false)

  useEffect(() => {
    if (!armed) return
    const id = window.setTimeout(() => setArmed(false), 4000)
    return () => window.clearTimeout(id)
  }, [armed])

  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={ariaLabel}
      aria-live={armed ? 'polite' : undefined}
      className={`btn ${armed ? 'btn-danger' : idleClassName} ${className}`}
      onClick={() => {
        if (armed) {
          setArmed(false)
          onConfirm()
        } else {
          setArmed(true)
        }
      }}
    >
      {armed ? confirmLabel : label}
    </button>
  )
}
