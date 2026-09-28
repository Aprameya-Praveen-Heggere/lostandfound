import os
import secrets
from urllib.parse import urlencode
import httpx
import jwt
from app.core.config import settings
from app.models import IdentityProviderConfig

def make_state(institution_id:str)->tuple[str,str]:
    nonce=secrets.token_urlsafe(24)
    token=jwt.encode({"institution_id":institution_id,"nonce":nonce,"purpose":"oidc","exp":__import__('time').time()+600},settings.secret_key,algorithm="HS256")
    return token,nonce

def verify_state(state:str)->dict:
    payload=jwt.decode(state,settings.secret_key,algorithms=["HS256"])
    if payload.get("purpose")!="oidc" or not payload.get("nonce"):raise ValueError("Invalid OIDC state")
    return payload

def discovery(config:IdentityProviderConfig)->dict:
    response=httpx.get(config.issuer_url.rstrip("/")+"/.well-known/openid-configuration",timeout=10);response.raise_for_status();return response.json()

def authorization_url(config:IdentityProviderConfig)->str:
    metadata=discovery(config);state,nonce=make_state(config.institution_id)
    params={"client_id":config.client_id,"redirect_uri":settings.oidc_redirect_base+"/api/v1/sso/callback","response_type":"code","scope":config.scopes,"state":state,"nonce":nonce}
    return metadata["authorization_endpoint"]+"?"+urlencode(params)

def exchange(config:IdentityProviderConfig,code:str,state:str)->dict:
    state_data=verify_state(state)
    if state_data["institution_id"]!=config.institution_id:raise ValueError("OIDC institution mismatch")
    metadata=discovery(config);secret=os.getenv(config.client_secret_env)
    if not secret:raise RuntimeError("OIDC client secret is not configured")
    response=httpx.post(metadata["token_endpoint"],data={"grant_type":"authorization_code","code":code,"redirect_uri":settings.oidc_redirect_base+"/api/v1/sso/callback","client_id":config.client_id,"client_secret":secret},timeout=10);response.raise_for_status()
    token=response.json()["id_token"]
    claims=jwt.decode(token,jwt.PyJWKClient(metadata["jwks_uri"]).get_signing_key_from_jwt(token).key,algorithms=["RS256","ES256"],audience=config.client_id,issuer=config.issuer_url)
    if claims.get("nonce")!=state_data["nonce"]:raise ValueError("Invalid OIDC nonce")
    if not claims.get("email_verified",False):raise ValueError("OIDC email is not verified")
    return claims
