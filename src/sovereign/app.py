import traceback
import uvicorn
from collections import namedtuple
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, FileResponse
from pkg_resources import resource_filename
from sovereign import config, asgi_config, __versionstr__, json_response_class
from sovereign.logs import queue_log_fields, application_log
from sovereign.sources import sources_refresh
from sovereign.views import crypto, discovery, healthchecks, admin, interface
from sovereign.middlewares import (
    RequestContextLogMiddleware,
    LoggingMiddleware,
    get_request_id,
    ScheduledTasksMiddleware,
)

Router = namedtuple("Router", "module tags prefix")

DEBUG = config.debug
SENTRY_DSN = config.sentry_dsn.get_secret_value()

try:
    import sentry_sdk
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
except ImportError:  # pragma: no cover
    sentry_sdk = None
    SentryAsgiMiddleware = None


def generic_error_response(e):
    """
    Responds with a JSON object containing basic context
    about the exception passed in to this function.

    If the server is in debug mode, it will include a traceback in the response.

    The traceback is **always** emitted in logs.
    """
    tb = [line for line in traceback.format_exc().split("\n")]
    error = {
        "error": e.__class__.__name__,
        "detail": getattr(e, "detail", "-"),
        "request_id": get_request_id(),
    }
    queue_log_fields(
        ERROR=error["error"],
        ERROR_DETAIL=error["detail"],
        TRACEBACK=tb,
    )
    # Don't expose tracebacks in responses, but add it to the logs
    if DEBUG:
        error["traceback"] = tb
    return json_response_class(
        content=error, status_code=getattr(e, "status_code", 500)
    )


def init_app() -> FastAPI:
    # Warm the sources once before starting
    sources_refresh()
    application_log(event="Initial fetch of Sources completed")

    application = FastAPI(title="Sovereign", version=__versionstr__, debug=DEBUG)
    routers = (
        Router(discovery.router, ["Configuration Discovery"], ""),
        Router(crypto.router, ["Cryptographic Utilities"], "/crypto"),
        Router(admin.router, ["Debugging Endpoints"], "/admin"),
        Router(interface.router, ["User Interface"], "/ui"),
        Router(healthchecks.router, ["Healthchecks"], ""),
    )
    for router in routers:
        application.include_router(
            router.module, tags=router.tags, prefix=router.prefix
        )

    application.add_middleware(RequestContextLogMiddleware)
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(ScheduledTasksMiddleware)

    if SentryAsgiMiddleware is not None and SENTRY_DSN and sentry_sdk:
        sentry_sdk.init(SENTRY_DSN)
        application.add_middleware(SentryAsgiMiddleware)
        application_log(event="Sentry middleware enabled")

    @application.exception_handler(500)
    async def exception_handler(_, exc: Exception) -> json_response_class:
        """
        We cannot incur the execution of this function from unit tests
        because the starlette test client simply returns exceptions and does
        not run them through the exception handler.
        Ergo, this is a facade function for `generic_error_response`
        """
        return generic_error_response(exc)  # pragma: no cover

    @application.get("/")
    def redirect_to_docs():
        return RedirectResponse("/ui")

    @application.get("/static/{filename}", summary="Return a static asset")
    def static(filename: str):
        return FileResponse(resource_filename("sovereign", f"static/{filename}"))

    return application


app = init_app()
application_log(
    event=f"Sovereign started and listening on {asgi_config.host}:{asgi_config.port}"
)


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
