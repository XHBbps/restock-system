// 任务进度轮询 store
import { getTask, type TaskRun } from '@/api/task'
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'

const POLL_INTERVAL_MS = 2000
const TERMINAL_STATES = new Set(['success', 'failed', 'skipped', 'cancelled'])

export const useTaskStore = defineStore('task', () => {
  const tasksById = reactive<Record<number, TaskRun>>({})
  const polling = ref<Set<number>>(new Set())

  function isTerminal(task: TaskRun): boolean {
    return TERMINAL_STATES.has(task.status)
  }

  async function startPolling(taskId: number, onTerminal?: (t: TaskRun) => void): Promise<void> {
    if (polling.value.has(taskId)) return
    polling.value.add(taskId)

    const tick = async () => {
      // 调用者通过 stopPolling 移除后，任何挂起的 tick 都应立即退出
      if (!polling.value.has(taskId)) return
      try {
        const t = await getTask(taskId)
        // 再次检查：网络请求期间可能被取消
        if (!polling.value.has(taskId)) return
        tasksById[taskId] = t
        if (isTerminal(t)) {
          polling.value.delete(taskId)
          onTerminal?.(t)
          return
        }
      } catch {
        // 失败也停止轮询，避免无限循环
        polling.value.delete(taskId)
        return
      }
      setTimeout(tick, POLL_INTERVAL_MS)
    }
    tick()
  }

  function stopPolling(taskId: number): void {
    polling.value.delete(taskId)
  }

  return { tasksById, polling, startPolling, stopPolling, isTerminal }
})
