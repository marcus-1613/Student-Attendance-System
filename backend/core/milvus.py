"""
Milvus Lite 客户端连接 + face_vectors collection 初始化。

设计要点：
1. 客户端在应用 lifespan 启动时创建一次，关闭时释放，避免重复初始化
   和文件锁冲突（Milvus Lite 同一数据目录同时只能被一个进程打开）。
2. 用一个模块级变量存"当前客户端"，供 vector_repo 使用；
   通过 get_milvus_client() 获取，返回 None 表示尚未初始化。
3. face_vectors collection 的创建逻辑也集中在这里，供 vector_repo 复用；
   上层 repository 不复制客户端初始化逻辑。
"""
from pymilvus import MilvusClient

from core.config import settings

# 模块级单例：lifespan 启动时赋值
_client: MilvusClient | None = None

# face_vectors collection 名称（人脸向量）
FACE_COLLECTION = "face_vectors"

# embedding 维度（ArcFace 512 维）
EMBEDDING_DIM = 512


def init_milvus() -> MilvusClient:
    """创建并缓存 Milvus 客户端。在 lifespan 启动事件里调用一次。"""
    global _client
    if _client is None:
        # 传入的是"数据目录"路径，Milvus 会在下面生成子目录
        _client = MilvusClient(settings.milvus_path)
    return _client


def get_milvus_client() -> MilvusClient | None:
    """获取当前客户端；未初始化时返回 None。"""
    return _client


def ensure_face_collection() -> None:
    """确保 face_vectors collection 存在（不存在则创建）。

    字段按需求文档 9.3 节：
    - face_id: INT64 主键（对应 SQLite faces.face_id）
    - student_id: INT64 标量字段（便于按学生过滤）
    - embedding: FLOAT_VECTOR(512)
    - created_at: INT64（Unix 时间戳）
    索引：HNSW，度量 COSINE。

    幂等：已存在则跳过，可安全地在启动时重复调用。
    """
    client = get_milvus_client()
    if client is None:
        raise RuntimeError("Milvus 客户端尚未初始化，请先调用 init_milvus()")

    if client.has_collection(FACE_COLLECTION):
        return

    # pymilvus 3.x 用 create_schema 组合字段，再 create_collection
    from pymilvus import DataType

    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field(field_name="face_id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="student_id", datatype=DataType.INT64)
    schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
    schema.add_field(field_name="created_at", datatype=DataType.INT64)

    client.create_collection(
        collection_name=FACE_COLLECTION,
        schema=schema,
    )

    # 建 HNSW + COSINE 索引
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="HNSW",
        metric_type="COSINE",
    )
    client.create_index(FACE_COLLECTION, index_params)


def close_milvus() -> None:
    """关闭客户端，释放文件锁。在 lifespan 关闭事件里调用。"""
    global _client
    if _client is not None:
        try:
            _client.close()
        finally:
            _client = None
