import { render, screen } from '@testing-library/react';

jest.mock('axios', () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

import App from './App_official';

test('renders the olive detection upload entry point', () => {
  render(<App />);
  expect(screen.getByText(/olive detection/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /upload images/i })).toBeInTheDocument();
});
