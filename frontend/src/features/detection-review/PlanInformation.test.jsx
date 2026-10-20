/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { PlanInformation } from './PlanInformation.jsx'

afterEach(cleanup)
it('keeps diagnostics optional, readable and keyboard accessible', () => {
  render(<PlanInformation title="Plan 3"><p>Source diagnostics</p><button>Review source</button></PlanInformation>)
  const trigger=screen.getByLabelText('Plan information'), details=trigger.closest('details')
  expect(details.open).toBe(false)
  expect(trigger.getAttribute('title')).toBe('Plan information')
  fireEvent.click(trigger)
  expect(details.open).toBe(true)
  screen.getByRole('button',{name:'Review source'}).focus()
  fireEvent.keyDown(document.activeElement,{key:'Escape'})
  expect(details.open).toBe(false)
  expect(document.activeElement).toBe(trigger)
})
