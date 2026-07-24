from huggingface_hub import snapshot_download

print("Downloading BGE-M3...")

snapshot_download(
    repo_id="BAAI/bge-m3",
    local_dir="models/bge-m3"
)

print("Downloading Qwen...")

snapshot_download(
    repo_id="Qwen/Qwen2.5-3B-Instruct",
    local_dir="models/qwen2.5"
)

print("Done.")