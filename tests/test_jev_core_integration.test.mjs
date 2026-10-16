import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createJevServer } from 'jev-core/server';
import { runNavigationLoop } from '../core/navigation/loop.mjs';
import { classifyItems } from '../core/classification/classifier.mjs';

test('Better AXI nav and classify use standalone Jev Core over HTTP', async () => {
  const server = createJevServer({
    apiKey: 'test-better-axi',
    env: { OPENROUTER_API_KEY: 'test-upstream' },
    fetchImpl: async (_url, options) => {
      const request = JSON.parse(options.body);
      let answers;
      if (request.questions.operation) {
        answers = request.state.page.text.includes('Results')
          ? { operation: { choice: 'DONE' } }
          : { operation: { choice: 'TYPE_TEXT' }, type_text_target: { choice: 'FILL:1' } };
      } else {
        answers = Object.fromEntries(
          Object.keys(request.questions).map((name) => [name, { choice: 'FIT' }])
        );
      }
      return { ok: true, json: async () => ({ answers }) };
    },
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const savedUrl = process.env.JEV_CORE_URL;
  const savedKey = process.env.JEV_CORE_API_KEY;
  process.env.JEV_CORE_URL = 'http://127.0.0.1:' + server.address().port;
  process.env.JEV_CORE_API_KEY = 'test-better-axi';
  try {
    let current = 'uid=1 textbox "Search"';
    const page = {
      snapshot: async () => current,
      fill: async (_uid, value) => {
        assert.equal(value, 'backend');
        current = 'uid=3 heading "Results"';
      },
    };
    const result = await runNavigationLoop(page, {
      goal: 'Search', fields: { Search: 'backend' },
    });
    assert.equal(result.status, 'done');
    assert.equal(result.decisions[0].provider, 'openrouter');

    const classification = await classifyItems([
      { id: '1', title: 'Backend engineer' },
    ], 'backend', { batchSize: 5 });
    assert.equal(classification.fit.length, 1);
    assert.equal(classification.fit[0].id, '1');
  } finally {
    if (savedUrl === undefined) delete process.env.JEV_CORE_URL;
    else process.env.JEV_CORE_URL = savedUrl;
    if (savedKey === undefined) delete process.env.JEV_CORE_API_KEY;
    else process.env.JEV_CORE_API_KEY = savedKey;
    await new Promise((resolve) => server.close(resolve));
  }
});
