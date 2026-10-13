import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Pagination } from '../components/Pagination';

describe('Pagination', () => {
  it('shows the page count and disables Previous on the first page', () => {
    render(<Pagination page={1} pageSize={20} total={45} onPage={() => undefined} />);
    expect(screen.getByText('Page 1 of 3')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Previous' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('asks for the next page', () => {
    const onPage = vi.fn();
    render(<Pagination page={2} pageSize={20} total={45} onPage={onPage} />);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(onPage).toHaveBeenCalledWith(3);
  });
});
