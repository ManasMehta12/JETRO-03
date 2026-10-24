"""Demo opaque sessions and production OIDC verification with RS256-only JWTs."""
import hashlib
import hmac
import json
import math
import time
from functools import lru_cache
from urllib.parse import urlparse
from urllib import request


class AuthError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class Actor(str):
    """Stable ownership key with explicit tenant and authorized application roles."""
    def __new__(cls, identity, *, tenant_id, roles):
        value = str.__new__(cls, identity)
        value.tenant_id = tenant_id
        value.roles = frozenset(roles)
        return value


def _configuration(settings):
    for name in ('oidc_issuer', 'oidc_jwks_url'):
        value = getattr(settings, name, '')
        parsed = urlparse(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise AuthError(503, 'identity_not_configured', 'A valid HTTPS OIDC issuer and JWKS URL are required')
    if not getattr(settings, 'oidc_audience', ''):
        raise AuthError(503, 'identity_not_configured', 'An OIDC audience is required')


class NoIdentityRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # JWKS URLs must resolve directly. A redirect may downgrade trust to HTTP.
        return None


@lru_cache(maxsize=8)
def _jwks_client(url):
    try:
        import jwt
    except ImportError as exc:
        raise AuthError(503, 'identity_not_configured', 'OIDC verification dependency is unavailable') from exc
    class VerifiedTransportClient(jwt.PyJWKClient):
        def fetch_data(self):
            data = None
            try:
                opener = request.build_opener(NoIdentityRedirect())
                with opener.open(request.Request(self.uri, headers=self.headers), timeout=5) as response:
                    encoded = response.read(1_000_001)
                if len(encoded) > 1_000_000:
                    raise ValueError('JWKS body exceeds limit')
                data = json.loads(encoded)
                if not isinstance(data, dict) or not isinstance(data.get('keys'), list):
                    raise ValueError('Invalid JWKS document')
                return data
            finally:
                if self.jwk_set_cache is not None:
                    self.jwk_set_cache.put(data)
    return VerifiedTransportClient(url, cache_jwk_set=True, lifespan=300, timeout=5)


def _verify_oidc(token, settings):
    _configuration(settings)
    try:
        import jwt
        # get_signing_key_from_jwt only selects a key. decode below establishes trust.
        key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=settings.oidc_audience,
                            issuer=settings.oidc_issuer, leeway=30,
                            options={'require': ['exp', 'iat', 'sub', 'aud', 'iss'],
                                     'verify_signature': True, 'verify_exp': True,
                                     'verify_iat': True, 'verify_aud': True, 'verify_iss': True})
    except ImportError as exc:
        raise AuthError(503, 'identity_not_configured', 'OIDC verification dependency is unavailable') from exc
    except AuthError:
        raise
    except Exception as exc:
        # Do not expose JWT text, remote key material, or network details.
        raise AuthError(401, 'unauthenticated', 'A valid bearer session is required') from exc
    return actor_from_claims(claims, settings)


def actor_from_claims(claims, settings):
    """Validate application claims after cryptographic verification.

    Public for claim-policy tests; callers must never use this function as a
    replacement for resolve_actor on an unverified browser-supplied dictionary.
    """
    now = time.time()
    required = ('exp', 'iat', 'sub', 'aud', 'iss')
    if not isinstance(claims, dict) or any(name not in claims for name in required):
        raise AuthError(401, 'unauthenticated', 'Required identity claims are missing')
    audience = claims.get('aud')
    audiences = audience if isinstance(audience, list) else [audience]
    if claims.get('iss') != settings.oidc_issuer or settings.oidc_audience not in audiences:
        raise AuthError(401, 'unauthenticated', 'Identity issuer or audience is invalid')
    for name in ('exp', 'iat'):
        if not isinstance(claims[name], (int, float)) or isinstance(claims[name], bool) or not math.isfinite(claims[name]):
            raise AuthError(401, 'unauthenticated', 'Identity timestamps are invalid')
    if claims['exp'] <= now - 30 or claims['iat'] > now + 30 or claims['exp'] <= claims['iat']:
        raise AuthError(401, 'unauthenticated', 'Identity token is expired or not yet valid')
    tenant = claims.get(getattr(settings, 'oidc_tenant_claim', 'tenant_id'))
    subject = claims.get('sub')
    if not isinstance(tenant, str) or not tenant.strip() or not isinstance(subject, str) or not subject.strip():
        raise AuthError(401, 'unauthenticated', 'A tenant and subject are required')
    roles = claims.get(getattr(settings, 'oidc_roles_claim', 'roles'))
    recognized = frozenset({'learner', 'reviewer', 'expert', 'operator'})
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise AuthError(403, 'forbidden_role', 'Application roles are required')
    roles = recognized.intersection(roles)
    if not roles:
        raise AuthError(403, 'forbidden_role', 'No authorized application role was granted')
    identity = 'oidc:' + hashlib.sha256((settings.oidc_issuer + '\0' + tenant + '\0' + subject).encode()).hexdigest()
    return Actor(identity, tenant_id=tenant, roles=roles)


def resolve_actor(authorization, settings):
    if not authorization or not authorization.startswith('Bearer ') or not authorization[7:].strip():
        raise AuthError(401, 'unauthenticated', 'A valid bearer session is required')
    token = authorization[7:]
    if len(token) > 16000 or token != token.strip():
        raise AuthError(401, 'unauthenticated', 'A valid bearer session is required')
    if settings.demo_database:
        for expected, identity in settings.demo_tokens.items():
            if hmac.compare_digest(token, expected):
                roles = {'operator'} if identity == 'operator' else {'learner'}
                return Actor(identity, tenant_id='demo', roles=roles)
        raise AuthError(401, 'unauthenticated', 'A valid bearer session is required')
    _configuration(settings)
    return _verify_oidc(token, settings)
