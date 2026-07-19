import { useCallback, useEffect, useRef } from 'react'
import { buildApiUrl } from '../api/client'
import type { ChatSource } from '../api/types'
import { useFocusTrap } from '../hooks/useFocusTrap'
import { formatSection } from '../utils'
import { CloseIcon, DocumentIcon, ExternalLinkIcon } from './Icons'

interface SourcePanelProps {
  source: ChatSource | null
  onClose: () => void
}

export function SourcePanel({ source, onClose }: SourcePanelProps) {
  const panelRef = useRef<HTMLElement>(null)
  const closePanel = useCallback(() => onClose(), [onClose])
  const isOpen = source !== null

  useFocusTrap(panelRef, isOpen, closePanel)

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

  if (!source) {
    return null
  }

  const cvHref = `${buildApiUrl(source.cv_url)}#page=${source.page}`

  return (
    <div className="source-overlay" role="presentation" onMouseDown={onClose}>
      <section
        ref={panelRef}
        className="source-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-panel-title"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="source-panel-header">
          <div>
            <p className="eyebrow">Verified CV evidence</p>
            <h2 id="source-panel-title">{source.candidate_name}</h2>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close source evidence"
          >
            <CloseIcon />
          </button>
        </div>

        <dl className="source-metadata">
          <div>
            <dt>File</dt>
            <dd>{source.filename}</dd>
          </div>
          <div>
            <dt>Page</dt>
            <dd>{source.page_label}</dd>
          </div>
          <div>
            <dt>Section</dt>
            <dd>{formatSection(source.section)}</dd>
          </div>
        </dl>

        <div className="source-supports">
          <p>Supports</p>
          <div className="requirement-list">
            {source.supports.length > 0 ? (
              source.supports.map((requirement) => (
                <span key={requirement}>{requirement}</span>
              ))
            ) : (
              <span className="context-only-chip">Supporting context</span>
            )}
          </div>
        </div>

        <blockquote className="source-evidence">{source.text}</blockquote>

        <details className="source-technical-details">
          <summary>Technical source details</summary>
          <dl>
            <div>
              <dt>Source ID</dt>
              <dd>{source.source_id}</dd>
            </div>
            <div>
              <dt>Chunk ID</dt>
              <dd>{source.chunk_id}</dd>
            </div>
          </dl>
        </details>

        <a
          className="open-cv-button"
          href={cvHref}
          target="_blank"
          rel="noreferrer"
        >
          <DocumentIcon />
          Open CV at page {source.page_label}
          <ExternalLinkIcon />
        </a>
      </section>
    </div>
  )
}
