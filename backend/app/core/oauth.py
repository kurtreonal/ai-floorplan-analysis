from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App

from app.core.config import OAuthOIDCConfiguration


OAUTH_CLIENT_REGISTRY_NAME = "configured_oidc"


def create_oauth_client(
    configuration: OAuthOIDCConfiguration,
) -> StarletteOAuth2App:
    oauth = OAuth()
    oauth.register(
        name=OAUTH_CLIENT_REGISTRY_NAME,
        client_id=configuration.client_id,
        client_secret=configuration.client_secret.get_secret_value(),
        server_metadata_url=str(configuration.discovery_url),
        client_kwargs={"scope": " ".join(configuration.scopes)},
    )
    client = oauth.create_client(OAUTH_CLIENT_REGISTRY_NAME)
    if client is None:
        raise RuntimeError("The configured OAuth/OIDC client could not be created.")
    return client
