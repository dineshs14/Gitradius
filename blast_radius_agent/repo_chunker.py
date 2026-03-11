import math
import os
import requests
import json

# Optionally skip binary or non-code files
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf",
    ".zip", ".tar", ".gz", ".mp3", ".mp4", ".wav", ".exe", ".dll", ".so", ".dylib"
}

def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 500) -> list[str]:
    """Split text into overlapping chunks of characters."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def read_repository_files(repo_path: str) -> dict[str, str]:
    """Read all valid text files in a given directory."""
    files_content = {}
    for root, _, files in os.walk(repo_path):
        if ".git" in root:
            continue
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in SKIP_EXTENSIONS:
                continue
            
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        files_content[filepath] = content
            except (UnicodeDecodeError, IsADirectoryError):
                pass
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
