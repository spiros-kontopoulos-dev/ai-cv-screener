import { useEffect, useMemo, useRef } from 'react'
import type { ChatCandidate, ChatResponse, ChatSource } from '../api/types'
import type { ChatTurn } from '../chatTypes'
import { formatPercent, formatScore } from '../utils'
import {
  AlertIcon,
  DocumentIcon,
  RefreshIcon,
  SparkleIcon,
} from './Icons'
import { OutcomeBadge, ProviderBadge } from './StatusBadges'

interface ChatThreadProps {
  turns: ChatTurn[]
  isSubmitting: boolean
  suggestions: string[]
  onSuggestion: (question: string) => void
  onSelectSource: (source: ChatSource) => void
  onRetry: (question: string) => void
}

interface CitationChipProps {
  source: ChatSource
  onSelect: (source: ChatSource) => void
}

function CitationChip({ source, onSelect }: CitationChipProps) {
  return (
    <button
      type="button"
      className="citation-chip"
      onClick={() => onSelect(source)}
      aria-label={`View source from ${source.candidate_name}, page ${source.page_label}`}
    >
      <DocumentIcon />
      <span>{source.candidate_name}</span>
      <span aria-hidden="true">·</span>
      <span>p. {source.page_label}</span>
    </button>
  )
}

interface CandidateAssessmentProps {
  candidate: ChatCandidate
  sourcesById: Map<string, ChatSource>
  onSelectSource: (source: ChatSource) => void
}

function CandidateAssessment({
  candidate,
  sourcesById,
  onSelectSource,
}: CandidateAssessmentProps) {
  const candidateSources = candidate.citation_ids
    .map((sourceId) => sourcesById.get(sourceId))
    .filter((source): source is ChatSource => Boolean(source))

  return (
    <article className="answer-candidate-card">
      <div className="answer-candidate-header">
        <div>
          <p className="candidate-rank">Rank {candidate.rank}</p>
          <h3>{candidate.name}</h3>
          <p>{candidate.professional_title}</p>
        </div>
        <span
          className={`support-label support-${candidate.support_level}`}
        >
          {candidate.support_level === 'complete'
            ? 'Complete coverage'
            : 'Partial coverage'}
        </span>
      </div>

      <div className="candidate-metrics">
        <div>
          <span>Relevance</span>
          <strong>{formatScore(candidate.relevance_score)}</strong>
          <div
            className="metric-bar"
            role="progressbar"
            aria-label={`${candidate.name} relevance score`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(candidate.relevance_score * 100)}
          >
            <span style={{ width: formatPercent(candidate.relevance_score) }} />
          </div>
        </div>
        <div>
          <span>Requirement coverage</span>
          <strong>{formatPercent(candidate.coverage_score)}</strong>
          <div
            className="metric-bar coverage-bar"
            role="progressbar"
            aria-label={`${candidate.name} requirement coverage`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(candidate.coverage_score * 100)}
          >
            <span style={{ width: formatPercent(candidate.coverage_score) }} />
          </div>
        </div>
      </div>

      {candidate.matched_requirements.length > 0 ? (
        <div className="requirement-list candidate-requirements">
          {candidate.matched_requirements.map((requirement) => (
            <span key={requirement}>{requirement}</span>
          ))}
        </div>
      ) : null}

      <p className="candidate-assessment">{candidate.assessment}</p>

      {candidateSources.length > 0 ? (
        <div className="citation-list" aria-label={`Sources for ${candidate.name}`}>
          {candidateSources.map((source) => (
            <CitationChip
              key={source.source_id}
              source={source}
              onSelect={onSelectSource}
            />
          ))}
        </div>
      ) : null}
    </article>
  )
}

interface AssistantMessageProps {
  response: ChatResponse
  onSelectSource: (source: ChatSource) => void
}

function AssistantMessage({
  response,
  onSelectSource,
}: AssistantMessageProps) {
  const sourcesById = useMemo(
    () => new Map(response.sources.map((source) => [source.source_id, source])),
    [response.sources],
  )
  const answerSources = response.answer_citation_ids
    .map((sourceId) => sourcesById.get(sourceId))
    .filter((source): source is ChatSource => Boolean(source))

  return (
    <div className="message-row assistant-message">
      <div className="message-avatar" aria-hidden="true">
        <SparkleIcon />
      </div>
      <div className="assistant-content">
        <div className="message-bubble assistant-bubble">
          <div className="answer-diagnostics">
            <OutcomeBadge outcome={response.outcome} />
            <ProviderBadge
              provider={response.provider}
              model={response.model}
              providerCalled={response.provider_called}
            />
          </div>

          <p className="answer-text">{response.answer}</p>

          {answerSources.length > 0 ? (
            <div className="citation-list answer-citations" aria-label="Answer sources">
              {answerSources.map((source) => (
                <CitationChip
                  key={source.source_id}
                  source={source}
                  onSelect={onSelectSource}
                />
              ))}
            </div>
          ) : null}
        </div>

        {response.warnings.length > 0 ? (
          <div className="warning-stack">
            {response.warnings.map((warning) => (
              <div key={warning} className="warning-notice" role="note">
                <AlertIcon />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        ) : null}

        {response.candidates.length > 0 ? (
          <div className="answer-candidate-list">
            {response.candidates.map((candidate) => (
              <CandidateAssessment
                key={candidate.candidate_id}
                candidate={candidate}
                sourcesById={sourcesById}
                onSelectSource={onSelectSource}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function UserMessage({ question }: { question: string }) {
  return (
    <div className="message-row user-message">
      <div className="message-bubble user-bubble">{question}</div>
    </div>
  )
}

function TypingMessage() {
  return (
    <div className="message-row assistant-message" role="status">
      <div className="message-avatar" aria-hidden="true">
        <SparkleIcon />
      </div>
      <div className="message-bubble assistant-bubble typing-bubble">
        <span className="sr-only">Reviewing candidate evidence</span>
        <span aria-hidden="true" />
        <span aria-hidden="true" />
        <span aria-hidden="true" />
      </div>
    </div>
  )
}

interface ErrorMessageProps {
  message: string
  question: string
  onRetry: (question: string) => void
}

function ErrorMessage({ message, question, onRetry }: ErrorMessageProps) {
  return (
    <div className="message-row assistant-message">
      <div className="message-avatar error-avatar" aria-hidden="true">
        <AlertIcon />
      </div>
      <div className="chat-error-card" role="alert">
        <div>
          <h3>Question could not be completed</h3>
          <p>{message}</p>
        </div>
        <button type="button" onClick={() => onRetry(question)}>
          <RefreshIcon />
          Retry
        </button>
      </div>
    </div>
  )
}

function EmptyState({
  suggestions,
  onSuggestion,
}: {
  suggestions: string[]
  onSuggestion: (question: string) => void
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-mark" aria-hidden="true">
        <SparkleIcon />
      </div>
      <h2>Start with a question</h2>
      <p>
        Answers are grounded only in the indexed CVs, with evidence you can
        inspect down to the file and page.
      </p>
      <div className="suggestion-list" aria-label="Suggested questions">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSuggestion(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ChatThread({
  turns,
  isSubmitting,
  suggestions,
  onSuggestion,
  onSelectSource,
  onRetry,
}: ChatThreadProps) {
  const threadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const thread = threadRef.current
    if (!thread) {
      return
    }

    thread.scrollTo({
      top: thread.scrollHeight,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'auto'
        : 'smooth',
    })
  }, [turns, isSubmitting])

  return (
    <div ref={threadRef} className="chat-thread" aria-live="polite">
      {turns.length === 0 ? (
        <EmptyState suggestions={suggestions} onSuggestion={onSuggestion} />
      ) : (
        turns.map((turn) => (
          <div key={turn.id} className="chat-turn">
            <UserMessage question={turn.question} />
            {turn.response ? (
              <AssistantMessage
                response={turn.response}
                onSelectSource={onSelectSource}
              />
            ) : null}
            {turn.error ? (
              <ErrorMessage
                message={turn.error}
                question={turn.question}
                onRetry={onRetry}
              />
            ) : null}
          </div>
        ))
      )}
      {isSubmitting ? <TypingMessage /> : null}
    </div>
  )
}
