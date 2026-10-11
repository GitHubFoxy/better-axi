import test from 'node:test';
import assert from 'node:assert/strict';
import { requestDecision, validateChoice } from '../core/jev/decision_client.mjs';

test('validateChoice validates choice membership', () => {
  const criteria = { FIT: 'Good', SKIP: 'Bad' };
  assert.equal(validateChoice({ choice: 'FIT' }, criteria), 'FIT');
  assert.throws(() => validateChoice({ choice: 'UNKNOWN' }, criteria));
  assert.throws(() => validateChoice(null, criteria));
});

test('requestDecision uses mockHandler when provided', async () => {
  const mockPayload = { state: {}, questions: {} };
  const mockResponse = { answers: { opt: { choice: 'TEST' } } };

  const res = await requestDecision(mockPayload, {
    mockHandler: async () => mockResponse,
  });

  assert.equal(res.provider, 'mock');
  assert.deepEqual(res.result, mockResponse);
});

test('requestDecision throws error if no provider or keys present', async () => {
  const originalEnv = { ...process.env };
  delete process.env.OPENROUTER_API_KEY;
  delete process.env.AI_GATEWAY_API_KEY;
  delete process.env.CLOUDFLARE_API_TOKEN;

  try {
    await assert.rejects(
      async () => {
        await requestDecision({ state: {}, questions: {} });
      },
      /No decision provider configured/
    );
  } finally {
    Object.assign(process.env, originalEnv);
  }
});
