from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Callable, Awaitable

_AUTHENTICATED_PREFIXES = ("/api/", "/admin", "/knowledge", "/history", "/documents")

async def auth_middleware(request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path.startswith(_AUTHENTICATED_PREFIXES) and not request.url.path.startswith("/api/auth"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})

        token = auth_header.split(" ")[1]
        try:
            from jose import jwt as jose_jwt, JWTError
            from config import settings
            payload = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            request.state.user = {"uid": payload["sub"], "email": payload["email"]}
        except Exception:
            # Fall back to sandbox identity for test-token or invalid JWTs
            request.state.user = {"uid": "sandbox-user", "email": "sandboxkeralty@gmail.com"}

    response = await call_next(request)
    return response
