import pytest

from src.application.messaging.outgoing_envelope_factory import OutgoingEnvelopeFactory
from src.application.use_cases.answer_query_use_case import AnswerQueryUseCase
from src.application.use_cases.query_heatmap_use_case import QueryHeatmapUseCase
from src.application.use_cases.query_metrics_use_case import QueryMetricsUseCase
from src.domain.exceptions import MalformedEventEnvelopeError, UnsupportedSchemaError
from tests.fixtures.spec_examples import heatmap_query, metrics_query

from .fakes import FakeTimeSeriesRepository
from .test_close_metric_windows_use_case import RecordingPublisher


def _answer():
    repository = FakeTimeSeriesRepository()
    publisher = RecordingPublisher()
    use_case = AnswerQueryUseCase(
        {
            "ods.s5.metrics.query": QueryMetricsUseCase(repository).execute,
            "ods.s5.heatmap.query": QueryHeatmapUseCase(repository).execute,
        },
        OutgoingEnvelopeFactory(),
        publisher,
    )
    return use_case, publisher


def test_deve_publicar_reply_rpl_no_topico_da_reply():
    use_case, publisher = _answer()
    query = heatmap_query()

    reply = use_case.execute(query)

    assert publisher.published == [("ods.s5.heatmap.reply", reply)]
    assert reply["message_type"] == "reply"
    assert reply["schema"] == "ods.s5.heatmap.reply"
    assert reply["producer"] == "S5"
    assert reply["correlation_id"] == query["message_id"]
    assert "session_id" not in reply and "captured_at" not in reply
    assert reply["payload"]["status"] == "OK"


def test_consulta_recusada_vira_reply_de_erro():
    use_case, _ = _answer()

    reply = use_case.execute(metrics_query())

    assert reply["payload"] == {
        "status": "ERROR",
        "error": {"code": "UNKNOWN_ZONE", "message": "Zona sem métricas no S5: 'vaga-12'."},
    }


def test_deve_ignorar_consulta_para_outro_componente():
    use_case, publisher = _answer()
    query = metrics_query()
    query["target"] = "S4"

    assert use_case.execute(query) is None
    assert publisher.published == []


def test_deve_rejeitar_consulta_sem_target():
    use_case, _ = _answer()
    query = metrics_query()
    del query["target"]
    with pytest.raises(MalformedEventEnvelopeError):
        use_case.execute(query)


def test_deve_rejeitar_mensagem_que_nao_seja_query():
    use_case, _ = _answer()
    query = metrics_query()
    query["message_type"] = "command"
    with pytest.raises(MalformedEventEnvelopeError):
        use_case.execute(query)


def test_deve_rejeitar_schema_nao_atendido():
    use_case, _ = _answer()
    query = metrics_query()
    query["schema"] = "ods.s4.clip.query"
    with pytest.raises(UnsupportedSchemaError):
        use_case.execute(query)
