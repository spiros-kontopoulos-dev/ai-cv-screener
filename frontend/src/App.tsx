import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ApiClientError,
  askQuestion,
  getCandidates,
  getHealth,
} from './api/client'
import type {
  CandidateListItem,
  ChatCandidate,
  ChatSource,
  HealthResponse,
} from './api/types'
import './App.css'
import type { ChatTurn } from './chatTypes'
import { CandidateSidebar } from './components/CandidateSidebar'
import { ChatComposer } from './components/ChatComposer'
import { ChatThread } from './components/ChatThread'
import { Header } from './components/Header'
import { AlertIcon } from './components/Icons'
import { SourcePanel } from './components/SourcePanel'

const MAX_QUESTION_LENGTH = 2000
const DEFAULT_CANDIDATE_LIMIT = 5
const SUGGESTED_QUESTIONS = [
  'Which candidates have experience with Python, FastAPI, and PostgreSQL?',
  'Find a backend engineer who speaks German natively.',
  'Which candidates hold government security clearance?',
]

let nextTurnNumber = 0

function createTurnId(): string {
  nextTurnNumber += 1
  return `turn-${Date.now()}-${nextTurnNumber}`
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message
  }
  return 'Something unexpected happened. Please try again.'
}

function App() {
  const [candidates, setCandidates] = useState<CandidateListItem[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [isCatalogLoading, setIsCatalogLoading] = useState(true)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [question, setQuestion] = useState('')
  const [composerError, setComposerError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [selectedSource, setSelectedSource] = useState<ChatSource | null>(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const activeRequestRef = useRef<AbortController | null>(null)
  const catalogRequestRef = useRef<AbortController | null>(null)

  const loadCatalog = useCallback(async () => {
    catalogRequestRef.current?.abort()
    const controller = new AbortController()
    catalogRequestRef.current = controller
    setIsCatalogLoading(true)
    setCatalogError(null)

    const [candidateResult, healthResult] = await Promise.allSettled([
      getCandidates(controller.signal),
      getHealth(controller.signal),
    ])

    if (controller.signal.aborted) {
      return
    }

    if (candidateResult.status === 'fulfilled') {
      setCandidates(candidateResult.value.candidates)
    } else {
      setCandidates([])
      setCatalogError(errorMessage(candidateResult.reason))
    }

    if (healthResult.status === 'fulfilled') {
      setHealth(healthResult.value)
    } else {
      setHealth(null)
    }

    if (catalogRequestRef.current === controller) {
      catalogRequestRef.current = null
      setIsCatalogLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCatalog()

    return () => {
      catalogRequestRef.current?.abort()
      activeRequestRef.current?.abort()
    }
  }, [loadCatalog])

  const latestResponse = useMemo(() => {
    for (let index = turns.length - 1; index >= 0; index -= 1) {
      if (turns[index].response) {
        return turns[index].response
      }
    }
    return null
  }, [turns])

  const matchedCandidates = useMemo(
    () =>
      new Map<string, ChatCandidate>(
        (latestResponse?.candidates ?? []).map((candidate) => [
          candidate.candidate_id,
          candidate,
        ]),
      ),
    [latestResponse],
  )

  const runQuestion = useCallback(async (normalizedQuestion: string, turnId: string) => {
    const controller = new AbortController()
    activeRequestRef.current = controller
    setIsSubmitting(true)

    try {
      const response = await askQuestion(
        {
          question: normalizedQuestion,
          candidate_limit: DEFAULT_CANDIDATE_LIMIT,
        },
        controller.signal,
      )

      setTurns((currentTurns) =>
        currentTurns.map((turn) =>
          turn.id === turnId
            ? { ...turn, response, error: null }
            : turn,
        ),
      )
    } catch (error) {
      if (controller.signal.aborted) {
        return
      }

      setTurns((currentTurns) =>
        currentTurns.map((turn) =>
          turn.id === turnId
            ? { ...turn, response: null, error: errorMessage(error) }
            : turn,
        ),
      )
    } finally {
      if (activeRequestRef.current === controller) {
        activeRequestRef.current = null
      }
      setIsSubmitting(false)
    }
  }, [])

  const submitQuestion = useCallback(
    (questionOverride?: string) => {
      if (isSubmitting) {
        return
      }

      const normalizedQuestion = (questionOverride ?? question)
        .replace(/\s+/g, ' ')
        .trim()

      if (!normalizedQuestion) {
        setComposerError('Enter a question before sending.')
        return
      }

      if (normalizedQuestion.length > MAX_QUESTION_LENGTH) {
        setComposerError(
          `Questions can contain at most ${MAX_QUESTION_LENGTH} characters.`,
        )
        return
      }

      setComposerError(null)
      setQuestion('')
      setSelectedSource(null)

      const turnId = createTurnId()
      setTurns((currentTurns) => [
        ...currentTurns,
        {
          id: turnId,
          question: normalizedQuestion,
          response: null,
          error: null,
        },
      ])
      void runQuestion(normalizedQuestion, turnId)
    },
    [isSubmitting, question, runQuestion],
  )

  const retryQuestion = useCallback(
    (questionToRetry: string) => {
      if (isSubmitting) {
        return
      }

      const failedTurn = [...turns]
        .reverse()
        .find(
          (turn) => turn.question === questionToRetry && Boolean(turn.error),
        )

      if (!failedTurn) {
        submitQuestion(questionToRetry)
        return
      }

      setTurns((currentTurns) =>
        currentTurns.map((turn) =>
          turn.id === failedTurn.id
            ? { ...turn, response: null, error: null }
            : turn,
        ),
      )
      void runQuestion(questionToRetry, failedTurn.id)
    },
    [isSubmitting, runQuestion, submitQuestion, turns],
  )

  const clearConversation = useCallback(() => {
    activeRequestRef.current?.abort()
    activeRequestRef.current = null
    setIsSubmitting(false)
    setTurns([])
    setQuestion('')
    setComposerError(null)
    setSelectedSource(null)
  }, [])

  const retryCatalog = useCallback(() => {
    void loadCatalog()
  }, [loadCatalog])

  const connectionNotice = useMemo(() => {
    if (!health || health.status === 'ok') {
      return null
    }

    if (!health.index.available) {
      return 'The CV index is not available. Rebuild or mount the persisted Chroma index before asking questions.'
    }

    if (!health.provider.ready) {
      return 'The configured hosted provider is not ready. Run setup.ps1 or select deterministic mode.'
    }

    return 'The API is running in a degraded state.'
  }, [health])

  return (
    <div className="app-shell">
      <Header
        candidateCount={candidates.length}
        isLoading={isCatalogLoading}
        hasConversation={turns.length > 0}
        onOpenSidebar={() => setIsSidebarOpen(true)}
        onClearConversation={clearConversation}
      />

      <div className="app-layout">
        <CandidateSidebar
          candidates={candidates}
          matchedCandidates={matchedCandidates}
          isLoading={isCatalogLoading}
          error={catalogError}
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          onRetry={retryCatalog}
        />

        <main className="chat-main">
          {connectionNotice ? (
            <div className="connection-notice" role="alert">
              <AlertIcon />
              {connectionNotice}
            </div>
          ) : null}

          {!isCatalogLoading && !catalogError && candidates.length === 0 ? (
            <div className="no-index-state" role="status">
              <AlertIcon />
              <h2>No indexed candidates</h2>
              <p>
                Ingest the committed CV PDFs before using the assistant, then
                reload the candidate catalogue.
              </p>
              <button type="button" onClick={retryCatalog}>
                Reload candidates
              </button>
            </div>
          ) : (
            <>
              <ChatThread
                turns={turns}
                isSubmitting={isSubmitting}
                suggestions={SUGGESTED_QUESTIONS}
                onSuggestion={submitQuestion}
                onSelectSource={setSelectedSource}
                onRetry={retryQuestion}
              />
              <ChatComposer
                value={question}
                isSubmitting={isSubmitting}
                error={composerError}
                maxLength={MAX_QUESTION_LENGTH}
                onChange={(value) => {
                  setQuestion(value)
                  if (composerError) {
                    setComposerError(null)
                  }
                }}
                onSubmit={() => submitQuestion()}
              />
            </>
          )}
        </main>
      </div>

      <SourcePanel
        source={selectedSource}
        onClose={() => setSelectedSource(null)}
      />
    </div>
  )
}

export default App
