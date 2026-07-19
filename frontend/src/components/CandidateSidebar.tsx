import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  buildApiUrl,
  getCandidatePhotoUrl,
} from '../api/client'
import type { CandidateListItem, ChatCandidate } from '../api/types'
import { useFocusTrap } from '../hooks/useFocusTrap'
import { avatarColor, formatPercent, formatScore, initials } from '../utils'
import {
  CloseIcon,
  DocumentIcon,
  ExternalLinkIcon,
  RefreshIcon,
  SearchIcon,
} from './Icons'

interface CandidateSidebarProps {
  candidates: CandidateListItem[]
  matchedCandidates: Map<string, ChatCandidate>
  isLoading: boolean
  error: string | null
  isOpen: boolean
  onClose: () => void
  onRetry: () => void
}

interface CandidateAvatarProps {
  candidate: CandidateListItem
}

function CandidateAvatar({ candidate }: CandidateAvatarProps) {
  const [photoFailed, setPhotoFailed] = useState(false)
  const showPhoto = candidate.photo_available && !photoFailed

  if (showPhoto) {
    return (
      <img
        className="candidate-avatar"
        src={getCandidatePhotoUrl(candidate.candidate_id)}
        alt=""
        onError={() => setPhotoFailed(true)}
      />
    )
  }

  return (
    <span
      className="candidate-avatar candidate-initials"
      style={{ background: avatarColor(candidate.name) }}
      aria-hidden="true"
    >
      {initials(candidate.name)}
    </span>
  )
}

interface CandidateCardProps {
  candidate: CandidateListItem
  match?: ChatCandidate
}

function CandidateCard({ candidate, match }: CandidateCardProps) {
  const cvHref = `${buildApiUrl(
    `/api/candidates/${candidate.candidate_id}/cv`,
  )}#page=1`

  return (
    <article
      className={`candidate-card${match ? ' matched' : ''}`}
      aria-label={`${candidate.name}, ${candidate.professional_title}`}
    >
      <div className="candidate-card-top">
        <CandidateAvatar candidate={candidate} />
        <div className="candidate-card-copy">
          <h3>{candidate.name}</h3>
          <p>{candidate.professional_title}</p>
        </div>
      </div>

      {match ? (
        <div className="candidate-score" aria-label="Candidate relevance">
          <div className="score-label-row">
            <span>Relevance {formatScore(match.relevance_score)}</span>
            <span>{formatPercent(match.relevance_score)}</span>
          </div>
          <div
            className="score-bar"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(match.relevance_score * 100)}
          >
            <span style={{ width: formatPercent(match.relevance_score) }} />
          </div>
        </div>
      ) : null}

      {candidate.cv_available ? (
        <a
          className="candidate-cv-link"
          href={cvHref}
          target="_blank"
          rel="noreferrer"
          aria-label={`Open ${candidate.name}'s CV`}
        >
          <DocumentIcon />
          Open CV
          <ExternalLinkIcon />
        </a>
      ) : (
        <span className="candidate-cv-unavailable">CV unavailable</span>
      )}
    </article>
  )
}

export function CandidateSidebar({
  candidates,
  matchedCandidates,
  isLoading,
  error,
  isOpen,
  onClose,
  onRetry,
}: CandidateSidebarProps) {
  const [filter, setFilter] = useState('')
  const sidebarRef = useRef<HTMLElement>(null)
  const closeSidebar = useCallback(() => onClose(), [onClose])

  useFocusTrap(sidebarRef, isOpen, closeSidebar)

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [isOpen])

  const filteredCandidates = useMemo(() => {
    const normalized = filter.trim().toLocaleLowerCase()
    if (!normalized) {
      return candidates
    }

    return candidates.filter((candidate) =>
      [
        candidate.name,
        candidate.professional_title,
        candidate.source_filename,
        candidate.candidate_id,
      ].some((value) => value.toLocaleLowerCase().includes(normalized)),
    )
  }, [candidates, filter])

  return (
    <>
      <button
        type="button"
        className={`sidebar-backdrop${isOpen ? ' visible' : ''}`}
        onClick={onClose}
        aria-label="Close candidate dossier"
        tabIndex={isOpen ? 0 : -1}
      />

      <aside
        ref={sidebarRef}
        className={`candidate-sidebar${isOpen ? ' open' : ''}`}
        aria-label="Candidate dossier"
        tabIndex={-1}
      >
        <div className="sidebar-mobile-header">
          <p>Candidate dossier</p>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close candidate dossier"
          >
            <CloseIcon />
          </button>
        </div>

        <label className="candidate-search">
          <SearchIcon />
          <span className="sr-only">Filter candidates</span>
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter by name or role"
            autoComplete="off"
          />
        </label>

        <div className="dossier-heading-row">
          <p className="dossier-label">Candidate dossier</p>
          {!isLoading && !error ? (
            <span>{filteredCandidates.length}</span>
          ) : null}
        </div>

        {isLoading ? (
          <div className="sidebar-state" role="status">
            <span className="spinner" aria-hidden="true" />
            Loading indexed candidates…
          </div>
        ) : null}

        {error ? (
          <div className="sidebar-state sidebar-error" role="alert">
            <p>{error}</p>
            <button type="button" onClick={onRetry}>
              <RefreshIcon />
              Retry
            </button>
          </div>
        ) : null}

        {!isLoading && !error && filteredCandidates.length === 0 ? (
          <div className="sidebar-state">
            No candidates match “{filter.trim()}”.
          </div>
        ) : null}

        <div className="candidate-list">
          {filteredCandidates.map((candidate) => (
            <CandidateCard
              key={candidate.candidate_id}
              candidate={candidate}
              match={matchedCandidates.get(candidate.candidate_id)}
            />
          ))}
        </div>
      </aside>
    </>
  )
}
