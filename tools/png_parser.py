#!/usr/bin/env python3
"""
解析 SillyTavern 角色卡 PNG - 提取嵌入的角色 JSON 数据
支持 V2 (chara) 和 V3 (ccv3) 格式

用法:
  python3 png_parser.py <image.png>           → 打印 JSON
  python3 png_parser.py <image.png> --save    → 保存到 ~/.hermes/characters/

来源: Chub (characterhub.org), JanitorAI, Discord 社区
"""

import base64
import json
import os
import struct
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
CHARACTERS_DIR = HERMES_HOME / "characters"


def parse_png_chunks(filepath: str) -> list[tuple[str, bytes]]:
    """解析 PNG chunk 数据"""
    chunks = []
    with open(filepath, "rb") as f:
        signature = f.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("不是有效的 PNG 文件")

        while True:
            length_bytes = f.read(4)
            if len(length_bytes) < 4:
                break
            length = struct.unpack(">I", length_bytes)[0]
            chunk_type = f.read(4).decode("ascii", errors="replace")
            chunk_data = f.read(length)
            crc = f.read(4)
            chunks.append((chunk_type, chunk_data))

    return chunks


def decode_tEXt(data: bytes) -> tuple[str, str]:
    """解码 tEXt chunk → (keyword, text)"""
    null_idx = data.find(b"\x00")
    if null_idx == -1:
        return ("", "")
    keyword = data[:null_idx].decode("latin-1")
    text = data[null_idx + 1:].decode("latin-1")
    return (keyword, text)


def decode_iTXt(data: bytes) -> tuple[str, str]:
    """解码 iTXt chunk → (keyword, text)"""
    null_idx = data.find(b"\x00")
    if null_idx == -1:
        return ("", "")
    keyword = data[:null_idx].decode("utf-8")
    rest = data[null_idx + 1:]
    if len(rest) < 2:
        return (keyword, "")
    compression_flag = rest[0]
    rest = rest[2:]
    null_idx = rest.find(b"\x00")
    if null_idx == -1:
        return (keyword, "")
    rest = rest[null_idx + 1:]
    null_idx = rest.find(b"\x00")
    if null_idx == -1:
        return (keyword, "")
    text_bytes = rest[null_idx + 1:]
    if compression_flag == 1:
        import zlib
        text_bytes = zlib.decompress(text_bytes)
    return (keyword, text_bytes.decode("utf-8"))


def extract_character_data(filepath: str) -> dict:
    """从 PNG 中提取角色数据，优先 V3 (ccv3)"""
    chunks = parse_png_chunks(filepath)

    text_chunks = []
    for chunk_type, data in chunks:
        if chunk_type == "tEXt":
            keyword, text = decode_tEXt(data)
            text_chunks.append((keyword, text))
        elif chunk_type == "iTXt":
            keyword, text = decode_iTXt(data)
            text_chunks.append((keyword, text))

    if not text_chunks:
        raise ValueError("PNG 中没有文本元数据 (无 tEXt/iTXt chunk)")

    # 优先 ccv3
    for keyword, text in text_chunks:
        if keyword.lower() == "ccv3":
            json_str = base64.b64decode(text).decode("utf-8")
            return json.loads(json_str)

    # 回退 chara (V2)
    for keyword, text in text_chunks:
        if keyword.lower() == "chara":
            json_str = base64.b64decode(text).decode("utf-8")
            return json.loads(json_str)

    raise ValueError("PNG 中没有角色卡数据 (chara 或 ccv3)")


def main():
    if len(sys.argv) < 2:
        print("用法: png_parser.py <image.png> [--save]")
        print("  --save  保存到 ~/.hermes/characters/ 目录")
        sys.exit(1)

    filepath = sys.argv[1]
    do_save = "--save" in sys.argv

    try:
        char_data = extract_character_data(filepath)
    except Exception as e:
        print(f"❌ 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    data = char_data.get("data", char_data)
    name = data.get("name", "未命名")

    if do_save:
        CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in name if c.isalnum() or c in "._- ()（）")
        save_path = CHARACTERS_DIR / f"{safe_name}.json"

        if "spec" not in char_data:
            char_data = {
                "spec": "chara_card_v3",
                "spec_version": "3.0",
                "data": char_data,
            }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(char_data, f, ensure_ascii=False, indent=2)

        print(f"✅ 角色卡已保存: {save_path}")
        print(f"   角色名: {name}")
        print(f"   加载: python3 character_engine.py load '{name}'")

    else:
        print(json.dumps(char_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
