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

import os
from macaroon_utils import Macaroon, verify_macaroon

# In a real environment, this root key comes from HashiCorp Vault / Cloud KMS
ROOT_MACAROON_KEY = os.getenv("MACAROON_ROOT_KEY", "super-secret-root-key").encode()

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # In a real app, verify against database and HashiCorp Vault.
    if form_data.username == "admin" and form_data.password == "admin":
        # Generate Macaroon instead of standard JWT
        admin_macaroon = Macaroon(ROOT_MACAROON_KEY, "admin-session-123", "alti-auth-service")
        # Append Cryptographic Caveats
        admin_macaroon.add_first_party_caveat("role=admin")
        
        return {"access_token": admin_macaroon.serialize(), "token_type": "bearer"}
        
    elif form_data.username == "analyst" and form_data.password == "analyst":
        analyst_macaroon = Macaroon(ROOT_MACAROON_KEY, "analyst-session-456", "alti-auth-service")
        analyst_macaroon.add_first_party_caveat("role=analyst")
        
        return {"access_token": analyst_macaroon.serialize(), "token_type": "bearer"}
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.get("/users/me", response_model=User)
async def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        # Verify Macaroon independently (No DB lookup required)
        mac_dict = Macaroon.deserialize(token)
        
        # In a real system the context would evaluate IP address, exact time, etc.
        mock_context = {"role": "admin"} 
        if verify_macaroon(mac_dict, ROOT_MACAROON_KEY, mock_context):
            return User(username="admin", email="admin@alti.analytics", role="Admin")
            
        mock_context = {"role": "analyst"}
        if verify_macaroon(mac_dict, ROOT_MACAROON_KEY, mock_context):
            return User(username="analyst", email="analyst@alti.analytics", role="Analyst")
            
        raise Exception("Caveat verification failed")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or unauthorized Macaroon: {e}")
