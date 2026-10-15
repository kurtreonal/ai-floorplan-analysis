import { createContext, useContext } from 'react'
import { DEFAULT_PREFERENCES } from './userPreferences.js'

export const PreferencesContext = createContext({ preferences: DEFAULT_PREFERENCES, updatePreferences: () => {}, storageError: null })
export function useUserPreferences() { return useContext(PreferencesContext) }
