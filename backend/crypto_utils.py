"""
API Key 加密/解密工具，基于 Fernet（AES-128-CBC + HMAC-SHA256）。

使用方式：
1. 生成主密钥：python encrypt_key.py --generate
2. 加密 API Key：python encrypt_key.py --encrypt <your-api-key>
3. 运行时设置环境变量：
   MASTER_KEY=<生成的主密钥>
   DEEPSEEK_API_KEY_ENC=<加密后的密文>
"""

from cryptography.fernet import Fernet


def generate_master_key() -> str:
    """生成一个新的 Fernet 主密钥（32 字节 URL-safe base64）。"""
    return Fernet.generate_key().decode()


def encrypt(plaintext: str, master_key: str) -> str:
    """使用主密钥加密明文，返回密文字符串。"""
    f = Fernet(master_key.encode())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, master_key: str) -> str:
    """使用主密钥解密密文，返回明文字符串。"""
    f = Fernet(master_key.encode())
    return f.decrypt(ciphertext.encode()).decode()
