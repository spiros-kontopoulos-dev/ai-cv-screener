export type ProviderMode = 'auto' | 'openai' | 'gemini' | 'deterministic'
export type AnswerProvider = 'openai' | 'gemini' | 'deterministic'
export type AnswerOutcome = 'supported' | 'partial' | 'unsupported'
export type CandidateSupportLevel = 'complete' | 'partial'

export interface HealthProviderStatus {
  requested_mode: ProviderMode
  active_provider: AnswerProvider
  model: string
  ready: boolean
}

export interface HealthIndexStatus {
  available: boolean
  record_count: number
  document_count: number
  candidate_count: number
  complete_document_count: number
  incomplete_document_count: number
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: string
  environment: string
  provider: HealthProviderStatus
  index: HealthIndexStatus
}

export interface CandidateListItem {
  candidate_id: string
  name: string
  professional_title: string
  source_filename: string
  cv_available: boolean
  photo_available: boolean
}

export interface CandidateListResponse {
  count: number
  candidates: CandidateListItem[]
}

export interface ChatRequest {
  question: string
  candidate_limit: number
}

export interface ChatCandidate {
  candidate_id: string
  name: string
  professional_title: string
  rank: number
  support_level: CandidateSupportLevel
  relevance_score: number
  coverage_score: number
  matched_requirements: string[]
  assessment: string
  citation_ids: string[]
}

export interface ChatSource {
  source_id: string
  candidate_id: string
  candidate_name: string
  filename: string
  page: number
  page_label: string
  section: string
  chunk_id: string
  supports: string[]
  text: string
  cv_url: string
}

export interface ChatResponse {
  question: string
  outcome: AnswerOutcome
  answer: string
  provider: AnswerProvider
  model: string
  provider_called: boolean
  provider_attempts: number
  answer_citation_ids: string[]
  candidates: ChatCandidate[]
  sources: ChatSource[]
  warnings: string[]
}

interface ApiErrorDetail {
  field: string
  message: string
}

export interface ApiErrorResponse {
  error: {
    code: string
    message: string
    details: ApiErrorDetail[]
  }
}
