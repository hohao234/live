import os
import requests
import json
from concurrent.futures import ThreadPoolExecutor

# 从环境变量读取（安全第一）
KV_ACCOUNT_ID = os.getenv("KV_ACCOUNT_ID")
KV_NAMESPACE_ID = os.getenv("KV_NAMESPACE_ID")
KV_API_TOKEN = os.getenv("KV_API_TOKEN")
LOCAL_DIR = "Images/CCTV"  # 注意：在 Action 中使用相对路径

BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{KV_ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}"
HEADERS = {"Authorization": f"Bearer {KV_API_TOKEN}"}

def get_kv_keys():
    """获取 KV 中目前所有的 Key"""
    all_keys = []
    cursor = ""
    while True:
        url = f"{BASE_URL}/keys?cursor={cursor}"
        res = requests.get(url, headers=HEADERS).json()
        if not res.get("success"): break
        all_keys.extend([item["name"] for item in res.get("result", [])])
        cursor = res.get("result_info", {}).get("cursor")
        if not cursor: break
    return set(all_keys)

def upload(key, file_path):
    url = f"{BASE_URL}/values/{key}"
    with open(file_path, "rb") as f:
        res = requests.put(url, headers={"Authorization": f"Bearer {KV_API_TOKEN}", "Content-Type": "application/octet-stream"}, data=f.read())
    if res.status_code == 200: print(f"✅ 上传: {key}")

def delete(key):
    url = f"{BASE_URL}/values/{key}"
    res = requests.delete(url, headers=HEADERS)
    if res.status_code == 200: print(f"🗑️ 删除: {key}")

def sync():
    # 1. 获取本地文件列表
    local_files = {}
    for root, _, files in os.walk(LOCAL_DIR):
        for f in files:
            if f.startswith('.') or f.lower() == 'thumbs.db': continue
            rel_path = os.path.relpath(os.path.join(root, f), LOCAL_DIR).replace("\\", "/")
            local_files[rel_path] = os.path.join(root, f)

    # 2. 获取 KV 远程列表
    kv_keys = get_kv_keys()

    # 3. 计算差异
    to_upload = set(local_files.keys()) - kv_keys
    to_delete = kv_keys - set(local_files.keys())

    print(f"📊 统计: 待上传 {len(to_upload)}, 待删除 {len(to_delete)}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        for k in to_upload: executor.submit(upload, k, local_files[k])
        for k in to_delete: executor.submit(delete, k)

if __name__ == "__main__":
    sync()
