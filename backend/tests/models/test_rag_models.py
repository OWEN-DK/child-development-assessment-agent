def test_test_run_result_metrics_fields():
    from src.models.test_case import TestRunResult
    from datetime import datetime, timezone

    result = TestRunResult(
        run_id="run_123",
        test_case_id="case_123",
        query="1岁宝宝走路正常吗",
        mrr=0.5,
        ndcg=0.75,
        precision=0.8,
        recall=0.6,
        hit_rate_1=1.0,
        hit_rate_3=0.8,
        hit_rate_5=0.6,
        retrieved_doc_ids=["doc1", "doc2"],
        relevant_doc_ids=["doc1"],
        created_at=datetime.now(timezone.utc),
    )

    assert result.mrr == 0.5
    assert result.ndcg == 0.75
    assert result.precision == 0.8
    assert result.recall == 0.6
    assert result.hit_rate_1 == 1.0
    assert result.hit_rate_3 == 0.8
    assert result.hit_rate_5 == 0.6


def test_test_run_status_field():
    from src.models.test_case import TestRun, TestRunStatus, ReportExportFormat
    from datetime import datetime, timezone

    test_run = TestRun(
        name="测试运行1",
        test_set_ids=["set_1", "set_2"],
        status=TestRunStatus.COMPLETED,
        report_export_format=ReportExportFormat.MARKDOWN,
        report_storage_path="/reports/run_1.md",
        created_at=datetime.now(timezone.utc),
    )

    assert test_run.status == TestRunStatus.COMPLETED
    assert hasattr(test_run, "report_export_format")
    assert hasattr(test_run, "report_storage_path")


def test_test_case_draft_batch_id_field():
    from src.models.test_case import TestCaseDraft
    from datetime import datetime, timezone

    draft = TestCaseDraft(
        source_document_id="doc_123",
        query="1岁宝宝走路正常吗",
        domain="gross_motor",
        age=1.0,
        generation_batch_id="doc_1_a1b2c3d4_20240101_1200",
        status="draft",
        created_at=datetime.now(timezone.utc),
    )

    assert draft.generation_batch_id == "doc_1_a1b2c3d4_20240101_1200"
