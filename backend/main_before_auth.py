
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from decimal import Decimal
import mysql.connector
from fastapi.middleware.cors import CORSMiddleware
from database import get_db_connection


app = FastAPI(
    title="Intelligent Urban Assets and Complaint Management System",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model for creating a complaint
class ComplaintCreate(BaseModel):
    RawDescription: str = Field(min_length=5, max_length=5000)
    Category: str
    Lat: Decimal = Field(ge=-90, le=90)
    Long: Decimal = Field(ge=-180, le=180)
    UrgencyScore: int = Field(ge=1, le=10)
    user_id: int = Field(gt=0)
    asset_id: int = Field(gt=0)
    PhotoURL: str | None = Field(default=None, max_length=500)


# Home endpoint
@app.get("/")
def home():
    return {
        "message": "Urban Assets Management API is running!"
    }


# Retrieve all assets
@app.get("/assets")
def get_assets():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                asset_id,
                AssetType,
                AssetName,
                Lat,
                `Long`,
                OperationalStatus,
                HealthScore,
                Description
            FROM ASSET
        """)

        return cursor.fetchall()

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve assets."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

@app.get("/staff")
def get_staff():
    connection = get_db_connection()

    if connection is None:
        raise HTTPException(
            status_code=500,
            detail="Database connection failed."
        )

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                s.staff_id,
                CONCAT(u.Fname, ' ', u.Lname) AS StaffName,
                s.Position
            FROM STAFF s
            JOIN `USER` u
                ON s.staff_id = u.user_id
            WHERE u.Role = 'Staff'
            ORDER BY s.staff_id
        """)

        return cursor.fetchall()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load staff: {str(e)}"
        )

    finally:
        cursor.close()
        connection.close()
# Submit a new complaint
@app.post("/complaints", status_code=201)
def create_complaint(complaint: ComplaintCreate):
    allowed_categories = {
        "Road",
        "Streetlight",
        "Garbage",
        "Water",
        "Drainage",
        "Electricity",
        "Traffic",
        "Other"
    }

    if complaint.Category not in allowed_categories:
        raise HTTPException(
            status_code=422,
            detail="Invalid complaint category."
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether the user exists
        cursor.execute(
            "SELECT user_id FROM `USER` WHERE user_id = %s",
            (complaint.user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="User not found."
            )

        # Check whether the asset exists
        cursor.execute(
            "SELECT asset_id FROM ASSET WHERE asset_id = %s",
            (complaint.asset_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found."
            )

        # Insert the complaint
        cursor.execute("""
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
        """, (
            complaint.RawDescription,
            complaint.Category,
            complaint.Lat,
            complaint.Long,
            complaint.UrgencyScore,
            complaint.PhotoURL,
            complaint.user_id,
            complaint.asset_id
        ))

        complaint_id = cursor.lastrowid

        # Add the initial complaint status
        cursor.execute("""
            INSERT INTO COMPLAINT_STATUS (
                complaint_id,
                Status,
                Note
            )
            VALUES (%s, %s, %s)
        """, (
            complaint_id,
            "Submitted",
            "Complaint received successfully."
        ))

        connection.commit()

        return {
            "message": "Complaint submitted successfully.",
            "complaint_id": complaint_id,
            "status": "Submitted"
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while submitting complaint."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# Track a complaint by its ID
@app.get("/complaints/{complaint_id}")
def track_complaint(complaint_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
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
        """, (complaint_id,))

        result = cursor.fetchone()

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found."
            )

        return result

    except HTTPException:
        raise

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve complaint details."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# Request model for updating complaint status
class ComplaintStatusUpdate(BaseModel):
    Status: str = Field(
        pattern="^(Assigned|In Progress|Resolved|Closed)$"
    )
    Note: str | None = Field(default=None, max_length=2000)


# Update complaint status
@app.put("/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    update: ComplaintStatusUpdate
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether the complaint exists
        cursor.execute(
            "SELECT complaint_id FROM COMPLAINT WHERE complaint_id = %s",
            (complaint_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found."
            )

        # Save the new status in the status history
        cursor.execute("""
            INSERT INTO COMPLAINT_STATUS (
                complaint_id,
                Status,
                Note
            )
            VALUES (%s, %s, %s)
        """, (
            complaint_id,
            update.Status,
            update.Note
        ))

        # Update the complaint's last-updated timestamp
        cursor.execute("""
            UPDATE COMPLAINT
            SET UpdatedAt = CURRENT_TIMESTAMP
            WHERE complaint_id = %s
        """, (complaint_id,))

        connection.commit()

        return {
            "message": "Complaint status updated successfully.",
            "complaint_id": complaint_id,
            "status": update.Status
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while updating complaint status."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# Request model for assigning a complaint
class ComplaintAssignment(BaseModel):
    staff_id: int = Field(gt=0)


# Assign a complaint to a staff member
@app.post("/complaints/{complaint_id}/assign", status_code=201)
def assign_complaint(
    complaint_id: int,
    assignment: ComplaintAssignment
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether the complaint exists
        cursor.execute(
            "SELECT complaint_id FROM COMPLAINT WHERE complaint_id = %s",
            (complaint_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found."
            )

        # Check whether the staff member exists
        cursor.execute(
            """
            SELECT s.staff_id
            FROM STAFF AS s
            JOIN `USER` AS u ON u.user_id = s.staff_id
            WHERE s.staff_id = %s AND u.Role = 'Staff'
            """,
            (assignment.staff_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Staff member not found."
            )

        # Insert the assignment
        cursor.execute(
            """
            INSERT INTO COMPLAINT_ASSIGNMENTS
                (staff_id, complaint_id)
            VALUES (%s, %s)
            """,
            (assignment.staff_id, complaint_id)
        )

        assignment_id = cursor.lastrowid

        # Record the Assigned status
        cursor.execute(
            """
            INSERT INTO COMPLAINT_STATUS
                (complaint_id, Status, Note)
            VALUES (%s, %s, %s)
            """,
            (
                complaint_id,
                "Assigned",
                f"Complaint assigned to staff ID {assignment.staff_id}."
            )
        )

        connection.commit()

        return {
            "message": "Complaint assigned successfully.",
            "assignment_id": assignment_id,
            "complaint_id": complaint_id,
            "staff_id": assignment.staff_id,
            "status": "Assigned"
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while assigning complaint."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# Retrieve all complaints with asset and staff details
@app.get("/complaints")
def get_complaints():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                c.complaint_id,
                c.RawDescription,
                c.Category,
                c.UrgencyScore,
                c.SubmittedAt,
                a.AssetName,
                COALESCE(latest.Status, 'Submitted') AS Status,
                latest.StatusNote,
                assigned.staff_id,
                assigned.StaffName,
                assigned.Position
            FROM COMPLAINT AS c

            LEFT JOIN ASSET AS a
                ON c.asset_id = a.asset_id

            LEFT JOIN (
                SELECT
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

            ORDER BY c.SubmittedAt DESC
        """)

        return cursor.fetchall()

    except mysql.connector.Error:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve complaints."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

# Resolve a complaint
@app.put("/complaints/{complaint_id}/resolve")
def resolve_complaint(complaint_id: int):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether the complaint exists
        cursor.execute(
            """
            SELECT complaint_id
            FROM COMPLAINT
            WHERE complaint_id = %s
            """,
            (complaint_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Complaint not found."
            )

        # Check the latest status
        cursor.execute(
            """
            SELECT Status
            FROM COMPLAINT_STATUS
            WHERE complaint_id = %s
            ORDER BY status_id DESC
            LIMIT 1
            """,
            (complaint_id,)
        )

        latest_status = cursor.fetchone()

        if latest_status is None:
            raise HTTPException(
                status_code=409,
                detail="Complaint has no status history."
            )

        if latest_status["Status"] in ("Resolved", "Closed"):
            raise HTTPException(
                status_code=409,
                detail="Complaint is already resolved or closed."
            )

        # Record the resolved status
        cursor.execute(
            """
            INSERT INTO COMPLAINT_STATUS
                (complaint_id, Status, Note)
            VALUES (%s, %s, %s)
            """,
            (
                complaint_id,
                "Resolved",
                "Complaint has been resolved."
            )
        )


        # Update the complaint's resolution timestamp
        cursor.execute(
            """
            UPDATE COMPLAINT
            SET ResolvedAt = CURRENT_TIMESTAMP,
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE complaint_id = %s
            """,
            (complaint_id,)
        )

        # Mark the active staff assignment as completed
        cursor.execute(
            """
            UPDATE COMPLAINT_ASSIGNMENTS
            SET CompletedAt = CURRENT_TIMESTAMP
            WHERE complaint_id = %s
              AND CompletedAt IS NULL
            """,
            (complaint_id,)
        )

        connection.commit()


        return {
            "message": "Complaint resolved successfully.",
            "complaint_id": complaint_id,
            "status": "Resolved"
        }

    except HTTPException:
        raise

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error while resolving complaint."
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
