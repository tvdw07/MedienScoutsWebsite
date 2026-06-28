from urllib.parse import urljoin, urlsplit, urlunsplit

from flask import current_app, url_for


def normalize_base_url(base_url):
    value = (base_url or '').strip()
    if not value:
        raise RuntimeError('Missing required environment variable: APP_BASE_URL')

    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError('APP_BASE_URL must be an absolute URL, for example https://example.com')
    if parsed.query or parsed.fragment:
        raise RuntimeError('APP_BASE_URL must not contain a query string or fragment')

    normalized_path = parsed.path.rstrip('/')
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, '', ''))


def build_absolute_url(endpoint, **values):
    base_url = current_app.config.get('APP_BASE_URL')
    if not base_url:
        raise RuntimeError('APP_BASE_URL is not configured')

    relative_url = url_for(endpoint, _external=False, **values)
    normalized_base_url = normalize_base_url(base_url)
    return urljoin(normalized_base_url.rstrip('/') + '/', relative_url.lstrip('/'))
