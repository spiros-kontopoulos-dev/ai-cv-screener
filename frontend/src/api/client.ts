import type {
  ApiErrorResponse,
  CandidateListResponse,
  ChatRequest,
  ChatResponse,
  HealthResponse,
} from './types'

const DEFAULT_API_BASE_URL = 'http://localhost:8000'
const DEFAULT_TIMEOUT_MS = 125_000

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

export const API_BASE_URL = normalizeBaseUrl(
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
)

export class ApiClientError extends Error {
  readonly code: string
  readonly status: number | null
  readonly details: ApiErrorResponse['error']['details']

  constructor(
    message: string,
    options: {
      code: string
      status?: number | null
      details?: ApiErrorResponse['error']['details']
    },
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.code = options.code
    this.status = options.status ?? null
    this.details = options.details ?? []
  }
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (!value || typeof value !== 'object' || !('error' in value)) {
    return false
  }

  const error = value.error
  return Boolean(
    error &&
      typeof error === 'object' &&
      'code' in error &&
      typeof error.code === 'string' &&
      'message' in error &&
      typeof error.message === 'string',
  )
}

function createRequestSignal(
  externalSignal?: AbortSignal,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): { signal: AbortSignal; cleanup: () => void; didTimeout: () => boolean } {
  const controller = new AbortController()
  let timedOut = false

  const abortFromExternal = () => controller.abort(externalSignal?.reason)
  externalSignal?.addEventListener('abort', abortFromExternal, { once: true })

  const timeoutId = window.setTimeout(() => {
    timedOut = true
    controller.abort('request-timeout')
  }, timeoutMs)

  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timeoutId)
      externalSignal?.removeEventListener('abort', abortFromExternal)
    },
    didTimeout: () => timedOut,
  }
}

async function parseErrorResponse(response: Response): Promise<ApiClientError> {
  let payload: unknown

  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (isApiErrorResponse(payload)) {
    return new ApiClientError(payload.error.message, {
      code: payload.error.code,
      status: response.status,
      details: payload.error.details,
    })
  }

  return new ApiClientError(
    response.status >= 500
      ? 'The CV assistant is temporarily unavailable. Please try again.'
      : 'The request could not be completed.',
    { code: 'http_error', status: response.status },
  )
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  externalSignal?: AbortSignal,
): Promise<T> {
  const requestSignal = createRequestSignal(externalSignal)

  try {
    const response = await fetch(buildApiUrl(path), {
      ...init,
      headers: {
        Accept: 'application/json',
        ...init.headers,
      },
      signal: requestSignal.signal,
    })

    if (!response.ok) {
      throw await parseErrorResponse(response)
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error
    }

    if (requestSignal.didTimeout()) {
      throw new ApiClientError(
        'The request took too long. Please try the question again.',
        { code: 'request_timeout' },
      )
    }

    if (externalSignal?.aborted) {
      throw new ApiClientError('The request was cancelled.', {
        code: 'request_cancelled',
      })
    }

    throw new ApiClientError(
      'Cannot reach the CV assistant API. Check that Docker is running and try again.',
      { code: 'network_error' },
    )
  } finally {
    requestSignal.cleanup()
  }
}

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

export function getCandidatePhotoUrl(candidateId: string): string {
  return `/candidate-images/${candidateId}.webp`
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/api/health', {}, signal)
}

export function getCandidates(
  signal?: AbortSignal,
): Promise<CandidateListResponse> {
  return requestJson<CandidateListResponse>('/api/candidates', {}, signal)
}

export function askQuestion(
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return requestJson<ChatResponse>(
    '/api/chat',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    },
    signal,
  )
}
