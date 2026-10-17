import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';

const runner = fileURLToPath(new URL('../core/workflows/runner.mjs', import.meta.url));

test('workflow classification executes over a real local PAG HTTP endpoint', async () => {
  const observed = [];
  const server = createServer(async (req, res) => {
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/v1/decisions');
    assert.equal(req.headers.authorization, 'Bearer pag_integration_key');
    let input = '';
    for await (const chunk of req) input += chunk;
    const data = JSON.parse(input);
    observed.push(data);
    const answers = Object.fromEntries(Object.keys(data.questions).map(id =>
      [id, { type: 'choice', choice: 'FIT', confidence: 0.95 }]
    ));
    res.writeHead(200, { 'content-type': 'application/json', 'x-pag-provider': 'local-stub' });
    res.end(JSON.stringify({ model: 'decision', answers }));
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  try {
    const port = server.address().port;
    const child = spawn(process.execPath, [runner, 'classify'], {
      env: { ...process.env, PAG_BASE_URL: 'http://127.0.0.1:' + port + '/v1',
        PAG_API_KEY: 'pag_integration_key', PAG_DECISION_MODEL: 'decision' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '', stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.stdin.end(JSON.stringify({ items: [{ id: '1', title: 'Backend Engineer', snippet: 'Node.js' }],
      criteria: 'backend' }));
    const [exitCode] = await once(child, 'close');
    assert.equal(exitCode, 0, stderr);
    const response = JSON.parse(stdout);
    assert.equal(response.fit.length, 1);
    assert.equal(response.fit[0].id, '1');
    assert.equal(observed.length, 1);
    assert.equal(observed[0].model, 'decision');
    assert.equal(observed[0].questions.item_0.instructions.includes('Classify'), true);
  } finally {
    server.close();
  }
});
