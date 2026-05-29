#!/usr/bin/env python3
"""API Key 加密 CLI 工具。

用法:
  # 生成主密钥
  python encrypt_key.py --generate

  # 加密 API Key（从环境变量 MASTER_KEY 读取主密钥）
  MASTER_KEY=<主密钥> python encrypt_key.py --encrypt "sk-your-api-key"

  # 从文件读取主密钥
  python encrypt_key.py --encrypt "sk-your-api-key" --key-file /path/to/master.key
"""

import os
import sys
import argparse
from crypto_utils import generate_master_key, encrypt


def main():
    parser = argparse.ArgumentParser(description="GamePlan API Key 加密工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate", action="store_true", help="生成新的主密钥")
    group.add_argument("--encrypt", metavar="PLAINTEXT", help="加密指定的明文 API Key")
    parser.add_argument("--key-file", help="从文件读取主密钥（默认从 MASTER_KEY 环境变量读取）")
    args = parser.parse_args()

    if args.generate:
        key = generate_master_key()
        print(f"主密钥（请妥善保存，用于加解密）:\n{key}")
        return

    if args.encrypt:
        master_key = None
        if args.key_file:
            with open(args.key_file) as f:
                master_key = f.read().strip()
        else:
            master_key = os.environ.get("MASTER_KEY", "")
        if not master_key:
            print("错误: 未提供主密钥。请设置 MASTER_KEY 环境变量或使用 --key-file", file=sys.stderr)
            sys.exit(1)
        try:
            ciphertext = encrypt(args.encrypt, master_key)
            print(f"加密后的密文（设置为 DEEPSEEK_API_KEY_ENC 环境变量）:\n{ciphertext}")
        except Exception as e:
            print(f"加密失败: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
