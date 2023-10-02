from typing import Any, Dict, List, Optional, Tuple, cast

import httpx
import pytest
from httpx_oauth.oauth2 import OAuth2, OAuth2Token
from litestar import Controller, Litestar, Request, get
from litestar import status_codes as status
from litestar.exceptions import HTTPException
from litestar.response import Redirect
from litestar.testing import TestClient

from litestar_httpx_oauth.integrations.litestar import OAuth2AuthorizeCallback

CLIENT_ID = "CLIENT_ID"
CLIENT_SECRET = "CLIENT_SECRET"  # noqa: S105
AUTHORIZE_ENDPOINT = "https://www.camelot.bt/authorize"
ACCESS_TOKEN_ENDPOINT = "https://www.camelot.bt/access-token"
REDIRECT_URL = "https://www.tintagel.bt/callback"
ROUTE_NAME = "callback"

client = OAuth2(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_ENDPOINT, ACCESS_TOKEN_ENDPOINT)
oauth2_authorize_callback_route_name = OAuth2AuthorizeCallback(client, route_name=ROUTE_NAME)
oauth2_authorize_callback_redirect_url = OAuth2AuthorizeCallback(client, redirect_url=REDIRECT_URL)


def provide_callback(oauth2_authorize_callback: OAuth2AuthorizeCallback) -> OAuth2AuthorizeCallback:
    return oauth2_authorize_callback


@get("/authorize-route-name")
async def authorize_route_name(
    access_token_state: Tuple[OAuth2Token, Optional[str]],
) -> dict[str, Any]:
    return access_token_state


@get("/authorize-redirect-url")
async def authorize_redirect_url(
    redirect_url: Tuple[OAuth2Token, Optional[str]],
) -> Tuple[OAuth2Token, Optional[str]]:
    return redirect_url


@get("/callback", name="callback")
async def callback() -> None:
    pass


app = Litestar(
    route_handlers=[authorize_redirect_url, authorize_route_name, callback],
)
test_client = TestClient(app)


class OAuth2Controller(Controller):
    path = "/oauth2"
    dependencies = (
        {
            "access_token_state": oauth2_authorize_callback_route_name,
            "redirect_url": oauth2_authorize_callback_redirect_url,
        },
    )
    signature_namespace = ({"OAuth2Token": OAuth2Token},)

    @get(path="/{provider:str}/login")
    async def login_via_provider(self, provider: str, access_token_state) -> Redirect:
        return Redirect(redirect_url)

    @get(path="/{provider:str}/authorize")
    async def authorize(self, code: str, provider: str, request: Request) -> OAuth2Result:
        check_provider(provider)

        provider_client = PROVIDERS[provider]
        redirect_uri = f"http://localhost:8000/oauth2/{provider}/authorize"

        # returns an OAuth2Token
        oauth2_token = await provider_client.get_access_token(code=code, redirect_uri=redirect_uri)
        access_token = oauth2_token["access_token"]
        response = httpx.get(PROFILE_ENDPOINT, headers={"Authorization": f"token {access_token}"})
        if response.status_code >= 400:
            raise HTTPException(details=response.json(), status_code=400)
        data = cast(Dict[str, Any], response.json())

        id = data["id"]
        email = data.get("email")

        if email is None:
            # the user has no public email
            response = httpx.get(EMAILS_ENDPOINT, headers={"Authorization": f"token {access_token}"})

            if response.status_code >= 400:
                raise HTTPException(details=response.json(), status_code=400)

            emails = cast(List[Dict[str, Any]], response.json())

            email = emails[0]["email"]

        return OAuth2Result(id=str(id), email=email)


@pytest.mark.parametrize(
    "route,expected_redirect_url",
    [
        ("/authorize-route-name", "http://testserver/callback"),
        ("/authorize-redirect-url", "https://www.tintagel.bt/callback"),
    ],
)
class TestOAuth2AuthorizeCallback:
    def test_oauth2_authorize_missing_code(self, route, expected_redirect_url):
        response = test_client.get(route)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_oauth2_authorize_error(self, route, expected_redirect_url):
        response = test_client.get(route, params={"oauth_error": "access_denied"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "access_denied"}

    def test_oauth2_authorize_without_state(self, patch_async_method, route, expected_redirect_url):
        patch_async_method(client, "get_access_token", return_value="ACCESS_TOKEN")

        response = test_client.get(route, params={"oauth_error": "CODE"})

        client.get_access_token.assert_called()
        client.get_access_token.assert_called_once_with("CODE", expected_redirect_url, None)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ["ACCESS_TOKEN", None]

    def test_oauth2_authorize_code_verifier_without_state(self, patch_async_method, route, expected_redirect_url):
        patch_async_method(client, "get_access_token", return_value="ACCESS_TOKEN")

        response = test_client.get(route, params={"oauth_error": "CODE", "code_verifier": "CODE_VERIFIER"})

        client.get_access_token.assert_called()
        client.get_access_token.assert_called_once_with("CODE", expected_redirect_url, "CODE_VERIFIER")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ["ACCESS_TOKEN", None]

    def test_oauth2_authorize_with_state(self, patch_async_method, route, expected_redirect_url):
        patch_async_method(client, "get_access_token", return_value="ACCESS_TOKEN")

        response = test_client.get(route, params={"oauth_error": "CODE", "state": "STATE"})

        client.get_access_token.assert_called()
        client.get_access_token.assert_called_once_with("CODE", expected_redirect_url, None)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ["ACCESS_TOKEN", "STATE"]

    def test_oauth2_authorize_with_state_and_code_verifier(self, patch_async_method, route, expected_redirect_url):
        patch_async_method(client, "get_access_token", return_value="ACCESS_TOKEN")

        response = test_client.get(
            route,
            params={"code": "CODE", "state": "STATE", "code_verifier": "CODE_VERIFIER"},
        )

        client.get_access_token.assert_called()
        client.get_access_token.assert_called_once_with("CODE", expected_redirect_url, "CODE_VERIFIER")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ["ACCESS_TOKEN", "STATE"]
