import { useState, useCallback, useEffect, createContext, useContext } from 'react'
import { apiUrl, backendUnavailableMessage, isNetworkFetchError } from '../lib/api.js'

export const AuthContext = createContext(null)

function buildApiErrorMessage(res, data, fallbackMessage) {
  const rawError = typeof data?.error === 'string' ? data.error.trim() : ''
  const contentType = (res.headers.get('content-type') || '').toLowerCase()

  if (res.status === 401) {
    return rawError || 'Invalid username or password'
  }

  if (res.status >= 500) {
    if (!contentType.includes('application/json') || !rawError || /proxy|doctype|html/i.test(rawError)) {
      return 'Backend service is unavailable. Make sure the RAD-ML backend is running on http://localhost:5001.'
    }
    return rawError
  }

  return rawError || `${fallbackMessage} (${res.status})`
}

async function parseApiResponse(res, fallbackMessage) {
  const text = await res.text()
  let data = {}

  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { error: text }
    }
  }

  if (!res.ok) {
    throw new Error(buildApiErrorMessage(res, data, fallbackMessage))
  }

  return data
}

export function useAuthProvider() {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)   // checking existing session

  // Check existing JWT on mount
  useEffect(() => {
    const token = localStorage.getItem('radml_token')
    if (!token) { setLoading(false); return }
    fetch(apiUrl('/auth/me'), {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => parseApiResponse(r, 'Failed to restore session'))
      .then(data => setUser(data.user))
      .catch(() => localStorage.removeItem('radml_token'))
      .finally(() => setLoading(false))
  }, [])

  const _storeToken = (token, userData) => {
    localStorage.setItem('radml_token', token)
    setUser(userData)
  }

  const register = useCallback(async (username, password, email = '') => {
    try {
      const res  = await fetch(apiUrl('/auth/register'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, email }),
      })
      const data = await parseApiResponse(res, 'Registration failed')
      _storeToken(data.token, data.user)
      return data.user
    } catch (error) {
      if (isNetworkFetchError(error)) {
        throw new Error(backendUnavailableMessage())
      }
      throw error
    }
  }, [])

  const login = useCallback(async (username, password) => {
    try {
      const res  = await fetch(apiUrl('/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await parseApiResponse(res, 'Login failed')
      _storeToken(data.token, data.user)
      return data.user
    } catch (error) {
      if (isNetworkFetchError(error)) {
        throw new Error(backendUnavailableMessage())
      }
      throw error
    }
  }, [])

  const logout = useCallback(async () => {
    localStorage.removeItem('radml_token')
    setUser(null)
    await fetch(apiUrl('/auth/logout'), { method: 'POST' }).catch(() => {})
  }, [])

  const getToken = useCallback(() => localStorage.getItem('radml_token'), [])

  return { user, loading, register, login, logout, getToken }
}

export function useAuth() {
  return useContext(AuthContext)
}
