/**
 * Multi-provider Decision Client for Jev.
 * Supports:
 * - OpenRouter Decisions API (~typesafe/jev-latest)
 * - Vercel AI Gateway (convaiinnovations/laya)
 * - Cloudflare Workers AI (@cf/cloudflare/clef)
 * - In-memory Mock Provider (for deterministic testing & offline mode)
 */

import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// Load .env automatically if present
const localEnv = fileURLToPath(new URL('./.env', import.meta.url));
if (existsSync(localEnv)) process.loadEnvFile(localEnv);

export function validateChoice(answer, criteria) {
  if (!answer || !Object.hasOwn(criteria, answer.choice)) {
    throw new Error(`Jev chose an invalid or missing choice: "${answer?.choice}"`);
  }
  return answer.choice;
}

function instructionText(instructions) {
  if (typeof instructions === 'string') return instructions;
  if (!instructions || typeof instructions !== 'object') return String(instructions ?? '');
  return Object.entries(instructions)
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join('\n');
}

function gatewayQuestions(questions) {
  return Object.fromEntries(
    Object.entries(questions).map(([name, question]) => [
      name,
      {
        ...question,
        instructions: instructionText(question.instructions),
      },
    ])
  );
}

export async function requestDecision(payload, options = {}) {
  const {
    timeoutMs = 25000,
    mockHandler = null,
    validateResult = null,
  } = options;

  // 1. Check Mock Handler first (used for deterministic unit tests)
  if (mockHandler) {
    const start = performance.now();
    const result = await mockHandler(payload);
    if (validateResult) validateResult(result);
    return {
      result,
      provider: 'mock',
      model: 'mock-jev',
      latency_ms: Math.round(performance.now() - start),
    };
  }

  // 2. Build provider chain
  const providers = [];
  if (process.env.OPENROUTER_API_KEY) {
    providers.push({
      name: 'openrouter',
      model: '~typesafe/jev-latest',
      url: 'https://openrouter.ai/api/alpha/decisions',
      token: process.env.OPENROUTER_API_KEY,
      body: { ...payload, model: '~typesafe/jev-latest' },
    });
  }

  if (process.env.AI_GATEWAY_API_KEY) {
    const gatewayBody = {
      ...payload,
      model: process.env.AI_GATEWAY_MODEL || 'convaiinnovations/laya',
      questions: gatewayQuestions(payload.questions),
    };
    if (process.env.AI_GATEWAY_PROVIDER) {
      gatewayBody.providerOptions = { gateway: { only: [process.env.AI_GATEWAY_PROVIDER] } };
    }
    providers.push({
      name: 'vercel-gateway',
      model: gatewayBody.model,
      url: 'https://ai-gateway.vercel.sh/v1/evaluate',
      token: process.env.AI_GATEWAY_API_KEY,
      body: gatewayBody,
    });
  }

  if (process.env.CLOUDFLARE_ACCOUNT_ID && process.env.CLOUDFLARE_API_TOKEN) {
    const model = process.env.CLOUDFLARE_AI_MODEL || '@cf/cloudflare/clef';
    providers.push({
      name: 'cloudflare',
      model,
      url: `https://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(
        process.env.CLOUDFLARE_ACCOUNT_ID
      )}/ai/run/${model}`,
      token: process.env.CLOUDFLARE_API_TOKEN,
      body: {
        ...payload,
        model: model.split('/').at(-1),
        questions: gatewayQuestions(payload.questions),
      },
    });
  }

  if (!providers.length) {
    throw new Error(
      'No decision provider configured. Please provide OPENROUTER_API_KEY, AI_GATEWAY_API_KEY, CLOUDFLARE_API_TOKEN, or use mockHandler.'
    );
  }

  const failures = [];
  const deadline = performance.now() + timeoutMs;

  for (const provider of providers) {
    if (performance.now() >= deadline) break;
    const requested = performance.now();
    try {
      const remainingTime = Math.max(100, Math.floor(deadline - performance.now()));
      const response = await fetch(provider.url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${provider.token}`,
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(remainingTime),
        body: JSON.stringify(provider.body),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const rawResult = await response.json();
      const result = provider.parse ? provider.parse(rawResult) : rawResult;

      if (validateResult) validateResult(result);

      return {
        result,
        provider: provider.name,
        model: provider.model,
        latency_ms: Math.round(performance.now() - requested),
      };
    } catch (err) {
      failures.push(`${provider.name}: ${err.message}`);
    }
  }

  throw new Error(`All decision providers failed: ${failures.join('; ')}`);
}
