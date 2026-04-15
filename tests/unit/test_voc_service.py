from app.services.voc_service import VocService


class StubVocGeminiSuccess:
    def __init__(self):
        self.calls = []

    def generate_voc_report(self, *, analyzer_prompt: str, cleaned_rows, total_rows: int) -> str:
        self.calls.append(
            {
                "analyzer_prompt": analyzer_prompt,
                "cleaned_rows": cleaned_rows,
                "total_rows": total_rows,
            }
        )
        return "# VOC Report\n\n## Executive Decisions\n- Amplify: compact design.\n- Fix: battery expectation gap."


class StubVocGeminiFailure:
    def generate_voc_report(self, *, analyzer_prompt: str, cleaned_rows, total_rows: int) -> str:
        _ = (analyzer_prompt, cleaned_rows, total_rows)
        raise RuntimeError("gemini unavailable")


def _csv_bytes(rows) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_start_analysis_sends_cleaned_rows_to_gemini(db_session):
    service = VocService(db_session)
    project = service.create_project("VOC Test Project", "unit test")
    upload = service.create_upload(
        project_id=project.id,
        filename="voc.csv",
        content=_csv_bytes(
            [
                "comment",
                "Great stabilization and very easy setup.",
                "ID 录入日期",
                "Does it really only fly for 20 minutes?",
            ]
        ),
    )
    service.start_cleaning(upload.id)
    gemini = StubVocGeminiSuccess()
    service.gemini_client = gemini

    run, report = service.start_analysis(upload.id)

    assert run.status == "completed"
    assert report.content.startswith("# VOC Report")
    assert len(gemini.calls) == 1
    call = gemini.calls[0]
    assert call["total_rows"] == upload.total_rows
    assert len(call["cleaned_rows"]) >= 1
    assert all(item["cleaned_text"].strip() for item in call["cleaned_rows"])
    assert all("language" in item and "source" in item for item in call["cleaned_rows"])


def test_start_analysis_falls_back_to_local_report_when_gemini_fails(db_session):
    service = VocService(db_session)
    project = service.create_project("VOC Fallback Project", "unit test")
    upload = service.create_upload(
        project_id=project.id,
        filename="voc.csv",
        content=_csv_bytes(
            [
                "comment",
                "Way too expensive for casual users.",
                "Battery life drops too fast in cold weather.",
            ]
        ),
    )
    service.start_cleaning(upload.id)
    service.gemini_client = StubVocGeminiFailure()

    run, report = service.start_analysis(upload.id)

    assert run.status == "completed"
    assert "# VOC Report" in report.content
    assert "## Top Insights" in report.content
