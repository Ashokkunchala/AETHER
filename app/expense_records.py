"""Local expense arithmetic, optimistic correction and optional request deduplication.

No payments, provider calls, old-row migration or currency conversion.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException

SCAN_LIMIT = 10000
ITEM_LIMIT = 1000
FIELDS = ('amount', 'currency', 'category', 'note', 'spent_on')


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def record(row) -> dict:
    result = dict(row)
    result['revision'] = digest(result)
    return result


def valid(row) -> bool:
    try:
        amount = Decimal(str(row['amount']))
        return (amount.is_finite() and Decimal('0') < amount <= Decimal('100000000')
                and re.fullmatch(r'[A-Z]{3}', row['currency'] or '') is not None
                and date.fromisoformat(row['spent_on']).isoformat() == row['spent_on'])
    except (InvalidOperation, ValueError, TypeError):
        return False


def listing(db, month: str | None) -> dict:
    if month is not None:
        try:
            if not re.fullmatch(r'\d{4}-\d{2}', month):
                raise ValueError
            date.fromisoformat(month + '-01')
        except ValueError:
            raise HTTPException(422, 'month must be a real month using YYYY-MM.') from None
    where, params = (' WHERE substr(spent_on,1,7)=?', (month,)) if month else ('', ())
    rows = db.execute('SELECT * FROM life_expenses' + where + ' ORDER BY spent_on DESC,id DESC LIMIT ?', (*params, SCAN_LIMIT + 1)).fetchall()
    selected = [row for row in rows[:SCAN_LIMIT] if valid(row)]
    totals: dict[str, Decimal] = defaultdict(Decimal)
    categories: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    category_counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in selected:
        currency, category = row['currency'], row['category']
        amount = Decimal(str(row['amount']))
        totals[currency] += amount
        categories[currency, category] += amount
        counts[currency] += 1
        category_counts[currency, category] += 1
    def money(amount):
        return format(amount.quantize(Decimal('0.01')), 'f')
    legacy_categories: list[dict[str, Any]] = [{'category': category, 'total': float(money(amount)), 'count': category_counts[currency, category]}
                         for (currency, category), amount in categories.items() if currency == 'INR']
    legacy_categories.sort(key=lambda row: (-row['total'], row['category']))
    return {'items': [record(row) for row in selected[:ITEM_LIMIT]],
            'total': float(money(totals.get('INR', Decimal(0)))), 'currency': 'INR',
            'by_category': legacy_categories, 'legacy_totals_scope': 'INR only',
            'totals_by_currency': [{'currency': currency, 'amount': money(amount), 'count': counts[currency]}
                                   for currency, amount in sorted(totals.items())],
            'categories_by_currency': [{'currency': currency, 'category': category, 'amount': money(amount), 'count': category_counts[currency, category]}
                                       for (currency, category), amount in sorted(categories.items())],
            'partial': len(rows) > SCAN_LIMIT, 'items_truncated': len(selected) > ITEM_LIMIT,
            'invalid_records_skipped': min(len(rows), SCAN_LIMIT) - len(selected),
            'scan_limit': SCAN_LIMIT, 'item_limit': ITEM_LIMIT,
            'notice': 'Local saved expenses only. Legacy total/by_category are INR-only; other currencies are separate, never converted or combined. Totals cover at most 10000 newest matching rows; partial=true means incomplete totals. Items show at most 1000 valid rows. Invalid legacy rows are skipped, not changed.'}


def create(db, item, now: str, request_key: str | None = None, requester: str | None = None) -> tuple[dict, bool]:
    values = item.model_dump()
    if request_key is not None:
        if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', request_key):
            raise HTTPException(422, 'Idempotency-Key must be 1-128 ASCII letters, digits, dots, colons, underscores or hyphens.')
        if not requester:
            raise HTTPException(401, 'An authenticated credential is required for idempotent create.')
        # New table only. No alterations or backfill of expense rows.
        db.execute('CREATE TABLE IF NOT EXISTS life_expense_requests (requester TEXT NOT NULL, request_key TEXT NOT NULL, request_hash TEXT NOT NULL, expense_id INTEGER NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(requester,request_key))')
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT * FROM life_expense_requests WHERE requester=? AND request_key=?', (requester, request_key)).fetchone()
        if previous:
            if previous['request_hash'] != digest(values):
                raise HTTPException(409, 'This request key was already used with different expense details. Check transactions before starting a new expense.')
            row = db.execute('SELECT * FROM life_expenses WHERE id=?', (previous['expense_id'],)).fetchone()
            if row is None:
                raise HTTPException(409, 'The original expense was deleted. Retry will not recreate it. Use a new key only for an intentional new expense.')
            return record(row), True
    cur = db.execute('INSERT INTO life_expenses(amount,currency,category,note,spent_on,created_at) VALUES(?,?,?,?,?,?)',
                     (*(values[field] for field in FIELDS), now))
    if request_key is not None:
        db.execute('INSERT INTO life_expense_requests VALUES(?,?,?,?,?)', (requester, request_key, digest(values), cur.lastrowid, now))
    return record(db.execute('SELECT * FROM life_expenses WHERE id=?', (cur.lastrowid,)).fetchone()), False


def correct(db, expense_id: int, item) -> dict:
    db.execute('BEGIN IMMEDIATE')
    row = db.execute('SELECT * FROM life_expenses WHERE id=?', (expense_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Expense not found.')
    values = item.model_dump(exclude={'expected_revision'})
    if record(row)['revision'] != item.expected_revision:
        # A response lost after an identical correction is safe to retry.
        if all(row[field] == values[field] for field in FIELDS):
            return record(row)
        raise HTTPException(409, 'Expense changed. Refresh the transaction and review the correction again.')
    db.execute('UPDATE life_expenses SET amount=?,currency=?,category=?,note=?,spent_on=? WHERE id=?',
               (*(values[field] for field in FIELDS), expense_id))
    return record(db.execute('SELECT * FROM life_expenses WHERE id=?', (expense_id,)).fetchone())
