import os
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor

# ---------------- 配置 ----------------
KV_ACCOUNT_ID = os.getenv("KV_ACCOUNT_ID")
KV_NAMESPACE_ID = os.getenv("KV_NAMESPACE_ID")
KV_API_TOKEN = os.getenv("KV_API_TOKEN")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DIR = os.path.join(BASE_DIR, "Images")

BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{KV_ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}"
HEADERS = {"Authorization": f"Bearer {KV_API_TOKEN}"}

# 自动终止标志
STOP_SYNC = False

def get_kv_keys():
    all_keys = []
    cursor = ""
    print("📡 正在获取 KV 远程列表...")
    try:
        while True:
            url = f"{BASE_URL}/keys?cursor={cursor}"
            res = requests.get(url, headers=HEADERS, timeout=20).json()
            if not res.get("success"):
                print(f"❌ 获取 Key 失败: {res}")
                break
            all_keys.extend([item["name"] for item in res.get("result", [])])
            cursor = res.get("result_info", {}).get("cursor")
            if not cursor: break
        return set(all_keys)
    except Exception as e:
        print(f"⚠️ 获取列表出错: {e}")
        return set()

def upload(key, file_path):
    global STOP_SYNC
    if STOP_SYNC: return

    url = f"{BASE_URL}/values/{key}"
    try:
        with open(file_path, "rb") as f:
            content = f.read()
            res = requests.put(
                url, 
                headers={
                    "Authorization": f"Bearer {KV_API_TOKEN}", 
                    "Content-Type": "application/octet-stream"
                }, 
                data=content,
                timeout=30
            )
        
        if res.status_code == 200:
            print(f"✅ 上传成功: {key}")
        elif res.status_code == 429:
            print(f"🛑 触发限制: 今天的 KV 写入额度已耗尽 (429)。")
            STOP_SYNC = True # 标记终止
        else:
            print(f"❌ 上传失败: {key} | 状态码: {res.status_code}")
    except Exception as e:
        print(f"⚠️ 错误: {key} | {e}")

def sync():
    if not os.path.exists(LOCAL_DIR):
        print(f"❌ 错误: 找不到目录 {LOCAL_DIR}")
        return

    # 1. 扫描本地文件
    local_files = {}
    for root, _, files in os.walk(LOCAL_DIR):
        for f in files:
            if f.startswith('.') or f.lower() == 'thumbs.db': continue
            rel_path = os.path.relpath(os.path.join(root, f), LOCAL_DIR).replace("\\", "/")
            local_files[rel_path] = os.path.join(root, f)

    # 2. 获取 KV 列表
    kv_keys = get_kv_keys()

    # 3. 比对差异 (只增量上传，不处理删除，确保 json 等 key 安全)
    to_upload = set(local_files.keys()) - kv_keys

    print(f"📊 本地文件: {len(local_files)} | KV 现有: {len(kv_keys)}")
    print(f"🚀 待同步上传: {len(to_upload)}")

    if not to_upload:
        print("✨ 没有需要上传的新文件。")
        return

    # 4. 执行上传
    with ThreadPoolExecutor(max_workers=5) as executor: # 适当降低并发，更稳定
        for k in sorted(to_upload): # 排序后上传，方便观察进度
            if STOP_SYNC: break
            executor.submit(upload, k, local_files[k])

if __name__ == "__main__":
    sync()
