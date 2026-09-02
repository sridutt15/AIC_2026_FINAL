/** Batch-workflow cache: results stored per dataset+workflow, shared across pages.
 *
 * Sidebar navigation NEVER triggers discovery — pages read whatever is
 * already cached and render it immediately. Discovery/processing runs only
 * when the user clicks a Discover/Refresh button, which stores the response
 * here. Keys are scoped per workflow + dataset (+ implicitly per user: the
 * API is user-scoped, and the cache resets on login change).
 */

import { getUserId } from './authClient'

type Entry<T> = { result: T; at: number }

const store = new Map<string, Entry<unknown>>()
const inflight = new Map<string, Promise<unknown>>()

function userScope(): string {
  return getUserId() ?? 'anon'
}

function fullKey(key: string): string {
  return `${userScope()}::${key}`
}

/** Read a cached batch result (null when nothing cached yet). */
export function getCachedBatch<T>(key: string): T | null {
  const hit = store.get(fullKey(key))
  return hit ? (hit.result as T) : null
}

/** Run (or join an in-flight) batch and store its result.
 * Only button handlers call this — never page navigation. */
export async function runAndCacheBatch<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const k = fullKey(key)
  const existing = inflight.get(k)
  if (existing) return existing as Promise<T>
  const promise = fetcher()
    .then((result) => {
      store.set(k, { result, at: Date.now() })
      return result
    })
    .finally(() => inflight.delete(k))
  inflight.set(k, promise)
  return promise
}

/** Force the next run to re-fetch (Refresh/Rediscover buttons). */
export function invalidateBatch(key: string): void {
  store.delete(fullKey(key))
}

/** Invalidate every cached entry for a dataset (all workflows). */
export function invalidateDataset(datasetId: string): void {
  const prefix = fullKey('')
  for (const key of [...store.keys()]) {
    if (key.startsWith(prefix) && key.includes(datasetId)) store.delete(key)
  }
  for (const key of [...inflight.keys()]) {
    if (key.startsWith(prefix) && key.includes(datasetId)) inflight.delete(key)
  }
}
