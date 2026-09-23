"""
应用入口。

P1 只做"骨架"：
- lifespan 启动事件：初始化 Milvus、建 SQLite 表（目前还没有 models，建表是空操作）
- 注册全局异常处理器
- 配置 CORS（localhost 前后端分离开发场景）
- 挂一个 /api/health 探活接口

业务路由（students/faces/stats/notices/audit）在后续阶段逐个挂进来。
"""
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import enums as enums_api
from api import faces as faces_api
from api import notices as notices_api
from api import stats as stats_api
from api import students as students_api
from api import audit as audit_api
from api import detect as detect_api
from api import recognition as recognition_api
from core import db, enums, milvus
from core.config import settings
from core.exceptions import register_exception_handlers
from core.face_engine import init_face_engine
from core.yolo_detector import init_face_detector
from schemas.common import ok
import models  # noqa: F401  确保所有 ORM 模型被 import，create_all 才能建表


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化资源，关闭时释放。"""
    # ---- 启动 ----
    # 1. 初始化 Milvus（连上 + 确保 face_vectors collection 存在）
    try:
        milvus.init_milvus()
        milvus.ensure_face_collection()
    except Exception as e:
        # Milvus 连不上不该让整个服务起不来，记下错误继续（health 会暴露它）
        print(f"[startup] Milvus 初始化失败: {e}")

    # 2. 加载班级/专业枚举（从 CSV 读入内存）
    enums.load_enums()

    # 3. 建 SQLite 表（当前没有 models，等 P3 加了模型后这里才会真正建表）
    db.Base.metadata.create_all(bind=db.engine)

    # 4. 加载人脸引擎（单例，模型常驻内存，避免每次请求重复加载 300MB 模型）
    try:
        init_face_engine()
    except Exception as e:
        # 模型加载失败不该让服务起不来，记下错误继续（health 可辅助排查）
        print(f"[startup] 人脸引擎初始化失败: {e}")

    # 5. 加载人脸检测器（P11 实时检测用，SCRFD/det_10g，只检测不识别）
    try:
        init_face_detector()
    except Exception as e:
        print(f"[startup] 人脸检测器初始化失败: {e}")

    yield

    # ---- 关闭 ----
    milvus.close_milvus()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS：允许 Vite 开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理器
register_exception_handlers(app)

# 挂载业务路由（后续阶段逐个加进来）
app.include_router(enums_api.router)
app.include_router(students_api.router)
app.include_router(faces_api.router)
app.include_router(stats_api.router)
app.include_router(notices_api.router)
app.include_router(notices_api.ws_router)  # WebSocket 端点 /ws/notices（无 /api 前缀）
app.include_router(audit_api.router)
app.include_router(detect_api.router)
app.include_router(recognition_api.router)

# 挂载脸照静态目录：/face-images/<student_id>/<filename> → storage/faces/<student_id>/<filename>
# 前端拿到的 image_path（如 /1/xxx.jpg）拼上 /face-images 前缀即可访问图片。
# 注意：前缀刻意避开前端路由 /faces（人脸录入页），否则 vite 代理会把页面请求
# 误判为静态图请求转发到后端，导致前端应用加载不出、内容区空白。
os.makedirs(settings.face_storage_dir, exist_ok=True)
app.mount("/face-images", StaticFiles(directory=settings.face_storage_dir), name="face-images")


@app.get("/api/health")
def health():
    """探活接口：返回 SQLite / Milvus / 应用 三者状态。

    调试期很有用：前端连不上、人脸失败时，先看这里分清是哪一层挂了。
    """
    # SQLite 状态
    sqlite_ok = True
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("SELECT 1"))
    except Exception:
        sqlite_ok = False

    # Milvus 状态
    milvus_client = milvus.get_milvus_client()
    milvus_ok = milvus_client is not None
    if milvus_ok:
        try:
            # 列一下集合名，验证真的能通信
            milvus_client.list_collections()
        except Exception:
            milvus_ok = False

    return ok({
        "app": settings.app_name,
        "version": settings.app_version,
        "sqlite": "ok" if sqlite_ok else "error",
        "milvus": "ok" if milvus_ok else "error",
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # 开发期如需热重载改成 True；Milvus 文件锁对 reload 敏感，先关
    )
