// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NotFound } from './NotFound';

describe('NotFound', () => {
  it('explains the dead link and offers the way back to the stages', () => {
    render(
      <MemoryRouter initialEntries={['/nowhere']}>
        <NotFound />
      </MemoryRouter>,
    );

    expect(document.title).toBe('Page not found · Lenguaraz');
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('There is nothing at this address.');
    expect(screen.getByRole('link', { name: 'Back to stages' })).toHaveAttribute('href', '/');
  });
});
