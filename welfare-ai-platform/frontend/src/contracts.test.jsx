import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { normalizeProfile } from './Citizen';
import { Badge, Trace, Source, ErrorNotice } from './ui';
import { safeUrl } from './api';

describe('profile values retain their meaning', () => {
  it('distinguishes zero, false and unanswered fields', () => {
    const profile = normalizeProfile({ annual_family_income: '0', disability_status: 'false', has_bank_account: 'true', student_status: '' });
    expect(profile.annual_family_income).toBe(0);
    expect(profile.disability_status).toBe(false);
    expect(profile.has_bank_account).toBe(true);
    expect(profile.student_status).toBeNull();
  });
});
describe('results remain understandable and safe', () => {
  it('shows a failing requirement as failing', () => {
    render(<Trace trace={{result:'FAIL',field:'annual_family_income',op:'<=',value:300000,expected:200000}}/>);
    expect(screen.getByText('Fail')).toBeInTheDocument();
    expect(screen.getByText(/Annual family income/)).toBeInTheDocument();
  });
  it('labels fictional sources and blocks executable URLs', () => {
    render(<MemoryRouter><Source fictional source={{title:'Local fixture',url:'javascript:alert(1)'}}/></MemoryRouter>);
    expect(screen.getByText(/Fictional academic fixture/)).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
    expect(safeUrl('https://example.gov.in/scheme')).toBeTruthy();
    expect(safeUrl('data:text/html,unsafe')).toBeFalsy();
  });
  it('makes recoverable failures visible', () => {
    const retry = vi.fn();
    render(<ErrorNotice error="Connection failed; your entries are preserved" retry={retry}/>);
    expect(screen.getByRole('alert')).toHaveTextContent('entries are preserved');
    screen.getByRole('button').click();
    expect(retry).toHaveBeenCalledTimes(1);
  });
  it('does not present unknown as success', () => {
    render(<Badge value="UNKNOWN"/>);
    expect(screen.getByText('Unknown')).toHaveClass('neutral');
  });
});
