"""Offline API/authorization tests. SQLite checks query scope, not PG triggers."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sahayak.api.auth import Principal, CognitoVerifier, validate_claims
from sahayak.api.config import Settings
from sahayak.api.main import create_app
from sahayak.api.models import Base, Profile, ProfileRole, Ticket
from sahayak.api.schemas import NewTicket, Outcome
from sahayak.api import service

SETTINGS = Settings(_env_file=None)


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {"iss": SETTINGS.issuer, "sub": "employee-one", "iat": now,
              "exp": now + timedelta(minutes=15), "token_use": "access",
              "client_id": SETTINGS.cognito_client_id, "scope": "openid email profile",
              "cognito:groups": ["employee"]}
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def test_access_token_accepts_correct_client(signing_key):
    principal = validate_claims(token(signing_key), signing_key.public_key(), SETTINGS)
    assert principal.subject == "employee-one"
    assert principal.groups == frozenset({"employee"})


@pytest.mark.parametrize("override", [
    {"token_use":"id"}, {"client_id":"someone-else"}, {"iss":"https://attacker.invalid"},
    {"exp":0}, {"scope":"email"}, {"cognito:groups":"engineer"}, {"sub":123},
])
def test_bad_claims_rejected(signing_key, override):
    with pytest.raises(jwt.PyJWTError):
        validate_claims(token(signing_key, **override), signing_key.public_key(), SETTINGS)


def test_invalid_signature_rejected(signing_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(jwt.PyJWTError):
        validate_claims(token(other), signing_key.public_key(), SETTINGS)


def test_revoked_token_denied_online(signing_key):
    verifier = CognitoVerifier(SETTINGS)
    verifier.keys = Mock()
    verifier.keys.get_signing_key_from_jwt.return_value.key = signing_key.public_key()
    verifier.http.close()
    verifier.http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(401)))
    with pytest.raises(HTTPException) as error:
        verifier.verify(token(signing_key))
    assert error.value.status_code == 401
    verifier.close()


def test_provider_outage_fails_closed(signing_key):
    verifier = CognitoVerifier(SETTINGS)
    verifier.keys = Mock()
    verifier.keys.get_signing_key_from_jwt.return_value.key = signing_key.public_key()
    verifier.http.close()
    verifier.http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(503)))
    with pytest.raises(HTTPException) as error:
        verifier.verify(token(signing_key))
    assert error.value.status_code == 503
    verifier.close()


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread":False},
                           execution_options={"schema_translate_map":{"sahayak":None}})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def profile(db, subject, roles=("employee",), active=True):
    p = Profile(id=uuid4(), identity_issuer=SETTINGS.issuer, identity_subject=subject,
                employee_code=subject, display_name=subject, active=active, is_test=False,
                phone_e164="+919999999999", phone_trusted_at=datetime.now(timezone.utc))
    db.add(p)
    for role in roles:
        db.add(ProfileRole(profile_id=p.id, role=role))
    db.commit()
    return p


def ticket(db, employee, number, status="new", assignee=None):
    now = datetime.now(timezone.utc)
    t = Ticket(id=uuid4(), ticket_number=number, employee_id=employee.id,
       request_key=uuid4(), category="vpn", description="VPN disconnects", priority="medium",
       status=status, version=1, schedule_generation=1, is_test=False,
       assigned_engineer_id=assignee, created_at=now, updated_at=now)
    db.add(t); db.commit()
    return t


def actor(db, p, groups=("employee",)):
    return service.actor_for(db, Principal(SETTINGS.issuer, p.identity_subject, frozenset(groups)))


def test_employee_can_only_read_own_tickets(db):
    one, two = profile(db,"one"), profile(db,"two")
    mine, theirs = ticket(db,one,1), ticket(db,two,2)
    a = actor(db,one)
    assert [t.id for t in service.tickets(db,a,None,None)] == [mine.id]
    with pytest.raises(HTTPException) as error:
        service.ticket(db,a,theirs.id)
    assert error.value.status_code == 404


def test_engineer_can_read_all_with_pagination(db):
    one, two = profile(db,"one"), profile(db,"two")
    eng = profile(db,"eng",("engineer","portal_admin"))
    ticket(db,one,1); ticket(db,two,2)
    a = actor(db,eng,("engineer","portal_admin"))
    assert [t.ticket_number for t in service.tickets(db,a,None,None)] == [2,1]
    assert [t.ticket_number for t in service.tickets(db,a,None,2)] == [1]


def test_stale_group_cannot_restore_removed_database_role(db):
    p = profile(db,"one")
    a = actor(db,p,("employee","engineer"))
    assert not a.engineer


def test_disabled_profile_denied(db):
    p = profile(db,"one",active=False)
    with pytest.raises(HTTPException) as error: actor(db,p)
    assert error.value.status_code == 403


def test_directory_engineer_without_token_group_denied(db):
    p = profile(db,"eng",("engineer",))
    with pytest.raises(HTTPException): actor(db,p,("employee",))


def test_employee_cannot_claim_or_resolve(db):
    p = profile(db,"one"); t = ticket(db,p,1,"transferred_to_human")
    a = actor(db,p)
    with pytest.raises(HTTPException) as e: service.claim_ticket(db,a,t.id,1)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        service.record_outcome(db,a,t.id,Outcome(expected_version=1,status="completed",note="Fixed"))
    assert e.value.status_code == 403


@pytest.mark.parametrize("status", ["new","in_progress","completed","failed","cancelled"])
def test_engineer_cannot_claim_non_escalated_ticket(db,status):
    p = profile(db,"one"); eng = profile(db,"eng",("engineer",))
    t = ticket(db,p,1,status)
    with pytest.raises(HTTPException) as e: service.claim_ticket(db,actor(db,eng,("engineer",)),t.id,1)
    assert e.value.status_code == 409


def test_other_engineer_cannot_steal_or_resolve(db):
    p = profile(db,"one"); a = profile(db,"a",("engineer",)); b = profile(db,"b",("engineer",))
    t = ticket(db,p,1,"transferred_to_human",a.id)
    who = actor(db,b,("engineer",))
    with pytest.raises(HTTPException) as e: service.claim_ticket(db,who,t.id,1)
    assert e.value.status_code == 409
    with pytest.raises(HTTPException) as e:
        service.record_outcome(db,who,t.id,Outcome(expected_version=1,status="failed",note="Cannot resolve"))
    assert e.value.status_code == 403


def test_idempotent_claim_does_not_write_again(db):
    p=profile(db,"one"); eng=profile(db,"eng",("engineer",))
    t=ticket(db,p,1,"transferred_to_human",eng.id)
    result=service.claim_ticket(db,actor(db,eng,("engineer",)),t.id,1)
    assert result.id == t.id and not db.dirty


def test_client_cannot_supply_identity_priority_or_unknown_status():
    with pytest.raises(ValueError):
        NewTicket(request_key=uuid4(),category="vpn",description="Issue",employee_id=str(uuid4()),priority="critical")
    with pytest.raises(ValueError): Outcome(expected_version=1,status="in_progress",note="Changed")
    with pytest.raises(ValueError): Outcome(expected_version=1,status="completed",note="   ")


def test_api_denies_missing_auth_without_using_database():
    verifier=Mock()
    with TestClient(create_app(SETTINGS,verifier=verifier)) as client:
        response=client.get("/api/tickets")
        assert response.status_code == 401
    verifier.verify.assert_not_called()


def test_api_does_not_leak_validation_inputs(db):
    p=profile(db,"one")
    verifier=Mock(); verifier.verify.return_value=Principal(SETTINGS.issuer,"one",frozenset({"employee"}))
    app=create_app(SETTINGS,verifier=verifier)
    app.dependency_overrides[app.state.database_dependency]=lambda: db
    with TestClient(app) as client:
        response=client.post("/api/tickets",headers={"Authorization":"Bearer test"},json={"password":"DO-NOT-LEAK"})
    assert response.status_code==422 and "DO-NOT-LEAK" not in response.text


def test_api_ownership_enforced_on_direct_detail_url(db):
    p=profile(db,"one"); other=profile(db,"two"); t=ticket(db,other,1)
    verifier=Mock(); verifier.verify.return_value=Principal(SETTINGS.issuer,"one",frozenset({"employee"}))
    app=create_app(SETTINGS,verifier=verifier)
    app.dependency_overrides[app.state.database_dependency]=lambda: db
    with TestClient(app) as client:
        result=client.get(f"/api/tickets/{t.id}",headers={"Authorization":"Bearer test"})
    assert result.status_code==404
