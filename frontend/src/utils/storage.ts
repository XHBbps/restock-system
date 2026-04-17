export type StorageGuard<T> = (value: unknown) => value is T

interface ReadStoredJsonOptions<T> {
  guard?: StorageGuard<T>
}

export function readStoredJson<T>(
  key: string,
  fallback: T,
  options: ReadStoredJsonOptions<T> = {},
): T {
  const raw = localStorage.getItem(key)
  if (raw === null) {
    return fallback
  }

  try {
    const parsed = JSON.parse(raw) as unknown
    if (options.guard && !options.guard(parsed)) {
      throw new Error(`Invalid stored value for ${key}`)
    }
    return parsed as T
  } catch {
    localStorage.removeItem(key)
    return fallback
  }
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}
