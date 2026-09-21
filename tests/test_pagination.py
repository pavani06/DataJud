from app.pagination import PaginationGuard


def test_repeated_page_stops():
    guard = PaginationGuard()
    assert guard.observe(['a'], [1]) is None
    assert guard.observe(['a'], [2]) == 'repeated_page'


def test_repeated_cursor_stops():
    guard = PaginationGuard()
    assert guard.observe(['a'], [1]) is None
    assert guard.observe(['b'], [1]) == 'repeated_cursor'


def test_missing_and_page_limit():
    assert PaginationGuard().observe(['a'], None) == 'missing_cursor'
    assert PaginationGuard(max_pages=1).observe(['a'], [1]) == 'max_pages'
