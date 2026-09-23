"""模型包：集中导入所有 ORM 实体。

main.py 的 create_all 依赖这里把所有模型 import 进来，
否则 SQLAlchemy 发现不了未 import 的模型，建不出表。
"""
from models.student import Student
from models.face import Face
from models.notice import Notice
from models.attendance import Attendance

__all__ = ["Student", "Face", "Notice", "Attendance"]
