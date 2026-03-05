from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta

app = FastAPI(title="Alti.Analytics Auth Service", version="1.0.0")

# OAuth2 Password flow token url definition
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str
    email: str | None = None
    role: str

@app.get("/health")
async def health_check():
    return {"status": "up"}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # In a real app, verify against database and HashiCorp Vault.
    if form_data.username == "admin" and form_data.password == "admin":
        return {"access_token": "fake-admin-token-123", "token_type": "bearer"}
    elif form_data.username == "analyst" and form_data.password == "analyst":
        return {"access_token": "fake-analyst-token-456", "token_type": "bearer"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.get("/users/me", response_model=User)
async def read_users_me(token: str = Depends(oauth2_scheme)):
    if token == "fake-admin-token-123":
        return User(username="admin", email="admin@alti.analytics", role="Admin")
    elif token == "fake-analyst-token-456":
        return User(username="analyst", email="analyst@alti.analytics", role="Analyst")
    raise HTTPException(status_code=401, detail="Invalid auth credentials")
