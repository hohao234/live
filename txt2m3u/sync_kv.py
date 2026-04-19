import os
import requests
import json
from concurrent.futures import ThreadPoolExecutor

# ---------------- 配置 ----------------
KV_ACCOUNT_ID = os.getenv("KV_ACCOUNT_ID")
KV_NAMESPACE_ID = os.getenv("KV_NAMESPACE_ID")
KV_API_TOKEN = os.getenv("KV_API_TOKEN")

# 获取脚本所在目录的上一级目录下的 Images 文件夹
# 结构：live/txt2m3u/sync_kv.py -> 向上找一层 -> live/Images
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DIR = os.path.join(BASE_DIR, "Images")

BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{KV_ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}"
HEADERS = {"Authorization": f"Bearer {KV_API_TOKEN}"}

def get_kv_keys():
    """获取 KV 中目前所有的 Key"""
    all_keys = []
    cursor = ""
    print("📡 正在获取 KV 远程列表...")
    while True:
        url = f"{BASE_URL}/keys?cursor={cursor}"
        res = requests.get(url, headers=HEADERS).json()
        if not res.get("success"):
            print(f"❌ 获取 Key 失败: {res}")
            break
        all_keys.extend([item["name"] for item in res.get("result", [])])
        cursor = res.get("result_info", {}).get("cursor")
        if not cursor: break
    return set(all_keys)

def upload(key, file_path):
    url = f"{BASE_URL}/values/{key}"
    try:
        with open(file_path, "rb") as f:
            res = requests.put(
                url, 
                headers={
                    "Authorization": f"Bearer {KV_API_TOKEN}", 
                    "Content-Type": "application/octet-stream"
                }, 
                data=f.read()
            )
        if res.status_code == 200:
            print(f"✅ 上传成功: {key}")
        else:
            print(f"❌ 上传失败: {key} | {res.text}")
    except Exception as e:
        print(f"⚠️ 错误: {key} | {e}")

def delete(key):
    url = f"{BASE_URL}/values/{key}"
    res = requests.delete(url, headers=HEADERS)
    if res.status_code == 200:
        print(f"🗑️ 已从 KV 删除: {key}")

def sync():
    if not os.path.exists(LOCAL_DIR):
        print(f"❌ 错误: 找不到目录 {LOCAL_DIR}")
        return

    # 1. 扫描本地文件 (相对于 Images 目录)
    local_files = {}
    for root, _, files in os.walk(LOCAL_DIR):
        for f in files:
            if f.startswith('.') or f.lower() == 'thumbs.db':
                continue
            # 计算相对于 Images 的路径，作为 KV 的 Key
            rel_path = os.path.relpath(os.path.join(root, f), LOCAL_DIR).replace("\\", "/")
            local_files[rel_path] = os.path.join(root, f)

    # 2. 获取 KV 列表
    kv_keys = get_kv_keys()

    # 3. 比对差异
    to_upload = set(local_files.keys()) - kv_keys
    to_delete = kv_keys - set(local_files.keys())

    print(f"📊 本地文件: {len(local_files)} | KV 现有: {len(kv_keys)}")
    print(f"🚀 待同步: 上传 {len(to_upload)} / 删除 {len(to_delete)}")

    # 4. 执行同步
    with ThreadPoolExecutor(max_workers=10) as executor:
        for k in to_upload:
            executor.submit(upload, k, local_files[k])
        for k in to_delete:
            executor.submit(delete, k)

if __name__ == "__main__":
    sync()
