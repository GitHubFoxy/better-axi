"""
Job Search Workflow (hh.ru) uniting AXI, Jev, and Crawl4AI.
1. Nav: Open hh.ru, search "backend", apply experience filter "1-3 years".
2. Extract: Extract listed vacancies into structured records via Crawl4AI.
3. Eval 1: Jev evaluates titles/snippets into Fit / 50-50 / Bad.
4. Batch Deep Extract: Crawl4AI extracts full descriptions for valid vacancies.
5. Eval 2: Jev/LLM detailed scoring, special screening check, draft response.
6. Apply: Jev/AXI navigates to best vacancy, triggers apply, enters cover letter.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable, Dict, List, Optional

from core.extractor.bridge import Crawl4AIBridge
from core.extractor.schemas import HHVacancyRecord


class JobSearchWorkflow:
    """Executes end-to-end HH.ru job search, evaluation, and application flow."""

    def __init__(
        self,
        extractor: Optional[Crawl4AIBridge] = None,
        classifier_fn: Optional[Callable[[List[Dict[str, Any]], str], Dict[str, Any]]] = None,
        page_action_fn: Optional[Callable[[str, str], Any]] = None,
    ):
        self.extractor = extractor or Crawl4AIBridge()
        self.classifier_fn = classifier_fn
        self.page_action_fn = page_action_fn

    def build_search_url(self, query: str = "backend", experience: str = "1-3 years") -> str:
        """Construct HH search URL with query and experience parameters."""
        exp_code = "between1And3" if "1" in experience and "3" in experience else "noExperience"
        return f"https://hh.ru/search/vacancy?text={query}&experience={exp_code}&order_by=relevance"

    def default_classify(self, items: List[Dict[str, Any]], criteria: str) -> Dict[str, Any]:
        """Heuristic or rule-based fallback classifier if no external LLM mock is supplied."""
        results = []
        for item in items:
            text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
            if any(bad in text for bad in ["1с", "1c", "php", "стажер", "team lead", "руководитель"]):
                label = "Bad"
                choice = "SKIP"
                conf = 0.85
            elif any(good in text for good in ["python", "fastapi", "django"]):
                label = "Fit"
                choice = "FIT"
                conf = 0.90
            elif any(rev in text for rev in ["go", "golang", "backend", "бэкенд"]):
                label = "50-50"
                choice = "REVIEW"
                conf = 0.65
            else:
                label = "50-50"
                choice = "REVIEW"
                conf = 0.50

            results.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "url": item.get("url"),
                "decision": label,
                "choice": choice,
                "confidence": conf,
            })

        return {
            "results": results,
            "passed": [r for r in results if r["decision"] in ("Fit", "50-50")],
            "fit": [r for r in results if r["decision"] == "Fit"],
            "review": [r for r in results if r["decision"] == "50-50"],
            "bad": [r for r in results if r["decision"] == "Bad"],
        }

    def detect_special_conditions(self, text: str) -> Dict[str, Any]:
        """Check for secret recruiter instructions like 'start cover letter with LOL'."""
        patterns = [
            r'начните\s+(?:свое\s+|свой\s+)?(?:сопроводительное\s+письмо|отклик|письмо)\s+(?:со\s+слов[а-я]*|с\s+фразы|со\s+слова)?\s*[:«"\'\s]+([A-Za-zА-Яа-я0-9_-]+)',
            r'в\s+начале\s+(?:сопроводительного\s+письма|отклика|письма)\s+(?:напишите|укажите)\s*(?:кодовое\s+слово)?\s*[:«"\'\s]+([A-Za-zА-Яа-я0-9_-]+)',
            r'start\s+(?:your\s+)?(?:cover\s+letter|application|response)\s+with\s+(?:the\s+word\s+)?[\'\"«\s]?([A-Za-z0-9_-]+)',
            r'(?:кодовое\s+слово|секретное\s+слово)\s*[:—–-]\s*[\'\"«\s]?([A-Za-zА-Яа-я0-9_-]+)',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                word = m.group(1).strip('\'":«».,')
                if len(word) >= 2 and word.lower() not in ("слов", "слова", "письма", "отклика"):
                    return {"has_condition": True, "prefix": word, "instruction": m.group(0)}
        return {"has_condition": False, "prefix": None, "instruction": None}

    def evaluate_deep(self, vacancy: HHVacancyRecord, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Deep evaluation of vacancy details against candidate profile."""
        full_text = f"{vacancy.title} {vacancy.description or ''} {vacancy.snippet or ''} {' '.join(vacancy.skills)}".lower()
        skills = [s.lower() for s in candidate.get("skills", ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"])]

        matches = sum(1 for s in skills if s in full_text)
        score = min(100, int((matches / max(1, len(skills))) * 70) + 30)

        special = self.detect_special_conditions(vacancy.description or vacancy.fit_markdown or "")
        
        # Draft tailored cover letter
        prefix = f"{special['prefix']}, " if special["has_condition"] and special["prefix"] else ""
        name = candidate.get("name", "Александр")
        cover_letter = (
            f"{prefix}Добрый день!\n\n"
            f"Меня зовут {name}. Меня очень заинтересовала вакансия «{vacancy.title}» в компании {vacancy.employer or 'вашей компании'}.\n\n"
            f"Мой стек и опыт: {candidate.get('summary', '2 года разработки backend-сервисов на Python/Go, PostgreSQL, Docker')}. "
            f"Готов оперативно выполнить тестовое задание или обсудить детали на интервью.\n\n"
            f"С уважением,\n{name}"
        )

        return {
            "vacancy_id": vacancy.id,
            "title": vacancy.title,
            "employer": vacancy.employer,
            "score": score,
            "special_condition": special,
            "cover_letter": cover_letter,
        }

    async def run(
        self,
        query: str = "backend",
        experience: str = "1-3 years",
        candidate_profile: Optional[Dict[str, Any]] = None,
        mock_search_html: Optional[str] = None,
        mock_detail_htmls: Optional[Dict[str, str]] = None,
        auto_apply: bool = False,
    ) -> Dict[str, Any]:
        """Execute the job search pipeline."""
        candidate = candidate_profile or {
            "name": "Александр",
            "skills": ["Python", "Go", "FastAPI", "PostgreSQL", "Docker", "Redis"],
            "summary": "2 года разработки высоконагруженных бэкенд-сервисов",
        }

        # Step 1: Nav
        search_url = self.build_search_url(query, experience)

        # Step 2: Extract search vacancies
        if mock_search_html:
            vacancies = self.extractor.parse_hh_search_html(mock_search_html)
        else:
            crawl_res = await self.extractor.crawl_url(search_url)
            vacancies = self.extractor.parse_hh_search_html(crawl_res.get("html", ""))

        if not vacancies:
            return {"status": "empty", "vacancies_found": 0, "message": "No vacancies found."}

        # Step 3: Eval 1 (Jev Fast Filter)
        criteria = f"Backend developer position matching {candidate['skills']} with experience 1-3 years."
        items_payload = [v.model_dump() for v in vacancies]
        classify_res = self.classifier_fn(items_payload, criteria) if self.classifier_fn else self.default_classify(items_payload, criteria)

        passed_ids = {r["id"] for r in classify_res.get("passed", [])}
        filtered_vacancies = [v for v in vacancies if v.id in passed_ids]

        # Step 4: Batch Deep Extract (Parallel extraction of full vacancy details)
        detailed_vacancies: List[HHVacancyRecord] = []
        if mock_detail_htmls:
            for v in filtered_vacancies:
                detail = self.extractor.parse_hh_vacancy_detail_html(mock_detail_htmls.get(v.id, ''), base_record=v) if v.id in mock_detail_htmls else v
                detailed_vacancies.append(detail)
        else:
            # Live crawl_batch for full descriptions
            urls_to_fetch = [v.url for v in filtered_vacancies if v.url and v.url.startswith('http')]
            if urls_to_fetch:
                try:
                    crawled_pages = await self.extractor.crawl_batch(urls_to_fetch)
                    page_map = {p.get('url'): p.get('html', '') for p in crawled_pages if p.get('url')}
                    for v in filtered_vacancies:
                        html = page_map.get(v.url)
                        detail = self.extractor.parse_hh_vacancy_detail_html(html, base_record=v) if html else v
                        detailed_vacancies.append(detail)
                except Exception:
                    detailed_vacancies = filtered_vacancies
            else:
                detailed_vacancies = filtered_vacancies

        # Step 5: Eval 2 (Detailed scoring & cover letter generation)
        evaluations = [self.evaluate_deep(v, candidate) for v in detailed_vacancies]
        evaluations.sort(key=lambda e: e["score"], reverse=True)

        winner = evaluations[0] if evaluations else None

        # Step 6: Apply
        apply_result = None
        if winner and auto_apply and self.page_action_fn:
            apply_result = self.page_action_fn(winner["vacancy_id"], winner["cover_letter"])

        return {
            "status": "success",
            "total_extracted": len(vacancies),
            "eval_1_passed": len(filtered_vacancies),
            "eval_1_breakdown": {
                "fit": len(classify_res.get("fit", [])),
                "review": len(classify_res.get("review", [])),
                "bad": len(classify_res.get("bad", [])),
            },
            "evaluations": evaluations,
            "top_vacancy": winner,
            "applied": apply_result is not None,
            "apply_result": apply_result,
        }


if __name__ == '__main__':
    import sys
    workflow = JobSearchWorkflow()
    query = sys.argv[1] if len(sys.argv) > 1 else 'backend'
    exp = sys.argv[2] if len(sys.argv) > 2 else '1-3 years'
    res = asyncio.run(workflow.run(query=query, experience=exp))
    print(json.dumps(res, ensure_ascii=False, indent=2))
