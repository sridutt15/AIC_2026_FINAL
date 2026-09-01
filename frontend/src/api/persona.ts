import { API_BASE_URL } from './health'
import type { Persona } from '../types'

/** GET /personas — list seeded personas for the navbar switcher. */
export async function listPersonas(): Promise<Persona[]> {
  const response = await fetch(`${API_BASE_URL}/personas`)
  if (!response.ok) {
    throw new Error(`Failed to list personas (${response.status})`)
  }
  const body = (await response.json()) as { personas: Persona[] }
  return body.personas
}

/** Append persona_id to a query string when a persona is selected. */
export function withPersona(
  query: string,
  personaId: string | null,
): string {
  if (!personaId) return query
  return query + (query ? '&' : '?') + `persona_id=${encodeURIComponent(personaId)}`
}
