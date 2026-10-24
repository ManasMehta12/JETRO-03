const origin = (process.env.TAKUMI_API_ORIGIN || 'http://127.0.0.1:8000').replace(/\/$/, '');
async function request(path, token, body) {
  const response = await fetch(`${origin}/api/v1${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(10000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || `Request failed (${response.status}): ${path}`);
  return result;
}
try {
  const health = await request('/health');
  const expert = await request('/auth/demo-login', undefined, { demo_user: 'expert' });
  const apprentice = await request('/auth/demo-login', undefined, { demo_user: 'apprentice' });
  const [config, overview, course] = await Promise.all([
    request('/studio/tasks/task_001/analysis/config', expert.access_token),
    request('/studio/tasks/task_001', expert.access_token),
    request('/learning/course', apprentice.access_token),
  ]);
  console.log(`Service: ${health.status} | database: ${health.database} | schema: ${health.schema_version}`);
  console.log(`Diagnosis: ${config.enabled ? 'enabled' : 'disabled'} | mode: ${config.mode} | provider: ${config.provider} | model: ${config.model}`);
  console.log(config.notice);
  console.log(`Bearing draft: r${overview.draft.revision} | pending expert questions: ${overview.draft.clarifications.filter(item => item.status === 'pending').length}`);
  console.log(`Apprentice release: ${course.release_id || 'not published'} | version: ${course.release_version || 'none'}`);
  console.log(`Course recording: ${course.video_configured ? 'configured — verify playback in the browser' : 'deferred — manual completion is available'}`);
  console.log('Open /studio or /studio/admin. Configure live credentials or explicitly select rehearsal, review proposed changes, then Approve & publish. The apprentice page refreshes automatically.');
  if (!config.enabled || health.status !== 'ok') process.exitCode = 1;
} catch (error) {
  console.error(`Demo preflight failed: ${error.message}. Start the updated backend and retry.`);
  process.exitCode = 1;
}
