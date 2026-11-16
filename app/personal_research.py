"""User-triggered travel/shopping source research, never quotes or bookings.

Queries contain only explicit form fields, not saved personal data. Search
snippets are unverified evidence, not confirmed prices, stock or availability.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.personal_data import require_device_token
from app.public_source_pages import router as source_pages_router
from app.research import search_web

router = APIRouter(prefix='/api/research', tags=['AETHER source research'], dependencies=[Depends(require_device_token)])
router.include_router(source_pages_router)


class _Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    @field_validator('*', mode='before')
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class TravelResearch(_Input):
    origin: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=120)
    travel_date: date | None = None
    preferences: str = Field(default='', max_length=500)


class ShoppingResearch(_Input):
    query: str = Field(min_length=2, max_length=200)
    budget: str = Field(default='', max_length=100)
    preferences: str = Field(default='', max_length=500)
    market: str = Field(min_length=2, max_length=80)


def _sources(queries):
    def find(group):
        label, query = group
        try:
            rows = search_web(query, 5)
        except Exception:
            return {'topic': label, 'query': query, 'status': 'unavailable', 'sources': [],
                    'notice': 'Search failed or timed out. No conclusion about availability can be drawn.'}
        safe = []
        seen = set()
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            url = str(row.get('url', ''))
            try:
                parsed = urlsplit(url)
                valid = parsed.scheme in ('https', 'http') and parsed.hostname and not parsed.username and not parsed.password
            except ValueError:
                valid = False
            if not valid or url in seen:
                continue
            seen.add(url)
            safe.append({'title': str(row.get('title', ''))[:300], 'url': url,
                         'snippet': str(row.get('snippet', ''))[:1000],
                         'page_verified': False})
        return {'topic': label, 'query': query, 'status': 'sources_returned' if safe else 'no_sources', 'sources': safe,
                'notice': 'Search snippets only; destination pages have not been verified.'}
    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(find, queries))


def _report(kind, fields, queries):
    groups = _sources(queries)
    return {'kind': kind, 'request': fields, 'searched_at': datetime.now(UTC).isoformat(),
            'groups': groups, 'partial': any(group['status'] != 'sources_returned' for group in groups),
            'booked': False, 'purchased': False,
            'notice': 'Source shortlist, not a verified itinerary, product recommendation or final quote. Prices, stock, dates, routes, taxes, fees, refund/cancellation terms and seller identity must be checked on the provider page. Snippets can be stale or wrong. Nothing was booked, ordered or paid. Only explicit query fields were sent to DuckDuckGo; no saved personal records were read.'}


@router.post('/travel')
def research_travel(item: TravelResearch):
    route = f'{item.origin} to {item.destination}'
    when = item.travel_date.isoformat() if item.travel_date else 'dates not specified'
    return _report('travel', item.model_dump(mode='json'), [
        ('Transport sources', f'{route} {when} flights trains transport official {item.preferences}'),
        ('Accommodation sources', f'{item.destination} {when} hotels accommodation official {item.preferences}'),
        ('Destination and policy sources', f'{item.destination} official tourism transport cancellation travel advice {item.preferences}'),
    ])


@router.post('/shopping')
def research_shopping(item: ShoppingResearch):
    base = f'{item.query} {item.market} {item.budget} {item.preferences}'
    return _report('shopping', item.model_dump(), [
        ('Manufacturer specifications', f'{base} official manufacturer specifications model comparison'),
        ('Seller pricing pages', f'{base} retailer price stock delivery'),
        ('Warranty and returns', f'{base} official warranty return policy seller'),
    ])
