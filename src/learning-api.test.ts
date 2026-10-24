import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const login = () => json({ access_token: 'apprentice-token', expires_at: new Date(Date.now() + 3600_000).toISOString() });

describe('learning service client', () => {
  beforeEach(() => { vi.resetModules(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('shares authentication across parallel dashboard requests', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(json({ id: 'ball-bearing' })).mockResolvedValueOnce(json({ course_id: 'ball-bearing' }));
    vi.stubGlobal('fetch', fetch);
    const { learningApi } = await import('./learning-api');
    await Promise.all([learningApi.getCourse(), learningApi.getProgress()]);
    expect(fetch.mock.calls.filter(([url]) => url === '/api/v1/auth/demo-login')).toHaveLength(1);
    expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer apprentice-token');
    expect(fetch.mock.calls[2][1].headers.Authorization).toBe('Bearer apprentice-token');
  });

  it('renews rejected authentication once and preserves server errors', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(json({ error: { code: 'TOKEN_EXPIRED', message: 'Expired' } }, 401)).mockResolvedValueOnce(login()).mockResolvedValueOnce(json({ error: { code: 'COURSE_INCOMPLETE', message: 'Watch the course first.' } }, 409));
    vi.stubGlobal('fetch', fetch);
    const { learningApi } = await import('./learning-api');
    await expect(learningApi.startInterview()).rejects.toMatchObject({ code: 'COURSE_INCOMPLETE', message: 'Watch the course first.', status: 409 });
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it('stops retrying after a second unauthorized response', async () => {
    const unauthorized = () => json({ error: { code: 'UNAUTHORIZED', message: 'Sign in required.' } }, 401);
    const fetch = vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(login()).mockResolvedValueOnce(unauthorized());
    vi.stubGlobal('fetch', fetch);
    const { learningApi } = await import('./learning-api');
    await expect(learningApi.getProgress()).rejects.toMatchObject({ code: 'UNAUTHORIZED', status: 401 });
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it('reports backend connectivity failures in user-readable language', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const { learningApi } = await import('./learning-api');
    await expect(learningApi.getCourse()).rejects.toMatchObject({ code: 'SERVICE_UNAVAILABLE', status: 0 });
  });

  it('records explicit manual section completion separately from assessment results', async () => {
    const progress = { manual_completion: { playground: '2026-10-25T01:00:00Z' }, interview_unlocked: true, playground_result: null };
    const fetch = vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(json(progress));
    vi.stubGlobal('fetch', fetch);
    const { learningApi } = await import('./learning-api');
    await expect(learningApi.completeSection('playground')).resolves.toEqual(progress);
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/learning/complete');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ stage: 'playground' });
  });

  it('resets student knowledge and returns fresh baseline progress', async () => {
    const cleared = { course_id: 'ball-bearing', watched_seconds: 0, course_completed: false, playground_unlocked: false, interview_unlocked: false, manual_completion: {}, playground_result: null, interview: null };
    const fetch = vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(json(cleared));
    vi.stubGlobal('fetch', fetch);
    const { learningApi } = await import('./learning-api');
    await expect(learningApi.resetKnowledge()).resolves.toEqual(cleared);
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/learning/reset');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({});
  });
});

