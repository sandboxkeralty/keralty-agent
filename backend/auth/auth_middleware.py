from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Callable, Awaitable

async def auth_middleware(request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]):
    """
    Middleware to validate requests to protected routes.
    For this implementation, it checks for a Bearer token.
    """
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/auth"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})
        
        token = auth_header.split(" ")[1]
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
            
        # In a real scenario, validate token (e.g. via firebase_admin.auth.verify_id_token)
        # We attach a default user dict for now
        request.state.user = {"uid": "sandbox-user", "email": "sandboxkeralty@gmail.com"}
        
    response = await call_next(request)
    return response
