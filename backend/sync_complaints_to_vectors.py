
import chromadb
import mysql.connector
from pathlib import Path
from dotenv import load_dotenv
import os

# Load database configuration from the existing backend .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Connect to MySQL
db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "urban_assets_db"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)

# Store ChromaDB data inside the backend project
client = chromadb.PersistentClient(
    path=str(BASE_DIR / "chroma_data")
)

collection = client.get_or_create_collection(
    name="urban_complaints"
)

try:
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT complaint_id, RawDescription, Category
        FROM COMPLAINT
        ORDER BY complaint_id
    """)

    complaints = cursor.fetchall()

    if not complaints:
        print("No complaints found in MySQL.")
    else:
        ids = []
        documents = []
        metadatas = []

        for complaint in complaints:
            ids.append(str(complaint["complaint_id"]))
            documents.append(complaint["RawDescription"])
            metadatas.append({
                "category": complaint["Category"]
            })

        # ChromaDB generates embeddings automatically when documents
        # are added to a collection without explicit embeddings.
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(f"Synced {len(complaints)} complaints to ChromaDB.")

        # Test semantic search
        results = collection.query(
            query_texts=["There is a damaged road with a pothole."],
            n_results=min(3, len(complaints))
        )

        print("\nSimilar complaints:")
        for complaint_id, description, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            print(f"\nComplaint ID: {complaint_id}")
            print(f"Category: {metadata['category']}")
            print(f"Description: {description}")
            print(f"Distance: {distance:.4f}")

finally:
    db.close()

print("\nSynchronization and search test completed.")
