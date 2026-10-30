"""OAuth failures stay fail-closed, with friendly browser navigation and JSON APIs."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from starlette.responses import RedirectResponse

from app.core.config import Settings
from app.core.database import get_db
from app.main import create_app
from app.core.auth_errors import AuthQueryRedactor


@pytest.fixture
def setup():
    application=create_app(Settings(_env_file=None,app_env='production',
        auto_start_interpretation_worker=False,frontend_url='http://localhost:5173',
        oauth_provider='synthetic',oauth_client_id='navigation-test-client',
        oauth_client_secret='navigation-test-secret',oauth_redirect_uri='http://localhost:8000/api/auth/callback',
        oauth_discovery_url='https://provider.invalid/.well-known/openid-configuration',
        oauth_scopes='openid profile email',session_secret='navigation-test-session-secret'))
    database=MagicMock()
    application.dependency_overrides[get_db]=lambda:database
    provider=AsyncMock()
    provider.authorize_redirect.return_value=RedirectResponse('https://provider.invalid/authorize')
    provider.authorize_access_token.return_value={'userinfo':{'sub':'synthetic-subject'}}
    with TestClient(application,base_url='https://testserver') as client,patch('app.api.routes.auth.create_oauth_client',return_value=provider):
        client.get('/api/auth/login',follow_redirects=False)
        state=provider.authorize_redirect.await_args.kwargs['state']
        yield client,application,database,provider,state


@pytest.mark.parametrize('accept,html', [('text/html,application/xhtml+xml',True),
    ('application/json',False),('*/*',False),('text/html;q=0,application/json',False)])
def test_database_failure_never_authenticates_or_leaks_and_browser_leaves_raw_callback(setup,accept,html,caplog):
    client,_,database,_,state=setup
    failure=OperationalError('private SQL',{},Exception(1044,'private-secret-and-identity'))
    with patch('app.api.routes.auth.resolve_external_user',side_effect=failure):
        response=client.get(f'/api/auth/callback?state={state}&code=private-code&return_url=https://evil.invalid',
            headers={'Accept':accept},follow_redirects=False)
    if html:
        assert response.status_code==303
        assert response.headers['location']=='http://localhost:5173#/signin?auth_error=service-unavailable'
        assert response.headers['cache-control']=='no-store'
        assert response.headers['referrer-policy']=='no-referrer'
    else:
        assert response.status_code==503
        assert response.json()['detail']['error']['code']=='AUTH_USER_RESOLUTION_FAILED'
    assert 'private-' not in response.text and 'private-' not in caplog.text
    database.rollback.assert_called_once()
    database.commit.assert_not_called()
    assert client.get('/api/auth/me').status_code==401


def test_invalid_browser_state_still_rejects_before_provider_exchange(setup):
    client,_,_,provider,_=setup
    response=client.get('/api/auth/callback?state=incorrect&code=private-code',
        headers={'Accept':'text/html'},follow_redirects=False)
    assert response.status_code==303 and response.headers['location'].endswith('auth_error=signin-failed')
    provider.authorize_access_token.assert_not_awaited()


def test_provider_and_configuration_failure_use_static_friendly_reasons(setup):
    client,app,_,provider,_=setup
    provider.authorize_redirect.side_effect=RuntimeError('private-provider-details')
    response=client.get('/api/auth/login',headers={'Accept':'text/html'},follow_redirects=False)
    assert response.status_code==303 and response.headers['location'].endswith('auth_error=provider-unavailable')
    app.state.oauth_oidc_configuration=None
    response=client.get('/api/auth/login',headers={'Accept':'text/html'},follow_redirects=False)
    assert response.status_code==303 and response.headers['location'].endswith('auth_error=service-unavailable')


def test_success_retains_original_redirect_and_session(setup):
    client,_,database,_,state=setup
    user=SimpleNamespace(id=42,display_name='Synthetic designer',email=None,avatar_url=None,
        role=SimpleNamespace(name='DESIGNER'))
    with patch('app.api.routes.auth.resolve_external_user',return_value=(user,False)):
        response=client.get(f'/api/auth/callback?state={state}&code=synthetic',follow_redirects=False)
    assert response.status_code==303 and response.headers['location']=='http://localhost:5173'
    database.commit.assert_called_once()
    with patch('app.api.dependencies.resolve_current_user',return_value=user):
        assert client.get('/api/auth/me').json()['id']==42


def test_api_lookup_failure_stays_json_even_when_browser_accepts_html(setup):
    client,_,_,_,_=setup
    response=client.get('/api/auth/me',headers={'Accept':'text/html'},follow_redirects=False)
    assert response.status_code==401
    assert response.headers['content-type'].startswith('application/json')


def test_access_logs_never_include_oauth_query_values():
    import logging
    record=logging.LogRecord('uvicorn.access',logging.INFO,'',0,'%s - "%s %s HTTP/%s" %s',
        ('local','GET','/api/auth/callback?code=private-code&state=private-state','1.1',503),None)
    assert AuthQueryRedactor().filter(record)
    assert 'private-' not in record.getMessage()
    assert '/api/auth/callback HTTP/' in record.getMessage()
