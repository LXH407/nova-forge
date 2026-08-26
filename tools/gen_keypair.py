# -*- coding: utf-8 -*-
"""生成 RSA 密钥对：
  - 私钥 -> keys/private.pem   （只保存在管理员手里，切勿提交到 GitHub）
  - 公钥 -> assets/public_key.pem（同时粘贴到 app/license.py 的 PUBLIC_KEY 常量，随程序分发）
用法: python tools/gen_keypair.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    keys_dir = os.path.join(root, "keys")
    assets_dir = os.path.join(root, "assets")
    os.makedirs(keys_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    priv_path = os.path.join(keys_dir, "private.pem")
    pub_path = os.path.join(assets_dir, "public_key.pem")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    with open(priv_path, "wb") as f:
        f.write(priv_pem)
    with open(pub_path, "wb") as f:
        f.write(pub_pem)

    print("密钥对已生成:")
    print("  私钥:", priv_path)
    print("  公钥:", pub_path)
    print()
    print("请把公钥内容粘贴到 app/license.py 的 PUBLIC_KEY 常量中，然后重新打包程序。")
    print("私钥请严格保密并加入 .gitignore，切勿上传 GitHub。")


if __name__ == "__main__":
    main()
