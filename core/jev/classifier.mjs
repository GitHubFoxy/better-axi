/**
 * Fast Jev Classifier for web navigation, filtering, and job candidate match.
 * Evaluates titles/snippets into Fit / 50-50 / Bad.
 */

import { requestDecision, validateChoice } from './decision_client.mjs';

export const CLASSIFICATION_CHOICES = {
  FIT: 'Fit: Strong match with criteria, key requirements and skills aligned.',
  REVIEW: '50-50: Borderline match or missing specific details, needs deep page review.',
  SKIP: 'Bad: Clear mismatch, wrong tech stack, experience mismatch, or irrelevant.',
};

export async function classifyItems(items, criteria, options = {}) {
  const { batchSize = 5, mockHandler = null, timeoutMs = 25000 } = options;

  if (!Array.isArray(items)) throw new Error('items must be an array');
  if (typeof criteria !== 'string' || !criteria.trim()) {
    throw new Error('criteria must be a non-empty string');
  }

  const results = [];
  const batches = [];
  for (let i = 0; i < items.length; i += batchSize) {
    batches.push(items.slice(i, i + batchSize));
  }

  let totalCost = 0;
  let totalCalls = 0;

  for (const batch of batches) {
    const questions = Object.fromEntries(
      batch.map((item, index) => [
        `item_${index}`,
        {
          type: 'choice',
          criteria: CLASSIFICATION_CHOICES,
          instructions: {
            id: item.id || String(index),
            title: item.title,
            snippet: item.snippet || item.description || '',
            rules:
              'Classify this item against criteria strictly based on facts. Do not invent missing facts. Use FIT for clear match, REVIEW for 50-50/borderline, and SKIP for bad match.',
          },
        },
      ])
    );

    const decisionResponse = await requestDecision(
      {
        state: { criteria, items: batch },
        questions,
      },
      {
        timeoutMs,
        mockHandler,
        validateResult: (res) => {
          batch.forEach((_, idx) => {
            const ans = res.answers?.[`item_${idx}`];
            validateChoice(ans, CLASSIFICATION_CHOICES);
          });
        },
      }
    );

    totalCalls++;
    const res = decisionResponse.result;
    totalCost += Number(res.usage?.cost ?? res.cost_usd ?? 0);

    batch.forEach((item, idx) => {
      const answer = res.answers?.[`item_${idx}`];
      const choice = validateChoice(answer, CLASSIFICATION_CHOICES);
      const confidence =
        typeof answer?.confidence === 'number' && Number.isFinite(answer.confidence)
          ? answer.confidence
          : (choice === 'FIT' ? 0.9 : choice === 'REVIEW' ? 0.6 : 0.2);

      // Normalize label to Fit / 50-50 / Bad
      const label = choice === 'FIT' ? 'Fit' : choice === 'REVIEW' ? '50-50' : 'Bad';

      results.push({
        id: item.id,
        title: item.title,
        url: item.url,
        decision: label,
        choice,
        confidence,
        reason: answer?.reason || `Classified as ${label} against search criteria`,
      });
    });
  }

  return {
    results,
    fit: results.filter((r) => r.decision === 'Fit'),
    review: results.filter((r) => r.decision === '50-50'),
    bad: results.filter((r) => r.decision === 'Bad'),
    passed: results.filter((r) => r.decision === 'Fit' || r.decision === '50-50'),
    calls: totalCalls,
    cost_usd: totalCost,
  };
}
