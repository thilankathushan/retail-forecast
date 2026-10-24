"""Auditable transaction cleaning and weekly positive observed-sales panels."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from .source import sha256

REQUIRED = {'Invoice', 'StockCode', 'Quantity', 'InvoiceDate', 'Price'}
NON_PRODUCT = {'POST', 'DOT', 'D', 'M', 'C2', 'BANK CHARGES', 'AMAZONFEE', 'CRUK',
               'S', 'B', 'ADJUST', 'ADJUST2', 'TEST001', 'TEST002'}
PRODUCT_PATTERN = re.compile(r'(?:[0-9]{5}[A-Z]{0,2}|DCGS[A-Z0-9]+|PADS|SP1002)\Z')


def monday(day):
    return day - timedelta(days=day.weekday())


def build_weekly(source, coverage_start, coverage_end, missing_days=(), *,
                 assume_complete=False, min_history_weeks=4, audit_path=None):
    """No zero filling without an explicit complete-extract assumption.

    Counts are exclusive outcomes; flags overlap. Duplicate fingerprints retain
    all eight source fields, with row order used only to identify repeats.
    """
    if coverage_start > coverage_end:
        raise ValueError('coverage_start must not exceed coverage_end')
    if type(min_history_weeks) is not int or min_history_weeks < 1:
        raise ValueError('min_history_weeks must be a positive integer')
    missing_days = set(missing_days)
    if any(d < coverage_start or d > coverage_end for d in missing_days):
        raise ValueError('missing days must be within coverage bounds')
    totals, returns = defaultdict(int), defaultdict(int)
    sale_rows = Counter()
    first_seen, fingerprints = {}, {}
    outcomes = ['input_rows', 'malformed_row', 'missing_invoice', 'missing_product',
                'invalid_timestamp', 'non_product_code', 'unrecognized_product_code',
                'invalid_quantity', 'invalid_price', 'outside_coverage', 'return_or_adjustment',
                'cancellation_nonnegative', 'zero_quantity', 'nonpositive_price',
                'untrusted_day', 'accepted_rows']
    counts = Counter(dict.fromkeys(outcomes, 0))
    flags, code_counts, daily = Counter(), Counter(), Counter()
    first_stamp = last_stamp = None
    audit_file = None
    if audit_path:
        Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
        audit_file = Path(audit_path).open('w', newline='')
        audit = csv.writer(audit_file)
        audit.writerow(['source_row', 'outcome', 'duplicate_of_row', 'flags'])
    try:
        with Path(source).open(newline='', encoding='utf-8-sig') as stream:
            reader = csv.DictReader(stream)
            if not REQUIRED.issubset(reader.fieldnames or []):
                raise ValueError(f'required columns: {sorted(REQUIRED)}')
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError('duplicate column names')
            for row_number, row in enumerate(reader, 2):
                counts['input_rows'] += 1
                row_flags = []
                fingerprint = hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).digest() if None not in row else None
                duplicate_of = fingerprints.get(fingerprint, '') if fingerprint else ''
                if duplicate_of:
                    row_flags.append('duplicate_retained')
                elif fingerprint:
                    fingerprints[fingerprint] = row_number
                invoice = (row.get('Invoice') or '').strip()
                product = (row.get('StockCode') or '').strip().upper()
                customer = (row.get('Customer ID') or '').strip()
                if not customer:
                    row_flags.append('missing_customer')
                cancellation = invoice.upper().startswith('C')
                if cancellation:
                    row_flags.append('cancellation_invoice')
                day = None
                try:
                    timestamp = datetime.fromisoformat((row.get('InvoiceDate') or '').strip())
                    if timestamp.tzinfo is not None:
                        raise ValueError('offset timestamp')
                    day = timestamp.date()
                    first_stamp = min(first_stamp or timestamp, timestamp)
                    last_stamp = max(last_stamp or timestamp, timestamp)
                    daily[day] += 1
                except ValueError:
                    row_flags.append('invalid_timestamp')
                numbers = {}
                for field in ('Quantity', 'Price'):
                    try:
                        number = Decimal((row.get(field) or '').strip())
                        if not number.is_finite() or (field == 'Quantity' and number != number.to_integral_value()):
                            raise InvalidOperation
                        numbers[field] = number
                    except InvalidOperation:
                        row_flags.append('invalid_' + field.lower())
                quantity, price = numbers.get('Quantity'), numbers.get('Price')
                if quantity is not None and quantity < 0:
                    row_flags.append('negative_quantity')
                if price is not None and price <= 0:
                    row_flags.append('nonpositive_price')
                if None in row or any(v is None for v in row.values()):
                    outcome = 'malformed_row'
                elif not invoice:
                    outcome = 'missing_invoice'
                elif not product:
                    outcome = 'missing_product'
                elif day is None:
                    outcome = 'invalid_timestamp'
                elif product in NON_PRODUCT or product.startswith('GIFT_'):
                    outcome = 'non_product_code'
                    code_counts[product] += 1
                elif not PRODUCT_PATTERN.fullmatch(product):
                    outcome = 'unrecognized_product_code'
                    code_counts[product] += 1
                elif quantity is None:
                    outcome = 'invalid_quantity'
                elif price is None:
                    outcome = 'invalid_price'
                elif not coverage_start <= day <= coverage_end:
                    outcome = 'outside_coverage'
                elif quantity < 0:
                    # Negative records are return/adjustment candidates, not proof
                    # that goods physically came back. Price is irrelevant to units.
                    outcome = 'return_or_adjustment'
                    kind = 'cancellation' if cancellation else 'negative_without_cancellation'
                    returns[product, monday(day), kind] += int(-quantity)
                elif cancellation:
                    outcome = 'cancellation_nonnegative'
                elif quantity == 0:
                    outcome = 'zero_quantity'
                elif price <= 0:
                    outcome = 'nonpositive_price'
                elif day in missing_days:
                    outcome = 'untrusted_day'
                else:
                    outcome = 'accepted_rows'
                    week = monday(day)
                    totals[product, week] += int(quantity)
                    sale_rows[product, week] += 1
                    first_seen[product] = min(first_seen.get(product, week), week)
                if outcome == 'accepted_rows':
                    if 'missing_customer' in row_flags:
                        row_flags.append('accepted_missing_customer')
                    if duplicate_of:
                        row_flags.append('accepted_duplicate_retained')
                counts[outcome] += 1
                flags.update(row_flags)
                if audit_file:
                    audit.writerow([row_number, outcome, duplicate_of, '|'.join(row_flags)])
    finally:
        if audit_file:
            audit_file.close()
    output = []
    for product in sorted(first_seen):
        week = first_seen[product]
        history = consecutive = 0
        while week <= monday(coverage_end):
            end = week + timedelta(days=6)
            if week < coverage_start or end > coverage_end:
                status, reason = 'partial_week', 'coverage_boundary'
            elif any(week <= d <= end for d in missing_days):
                status, reason = 'missing_observation', 'declared_missing_day'
            elif not assume_complete:
                status, reason = 'missing_observation', 'coverage_unverified'
            else:
                status, reason = 'observed', 'assumed_complete_extract'
            output.append({'product_id': product, 'week_start': week.isoformat(),
                           'observed_units': totals[product, week] if status == 'observed' else None,
                           'recorded_positive_units': totals[product, week],
                           'accepted_sale_rows': sale_rows[product, week], 'status': status,
                           'coverage_reason': reason,
                           'days_without_source_transactions': sum(not daily[week + timedelta(days=i)] for i in range(7)),
                           'prior_observed_weeks': history,
                           'prior_consecutive_observed_weeks': consecutive,
                           'history_eligible_at_issue': consecutive >= min_history_weeks})
            if status == 'observed':
                history += 1
                consecutive += 1
            else:
                consecutive = 0
            week += timedelta(days=7)
    return_rows = [{'product_id': p, 'week_start': w.isoformat(), 'kind': k, 'recorded_return_units': n,
                    'complete_week_assumed': assume_complete and w >= coverage_start and w + timedelta(days=6) <= coverage_end
                    and not any(w <= d <= w + timedelta(days=6) for d in missing_days)}
                   for (p, w, k), n in sorted(returns.items())]
    no_activity = []
    day = coverage_start
    while day <= coverage_end:
        if not daily[day]:
            no_activity.append(day.isoformat())
        day += timedelta(days=1)
    report = {'schema_version': 2, 'source_sha256': sha256(source),
              'coverage_start': coverage_start.isoformat(), 'coverage_end': coverage_end.isoformat(),
              'min_valid_timestamp': first_stamp.isoformat() if first_stamp else None,
              'max_valid_timestamp': last_stamp.isoformat() if last_stamp else None,
              'assume_complete': assume_complete, 'missing_days': sorted(d.isoformat() for d in missing_days),
              'days_without_transactions': no_activity, 'min_history_weeks': min_history_weeks,
              'counts': dict(sorted(counts.items())), 'overlapping_flags': dict(sorted(flags.items())),
              'excluded_code_counts': dict(sorted(code_counts.items())),
              'products': len(first_seen), 'weekly_rows': len(output),
              'weekly_status_counts': dict(Counter(r['status'] for r in output)),
              'accepted_positive_units': sum(totals.values()), 'recorded_return_units': sum(returns.values()),
              'target': 'positive sales units after documented exclusions; returns separate',
              'returns_weekly': return_rows}
    assert sum(v for k, v in counts.items() if k != 'input_rows') == counts['input_rows']
    return output, report


def save_prepared(rows, report, output_dir):
    import pandas as pd
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_dir / 'weekly.csv', index=False)
    report = dict(report)
    returns = report.pop('returns_weekly')
    pd.DataFrame(returns, columns=['product_id', 'week_start', 'kind', 'recorded_return_units',
                                 'complete_week_assumed']).to_csv(output_dir / 'returns_weekly.csv', index=False)
    (output_dir / 'quality.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
