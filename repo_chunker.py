import math
import os
import requests
import json

# ─────────────────────────────────────────────────────────────────
# File-type handling
# ─────────────────────────────────────────────────────────────────

# Extensions that are definitively binary/media — skip without reading
ALWAYS_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z", ".jar", ".war",
    ".mp3", ".mp4", ".wav", ".ogg", ".flac", ".avi", ".mov", ".mkv",
    ".exe", ".dll", ".so", ".dylib", ".class", ".pyc", ".pyo", ".pyd",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".db", ".sqlite", ".sqlite3", ".mdb",
    ".bin", ".dat", ".img", ".iso",
}

# Directories to skip
SKIP_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".tox", "dist", "build", "out", ".venv", "venv", "env",
    "coverage", ".nyc_output", ".next", ".nuxt",
}


def _is_binary_content(path: str) -> bool:
    """
    Detect binary files by scanning the first 8 KB for null bytes.
    Works for any file type without external dependencies.
    """
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 500) -> list[str]:
    """Split text into overlapping chunks of characters."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def read_repository_files(
    repo_path: str,
    max_file_kb: int = 512,
    progress_every: int = 200,
) -> dict[str, str]:
    """
    Read ALL readable text files under repo_path.

    Accepts any programming language, config format, markup, or script file.
    Automatically detects and skips binary/media files.
    Large files are truncated to max_file_kb to protect context windows.
    Prints progress for large repositories.
    """
    files_content: dict[str, str] = {}
    skipped_binary = 0
    total_scanned  = 0

    for root, dirs, files in os.walk(repo_path):
        # Prune directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for fname in files:
            filepath = os.path.join(root, fname)
            total_scanned += 1

            ext = os.path.splitext(fname)[1].lower()

            # Fast skip for known binary extensions
            if ext in ALWAYS_BINARY_EXTENSIONS:
                skipped_binary += 1
                continue

            # Content-based binary detection (null bytes)
            if _is_binary_content(filepath):
                skipped_binary += 1
                continue

            # Read as text (replace undecodable bytes gracefully)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue

            if not content.strip():
                continue

            # Truncate oversized files
            max_bytes = max_file_kb * 1024
            if len(content) > max_bytes:
                content = (
                    content[:max_bytes]
                    + f"\n\n... [TRUNCATED — exceeds {max_file_kb} KB] ..."
                )

            files_content[filepath] = content

            if total_scanned % progress_every == 0:
                print(f"    … scanned {total_scanned} files, "
                      f"{len(files_content)} readable so far …")

    if skipped_binary:
        print(f"  ⚠  Skipped {skipped_binary} binary/media file(s) out of {total_scanned} total.")

    return files_content

def get_embedding(text: str, model: str = "mistral") -> list[float]:
    """Get embedding from local Ollama model."""
    url = "http://localhost:11434/api/embeddings"
    payload = {
        "model": model,
        "prompt": text
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("embedding", [])
    except Exception as e:
        print(f"Failed to get embedding: {e}")
        return []

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not vec1 or not vec2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def find_relevant_chunks(issue_text: str, repo_path: str, model: str = "mistral", top_k: int = 5) -> list[dict]:
    """
    Chunk all files, embed them, embed the issue, and return the top_k most similar chunks.
    """
    print("  📦 Reading repository files...")
    files = read_repository_files(repo_path)
    print(f"  ✓ Found {len(files)} code files.")
    
    print("  ✂️  Chunking files...")
    all_chunks = []
    for filepath, content in files.items():
        rel_path = os.path.relpath(filepath, repo_path)
        chunks = chunk_text(content)
        for i, chunk_text_data in enumerate(chunks):
            # prepend file context to chunk
            chunk_with_context = f"File: {rel_path}\nChunk {i+1}:\n{chunk_text_data}"
            all_chunks.append({
                "path": rel_path,
                "text": chunk_with_context
            })
    
    print(f"  ✓ Created {len(all_chunks)} chunks.")
    
    print(f"  🧠 Embedding Issue with {model}...")
    issue_embed = get_embedding(issue_text, model=model)
    if not issue_embed:
        print("  ✖ Failed to embed issue. Cannot perform RAG.")
        return []
    
    print(f"  🧠 Embedding {len(all_chunks)} chunks (this might take a few moments)...")
    # For a real big repo, this could take a while with Ollama.
    # To keep it somewhat fast for PoC, we will embed chunks one by one
    # If the repo is massive, this local loop might take a long time.
    for i, chunk in enumerate(all_chunks):
        if i > 0 and i % 50 == 0:
            print(f"    ... embedded {i}/{len(all_chunks)} chunks")
        chunk["embedding"] = get_embedding(chunk["text"], model=model)
        chunk["score"] = cosine_similarity(issue_embed, chunk["embedding"])
    
    # Sort by score descending
    all_chunks.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    
    top_chunks = all_chunks[:top_k]
    print(f"  ✓ Selected top {len(top_chunks)} relevant chunks based on similarity.")
    for idx, c in enumerate(top_chunks):
        print(f"    {idx+1}. {c['path']} (score: {c.get('score', 0):.4f})")
        
    return top_chunks
