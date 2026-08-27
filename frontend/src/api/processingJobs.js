import { API_BASE_URL } from './auth.js'


const GENERIC_PROCESSING_ERROR = 'The processing request could not be completed.'
const GENERIC_STATUS_ERROR = 'The processing status could not be loaded.'
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
