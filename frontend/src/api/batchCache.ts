/** Batch-workflow cache: one fetch per dataset per workflow, shared across pages.
 *
 * Navigating between sidebar pages must not re-run batches that already
 * completed (results are persisted server-side too — the cache just avoids
 * duplicate requests during a session). */

type Entry = { promise: Promise<unknown>; done: boolean }

const cache = new Map<string, Entry>()

/** Fetch-once-per-key: concurrent callers share the in-flight promise. */
export function cachedBatch<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const hit = cache.get(key)
  if (hit && hit.done === false) {
    return hit.promise as Promise<T>
  }
  if (hit && hit.done) {
    return hit.promise as Promise<T>
  }
  const entry: Entry = { promise: fetcher().finally(() => (entry.done = true)), done: false }
  cache.set(key, entry)
  return entry.promise as Promise<T>
}

/** Force the next call for a key to re-fetch (e.g. after re-discovery). */
export function invalidateBatch(key: string): void {
  cache.delete(key)
}

/** Invalidate every cached entry for a dataset (all workflows). */
export function invalidateDataset(datasetId: string): void {
  for (const key of [...cache.keys()]) {
    if (key.includes(datasetId)) cache.delete(key)
  }
}
