"""
配置中心（对应 Spring 的 application.yml）。

所有可变的路径、阈值、开关都集中在这里，通过环境变量或 .env 文件覆盖。
第一阶段只用 SQLite + Milvus Lite 本地文件，不涉及远程服务地址。
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（本文件在 backend/core/ 下，向上两级即 backend/）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """全局配置。

    每个字段都有默认值，运行时可用同名环境变量（如 BACKEND_DB_PATH）
    或项目根目录的 .env 文件覆盖，无需改代码。
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        # 环境变量名不区分大小写，方便 Windows 下使用
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 基础信息 ----------
    app_name: str = "学生刷脸考勤系统"
    app_version: str = "0.1.0"

    # ---------- 数据库 ----------
    # SQLite 文件路径。用绝对路径避免"从哪个目录启动"导致库文件漂移。
    db_path: str = str(BASE_DIR / "dev.db")

    # ---------- Milvus Lite ----------
    # 注意：本地路径必须以 ".db" 结尾，否则 MilvusClient 报
    # "uri ... is illegal, needs ... a local file endswith [.db]"。
    # milvus-lite 会把这个 .db 路径当作前缀，在其下生成数据文件/子目录。
    milvus_path: str = str(BASE_DIR / "milvus.db")

    # ---------- 脸照存储 ----------
    # P6 才用，这里先定义好，避免后面到处硬编码。
    face_storage_dir: str = str(BASE_DIR / "storage" / "faces")

    # ---------- 人脸模型 ----------
    # buffalo_l 模型根目录。注意：insightface 的目录约定是
    # <root>/models/<包名>/，即 face_model_root/models/buffalo_l/。
    # 本机模型放在 D:\...\Student\buffalo\models\buffalo_l\，所以这里指向 buffalo/。
    face_model_root: str = str(BASE_DIR.parent / "buffalo")

    # ---------- 人脸检测（P11 实时检测，复用 buffalo_l 的 det_10g SCRFD） ----------
    # 检测模型文件绝对路径（不经过 insightface FaceAnalysis 完整流水线，
    # 单独加载 SCRFD 只做「检测框」，不做识别，速度快、省内存）。
    face_detector_model: str = str(BASE_DIR.parent / "buffalo" / "models" / "buffalo_l" / "det_10g.onnx")
    # 检测置信度阈值 / NMS 阈值 / 输入尺寸（SCRFD 参数）
    face_detector_thresh: float = 0.5
    face_detector_nms_thresh: float = 0.4
    face_detector_input_size: tuple[int, int] = (640, 640)

    # ---------- 人脸录入查重（防「一人多号」） ----------
    # 录入时跨学号查重阈值：新脸与底库中「其他学号」的人脸余弦相似度 >= 此值，
    # 判定为「同一张脸已登记在别的学号下」，拒绝录入。
    # 0.75 既能拦住"同一人多角度照片"（实测互相似度约 0.83），
    # 又不会误伤"确实不同的两个人"（正常不同人相似度一般 < 0.6）。
    face_duplicate_threshold: float = 0.75

    # ---------- CORS（前后端分离开发场景） ----------
    # Vite 开发服务器默认端口 5173。生产环境可改为空列表关闭跨域。
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # ---------- 服务端口 ----------
    host: str = "127.0.0.1"
    port: int = 8000


# 全局单例：进程内所有模块 import 同一个实例，保证配置一致
settings = Settings()
