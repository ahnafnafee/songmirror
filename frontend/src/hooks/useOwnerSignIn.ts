import { createContext, useContext } from 'react'

interface OwnerSignIn {
  enabled: boolean
  setup: (username: string, password: string, setupCode: string) => Promise<void>
}

export const OwnerSignInContext = createContext<OwnerSignIn | null>(null)

export function useOwnerSignIn() {
  const context = useContext(OwnerSignInContext)
  if (!context) throw new Error('Owner sign-in settings require ProfileShell')
  return context
}
