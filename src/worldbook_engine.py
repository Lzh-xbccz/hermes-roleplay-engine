#!/usr/bin/env python3
"""
World Book 自动挂载引擎
用法: worldbook_engine.py load <世界书名>  →  解析WB条目 → 写入memory
      worldbook_engine.py list              →  查看已挂载的WB
      worldbook_engine.py unload <世界书名> →  卸载
"""

import json, os, sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
REFS_DIR = HERMES_HOME / "skills/sillytavern-roleplay/references"
STATE_FILE = HERMES_HOME / "characters/_active_worldbooks.json"
MEMORY_PREFIX = "[WB]"

# ─── 加载 World Book ───
def load_worldbook(name: str) -> dict:
    """解析WB JSON，返回条目列表"""
    # 模糊匹配文件名
    wb_path = None
    for f in REFS_DIR.glob("*.json"):
        if name.lower() in f.stem.lower():
            wb_path = f
            break
    if not wb_path:
        return {"success": False, "error": f"未找到世界书: {name}"}

    with open(wb_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", {})
    if not entries:
        return {"success": False, "error": "世界书内无条目"}

    # 兼容 entries 为 list 或 dict
    if isinstance(entries, list):
        entry_iter = enumerate(entries)
    else:
        entry_iter = entries.items()

    # 提取条目
    items = []
    for uid, entry in entry_iter:
        if not isinstance(entry, dict):
            continue
        keys = entry.get("key", entry.get("keys", []))
        if isinstance(keys, str):
            keys = [keys]
        comment = entry.get("comment", "")
        content = entry.get("content", "")

        if not content:
            continue

        # 构建 memory 条目：关键词有助于语义匹配
        kw_str = ", ".join(keys[:10]) if keys else ""
        header = f"[WB:{name} | {comment}]" if comment else f"[WB:{name}]"
        if kw_str:
            header += f" 触发词: {kw_str}"

        # 截断过长内容
        if len(content) > 800:
            content = content[:800] + "..."

        items.append({
            "uid": str(uid),
            "keys": keys[:10],
            "comment": comment,
            "content": f"{header}\n{content}",
            "wb_name": name,
        })

    return {"success": True, "name": name, "count": len(items), "items": items, "path": str(wb_path)}


# ─── 输出 memory 写入指令 ───
def print_memory_commands(items: list, wb_name: str):
    """打印给 Hermes 执行的 memory 写入指令"""
    print(f"\n⚠️  请执行以下 memory 写入（复制给 Hermes 或用 skill）：\n")
    for i, item in enumerate(items):
        # 限制长度
        content = item['content'][:500]
        keys_tag = f" [{', '.join(item['keys'][:5])}]" if item['keys'] else ""
        print(f"#{i+1} {item['comment']}{keys_tag}")
        print(f"   {content[:150]}...")
    print(f"\n共 {len(items)} 条，建议分 3 批写入 memory")


# ─── 保存/读取挂载状态 ───
def get_active_wbs() -> list:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return []


def save_active_wbs(wbs: list):
    with open(STATE_FILE, "w") as f:
        json.dump(wbs, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: worldbook_engine.py <load|list|unload> [name]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "load":
        if len(sys.argv) < 3:
            print("用法: worldbook_engine.py load <世界书名>")
            sys.exit(1)
        name = sys.argv[2]
        result = load_worldbook(name)
        if not result["success"]:
            print(f"❌ {result['error']}")
            sys.exit(1)

        items = result["items"]
        print(f"📖 世界书: {result['name']} ({result['count']}条) — {result['path']}")
        print_memory_commands(items, result["name"])

        # 记录挂载（去重）
        active = get_active_wbs()
        active = [wb for wb in active if result["name"].lower() not in wb["name"].lower()]
        active.append({"name": result["name"], "count": result["count"], "path": result["path"]})
        save_active_wbs(active)

    elif cmd == "list":
        active = get_active_wbs()
        # 也列出可用世界书
        print("📖 已挂载:")
        for wb in active:
            print(f"  ✅ {wb['name']} ({wb['count']}条)")

        print("\n📚 可用世界书:")
        for f in sorted(REFS_DIR.glob("*.json")):
            try:
                with open(f, "r") as fp:
                    d = json.load(fp)
                entries = len(d.get("entries", {}))
                name = d.get("name", f.stem)
                print(f"  📖 {name} ({entries}条)")
            except:
                print(f"  ❓ {f.stem}")

    elif cmd == "unload":
        if len(sys.argv) < 3:
            print("用法: worldbook_engine.py unload <世界书名>")
            sys.exit(1)
        name = sys.argv[2]
        active = get_active_wbs()
        new_active = [wb for wb in active if name.lower() not in wb["name"].lower()]
        save_active_wbs(new_active)
        print(f"✅ 已卸载 {name}（需手动清理 memory 中对应条目）")

    else:
        print(f"未知命令: {cmd}")
