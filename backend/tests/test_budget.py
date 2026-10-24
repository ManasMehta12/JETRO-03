"""Paid calls reserve a persistent maximum before contacting a provider."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4
import pytest
from app.config import Settings
from app.db import Database
from app.seed import seed
from app import service
from app.budget import parse_pricing, estimate_text, text_cost, estimate_audio, reserve, settle, totals

PRICING={'version':'2026-10-24-test-rates','effective_date':'2026-10-24','currency':'USD','text_input_per_million':'2','text_output_per_million':'8','audio_per_minute':'0.10'}

@pytest.fixture
def setup(tmp_path):
    settings=Settings(database_url='sqlite:///'+str(tmp_path/'budget.db'),provider_mode='fixture',run_inline_worker=False,session_spend_cap=1.0,pricing_json=PRICING)
    database=Database(settings.database_url,settings);database.initialize();seed(database)
    session=service.mutate(database,'learner-1','/viva/sessions',str(uuid4()),{'attempt_id':'attempt-demo-success','input_mode':'text'},lambda db:service.start(db,'learner-1',{'attempt_id':'attempt-demo-success','input_mode':'text'},settings))
    yield database,session['id']
    database.engine.dispose()

def test_explicit_dated_rates_are_required(setup):
    database,sid=setup
    database.settings.pricing_json={}
    with pytest.raises(service.DomainError) as error:parse_pricing(database.settings)
    assert error.value.code=='pricing_not_configured'
    database.settings.pricing_json={**PRICING,'text_input_per_million':'NaN'}
    with pytest.raises(service.DomainError):parse_pricing(database.settings)
    database.settings.pricing_json={**PRICING,'effective_date':'not-a-date'}
    with pytest.raises(service.DomainError):parse_pricing(database.settings)

def test_costs_use_configured_decimal_rates(setup):
    database,sid=setup
    assert estimate_text(database.settings,1000,2000)==Decimal('0.018')
    assert text_cost(database.settings,{'input_tokens':1000,'output_tokens':2000})==Decimal('0.018')
    assert estimate_audio(database.settings,90)==Decimal('0.15')

def test_reservations_and_actual_usage_share_session_cap(setup):
    database,sid=setup
    first=reserve(database,sid,'text-followup',Decimal('0.7'))
    with pytest.raises(service.DomainError) as error:reserve(database,sid,'evaluation',Decimal('0.4'))
    assert error.value.status==429
    settled=settle(first,{'input_tokens':100},Decimal('0.3'))
    assert Decimal(settled['consumed'])==Decimal('0.3')
    second=reserve(database,sid,'evaluation',Decimal('0.7'))
    assert Decimal(totals(database,sid)['remaining'])==0
    settle(second,{},Decimal('0.2'))
    assert Decimal(totals(database,sid)['consumed'])==Decimal('0.5')

def test_settlement_is_idempotent_and_conflicting_rewrite_fails(setup):
    database,sid=setup
    reservation=reserve(database,sid,'text',Decimal('0.6'))
    settle(reservation,{'input_tokens':12},Decimal('0.2'))
    settle(reservation,{'input_tokens':12},Decimal('0.2'))
    assert Decimal(totals(database,sid)['consumed'])==Decimal('0.2')
    with pytest.raises(service.DomainError) as error:settle(reservation,{'input_tokens':12},Decimal('0.1'))
    assert error.value.status==409

def test_concurrent_reservations_cannot_overspend(setup):
    database,sid=setup
    def attempt(_):
        try:return reserve(database,sid,'text',Decimal('0.6')).id
        except service.DomainError as error:return error.code
    with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(attempt,range(2)))
    assert results.count('budget_exhausted')==1
    assert Decimal(totals(database,sid)['reserved'])==Decimal('0.6')

def test_unknown_provider_outcome_can_charge_conservative_reservation(setup):
    database,sid=setup
    reservation=reserve(database,sid,'evaluation',Decimal('0.3'))
    settle(reservation,{'outcome':'unknown'},reservation.reserved_cost)
    assert Decimal(totals(database,sid)['consumed'])==Decimal('0.3')

def test_record_actual_overrun_without_hiding_billed_usage(setup):
    database,sid=setup
    reservation=reserve(database,sid,'text',Decimal('0.5'))
    settle(reservation,{'provider_reported':True},Decimal('1.1'))
    assert Decimal(totals(database,sid)['consumed'])==Decimal('1.1')
    with pytest.raises(service.DomainError):reserve(database,sid,'next',Decimal('0.01'))
