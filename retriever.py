"""Role-filtered semantic search."""
from ingest import get_collection, ROLES

MAX_DISTANCE = 0.7  # cosine distance; lower = more similar. Tune for your data.


def retrieve(question: str, role: str, k: int = 4):
    if role not in ROLES:
        raise ValueError(f"Unknown role '{role}'. Choose from {ROLES}")
    res = get_collection().query(
        query_texts=[question],
        n_results=k,
        where={f"allow_{role}": True},  # permission filter happens BEFORE the LLM sees anything
    )
    hits = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        if dist <= MAX_DISTANCE:
            hits.append({"text": text, "meta": meta, "distance": round(dist, 3)})
    return hits
