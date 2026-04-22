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

def get_kv_inventory():
    """获取远程清单，包含 Key 和它的元数据（用于判断覆盖）"""
    inventory = {}
    cursor = ""
    try:
        while True:
            # 这里的 list 接口只会消耗极少的读取额度
            url = f"{BASE_URL}/keys?cursor={cursor}"
            res = requests.get(url, headers=HEADERS, timeout=15).json()
            if not res.get("success"): break
            
            for item in res.get("result", []):
                name = item["name"]
                if any(name.startswith(p) for p in ["REGISTRY", "SOURCES", "DATA_"]): continue
                
                # 我们记录下这个文件的元数据，如果没有元数据，后续逻辑会处理
                inventory[name] = item.get("metadata", {})
            
            cursor = res.get("result_info", {}).get("cursor")
            if not cursor: break
        return inventory
    except Exception as e:
        print(f"📡 获取列表失败: {e}")
        return {}

def sync():
    if not os.path.exists(LOCAL_DIR): os.makedirs(LOCAL_DIR)

    # 1. 获取远程 KV 清单
    remote_inventory = get_kv_inventory()
    
    # 2. 获取本地文件列表
    local_files = []
    for root, _, files in os.walk(LOCAL_DIR):
        for f in files:
            if f.startswith('.'): continue
            rel_path = os.path.relpath(os.path.join(root, f), LOCAL_DIR).replace("\\", "/")
            local_files.append(rel_path)
    local_set = set(local_files)

    # 3. 核心逻辑：判断哪些需要下载
    to_download = []
    
    for name in remote_inventory.keys():
        local_path = os.path.join(LOCAL_DIR, name.replace("/", os.sep))
        
        # 特例处理：如果本地没有，或者你认为需要强制检查更新
        if name not in local_set:
            to_download.append(name)
        else:
            # 【这里解决同名覆盖问题】
            # 如果你在上传 KV 时习惯带上版本号或时间戳在 metadata 里，可以在这里对比
            # 如果没有 metadata，我们可以通过 API 获取单个文件的 Headers (HEAD请求) 
            # 但最简单直接的方法：如果你怀疑有覆盖，手动运行 Actions 时加个参数清空 Images 即可
            pass

    # 4. 执行同步
    if to_download:
        print(f"🚀 准备同步 {len(to_download)} 个文件...")
        for k in sorted(to_download):
            p = os.path.join(LOCAL_DIR, k.replace("/", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            res = requests.get(f"{BASE_URL}/values/{k}", headers=HEADERS, timeout=20)
            if res.status_code == 200:
                with open(p, "wb") as f:
                    f.write(res.content)
                print(f"✅ 同步成功: {k}")

    # 5. 删除本地多余文件
    to_delete = local_set - set(remote_inventory.keys())
    for k in to_delete:
        p = os.path.join(LOCAL_DIR, k.replace("/", os.sep))
        if os.path.exists(p):
            os.remove(p)
            print(f"🗑️ 清理废弃: {k}")

if __name__ == "__main__":
    sync()
