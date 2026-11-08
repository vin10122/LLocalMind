"""Bounded DuckDuckGo search and HTTPS page extraction."""
from __future__ import annotations
from .i18n import tr

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
import ipaddress
import socket
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit
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
        self.challenge = False
        self._active = None
        self._capture = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set(attributes.get('class', '').split())
        if attributes.get('id') in ('challenge-form','anomaly-form') or classes.intersection({'anomaly-modal','g-recaptcha'}):
            self.challenge = True
        if tag == 'a' and classes.intersection({'result__a','result-link'}) and len(self.results) < 10:
            self._active = {'url': attributes.get('href', ''), 'title': ''}
            self.results.append(self._active)
            self._capture = 'title'
        elif classes.intersection({'result__snippet','result-snippet'}) and self.results:
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
        raise ValueError(tr('URL non valido'))
    parsed = urlsplit(url)
    if (parsed.scheme.lower() != 'https' or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError('Sono consentiti solo URL HTTPS pubblici')
    hostname = parsed.hostname.rstrip('.').lower()
    if hostname == 'localhost' or hostname.endswith(('.localhost', '.local')):
        raise ValueError(tr('Host locale non consentito'))
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(
            hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError as error:
        raise ValueError(tr('Host non raggiungibile')) from error
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError(tr('Host non pubblico non consentito'))
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
            raise WebSearchError(tr('Il risultato non è una pagina HTML o testo'))
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise WebSearchError(tr('La pagina supera il limite di download'))
        charset = response.headers.get_content_charset() or 'utf-8'
        return body.decode(charset, errors='replace')


def _result_url(url: str) -> str:
    if not url.strip():raise ValueError('Missing result URL')
    url = urljoin('https://duckduckgo.com/', url)
    parsed = urlsplit(url)
    if parsed.hostname and (parsed.hostname.lower() == 'duckduckgo.com'
                            or parsed.hostname.lower().endswith('.duckduckgo.com')):
        destination = parse_qs(parsed.query).get('uddg', [])
        if destination:
            return destination[0]
        raise ValueError('DuckDuckGo navigation is not a result')
    return url


def _parse_results(document: str) -> list[WebResult]:
    parser = _SearchParser()
    parser.feed(document)
    if parser.challenge:
        raise WebSearchError(tr('DuckDuckGo richiede una verifica anti-bot. La ricerca automatica non può proseguire; riprova più tardi.'))
    results = []
    seen=set()
    for item in parser.results:
        try:
            result_url = _validate_https_url(_result_url(item.get('url', '')))
        except ValueError:
            continue
        if result_url in seen:continue
        seen.add(result_url)
        title = ' '.join(item.get('title', '').split()) or result_url
        snippet = ' '.join(item.get('snippet', '').split())
        results.append(WebResult(title, result_url, snippet, ''))
        if len(results) == MAX_RESULTS:
            break
    return results


def _search(query: str, *, stop=None) -> list[WebResult]:
    # Both are public DuckDuckGo text interfaces. Do not try another endpoint
    # after a CAPTCHA/rate-limit/access block, and never solve challenges.
    for endpoint in ('https://html.duckduckgo.com/html/', 'https://lite.duckduckgo.com/lite/'):
        if stop is not None and stop.is_set():raise WebSearchCancelled()
        try:
            document = _open(endpoint+'?q='+quote_plus(query),max_bytes=MAX_SEARCH_BYTES)
        except HTTPError as error:
            if error.code in (202,403,429):
                raise WebSearchError(tr('DuckDuckGo ha bloccato la ricerca automatica. Riprova più tardi.')) from error
            raise WebSearchError(tr('Ricerca DuckDuckGo non riuscita: {error}',error=f'HTTP {error.code}')) from error
        except (OSError, URLError, TimeoutError, ValueError, WebSearchError) as error:
            raise WebSearchError(tr('Ricerca DuckDuckGo non riuscita: {error}',error=type(error).__name__)) from error
        results=_parse_results(document)
        if results:return results
    raise WebSearchError(tr('DuckDuckGo non ha restituito risultati HTTPS pubblici utilizzabili'))


def _fetch(result: WebResult) -> WebResult:
    try:
        document = _open(result.url, max_bytes=MAX_PAGE_BYTES)
        parser = _PageParser()
        parser.feed(document)
        content = ' '.join(' '.join(parser.parts).split())[:MAX_EXCERPT_CHARS]
        if not content:
            raise WebSearchError(tr('La pagina non contiene testo leggibile'))
        return WebResult(result.title, result.url, result.snippet, content)
    except (OSError, URLError, TimeoutError, ValueError, WebSearchError) as error:
        return WebResult(result.title, result.url, result.snippet, '',
                         type(error).__name__)


def search_and_fetch(query: str, *, stop: threading.Event | None = None,
                     on_status=None) -> list[WebResult]:
    """Search DuckDuckGo and read at most three public HTTPS pages."""
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError(tr('La domanda per la ricerca web deve contenere da 1 a 500 caratteri'))
    if stop is not None and stop.is_set():
        raise WebSearchCancelled()
    if on_status:
        on_status(tr('Ricerca DuckDuckGo'))
    results = _search(query.strip(),stop=stop)
    if stop is not None and stop.is_set():
        raise WebSearchCancelled()
    if on_status:
        on_status(tr('Lettura di {count} risultati web',count=len(results)))
    with ThreadPoolExecutor(max_workers=MAX_RESULTS) as executor:
        fetched = list(executor.map(_fetch, results))
    if stop is not None and stop.is_set():
        raise WebSearchCancelled()
    return fetched


def format_research(results: list[WebResult]) -> str:
    """Format retrieved evidence and provenance for the local model."""
    if not results:
        raise ValueError(tr('La ricerca web non contiene risultati'))
    sections = []
    for index, result in enumerate(results, 1):
        text = result.content
        if not text:
            text = result.snippet or tr('Pagina non disponibile ({error}).',error=result.fetch_error)
            source_kind = tr('snippet DuckDuckGo; pagina non letta')
        else:
            source_kind = tr('estratto della pagina')
        sections.append(
            f'{index}. {result.title}\nURL: {result.url}\n'
            f'{source_kind}:\n[INIZIO CONTENUTO WEB NON ATTENDIBILE]\n'
            f'{text}\n[FINE CONTENUTO WEB NON ATTENDIBILE]'
        )
    return '\n\n'.join(sections)
