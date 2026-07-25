import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai.client import _FakeToolCall
from app.models.session import Session
from app.services.chat import ChatService, ChatResult, INSURANCE_STATES
from app.services.tool_bridge import ToolBridge


class MockToolCall:
    def __init__(self, name: str, arguments: dict):
        self.function = MagicMock()
        self.function.name = name
        self.function.arguments = json.dumps(arguments)
        self.id = f"call_{name}"
        self.type = "function"


@pytest.mark.asyncio
async def test_chat_service_init(db_engine, mock_ai_client):
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    tool_bridge = MagicMock(spec=ToolBridge)
    service = ChatService(
        session_maker=maker,
        ai_client=mock_ai_client,
        tool_bridge=tool_bridge,
    )
    assert service._session_maker is maker
    assert service._ai_client is mock_ai_client
    assert service._tool_bridge is tool_bridge


@pytest.mark.asyncio
async def test_get_or_create_session_new(db_engine):
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, is_new = await service.get_or_create_session(session_id=None)
    assert is_new is True
    assert session.estado_actual == "inicio"
    assert session.activa is True
    assert len(session.id) == 36


@pytest.mark.asyncio
async def test_get_or_create_session_existing(db_engine):
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )

    session, _ = await service.get_or_create_session(session_id=None)
    existing_id = session.id

    retrieved, is_new = await service.get_or_create_session(
        session_id=existing_id
    )
    assert is_new is False
    assert retrieved.id == existing_id


class TestBuildSystemPrompt:
    def _make_session(self, insurance_profile=None, campos=None):
        return Session(
            id="test-id",
            estado_actual="perfilando",
            insurance_profile=insurance_profile,
            campos_diligenciados=campos or {},
            activa=True,
        )

    def _build_prompt(self, session):
        service = ChatService(
            session_maker=MagicMock(),
            ai_client=MagicMock(),
            tool_bridge=MagicMock(),
        )
        return service._build_system_prompt(session)

    def test_build_system_prompt_includes_formschema(self):
        session = self._make_session()
        session.estado_actual = "recopilando_datos_seguro"
        prompt = self._build_prompt(session)
        assert "ESQUEMA DEL FORMULARIO DE SEGURO" in prompt
        assert "REQ" in prompt

    def test_build_system_prompt_includes_profiling_instructions(self):
        session = self._make_session()
        prompt = self._build_prompt(session)
        assert "PERFILACIÓN CONVERSACIONAL" in prompt
        assert "MODO PERFILADO" in prompt

    def test_build_system_prompt_includes_context_aware_profiling(self):
        """When product_context is movilidad, shows vehicle-specific questions."""
        session = self._make_session(
            insurance_profile={"product_context": "movilidad"}
        )
        prompt = self._build_prompt(session)
        assert "ACCIÓN INMEDIATA REQUERIDA" in prompt
        assert "VEHÍCULO" in prompt
        assert "recommend_insurance" in prompt

    def test_build_system_prompt_includes_collection_state(self):
        session = self._make_session(campos={"nombre": "Juan"})
        session.estado_actual = "recopilando_datos_seguro"
        prompt = self._build_prompt(session)
        assert "ESTADO DE RECOLECCIÓN" in prompt
        assert "nombre" in prompt

    def test_build_system_prompt_includes_tool_instructions(self):
        session = self._make_session()
        session.estado_actual = "recopilando_datos_seguro"
        prompt = self._build_prompt(session)
        assert "INSTRUCCIONES DE RECOLECCIÓN (SEGURO)" in prompt
        assert "save_form_field" in prompt
        assert "create_policy" in prompt

    def test_build_system_prompt_in_insurance_states(self):
        """Profiling instructions present in any insurance state."""
        session = self._make_session()
        prompt = self._build_prompt(session)
        assert "PERFILACIÓN CONVERSACIONAL" in prompt

    def test_build_system_prompt_no_form_in_inicio(self):
        """In 'inicio' state, no form schema is shown."""
        session = self._make_session()
        session.estado_actual = "inicio"
        prompt = self._build_prompt(session)
        assert "ESQUEMA DEL FORMULARIO" not in prompt
        assert "MODO PERFILADO" not in prompt


class TestComputeCompletitudPct:
    def _make_session(self, campos=None):
        return Session(
            id="test",
            estado_actual="perfilando",
            campos_diligenciados=campos or {},
            activa=True,
        )

    def test_zero_percent_empty(self):
        session = self._make_session(campos={})
        pct = ChatService._compute_completitud_pct(session)
        assert pct == 0.0

    def test_fifty_percent(self):
        from app.schemas.insurance_schema import InsuranceFormSchema
        all_required = InsuranceFormSchema.campos_requeridos()
        half_count = len(all_required) // 2
        half_filled = {f.nombre: "test" for f in all_required[:half_count]}
        session = self._make_session(campos=half_filled)
        pct = ChatService._compute_completitud_pct(session)
        expected = round((half_count / len(all_required)) * 100, 1)
        assert pct == expected, f"expected {expected}, got {pct}"

    def test_one_hundred_percent_all_required(self):
        from app.schemas.insurance_schema import InsuranceFormSchema
        all_required = InsuranceFormSchema.campos_requeridos()
        all_filled = {f.nombre: "test" for f in all_required}
        session = self._make_session(campos=all_filled)
        pct = ChatService._compute_completitud_pct(session)
        assert pct == 100.0

    def test_no_required_fields(self):
        session = self._make_session(campos={"opcional": "x"})
        pct = ChatService._compute_completitud_pct(session)
        assert pct >= 0.0


class TestParseCamposActualizados:
    def test_empty_tool_calls(self):
        result = ChatService._parse_campos_actualizados([])
        assert result == []

    def test_none_tool_calls(self):
        result = ChatService._parse_campos_actualizados(None)
        assert result == []

    def test_extracts_save_form_field(self):
        calls = [
            MockToolCall("save_form_field", {"campo": "nombres", "valor": "Juan"}),
            MockToolCall("save_form_field", {"campo": "email", "valor": "a@b.com"}),
        ]
        result = ChatService._parse_campos_actualizados(calls)
        assert result == ["nombres", "email"]

    def test_ignores_other_tools(self):
        calls = [
            MockToolCall("get_products", {"tipo": "credito"}),
            MockToolCall("save_form_field", {"campo": "ciudad", "valor": "Bogotá"}),
        ]
        result = ChatService._parse_campos_actualizados(calls)
        assert result == ["ciudad"]

    def test_handles_missing_campo_key(self):
        calls = [
            MockToolCall("save_form_field", {"valor": "algo"}),
        ]
        result = ChatService._parse_campos_actualizados(calls)
        assert result == []

    def test_handles_invalid_json(self):
        call = MagicMock()
        call.function.name = "save_form_field"
        call.function.arguments = "not-json"
        result = ChatService._parse_campos_actualizados([call])
        assert result == []


# ---------------------------------------------------------------------------
# Task 3.1: Insurance state helpers + transitions
# ---------------------------------------------------------------------------


class TestInsuranceStateHelpers:
    def test_insurance_states_constant(self):
        assert "perfilando" in INSURANCE_STATES
        assert "recomendando" in INSURANCE_STATES
        assert "cotizando" in INSURANCE_STATES
        assert "recopilando_datos_seguro" in INSURANCE_STATES
        assert "completado_seguro" in INSURANCE_STATES
        assert len(INSURANCE_STATES) == 5

    def test_is_insurance_state_returns_true_for_insurance_states(self):
        for state in INSURANCE_STATES:
            assert ChatService._is_insurance_state(state) is True

    def test_is_insurance_state_returns_false_for_credit_states(self):
        credit_states = ["inicio", "validando_afiliacion", "recolectando_datos",
                         "recopilando_datos", "evaluando", "ofreciendo_producto",
                         "completado"]
        for state in credit_states:
            assert ChatService._is_insurance_state(state) is False

    def test_is_insurance_state_returns_false_for_unknown(self):
        assert ChatService._is_insurance_state("no_existe") is False


@pytest.mark.asyncio
async def test_update_session_state_perfilando_to_recomendando(db_engine):
    """When recommend_insurance is called, perfilando → recomendando."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "perfilando"
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("recommend_insurance", {"profile": {"edad": 35}})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.estado_actual == "recomendando"


@pytest.mark.asyncio
async def test_update_session_state_recomendando_to_cotizando(db_engine):
    """When quote_insurance is called, recomendando → cotizando."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "recomendando"
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("quote_insurance", {"product_id": "vida"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.estado_actual == "cotizando"


@pytest.mark.asyncio
async def test_update_session_state_cotizando_to_recopilando_datos_seguro(db_engine):
    """When first save_form_field in insurance, cotizando → recopilando_datos_seguro."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "cotizando"
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("save_form_field", {"campo": "nombre", "valor": "Juan"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.estado_actual == "recopilando_datos_seguro"


@pytest.mark.asyncio
async def test_update_session_state_recopilando_datos_seguro_to_completado(db_engine):
    """When create_policy succeeds, recopilando_datos_seguro → completado_seguro."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "recopilando_datos_seguro"
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("create_policy", {"insurance_id": "vida"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.estado_actual == "completado_seguro"
    assert updated.activa is False


@pytest.mark.asyncio
async def test_update_session_state_cotizando_to_recomendando_on_decline(db_engine):
    """When user wants different product, cotizando → recomendando."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )

    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "cotizando"
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("quote_insurance", {"product_id": "hogar"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.estado_actual == "recomendando"


# ---------------------------------------------------------------------------
# Task 4.2: Domain tool filtering — ChatService integration perspective
# ---------------------------------------------------------------------------


@pytest.fixture
def _domain_filter_mcp():
    """Mock MCP with credit + insurance + shared tools."""
    from unittest.mock import AsyncMock, MagicMock

    tools = []
    for name in [
        "get_customer", "get_products", "simulate_credit", "check_eligibility",
        "recommend_insurance", "quote_insurance", "create_policy",
        "save_form_field",
    ]:
        t = MagicMock()
        t.name = name
        t.description = f"Tool {name}"
        t.parameters = {
            "type": "object",
            "properties": {"dummy": {"type": "string"}},
            "required": [],
        }
        tools.append(t)

    mcp = MagicMock()
    mcp.list_tools = AsyncMock(return_value=tools)
    mcp.call_tool = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text="ok")])
    )
    return mcp


class TestDomainToolFiltering:
    """ToolBridge domain filtering from ChatService perspective."""

    @pytest.mark.asyncio
    async def test_insurance_domain_returns_only_insurance_tools(self, _domain_filter_mcp):
        """domain='insurance' returns only insurance-tagged tools."""
        from app.services.tool_bridge import ToolBridge

        bridge = ToolBridge(_domain_filter_mcp)
        result = await bridge.get_openai_tools(domain="insurance")
        names = {t["function"]["name"] for t in result}
        assert "recommend_insurance" in names
        assert "quote_insurance" in names
        assert "create_policy" in names
        assert "get_customer" not in names
        assert "get_products" not in names
        assert "simulate_credit" not in names
        assert "check_eligibility" not in names

    @pytest.mark.asyncio
    async def test_credit_domain_returns_only_credit_tools(self, _domain_filter_mcp):
        """domain='credit' returns only credit-tagged tools."""
        from app.services.tool_bridge import ToolBridge

        bridge = ToolBridge(_domain_filter_mcp)
        result = await bridge.get_openai_tools(domain="credit")
        names = {t["function"]["name"] for t in result}
        assert "get_customer" in names
        assert "get_products" in names
        assert "simulate_credit" in names
        assert "check_eligibility" in names
        assert "recommend_insurance" not in names
        assert "quote_insurance" not in names
        assert "create_policy" not in names

    @pytest.mark.asyncio
    async def test_none_domain_returns_all_tools(self, _domain_filter_mcp):
        """domain=None returns ALL tools (no filtering)."""
        from app.services.tool_bridge import ToolBridge

        bridge = ToolBridge(_domain_filter_mcp)
        result = await bridge.get_openai_tools(domain=None)
        names = {t["function"]["name"] for t in result}
        # Shared tools like save_form_field should be visible
        assert "save_form_field" in names
        assert "recommend_insurance" in names
        assert "get_customer" in names
        assert "create_policy" in names
        assert len(result) == 8


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T005: Profile pre-seed + anonymous salary flow
# ---------------------------------------------------------------------------

class MockSegmentDataService:
    """Minimal mock for SegmentDataService used in pre-seed tests."""

    def __init__(self, result: dict | None = None):
        self._result = result

    def is_loaded(self):
        return True

    def lookup_by_documento(self, documento: str):
        return self._result


def _patch_segment_svc(mock_svc):
    """Replace SegmentDataService.get_instance with a classmethod returning mock_svc."""
    import app.services.segment_data as _sd

    _sd.SegmentDataService.get_instance = classmethod(lambda cls: mock_svc)


@ pytest.mark.asyncio
async def test_profile_preseed_on_get_customer(db_engine):
    """get_customer tool call → insurance_profile populated from segment data."""
    _patch_segment_svc(MockSegmentDataService({
        "documento": "123",
        "categoria": "A",
        "segmento": "LAMBDA",
    }))

    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "perfilando"
    session.insurance_profile = {}
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("get_customer", {"documento_identidad": "123"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.insurance_profile is not None
    assert updated.insurance_profile.get("categoria_afiliacion") == "A"
    assert updated.insurance_profile.get("segmento_grupo_familiar") == "LAMBDA"


@ pytest.mark.asyncio
async def test_profile_preseed_doc_not_found(db_engine):
    """get_customer with documento not in dataset → insurance_profile unchanged."""
    _patch_segment_svc(MockSegmentDataService(None))  # lookup returns None

    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "perfilando"
    session.insurance_profile = {}
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("get_customer", {"documento_identidad": "NOT_FOUND"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    # insurance_profile should still be empty dict
    assert updated.insurance_profile == {}


@ pytest.mark.asyncio
async def test_profile_preseed_preserves_existing(db_engine):
    """Existing keys in insurance_profile are preserved when pre-seeding."""
    _patch_segment_svc(MockSegmentDataService({
        "documento": "456",
        "categoria": "B",
        "segmento": "RHO",
    }))

    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "perfilando"
    session.insurance_profile = {"product_context": "vida", "edad": 35}
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("get_customer", {"documento_identidad": "456"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.insurance_profile is not None
    # Existing keys preserved
    assert updated.insurance_profile.get("product_context") == "vida"
    assert updated.insurance_profile.get("edad") == 35
    # New keys added
    assert updated.insurance_profile.get("categoria_afiliacion") == "B"
    assert updated.insurance_profile.get("segmento_grupo_familiar") == "RHO"


@ pytest.mark.asyncio
async def test_profile_preseed_no_get_customer(db_engine):
    """Tool call that is NOT get_customer → profile not modified."""
    _patch_segment_svc(MockSegmentDataService({"categoria": "A"}))

    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "perfilando"
    session.insurance_profile = {}
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("get_products", {"tipo": "credito"})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.insurance_profile == {}


class TestAnonymousSalaryProfiling:
    def _make_session(self, insurance_profile=None):
        return Session(
            id="test-id",
            estado_actual="perfilando",
            insurance_profile=insurance_profile,
            campos_diligenciados={},
            activa=True,
        )

    def _build_prompt(self, session):
        service = ChatService(
            session_maker=MagicMock(),
            ai_client=MagicMock(),
            tool_bridge=MagicMock(),
        )
        return service._build_system_prompt(session)

    def test_anonymous_salary_in_profiling(self):
        """Without categoria_afiliacion, system prompt includes salary flow."""
        session = self._make_session(insurance_profile={})
        prompt = self._build_prompt(session)
        assert "PERFILACIÓN SIN DOCUMENTO" in prompt
        assert "rango salarial" in prompt
        assert "set_category" in prompt

    def test_no_anonymous_salary_when_categoria_present(self):
        """When profile has categoria_afiliacion, salary section is NOT included."""
        session = self._make_session(
            insurance_profile={"categoria_afiliacion": "A"}
        )
        prompt = self._build_prompt(session)
        assert "PERFILACIÓN SIN DOCUMENTO" not in prompt


@ pytest.mark.asyncio
async def test_set_category_tool_updates_profile(db_engine, monkeypatch):
    """set_category tool call updates insurance_profile.categoria_afiliacion."""
    from app.tools import domain_tools

    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(domain_tools, "async_session_maker", maker)

    # Create a session with no categoria
    async with maker() as db:
        session = Session(
            id="set-cat-test",
            estado_actual="perfilando",
            insurance_profile={},
            activa=True,
        )
        db.add(session)
        await db.commit()

    # Call set_category directly
    result = await domain_tools.set_category(
        session_id="set-cat-test",
        categoria="B",
    )

    assert "Categoría B registrada" in result

    async with maker() as db:
        updated = await db.get(Session, "set-cat-test")
    assert updated is not None
    assert updated.insurance_profile is not None
    assert updated.insurance_profile.get("categoria_afiliacion") == "B"


@ pytest.mark.asyncio
async def test_set_category_invalid_value(db_engine):
    """set_category with invalid category returns error."""
    from app.tools import domain_tools

    result = await domain_tools.set_category(
        session_id="any-id",
        categoria="INVALID",
    )
    assert "Error" in result
    assert "INVALID" in result
    assert "A, B o C" in result


@ pytest.mark.asyncio
async def test_update_session_state_insurance_transitions(db_engine):
    """Insurance state transitions work correctly."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    service = ChatService(
        session_maker=maker,
        ai_client=MagicMock(),
        tool_bridge=MagicMock(),
    )
    session, _ = await service.get_or_create_session(session_id=None)
    session.estado_actual = "perfilando"
    async with maker() as db:
        await db.merge(session)
        await db.commit()

    await service._update_session_state(
        session.id,
        tool_calls=[MockToolCall("recommend_insurance", {"profile": {"edad": 35}})],
    )

    async with maker() as db:
        updated = await db.get(Session, session.id)
    assert updated is not None
    assert updated.estado_actual == "recomendando"
