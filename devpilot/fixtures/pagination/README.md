# Pagination fixture
The `page` argument is one-based. A full page must contain `page_size` items.
The last page may be shorter. Empty input returns an empty list. Invalid page or
page size must raise ValueError. Fix the off-by-one error without editing tests.
