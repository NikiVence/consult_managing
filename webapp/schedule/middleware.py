import json
import logging
import time

logger = logging.getLogger("consultations")


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000, 2),
                }
            )
        )
        return response
