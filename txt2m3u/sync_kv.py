import os
import requests

# ---------------- 配置 ----------------
KV_ACCOUNT_ID = os.getenv("KV_ACCOUNT_ID")
KV_NAMESPACE_ID = os.getenv("KV_NAMESPACE_ID")
KV_API_TOKEN = os.getenv("KV_API_TOKEN")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DIR = os.path.join(BASE_DIR, "Images")
BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{KV_ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}"
HEADERS = {"Authorization": f"Bearer {KV_API_TOKEN}"}

def get_kv_keys():
    """获取 KV 远程所有 Key (只读 Key 列表，不读内容，非常省额度)"""
    all_keys = []
    cursor = ""
    try:
        while True:
            url = f"{BASE_URL}/keys?cursor={cursor}"
            res = requests.get(url, headers=HEADERS, timeout=15).json()
            if not res.get("success"): break
            
            for item in res.get("result", []):
                key = item["name"]
                # 过滤掉系统配置文件，只看图标
                if not any(key.startswith(p) for p in ["REGISTRY", "SOURCES", "DATA_"]):
                    all_keys.append(key)
            
            cursor = res.get("result_info", {}).get("cursor")
            if not cursor: break
        return set(all_keys)
    except Exception as e:
        print(f"获取列表失败: {e}")
        return set()

def sync():
    if not os.path.exists(LOCAL_DIR): os.makedirs(LOCAL_DIR)

    # 1. 获取 KV 远程清单
    kv_keys = get_kv_keys()
    
    # 2. 获取本地已有清单
    local_files = []
    for root, _, files in os.walk(LOCAL_DIR):
        for f in files:
            if f.startswith('.'): continue
            rel_path = os.path.relpath(os.path.join(root, f), LOCAL_DIR).replace("\\", "/")
            local_files.append(rel_path)
    local_set = set(local_files)

    # 3. 找出“真正需要下载”和“需要删除”的
    to_download = kv_keys - local_set
    to_delete = local_set - kv_keys

    # 4. 只下载新内容 (几秒钟的关键就在这里：不重复下载旧内容)
    if to_download:
        print(f"🚀 发现 {len(to_download)} 个新内容，开始按需下载...")
        for k in sorted(to_download):
            p = os.path.join(LOCAL_DIR, k.replace("/", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            res = requests.get(f"{BASE_URL}/values/{k}", headers=HEADERS, timeout=20)
            if res.status_code == 200:
                with open(p, "wb") as f:
                    f.write(res.content)
                print(f"✅ 已补全: {k}")
    
    # 5. 只删除已不存在的内容
    if to_delete:
        print(f"🗑️ 发现 {len(to_delete)} 个失效内容，正在清理...")
        for k in to_delete:
            p = os.path.join(LOCAL_DIR, k.replace("/", os.sep))
            if os.path.exists(p):
                os.remove(p)
                print(f"🗑️ 已移除: {k}")

    if not to_download and not to_delete:
        print("✨ 库已经是最新状态，无需操作。")

if __name__ == "__main__":
    sync()
