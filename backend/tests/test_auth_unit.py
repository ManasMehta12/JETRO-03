"""Authentication policy tests written before OIDC implementation."""
import time
import importlib.util
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.auth import Actor, AuthError, NoIdentityRedirect, actor_from_claims, resolve_actor


class AuthenticationTests(unittest.TestCase):
    def settings(self, **kw):
        defaults = dict(demo_database=True, demo_tokens={'demo-secret': 'learner-1', 'operator-secret': 'operator'},
                        oidc_issuer='https://identity.example', oidc_audience='viva-api',
                        oidc_jwks_url='https://identity.example/.well-known/jwks.json',
                        oidc_tenant_claim='tenant_id', oidc_roles_claim='roles')
        return SimpleNamespace(**{**defaults, **kw})

    def claims(self, **kw):
        now = int(time.time())
        return {**{'sub':'user-1', 'iss':'https://identity.example', 'aud':'viva-api',
                   'exp':now + 300, 'iat':now, 'tenant_id':'tenant-a', 'roles':['learner']}, **kw}

    def test_demo_tokens_constant_time_policy_and_roles(self):
        actor = resolve_actor('Bearer demo-secret', self.settings())
        self.assertIsInstance(actor, Actor)
        self.assertEqual(actor, 'learner-1')
        self.assertEqual(actor.tenant_id, 'demo')
        self.assertIn('learner', actor.roles)
        self.assertIn('operator', resolve_actor('Bearer operator-secret', self.settings()).roles)

    def test_missing_malformed_and_unknown_demo_tokens_fail(self):
        for header in (None, 'demo-secret', 'Basic demo-secret', 'Bearer bad', 'Bearer '):
            with self.assertRaises(AuthError) as caught:
                resolve_actor(header, self.settings())
            self.assertEqual(caught.exception.status, 401)

    def test_production_never_accepts_static_demo_token(self):
        with patch('app.auth._verify_oidc', side_effect=AuthError(401, 'unauthenticated', 'Invalid token')) as verify:
            with self.assertRaises(AuthError):
                resolve_actor('Bearer demo-secret', self.settings(demo_database=False))
            verify.assert_called_once()

    def test_production_actor_partition_includes_issuer_tenant_and_subject(self):
        first = actor_from_claims(self.claims(), self.settings())
        second = actor_from_claims(self.claims(tenant_id='tenant-b'), self.settings())
        third = actor_from_claims(self.claims(sub='user-2'), self.settings())
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertTrue(first.startswith('oidc:'))
        self.assertEqual(first.tenant_id, 'tenant-a')
        self.assertEqual(first.roles, frozenset({'learner'}))

    def test_missing_or_invalid_identity_claims_are_rejected(self):
        for changed in ({'tenant_id':''}, {'sub':''}, {'roles':['unknown']}, {'roles':'learner'},
                        {'exp':0}, {'iat':int(time.time()) + 3600}, {'aud':'other-api'},
                        {'iss':'https://attacker.example'}, {'exp':'never'}, {'exp':float('nan')}):
            with self.assertRaises(AuthError):
                actor_from_claims(self.claims(**changed), self.settings())
        for claim in ('sub', 'iss', 'aud', 'exp', 'iat'):
            claims = self.claims()
            del claims[claim]
            with self.assertRaises(AuthError):
                actor_from_claims(claims, self.settings())

    def test_audience_list_and_recognized_roles(self):
        actor = actor_from_claims(self.claims(aud=['other', 'viva-api'], roles=['operator', 'reviewer']), self.settings())
        self.assertEqual(actor.roles, frozenset({'operator', 'reviewer'}))

    def test_production_requires_https_jwks_and_issuer(self):
        for kw in ({'oidc_jwks_url':'http://identity.example/keys'}, {'oidc_issuer':'http://identity.example'},
                   {'oidc_jwks_url':'https://user:password@identity.example/keys'}, {'oidc_audience':''}):
            with self.assertRaises(AuthError) as caught:
                resolve_actor('Bearer ey.invalid.jwt', self.settings(demo_database=False, **kw))
            self.assertEqual(caught.exception.status, 503)


    def test_jwks_endpoint_redirects_are_refused(self):
        from urllib.request import Request
        handler = NoIdentityRedirect()
        self.assertIsNone(handler.redirect_request(Request('https://identity.example/keys'), None, 302, 'Found', {}, 'http://attacker.example/keys'))

    def test_oidc_verifier_enforces_signature_algorithm_claim_requirements(self):
        captured = {}
        def decode(token, key, **kwargs):
            captured.update(kwargs)
            return self.claims()
        fake_jwt = SimpleNamespace(decode=decode)
        client = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key='public-key'))
        with patch.dict(sys.modules, {'jwt': fake_jwt}), patch('app.auth._jwks_client', return_value=client):
            actor = resolve_actor('Bearer signed-token', self.settings(demo_database=False))
        self.assertEqual(actor.tenant_id, 'tenant-a')
        self.assertEqual(captured['algorithms'], ['RS256'])
        self.assertTrue(captured['options']['verify_signature'])
        self.assertEqual(set(captured['options']['require']), {'exp','iat','sub','aud','iss'})
        self.assertEqual(captured['issuer'], 'https://identity.example')
        self.assertEqual(captured['audience'], 'viva-api')

    @unittest.skipUnless(importlib.util.find_spec('jwt') and importlib.util.find_spec('cryptography'), 'PyJWT/cryptography dependencies unavailable')
    def test_real_rs256_signature_and_algorithm_are_verified(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(self.claims(), private_key, algorithm='RS256', headers={'kid':'test'})
        client = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private_key.public_key()))
        with patch('app.auth._jwks_client', return_value=client):
            self.assertIn('learner', resolve_actor('Bearer ' + token, self.settings(demo_database=False)).roles)
            tampered = jwt.encode(self.claims(), wrong_key, algorithm='RS256')
            with self.assertRaises(AuthError):
                resolve_actor('Bearer ' + tampered, self.settings(demo_database=False))
            symmetric = jwt.encode(self.claims(), 'not-an-rsa-key', algorithm='HS256')
            with self.assertRaises(AuthError):
                resolve_actor('Bearer ' + symmetric, self.settings(demo_database=False))


if __name__ == '__main__':
    unittest.main()
