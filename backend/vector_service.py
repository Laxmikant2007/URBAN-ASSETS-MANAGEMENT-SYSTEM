
import os
import uuid
from pathlib import Path

import chromadb
import jwt
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from database import get_db_connection

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing from the backend .env file.")

CHROMA_PATH = BASE_DIR / "chroma_data"
MAX_DISTANCE = 0.80

client = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection = client.get_or_create_collection(
    name="urban_complaints"
)

security = HTTPBearer(auto_error=False)

app = FastAPI(
    title="UrbanCare Vector Search API",
    description="Semantic search for similar urban complaints",
    version="1.1.0",
)



class SearchRequest(BaseModel):
    description: str = Field(min_length=3, max_length=5000)
    category: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=5, ge=1, le=10)


class VectorRecordCreate(BaseModel):
    description: str = Field(min_length=3, max_length=5000)
    category: str = Field(min_length=1, max_length=100)


class VectorRecordUpdate(BaseModel):
    description: str | None = Field(
        default=None, min_length=3, max_length=5000
    )
    category: str | None = Field(
        default=None, min_length=1, max_length=100
    )

def normalize_category(category):
    if not category:
        return "unknown"
    return str(category).strip().casefold()


@app.get("/")
def health_check():
    return {
        "status": "running",
        "service": "UrbanCare Vector Search",
        "stored_complaints": collection.count(),
        "max_distance": MAX_DISTANCE,
    }



def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Please log in to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        subject = payload.get("sub")

        if not subject:
            raise ValueError("Missing token subject")

        user_id = int(subject)
        if user_id <= 0:
            raise ValueError("Invalid user ID")

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_id, Role
            FROM `USER`
            WHERE user_id = %s
            """,
            (user_id,),
        )
        user = cursor.fetchone()

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="User account not found.",
            )

        return user

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to verify your account.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


def require_admin(
    current_user: dict = Depends(get_current_user),
):
    if current_user["Role"] != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator permission is required.",
        )
    return current_user


@app.post("/search")
def search_complaints(request: SearchRequest):
    description = request.description.strip()

    if len(description) < 3:
        raise HTTPException(
            status_code=400,
            detail="Please provide a longer complaint description.",
        )

    total = collection.count()

    if total == 0:
        return {"results": [], "message": "No complaints indexed yet."}

    # Retrieve more candidates so category filtering has enough
    # results to work with.
    candidate_limit = min(max(request.limit * 4, 20), total)

    results = collection.query(
        query_texts=[description],
        n_results=candidate_limit,
        include=["documents", "metadatas", "distances"],
    )

    query_category = normalize_category(request.category)
    matches = []

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for complaint_id, document, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        metadata = metadata or {}
        result_category = normalize_category(
            metadata.get("category", "Unknown")
        )
        distance = float(distance)

        # Remove weak semantic matches.
        if distance > MAX_DISTANCE:
            continue

        # If a category was supplied, exclude records that have a
        # known, different category. Keep Unknown records only when
        # their descriptions are sufficiently similar.
        if (
            query_category != "unknown"
            and result_category != "unknown"
            and result_category != query_category
        ):
            continue

        matches.append({
            "complaint_id": complaint_id,
            "description": document,
            "category": metadata.get("category", "Unknown"),
            "distance": round(distance, 4),
        })

    # Best semantic matches first.
    matches.sort(key=lambda item: item["distance"])
    matches = matches[:request.limit]

    return {
        "results": matches,
        "message": (
            "Similar complaints found."
            if matches
            else "No sufficiently similar complaints found."
        ),
    }


@app.get("/health")
def health():
    return {"status": "ok"}

class VectorRecordCreate(BaseModel):
    description: str = Field(min_length=3, max_length=5000)
    category: str = Field(min_length=1, max_length=100)


class VectorRecordUpdate(BaseModel):
    description: str | None = Field(
        default=None, min_length=3, max_length=5000
    )
    category: str | None = Field(
        default=None, min_length=1, max_length=100
    )


@app.post("/records", status_code=201)
def create_record(
    request: VectorRecordCreate,
    admin: dict = Depends(require_admin),
):
    record_id = str(uuid.uuid4())

    collection.add(
        ids=[record_id],
        documents=[request.description.strip()],
        metadatas=[{"category": request.category.strip()}],
    )

    return {
        "record_id": record_id,
        "description": request.description.strip(),
        "category": request.category.strip(),
        "message": "Record created successfully.",
    }


@app.get("/records/{record_id}")
def read_record(
    record_id: str,
    admin: dict = Depends(require_admin),
):
    record = collection.get(
        ids=[record_id],
        include=["documents", "metadatas"],
    )

    if not record["ids"]:
        raise HTTPException(status_code=404, detail="Record not found.")

    return {
        "record_id": record["ids"][0],
        "description": record["documents"][0],
        "category": (record["metadatas"][0] or {}).get("category", "Unknown"),
    }


@app.put("/records/{record_id}")
def update_record(
    record_id: str,
    request: VectorRecordUpdate,
    admin: dict = Depends(require_admin),
):
    if request.description is None and request.category is None:
        raise HTTPException(
            status_code=400,
            detail="Provide a description or category to update.",
        )

    existing = collection.get(ids=[record_id])

    if not existing["ids"]:
        raise HTTPException(status_code=404, detail="Record not found.")

    fields = {}

    if request.description is not None:
        fields["documents"] = [request.description.strip()]

    if request.category is not None:
        fields["metadatas"] = [{"category": request.category.strip()}]

    collection.update(ids=[record_id], **fields)

    return {
        "record_id": record_id,
        "message": "Record updated successfully.",
    }


@app.delete("/records/{record_id}")
def delete_record(
    record_id: str,
    admin: dict = Depends(require_admin),
):
    existing = collection.get(ids=[record_id])

    if not existing["ids"]:
        raise HTTPException(status_code=404, detail="Record not found.")

    collection.delete(ids=[record_id])

    return {
        "record_id": record_id,
        "message": "Record deleted successfully.",
    }