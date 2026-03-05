from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Alti.Analytics User Service", version="1.0.0")

class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    department: str
    tenant_id: str

# Mock Database
MOCK_USERS = [
    UserProfile(id="u1", username="admin", email="admin@alti.analytics", department="IT", tenant_id="t1"),
    UserProfile(id="u2", username="analyst", email="analyst@alti.analytics", department="Data", tenant_id="t1"),
    UserProfile(id="u3", username="sales_rep", email="rep@detroitlions.local", department="Sales", tenant_id="t2"),
]

@app.get("/health")
async def health_check():
    return {"status": "up"}

@app.get("/users", response_model=List[UserProfile])
async def list_users(tenant_id: str | None = None):
    if tenant_id:
        return [u for u in MOCK_USERS if u.tenant_id == tenant_id]
    return MOCK_USERS

@app.get("/users/{user_id}", response_model=UserProfile)
async def get_user_by_id(user_id: str):
    user = next((u for u in MOCK_USERS if u.id == user_id), None)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
