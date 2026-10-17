/**
 * Adapter for Personal AI Gateway's structured Decisions API.
 * PAG owns provider keys, routing, fallback and cooldowns; Better-AXI owns browser actions.
 */
const DEFAULT_BASE_URL = 'http://127.0.0.1:4000/v1';

export function validateChoice(answer, criteria) {
  if (!answer || typeof answer.choice !== 'string' || !Object.hasOwn(criteria, answer.choice)) {
    throw new Error('Decision returned an invalid or missing choice: ' + String(answer?.choice));
  }
  return answer.choice;
}

export function decisionsEndpoint(baseUrl = DEFAULT_BASE_URL) {
  const url = new URL(baseUrl);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('PAG_BASE_URL must be an HTTP(S) URL without credentials, query or fragment');
  }
  if (url.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
    throw new Error('Use HTTPS when connecting to a remote PAG instance');
  }
  const path = url.pathname.replace(/\/+$/, '');
  if (path.endsWith('/v1/decisions')) return url.origin + path;
  if (path.endsWith('/v1')) return url.origin + path + '/decisions';
  return url.origin + path + '/v1/decisions';
}

function normalizePayload(payload, model) {
  if (!payload || !payload.questions || typeof payload.questions !== 'object') {
    throw new Error('Expected state and named decision questions');
  }
  const questions = Object.fromEntries(Object.entries(payload.questions).map(([name, question]) => {
    const instructions = typeof question.instructions === 'string'
      ? question.instructions : JSON.stringify(question.instructions ?? '');
    const rawChoices = question.criteria ?? question.choices;
    const normalized = { ...question, instructions };
    if (question.type === 'choice' && rawChoices && !Array.isArray(rawChoices)) {
      normalized.criteria = Object.fromEntries(
        Object.entries(rawChoices).map(([key, value]) => [
          key, typeof value === 'string' ? value : JSON.stringify(value),
        ])
      );
      delete normalized.choices;
    }
    return [name, normalized];
  }));
  return { ...payload, model, questions };
}

export async function requestDecision(payload, options = {}) {
  const {
    mockHandler = null,
    validateResult = null,
    timeoutMs = 25000,
    fetcher = fetch,
    gatewayUrl = process.env.PAG_BASE_URL || DEFAULT_BASE_URL,
    apiKey = process.env.PAG_API_KEY,
    model = process.env.PAG_DECISION_MODEL || 'decision',
  } = options;

  const start = performance.now();
  if (mockHandler) {
    const result = await mockHandler(payload);
    if (validateResult) validateResult(result);
    return { result, provider: 'mock', model: 'mock', latency_ms: Math.round(performance.now() - start) };
  }
  if (!apiKey || typeof apiKey !== 'string') {
    throw new Error('PAG_API_KEY is required. Configure and start Personal AI Gateway first.');
  }
  const url = decisionsEndpoint(gatewayUrl);
  const body = normalizePayload(payload, model);
  const response = await fetcher(url, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(Math.max(100, Math.floor(timeoutMs))),
  });
  if (!response.ok) {
    let detail = '';
    try {
      const problem = await response.json();
      detail = typeof problem?.error === 'string' ? problem.error
        : typeof problem?.error?.message === 'string' ? problem.error.message : '';
    } catch { /* Error responses need not be JSON. */ }
    throw new Error('PAG Decisions HTTP ' + response.status + (detail ? ': ' + detail.slice(0, 300) : ''));
  }
  const result = await response.json();
  if (!result || !result.answers || Array.isArray(result.answers)) {
    throw new Error('Unexpected PAG Decisions response: expected named answers');
  }
  if (validateResult) validateResult(result);
  return {
    result,
    provider: response.headers.get('x-pag-provider') || 'pag',
    model: response.headers.get('x-pag-model') || result.model || model,
    latency_ms: Math.round(performance.now() - start),
  };
}
