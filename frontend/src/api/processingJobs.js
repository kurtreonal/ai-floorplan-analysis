import { API_BASE_URL } from './auth.js'


const GENERIC_PROCESSING_ERROR = 'The processing request could not be completed.'
const GENERIC_STATUS_ERROR = 'The processing status could not be loaded.'
const GENERIC_HISTORY_ERROR = 'Processing-job history could not be loaded.'
const GENERIC_CANCELLATION_ERROR = 'The cancellation request could not be completed.'
const PROCESSING_STATUSES = new Set([
  'queued',
  'processing',
  'completed',
  'failed',
  'cancelled',
])


export class ProcessingJobApiError extends Error {
  constructor(message, status = 0, code = null, existingJobId = null) {
    super(message)
    this.name = 'ProcessingJobApiError'
    this.status = status
    this.code = code
    this.existingJobId = existingJobId
  }
}

function isPositiveInteger(value) {
  return Number.isInteger(value) && value > 0
}

async function parseJson(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

async function parseSafeError(response, genericMessage) {
  const payload = await parseJson(response)
  const error = payload?.detail?.error
  const code = typeof error?.code === 'string' && error.code.length > 0
    ? error.code
    : null
  const message = typeof error?.message === 'string' && error.message.length > 0
    ? error.message
    : genericMessage
  const existingJobId = (
    response.status === 409
    && code === 'PROCESSING_JOB_ALREADY_ACTIVE'
    && isPositiveInteger(error?.details?.job_id)
  )
    ? error.details.job_id
    : null

  return { code, message, existingJobId }
}

async function request(url, options, genericMessage) {
  let response
  try {
    response = await fetch(url, options)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ProcessingJobApiError(genericMessage)
  }

  if (!response.ok) {
    const safeError = await parseSafeError(response, genericMessage)
    throw new ProcessingJobApiError(
      safeError.message,
      response.status,
      safeError.code,
      safeError.existingJobId,
    )
  }

  return parseJson(response)
}

function normalizeStartResponse(payload) {
  if (!isPositiveInteger(payload?.job_id) || payload?.status !== 'queued') {
    throw new ProcessingJobApiError(GENERIC_PROCESSING_ERROR)
  }

  return {
    job_id: payload.job_id,
    status: payload.status,
  }
}

function normalizeStatusResponse(payload) {
  if (
    !isPositiveInteger(payload?.job_id)
    || typeof payload?.type !== 'string'
    || payload.type.length === 0
    || !PROCESSING_STATUSES.has(payload?.status)
    || !Number.isInteger(payload?.progress)
    || payload.progress < 0
    || payload.progress > 100
    || !(payload?.error_message === null || typeof payload?.error_message === 'string')
  ) {
    throw new ProcessingJobApiError(GENERIC_STATUS_ERROR)
  }

  return {
    job_id: payload.job_id,
    type: payload.type,
    status: payload.status,
    progress: payload.progress,
    error_message: payload.error_message,
  }
}

function normalizeHistoryItem(payload) {
  const normalized = normalizeStatusResponse(payload)
  if (
    typeof payload?.created_at !== 'string'
    || Number.isNaN(Date.parse(payload.created_at))
    || typeof payload?.updated_at !== 'string'
    || Number.isNaN(Date.parse(payload.updated_at))
  ) {
    throw new ProcessingJobApiError(GENERIC_HISTORY_ERROR)
  }
  return {
    ...normalized,
    created_at: payload.created_at,
    updated_at: payload.updated_at,
  }
}

export async function startFloorPlanProcessing(floorPlanId, { signal } = {}) {
  const payload = await request(
    `${API_BASE_URL}/api/floor-plans/${encodeURIComponent(floorPlanId)}/process`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    },
    GENERIC_PROCESSING_ERROR,
  )
  return normalizeStartResponse(payload)
}

export async function fetchProcessingJob(jobId, { signal } = {}) {
  const payload = await request(
    `${API_BASE_URL}/api/processing-jobs/${encodeURIComponent(jobId)}`,
    {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    },
    GENERIC_STATUS_ERROR,
  )
  return normalizeStatusResponse(payload)
}

export async function listProcessingJobs(floorPlanId, { signal } = {}) {
  const payload = await request(
    `${API_BASE_URL}/api/floor-plans/${encodeURIComponent(floorPlanId)}/processing-jobs?limit=50`,
    {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    },
    GENERIC_HISTORY_ERROR,
  )
  if (!Array.isArray(payload)) {
    throw new ProcessingJobApiError(GENERIC_HISTORY_ERROR)
  }
  return payload.map(normalizeHistoryItem)
}

export async function cancelProcessingJob(jobId, { signal } = {}) {
  if (!isPositiveInteger(jobId)) {
    throw new ProcessingJobApiError(GENERIC_CANCELLATION_ERROR)
  }
  const payload = await request(
    `${API_BASE_URL}/api/processing-jobs/${jobId}/cancel`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    },
    GENERIC_CANCELLATION_ERROR,
  )
  if (!isPositiveInteger(payload?.job_id)
    || payload.job_id !== jobId
    || !['processing', 'cancelled'].includes(payload.status)
    || !['queued_cancelled', 'cooperative_requested'].includes(payload.cancellation_mode)) {
    throw new ProcessingJobApiError(GENERIC_CANCELLATION_ERROR)
  }
  return {
    job_id: payload.job_id,
    status: payload.status,
    cancellation_mode: payload.cancellation_mode,
  }
}
