
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import jwt
import mysql.connector
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pwdlib import PasswordHash
from pydantic import BaseModel, Field
from database import get_db_connection
import requests
from fastapi import HTTPException
from datetime import date, datetime, timedelta, timezone

# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv(Path(__file__).resolve().parent / ".env")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing from the backend .env file."
    )

password_hasher = PasswordHash.recommended()
security = HTTPBearer(auto_error=False)

app = FastAPI(
    title="Intelligent Urban Assets and Complaint Management System",
    version="1.1.0",
)
# --------------------------------------------------
# File upload configuration
# --------------------------------------------------

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

ALLOWED_FILES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}

# Make uploaded files accessible through /uploads/<filename>
app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Next.js frontend
        "http://localhost:3000",
        "http://127.0.0.1:3000",

        # Original frontend (backup)
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Request models
# --------------------------------------------------

class LoginRequest(BaseModel):
    Email: str = Field(min_length=3, max_length=254)
    Password: str = Field(min_length=1, max_length=1024)


class ComplaintCreate(BaseModel):
    RawDescription: str = Field(min_length=5, max_length=5000)
    Category: str
    Lat: Decimal = Field(ge=-90, le=90)
    Long: Decimal = Field(ge=-180, le=180)
    UrgencyScore: int = Field(ge=1, le=10)

    # The server determines the user from the JWT.
    # A client-supplied user_id is not used.
    asset_id: int = Field(gt=0)
    PhotoURL: str | None = Field(default=None, max_length=500)






class ComplaintStatusUpdate(BaseModel):
    Status: str = Field(
        pattern="^(Assigned|In Progress|Resolved|Closed)$"
    )
    Note: str | None = Field(default=None, max_length=2000)


class ComplaintAssignment(BaseModel):
    staff_id: int = Field(gt=0)

class AssetCreate(BaseModel):
    AssetType: str = Field(min_length=1, max_length=100)
    AssetName: str = Field(min_length=1, max_length=150)
    Lat: Decimal = Field(ge=-90, le=90)
    Long: Decimal = Field(ge=-180, le=180)
    InstallationDate: date
    OperationalStatus: str = Field(
        pattern="^(Operational|Under Maintenance|Non-Operational)$"
    )
    HealthScore: Decimal | None = Field(default=None, ge=0, le=100)
    LastMaintenanceDate: date | None = None
    Description: str | None = None


class AssetUpdate(AssetCreate):
    pass


class StaffAssetMaintenanceUpdate(BaseModel):
    OperationalStatus: str = Field(
        pattern="^(Operational|Under Maintenance|Non-Operational)$"
    )
    HealthScore: Decimal = Field(ge=0, le=100)
    LastMaintenanceDate: date | None = None

class ResolutionReview(BaseModel):
    Decision: str = Field(pattern="^(Approved|Rejected)$")
    Note: str | None = Field(default=None, max_length=2000)

# --------------------------------------------------
# Authentication helpers
# --------------------------------------------------

def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


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

        # Read the current role from the database on every request.
        # This prevents a token from preserving an outdated role.
        cursor.execute(
            """
            SELECT user_id, Fname, Lname, Email, Role
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


def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["Role"] != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator permission is required.",
        )
    return current_user

def require_staff(current_user: dict = Depends(get_current_user)):
    if current_user["Role"] != "Staff":
        raise HTTPException(
            status_code=403,
            detail="Staff permission is required.",
        )
    return current_user

def require_citizen(current_user: dict = Depends(get_current_user)):
    if current_user["Role"] != "Citizen":
        raise HTTPException(
            status_code=403,
            detail="Citizen permission is required.",
        )
    return current_user

# --------------------------------------------------
# Upload complaint attachment (Citizen only)
# --------------------------------------------------

@app.post("/uploads")
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_citizen),
):
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()

    # Check extension
    if extension not in ALLOWED_FILES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG, PNG, WEBP, GIF and PDF files are allowed.",
        )

    # Check MIME type
    if file.content_type != ALLOWED_FILES[extension]:
        raise HTTPException(
            status_code=400,
            detail="The file type does not match the selected extension.",
        )

    try:
        # Read at most 5 MB plus one byte to detect oversized files
        content = await file.read(MAX_UPLOAD_SIZE + 1)

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail="The maximum file size is 5 MB.",
            )

        # Check the actual file signature
        valid_signature = (
            (
                extension in {".jpg", ".jpeg"}
                and content.startswith(b"\xff\xd8\xff")
            )
            or (
                extension == ".png"
                and content.startswith(b"\x89PNG\r\n\x1a\n")
            )
            or (
                extension == ".gif"
                and content.startswith((b"GIF87a", b"GIF89a"))
            )
            or (
                extension == ".webp"
                and content.startswith(b"RIFF")
                and content[8:12] == b"WEBP"
            )
            or (
                extension == ".pdf"
                and content.startswith(b"%PDF-")
            )
        )

        if not valid_signature:
            raise HTTPException(
                status_code=400,
                detail="The file content does not match its file type.",
            )

        # Generate a random filename instead of trusting the original name
        filename = f"{uuid.uuid4().hex}{extension}"
        destination = UPLOAD_DIR / filename

        destination.write_bytes(content)

        return {
            "message": "File uploaded successfully.",
            "url": f"/uploads/{filename}",
            "filename": original_name,
        }

    finally:
        await file.close()


# --------------------------------------------------
# Home and authentication endpoints
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Urban Assets Management API is running!"
    }


@app.post("/auth/login")
def login(login_data: LoginRequest):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT user_id, Fname, Lname, Email, Role, PasswordHash
            FROM `USER`
            WHERE LOWER(Email) = LOWER(%s)
            """,
            (login_data.Email.strip(),),
        )

        user = cursor.fetchone()

        # Keep the response generic so it does not reveal
        # whether an email address exists.
        password_is_valid = False

        if user is not None:
            try:
                password_is_valid = password_hasher.verify(
                    login_data.Password,
                    user["PasswordHash"],
                )
            except Exception:
                password_is_valid = False

        if user is None or not password_is_valid:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password.",
            )

        token = create_access_token(user["user_id"])

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "user_id": user["user_id"],
                "Fname": user["Fname"],
                "Lname": user["Lname"],
                "Email": user["Email"],
                "Role": user["Role"],
            },
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to process login.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.get("/auth/me")
def get_my_account(current_user: dict = Depends(get_current_user)):
    return current_user


# --------------------------------------------------
# Assets
# --------------------------------------------------


@app.get("/assets")
def get_assets():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                asset_id,
                AssetType,
                AssetName,
                Lat,
                `Long`,
                InstallationDate,
                OperationalStatus,
                HealthScore,
                LastMaintenanceDate,
                Description
            FROM ASSET
            ORDER BY asset_id
            """
        )

        return cursor.fetchall()

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve assets.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()



@app.post("/assets", status_code=201)
def create_asset(
    asset: AssetCreate,
    admin: dict = Depends(require_admin),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO ASSET (
                AssetType,
                AssetName,
                Lat,
                `Long`,
                InstallationDate,
                OperationalStatus,
                HealthScore,
                LastMaintenanceDate,
                Description
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                asset.AssetType.strip(),
                asset.AssetName.strip(),
                asset.Lat,
                asset.Long,
                asset.InstallationDate,
                asset.OperationalStatus,
                asset.HealthScore,
                asset.LastMaintenanceDate,
                asset.Description,
            ),
        )

        asset_id = cursor.lastrowid
        connection.commit()

        return {
            "message": "Asset added successfully.",
            "asset_id": asset_id,
        }

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while adding asset.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()



@app.put("/assets/{asset_id}")
def update_asset(
    asset_id: int,
    asset: AssetUpdate,
    admin: dict = Depends(require_admin),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT asset_id FROM ASSET WHERE asset_id = %s",
            (asset_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found.",
            )

        cursor.execute(
            """
            UPDATE ASSET
            SET
                AssetType = %s,
                AssetName = %s,
                Lat = %s,
                `Long` = %s,
                InstallationDate = %s,
                OperationalStatus = %s,
                HealthScore = %s,
                LastMaintenanceDate = %s,
                Description = %s,
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE asset_id = %s
            """,
            (
                asset.AssetType.strip(),
                asset.AssetName.strip(),
                asset.Lat,
                asset.Long,
                asset.InstallationDate,
                asset.OperationalStatus,
                asset.HealthScore,
                asset.LastMaintenanceDate,
                asset.Description,
                asset_id,
            ),
        )

        connection.commit()

        return {
            "message": "Asset updated successfully.",
            "asset_id": asset_id,
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while updating asset.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

@app.put("/assets/{asset_id}/maintenance")
def update_asset_maintenance(
    asset_id: int,
    update: StaffAssetMaintenanceUpdate,
    staff: dict = Depends(require_staff),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether the asset exists.
        cursor.execute(
            "SELECT asset_id FROM ASSET WHERE asset_id = %s",
            (asset_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found.",
            )

        # Verify that this asset is linked to a complaint
        # assigned to the currently logged-in staff member.
        cursor.execute(
            """
            SELECT ca.assignment_id
            FROM COMPLAINT_ASSIGNMENTS ca
            JOIN COMPLAINT c
                ON ca.complaint_id = c.complaint_id
            WHERE ca.staff_id = %s
              AND c.asset_id = %s
            LIMIT 1
            """,
            (staff["user_id"], asset_id),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to update this asset.",
            )

        cursor.execute(
            """
            UPDATE ASSET
            SET
                OperationalStatus = %s,
                HealthScore = %s,
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE asset_id = %s
            """,
            (
                update.OperationalStatus,
                update.HealthScore,
                asset_id,
            ),
        )

        connection.commit()

        return {
            "message": "Asset maintenance details updated successfully.",
            "asset_id": asset_id,
            "OperationalStatus": update.OperationalStatus,
            "HealthScore": float(update.HealthScore),
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while updating asset maintenance.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    admin: dict = Depends(require_admin),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT asset_id FROM ASSET WHERE asset_id = %s",
            (asset_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found.",
            )

        cursor.execute(
            """
            SELECT complaint_id
            FROM COMPLAINT
            WHERE asset_id = %s
            LIMIT 1
            """,
            (asset_id,),
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete this asset because complaints are linked to it.",
            )

        cursor.execute(
            "DELETE FROM ASSET WHERE asset_id = %s",
            (asset_id,),
        )

        connection.commit()

        return {
            "message": "Asset deleted successfully.",
            "asset_id": asset_id,
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while deleting asset.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# --------------------------------------------------
# Staff directory (Admin only)
# --------------------------------------------------

@app.get("/staff")
def get_staff(admin: dict = Depends(require_admin)):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                s.staff_id,
                CONCAT(u.Fname, ' ', u.Lname) AS StaffName,
                s.Position
            FROM STAFF s
            JOIN `USER` u ON s.staff_id = u.user_id
            WHERE u.Role = 'Staff'
            ORDER BY s.staff_id
            """
        )

        return cursor.fetchall()

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to load staff.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


class SimilarityCheckRequest(BaseModel):
    RawDescription: str = Field(min_length=5, max_length=5000)
    Category: str = Field(min_length=1, max_length=100)


@app.post("/complaints/check-similar")
def check_similar_complaints(
    request: SimilarityCheckRequest,
    current_user: dict = Depends(require_citizen),
):
    try:
        response = requests.post(
            "http://127.0.0.1:8001/search",
            json={
                "description": request.RawDescription,
                "category": request.Category,
                "limit": 5,
            },
            timeout=10,
        )
        response.raise_for_status()

        return {
            "results": response.json().get("results", []),
            "message": "Similarity search completed.",
        }

    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Similarity search is temporarily unavailable.",
        )


@app.get("/debug-similarity-route")
def debug_similarity_route():
    return {
        "message": "Updated main.py is loaded",
        "similarity_route_registered": any(
            route.path == "/complaints/check-similar"
            for route in app.routes
        ),
    }

# --------------------------------------------------
# Submit a complaint (Citizen only)
# --------------------------------------------------



@app.post("/complaints", status_code=201)
def create_complaint(
    complaint: ComplaintCreate,
    current_user: dict = Depends(require_citizen),
):
    allowed_categories = {
        "Road",
        "Streetlight",
        "Garbage",
        "Water",
        "Drainage",
        "Electricity",
        "Traffic",
        "Other",
    }

    if complaint.Category not in allowed_categories:
        raise HTTPException(
            status_code=422,
            detail="Invalid complaint category.",
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT asset_id FROM ASSET WHERE asset_id = %s",
            (complaint.asset_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found.",
            )

        # Never trust a user_id supplied by the frontend.
        # Use the identity verified from the JWT instead.
        authenticated_user_id = current_user["user_id"]

        cursor.execute(
            """
            INSERT INTO COMPLAINT (
                RawDescription,
                Category,
                Lat,
                `Long`,
                UrgencyScore,
                PhotoURL,
                user_id,
                asset_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                complaint.RawDescription,
                complaint.Category,
                complaint.Lat,
                complaint.Long,
                complaint.UrgencyScore,
                complaint.PhotoURL,
                authenticated_user_id,
                complaint.asset_id,
            ),
        )

        complaint_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO COMPLAINT_STATUS (
                complaint_id,
                Status,
                Note
            )
            VALUES (%s, %s, %s)
            """,
            (
                complaint_id,
                "Submitted",
                "Complaint received successfully.",
            ),
        )

        connection.commit()

        return {
            "message": "Complaint submitted successfully.",
            "complaint_id": complaint_id,
            "status": "Submitted",
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while submitting complaint.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# Track a complaint (owner, assigned staff, or Admin)
# --------------------------------------------------

@app.get("/complaints/{complaint_id}")
def track_complaint(
    complaint_id: int,
    current_user: dict = Depends(get_current_user),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                c.complaint_id,
                c.RawDescription,
                c.Category,
                c.Lat,
                c.`Long`,
                c.UrgencyScore,
                c.SubmittedAt,
                c.PhotoURL,
                c.user_id,
                c.asset_id,
                a.AssetName,
                cs.Status,
                cs.Note AS StatusNote,
                cs.UpdatedAt AS StatusUpdatedAt
            FROM COMPLAINT AS c
            LEFT JOIN ASSET AS a
                ON c.asset_id = a.asset_id
            LEFT JOIN COMPLAINT_STATUS AS cs
                ON cs.complaint_id = c.complaint_id
            WHERE c.complaint_id = %s
            ORDER BY cs.UpdatedAt DESC
            LIMIT 1
            """,
            (complaint_id,),
        )

        result = cursor.fetchone()

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found.",
            )

        role = current_user["Role"]
        user_id = current_user["user_id"]

        if role == "Citizen" and result["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own complaints.",
            )

        if role == "Staff":
            cursor.execute(
                """
                SELECT assignment_id
                FROM COMPLAINT_ASSIGNMENTS
                WHERE complaint_id = %s
                  AND staff_id = %s
                LIMIT 1
                """,
                (complaint_id, user_id),
            )

            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view complaints assigned to you.",
                )

        return result

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve complaint details.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# Update complaint status (Admin only)
# --------------------------------------------------

@app.put("/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    update: ComplaintStatusUpdate,
    admin: dict = Depends(require_admin),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT complaint_id FROM COMPLAINT WHERE complaint_id = %s",
            (complaint_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found.",
            )

        cursor.execute(
            """
            INSERT INTO COMPLAINT_STATUS (
                complaint_id,
                Status,
                Note
            )
            VALUES (%s, %s, %s)
            """,
            (complaint_id, update.Status, update.Note),
        )

        cursor.execute(
            """
            UPDATE COMPLAINT
            SET UpdatedAt = CURRENT_TIMESTAMP
            WHERE complaint_id = %s
            """,
            (complaint_id,),
        )

        connection.commit()

        return {
            "message": "Complaint status updated successfully.",
            "complaint_id": complaint_id,
            "status": update.Status,
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while updating complaint status.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()



# --------------------------------------------------
# Update complaint status (Assigned Staff only)
# --------------------------------------------------

@app.put("/complaints/{complaint_id}/staff-status")
def update_staff_complaint_status(
    complaint_id: int,
    update: ComplaintStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    if current_user["Role"] != "Staff":
        raise HTTPException(
            status_code=403,
            detail="Staff permission is required.",
        )

    if update.Status not in ("In Progress", "Resolved"):
        raise HTTPException(
            status_code=400,
            detail="Staff can only select In Progress or Resolved.",
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)

        # Verify the complaint is assigned to this Staff member.
        cursor.execute(
            """
            SELECT complaint_id
            FROM COMPLAINT_ASSIGNMENTS
            WHERE complaint_id = %s AND staff_id = %s
            """,
            (complaint_id, current_user["user_id"]),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=403,
                detail="This complaint is not assigned to you.",
            )

        # Check the current complaint status.
        cursor.execute(
            """
            SELECT Status
            FROM COMPLAINT_STATUS
            WHERE complaint_id = %s
            ORDER BY status_id DESC
            LIMIT 1
            """,
            (complaint_id,),
        )

        latest = cursor.fetchone()

        if latest is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint status history was not found.",
            )

        if latest["Status"] in ("Resolved", "Closed"):
            raise HTTPException(
                status_code=409,
                detail="This complaint is already completed.",
            )

        if update.Status == "Resolved":
            # Detect an existing request that has not been reviewed.
            cursor.execute(
                """
                SELECT status_id
                FROM COMPLAINT_STATUS
                WHERE complaint_id = %s
                  AND Note LIKE 'RESOLUTION_REQUEST:%%'
                ORDER BY status_id DESC
                LIMIT 1
                """,
                (complaint_id,),
            )

            request_record = cursor.fetchone()

            if request_record is not None:
                cursor.execute(
                    """
                    SELECT status_id, Status, Note
                    FROM COMPLAINT_STATUS
                    WHERE complaint_id = %s
                      AND status_id > %s
                    ORDER BY status_id DESC
                    LIMIT 1
                    """,
                    (complaint_id, request_record["status_id"]),
                )

                later_record = cursor.fetchone()

                # Until Admin review is implemented, do not allow
                # duplicate requests for the same complaint.
                if later_record is None:
                    raise HTTPException(
                        status_code=409,
                        detail="A resolution request has already been submitted.",
                    )

            note = (update.Note or "").strip()
            request_note = f"RESOLUTION_REQUEST: {note or 'Staff requested resolution review.'}"

            cursor.execute(
                """
                INSERT INTO COMPLAINT_STATUS
                    (complaint_id, Status, Note)
                VALUES (%s, %s, %s)
                """,
                (complaint_id, "In Progress", request_note),
            )

            message = "Resolution request submitted for Admin review."

        else:
            cursor.execute(
                """
                INSERT INTO COMPLAINT_STATUS
                    (complaint_id, Status, Note)
                VALUES (%s, %s, %s)
                """,
                (complaint_id, "In Progress", update.Note),
            )

            message = "Complaint status updated to In Progress."

        cursor.execute(
            """
            UPDATE COMPLAINT
            SET UpdatedAt = CURRENT_TIMESTAMP
            WHERE complaint_id = %s
            """,
            (complaint_id,),
        )

        connection.commit()

        return {
            "message": message,
            "complaint_id": complaint_id,
            "status": "In Progress",
            "resolution_requested": update.Status == "Resolved",
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while updating complaint.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# Assign complaint to Staff (Admin only)
# --------------------------------------------------

@app.post("/complaints/{complaint_id}/assign", status_code=201)
def assign_complaint(
    complaint_id: int,
    assignment: ComplaintAssignment,
    admin: dict = Depends(require_admin),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT complaint_id FROM COMPLAINT WHERE complaint_id = %s",
            (complaint_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found.",
            )

        cursor.execute(
            """
            SELECT s.staff_id
            FROM STAFF AS s
            JOIN `USER` AS u ON u.user_id = s.staff_id
            WHERE s.staff_id = %s
              AND u.Role = 'Staff'
            """,
            (assignment.staff_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Staff member not found.",
            )

        cursor.execute(
            """
            INSERT INTO COMPLAINT_ASSIGNMENTS
                (staff_id, complaint_id)
            VALUES (%s, %s)
            """,
            (assignment.staff_id, complaint_id),
        )

        assignment_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO COMPLAINT_STATUS
                (complaint_id, Status, Note)
            VALUES (%s, %s, %s)
            """,
            (
                complaint_id,
                "Assigned",
                f"Complaint assigned to staff ID {assignment.staff_id}.",
            ),
        )

        cursor.execute(
            """
            UPDATE COMPLAINT
            SET UpdatedAt = CURRENT_TIMESTAMP
            WHERE complaint_id = %s
            """,
            (complaint_id,),
        )

        connection.commit()

        return {
            "message": "Complaint assigned successfully.",
            "assignment_id": assignment_id,
            "complaint_id": complaint_id,
            "staff_id": assignment.staff_id,
            "status": "Assigned",
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while assigning complaint.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# Retrieve complaints
# Admin: all complaints
# Citizen: own complaints
# Staff: complaints assigned to them
# --------------------------------------------------

@app.get("/complaints")
def get_complaints(current_user: dict = Depends(get_current_user)):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)

        query = """
            SELECT
                c.complaint_id,
                c.RawDescription,
                c.Category,
                c.UrgencyScore,
                c.SubmittedAt,
                c.PhotoURL,
                a.AssetName,
                COALESCE(latest.Status, 'Submitted') AS Status,
                latest.StatusNote,
                assigned.staff_id,
                assigned.StaffName,
                assigned.Position,

                CASE
                    WHEN latest.Status = 'In Progress'
                     AND latest.StatusNote LIKE 'RESOLUTION_REQUEST:%'
                    THEN TRUE
                    ELSE FALSE
                END AS ResolutionRequestPending,

                CASE
                    WHEN latest.StatusNote LIKE 'RESOLUTION_REQUEST:%'
                    THEN latest.StatusNote
                    ELSE NULL
                END AS ResolutionRequestNote,

                CASE
                    WHEN latest.StatusNote LIKE 'RESOLUTION_REQUEST:%'
                    THEN latest.status_id
                    ELSE NULL
                END AS ResolutionRequestId

            FROM COMPLAINT AS c

            LEFT JOIN ASSET AS a
                ON c.asset_id = a.asset_id

            LEFT JOIN (
                SELECT
                    cs1.status_id,
                    cs1.complaint_id,
                    cs1.Status,
                    cs1.Note AS StatusNote
                FROM COMPLAINT_STATUS AS cs1
                INNER JOIN (
                    SELECT
                        complaint_id,
                        MAX(status_id) AS latest_status_id
                    FROM COMPLAINT_STATUS
                    GROUP BY complaint_id
                ) AS latest_ids
                    ON cs1.status_id = latest_ids.latest_status_id
            ) AS latest
                ON c.complaint_id = latest.complaint_id

            LEFT JOIN (
                SELECT
                    ca.complaint_id,
                    ca.staff_id,
                    CONCAT(u.Fname, ' ', u.Lname) AS StaffName,
                    s.Position
                FROM COMPLAINT_ASSIGNMENTS AS ca
                INNER JOIN (
                    SELECT
                        complaint_id,
                        MAX(assignment_id) AS latest_assignment_id
                    FROM COMPLAINT_ASSIGNMENTS
                    GROUP BY complaint_id
                ) AS latest_assignments
                    ON ca.assignment_id = latest_assignments.latest_assignment_id
                INNER JOIN STAFF AS s
                    ON ca.staff_id = s.staff_id
                INNER JOIN `USER` AS u
                    ON u.user_id = s.staff_id
            ) AS assigned
                ON c.complaint_id = assigned.complaint_id
        """

        params = ()
        role = current_user["Role"]
        user_id = current_user["user_id"]

        if role == "Citizen":
            query += " WHERE c.user_id = %s"
            params = (user_id,)

        elif role == "Staff":
            query += """
                WHERE EXISTS (
                    SELECT 1
                    FROM COMPLAINT_ASSIGNMENTS AS my_assignment
                    WHERE my_assignment.complaint_id = c.complaint_id
                      AND my_assignment.staff_id = %s
                )
            """
            params = (user_id,)

        elif role != "Admin":
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to view complaints.",
            )

        query += " ORDER BY c.SubmittedAt DESC"

        cursor.execute(query, params)
        return cursor.fetchall()

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve complaints.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# Resolve complaint (Admin only)
# --------------------------------------------------

@app.put("/complaints/{complaint_id}/resolve")
def resolve_complaint(
    complaint_id: int,
    admin: dict = Depends(require_admin),
):
    # Direct resolution is disabled.
    # Admins must use /resolution-review to approve a
    # pending Staff resolution request.
    raise HTTPException(
        status_code=403,
        detail=(
            "Direct resolution is disabled. "
            "Use the resolution-review endpoint to approve "
            "a pending Staff resolution request."
        ),
    )



@app.put("/complaints/{complaint_id}/resolution-review")
def review_resolution_request(
    complaint_id: int,
    review: ResolutionReview,
    admin: dict = Depends(require_admin),
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        connection.start_transaction()

        # Lock this complaint's status history while reviewing it.
        cursor.execute(
            """
            SELECT status_id, Status, Note
            FROM COMPLAINT_STATUS
            WHERE complaint_id = %s
            ORDER BY status_id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (complaint_id,),
        )
        latest = cursor.fetchone()

        if latest is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint or status history not found.",
            )

        # A request is pending only when the latest status history
        # record is the Staff resolution request.
        if not (
            latest["Status"] == "In Progress"
            and (latest["Note"] or "").startswith("RESOLUTION_REQUEST:")
        ):
            raise HTTPException(
                status_code=409,
                detail="No pending resolution request was found.",
            )

        if review.Decision == "Approved":
            cursor.execute(
                """
                INSERT INTO COMPLAINT_STATUS
                    (complaint_id, Status, Note)
                VALUES (%s, %s, %s)
                """,
                (
                    complaint_id,
                    "Resolved",
                    "RESOLUTION_APPROVED: "
                    + (review.Note or "Admin approved the resolution."),
                ),
            )

            cursor.execute(
                """
                UPDATE COMPLAINT
                SET ResolvedAt = CURRENT_TIMESTAMP,
                    UpdatedAt = CURRENT_TIMESTAMP
                WHERE complaint_id = %s
                """,
                (complaint_id,),
            )

            cursor.execute(
                """
                UPDATE COMPLAINT_ASSIGNMENTS
                SET CompletedAt = CURRENT_TIMESTAMP
                WHERE complaint_id = %s
                  AND CompletedAt IS NULL
                """,
                (complaint_id,),
            )

            message = "Resolution request approved."

        else:
            # Keep the complaint In Progress and record the decision.
            cursor.execute(
                """
                INSERT INTO COMPLAINT_STATUS
                    (complaint_id, Status, Note)
                VALUES (%s, %s, %s)
                """,
                (
                    complaint_id,
                    "In Progress",
                    "RESOLUTION_REJECTED: "
                    + (review.Note or "Admin requested further work."),
                ),
            )

            cursor.execute(
                """
                UPDATE COMPLAINT
                SET UpdatedAt = CURRENT_TIMESTAMP
                WHERE complaint_id = %s
                """,
                (complaint_id,),
            )

            message = "Resolution request rejected; complaint remains In Progress."

        connection.commit()

        return {
            "message": message,
            "complaint_id": complaint_id,
            "decision": review.Decision,
            "status": "Resolved" if review.Decision == "Approved" else "In Progress",
        }

    except HTTPException:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while reviewing resolution request.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

