"""Bounded DuckDuckGo search and HTTPS page extraction."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
import ipaddress
import socket
import threading
from urllib.error import URLError
from urllib.parse import parse_qs, quote_plus, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_RESULTS = 3
MAX_SEARCH_BYTES = 1_000_000
MAX_PAGE_BYTES = 1_000_000
MAX_EXCERPT_CHARS = 900
REQUEST_TIMEOUT = 8
USER_AGENT = 'LLocalMind/0.2 (web research)'


class WebSearchError(RuntimeError):
    """A search or its response could not be processed safely."""


class WebSearchCancelled(RuntimeError):
    """The user cancelled a web search before inference started."""


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    snippet: str
    content: str
    fetch_error: str = ''


class _SearchParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self._active = None
        self._capture = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set(attributes.get('class', '').split())
        if tag == 'a' and 'result__a' in classes and len(self.results) < 10:
            self._active = {'url': attributes.get('href', ''), 'title': ''}
            self.results.append(self._active)
            self._capture = 'title'
        elif 'result__snippet' in classes and self.results:
            self._capture = 'snippet'
            self.results[-1].setdefault('snippet', '')

    def handle_endtag(self, tag):
        if tag == 'a' and self._capture == 'title':
            self._capture = None
            self._active = None
        elif self._capture == 'snippet' and tag in ('a', 'div', 'td'):
            self._capture = None

    def handle_data(self, data):
        if self._capture == 'title' and self._active is not None:
            self._active['title'] += data
        elif self._capture == 'snippet' and self.results:
            self.results[-1]['snippet'] += data


class _PageParser(HTMLParser):
    _IGNORED = {'script', 'style', 'noscript', 'svg', 'iframe', 'template'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._ignored_tags = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        style = attributes.get('style', '').replace(' ', '').lower()
        if (tag in self._IGNORED or 'hidden' in attributes
                or attributes.get('aria-hidden') == 'true'
                or 'display:none' in style or 'visibility:hidden' in style):
            self._ignored_tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self._ignored_tags:
            self._ignored_tags.remove(tag)
        elif tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'article', 'section'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self._ignored_tags:
            text = ' '.join(data.split())
            if text:
                self.parts.append(text)


def _validate_https_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('URL non valido')
    parsed = urlsplit(url)
    if (parsed.scheme.lower() != 'https' or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError('Sono consentiti solo URL HTTPS pubblici')
    hostname = parsed.hostname.rstrip('.').lower()
    if hostname == 'localhost' or hostname.endswith(('.localhost', '.local')):
        raise ValueError('Host locale non consentito')
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(
            hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError as error:
        raise ValueError('Host non raggiungibile') from error
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('Host non pubblico non consentito')
    return url


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        _validate_https_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def _open(url: str, *, max_bytes: int):
    _validate_https_url(url)
    request = Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9',
        'Accept-Encoding': 'identity',
    })
    with build_opener(_SafeRedirectHandler()).open(request, timeout=REQUEST_TIMEOUT) as response:
        content_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if content_type not in ('text/html', 'application/xhtml+xml', 'text/plain'):
            raise WebSearchError('Il risultato non è una pagina HTML o testo')
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise WebSearchError('La pagina supera il limite di download')
        charset = response.headers.get_content_charset() or 'utf-8'
        return body.decode(charset, errors='replace')


def _result_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.hostname and (parsed.hostname.lower() == 'duckduckgo.com'
                            or parsed.hostname.lower().endswith('.duckduckgo.com')):
        destination = parse_qs(parsed.query).get('uddg', [])
        if destination:
            return destination[0]
    return url


def _search(query: str) -> list[WebResult]:
    url = 'https://html.duckduckgo.com/html/?q=' + quote_plus(query)
    try:
        document = _open(url, max_bytes=MAX_SEARCH_BYTES)
    except (OSError, URLError, TimeoutError, ValueError, WebSearchError) as error:
        raise WebSearchError(f'Ricerca DuckDuckGo non riuscita: {type(error).__name__}') from error
    parser = _SearchParser()
    parser.feed(document)
    results = []
    for item in parser.results:
        try:
            result_url = _validate_https_url(_result_url(item.get('url', '')))
        except ValueError:
            continue
        title = ' '.join(item.get('title', '').split()) or result_url
        snippet = ' '.join(item.get('snippet', '').split())
        results.append(WebResult(title, result_url, snippet, ''))
        if len(results) == MAX_RESULTS:
            break
    if not results:
        raise WebSearchError('DuckDuckGo non ha restituito risultati HTTPS pubblici utilizzabili')
    return results


def _fetch(result: WebResult) -> WebResult:
    try:
        document = _open(result.url, max_bytes=MAX_PAGE_BYTES)
        parser = _PageParser()
        parser.feed(document)
        content = ' '.join(' '.join(parser.parts).split())[:MAX_EXCERPT_CHARS]
        if not content:
            raise WebSearchError('La pagina non contiene testo leggibile')
        return WebResult(result.title, result.url, result.snippet, content)
    except (OSError, URLError, TimeoutError, ValueError, WebSearchError) as error:
        return WebResult(result.title, result.url, result.snippet, '',
                         type(error).__name__)


def search_and_fetch(query: str, *, stop: threading.Event | None = None,
                     on_status=None) -> list[WebResult]:
    """Search DuckDuckGo and read at most three public HTTPS pages."""
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError('La domanda per la ricerca web deve contenere da 1 a 500 caratteri')
    if stop is not None and stop.is_set():
        raise WebSearchCancelled()
    if on_status:
        on_status('Ricerca DuckDuckGo')
    results = _search(query.strip())
    if stop is not None and stop.is_set():
        raise WebSearchCancelled()
    if on_status:
        on_status(f'Lettura di {len(results)} risultati web')
    with ThreadPoolExecutor(max_workers=MAX_RESULTS) as executor:
        fetched = list(executor.map(_fetch, results))
    if stop is not None and stop.is_set():
        raise WebSearchCancelled()
    return fetched


def format_research(results: list[WebResult]) -> str:
    """Format retrieved evidence and provenance for the local model."""
    if not results:
        raise ValueError('La ricerca web non contiene risultati')
    sections = []
    for index, result in enumerate(results, 1):
        text = result.content
        if not text:
            text = result.snippet or f'Pagina non disponibile ({result.fetch_error}).'
            source_kind = 'snippet DuckDuckGo; pagina non letta'
        else:
            source_kind = 'estratto della pagina'
        sections.append(
            f'{index}. {result.title}\nURL: {result.url}\n'
            f'{source_kind}:\n[INIZIO CONTENUTO WEB NON ATTENDIBILE]\n'
            f'{text}\n[FINE CONTENUTO WEB NON ATTENDIBILE]'
        )
    return '\n\n'.join(sections)
