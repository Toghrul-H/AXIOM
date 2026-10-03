from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.routers.questions import router
from app.routers.metadata import router as metadata_router
from app.routers.quizzes import router as quiz_router
from app.routers.auth import router as auth_router
from app.routers.progress import router as progress_router
from app.routers.manual_grading import router as manual_grading_router
from app.config import get_settings

app = FastAPI(title="DMI Platform API")
app.include_router(router)
app.include_router(metadata_router)
app.include_router(quiz_router)
app.include_router(auth_router)
app.include_router(progress_router)
app.include_router(manual_grading_router)


@app.middleware("http")
async def private_attempt_responses(request: Request, call_next):
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        origin = request.headers.get('origin')
        if origin and origin not in get_settings().auth_allowed_origins:
            return JSONResponse(status_code=403, content={'detail':'Untrusted request origin'})
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse(status_code=403, content={'detail':'Cross-site requests are not permitted'})
        if request.url.path in {'/auth/login','/auth/register'} and request.headers.get('content-type','').split(';')[0] != 'application/json':
            return JSONResponse(status_code=415, content={'detail':'Use application/json'})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Cookie"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # Never echo credentials or other submitted values in validation responses.
    return JSONResponse(status_code=422, content={'detail':[
        {'loc':e['loc'],'msg':e['msg'],'type':e['type']} for e in exc.errors()
    ]})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database operation unavailable"})


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "DMI Platform API"}


