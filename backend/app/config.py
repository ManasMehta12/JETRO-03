"""Server-only configuration with explicit offline fixture mode."""
import json
import os
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class Settings:
    database_url: str = 'sqlite:///./viva-demo.db'
    provider_mode: str = 'fixture'
    demo_database: bool = True
    seed_demo: bool = True
    run_inline_worker: bool = True
    allowed_origin: str = 'http://localhost:3000'
    max_active_seconds: int = 600
    session_expiry_seconds: int = 86400
    retention_days: int = 30
    max_context_tokens: int = 12000
    provider_timeout: float = 20.0
    evaluation_retry_limit: int = 3
    openai_api_key: str = ''
    voice_model: str = 'gpt-realtime'
    text_model: str = 'gpt-4.1-mini'
    provider_base_url: str = 'https://api.openai.com/v1'
    media_directory: str = './media'
    session_spend_cap: float = 1.0
    pricing_json: dict = field(default_factory=dict)
    oidc_issuer: str = ''
    oidc_audience: str = ''
    oidc_jwks_url: str = ''
    oidc_tenant_claim: str = 'tenant_id'
    oidc_roles_claim: str = 'roles'
    demo_tokens: Dict[str, str] = field(default_factory=lambda: {'demo-learner-token':'learner-1', 'demo-other-token':'learner-2', 'demo-operator-token':'operator'})

    def __post_init__(self):
        if self.provider_mode not in ('fixture', 'openai'):
            raise ValueError('VIVA_PROVIDER_MODE must be fixture or openai')
        if not self.demo_database and (self.seed_demo or self.provider_mode == 'fixture'):
            raise ValueError('Production configuration requires seed_demo=false and provider_mode=openai')
        if not self.demo_database:
            if self.demo_tokens:
                raise ValueError('Production uses OIDC only: set VIVA_DEMO_TOKENS={} and disable demo seeding')
            from .auth import _configuration, AuthError
            try:
                _configuration(self)
            except AuthError as exc:
                raise ValueError(exc.message) from exc
        if not isinstance(self.demo_tokens, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in self.demo_tokens.items()):
            raise ValueError('Demo tokens must map nonempty opaque strings to actor IDs')
        if self.retention_days <= 0:
            raise ValueError('Retention days must be positive')
        if self.max_active_seconds <= 0 or self.max_context_tokens <= 0:
            raise ValueError('Time and context limits must be positive')

    @classmethod
    def from_env(cls):
        def flag(name, default):
            return os.getenv(name, str(default)).lower() in ('1','true','yes')
        return cls(database_url=os.getenv('VIVA_DATABASE_URL','sqlite:///./viva-demo.db'),
            provider_mode=os.getenv('VIVA_PROVIDER_MODE','fixture'), demo_database=flag('VIVA_DEMO_DATABASE',True),
            seed_demo=flag('VIVA_SEED_DEMO',True), run_inline_worker=flag('VIVA_RUN_INLINE_WORKER',True),
            allowed_origin=os.getenv('VIVA_ALLOWED_ORIGIN','http://localhost:3000'),
            max_active_seconds=int(os.getenv('VIVA_MAX_ACTIVE_SECONDS','600')),
            session_expiry_seconds=int(os.getenv('VIVA_SESSION_EXPIRY_SECONDS','86400')),
            retention_days=int(os.getenv('VIVA_RETENTION_DAYS','30')),
            max_context_tokens=int(os.getenv('VIVA_MAX_CONTEXT_TOKENS','12000')),
            provider_timeout=float(os.getenv('VIVA_PROVIDER_TIMEOUT','20')),
            evaluation_retry_limit=int(os.getenv('VIVA_EVALUATION_RETRY_LIMIT','3')),
            openai_api_key=os.getenv('OPENAI_API_KEY',''), voice_model=os.getenv('VIVA_VOICE_MODEL','gpt-realtime'),
            text_model=os.getenv('VIVA_TEXT_MODEL','gpt-4.1-mini'),
            provider_base_url=os.getenv('VIVA_PROVIDER_BASE_URL','https://api.openai.com/v1'),
            media_directory=os.getenv('VIVA_MEDIA_DIRECTORY','./media'),
            session_spend_cap=float(os.getenv('VIVA_SESSION_SPEND_CAP','1')),
            pricing_json=json.loads(os.getenv('VIVA_PRICING_JSON','{}')),
            oidc_issuer=os.getenv('VIVA_OIDC_ISSUER',''), oidc_audience=os.getenv('VIVA_OIDC_AUDIENCE',''),
            oidc_jwks_url=os.getenv('VIVA_OIDC_JWKS_URL',''),
            oidc_tenant_claim=os.getenv('VIVA_OIDC_TENANT_CLAIM','tenant_id'),
            oidc_roles_claim=os.getenv('VIVA_OIDC_ROLES_CLAIM','roles'),
            demo_tokens=json.loads(os.getenv('VIVA_DEMO_TOKENS','{"demo-learner-token":"learner-1","demo-other-token":"learner-2","demo-operator-token":"operator"}')))
