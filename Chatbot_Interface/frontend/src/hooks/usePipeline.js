import { useState, useRef, useCallback, useEffect } from 'react'
import { apiUrl } from '../lib/api.js'

export function usePipeline(getToken) {
  const [jobs, setJobs] = useState([])
  const [activeJob, setActive] = useState(null)
  const esRef = useRef(null)

  const _authHeaders = useCallback(() => ({
    Authorization: `Bearer ${getToken()}`,
  }), [getToken])

  const _jsonHeaders = useCallback(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${getToken()}`,
  }), [getToken])

  const _updateJob = useCallback((id, patch) => {
    setJobs(prev => prev.map(j => (
      j.id === id || j.job_id === id ? { ...j, ...patch } : j
    )))
    setActive(prev => (
      prev?.id === id || prev?.job_id === id ? { ...prev, ...patch } : prev
    ))
  }, [])

  const _appendLog = useCallback((id, entry) => {
    setJobs(prev => prev.map(j => (
      j.id === id || j.job_id === id
        ? { ...j, logs: [...(j.logs || []), entry] }
        : j
    )))
    setActive(prev => (
      prev?.id === id || prev?.job_id === id
        ? { ...prev, logs: [...(prev.logs || []), entry] }
        : prev
    ))
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/history'), { headers: _jsonHeaders() })
      if (!res.ok) return
      const data = await res.json()
      setJobs((data.jobs || []).map(j => ({
        id: j.job_id || j.id,
        job_id: j.job_id || j.id,
        prompt: j.prompt,
        status: j.status,
        logs: j.logs || [],
        result: j.result || {},
        error: j.error || '',
        created: j.created_at || j.created,
      })))
    } catch {
      // backend may not be running yet
    }
  }, [_jsonHeaders])

  const _pollUntilDone = useCallback((job_id) => {
    const iv = setInterval(async () => {
      try {
        const res = await fetch(apiUrl(`/pipeline/status/${job_id}`), {
          headers: _jsonHeaders(),
        })
        if (!res.ok) {
          clearInterval(iv)
          return
        }
        const data = await res.json()
        _updateJob(job_id, {
          status: data.status,
          logs: data.logs || [],
          result: data.result || {},
          error: data.error || '',
        })
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(iv)
          loadHistory()
        }
      } catch {
        clearInterval(iv)
      }
    }, 3000)
  }, [_jsonHeaders, _updateJob, loadHistory])

  const _subscribeSSE = useCallback((job_id) => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    const token = localStorage.getItem('radml_token') || ''
    const es = new EventSource(apiUrl(`/pipeline/stream/${job_id}?token=${encodeURIComponent(token)}`))
    esRef.current = es

    es.onmessage = (e) => {
      let msg
      try {
        msg = JSON.parse(e.data)
      } catch {
        return
      }

      if (msg.type === 'heartbeat') return

      if (msg.type === 'done' || msg.type === 'error') {
        _updateJob(job_id, {
          status: msg.type === 'done' ? 'done' : 'error',
          result: msg.result || {},
          error: msg.error || '',
        })
        loadHistory()
        es.close()
        esRef.current = null
        return
      }

      _appendLog(job_id, msg)
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      _pollUntilDone(job_id)
    }
  }, [_appendLog, _pollUntilDone, _updateJob, loadHistory])

  const _startJob = useCallback((job_id, prompt) => {
    const newJob = {
      id: job_id,
      job_id,
      prompt,
      status: 'running',
      logs: [],
      result: {},
      error: '',
    }
    setJobs(prev => [newJob, ...prev])
    setActive(newJob)
    _subscribeSSE(job_id)
  }, [_subscribeSSE])

  const runPipeline = useCallback(async (prompt) => {
    try {
      const res = await fetch(apiUrl('/pipeline/run'), {
        method: 'POST',
        headers: _jsonHeaders(),
        body: JSON.stringify({ prompt }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `HTTP ${res.status}`)
      }
      const data = await res.json()
      _startJob(data.job_id, prompt)
    } catch (err) {
      const fakeId = `err-${Date.now()}`
      const failed = {
        id: fakeId,
        job_id: fakeId,
        prompt,
        status: 'error',
        logs: [],
        result: {},
        error: err.message,
      }
      setJobs(prev => [failed, ...prev])
      setActive(failed)
    }
  }, [_jsonHeaders, _startJob])

  const runPipelineWithFile = useCallback(async (prompt, file) => {
    try {
      const formData = new FormData()
      formData.append('prompt', prompt)
      formData.append('file', file)
      const res = await fetch(apiUrl('/pipeline/upload'), {
        method: 'POST',
        headers: _authHeaders(),
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `HTTP ${res.status}`)
      }
      const data = await res.json()
      _startJob(data.job_id, `[Upload: ${file.name}] ${prompt}`)
    } catch (err) {
      const fakeId = `err-${Date.now()}`
      const failed = {
        id: fakeId,
        job_id: fakeId,
        prompt,
        status: 'error',
        logs: [],
        result: {},
        error: err.message,
      }
      setJobs(prev => [failed, ...prev])
      setActive(failed)
    }
  }, [_authHeaders, _startJob])

  const stopPipeline = useCallback(async (jobId) => {
    try {
      await fetch(apiUrl(`/pipeline/stop/${jobId}`), {
        method: 'POST',
        headers: _jsonHeaders(),
      })
    } catch {
      // ignore
    }
    _updateJob(jobId, { status: 'error', error: 'Cancelled by user.' })
    loadHistory()
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [_jsonHeaders, _updateJob, loadHistory])

  const selectJob = useCallback(async (jobId) => {
    if (!jobId) {
      setActive(null)
      return
    }

    const inMem = jobs.find(j => j.id === jobId || j.job_id === jobId)
    if (inMem && (inMem.logs?.length || inMem.status !== 'running')) {
      setActive(inMem)
      if (inMem.status === 'running') _subscribeSSE(jobId)
      return
    }

    try {
      const res = await fetch(apiUrl(`/history/${jobId}`), { headers: _jsonHeaders() })
      if (!res.ok) return
      const data = await res.json()
      const full = {
        id: data.job_id || jobId,
        job_id: data.job_id || jobId,
        prompt: data.prompt,
        status: data.status,
        logs: data.logs || [],
        result: data.result || {},
        error: data.error || '',
      }
      setActive(full)
      if (data.status === 'running') _subscribeSSE(jobId)
    } catch {
      // ignore
    }
  }, [jobs, _jsonHeaders, _subscribeSSE])

  const deleteJob = useCallback(async (jobId) => {
    try {
      await fetch(apiUrl(`/history/${jobId}`), {
        method: 'DELETE',
        headers: _jsonHeaders(),
      })
    } catch {
      // ignore
    }
    setJobs(prev => prev.filter(j => j.id !== jobId && j.job_id !== jobId))
    setActive(prev => (prev?.id === jobId || prev?.job_id === jobId ? null : prev))
  }, [_jsonHeaders])

  const deleteAllHistory = useCallback(async () => {
    try {
      await fetch(apiUrl('/history'), {
        method: 'DELETE',
        headers: _jsonHeaders(),
      })
    } catch {
      // ignore
    }
    setJobs([])
    setActive(null)
  }, [_jsonHeaders])

  useEffect(() => () => esRef.current?.close(), [])

  return {
    jobs,
    activeJob,
    runPipeline,
    runPipelineWithFile,
    stopPipeline,
    loadHistory,
    selectJob,
    deleteJob,
    deleteAllHistory,
  }
}
