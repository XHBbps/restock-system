import client from './client'

interface EngineRunResponse {
  task_id: number
  existing?: boolean
}

export function runEngine() {
  return client.post<EngineRunResponse>('/api/engine/run')
}
