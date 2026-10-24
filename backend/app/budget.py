"""Persistent per-session reservations with explicit dated USD pricing.

Reservations are conservative maxima, committed before paid network calls. An
unknown network outcome retains that maximum as consumed usage. No rates are
inferred from model names, and cached-token discounts are not assumed.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any
from sqlalchemy import select, func, text
from .models import ProviderUsage, VivaSession, uid, now
from . import service

MICROS=Decimal('1000000')

@dataclass(frozen=True)
class Pricing:
    version:str
    effective_date:str
    currency:str
    text_input_per_million:Decimal
    text_output_per_million:Decimal
    audio_per_minute:Decimal

@dataclass(frozen=True)
class Reservation:
    database:Any
    id:str
    session_id:str
    reserved_cost:Decimal
    price_version:str


def _amount(value):
    try:
        parsed=Decimal(str(value))
        if not parsed.is_finite() or parsed<0:raise ValueError()
        return parsed
    except (InvalidOperation,ValueError,TypeError):
        raise service.DomainError(503,'pricing_not_configured','Explicit finite nonnegative provider pricing is required') from None


def parse_pricing(settings):
    raw=getattr(settings,'pricing_json',{})
    try:
        if not isinstance(raw,dict) or raw.get('currency')!='USD' or not isinstance(raw.get('version'),str) or not raw['version'].strip():raise ValueError()
        effective=raw['effective_date']
        date.fromisoformat(effective)
        return Pricing(raw['version'],effective,'USD',_amount(raw['text_input_per_million']),_amount(raw['text_output_per_million']),_amount(raw['audio_per_minute']))
    except (KeyError,TypeError,ValueError):
        raise service.DomainError(503,'pricing_not_configured','Configure versioned dated USD provider rates before live calls') from None


def _tokens(value):
    if type(value) is not int or value<0:raise service.DomainError(503,'invalid_provider_usage','Provider token usage is invalid')
    return Decimal(value)


def estimate_text(settings,input_tokens,max_output_tokens):
    pricing=parse_pricing(settings)
    return (_tokens(input_tokens)*pricing.text_input_per_million + _tokens(max_output_tokens)*pricing.text_output_per_million)/MICROS


def text_cost(settings,usage):
    return estimate_text(settings,usage.get('input_tokens',0),usage.get('output_tokens',0))


def estimate_audio(settings,seconds):
    return _amount(seconds)*parse_pricing(settings).audio_per_minute/Decimal(60)


def _micros(value):
    return int((_amount(value)*MICROS).to_integral_value(rounding=ROUND_CEILING))


def _summary(db,database,sid):
    consumed=db.scalar(select(func.coalesce(func.sum(ProviderUsage.actual_microdollars),0)).where(ProviderUsage.session_id==sid,ProviderUsage.status=='settled'))
    reserved=db.scalar(select(func.coalesce(func.sum(ProviderUsage.reserved_microdollars),0)).where(ProviderUsage.session_id==sid,ProviderUsage.status=='reserved'))
    cap=_micros(database.settings.session_spend_cap)
    return {'consumed':str(Decimal(consumed)/MICROS),'reserved':str(Decimal(reserved)/MICROS),
        'remaining':str(Decimal(max(0,cap-consumed-reserved))/MICROS),'cap':str(Decimal(cap)/MICROS),'currency':'USD'}


def totals(database,sid):
    with database.session_factory() as db:
        if not db.get(VivaSession,sid):raise service.DomainError(404,'not_found','Interview not found')
        return _summary(db,database,sid)


@contextmanager
def _write(database):
    with database.session_factory() as db:
        if database.engine.dialect.name=='sqlite':db.execute(text('BEGIN IMMEDIATE'))
        else:db.begin()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def reserve(database,sid,kind,estimated_max_cost,price_version=None):
    pricing=parse_pricing(database.settings)
    if price_version is not None and price_version!=pricing.version:raise service.DomainError(503,'pricing_version_mismatch','Pricing changed before reserving the request')
    maximum=_micros(estimated_max_cost)
    with service._LOCK,_write(database) as db:
        session=db.scalar(select(VivaSession).where(VivaSession.id==sid).with_for_update())
        if not session:raise service.DomainError(404,'not_found','Interview not found')
        summary=_summary(db,database,sid)
        if maximum>_micros(summary['remaining']):
            raise service.DomainError(429,'budget_exhausted','This interview has reached its configured provider spend limit',summary)
        row=ProviderUsage(id=uid(),session_id=sid,request_kind=str(kind),price_version=pricing.version,
            reserved_microdollars=maximum,status='reserved',usage={},created_at=now())
        db.add(row);db.flush()
        return Reservation(database,row.id,sid,Decimal(maximum)/MICROS,pricing.version)


def settle(reservation,usage,actual_cost):
    """Settle once. Preserve an actual overrun rather than concealing billed usage."""
    maximum=_micros(actual_cost)
    if not isinstance(usage,dict):raise service.DomainError(503,'invalid_provider_usage','Usage must be a JSON object')
    # Usage contains counters/statuses only; provider content and credentials never belong here.
    import json
    try:
        encoded=json.dumps(usage,allow_nan=False)
        if len(encoded)>10000:raise ValueError()
    except (TypeError,ValueError):raise service.DomainError(503,'invalid_provider_usage','Usage metadata is invalid') from None
    database=reservation.database
    with service._LOCK,_write(database) as db:
        row=db.scalar(select(ProviderUsage).where(ProviderUsage.id==reservation.id).with_for_update())
        if not row or row.session_id!=reservation.session_id:raise service.DomainError(404,'not_found','Usage reservation not found')
        if row.status=='settled':
            if row.actual_microdollars!=maximum or row.usage!=usage:raise service.DomainError(409,'usage_conflict','Settled provider usage cannot be rewritten')
            return _summary(db,database,row.session_id)
        row.actual_microdollars=maximum;row.usage=usage;row.status='settled';row.settled_at=now();db.flush()
        return _summary(db,database,row.session_id)
