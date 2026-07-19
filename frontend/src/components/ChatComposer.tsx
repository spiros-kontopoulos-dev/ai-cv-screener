import { useId } from 'react'
import { SendIcon } from './Icons'

interface ChatComposerProps {
  value: string
  isSubmitting: boolean
  error: string | null
  maxLength: number
  onChange: (value: string) => void
  onSubmit: () => void
}

export function ChatComposer({
  value,
  isSubmitting,
  error,
  maxLength,
  onChange,
  onSubmit,
}: ChatComposerProps) {
  const errorId = useId()
  const normalizedLength = value.trim().length

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSubmit()
    }
  }

  return (
    <div className="composer-shell">
      <div className={`composer-inner${error ? ' has-error' : ''}`}>
        <label className="sr-only" htmlFor="candidate-question">
          Ask a question about the candidates
        </label>
        <textarea
          id="candidate-question"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about the candidates"
          rows={1}
          maxLength={maxLength}
          disabled={isSubmitting}
          aria-describedby={error ? errorId : undefined}
          aria-invalid={Boolean(error)}
        />
        <button
          type="button"
          className="send-button"
          onClick={onSubmit}
          disabled={isSubmitting || normalizedLength === 0}
          aria-label={isSubmitting ? 'Sending question' : 'Send question'}
        >
          {isSubmitting ? (
            <span className="spinner spinner-light" aria-hidden="true" />
          ) : (
            <SendIcon />
          )}
        </button>
      </div>

      <div className="composer-meta">
        <p id={errorId} className="composer-error" role={error ? 'alert' : undefined}>
          {error ?? 'Enter to send · Shift + Enter for a new line'}
        </p>
        <span className={normalizedLength > maxLength * 0.9 ? 'near-limit' : ''}>
          {normalizedLength}/{maxLength}
        </span>
      </div>
    </div>
  )
}
