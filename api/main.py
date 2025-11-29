from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Autoriser toutes les origines (DEV)
    allow_credentials=True,
    allow_methods=["*"],        # Autoriser tous les verbes HTTP
    allow_headers=["*"],        # Autoriser tous les headers
    expose_headers=["*"],       # Expose tous les headers
)

@app.get("/health")
def health():
    return {"status": "ok"}
