from pathlib import Path
import chromadb

BASE_DIR = Path(__file__).resolve().parent
client = chromadb.PersistentClient(
    path=str(BASE_DIR / "chroma_data")
)
collection = client.get_or_create_collection(
    name="urban_complaints"
)

test_id = "rud_test_001"

try:
    # CREATE
    collection.upsert(
        ids=[test_id],
        documents=["Temporary test complaint: broken streetlight."],
        metadatas=[{"category": "RUD_TEST"}],
    )
    print("CREATE:", collection.get(ids=[test_id])["ids"])

    # READ
    record = collection.get(
        ids=[test_id],
        include=["documents", "metadatas"],
    )
    print("READ:", record["documents"][0])

    # UPDATE
    collection.update(
        ids=[test_id],
        documents=["Updated test complaint: damaged road."],
        metadatas=[{"category": "RUD_TEST_UPDATED"}],
    )
    record = collection.get(
        ids=[test_id],
        include=["documents", "metadatas"],
    )
    print("UPDATE:", record["documents"][0])
    print("UPDATED CATEGORY:", record["metadatas"][0]["category"])

    # DELETE
    collection.delete(ids=[test_id])
    print("DELETE: remaining records =", collection.get(ids=[test_id])["ids"])

finally:
    # Safety cleanup if a previous step fails
    collection.delete(ids=[test_id])
    print("CLEANUP: test record removed")