import test from 'node:test';
import assert from 'node:assert/strict';
import {
  detectSpecialConditions,
  evaluateDeepMatch,
  draftCoverLetter,
} from '../core/workflows/evaluator.mjs';

test('detectSpecialConditions identifies secret screening words in Russian and English', () => {
  // Russian variations
  const t1 = 'Мы ценим внимание к деталям. Начните сопроводительное письмо со слов LOL.';
  const r1 = detectSpecialConditions(t1);
  assert.equal(r1.hasCondition, true);
  assert.equal(r1.prefix, 'LOL');

  const t2 = 'В начале отклика напишите кодовое слово: REDIS';
  const r2 = detectSpecialConditions(t2);
  assert.equal(r2.hasCondition, true);
  assert.equal(r2.prefix, 'REDIS');

  // English variation
  const t3 = 'To make sure you read this, start your cover letter with the word POTATO.';
  const r3 = detectSpecialConditions(t3);
  assert.equal(r3.hasCondition, true);
  assert.equal(r3.prefix, 'POTATO');

  // Negative test
  const t4 = 'Обычное описание вакансии без скрытых условий и кодовых слов.';
  const r4 = detectSpecialConditions(t4);
  assert.equal(r4.hasCondition, false);
  assert.equal(r4.prefix, null);
});

test('evaluateDeepMatch computes score and recommendation', () => {
  const vacancy = {
    id: '123',
    title: 'Python Backend Developer',
    description: 'Ищем разработчика Python 3.11, FastAPI, PostgreSQL, Redis, Docker. Удаленная работа.',
    skills: ['Python', 'FastAPI', 'PostgreSQL', 'Docker'],
    experience: '1-3 года',
  };

  const candidate = {
    name: 'Александр',
    skills: ['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'Redis'],
    isSenior: false,
  };

  const match = evaluateDeepMatch(vacancy, candidate);
  assert.ok(match.score >= 80, `Expected score >= 80, got ${match.score}`);
  assert.equal(match.recommendation, 'APPLY_STRONG');
});

test('draftCoverLetter attaches prefix if special condition detected', () => {
  const vacancy = {
    title: 'Backend Developer',
    employer: 'SuperTech',
    description: 'Внимание: начните сопроводительное письмо со слов LOL.',
  };
  const candidate = {
    name: 'Александр',
    experienceSummary: '2 года разработки на Python',
  };

  const letter = draftCoverLetter(vacancy, candidate);
  assert.equal(letter.specialConditionFollowed, true);
  assert.equal(letter.prefixApplied, 'LOL');
  assert.ok(letter.text.startsWith('LOL, Добрый день!'));
  assert.ok(letter.text.includes('SuperTech'));
});
