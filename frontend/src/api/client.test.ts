import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  askQuestion,
  buildApiUrl,
  getCandidates,
} from './client'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
})

describe('API client', () => {
  it('loads candidates from the configured API origin', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          count: 1,
          candidates: [
            {
              candidate_id: 'candidate_001',
              name: 'Eleni Markou',
              professional_title: 'Senior Python Backend Engineer',
              source_filename: 'eleni-markou-cv.pdf',
              cv_available: true,
              photo_available: false,
            },
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const response = await getCandidates()

    expect(response.count).toBe(1)
    expect(response.candidates[0].candidate_id).toBe('candidate_001')
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/candidates',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('posts the frozen chat request contract', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          question: 'Who knows Python?',
          outcome: 'unsupported',
          answer: 'No supported evidence.',
          provider: 'deterministic',
          model: 'deterministic-template-v1',
          provider_called: false,
          provider_attempts: 0,
          answer_citation_ids: [],
          candidates: [],
          sources: [],
          warnings: [],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await askQuestion({ question: 'Who knows Python?', candidate_limit: 5 })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/chat',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          question: 'Who knows Python?',
          candidate_limit: 5,
        }),
      }),
    )
  })

  it('surfaces the safe API error envelope', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'provider_not_configured',
            message: 'Run setup.ps1 or choose deterministic mode.',
            details: [],
          },
        }),
        { status: 503, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await expect(getCandidates()).rejects.toMatchObject({
      code: 'provider_not_configured',
      status: 503,
      message: 'Run setup.ps1 or choose deterministic mode.',
    })
  })

  it('builds absolute URLs for relative PDF paths', () => {
    expect(buildApiUrl('/api/candidates/candidate_001/cv')).toBe(
      'http://localhost:8000/api/candidates/candidate_001/cv',
    )
  })
})
