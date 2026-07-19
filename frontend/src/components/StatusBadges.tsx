import type { AnswerOutcome, AnswerProvider } from '../api/types'
import { outcomeLabel, providerLabel } from '../utils'

interface OutcomeBadgeProps {
  outcome: AnswerOutcome
}

export function OutcomeBadge({ outcome }: OutcomeBadgeProps) {
  return (
    <span className={`status-badge outcome-badge outcome-${outcome}`}>
      <span className="status-dot" aria-hidden="true" />
      {outcomeLabel(outcome)}
    </span>
  )
}

interface ProviderBadgeProps {
  provider: AnswerProvider
  model: string
  providerCalled: boolean
}

export function ProviderBadge({
  provider,
  model,
  providerCalled,
}: ProviderBadgeProps) {
  const callLabel = providerCalled ? 'hosted model called' : 'no hosted call'

  return (
    <span
      className={`status-badge provider-badge provider-${provider}`}
      title={`${model} · ${callLabel}`}
    >
      {providerLabel(provider)}
      <span aria-hidden="true">·</span>
      <span className="provider-call-label">
        {providerCalled ? 'AI generated' : 'local response'}
      </span>
    </span>
  )
}
