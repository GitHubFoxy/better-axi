#!/usr/bin/env node
/**
 * CLI Runner for better-axi workflows.
 */

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = join(__dirname, '../..');
const pythonBin = join(rootDir, '.venv/bin/python');

const [command, ...args] = process.argv.slice(2);

function runPython(moduleArgs) {
  const proc = spawn(pythonBin, moduleArgs, {
    cwd: rootDir,
    stdio: 'inherit',
    env: process.env,
  });
  proc.on('close', (code) => {
    process.exit(code ?? 0);
  });
}

switch (command) {
  case 'classify':
    import('../agent/classifier.mjs').then(({ classifyItems }) => {
      let input = '';
      process.stdin.on('data', (d) => { input += d; });
      process.stdin.on('end', async () => {
        try {
          const { items, criteria, options } = JSON.parse(input);
          const result = await classifyItems(items, criteria, options);
          console.log(JSON.stringify(result));
        } catch (e) {
          console.error(e);
          process.exit(1);
        }
      });
    });
    break;

  case 'job-search':
    runPython(['-m', 'core.workflows.job_search', ...args]);
    break;
  case 'ozon-buyer':
    runPython(['-m', 'core.workflows.ozon_buyer', ...args]);
    break;
  case 'extract':
    runPython(['-m', 'core.extractor.bridge', ...args]);
    break;
  default:
    console.log(`better-axi CLI
Usage:
  node core/workflows/runner.mjs job-search [options]
  node core/workflows/runner.mjs ozon-buyer [options]
  node core/workflows/runner.mjs extract [options]
`);
    process.exit(0);
}
