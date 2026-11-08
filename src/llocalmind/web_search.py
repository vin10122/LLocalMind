"""Tavily search using a user-owned .env key; legacy DuckDuckGo is explicit."""
from __future__ import annotations
from .i18n import tr

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .app_paths import data_root


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
    provider: str = 'duckduckgo'


class _NoAPIRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        # Never resend the question to another endpoint after a redirect.
        return None


def _tavily_key() -> str:
    """Read only the known per-user file; never export its key to child engines."""
    path=data_root()/'.env'
    try:
        with path.open('rb') as source:raw=source.read(16_385)
    except OSError:
        raise WebSearchError(tr('Configura la chiave Tavily nel file {path}: TAVILY_API_KEY=tvly-…',path=path)) from None
    try:
        if len(raw)>16_384:raise ValueError()
        found=None
        for line in raw.decode('utf-8-sig').splitlines():
            line=line.strip()
            if line.startswith('export '):line=line[7:].lstrip()
            name,separator,value=line.partition('=')
            if not separator or name.strip()!='TAVILY_API_KEY':continue
            if found is not None:raise ValueError()
            value=value.strip()
            if value.startswith(('"',"'")):
                quoted=re.fullmatch(r'''(['"])(.*?)\1\s*(?:#.*)?''',value)
                if quoted is None:raise ValueError()
                value=quoted[2]
            else:value=value.split('#',1)[0].strip()
            if not re.fullmatch(r'tvly-[A-Za-z0-9_-]{8,256}',value):raise ValueError()
            found=value
        if found is None:raise ValueError()
        return found
    except (ValueError,UnicodeError):
        raise WebSearchError(tr('Chiave Tavily mancante o non valida nel file {path}.',path=path)) from None


def _tavily_search(query: str) -> list[WebResult]:
    """One basic request using the configured account. Billing stays provider-owned."""
    key=_tavily_key()
    request=Request('https://api.tavily.com/search',data=json.dumps(dict(
        query=query,search_depth='basic',max_results=MAX_RESULTS,
        include_answer=False,include_raw_content=False,include_images=False,
        auto_parameters=False)).encode('utf-8'),headers={
        'Content-Type':'application/json','Accept':'application/json',
        'User-Agent':USER_AGENT,'Authorization':'Bearer '+key,
        'X-Client-Source':'llocalmind'})
    status=200
    try:
        try:
            response=build_opener(_NoAPIRedirect()).open(request,timeout=15)
        except HTTPError as error:
            response=error
            status=error.code
        with response:
            body=response.read(MAX_SEARCH_BYTES+1)
        if len(body)>MAX_SEARCH_BYTES:raise ValueError('Oversized API response')
        if status in (429,432,433):
            raise WebSearchError(tr('Quota o limite Tavily raggiunto. Controlla i crediti del piano Free; la ricerca è stata interrotta.'))
        if status==401:
            raise WebSearchError(tr('Chiave Tavily rifiutata. Correggi TAVILY_API_KEY nel file .env.'))
        if status==403:
            raise WebSearchError(tr('Accesso Tavily negato. Verifica chiave e disponibilità del piano nel tuo account.'))
        if status!=200:
            raise WebSearchError(tr('Ricerca Tavily non riuscita (HTTP {code}).',code=status))
        data=json.loads(body)
        if not isinstance(data,dict):raise ValueError('Invalid API response')
        if isinstance(data.get('error'),dict):
            raise WebSearchError(tr('Ricerca Tavily non disponibile per questo account. Controlla chiave e crediti nel pannello Tavily.'))
        if not isinstance(data.get('results'),list):raise ValueError('Invalid API results')
        results=[]
        seen=set()
        for item in data['results'][:20]:
            if not isinstance(item,dict):continue
            try:url=_validate_https_url(item.get('url',''))
            except ValueError:continue
            text=item.get('content')
            if url in seen or not isinstance(text,str) or not text.strip():continue
            seen.add(url)
            title=item.get('title')
            title=' '.join(title.split())[:300] if isinstance(title,str) else url
            text=' '.join(text.split())[:MAX_EXCERPT_CHARS]
            results.append(WebResult(title or url,url,text,text,provider='tavily'))
            if len(results)==MAX_RESULTS:break
        if not results:raise WebSearchError(tr('Tavily non ha restituito fonti HTTPS pubbliche utilizzabili.'))
        return results
    except WebSearchError:raise
    except (OSError,URLError,TimeoutError,ValueError) as error:
        raise WebSearchError(tr('Ricerca Tavily non riuscita: {error}',error=type(error).__name__)) from error


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
                     on_status=None,provider='tavily') -> list[WebResult]:
    """Fetch up to three sources, without retries or an anonymous/paid fallback."""
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError(tr('La domanda per la ricerca web deve contenere da 1 a 500 caratteri'))
    if stop is not None and stop.is_set():
        raise WebSearchCancelled()
    if provider not in ('tavily','duckduckgo'):raise ValueError('Invalid search provider')
    if provider=='tavily':
        if on_status:on_status(tr('Ricerca Tavily'))
        results=_tavily_search(query.strip())
        if stop is not None and stop.is_set():raise WebSearchCancelled()
        return results
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
        elif result.provider=='tavily':
            source_kind=tr('estratto restituito da Tavily; pagina non letta direttamente')
        else:
            source_kind = tr('estratto della pagina')
        sections.append(
            f'{index}. {result.title}\nURL: {result.url}\n'
            f'{source_kind}:\n[INIZIO CONTENUTO WEB NON ATTENDIBILE]\n'
            f'{text}\n[FINE CONTENUTO WEB NON ATTENDIBILE]'
        )
    return '\n\n'.join(sections)
