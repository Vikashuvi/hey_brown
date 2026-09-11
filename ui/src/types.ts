export type BrownMascotState =
  | 'SLEEPING'
  | 'IDLE'
  | 'WAKE_DETECTED'
  | 'LISTENING'
  | 'THINKING'
  | 'EXECUTING'
  | 'VERIFYING'
  | 'SPEAKING'
  | 'HAPPY'
  | 'CONFUSED'
  | 'CONCERNED'
  | 'ERROR'
  | 'OFFLINE'

export interface StructuredInfo {
  title?: string
  items?: string[]
  details?: Record<string, any>
}

export interface UIEventMessage {
  event: string
  data: Record<string, any>
  timestamp: number
}
