import type { Page } from '@playwright/test';
import type { LearningCourse, LearningProgress } from '../src/learning-api';

export const courseFixture: LearningCourse = {
  id: 'ball-bearing', title: 'Shaft and Bearing Inspection',
  description: 'Illustrative course for the unpowered bearing bench assembly.',
  equipment: 'Shaft-and-bearing bench', source_label: 'illustrative', release_id: 'release_001',
  video_url: '/e2e/fixtures/lesson.webm', video_duration_seconds: 6, video_configured: true,
  knowledge_units: [{ id: 'ku_001', action: 'Inspect the bearing housing', cue: 'Use the recorded evidence.' }],
};

export async function mockLearning(page: Page, courseCompleted = true) {
  let progress: LearningProgress = {
    course_id: 'ball-bearing', release_id: 'release_001', watched_seconds: courseCompleted ? 6 : 0,
    course_completed: courseCompleted, playground_unlocked: courseCompleted,
    interview_unlocked: false, playground_result: null, interview: null,
  };
  await page.route('**/api/v1/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    let body: unknown = progress;
    if (pathname.endsWith('/auth/demo-login')) body = { access_token: 'browser-test-token', expires_at: '2099-01-01T00:00:00Z' };
    else if (pathname.endsWith('/learning/course')) body = courseFixture;
    else if (pathname.endsWith('/learning/complete')) {
      const { stage } = route.request().postDataJSON();
      progress = { ...progress, course_completed: true, playground_unlocked: true,
        interview_unlocked: stage === 'playground', manual_completion: { ...progress.manual_completion, [stage]: new Date().toISOString() } };
      body = progress;
    }
    else if (pathname.endsWith('/learning/playground')) {
      const input = route.request().postDataJSON();
      progress = { ...progress, interview_unlocked: true, playground_result: {
        id: 'attempt_test', scenario: input.scenario, mode: input.mode,
        scores: { procedure: 100, judgment: 100, knowledge: 100 },
        outcome: 'All authored checks were recorded.', critical_error: false, release_id: 'release_001',
      } };
      body = progress;
    }
    else if (pathname.endsWith('/learning/reset')) {
      progress = {
        course_id: 'ball-bearing', release_id: 'release_001', watched_seconds: 0,
        course_completed: false, playground_unlocked: false,
        interview_unlocked: false, playground_result: null, interview: null, manual_completion: {},
      };
      body = progress;
    }
    await route.fulfill({ json: body });

  });
}

export async function openPlayground(page: Page) {
  await mockLearning(page);
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Course modules' }).getByRole('button', { name: /Simulation playground/i }).click();
}
