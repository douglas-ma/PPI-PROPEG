import logging
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.shortcuts import render


logger = logging.getLogger(__name__)


def _safe_text(value, fallback='(ausente)', limit=300):
    text = str(value) if value is not None else fallback
    text = ''.join(char if char.isprintable() else ' ' for char in text)
    return (text[:limit] or fallback)


def _referer_origin(referer):
    if not referer:
        return '(ausente)'
    try:
        parsed = urlsplit(referer)
        hostname = parsed.hostname
        if not parsed.scheme or not hostname:
            return '(indisponível)'
        if ':' in hostname and not hostname.startswith('['):
            hostname = f'[{hostname}]'
        port = parsed.port
        authority = f'{hostname}:{port}' if port else hostname
        return _safe_text(f'{parsed.scheme}://{authority}')
    except ValueError:
        return '(indisponível)'


def csrf_failure(request, reason=''):
    """Return a safe, copyable diagnosis for rejected CSRF requests."""
    code = uuid.uuid4().hex[:12].upper()
    origin = _safe_text(request.headers.get('Origin'))
    host = _safe_text(request.META.get('HTTP_HOST'))
    referer_origin = _referer_origin(request.headers.get('Referer'))
    resolver_match = getattr(request, 'resolver_match', None)
    view_name = _safe_text(
        getattr(resolver_match, 'view_name', None),
        fallback='(não resolvida)',
    )
    safe_reason = _safe_text(reason, fallback='Falha na verificação CSRF.')
    user_agent = _safe_text(request.headers.get('User-Agent'))

    diagnostic_text = '\n'.join([
        f'Código: {code}',
        f'Motivo CSRF: {safe_reason}',
        f'Método: {_safe_text(request.method)}',
        f'View: {view_name}',
        f'Host: {host}',
        f'Origin: {origin}',
        f'Referer origin: {referer_origin}',
        f'Esquema: {_safe_text(request.scheme)}',
        f'Navegador (User-Agent): {user_agent}',
    ])

    logger.warning(
        'Falha CSRF %s: motivo=%s view=%s host=%s origin=%s referer_origin=%s',
        code,
        safe_reason,
        view_name,
        host,
        origin,
        referer_origin,
    )

    return render(
        request,
        'errors/csrf_failure.html',
        {
            'show_diagnostics': settings.DEBUG,
            'diagnostic_code': code,
            'diagnostic_text': diagnostic_text if settings.DEBUG else '',
        },
        status=403,
    )
