import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider, defaultTheme } from '@adobe/react-spectrum';
import { AuthProvider } from '../context/AuthContext';
import ResultsPage from '../pages/ResultsPage';
import * as api from '../api';

const QUESTIONS = [
  { number: 1, text: 'Question one', reference: 'APL 1' },
  { number: 2, text: 'Question two', reference: 'APL 2' },
  { number: 3, text: 'Question three', reference: 'APL 3' },
];

const DATA = {
  metadata: { submission_item: 'Test', apl_reference: 'APL-001' },
  questions: QUESTIONS,
};

function renderResults(data = DATA) {
  return render(
    <Provider theme={defaultTheme}>
      <AuthProvider>
        <ResultsPage data={data} onError={vi.fn()} onLogout={vi.fn()} />
      </AuthProvider>
    </Provider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('Evaluate All', () => {
  it('skips already-evaluated questions', async () => {
    const evaluateSpy = vi.spyOn(api, 'evaluateQuestion');

    let callCount = 0;
    evaluateSpy.mockImplementation(() => {
      callCount += 1;
      return Promise.resolve({
        status: 'met',
        evidence: `evidence ${callCount}`,
        citation: `cite ${callCount}`,
      });
    });

    renderResults();
    const user = userEvent.setup();

    const playButtons = screen.getAllByLabelText(/Evaluate question/);
    await user.click(playButtons[0]);

    await waitFor(() => {
      expect(evaluateSpy).toHaveBeenCalledTimes(1);
    });

    const evaluateAllButton = screen.getByRole('button', { name: /Evaluate All/ });
    await user.click(evaluateAllButton);

    await waitFor(() => {
      expect(evaluateSpy).toHaveBeenCalledTimes(3);
    });

    expect(evaluateSpy).toHaveBeenNthCalledWith(1, 'Question one', expect.any(Object));
    expect(evaluateSpy).toHaveBeenNthCalledWith(2, 'Question two', expect.any(Object));
    expect(evaluateSpy).toHaveBeenNthCalledWith(3, 'Question three', expect.any(Object));
  });

  it('stops evaluation when cancel is clicked', async () => {
    const evaluateSpy = vi.spyOn(api, 'evaluateQuestion');

    let resolveFirst;
    const firstCall = new Promise((resolve) => {
      resolveFirst = resolve;
    });

    evaluateSpy
      .mockImplementationOnce(() => firstCall)
      .mockImplementation(() => Promise.resolve({ status: 'met', evidence: 'e', citation: 'c' }));

    renderResults();
    const user = userEvent.setup();

    const evaluateAllButton = screen.getByRole('button', { name: /Evaluate All/ });
    await user.click(evaluateAllButton);

    const stopButton = await screen.findByRole('button', { name: /Stop/ });
    await user.click(stopButton);

    resolveFirst({ status: 'met', evidence: 'e', citation: 'c' });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Evaluate All/ })).toBeInTheDocument();
    });

    expect(evaluateSpy).toHaveBeenCalledTimes(1);
  });
});