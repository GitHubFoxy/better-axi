from pathlib import Path
import pytest
from core.workflows.job_search import JobSearchWorkflow

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.mark.asyncio
async def test_job_search_workflow_end_to_end():
    search_html = (FIXTURES_DIR / "hh_search_page.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "hh_vacancy_page.html").read_text(encoding="utf-8")

    applied_jobs = []
    def mock_apply(vac_id, letter):
        applied_jobs.append((vac_id, letter))
        return {"status": "applied", "vac_id": vac_id}

    workflow = JobSearchWorkflow(page_action_fn=mock_apply)

    result = await workflow.run(
        query="backend",
        experience="1-3 years",
        candidate_profile={
            "name": "Александр",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
            "summary": "2 года бэкенд разработки на Python/FastAPI",
        },
        mock_search_html=search_html,
        mock_detail_htmls={"10101001": detail_html},
        auto_apply=True,
    )

    assert result["status"] == "success"
    assert result["total_extracted"] == 3
    # Eval 1 passed 2 jobs (Python & Go), skipped 1C
    assert result["eval_1_passed"] == 2
    assert result["eval_1_breakdown"]["bad"] == 1

    # Top vacancy should be Python FastAPI (10101001)
    top = result["top_vacancy"]
    assert top is not None
    assert top["vacancy_id"] == "10101001"
    assert top["score"] >= 80

    # Screening Easter egg "LOL" must be detected and used in cover letter!
    assert top["special_condition"]["has_condition"] is True
    assert top["special_condition"]["prefix"] == "LOL"
    assert top["cover_letter"].startswith("LOL, Добрый день!")

    # Apply action should have executed
    assert result["applied"] is True
    assert len(applied_jobs) == 1
    assert applied_jobs[0][0] == "10101001"
    assert "LOL, Добрый день!" in applied_jobs[0][1]
