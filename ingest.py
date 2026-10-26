"""Read docs, chunk them, tag each chunk with role permissions, store in Chroma."""
import re
from pathlib import Path
import chromadb

DOCS_DIR = Path("data/docs")
DB_DIR = "chroma_db"
COLLECTION = "company_kb"
ROLES = ["employee", "support", "sales", "hr"]


def parse_doc(path: Path):
    """Split optional '---' header (key: value lines) from the body."""
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.split("#")[0].strip()
        body = m.group(2)
    return meta, body.strip()


def chunk(text: str, max_chars: int = 800, overlap: int = 100):
    """Paragraph-based chunking with a small character overlap."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) + 2 > max_chars:
            chunks.append(cur)
            cur = cur[-overlap:] + "\n\n" + p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def allowed_roles(meta: dict):
    raw = meta.get("allowed_roles", "all").lower()
    if raw == "all":
        return set(ROLES)
    return {r.strip() for r in raw.split(",") if r.strip()}


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=DB_DIR)
    return _client


def get_collection(client=None):
    return (client or _get_client()).get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"})


def index_file(path: Path, col=None) -> int:
    """(Re)index one document. Replaces any older chunks of the same file."""
    col = col or get_collection()
    col.delete(where={"source": path.name})
    meta, body = parse_doc(path)
    roles = allowed_roles(meta)
    ids, docs, metas = [], [], []
    for i, piece in enumerate(chunk(body)):
        m = {"source": path.name, "title": meta.get("title", path.stem),
             "updated": meta.get("updated", "unknown"), "chunk": i}
        for r in ROLES:  # Chroma metadata must be scalar, so one boolean per role
            m[f"allow_{r}"] = r in roles
        ids.append(f"{path.stem}-{i}")
        docs.append(piece)
        metas.append(m)
    if ids:
        col.add(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def remove_source(filename: str):
    get_collection().delete(where={"source": filename})


def main():
    """Rebuild the whole index from data/docs."""
    try:
        _get_client().delete_collection(COLLECTION)
    except Exception:
        pass
    col = get_collection()
    total = 0
    for path in sorted(DOCS_DIR.glob("*.md")):
        n = index_file(path, col)
        total += n
        print(f"{path.name}: {n} chunks, roles={sorted(allowed_roles(parse_doc(path)[0]))}")
    print(f"Done. {total} chunks indexed.")


if __name__ == "__main__":
    main()
