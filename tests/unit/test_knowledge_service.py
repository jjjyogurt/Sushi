import asyncio
from io import BytesIO

from starlette.datastructures import UploadFile

from app.models.monitor_profile import MonitorProfile
from app.services.knowledge_ingestion_service import KnowledgeIngestionService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.utils.json_codec import encode_json


def test_knowledge_bases_support_multiple_per_project_and_activation(db_session, monitor_profile):
    service = KnowledgeIngestionService(db_session)
    kb_specs = service.create_base(monitor_profile_id=monitor_profile.id, name="Specs")
    kb_faq = service.create_base(monitor_profile_id=monitor_profile.id, name="FAQ")

    assert kb_specs.is_active is True
    assert kb_faq.is_active is False

    renamed = service.update_base(
        knowledge_base_id=kb_faq.id,
        name="Support FAQ",
        description=None,
        is_active=True,
    )
    assert renamed.name == "Support FAQ"

    all_bases = service.list_bases(monitor_profile_id=monitor_profile.id)
    active = [item for item in all_bases if item.is_active]
    assert len(active) == 1
    assert active[0].id == kb_faq.id


def test_knowledge_retrieval_is_scoped_by_project_and_base(db_session, monitor_profile):
    second_profile = MonitorProfile(
        name="Second",
        brand_keywords=encode_json(["v-copter"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(second_profile)
    db_session.commit()
    db_session.refresh(second_profile)

    ingestion = KnowledgeIngestionService(db_session)
    retrieval = KnowledgeRetrievalService(db_session)

    kb_primary = ingestion.create_base(monitor_profile_id=monitor_profile.id, name="Primary KB")
    kb_secondary = ingestion.create_base(monitor_profile_id=second_profile.id, name="Secondary KB")

    primary_file = UploadFile(filename="specs.txt", file=BytesIO(b"HoverAir supports quick setup and stable hover modes."))
    secondary_file = UploadFile(filename="specs.txt", file=BytesIO(b"V-Copter has dual-rotor efficiency and long endurance."))

    asyncio.run(
        ingestion.add_file_source(
            monitor_profile_id=monitor_profile.id,
            knowledge_base_id=kb_primary.id,
            upload=primary_file,
        )
    )
    asyncio.run(
        ingestion.add_file_source(
            monitor_profile_id=second_profile.id,
            knowledge_base_id=kb_secondary.id,
            upload=secondary_file,
        )
    )

    primary_context = retrieval.build_knowledge_context(
        monitor_profile_id=monitor_profile.id,
        knowledge_base_id=kb_primary.id,
        query_text="hoverair setup",
    )
    secondary_context = retrieval.build_knowledge_context(
        monitor_profile_id=second_profile.id,
        knowledge_base_id=kb_secondary.id,
        query_text="endurance",
    )

    assert "HoverAir supports quick setup" in primary_context
    assert "V-Copter has dual-rotor efficiency" in secondary_context
    assert "V-Copter has dual-rotor efficiency" not in primary_context
