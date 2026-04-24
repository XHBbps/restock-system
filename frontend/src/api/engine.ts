import client from './client'

interface EngineRunResponse {
  task_id: number
  existing?: boolean
}

export interface EngineRunRequest {
  demand_date: string
}

export function runEngine(payload: EngineRunRequest) {
  return client.post<EngineRunResponse>('/api/engine/run', payload)
}
