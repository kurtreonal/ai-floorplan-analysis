"""Browser-friendly OAuth failures; JSON API contracts remain unchanged."""
import logging
from urllib.parse import urlsplit

from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse


class AuthQueryRedactor(logging.Filter):
    def filter(self,record):
        if isinstance(record.args,tuple) and len(record.args)>=3 and isinstance(record.args[2],str):
            path=record.args[2]
            if path.partition('?')[0].startswith('/api/auth/'):
                record.args=(*record.args[:2],path.partition('?')[0],*record.args[3:])
        return True


def protect_auth_access_logs():
    logger=logging.getLogger('uvicorn.access')
    if not any(isinstance(item,AuthQueryRedactor) for item in logger.filters):
        logger.addFilter(AuthQueryRedactor())


def _accepts_html(value):
    for item in value.lower().split(','):
        media,*options=item.split(';')
        if media.strip() != 'text/html': continue
        quality=next((p.strip()[2:] for p in options if p.strip().startswith('q=')),'1')
        try:
            if float(quality)>0: return True
        except ValueError:
            continue
    return False


async def auth_exception_handler(request: Request, error: HTTPException):
    navigation=request.url.path in ('/api/auth/login','/api/auth/callback')
    if navigation and _accepts_html(request.headers.get('accept','')):
        code = error.detail.get('error', {}).get('code') if isinstance(error.detail, dict) else None
        reason=('account-not-provisioned' if code == 'ACCOUNT_NOT_PROVISIONED' else
                'service-unavailable' if error.status_code==503 else
                'provider-unavailable' if error.status_code>=500 else 'signin-failed')
        # Never echo provider queries, tokens, internal messages or return URLs.
        target=urlsplit(str(request.app.state.settings.frontend_url))._replace(
            fragment=f'/signin?auth_error={reason}').geturl()
        return RedirectResponse(target,status_code=303,headers={
            'Cache-Control':'no-store','Referrer-Policy':'no-referrer',
        })
    return await http_exception_handler(request,error)
