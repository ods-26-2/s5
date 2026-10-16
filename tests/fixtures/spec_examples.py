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


def zone_transition_exit() -> dict:
    return copy.deepcopy(_ZONE_TRANSITION_EXIT)


def zone_occupancy() -> dict:
    return copy.deepcopy(_ZONE_OCCUPANCY)


def qualified_event() -> dict:
    return copy.deepcopy(_QUALIFIED_EVENT)
