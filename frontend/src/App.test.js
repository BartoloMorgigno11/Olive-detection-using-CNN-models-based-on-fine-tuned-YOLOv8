import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';

jest.mock('axios', () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

import App from './App_official';

const uploadImage = () => {
  fireEvent.change(screen.getByLabelText(/upload images/i), {
    target: { files: [new File(['image'], 'olive.png', { type: 'image/png' })] },
  });
};

beforeAll(() => {
  URL.createObjectURL = jest.fn(() => 'blob:olive-preview');
});

beforeEach(() => {
  jest.clearAllMocks();
});

test('renders the olive detection upload entry point', () => {
  render(<App />);
  expect(screen.getByText(/olive detection/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /upload images/i })).toBeInTheDocument();
});

test('offers reset after an upload error', async () => {
  axios.post.mockRejectedValueOnce({ response: { data: { error: 'Only PNG and JPEG image files are accepted.' } } });

  render(<App />);
  uploadImage();
  fireEvent.click(screen.getByRole('button', { name: /start analysis/i }));

  expect(await screen.findByText(/only png and jpeg/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /start a new analysis/i })).toBeEnabled();
});

test('uses reset to recover when completed artefacts reject a new upload', async () => {
  axios.post
    .mockRejectedValueOnce({ response: { data: { error: 'Clear the completed local analysis before starting a new one.' } } })
    .mockResolvedValueOnce({ status: 200 });

  render(<App />);
  uploadImage();
  fireEvent.click(screen.getByRole('button', { name: /start analysis/i }));

  expect(await screen.findByText(/clear the completed local analysis/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /start a new analysis/i }));

  await waitFor(() => {
    expect(axios.post).toHaveBeenLastCalledWith('http://localhost:3001/clean_folders');
  });
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /upload images/i })).toBeInTheDocument();
  });
});

test('disables reset while an analysis is active', async () => {
  axios.post.mockResolvedValueOnce({ status: 200 });

  render(<App />);
  uploadImage();
  fireEvent.click(screen.getByRole('button', { name: /start analysis/i }));

  await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(1));
  const reset = screen.getByRole('button', { name: /start a new analysis/i });
  expect(reset).toBeDisabled();
  fireEvent.click(reset);
  expect(axios.post).toHaveBeenCalledTimes(1);
});
