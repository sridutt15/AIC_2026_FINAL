import { createContext, useContext } from 'react'
import type { Persona } from '../types'

/** App-level persona context: the selected persona flows to every page. */
export const PersonaContext = createContext<{
  persona: Persona | null
  personas: Persona[]
  setPersona: (p: Persona | null) => void
}>({
  persona: null,
  personas: [],
  setPersona: () => undefined,
})

export function usePersona() {
  return useContext(PersonaContext)
}

export function usePersonaId(): string | null {
  const { persona } = usePersona()
  return persona?.persona_id ?? null
}
