"""Explicitly opted-in Google Contacts reads. Never send, merge or edit contacts."""
from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.personal_data import require_device_token

router = APIRouter(prefix='/api/contacts', tags=['AETHER contacts'], dependencies=[Depends(require_device_token)])
CONTACTS_SCOPE = 'https://www.googleapis.com/auth/contacts.readonly'
PEOPLE_SEARCH = 'https://people.googleapis.com/v1/people:searchContacts'
READ_MASK = 'names,emailAddresses,phoneNumbers,organizations'


def _credentials():
    from app.integrations import _provider
    data = _provider('google')
    scopes = str(data.get('scope', '')).split()
    if CONTACTS_SCOPE not in scopes and 'https://www.googleapis.com/auth/contacts' not in scopes:
        raise HTTPException(409, 'Reconnect Google using the explicit read-only Contacts opt-in. Existing calendar/email consent is not Contacts consent.')
    return data


@router.get('/status')
def contacts_status():
    try:
        _credentials()
    except HTTPException as exc:
        if exc.status_code == 409:
            return {'authorized': False, 'message': exc.detail}
        raise
    return {'authorized': True, 'message': 'Saved Google grant includes contact-read scope. Search checks live API access; the People API must be enabled in your Google Cloud project.'}


@router.get('/search')
async def search_contacts(q: str = Query(min_length=1, max_length=200), limit: int = Query(default=10, ge=1, le=30)):
    query = q.strip()
    if not query:
        raise HTTPException(422, 'Enter a contact name, email or phone prefix.')
    _credentials()
    from app.integrations import _google_access_token
    token = await _google_access_token()
    async def request(client, value):
        try:
            response = await client.get(PEOPLE_SEARCH, params={'query': value, 'pageSize': limit, 'readMask': READ_MASK}, headers={'Authorization': 'Bearer ' + token})
        except httpx.RequestError:
            raise HTTPException(502, 'Google Contacts could not be reached. Nothing was changed.') from None
        if response.status_code in (401, 403):
            raise HTTPException(409, 'Google Contacts access was refused. Check People API enablement and reconnect with read-only Contacts consent.')
        if response.status_code == 429:
            raise HTTPException(429, 'Google Contacts rate limit reached. Wait before searching again.')
        if response.status_code != 200:
            raise HTTPException(502, 'Google Contacts search failed. Nothing was changed.')
        try:
            payload = response.json()
        except ValueError:
            raise HTTPException(502, 'Google Contacts returned an invalid response.') from None
        if not isinstance(payload, dict) or not isinstance(payload.get('results', []), list):
            raise HTTPException(502, 'Google Contacts returned an invalid response.')
        return payload
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        # Google documents a lazy search cache: warm up, then wait five seconds.
        await request(client, '')
        await asyncio.sleep(5)
        data = await request(client, query)
    items = []
    for result in data.get('results', [])[:limit]:
        person = result.get('person', {}) if isinstance(result, dict) else {}
        if not isinstance(person, dict):
            continue
        def values(field, key):
            source = person.get(field, [])
            if not isinstance(source, list):
                return []
            return [str(item[key])[:320] for item in source[:10] if isinstance(item, dict) and item.get(key)]
        items.append({'resource_name': str(person.get('resourceName', ''))[:200],
                      'names': values('names', 'displayName'),
                      'emails': values('emailAddresses', 'value'),
                      'phones': values('phoneNumbers', 'value'),
                      'organizations': values('organizations', 'name')})
    return {'query': query, 'items': items, 'source': 'Google People API / CONTACT source',
            'notice': 'Prefix matches only, at most 30 contacts. Not a full address book or proof of identity. Similar names remain separate. No contact was changed, selected as a recipient or messaged.'}
