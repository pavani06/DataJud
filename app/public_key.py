"""Resolve the current public credential from the official CNJ access page.

HTML and credentials live only in local variables; nothing is cached or persisted.
"""

from contextlib import closing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import math
import re
import time

import httpx

PUBLIC_KEY_URL = "https://datajud-wiki.cnj.jus.br/api-publica/acesso/"
MAX_PUBLIC_KEY_PAGE_BYTES = 256 * 1024
RETRY_STATUSES = {429, 502, 503, 504}
TRANSIENT_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class PublicKeyError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502, *, upstream_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.upstream_status = upstream_status


def retry_delay(attempt: int, retry_after: str | None = None) -> float:
    fallback = min(0.25 * (2**attempt), 2.0)
    if retry_after is None:
        return fallback
    try:
        delay = float(retry_after)
    except ValueError:
        try:
            when = parsedate_to_datetime(retry_after)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            delay = (when - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return fallback
    return min(max(delay, 0.0), 2.0) if math.isfinite(delay) else fallback


class _PageText(HTMLParser):
    _ignored = {"script", "style", "template", "noscript"}
    _blocks = {"p", "div", "pre", "br", "li", "td", "th", "tr", "h1", "h2", "h3", "h4", "section", "article", "header", "footer"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._ignored:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag in self._blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._ignored and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and tag in self._blocks:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored_depth:
            self.parts.append(data)


def parse_public_key(html: str) -> str:
    """Read a unique Authorization: APIKey token, including syntax-highlight spans."""
    if not isinstance(html, str):
        raise PublicKeyError("public_key_invalid_response", "A página da chave pública tem formato inválido.")
    try:
        if len(html.encode("utf-8")) > MAX_PUBLIC_KEY_PAGE_BYTES:
            raise PublicKeyError("public_key_response_too_large", "A página da chave pública excede o limite de 256 KiB.")
        parser = _PageText()
        parser.feed(html)
        parser.close()
    except (ValueError, AssertionError):
        raise PublicKeyError("public_key_invalid_response", "A página da chave pública tem formato inválido.") from None
    text = "".join(parser.parts)
    markers = list(re.finditer(r"\bAuthorization\s*:\s*APIKey\b", text, re.IGNORECASE))
    if not markers:
        raise PublicKeyError("public_key_not_found", "A chave pública não foi encontrada na página oficial do CNJ.")
    keys = set()
    for marker in markers:
        tail = text[marker.end():]
        # The official instructions repeat the header using this literal placeholder.
        # Ignore only that documented placeholder, never a second real credential.
        if re.match(r"\s+\[Chave\s+P[uú]blica\]", tail, re.IGNORECASE):
            continue
        # Require whitespace between the scheme and credential, never repair it.
        candidate = re.match(r"\s+(\S+)", tail)
        if candidate is None:
            raise PublicKeyError("public_key_invalid_response", "A chave publicada pelo CNJ tem formato inesperado.")
        token = candidate.group(1)
        if len(token) > 4096 or not re.fullmatch(r"[A-Za-z0-9._~+/-]+={0,}", token):
            raise PublicKeyError("public_key_invalid_response", "A chave publicada pelo CNJ tem formato inesperado.")
        keys.add(token)
    if not keys:
        raise PublicKeyError("public_key_not_found", "A chave pública não foi encontrada na página oficial do CNJ.")
    if len(keys) != 1:
        raise PublicKeyError("public_key_ambiguous", "A página oficial apresenta mais de uma chave pública diferente.")
    return keys.pop()


def fetch_public_key(client: httpx.Client, *, max_retries: int = 2) -> str:
    """GET the fixed HTTPS page with bounded streaming and no authorization header.

    At most max_retries+1 GET attempts per resolution; redirects are never followed.
    Identity encoding prevents compressed responses from bypassing the byte bound.
    """
    if type(max_retries) is not int or not 0 <= max_retries <= 3:
        raise ValueError("max_retries deve estar entre 0 e 3.")
    for attempt in range(max_retries + 1):
        try:
            request = client.build_request(
                "GET", PUBLIC_KEY_URL,
                headers={"Accept": "text/html", "Accept-Encoding": "identity", "Cache-Control": "no-cache"},
            )
            # Defense in depth if a caller passed a client with a default header.
            request.headers.pop("Authorization", None)
            request.headers.pop("Proxy-Authorization", None)
            response = client.send(request, stream=True, follow_redirects=False, auth=None)
            with closing(response):
                status = response.status_code
                if 300 <= status < 400:
                    raise PublicKeyError("public_key_redirect", "A página oficial da chave pública redirecionou; consulta recusada.", upstream_status=status)
                if status != 200:
                    if status in RETRY_STATUSES and attempt < max_retries:
                        delay = retry_delay(attempt, response.headers.get("Retry-After"))
                    else:
                        raise PublicKeyError("public_key_http_error", "A página oficial da chave pública retornou erro HTTP.", upstream_status=status)
                else:
                    if response.headers.get("Content-Encoding", "identity").lower().strip() != "identity":
                        raise PublicKeyError("public_key_invalid_response", "A página da chave pública retornou codificação não suportada.", upstream_status=status)
                    try:
                        length = int(response.headers.get("Content-Length", "0"))
                    except ValueError:
                        length = 0  # The actual stream is authoritative and bounded.
                    if length > MAX_PUBLIC_KEY_PAGE_BYTES:
                        raise PublicKeyError("public_key_response_too_large", "A página da chave pública excede o limite de 256 KiB.", upstream_status=status)
                    content = bytearray()
                    for chunk in response.iter_bytes(chunk_size=8192):
                        if len(content) + len(chunk) > MAX_PUBLIC_KEY_PAGE_BYTES:
                            raise PublicKeyError("public_key_response_too_large", "A página da chave pública excede o limite de 256 KiB.", upstream_status=status)
                        content.extend(chunk)
                    try:
                        html = content.decode("utf-8-sig")
                    except UnicodeError:
                        raise PublicKeyError("public_key_invalid_response", "A página da chave pública não contém texto UTF-8 válido.", upstream_status=status) from None
                    return parse_public_key(html)
        except httpx.RequestError as exc:
            if isinstance(exc, TRANSIENT_ERRORS) and attempt < max_retries:
                delay = retry_delay(attempt)
            elif isinstance(exc, httpx.TimeoutException):
                raise PublicKeyError("public_key_timeout", "A página oficial da chave pública excedeu o tempo limite.", 504) from None
            else:
                raise PublicKeyError("public_key_connection_error", "Não foi possível obter a chave pública na página oficial do CNJ.", 503) from None
        time.sleep(delay)
    raise AssertionError("Unreachable public-key retry state")
