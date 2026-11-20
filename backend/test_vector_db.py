
import chromadb

# Create a persistent vector database for UrbanCare
client = chromadb.PersistentClient(path="./chroma_data")

# Create a collection for complaint descriptions
collection = client.get_or_create_collection(
    name="urban_complaints"
)

# Add sample complaints
collection.upsert(
    ids=["test_001", "test_002", "test_003"],
    documents=[
        "Garbage is overflowing near the main road.",
        "Waste is not collected near the bus stop.",
        "The streetlight is not working outside my house."
    ]
)

# Search for complaints with a similar meaning
results = collection.query(
    query_texts=["There is too much rubbish on the road."],
    n_results=2
)

print("\nSimilar complaints found:\n")

for complaint_id, description, distance in zip(
    results["ids"][0],
    results["documents"][0],
    results["distances"][0]
):
    print(f"ID: {complaint_id}")
    print(f"Description: {description}")
    print(f"Distance: {distance:.4f}")
    print("-" * 40)

print("Vector database test completed!")
