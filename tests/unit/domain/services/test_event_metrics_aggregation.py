from datetime import datetime, timedelta

from src.domain.entities.qualified_event import QualifiedEvent
from src.domain.services.event_metrics_aggregation import EventMetricsAggregation
from src.domain.value_objects.time_window import TimeWindow

BASE = datetime(2026, 9, 23, 14, 0)
WINDOW = TimeWindow(start_time=BASE, end_time=BASE + timedelta(hours=1))


def _event(event_id, phase="STARTED", status="CONFIRMED", started_min=10, occurred_min=None,
           duration_ms=5000, zone_id="galpao-solda", event_type="PPE_NON_COMPLIANT"):
    started_at = BASE + timedelta(minutes=started_min)
    occurred_at = BASE + timedelta(minutes=occurred_min if occurred_min is not None else started_min)
    return QualifiedEvent(
        event_id=event_id, event_type=event_type, status=status, phase=phase,
        started_at=started_at, duration_ms=duration_ms, occurred_at=occurred_at,
        session_id="s-1", zone_id=zone_id, object_class="person",
    )


def _aggregate(events):
    return EventMetricsAggregation().aggregate(events, WINDOW)


def test_deve_contar_eventos_distintos_iniciados_na_janela_e_os_em_duvida():
    metrics = _aggregate([
        _event("a"), _event("a", phase="UPDATED", occurred_min=12),
        _event("b"), _event("c"), _event("d", status="UNCERTAIN"),
    ])

    assert len(metrics) == 1
    assert metrics[0].count == 4
    assert metrics[0].uncertain_count == 1


def test_deve_usar_o_status_da_ultima_publicacao_antes_do_fim_da_janela():
    metrics = _aggregate([
        _event("a", status="UNCERTAIN"),
        _event("a", phase="UPDATED", status="CONFIRMED", occurred_min=20),
    ])
    assert metrics[0].uncertain_count == 0


def test_deve_calcular_duracao_media_dos_eventos_encerrados_na_janela():
    metrics = _aggregate([
        _event("a", phase="ENDED", occurred_min=20, duration_ms=10000),
        _event("b", phase="ENDED", occurred_min=30, duration_ms=14800),
    ])
    assert metrics[0].duration_avg_ms == 12400


def test_deve_publicar_duracao_de_evento_iniciado_antes_e_encerrado_na_janela():
    metrics = _aggregate([_event("a", started_min=-30, occurred_min=-30),
                          _event("a", phase="ENDED", started_min=-30, occurred_min=5, duration_ms=2100000)])
    assert metrics[0].count == 0
    assert metrics[0].duration_avg_ms == 2100000


def test_deve_separar_metricas_por_tipo_e_zona():
    metrics = _aggregate([_event("a"), _event("b", zone_id="patio"), _event("c", event_type="ZONE_ENTER")])
    assert {(m.event_type, m.zone_id) for m in metrics} == {
        ("PPE_NON_COMPLIANT", "galpao-solda"), ("PPE_NON_COMPLIANT", "patio"), ("ZONE_ENTER", "galpao-solda"),
    }


def test_nao_deve_gerar_metrica_sem_ocorrencia_na_janela():
    assert _aggregate([_event("a", started_min=90, occurred_min=90)]) == []
