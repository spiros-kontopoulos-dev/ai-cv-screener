import type { ChatResponse } from './api/types'

export interface ChatTurn {
  id: string
  question: string
  response: ChatResponse | null
  error: string | null
}
