import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const cliBin = join(__dirname, '..', 'bin', 'better-axi');

test('better-axi CLI: --help outputs usage information', () => {
  const res = spawnSync(cliBin, ['--help'], { encoding: 'utf-8' });
  assert.equal(res.status, 0);
  assert.match(res.stdout, /better-axi — Agentic Browser Building Blocks/);
  assert.match(res.stdout, /nav --goal/);
  assert.match(res.stdout, /extract active/);
  assert.match(res.stdout, /classify --criteria/);
});

test('better-axi CLI: nav without --goal exits with code 1', () => {
  const res = spawnSync(cliBin, ['nav'], { encoding: 'utf-8' });
  assert.equal(res.status, 1);
  assert.match(res.stderr, /--goal is required/);
});

test('better-axi CLI: classify without piped stdin exits with code 1 (no TTY hang)', () => {
  const res = spawnSync(cliBin, ['classify', '--criteria', 'test'], { encoding: 'utf-8' });
  assert.equal(res.status, 1);
  assert.match(res.stderr, /better-axi classify expects JSON array via stdin pipe/);
});

test('better-axi CLI: classify with invalid JSON exits with code 1', () => {
  const res = spawnSync(cliBin, ['classify', '--criteria', 'test'], {
    input: 'invalid json content',
    encoding: 'utf-8',
  });
  assert.equal(res.status, 1);
  assert.match(res.stderr, /Unexpected token|JSON|Error in classify/);
});

test('better-axi CLI: extract batch with no URLs returns empty array', () => {
  const res = spawnSync(cliBin, ['extract', 'batch'], { encoding: 'utf-8' });
  assert.equal(res.status, 0);
  assert.equal(res.stdout.trim(), '[]');
});

test('better-axi CLI: unknown command prints help and exits', () => {
  const res = spawnSync(cliBin, ['unknown_subcmd'], { encoding: 'utf-8' });
  assert.match(res.stderr, /Unknown command: unknown_subcmd/);
});
