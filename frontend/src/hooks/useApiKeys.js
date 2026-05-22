import { useState, useCallback } from 'react'
import { getKey, setKey } from '../lib/storage'

const KEY_NAMES = ['gemini', 'fal', 'elevenlabs']

function readKeys() {
  return Object.fromEntries(KEY_NAMES.map(k => [k, getKey(k)]))
}

export function useApiKeys() {
  const [keys, setKeys] = useState(readKeys)

  const updateKey = useCallback((name, value) => {
    setKey(name, value)
    setKeys(prev => ({ ...prev, [name]: value }))
  }, [])

  return { keys, updateKey }
}
