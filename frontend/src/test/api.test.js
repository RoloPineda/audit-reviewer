import { describe, it, expect, vi, beforeEach } from 'vitest';
import { uploadQuestionnaire, evaluateQuestion } from '../api';

const AUTH_HEADER = { Authorization: 'Basic dGVzdDpwYXNz' };

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('uploadQuestionnaire', () => {
  it('sends auth header and returns parsed JSON', async () => {
    const mockResponse = { metadata: {}, questions: [] };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    });
    vi.stubGlobal('fetch', fetchMock);

    const file = new File(['pdf'], 'test.pdf', { type: 'application/pdf' });
    const result = await uploadQuestionnaire(file, AUTH_HEADER);

    expect(result).toEqual(mockResponse);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/questionnaire'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining(AUTH_HEADER),
      }),
    );
  });

  it('throws on 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }));

    const file = new File(['pdf'], 'test.pdf', { type: 'application/pdf' });
    await expect(uploadQuestionnaire(file, AUTH_HEADER)).rejects.toThrow('Invalid credentials');
  });

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Server error'),
    }));

    const file = new File(['pdf'], 'test.pdf', { type: 'application/pdf' });
    await expect(uploadQuestionnaire(file, AUTH_HEADER)).rejects.toThrow('Server error');
  });
});

describe('evaluateQuestion', () => {
  it('sends question as JSON with auth header', async () => {
    const mockResult = { status: 'met', evidence: 'found', citation: 'p1' };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResult),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await evaluateQuestion('test question', AUTH_HEADER);

    expect(result).toEqual(mockResult);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/evaluate'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          ...AUTH_HEADER,
        }),
        body: JSON.stringify({ question: 'test question' }),
      }),
    );
  });

  it('throws on 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }));
    await expect(evaluateQuestion('q', AUTH_HEADER)).rejects.toThrow('Invalid credentials');
  });
});