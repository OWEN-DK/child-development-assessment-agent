import base64
import os

from cryptography.fernet import Fernet

from src.utils.logger import logger


class CryptoService:
    """AES 对称加密服务（用于敏感配置加密存储）"""

    def __init__(self, key: str = None):
        # 使用环境变量中的密钥，或生成新密钥
        if not key:
            key = os.getenv("ENCRYPTION_KEY")
        if key:
            self._key = self._derive_key(key)
        else:
            self._key = Fernet.generate_key()
            logger.warning(
                "未配置ENCRYPTION_KEY环境变量，使用临时生成的密钥，重启后加密数据将无法解密"
            )
        self._fernet = Fernet(self._key)

    def _derive_key(self, password: str) -> bytes:
        """从密码派生 32 字节密钥"""
        import hashlib

        return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

    def encrypt(self, plaintext: str) -> str:
        """加密"""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """解密"""
        return self._fernet.decrypt(ciphertext.encode()).decode()

    @staticmethod
    def mask_api_key(key: str, visible_chars: int = 4) -> str:
        """API Key 脱敏显示（如 sk-****1234）"""
        if not key or len(key) <= visible_chars * 2:
            return "****"
        return f"{key[:visible_chars]}****{key[-visible_chars:]}"


# 全局单例
crypto_service = CryptoService()
