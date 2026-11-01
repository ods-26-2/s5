"""Mensagens da Especificação de interfaces 1.0 (seção 7), completadas com os campos de
envelope que os exemplos omitem (seção 3, perfis EV-SINAL e EV-SERVIÇO). Cada função devolve uma
cópia nova, para que um teste possa alterá-la sem afetar os demais."""

import copy

SESSION_ID = "9c2a1f3e-4d5b-4c6a-9e8f-0a1b2c3d4e5f"

_ZONE_TRANSITION_EXIT = {
    "message_type": "event",
    "message_id": "1b2c3d4e-5f60-4a7b-8c9d-0e1f2a3b4c5d",
    "schema": "ods.s1.zone_transition",
    "schema_version": "1.0",
    "producer": "S1",
    "published_at": "2026-09-23T14:29:59.450Z",
    "captured_at": "2026-09-23T14:29:59.200Z",
    "source_id": "cam0",
    "session_id": SESSION_ID,
    "sequence": 1204,
    "artifact_version": "zones-a8-2",
    "payload": {
        "track_id": "t-0391",
        "class": "vehicle",
        "zone_id": "vaga-12",
        "transition": "EXIT",
        "entered_at": "2026-09-23T12:10:04.200Z",
        "dwell_s": 8395,
    },
}

_ZONE_OCCUPANCY = {
    "message_type": "event",
    "message_id": "2c3d4e5f-6071-4b8c-9d0e-1f2a3b4c5d6e",
    "schema": "ods.s1.zone_occupancy",
    "schema_version": "1.0",
    "producer": "S1",
    "published_at": "2026-09-23T14:29:59.460Z",
    "captured_at": "2026-09-23T14:29:59.200Z",
    "source_id": "cam0",
    "session_id": SESSION_ID,
    "sequence": 1205,
    "artifact_version": "zones-a8-2",
    "payload": {
        "zone_id": "vaga-12",
        "count": 0,
        "count_by_class": {"vehicle": 0, "person": 0},
        "max_occupancy": 1,
        "track_ids": [],
    },
}

_QUALIFIED_EVENT = {
    "message_type": "event",
    "message_id": "3d4e5f60-7182-4c9d-8e0f-2a3b4c5d6e7f",
    "schema": "ods.s2.event",
    "schema_version": "1.0",
    "producer": "S2",
    "published_at": "2026-09-23T14:30:00.150Z",
    "captured_at": "2026-09-23T14:30:00.000Z",
    "source_id": "cam0",
    "session_id": SESSION_ID,
    "sequence": 311,
    "artifact_version": "rules-a5-3",
    "payload": {
        "event_id": "6d9f2b1c-3e4a-4b5c-8d6e-7f8a9b0c1d2e",
        "event_type": "PPE_NON_COMPLIANT",
        "rule_id": "a5-luva-galpao",
        "status": "CONFIRMED",
        "phase": "STARTED",
        "confidence": 0.81,
        "entity_id": "e-7a21",
        "class": "person",
        "zone_id": "galpao-solda",
        "equipment_item": "luva",
        "started_at": "2026-09-23T14:29:52.000Z",
        "duration_ms": 8000,
        "source_ids": ["cam0"],
        "details": {"compliance": "ABSENT", "min_duration_ms": 5000},
    },
}

_POSITION = {
    "message_type": "event",
    "message_id": "60718293-a4b5-4f20-9b3c-5d6e7f8091a2",
    "schema": "ods.s1.position",
    "schema_version": "1.0",
    "producer": "S1",
    "published_at": "2026-09-23T14:30:00.140Z",
    "captured_at": "2026-09-23T14:29:59.870Z",
    "source_id": "cam0",
    "session_id": SESSION_ID,
    "sequence": 48213,
    "artifact_version": "zones-a8-2",
    "payload": {
        "frame_index": 48213,
        "positions": [
            {
                "track_id": "t-0391",
                "class": "person",
                "point_px": [505, 702],
                "position_m": [3.42, 7.10],
                "space_id": "patio-1",
                "zone_ids": ["vaga-12"],
            }
        ],
    },
}

_METRICS_QUERY = {
    "message_type": "query",
    "message_id": "71829304-b5c6-4031-8c4d-6e7f8091a2b3",
    "schema": "ods.s5.metrics.query",
    "schema_version": "1.0",
    "producer": "A8",
    "target": "S5",
    "published_at": "2026-09-23T15:00:00.000Z",
    "payload": {
        "metric": "ZONE",
        "zone_id": "vaga-12",
        "class": "vehicle",
        "period_start_at": "2026-09-22T00:00:00.000Z",
        "period_end_at": "2026-09-23T00:00:00.000Z",
        "granularity": "1h",
    },
}

_HEATMAP_QUERY = {
    "message_type": "query",
    "message_id": "8293a4b5-c6d7-4142-9d5e-7f8091a2b3c4",
    "schema": "ods.s5.heatmap.query",
    "schema_version": "1.0",
    "producer": "A3",
    "target": "S5",
    "published_at": "2026-09-23T15:00:00.000Z",
    "payload": {
        "space_id": "patio-1",
        "class": "person",
        "period_start_at": "2026-09-23T14:00:00.000Z",
        "period_end_at": "2026-09-23T15:00:00.000Z",
        "cell_size_m": 0.5,
    },
}

REPLAY_SESSION_ID = "4b5c6d7e-8f90-4a1b-9c2d-3e4f5a6b7c8d"

_REPLAY_SESSION_STARTED = {
    "message_type": "event",
    "message_id": "4e5f6071-8293-4d0e-9f1a-3b4c5d6e7f80",
    "schema": "ods.session.started",
    "schema_version": "1.0",
    "producer": "P6",
    "published_at": "2026-10-16T13:00:00.020Z",
    "captured_at": "2026-09-23T14:29:58.000Z",
    "session_id": REPLAY_SESSION_ID,
    "sequence": 0,
    "payload": {
        "mode": "REPLAY",
        "started_at": "2026-09-23T14:29:58.000Z",
        "sources": ["cam0", "mic0"],
        "recording_id": "rec-2026-09-23-001",
        "previous_session_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
        "reason": "SEEK",
    },
}

_REPLAY_STATE = {
    "message_type": "event",
    "message_id": "5f607182-93a4-4e1f-8a2b-4c5d6e7f8091",
    "schema": "ods.p6.replay.state",
    "schema_version": "1.0",
    "producer": "P6",
    "published_at": "2026-10-16T13:00:01.010Z",
    "captured_at": "2026-09-23T14:29:59.000Z",
    "session_id": REPLAY_SESSION_ID,
    "sequence": 1,
    "payload": {
        "recording_id": "rec-2026-09-23-001",
        "state": "PLAYING",
        "position_ms": 126000,
        "duration_ms": 600000,
        "speed_factor": 1.0,
        "loop": False,
    },
}


def zone_transition_exit() -> dict:
    return copy.deepcopy(_ZONE_TRANSITION_EXIT)


def zone_occupancy() -> dict:
    return copy.deepcopy(_ZONE_OCCUPANCY)


def qualified_event() -> dict:
    return copy.deepcopy(_QUALIFIED_EVENT)


def replay_session_started() -> dict:
    return copy.deepcopy(_REPLAY_SESSION_STARTED)


def replay_state() -> dict:
    return copy.deepcopy(_REPLAY_STATE)


def in_session(message: dict, session_id: str, message_id: str, captured_at: str | None = None) -> dict:
    """A mesma mensagem em outra sessão (e, se pedido, em outro instante), com message_id
    novo para não cair na deduplicação."""
    message["session_id"] = session_id
    message["message_id"] = message_id
    if captured_at is not None:
        message["captured_at"] = captured_at
    return message


def position() -> dict:
    return copy.deepcopy(_POSITION)


def metrics_query() -> dict:
    return copy.deepcopy(_METRICS_QUERY)


def heatmap_query() -> dict:
    return copy.deepcopy(_HEATMAP_QUERY)
