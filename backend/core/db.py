"""
数据库基础设施：SQLAlchemy engine / Session / Base。

设计要点：
1. engine 是进程级单例，创建一次、全局复用（连接是昂贵的）。
2. SessionLocal 是"会话工厂"，每处理一个请求就 new 一个 Session，
   用完关闭——这是 FastAPI + SQLAlchemy 的标准姿势，避免会话跨请求串用。
3. check_same_thread=False 是因为 FastAPI 可能在不同线程里拿到同一个
   SQLite 连接；默认限制会导致 "SQLite objects created in a thread..."
   报错。
4. 建表（create_all）不在 import 时执行，而是放到 main.py 的 lifespan
   里，确保"应用启动时"才建，且只建一次。
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings

# SQLite 需要指定连接参数，否则多线程下会报错
engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    echo=False,  # 调试时改成 True 可打印每句 SQL
)

# 会话工厂：每个请求用 with SessionLocal() 拿一个独立会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。

    models/ 下的每个实体都继承它，create_all() 才能发现并建表。
    """
    pass


def get_db():
    """FastAPI 依赖：为每个请求提供一个 Session，请求结束自动关闭。

    用法（在 api 层）：
        def some_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
