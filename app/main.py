from app.routers.auth import router as auth_router
from fastapi import FastAPI
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware
from app.config import SECRET_KEY
from app.database import engine
from app.routers.accounts import router as accounts_router
from app.routers.call_logs import router as call_logs_router
from app.routers.ptp import router as ptp_router
from app.routers.payments import router as payments_router
from app.routers.allocations import router as allocations_router
from app.routers.dashboard import router as dashboard_router
from app.routers.imports import router as imports_router
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers.settlements import router as settlements_router

app = FastAPI(
    title="Shaha Finlease LMS",
    description="Loan recovery and collections management prototype",
    version="0.1.0",
)

templates = Jinja2Templates(directory="app/templates")

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="shaha_session",
    same_site="lax",
    https_only=False,  # Local development only; enable HTTPS in production.
)
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(call_logs_router)
app.include_router(ptp_router)
app.include_router(payments_router)
app.include_router(allocations_router)
app.include_router(dashboard_router)
app.include_router(imports_router)
app.include_router(settlements_router)

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
    )


@app.get("/dashboard")
def dashboard_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
    )
@app.get("/portfolio")
def portfolio_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
    )

@app.get("/settlement-centre")
def settlement_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="settlements.html",
    )

@app.get('/')
def home():
    return {
        "message": "Shaha Finlease LMS is running",
        "version": app.version,
    }


@app.get("/health")
def health_check():
    # Check actual database connectivity, not just server status.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": "connected",
    }
