from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.account import router as account_router
from app.routers.auth import router as auth_router
from app.routers.cycle import router as cycle_router
from app.routers.participant import router as participant_router
from app.routers.prediction import router as prediction_router
from app.routers.relationship import router as relationship_router
from app.routers.super_admin import router as super_admin_router
from app.routers.user import router as user_router

app = FastAPI(
    title="Closed Loop API",
    description="Closed-loop payment network API with token authentication",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:3000",
        "https://closedloop.co.ke",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=False,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.include_router(auth_router)
app.include_router(account_router)
app.include_router(user_router)
app.include_router(participant_router)
app.include_router(relationship_router)
app.include_router(cycle_router)
app.include_router(prediction_router)
app.include_router(super_admin_router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "Closed Loop API is running"}


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
