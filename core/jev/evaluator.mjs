/**
 * Detailed Evaluator (Eval 2) and Cover Letter Generator for Jev.
 * Performs in-depth vacancy analysis, screens for hidden employer requirements
 * (e.g., "start cover letter with LOL"), and drafts customized responses.
 */

export function detectSpecialConditions(text) {
  if (!text || typeof text !== 'string') {
    return { hasCondition: false, prefix: null, instruction: null };
  }

  // Regex patterns for easter eggs / secret words in Russian and English
  const patterns = [
    /начните\s+(?:свое\s+|свой\s+)?(?:сопроводительное\s+письмо|отклик|письмо)\s+(?:со\s+слов[а-я]*|с\s+фразы|со\s+слова)?\s*[:«"'\s]+([A-Za-zА-Яа-я0-9_-]+)/i,
    /в\s+начале\s+(?:сопроводительного\s+письма|отклика|письма)\s+(?:напишите|укажите)\s*(?:кодовое\s+слово)?\s*[:«"'\s]+([A-Za-zА-Яа-я0-9_-]+)/i,
    /start\s+(?:your\s+)?(?:cover\s+letter|application|response)\s+with\s+(?:the\s+word\s+)?['"«\s]?([A-Za-z0-9_-]+)/i,
    /(?:кодовое\s+слово|секретное\s+слово|код\s+для\s+отклика)\s*[:—–-]\s*['"«\s]?([A-Za-zА-Яа-я0-9_-]+)/i,
    /(?:secret\s+word|secret\s+code|screening\s+word)\s*[:—–-]\s*['"«\s]?([A-Za-z0-9_-]+)/i,
  ];

  for (const pat of patterns) {
    const match = text.match(pat);
    if (match && match[1]) {
      const keyword = match[1].replace(/['"»«\.,]/g, '').trim();
      if (keyword.length >= 2 && !/^(?:слов|слова|письма|отклика)$/i.test(keyword)) {
        return {
          hasCondition: true,
          prefix: keyword,
          instruction: match[0].trim(),
        };
      }
    }
  }

  return { hasCondition: false, prefix: null, instruction: null };
}

export function evaluateDeepMatch(vacancy, candidate) {
  const text = `${vacancy.title} ${vacancy.description || ''} ${vacancy.snippet || ''} ${(vacancy.skills || []).join(' ')}`.toLowerCase();
  const candidateSkills = (candidate.skills || ['Python', 'Go', 'FastAPI', 'PostgreSQL', 'Docker', 'Redis', 'Kafka', 'Asyncio']).map(s => s.toLowerCase());

  let matchedSkills = 0;
  for (const skill of candidateSkills) {
    if (text.includes(skill)) matchedSkills++;
  }

  const skillScore = Math.min(60, Math.round((matchedSkills / Math.max(3, candidateSkills.length)) * 60));
  
  // Experience match
  let expScore = 20;
  if (/senior|lead|руководитель|тимлид/i.test(vacancy.title) && !candidate.isSenior) {
    expScore = 5;
  } else if (/1[-–]3|от\s*1\s*года/i.test(vacancy.experience || text)) {
    expScore = 20;
  }

  // Work format bonus (remote / hybrid)
  let formatScore = 15;
  if (/удален|remote|гибрид|hybrid/i.test(text)) {
    formatScore = 20;
  }

  const totalScore = Math.min(100, skillScore + expScore + formatScore);

  const condition = detectSpecialConditions(vacancy.description || vacancy.fit_markdown || vacancy.snippet || '');

  return {
    id: vacancy.id,
    title: vacancy.title,
    employer: vacancy.employer,
    score: totalScore,
    matchedSkillsCount: matchedSkills,
    specialCondition: condition,
    recommendation: totalScore >= 70 ? 'APPLY_STRONG' : totalScore >= 50 ? 'APPLY_MODERATE' : 'CONSIDER_SKIP',
  };
}

export function draftCoverLetter(vacancy, candidate, specialCondition = null) {
  const cond = specialCondition || detectSpecialConditions(vacancy.description || vacancy.fit_markdown || '');
  const prefixPart = cond.hasCondition && cond.prefix ? `${cond.prefix}, ` : '';

  const candidateName = candidate.name || 'Александр';
  const candidateExperience = candidate.experienceSummary || '2 года коммерческой разработки на Python и Go (FastAPI, PostgreSQL, Redis, Docker)';

  const letter = [
    `${prefixPart}Добрый день!`,
    '',
    `Меня зовут ${candidateName}, меня очень заинтересовала вакансия «${vacancy.title}» в компании ${vacancy.employer || 'вашей компании'}.`,
    '',
    `Мой профиль и опыт: ${candidateExperience}. Имею опыт проектирования масштабируемых API, работы с реляционными базами данных, оптимизации запросов и контейнеризации сервисов.`,
    '',
    'Буду рад обсудить задачи команды и детали сотрудничества на интервью.',
    '',
    'С уважением,',
    candidateName,
  ].join('\n');

  return {
    text: letter,
    specialConditionFollowed: cond.hasCondition,
    prefixApplied: cond.prefix,
  };
}
