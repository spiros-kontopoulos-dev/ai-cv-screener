"""Endpoint tests for the frozen grounded-chat response contract."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_grounded_answer_generator
from app.cv_answer_generation import (
    GroundedAnswerConfigurationError,
    GroundedAnswerDraft,
    GroundedAnswerGenerationFailed,
    GroundedAnswerGenerationResult,
    GroundedCandidateAnswer,
)
from app.main import app
from cv_retrieval_test_helpers import (
    CandidateSpec,
    build_candidate_result,
    finalize_for_test,
)


class FakeGenerator:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.queries = []

    def generate(self, query):
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.result


def _supported_generation_result() -> GroundedAnswerGenerationResult:
    retrieval = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Eleni Markou",
                    "Senior Python Backend Engineer",
                    matched_count=2,
                    candidate_score=0.91,
                    coverage_score=1.0,
                    evidence_texts=("Python FastAPI PostgreSQL evidence.",),
                ),
            ),
            question="Which candidates know Python and PostgreSQL?",
        )
    )
    draft = GroundedAnswerDraft(
        outcome="supported",
        answer="Eleni Markou has source-backed Python and PostgreSQL experience.",
        answer_citation_ids=["candidate_001-source-1"],
        candidates=[
            GroundedCandidateAnswer(
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                professional_title="Senior Python Backend Engineer",
                assessment="Complete source-backed match.",
                matched_requirements=["python", "postgresql"],
                citation_ids=["candidate_001-source-1"],
            )
        ],
        limitations=[],
    )
    return GroundedAnswerGenerationResult(
        retrieval_result=retrieval,
        draft=draft,
        attempts=0,
        provider_called=False,
        model_name="deterministic-template-v1",
        provider_name="deterministic",
    )


def _unsupported_generation_result() -> GroundedAnswerGenerationResult:
    retrieval = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Eleni Markou",
                    "Senior Python Backend Engineer",
                    matched_count=0,
                    candidate_score=0.1,
                    coverage_score=0.0,
                ),
            ),
            question="Who holds government security clearance?",
            condition_labels=("government", "security", "clearance"),
        )
    )
    draft = GroundedAnswerDraft(
        outcome="unsupported",
        answer="No sufficiently supported candidate evidence was found.",
        answer_citation_ids=[],
        candidates=[],
        limitations=[retrieval.support_message],
    )
    return GroundedAnswerGenerationResult(
        retrieval_result=retrieval,
        draft=draft,
        attempts=0,
        provider_called=False,
        model_name="deterministic-template-v1",
        provider_name="deterministic",
    )


def test_supported_chat_response_adds_relevance_and_page_fields() -> None:
    generator = FakeGenerator(_supported_generation_result())
    app.dependency_overrides[get_grounded_answer_generator] = lambda: generator
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={
                "question": "  Which candidates know Python and PostgreSQL?  ",
                "candidate_limit": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["question"] == "Which candidates know Python and PostgreSQL?"
    assert payload["outcome"] == "supported"
    assert payload["provider"] == "deterministic"
    assert payload["candidates"][0]["relevance_score"] == 0.91
    assert payload["candidates"][0]["support_level"] == "complete"
    assert payload["sources"][0]["page"] == 1
    assert payload["sources"][0]["cv_url"] == (
        "/api/candidates/candidate_001/cv"
    )
    assert generator.queries[0].candidate_limit == 3


def test_unsupported_chat_is_a_successful_grounded_response() -> None:
    generator = FakeGenerator(_unsupported_generation_result())
    app.dependency_overrides[get_grounded_answer_generator] = lambda: generator
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={"question": "Who holds government security clearance?"},
        )
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["outcome"] == "unsupported"
    assert payload["provider_called"] is False
    assert payload["candidates"] == []
    assert payload["sources"] == []


def test_blank_and_overlong_questions_return_structured_422() -> None:
    generator = FakeGenerator(_supported_generation_result())
    app.dependency_overrides[get_grounded_answer_generator] = lambda: generator
    try:
        client = TestClient(app)
        blank = client.post("/api/chat", json={"question": "   "})
        overlong = client.post("/api/chat", json={"question": "x" * 2001})
    finally:
        app.dependency_overrides.clear()

    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "validation_error"
    assert overlong.status_code == 422
    assert overlong.json()["error"]["code"] == "validation_error"
    assert generator.queries == []


def test_provider_failure_does_not_expose_secret_details() -> None:
    generator = FakeGenerator(
        error=GroundedAnswerGenerationFailed(
            attempts=1,
            reasons=["OPENAI_API_KEY=super-secret provider failure"],
        )
    )
    app.dependency_overrides[get_grounded_answer_generator] = lambda: generator
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={"question": "Which candidates know Python?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "answer_provider_failed"
    assert "super-secret" not in response.text


def test_explicit_provider_configuration_error_maps_to_setup_message() -> None:
    generator = FakeGenerator(
        error=GroundedAnswerConfigurationError("missing key")
    )
    app.dependency_overrides[get_grounded_answer_generator] = lambda: generator
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={"question": "Which candidates know Python?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_not_configured"
    assert "setup.ps1" in response.json()["error"]["message"]


def test_partial_chat_preserves_partial_state_and_warning() -> None:
    retrieval = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_002",
                    "Jonas Keller",
                    "Python Backend Engineer",
                    matched_count=2,
                    candidate_score=0.55,
                    coverage_score=2 / 3,
                ),
            ),
            question="Find a native German backend engineer.",
            condition_labels=("backend engineer", "german", "native"),
        )
    )
    draft = GroundedAnswerDraft(
        outcome="partial",
        answer="Jonas Keller is a high-confidence partial match.",
        answer_citation_ids=["candidate_002-source-1"],
        candidates=[
            GroundedCandidateAnswer(
                candidate_id="candidate_002",
                candidate_name="Jonas Keller",
                professional_title="Python Backend Engineer",
                assessment="Partial source-backed match.",
                matched_requirements=["backend engineer", "german"],
                citation_ids=["candidate_002-source-1"],
            )
        ],
        limitations=[retrieval.support_message],
    )
    result = GroundedAnswerGenerationResult(
        retrieval_result=retrieval,
        draft=draft,
        attempts=1,
        provider_called=True,
        model_name="gpt-test",
        provider_name="openai",
    )
    app.dependency_overrides[get_grounded_answer_generator] = lambda: FakeGenerator(
        result
    )
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={"question": "Find a native German backend engineer."},
        )
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["outcome"] == "partial"
    assert payload["provider"] == "openai"
    assert payload["provider_called"] is True
    assert payload["candidates"][0]["support_level"] == "partial"
    assert payload["warnings"] == [retrieval.support_message]


def test_hosted_provider_diagnostics_are_preserved_without_keys() -> None:
    base = _supported_generation_result()
    for provider_name, model_name in (
        ("openai", "gpt-test"),
        ("gemini", "gemini-test"),
    ):
        result = GroundedAnswerGenerationResult(
            retrieval_result=base.retrieval_result,
            draft=base.draft,
            attempts=1,
            provider_called=True,
            model_name=model_name,
            provider_name=provider_name,
        )
        app.dependency_overrides[get_grounded_answer_generator] = (
            lambda result=result: FakeGenerator(result)
        )
        try:
            response = TestClient(app).post(
                "/api/chat",
                json={"question": "Which candidates know Python?"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["provider"] == provider_name
        assert response.json()["model"] == model_name
        assert response.json()["provider_called"] is True


def test_supported_hosted_reassurance_is_not_exposed_as_warning() -> None:
    base = _supported_generation_result()
    draft = base.draft.model_copy(
        update={
            "limitations": [
                "All candidates are complete matches, so no partial "
                "coverage needs to be noted."
            ]
        }
    )
    result = GroundedAnswerGenerationResult(
        retrieval_result=base.retrieval_result,
        draft=draft,
        attempts=1,
        provider_called=True,
        model_name="gpt-test",
        provider_name="openai",
    )
    app.dependency_overrides[get_grounded_answer_generator] = lambda: FakeGenerator(
        result
    )
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={"question": "Which candidates know Python?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["outcome"] == "supported"
    assert response.json()["warnings"] == []
