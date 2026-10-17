import test from 'node:test';
import assert from 'node:assert/strict';
import { requestDecision, validateChoice, decisionsEndpoint } from '../core/pag/client.mjs';

const payload = {
  state: { role: 'backend' },
  questions: {
    match: {
      type: 'choice',
      criteria: { FIT: 'Good', SKIP: 'Bad' },
      instructions: { rules: 'Do not guess' },
    },
  },
};

test('validateChoice rejects non-member decisions', () => {
  assert.equal(validateChoice({ choice: 'FIT' }, { FIT: 'Good' }), 'FIT');
  assert.throws(() => validateChoice({ choice: 'wrong' }, { FIT: 'Good' }));
  assert.throws(() => validateChoice(null, { FIT: 'Good' }));
});

test('PAG endpoint normalization and HTTPS for remote gateways', () => {
  assert.equal(decisionsEndpoint('http://127.0.0.1:4000'), 'http://127.0.0.1:4000/v1/decisions');
  assert.equal(decisionsEndpoint('http://127.0.0.1:4000/v1'), 'http://127.0.0.1:4000/v1/decisions');
  assert.equal(decisionsEndpoint('https://pag.example.com/v1'), 'https://pag.example.com/v1/decisions');
  assert.throws(() => decisionsEndpoint('http://pag.example.com/v1'), /HTTPS/);
});

test('PAG adapter sends normalized System One questions with the gateway token', async () => {
  let called = 0;
  const answer = await requestDecision(payload, {
    gatewayUrl: 'http://127.0.0.1:4000/v1',
    apiKey: 'pag_test_key',
    model: 'decision',
    fetcher: async (url, opts) => {
      called++;
      assert.equal(url, 'http://127.0.0.1:4000/v1/decisions');
      assert.equal(opts.headers.Authorization, 'Bearer pag_test_key');
      const body = JSON.parse(opts.body);
      assert.equal(body.model, 'decision');
      assert.equal(body.questions.match.instructions, '{"rules":"Do not guess"}');
      assert.deepEqual(body.questions.match.criteria, { FIT: 'Good', SKIP: 'Bad' });
      return new Response(JSON.stringify({ model: 'decision', answers: { match: { choice: 'FIT' } } }), {
        headers: { 'content-type': 'application/json', 'x-pag-provider': 'vercel-dc', 'x-pag-model': 'laya' },
      });
    },
    validateResult: result => validateChoice(result.answers.match, payload.questions.match.criteria),
  });
  assert.equal(called, 1);
  assert.equal(answer.result.answers.match.choice, 'FIT');
  assert.equal(answer.provider, 'vercel-dc');
  assert.equal(answer.model, 'laya');
});

test('mock decisions require no key or live PAG process', async () => {
  const res = await requestDecision(payload, {
    apiKey: undefined,
    mockHandler: async () => ({ answers: { match: { choice: 'SKIP' } } }),
  });
  assert.equal(res.provider, 'mock');
  assert.equal(res.result.answers.match.choice, 'SKIP');
});

test('missing PAG key fails before HTTP', async () => {
  await assert.rejects(requestDecision(payload, { apiKey: '' }), /PAG_API_KEY is required/);
});

test('PAG adapter never retries providers itself', async () => {
  let calls = 0;
  await assert.rejects(requestDecision(payload, {
    apiKey: 'pag_key',
    fetcher: async () => {
      calls++;
      return new Response(JSON.stringify({ error: 'No upstream route completed successfully' }), {
        status: 503, headers: { 'content-type': 'application/json' },
      });
    },
  }), /PAG Decisions HTTP 503/);
  assert.equal(calls, 1);
});
