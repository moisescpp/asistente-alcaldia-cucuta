def build_feedback_payload(**overrides) -> dict:
    payload = {
        "participant_name": "Test participante SUS",
        "participant_profile": "Familiar invitado",
        "tested_question": "Quiero informacion sobre impuesto predial",
        "found_answer": True,
        "clarity_rating": 5,
        "speed_rating": 4,
        "visual_rating": 5,
        "sus_1": 5,
        "sus_2": 1,
        "sus_3": 5,
        "sus_4": 1,
        "sus_5": 5,
        "sus_6": 1,
        "sus_7": 5,
        "sus_8": 1,
        "sus_9": 5,
        "sus_10": 1,
        "confusion_notes": "No tuve confusion relevante.",
        "suggestions": "Mantener requisitos visibles.",
    }
    payload.update(overrides)
    return payload


def test_public_feedback_endpoint_calculates_sus_score(client) -> None:
    response = client.post("/api/feedback", json=build_feedback_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["participant_name"] == "Test participante SUS"
    assert data["sus_score"] == 100.0
    assert data["clarity_rating"] == 5


def test_public_feedback_rejects_invalid_scale_values(client) -> None:
    response = client.post(
        "/api/feedback",
        json=build_feedback_payload(sus_1=6),
    )

    assert response.status_code == 422


def test_admin_can_list_citizen_feedback(client, admin_headers) -> None:
    created_response = client.post("/api/feedback", json=build_feedback_payload())
    assert created_response.status_code == 201

    response = client.get("/api/admin/feedback", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert any(item["participant_name"] == "Test participante SUS" for item in data)
