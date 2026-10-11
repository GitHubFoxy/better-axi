import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyItems, CLASSIFICATION_CHOICES } from '../core/jev/classifier.mjs';

test('classifyItems categorizes items into Fit / 50-50 / Bad', async () => {
  const items = [
    { id: '1', title: 'Senior Backend Python Developer', snippet: 'FastAPI, PostgreSQL' },
    { id: '2', title: '1C Programmer', snippet: 'Configuration 1C' },
    { id: '3', title: 'Go / Python Engineer', snippet: 'Distributed microservices' },
  ];

  const mockHandler = async (payload) => {
    return {
      answers: {
        item_0: { choice: 'FIT', confidence: 0.95 },
        item_1: { choice: 'SKIP', confidence: 0.99 },
        item_2: { choice: 'REVIEW', confidence: 0.70 },
      },
      usage: { cost: 0.001 },
    };
  };

  const res = await classifyItems(items, 'Looking for Python/Go backend developer', {
    mockHandler,
    batchSize: 5,
  });

  assert.equal(res.results.length, 3);
  assert.equal(res.fit.length, 1);
  assert.equal(res.fit[0].id, '1');
  assert.equal(res.fit[0].decision, 'Fit');

  assert.equal(res.bad.length, 1);
  assert.equal(res.bad[0].id, '2');
  assert.equal(res.bad[0].decision, 'Bad');

  assert.equal(res.review.length, 1);
  assert.equal(res.review[0].id, '3');
  assert.equal(res.review[0].decision, '50-50');

  assert.equal(res.passed.length, 2);
  assert.equal(res.calls, 1);
  assert.equal(res.cost_usd, 0.001);
});

test('classifyItems batches properly when items exceed batchSize', async () => {
  const items = Array.from({ length: 7 }, (_, i) => ({
    id: `item_${i}`,
    title: `Vacancy ${i}`,
  }));

  let calls = 0;
  const mockHandler = async (payload) => {
    calls++;
    const answers = {};
    payload.state.items.forEach((_, idx) => {
      answers[`item_${idx}`] = { choice: 'FIT', confidence: 0.9 };
    });
    return { answers, usage: { cost: 0.0005 } };
  };

  const res = await classifyItems(items, 'Criteria', { mockHandler, batchSize: 3 });
  assert.equal(calls, 3); // 3 batches: 3 + 3 + 1
  assert.equal(res.results.length, 7);
  assert.equal(res.fit.length, 7);
});
