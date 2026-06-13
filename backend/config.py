from pydantic_settings import BaseSettings


class Config(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./temperature.db"
    DATA_RETENTION_DAYS: int = 90  # 自动清理超过 N 天的旧数据，0 表示不清理

    # Socket 服务配置
    SOCKET_HOST: str = "0.0.0.0"
    SOCKET_PORT: int = 9999
    SOCKET_PROTOCOL: str = "TCP"  # 或 UDP
    TCP_TIMEOUT: int = 30  # TCP 读超时(秒)

    # 数据包格式配置
    PACKET_HEADER: bytes = b"\xAA\xBB"  # 数据包头
    PACKET_LENGTH: int = 20  # 数据包总长度

    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # 日志配置
    LOG_LEVEL: str = "INFO"  # DEBUG / INFO / WARNING / ERROR

    class Config:
        env_file = ".env"


config = Config()