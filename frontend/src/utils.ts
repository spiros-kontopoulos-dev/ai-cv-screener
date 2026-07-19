import type { AnswerOutcome, AnswerProvider } from './api/types'

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

const AVATAR_COLORS = ['#3E6259', '#D98E3F', '#C1666B', '#7A6C5D']

export function avatarColor(name: string): string {
  let hash = 0
  for (const character of name) {
    hash = character.charCodeAt(0) + ((hash << 5) - hash)
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

export function formatScore(score: number): string {
  return score.toFixed(2)
}

export function formatPercent(score: number): string {
  return `${Math.round(score * 100)}%`
}

export function formatSection(section: string): string {
  return section
    .split('_')
    .filter(Boolean)
    .map((part) => `${part[0]?.toUpperCase() ?? ''}${part.slice(1)}`)
    .join(' ')
}

export function outcomeLabel(outcome: AnswerOutcome): string {
  const labels: Record<AnswerOutcome, string> = {
    supported: 'Supported',
    partial: 'Partial support',
    unsupported: 'Unsupported',
  }
  return labels[outcome]
}

export function providerLabel(provider: AnswerProvider): string {
  const labels: Record<AnswerProvider, string> = {
    openai: 'OpenAI',
    gemini: 'Gemini',
    deterministic: 'Deterministic',
  }
  return labels[provider]
}
