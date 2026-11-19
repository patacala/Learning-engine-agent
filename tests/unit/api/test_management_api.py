"""Tests for CRM Management API — provisioning, agents, versions, config, knowledge, outbound."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from learning_engine.api.v1.dependencies import get_authenticated_org, get_db_session, verify_provisioning_secret
from learning_engine.api.v1.endpoints.management import router as management_router
from learning_engine.api.v1.endpoints.provisioning import router as provisioning_router
from learning_engine.infrastructure.database.models_agent import (
    AgentIdentityModel,
    AgentModel,
    AgentPersonalityModel,
    AgentRuleModel,
    AgentStrategyModel,
    AgentTacticModel,
    AgentVersionModel,
    AgentVoiceModel,
    OrganizationAgentModel,
    OrganizationModel,
)
from learning_engine.infrastructure.security.api_keys import hash_api_key

app = FastAPI()
app.include_router(provisioning_router, prefix="/api/v1")
app.include_router(management_router, prefix="/api/v1")

PROV_SECRET = "test-provisioning-secret"
ORG_API_KEY = "sk-testorg-abcdef123456abcdef123456"


def _mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


def _mock_org(org_id=None, name="Test Org", slug="test-org"):
    org = MagicMock(spec=OrganizationModel)
    org.id = org_id or uuid.uuid4()
    org.name = name
    org.slug = slug
    org.api_key_hash = hash_api_key(ORG_API_KEY)
    org.api_key_prefix = ORG_API_KEY[:8]
    org._auth_api_key = ORG_API_KEY  # set by get_authenticated_org at runtime
    org.capabilities = ["knowledge", "escalation"]
    org.is_active = True
    org.created_at = datetime.utcnow()
    org.updated_at = datetime.utcnow()
    return org


def _mock_agent(agent_id=None, name="Sales Bot", slug="sales-bot"):
    agent = MagicMock(spec=AgentModel)
    agent.id = agent_id or uuid.uuid4()
    agent.name = name
    agent.slug = slug
    agent.agent_type = "sales"
    agent.description = "AI sales agent"
    agent.is_active = True
    agent.created_at = datetime.utcnow()
    agent.updated_at = datetime.utcnow()
    return agent


def _mock_version(version_id=None, agent_id=None, number=1, published=True):
    version = MagicMock(spec=AgentVersionModel)
    version.id = version_id or uuid.uuid4()
    version.agent_id = agent_id or uuid.uuid4()
    version.version_number = number
    version.is_published = published
    version.capabilities = ["voice", "negotiation"]
    version.created_at = datetime.utcnow()
    return version


def _override_provisioning_no_check():
    """Override provisioning secret check."""
    async def _noop():
        pass
    app.dependency_overrides[verify_provisioning_secret] = _noop


def _override_org(org=None):
    """Override org auth to return mock org."""
    org = org or _mock_org()
    async def _get_org():
        return org
    app.dependency_overrides[get_authenticated_org] = _get_org
    return org


def _override_session(session=None):
    session = session or _mock_session()
    async def _get():
        return session
    app.dependency_overrides[get_db_session] = _get
    return session


def _cleanup():
    app.dependency_overrides.clear()


# ==================== PROVISIONING ====================


class TestProvisioning:
    @pytest.mark.asyncio
    async def test_provision_org_creates_new(self):
        _override_provisioning_no_check()
        mock_session = _override_session()

        org = _mock_org(slug="new-org")

        with patch("learning_engine.api.v1.endpoints.provisioning.create_organization", new_callable=AsyncMock) as mock_create:
            # No existing org
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_create.return_value = org

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/provisioning/organizations/new-org",
                    json={"name": "New Org", "capabilities_preset": "full"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["slug"] == "new-org"
            mock_create.assert_called_once()

        _cleanup()

    @pytest.mark.asyncio
    async def test_provision_org_updates_existing(self):
        _override_provisioning_no_check()
        mock_session = _override_session()

        org = _mock_org(slug="existing-org")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = org
        mock_session.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                "/api/v1/provisioning/organizations/existing-org",
                json={"name": "Updated Name", "capabilities_preset": "knowledge_only"},
            )

        assert response.status_code == 200
        assert org.name == "Updated Name"

        _cleanup()

    @pytest.mark.asyncio
    async def test_provision_org_bad_secret_401(self):
        # Don't override provisioning check — let it validate
        _cleanup()

        with patch("learning_engine.api.v1.dependencies.settings") as mock_settings:
            mock_settings.provisioning_secret = "real-secret"

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/provisioning/organizations/test",
                    json={"name": "Test"},
                    headers={"Authorization": "Bearer wrong-secret"},
                )

            assert response.status_code == 401

        _cleanup()

    @pytest.mark.asyncio
    async def test_regenerate_key_updates_stored_hash(self):
        _override_provisioning_no_check()
        mock_session = _override_session()

        org = _mock_org()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = org
        mock_session.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/provisioning/organizations/{org.id}/regenerate-key",
            )

        assert response.status_code == 200
        new_key = response.json()["api_key"]
        assert new_key != ORG_API_KEY
        assert org.api_key_hash == hash_api_key(new_key)

        _cleanup()


# ==================== AGENTS ====================


class TestAgents:
    @pytest.mark.asyncio
    async def test_create_agent_from_template(self):
        org = _override_org()
        agent = _mock_agent()
        version = _mock_version(agent_id=agent.id)

        # Mock the session from the org
        mock_session = _mock_session()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.create_agent_from_template", new_callable=AsyncMock) as mock_create,
            patch("learning_engine.api.v1.endpoints.management.assign_agent_to_org", new_callable=AsyncMock),
        ):
            mock_create.return_value = (agent, version)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/management/agents",
                    json={"name": "Sales Bot", "slug": "sales-bot", "agent_type": "sales"},
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Sales Bot"
            assert data["latest_version_id"] == str(version.id)

        _cleanup()

    @pytest.mark.asyncio
    async def test_list_agents_scoped_to_org(self):
        org = _override_org()
        agent = _mock_agent()
        version = _mock_version(agent_id=agent.id)

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.all.return_value = [(agent, version)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/management/agents",
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Sales Bot"

        _cleanup()

    @pytest.mark.asyncio
    async def test_patch_agent(self):
        org = _override_org()
        agent = _mock_agent()
        version = _mock_version(agent_id=agent.id)

        mock_session = _mock_session()

        # First call: verify_agent, second: re-fetch agent, third: get latest version
        mock_result_verify = MagicMock()
        mock_result_verify.scalar_one_or_none.return_value = agent

        mock_result_refetch = MagicMock()
        mock_result_refetch.scalar_one.return_value = agent

        mock_result_version = MagicMock()
        mock_result_version.scalar_one_or_none.return_value = version

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_verify, mock_result_refetch, mock_result_version]
        )

        with patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/management/agents/{agent.id}",
                    json={"name": "Updated Bot", "description": "New desc"},
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            assert agent.name == "Updated Bot"
            assert agent.description == "New desc"

        _cleanup()


# ==================== VERSIONS ====================


class TestVersions:
    @pytest.mark.asyncio
    async def test_create_version_not_published(self):
        org = _override_org()
        agent = _mock_agent()
        latest = _mock_version(agent_id=agent.id, number=1)

        mock_session = _mock_session()

        # verify agent, find latest version
        mock_result_verify = MagicMock()
        mock_result_verify.scalar_one_or_none.return_value = agent

        mock_result_latest = MagicMock()
        mock_result_latest.scalar_one_or_none.return_value = latest

        mock_session.execute = AsyncMock(side_effect=[mock_result_verify, mock_result_latest])

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management._deep_copy_version_config", new_callable=AsyncMock),
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/management/agents/{agent.id}/versions",
                    json={},
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["version_number"] == 2
            assert data["is_published"] is False

        _cleanup()

    @pytest.mark.asyncio
    async def test_create_version_copies_from_latest(self):
        org = _override_org()
        agent = _mock_agent()
        latest = _mock_version(agent_id=agent.id, number=1)

        mock_session = _mock_session()

        mock_result_verify = MagicMock()
        mock_result_verify.scalar_one_or_none.return_value = agent

        mock_result_latest = MagicMock()
        mock_result_latest.scalar_one_or_none.return_value = latest

        mock_session.execute = AsyncMock(side_effect=[mock_result_verify, mock_result_latest])

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management._deep_copy_version_config", new_callable=AsyncMock) as mock_copy,
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/management/agents/{agent.id}/versions",
                    json={},
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            mock_copy.assert_called_once()

        _cleanup()

    @pytest.mark.asyncio
    async def test_patch_version_publish(self):
        org = _override_org()
        version = _mock_version(published=False)

        mock_session = _mock_session()

        mock_result_verify = MagicMock()
        mock_result_verify.scalar_one_or_none.return_value = version

        mock_result_refetch = MagicMock()
        mock_result_refetch.scalar_one.return_value = version

        mock_session.execute = AsyncMock(side_effect=[mock_result_verify, mock_result_refetch])

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.invalidate_agent_version_cache", new_callable=AsyncMock),
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/management/versions/{version.id}",
                    json={"is_published": True},
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            assert version.is_published is True

        _cleanup()


# ==================== CONFIG ====================


class TestConfig:
    @pytest.mark.asyncio
    async def test_put_identity_replaces(self):
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.invalidate_agent_version_cache", new_callable=AsyncMock),
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    f"/api/v1/management/versions/{version.id}/identity",
                    json={
                        "name": "Agent Smith",
                        "description": "Updated identity",
                        "communication_style": "direct",
                        "principles": ["Be honest"],
                        "values": ["Trust"],
                    },
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Agent Smith"
            assert data["principles"] == ["Be honest"]
            assert data["values"] == ["Trust"]

        _cleanup()

    @pytest.mark.asyncio
    async def test_get_identity(self):
        org = _override_org()
        version = _mock_version()

        identity = MagicMock(spec=AgentIdentityModel)
        identity.name = "Test Agent"
        identity.description = "Desc"
        identity.communication_style = "consultive"
        identity.compliance_notes = ""
        identity.principles = ["P1"]
        identity.beliefs = ["B1"]
        identity.values_list = ["V1"]
        identity.words_never_use = ["bad"]
        identity.words_prefer = ["good"]

        mock_session = _mock_session()

        # First call: verify version, second call: get identity
        mock_result_verify = MagicMock()
        mock_result_verify.scalar_one_or_none.return_value = version

        mock_result_identity = MagicMock()
        mock_result_identity.scalar_one_or_none.return_value = identity

        mock_session.execute = AsyncMock(side_effect=[mock_result_verify, mock_result_identity])

        with patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/management/versions/{version.id}/identity",
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test Agent"
            assert data["values"] == ["V1"]

        _cleanup()

    @pytest.mark.asyncio
    async def test_put_rules_bulk_replace(self):
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.invalidate_agent_version_cache", new_callable=AsyncMock),
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
        ):
            rules = [
                {"rule_id": "r1", "action_type": "greet", "intent": "greeting", "priority": 10},
                {"rule_id": "r2", "action_type": "inform", "intent": "inquiry", "priority": 8},
            ]

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    f"/api/v1/management/versions/{version.id}/rules",
                    json=rules,
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["rule_id"] == "r1"

        _cleanup()

    @pytest.mark.asyncio
    async def test_put_strategies_with_tactics(self):
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.invalidate_agent_version_cache", new_callable=AsyncMock),
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
        ):
            strategies = [{
                "strategy_type": "consultive",
                "name": "Consultive Selling",
                "tactics": [
                    {"name": "discover", "prompt_instruction": "Ask questions", "position": 0},
                    {"name": "match", "prompt_instruction": "Match needs", "position": 1},
                ],
            }]

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    f"/api/v1/management/versions/{version.id}/strategies",
                    json=strategies,
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert len(data[0]["tactics"]) == 2

        _cleanup()

    @pytest.mark.asyncio
    async def test_put_voice_config(self):
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.invalidate_agent_version_cache", new_callable=AsyncMock),
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    f"/api/v1/management/versions/{version.id}/voice",
                    json={
                        "backchannels_es": ["claro", "sí"],
                        "backchannels_en": ["sure", "yes"],
                        "backchannel_probability": 0.4,
                        "enable_ssml": False,
                    },
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["backchannel_probability"] == 0.4
            assert data["enable_ssml"] is False

        _cleanup()


# ==================== ASSIGNMENTS ====================


class TestAssignments:
    @pytest.mark.asyncio
    async def test_assign_agent_to_org(self):
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        assignment = MagicMock(spec=OrganizationAgentModel)
        assignment.id = uuid.uuid4()
        assignment.is_primary = True
        assignment.is_active = True

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.assign_agent_to_org", new_callable=AsyncMock, return_value=assignment),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/management/agents/{version.agent_id}/assign",
                    json={"agent_version_id": str(version.id), "is_primary": True},
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["is_primary"] is True

        _cleanup()

    @pytest.mark.asyncio
    async def test_unassign_agent(self):
        org = _override_org()
        assignment_id = uuid.uuid4()

        assignment = MagicMock(spec=OrganizationAgentModel)
        assignment.id = assignment_id

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assignment
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cache = AsyncMock()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.get_redis_cache", return_value=mock_cache),
            patch("learning_engine.api.v1.endpoints.management.invalidate_agent_context", new_callable=AsyncMock) as mock_invalidate,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.delete(
                    f"/api/v1/management/assignments/{assignment_id}",
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 204
            mock_session.delete.assert_awaited_once_with(assignment)
            mock_invalidate.assert_awaited_once()
            assert mock_invalidate.await_args.args[1] == ORG_API_KEY

        _cleanup()


# ==================== KNOWLEDGE ====================


class TestKnowledge:
    @pytest.mark.asyncio
    async def test_index_document_scoped_to_org(self):
        org = _override_org()
        mock_session = _mock_session()
        doc_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.title = "Product Guide"
        mock_doc.category = "products"
        mock_doc.created_at = datetime.utcnow()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.index_document", new_callable=AsyncMock, return_value=mock_doc),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/management/knowledge",
                    json={"title": "Product Guide", "content": "All about products", "category": "products"},
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Product Guide"
            assert data["id"] == str(doc_id)

        _cleanup()

    @pytest.mark.asyncio
    async def test_list_documents_filtered(self):
        org = _override_org()
        mock_session = _mock_session()

        doc1 = MagicMock()
        doc1.id = uuid.uuid4()
        doc1.title = "Doc 1"
        doc1.category = "products"
        doc1.created_at = datetime.utcnow()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [doc1]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/management/knowledge?category=products",
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["category"] == "products"

        _cleanup()

    @pytest.mark.asyncio
    async def test_delete_document_204(self):
        org = _override_org()
        doc_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = doc_id

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.delete(
                    f"/api/v1/management/knowledge/{doc_id}",
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 204

        _cleanup()


# ==================== OUTBOUND ====================


class TestOutbound:
    @pytest.mark.asyncio
    async def test_outbound_sends_ids_not_secrets(self):
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.settings") as mock_settings,
            patch("learning_engine.api.v1.endpoints.management.OutboundCallService") as MockService,
        ):
            mock_settings.retell_api_key = "test-retell-key"

            mock_data = {"call_id": "call_123", "status": "initiated"}
            MockService.return_value.initiate = AsyncMock(return_value=mock_data)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/management/outbound-calls",
                    json={
                        "agent_version_id": str(version.id),
                        "to_number": "+1234567890",
                        "from_number": "+0987654321",
                    },
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["call_id"] == "call_123"

            # Verify IDs were passed, not secrets
            call_args = MockService.return_value.initiate.call_args
            assert call_args.kwargs["organization_id"] == str(org.id)
            assert call_args.kwargs["agent_version_id"] == str(version.id)

        _cleanup()

    @pytest.mark.asyncio
    async def test_outbound_passes_per_call_retell_creds(self):
        # The CRM supplies the org's Retell key per call; LearningEngine forwards it to
        # the service (never stored) and accepts it even with no global key.
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.settings") as mock_settings,
            patch("learning_engine.api.v1.endpoints.management.OutboundCallService") as MockService,
        ):
            mock_settings.retell_api_key = ""  # no global key — per-call must suffice
            MockService.return_value.initiate = AsyncMock(
                return_value={"call_id": "call_789", "status": "initiated"}
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/management/outbound-calls",
                    json={
                        "agent_version_id": str(version.id),
                        "to_number": "+111",
                        "from_number": "+222",
                        "retell_api_key": "org-retell-key",
                        "retell_agent_id": "agent-abc",
                    },
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            call_args = MockService.return_value.initiate.call_args
            assert call_args.kwargs["api_key"] == "org-retell-key"
            assert call_args.kwargs["retell_agent_id"] == "agent-abc"

        _cleanup()

    @pytest.mark.asyncio
    async def test_outbound_returns_call_id(self):
        org = _override_org()
        version = _mock_version()

        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=mock_session),
            patch("learning_engine.api.v1.endpoints.management.settings") as mock_settings,
            patch("learning_engine.api.v1.endpoints.management.OutboundCallService") as MockService,
        ):
            mock_settings.retell_api_key = "test-key"
            MockService.return_value.initiate = AsyncMock(
                return_value={"call_id": "call_456", "status": "queued"}
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/management/outbound-calls",
                    json={
                        "agent_version_id": str(version.id),
                        "to_number": "+111",
                        "from_number": "+222",
                    },
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 200
            assert response.json()["call_id"] == "call_456"
            assert response.json()["status"] == "queued"

        _cleanup()

    @pytest.mark.asyncio
    async def test_outbound_no_retell_key_returns_400(self):
        org = _override_org()

        with patch("learning_engine.api.v1.endpoints.management.settings") as mock_settings:
            mock_settings.retell_api_key = ""

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/management/outbound-calls",
                    json={
                        "agent_version_id": str(uuid.uuid4()),
                        "to_number": "+111",
                        "from_number": "+222",
                    },
                    headers={"Authorization": f"Bearer {ORG_API_KEY}"},
                )

            assert response.status_code == 400
            assert "not configured" in response.json()["detail"]

        _cleanup()


# ==================== AUTH ====================


class TestAuth:
    @pytest.mark.asyncio
    async def test_management_no_auth_returns_401(self):
        _cleanup()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/management/agents")

        # FastAPI returns 422 for missing required header, but our dep returns 401
        assert response.status_code in (401, 422)

        _cleanup()

    @pytest.mark.asyncio
    async def test_management_invalid_key_returns_401(self):
        _cleanup()

        mock_session = _override_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/management/agents",
                headers={"Authorization": "Bearer invalid-key-12345678"},
            )

        assert response.status_code == 401

        _cleanup()
