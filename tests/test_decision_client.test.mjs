import test from 'node:test';
import assert from 'node:assert/strict';
import { requestDecision, validateChoice } from 'jev-core';

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

test('requestDecision requires Jev Core client API key', async () => {
  const originalKey = process.env.JEV_CORE_API_KEY;
  delete process.env.JEV_CORE_API_KEY;

  try {
    await assert.rejects(
      async () => {
        await requestDecision({ state: {}, questions: {} });
      },
      /JEV_CORE_API_KEY is required/
    );
  } finally {
    if (originalKey === undefined) delete process.env.JEV_CORE_API_KEY;
    else process.env.JEV_CORE_API_KEY = originalKey;
  }
});
