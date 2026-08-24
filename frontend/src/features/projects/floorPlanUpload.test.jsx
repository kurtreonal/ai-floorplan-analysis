/* @vitest-environment jsdom */

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FloorPlanApiError, uploadFloorPlan } from '../../api/floorPlans.js'
import {
  createProjectFloor,
  listProjectFloors,
  ProjectFloorApiError,
} from '../../api/projectFloors.js'
import { CreateProjectFloorForm } from './CreateProjectFloorForm.jsx'
import { FloorPlanUploadForm, FLOOR_PLAN_ACCEPT } from './FloorPlanUploadForm.jsx'
import { ProjectFloorUploadPanel } from './ProjectFloorUploadPanel.jsx'


vi.mock('../../api/projectFloors.js', async () => {
  const actual = await vi.importActual('../../api/projectFloors.js')
  return {
    ...actual,
    createProjectFloor: vi.fn(),
    listProjectFloors: vi.fn(),
  }
})

vi.mock('../../api/floorPlans.js', async () => {
  const actual = await vi.importActual('../../api/floorPlans.js')
  return {
    ...actual,
    uploadFloorPlan: vi.fn(),
  }
})

const PROJECT_ID = 7
const FLOORS = [
  { id: 12, project_id: PROJECT_ID, name: 'Ground Floor', sort_order: 0 },
  { id: 19, project_id: PROJECT_ID, name: 'Second Floor', sort_order: 1 },
]
const DESIGNER_SESSION = { user: { id: 10, role: 'DESIGNER' } }
const ADMIN_SESSION = { user: { id: 1, role: 'ADMIN' } }
const UPLOAD = {
  id: 42,
  project_floor_id: 12,
  original_filename: 'house-plan.png',
  mime_type: 'image/png',
  file_size: 4,
  processing_status: 'uploaded',
}

function imageFile(name = 'house-plan.png', type = 'image/png') {
  return new File([new Uint8Array([1, 2, 3, 4])], name, { type })
}

function chooseFile(file = imageFile()) {
  const input = screen.getByLabelText('Floor-plan file')
  fireEvent.change(input, { target: { files: [file] } })
  return input
}

function submitUpload() {
  fireEvent.click(screen.getByRole('button', { name: 'Upload floor plan' }))
}

function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () => resolve(Array.from(new Uint8Array(reader.result)))
    reader.readAsArrayBuffer(file)
  })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.location.hash = ''
})

describe('project floor upload panel', () => {
  it('shows an accessible floor loading state', () => {
    listProjectFloors.mockReturnValue(new Promise(() => {}))

    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={DESIGNER_SESSION} />)

    expect(screen.getByRole('status').textContent).toContain('Loading project floors')
  })

  it('shows the empty state and Designer floor-creation form', async () => {
    listProjectFloors.mockResolvedValue([])

    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={DESIGNER_SESSION} />)

    expect(await screen.findByText('No project floors yet.')).toBeTruthy()
    expect(screen.getByLabelText('Floor name')).toBeTruthy()
    expect(screen.queryByLabelText('Floor-plan file')).toBeNull()
  })

  it('shows a safe list error and retries', async () => {
    listProjectFloors
      .mockRejectedValueOnce(new ProjectFloorApiError('private detail', 503))
      .mockResolvedValueOnce(FLOORS)

    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={DESIGNER_SESSION} />)

    expect(await screen.findByText('Project floors are temporarily unavailable.')).toBeTruthy()
    expect(screen.queryByText('private detail')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('combobox', { name: 'Project floor' })).toBeTruthy()
    expect(listProjectFloors).toHaveBeenCalledTimes(2)
  })

  it('keeps floor ordering exactly as returned by the API', async () => {
    listProjectFloors.mockResolvedValue([FLOORS[1], FLOORS[0]])

    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={DESIGNER_SESSION} />)

    const options = await screen.findAllByRole('option')
    expect(options.map((option) => option.textContent)).toEqual([
      'Second Floor',
      'Ground Floor',
    ])
  })

  it('shows Admin floor information without create or upload controls', async () => {
    listProjectFloors.mockResolvedValue(FLOORS)

    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={ADMIN_SESSION} />)

    expect(await screen.findByText('Floor-plan uploads require a Designer account.')).toBeTruthy()
    expect(screen.getByText('Ground Floor')).toBeTruthy()
    expect(screen.queryByLabelText('Floor name')).toBeNull()
    expect(screen.queryByLabelText('Floor-plan file')).toBeNull()
    expect(screen.queryByRole('button', { name: /upload floor plan/i })).toBeNull()
  })

  it('automatically selects a newly created floor', async () => {
    const createdFloor = {
      id: 27,
      project_id: PROJECT_ID,
      name: 'Ground Floor',
      sort_order: 0,
    }
    listProjectFloors.mockResolvedValue([])
    createProjectFloor.mockResolvedValue(createdFloor)
    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={DESIGNER_SESSION} />)
    await screen.findByText('No project floors yet.')

    fireEvent.change(screen.getByLabelText('Floor name'), {
      target: { value: '  Ground Floor  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create floor' }))

    const selector = await screen.findByRole('combobox', { name: 'Project floor' })
    expect(selector.value).toBe('27')
    expect(createProjectFloor).toHaveBeenCalledWith(
      PROJECT_ID,
      { name: 'Ground Floor' },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('locks floor creation against repeated submission', async () => {
    let resolveCreation
    createProjectFloor.mockReturnValue(new Promise((resolve) => {
      resolveCreation = resolve
    }))
    const onCreated = vi.fn()
    const { container } = render(
      <CreateProjectFloorForm projectId={PROJECT_ID} onCreated={onCreated} />,
    )
    fireEvent.change(screen.getByLabelText('Floor name'), {
      target: { value: 'Ground Floor' },
    })
    const form = container.querySelector('form')

    fireEvent.submit(form)
    fireEvent.submit(form)

    expect(screen.getByRole('button', { name: 'Creating floor…' }).disabled).toBe(true)
    expect(createProjectFloor).toHaveBeenCalledTimes(1)
    await act(async () => resolveCreation(FLOORS[0]))
    expect(onCreated).toHaveBeenCalledWith(FLOORS[0])
  })
})

describe('floor plan upload form', () => {
  it('advertises the approved JPEG, PNG, and PDF accept values', () => {
    render(
      <FloorPlanUploadForm
        projectId={PROJECT_ID}
        projectFloorId={12}
        onUploaded={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Floor-plan file').getAttribute('accept')).toBe(
      FLOOR_PLAN_ACCEPT,
    )
    expect(FLOOR_PLAN_ACCEPT).toContain('.jpg')
    expect(FLOOR_PLAN_ACCEPT).toContain('.jpeg')
    expect(FLOOR_PLAN_ACCEPT).toContain('.png')
    expect(FLOOR_PLAN_ACCEPT).toContain('.pdf')
  })

  it('blocks unsupported extensions before upload', () => {
    render(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId={12} onUploaded={vi.fn()} />,
    )

    chooseFile(imageFile('plan.gif', 'image/gif'))

    expect(screen.getByRole('alert').textContent).toBe('Choose a JPEG, PNG, or PDF floor plan.')
    expect(uploadFloorPlan).not.toHaveBeenCalled()
  })

  it('blocks empty or mismatched MIME types before upload', () => {
    const { rerender } = render(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId={12} onUploaded={vi.fn()} />,
    )

    chooseFile(imageFile('plan.png', ''))
    expect(screen.getByRole('alert').textContent).toContain('does not match')
    rerender(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId={12} onUploaded={vi.fn()} />,
    )
    chooseFile(imageFile('plan.png', 'image/jpeg'))
    expect(screen.getByRole('alert').textContent).toContain('does not match')
    expect(uploadFloorPlan).not.toHaveBeenCalled()
  })

  it('requires a selected project floor', () => {
    render(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId="" onUploaded={vi.fn()} />,
    )
    chooseFile()

    submitUpload()

    expect(screen.getByRole('alert').textContent).toBe('Select a project floor before uploading.')
    expect(uploadFloorPlan).not.toHaveBeenCalled()
  })

  it('shows indeterminate loading and prevents repeated submissions', async () => {
    let resolveUpload
    uploadFloorPlan.mockReturnValue(new Promise((resolve) => {
      resolveUpload = resolve
    }))
    const { container } = render(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId={12} onUploaded={vi.fn()} />,
    )
    chooseFile()
    const form = container.querySelector('form')

    fireEvent.submit(form)
    fireEvent.submit(form)

    expect(screen.getByRole('status').textContent).toContain('Uploading floor plan')
    expect(screen.getByRole('button', { name: 'Uploading…' }).disabled).toBe(true)
    expect(screen.getByLabelText('Floor-plan file').disabled).toBe(true)
    expect(uploadFloorPlan).toHaveBeenCalledTimes(1)
    await act(async () => resolveUpload(UPLOAD))
  })

  it('disables floor selection while an upload is pending', async () => {
    let resolveUpload
    listProjectFloors.mockResolvedValue(FLOORS)
    uploadFloorPlan.mockReturnValue(new Promise((resolve) => {
      resolveUpload = resolve
    }))
    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={DESIGNER_SESSION} />)
    const selector = await screen.findByRole('combobox', { name: 'Project floor' })
    chooseFile()

    submitUpload()

    expect(selector.disabled).toBe(true)
    await act(async () => resolveUpload(UPLOAD))
  })

  it('renders a successful response in the session workspace and clears the input', async () => {
    listProjectFloors.mockResolvedValue(FLOORS)
    uploadFloorPlan.mockResolvedValue(UPLOAD)
    render(<ProjectFloorUploadPanel projectId={PROJECT_ID} session={DESIGNER_SESSION} />)
    await screen.findByRole('combobox', { name: 'Project floor' })
    const input = chooseFile()

    submitUpload()

    expect(await screen.findByRole('heading', { name: 'Uploaded this session' })).toBeTruthy()
    expect(screen.getByText(UPLOAD.original_filename)).toBeTruthy()
    expect(screen.getByText(UPLOAD.processing_status)).toBeTruthy()
    expect(screen.getAllByText('Ground Floor')).toHaveLength(2)
    expect(screen.getByText(String(UPLOAD.id))).toBeTruthy()
    expect(screen.queryByText(/Selected:/)).toBeNull()
    expect(input.value).toBe('')
  })

  it('preserves a selected file and its bytes after a failed upload', async () => {
    const file = imageFile()
    const bytesBefore = await readFile(file)
    uploadFloorPlan.mockRejectedValue(
      new FloorPlanApiError('The uploaded image is corrupt.', 422, 'UPLOAD_IMAGE_INVALID'),
    )
    render(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId={12} onUploaded={vi.fn()} />,
    )
    chooseFile(file)

    submitUpload()

    expect(await screen.findByText('The uploaded image is corrupt.')).toBeTruthy()
    expect(screen.getByText(/Selected:/).textContent).toContain(file.name)
    expect(file.name).toBe('house-plan.png')
    expect(file.size).toBe(4)
    expect(file.type).toBe('image/png')
    expect(await readFile(file)).toEqual(bytesBefore)
    expect(uploadFloorPlan.mock.calls[0][1].file).toBe(file)
  })

  it.each([
    [413, 'UPLOAD_TOO_LARGE', 'backend detail', 'The selected file exceeds the configured upload-size limit.'],
    [415, 'UPLOAD_MIME_UNSUPPORTED', 'This MIME type is unsupported.', 'This MIME type is unsupported.'],
    [422, 'UPLOAD_IMAGE_INVALID', 'The uploaded image is corrupt.', 'The uploaded image is corrupt.'],
    [403, 'AUTHORIZATION_DENIED', 'backend detail', 'You are not authorized to upload floor plans.'],
    [404, 'PROJECT_FLOOR_NOT_FOUND', 'backend detail', 'The selected project or floor is no longer available.'],
    [503, 'FLOOR_PLAN_UPLOAD_FAILED', 'backend detail', 'The floor-plan upload service is temporarily unavailable.'],
  ])('shows the safe UI message for backend %s', async (status, code, apiMessage, expected) => {
    uploadFloorPlan.mockRejectedValue(new FloorPlanApiError(apiMessage, status, code))
    render(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId={12} onUploaded={vi.fn()} />,
    )
    chooseFile()

    submitUpload()

    expect(await screen.findByText(expected)).toBeTruthy()
  })

  it('redirects a 401 upload response to session-expired sign-in', async () => {
    uploadFloorPlan.mockRejectedValue(
      new FloorPlanApiError('Authentication is required.', 401, 'AUTHENTICATION_REQUIRED'),
    )
    render(
      <FloorPlanUploadForm projectId={PROJECT_ID} projectFloorId={12} onUploaded={vi.fn()} />,
    )
    chooseFile()

    submitUpload()

    await waitFor(() => {
      expect(window.location.hash).toBe('#/signin?reason=session-expired')
    })
  })
})
