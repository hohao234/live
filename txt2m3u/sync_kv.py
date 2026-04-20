import os
import requests
import json
import base64
from concurrent.futures import ThreadPoolExecutor

# ---------------- 配置 ----------------
KV_ACCOUNT_ID = os.getenv("KV_ACCOUNT_ID")
KV_NAMESPACE_ID = os.getenv("KV_NAMESPACE_ID")
KV_API_TOKEN = os.getenv("KV_API_TOKEN")

# 定位到 Images 文件夹
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DIR = os.path.join(BASE_DIR, "Images")

BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{KV_ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}"
HEADERS = {"Authorization": f"Bearer {KV_API_TOKEN}"}

# 排除列表：不希望同步回 GitHub 的 Key
EXCLUDE_KEYS = {"json", "config"} 

def get_kv_keys():
    all_keys = []
    cursor = ""
    print("📡 正在读取 KV 远程清单...")
    while True:
        url = f"{BASE_URL}/keys?cursor={cursor}"
        res = requests.get(url, headers=HEADERS).json()
        if not res.get("success"): break
        all_keys.extend([item["name"] for item in res.get("result", [])])
        cursor = res.get("result_info", {}).get("cursor")
        if not cursor: break
    return set(all_keys)

def download_value(key):
    """从 KV 下载内容并保存到本地"""
    url = f"{BASE_URL}/values/{key}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        file_path = os.path.join(LOCAL_DIR, key.replace("/", os.sep))
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(res.content)
        print(f"📥 下载成功: {key}")

def sync():
    if not os.path.exists(LOCAL_DIR):
        os.makedirs(LOCAL_DIR)

    # 1. 获取 KV 所有的 Key (排除非图片 Key)
    kv_keys = {k for k in get_kv_keys() if k not in EXCLUDE_KEYS}

    # 2. 扫描本地已有文件
    local_files = set()
    for root, _, files in os.walk(LOCAL_DIR):
        for f in files:
            if f.startswith('.') or f.lower() == 'thumbs.db': continue
            rel_path = os.path.relpath(os.path.join(root, f), LOCAL_DIR).replace("\\", "/")
            local_files.add(rel_path)

    # 3. 计算差异
    to_download = kv_keys - local_files  # KV 有但本地没有 -> 下载
    to_delete = local_files - kv_keys    # 本地有但 KV 没了 -> 删除

    print(f"📊 KV 现有: {len(kv_keys)} | 本地文件: {len(local_files)}")
    print(f"🚀 动作: 需下载 {len(to_download)} | 需删除 {len(to_delete)}")

    # 4. 执行
    with ThreadPoolExecutor(max_workers=10) as executor:
        for k in to_download:
            executor.submit(download_value, k)
    
    for k in to_delete:
        file_path = os.path.join(LOCAL_DIR, k.replace("/", os.sep))
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ 本地已删除: {k}")

if __name__ == "__main__":
    sync()
