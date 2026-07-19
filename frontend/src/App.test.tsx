import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import {
  ApiClientError,
  askQuestion,
  getCandidates,
  getHealth,
} from './api/client'
import type {
  CandidateListResponse,
  ChatResponse,
  HealthResponse,
} from './api/types'

vi.mock('./api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api/client')>()
  return {
    ...actual,
    getCandidates: vi.fn(),
    getHealth: vi.fn(),
    askQuestion: vi.fn(),
  }
})

const mockedGetCandidates = vi.mocked(getCandidates)
const mockedGetHealth = vi.mocked(getHealth)
const mockedAskQuestion = vi.mocked(askQuestion)

const candidateResponse: CandidateListResponse = {
  count: 2,
  candidates: [
    {
      candidate_id: 'candidate_001',
      name: 'Eleni Markou',
      professional_title: 'Senior Python Backend Engineer',
      source_filename: 'eleni-markou-senior-python-backend-engineer-cv.pdf',
      cv_available: true,
      photo_available: false,
    },
    {
      candidate_id: 'candidate_002',
      name: 'Jonas Keller',
      professional_title: 'Python Backend Engineer',
      source_filename: 'jonas-keller-python-backend-engineer-cv.pdf',
      cv_available: true,
      photo_available: true,
    },
  ],
}

const healthResponse: HealthResponse = {
  status: 'ok',
  service: 'AI CV Screener API',
  environment: 'development',
  provider: {
    requested_mode: 'auto',
    active_provider: 'openai',
    model: 'gpt-5.4-mini',
    ready: true,
  },
  index: {
    available: true,
    record_count: 184,
    document_count: 30,
    candidate_count: 30,
    complete_document_count: 30,
    incomplete_document_count: 0,
  },
}

const supportedResponse: ChatResponse = {
  question: 'Who knows Python and FastAPI?',
  outcome: 'supported',
  answer: 'Eleni Markou has complete source-backed experience.',
  provider: 'openai',
  model: 'gpt-5.4-mini',
  provider_called: true,
  provider_attempts: 1,
  answer_citation_ids: ['candidate_001-source-1'],
  candidates: [
    {
      candidate_id: 'candidate_001',
      name: 'Eleni Markou',
      professional_title: 'Senior Python Backend Engineer',
      rank: 1,
      support_level: 'complete',
      relevance_score: 0.91,
      coverage_score: 1,
      matched_requirements: ['python', 'fastapi'],
      assessment: 'Complete match supported by the professional summary.',
      citation_ids: ['candidate_001-source-1'],
    },
  ],
  sources: [
    {
      source_id: 'candidate_001-source-1',
      candidate_id: 'candidate_001',
      candidate_name: 'Eleni Markou',
      filename: 'eleni-markou-senior-python-backend-engineer-cv.pdf',
      page: 1,
      page_label: '1',
      section: 'professional_summary',
      chunk_id: 'chunk_candidate_001_1',
      supports: ['python', 'fastapi'],
      text: 'Senior Python backend engineer experienced with FastAPI.',
      cv_url: '/api/candidates/candidate_001/cv',
    },
  ],
  warnings: [],
}

beforeEach(() => {
  mockedGetCandidates.mockResolvedValue(candidateResponse)
  mockedGetHealth.mockResolvedValue(healthResponse)
  mockedAskQuestion.mockResolvedValue(supportedResponse)
})

describe('CV Assistant application', () => {
  it('loads real candidates and renders a grounded supported answer', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(await screen.findByText('2 candidates')).toBeInTheDocument()
    expect(screen.getByText('Eleni Markou')).toBeInTheDocument()

    const composer = screen.getByLabelText('Ask a question about the candidates')
    await user.type(composer, 'Who knows Python and FastAPI?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(
      await screen.findByText(
        'Eleni Markou has complete source-backed experience.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Supported')).toBeInTheDocument()
    expect(screen.getByText('OpenAI')).toBeInTheDocument()
    expect(
      screen.getByText('Complete match supported by the professional summary.'),
    ).toBeInTheDocument()

    expect(mockedAskQuestion).toHaveBeenCalledWith(
      {
        question: 'Who knows Python and FastAPI?',
        candidate_limit: 5,
      },
      expect.any(AbortSignal),
    )
  })

  it('opens citation evidence and links to the cited PDF page', async () => {
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('2 candidates')
    await user.type(
      screen.getByLabelText('Ask a question about the candidates'),
      'Who knows Python and FastAPI?',
    )
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    const citationButtons = await screen.findAllByRole('button', {
      name: 'View source from Eleni Markou, page 1',
    })
    await user.click(citationButtons[0])

    const dialog = screen.getByRole('dialog', { name: 'Eleni Markou' })
    expect(dialog).toBeInTheDocument()
    expect(
      screen.getByText('Senior Python backend engineer experienced with FastAPI.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Open CV at page 1' }),
    ).toHaveAttribute(
      'href',
      'http://localhost:8000/api/candidates/candidate_001/cv#page=1',
    )
  })

  it('shows a recoverable candidate catalogue error', async () => {
    mockedGetCandidates.mockRejectedValue(
      new ApiClientError('Cannot reach the CV assistant API.', {
        code: 'network_error',
      }),
    )

    render(<App />)

    expect(
      await screen.findByText('Cannot reach the CV assistant API.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('renders partial support as a distinct evidence state', async () => {
    const user = userEvent.setup()
    mockedAskQuestion.mockResolvedValue({
      ...supportedResponse,
      outcome: 'partial',
      answer: 'Eleni has partial source-backed coverage.',
      candidates: [
        {
          ...supportedResponse.candidates[0],
          support_level: 'partial',
          coverage_score: 0.67,
          assessment: 'Python is supported, but the remaining requirement is incomplete.',
        },
      ],
      warnings: ['Some requested requirements are not fully supported.'],
    })

    render(<App />)
    await screen.findByText('2 candidates')
    await user.type(
      screen.getByLabelText('Ask a question about the candidates'),
      'Find partial evidence',
    )
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(
      await screen.findByText('Eleni has partial source-backed coverage.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Partial support')).toBeInTheDocument()
    expect(screen.getByText('Partial coverage')).toBeInTheDocument()
    expect(
      screen.getByText('Some requested requirements are not fully supported.'),
    ).toBeInTheDocument()
  })

  it('shows a retry action when a chat request fails safely', async () => {
    const user = userEvent.setup()
    mockedAskQuestion.mockRejectedValue(
      new ApiClientError('The provider is temporarily unavailable.', {
        code: 'provider_unavailable',
        status: 503,
      }),
    )

    render(<App />)
    await screen.findByText('2 candidates')
    await user.type(
      screen.getByLabelText('Ask a question about the candidates'),
      'Who knows FastAPI?',
    )
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(
      await screen.findByText('The provider is temporarily unavailable.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Retry' }),
    ).toBeInTheDocument()
  })

  it('renders unsupported deterministic responses without candidate claims', async () => {
    const user = userEvent.setup()
    mockedAskQuestion.mockResolvedValue({
      ...supportedResponse,
      question: 'Who has clearance?',
      outcome: 'unsupported',
      answer: 'No supported clearance evidence was found.',
      provider: 'deterministic',
      model: 'deterministic-template-v1',
      provider_called: false,
      provider_attempts: 0,
      answer_citation_ids: [],
      candidates: [],
      sources: [],
      warnings: ['The indexed CV collection does not support this question.'],
    })

    render(<App />)
    await screen.findByText('2 candidates')
    await user.type(
      screen.getByLabelText('Ask a question about the candidates'),
      'Who has clearance?',
    )
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(
      await screen.findByText('No supported clearance evidence was found.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Unsupported')).toBeInTheDocument()
    expect(screen.getByText('Deterministic')).toBeInTheDocument()
    expect(
      screen.getByText('The indexed CV collection does not support this question.'),
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(
        screen.queryByText('Complete match supported by the professional summary.'),
      ).not.toBeInTheDocument()
    })
  })
})
