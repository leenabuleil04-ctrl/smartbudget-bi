"""Unit tests for pdf_parser helpers.

Tests the three pure-Python helper functions without requiring a real PDF.
Run with:  python tests/test_pdf_parser.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pdf_parser import _clean_amount, _date_to_iso, _is_number


def check(label, got, expected):
    if got == expected:
        print(f'  OK  {label}')
        return True
    print(f'  FAIL {label}: expected {expected!r}, got {got!r}')
    return False


def test_clean_amount():
    print('── _clean_amount ──')
    ok = True
    ok &= check('plain int',              _clean_amount('100'),           100.0)
    ok &= check('comma thousands',        _clean_amount('1,477.84'),      1477.84)
    ok &= check('shekel prefix',          _clean_amount('₪2,500.00'),     2500.0)
    ok &= check('large with commas',      _clean_amount('1,234,567.89'),  1234567.89)
    ok &= check('cents only',             _clean_amount('0.50'),          0.5)
    ok &= check('empty string',           _clean_amount(''),              None)
    ok &= check('None input',             _clean_amount(None),            None)
    ok &= check('whitespace',             _clean_amount('  500.00  '),    500.0)
    return ok


def test_date_to_iso():
    print('── _date_to_iso ──')
    ok = True
    ok &= check('standard date',          _date_to_iso('15/06/2026'),   '2026-06-15')
    ok &= check('start of year',          _date_to_iso('01/01/2025'),   '2025-01-01')
    ok &= check('end of year',            _date_to_iso('31/12/2024'),   '2024-12-31')
    ok &= check('leading space',          _date_to_iso(' 05/03/2026'),  '2026-03-05')
    ok &= check('wrong format ISO',       _date_to_iso('2026-06-15'),   None)
    ok &= check('plain text',             _date_to_iso('not-a-date'),   None)
    ok &= check('empty string',           _date_to_iso(''),             None)
    return ok


def test_is_number():
    print('── _is_number ──')
    ok = True
    ok &= check('integer',                _is_number('100'),         True)
    ok &= check('decimal',                _is_number('1,477.84'),    True)
    ok &= check('shekel amount',          _is_number('₪500.00'),     True)
    ok &= check('zero',                   _is_number('0.00'),        True)
    ok &= check('date string',            _is_number('15/06/2026'),  False)
    ok &= check('Hebrew text',            _is_number('פעולה'),       False)
    ok &= check('empty string',           _is_number(''),            False)
    ok &= check('mixed alpha',            _is_number('123abc'),      False)
    return ok


if __name__ == '__main__':
    results = [
        test_clean_amount(),
        test_date_to_iso(),
        test_is_number(),
    ]
    print()
    if all(results):
        print('All tests passed.')
    else:
        print('Some tests FAILED.')
        sys.exit(1)
