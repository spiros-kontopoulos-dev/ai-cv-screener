import { CheckCircleIcon, MenuIcon, TrashIcon } from './Icons'

interface HeaderProps {
  candidateCount: number
  isLoading: boolean
  hasConversation: boolean
  onOpenSidebar: () => void
  onClearConversation: () => void
}

export function Header({
  candidateCount,
  isLoading,
  hasConversation,
  onOpenSidebar,
  onClearConversation,
}: HeaderProps) {
  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          className="icon-button mobile-menu-button"
          onClick={onOpenSidebar}
          aria-label="Open candidate dossier"
        >
          <MenuIcon />
        </button>

        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <CheckCircleIcon />
          </div>
          <div>
            <h1>CV Assistant</h1>
            <p>Ask anything about the candidate pool</p>
          </div>
        </div>
      </div>

      <div className="header-actions">
        {hasConversation ? (
          <button
            type="button"
            className="clear-button"
            onClick={onClearConversation}
          >
            <TrashIcon />
            <span>Clear</span>
          </button>
        ) : null}
        <span className="count-pill" aria-live="polite">
          {isLoading ? 'Loading candidates' : `${candidateCount} candidates`}
        </span>
      </div>
    </header>
  )
}
