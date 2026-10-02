import { useEffect, useState } from 'react'

/**
 * A control that will not fire on the first press.
 * Regenerating a camp discards its to-dos, so the press has to be meant.
 */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  disabled = false,
  quiet = false,
  className = '',
}: {
  label: string
  confirmLabel: string
  onConfirm: () => void
  disabled?: boolean
  /** Drop the ringed ends: for repeated row-level controls, which must not
   *  compete with the card's own edge tabs. */
  quiet?: boolean
  className?: string
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
      aria-live={armed ? 'polite' : undefined}
      className={`${armed ? 'border-fault! text-fault!' : ''} edge-tab ${quiet ? 'edge-tab-quiet' : ''} ${className}`}
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
