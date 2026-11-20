# 🏙️ UrbanCare – Intelligent Urban Assets and Complaint Management System

A web-based civic complaint and urban infrastructure management system that helps citizens report city problems, staff handle assigned complaints, and administrators manage assets, assignments, and complaint resolutions.

UrbanCare combines a relational database (MySQL) with a vector database (ChromaDB) to support structured complaint management and semantic similarity detection.

---

## 📌 Project Overview

UrbanCare provides a centralized platform for managing urban infrastructure and civic complaints such as:

- Road damage and potholes
- Streetlight issues
- Garbage accumulation
- Water supply problems
- Drainage issues
- Other civic infrastructure complaints

The system provides separate functionalities for Citizens, Staff, and Admin, with role-based permissions and a controlled complaint-resolution workflow.

---

## 🎯 Objectives

- Digitize urban complaint management.
- Provide a centralized platform for citizens to report civic problems.
- Manage urban infrastructure assets efficiently.
- Assign complaints to staff members.
- Track complaint status and resolution progress.
- Verify complaint resolutions through administrator review.
- Detect semantically similar complaints using vector embeddings.
- Maintain secure role-based access control.

---

## ✨ Features

### 🔐 Authentication and Authorization
- User login and authentication.
- JWT-based authentication.
- Role-based access control.
- Separate access permissions for Citizens, Staff, and Admin.

### 📝 Complaint Management
- Register civic complaints.
- Store complaint descriptions, categories, locations, urgency, and related information.
- View complaints according to user permissions.
- Track complaint progress and status.

### 🏗️ Urban Asset Management
- Manage infrastructure assets.
- Store asset name, type, coordinates, installation date, operational status, health score, and maintenance information.
- Add, update, and delete assets through authorized operations.

### 👨‍🔧 Complaint Assignment
- Assign complaints to staff members.
- Maintain complaint assignment records.
- Allow staff to handle their assigned complaints.

### ✅ Resolution Verification
- Staff submit resolution requests after addressing complaints.
- Admin reviews resolution requests.
- Approved resolutions mark complaints as resolved.
- Rejected resolutions return complaints to In Progress.

### 🔎 Similar Complaint Detection
- Uses ChromaDB vector database.
- Stores complaint embeddings.
- Performs semantic similarity search.
- Helps identify complaints with similar meanings despite differences in wording.

### 📍 Location-Based Complaint Management
- Stores latitude and longitude for complaints and urban assets.
- Supports location-associated civic issue management.

### 📎 Complaint Attachments
- Supports complaint-related file and image uploads.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| HTML5 | Frontend page structure |
| CSS3 | Frontend styling and layout |
| JavaScript | Frontend interactions and API requests |
| Python | Backend logic |
| FastAPI | Backend API framework |
| MySQL | Primary relational database |
| ChromaDB | Vector database and similarity search |
| JWT | Authentication |
| SQL | Database queries and management |
| Git | Version control |
| GitHub | Source code hosting |

---

## 🏛️ System Architecture

```text
               CITIZEN / STAFF / ADMIN
                         |
                         v
                 HTML / CSS / JS
                    FRONTEND
                         |
                         v
                  FASTAPI BACKEND
                 Port: 8010
                         |
              +----------+-----------+
              |                      |
              v                      v
          MYSQL DATABASE       VECTOR SERVICE
                                     |
                                     v
                                  CHROMADB
```

### Components

- **Frontend:** User interface built with HTML, CSS, and JavaScript.
- **Main Backend:** FastAPI application responsible for authentication, authorization, complaint operations, asset management, and business logic.
- **MySQL:** Stores structured application information.
- **Vector Service:** Separate FastAPI service that manages vector database operations.
- **ChromaDB:** Stores embeddings and performs similarity search.

---

## 🗄️ Database Management

### MySQL

MySQL is the primary relational database used to store structured data.

The database includes tables for:

- User
- Citizen
- Staff
- Department
- Asset
- Complaint
- Complaint Assignments
- Complaint Status
- Complaint Details

MySQL manages structured information and relationships between citizens, staff, departments, complaints, assets, and assignments.

### ChromaDB

ChromaDB is used to store complaint embeddings and perform semantic similarity search.

It helps retrieve complaints with similar meanings even when the descriptions contain different words.

**Example:**

| Complaint | Description |
|---|---|
| Complaint A | There is a large pothole on the road. |
| Complaint B | The road is damaged and vehicles are struggling to pass. |

The system can identify that these complaints may describe a similar issue using vector similarity rather than exact keyword matching.

---

## 🔄 Complaint Workflow

```text
Citizen Submits Complaint
          |
          v
Complaint Stored in MySQL
          |
          v
Similar Complaint Check
          |
          v
Admin Assigns Complaint
          |
          v
Staff Handles Complaint
          |
          v
Staff Submits Resolution Request
          |
          v
Admin Reviews Resolution
          |
      +---+---+
      |       |
   Approved Rejected
      |       |
      v       v
  Resolved In Progress
```

---

## 👥 User Roles

| Role | Responsibilities |
|---|---|
| Citizen | Submit complaints and access citizen complaint features. |
| Staff | Handle assigned complaints and submit resolution requests. |
| Admin | Manage assets, complaints, assignments, users, and resolution approvals. |

---

## 📂 Project Structure

```text
UrbanCare/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── vector_service.py
│   ├── sync_complaints_to_vectors.py
│   ├── test_vector_db.py
│   ├── test_vector_rud.py
│   ├── setup_demo_passwords.py
│   ├── main_before_auth.py
│   ├── chroma_data/
│   ├── uploads/
│   ├── .env
│   ├── .venv/
│   └── .venv-vector/
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── chroma_data/
├── .gitignore
└── README.md
```

> Virtual environments, `.env` files, uploaded files, and generated vector database files are local resources and should not be committed to GitHub.

---

# 🚀 How to Run the Project Locally

## Prerequisites

Make sure the following software is installed:

- Python
- MySQL Server
- Git
- Visual Studio Code (recommended)

The project uses Python virtual environments to manage dependencies.

---

## 1️⃣ Start MySQL Database

Start your local MySQL server using your installed MySQL service or MySQL Workbench.

Make sure:

- MySQL server is running.
- The UrbanCare database exists.
- Database tables are created.
- Backend database credentials are configured in the backend `.env` file.

The database connection configuration is maintained in:

```text
backend/database.py
```

Sensitive database credentials should be maintained in `.env` and not uploaded to GitHub.

---

## 2️⃣ Start the Main Backend

### Backend location

```text
UrbanCare/backend/
```

### Open PowerShell – Terminal 1

Navigate to the backend directory:

```powershell
cd "YOUR_PROJECT_PATH\backend"
```

For example:

```powershell
cd "C:\Users\Laxmikant\urban_assets_project\backend"
```

Activate the Python virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start the FastAPI backend:

```powershell
uvicorn main:app --reload --port 8010
```

### Backend URL

```text
http://127.0.0.1:8010
```

### API documentation (Swagger)

```text
http://127.0.0.1:8010/docs
```

Swagger UI can be used to inspect and test the backend API endpoints.

---

## 3️⃣ Start the ChromaDB Vector Service

The vector database runs through a separate FastAPI service.

### Vector service location

```text
UrbanCare/backend/vector_service.py
```

### Open PowerShell – Terminal 2

Navigate to the backend folder:

```powershell
cd "C:\Users\Laxmikant\urban_assets_project\backend"
```

Activate the vector service environment:

```powershell
.\.venv-vector\Scripts\Activate.ps1
```

Start the vector service:

```powershell
uvicorn vector_service:app --reload --port 8001
```

### Vector service URL

```text
http://127.0.0.1:8001
```

The vector service handles complaint embedding storage, vector retrieval, and similarity search using ChromaDB.

The ChromaDB storage directory is configured in the vector service. Generated database files are stored locally and should not be uploaded to GitHub.

---

## 4️⃣ Start the Frontend

### Frontend location

```text
UrbanCare/frontend/
```

The frontend uses the original HTML, CSS, and JavaScript implementation.

### Open PowerShell – Terminal 3

Navigate to the frontend folder:

```powershell
cd "C:\Users\Laxmikant\urban_assets_project\frontend"
```

Start the frontend web server:

```powershell
python -m http.server 5500
```

### Frontend URL

```text
http://localhost:5500
```

Open the URL in your browser to access the UrbanCare application.

---

## ▶️ Running All Components

All three services must be running simultaneously.

| Component | Terminal | Port | Command |
|---|---|---:|---|
| MySQL | MySQL Service / Workbench | 3306 | Start MySQL server |
| Main Backend | Terminal 1 | 8010 | `uvicorn main:app --reload --port 8010` |
| Vector Service | Terminal 2 | 8001 | `uvicorn vector_service:app --reload --port 8001` |
| Frontend | Terminal 3 | 5500 | `python -m http.server 5500` |

### Application access

| Service | URL |
|---|---|
| Frontend | http://localhost:5500 |
| Main Backend | http://127.0.0.1:8010 |
| Backend API Docs | http://127.0.0.1:8010/docs |
| Vector Service | http://127.0.0.1:8001 |

---

## 🧪 Testing

The project includes testing scripts for vector database functionality.

### Vector database test

Navigate to the backend folder and activate the vector environment if required.

```powershell
python test_vector_db.py
```

### Vector database CRUD test

```powershell
python test_vector_rud.py
```

These scripts are used to test vector database operations and functionality.

---

## 🔐 Security

- JWT-based authentication.
- Role-based access control.
- Protected API endpoints.
- Authorization checks for administrative operations.
- Controlled complaint resolution and approval.
- Sensitive configuration stored in environment variables.

---

## 📈 Future Enhancements

- Interactive map for urban asset visualization.
- Complaint heatmaps.
- Notification system.
- Improved semantic duplicate complaint detection.
- Infrastructure maintenance prediction.
- Complaint analytics and reporting.
- Mobile-responsive enhancements.

---

## 🎓 Academic Project

Developed as a DBMS Mini Project.

**Project Name:** Intelligent Urban Assets and Complaint Management System

**Short Name:** UrbanCare

---

## 👨‍💻 Contributors

Developed as part of an academic DBMS mini-project.

---

## 📄 License

This project is developed for academic purposes.
