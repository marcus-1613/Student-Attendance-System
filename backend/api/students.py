"""学生管理接口（控制层）。

职责：收请求、校验、调 Service、包统一响应。不写业务、不碰数据库。
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session

from core.db import get_db
from schemas.common import ok
from schemas.student import StudentCreate, StudentOut, StudentUpdate, ImportResult
from service.student_service import StudentService

router = APIRouter(prefix="/api/students", tags=["学生管理"])


def _get_service(db: Session = Depends(get_db)) -> StudentService:
    return StudentService(db)


@router.post("", summary="新增学生")
def create_student(payload: StudentCreate, svc: StudentService = Depends(_get_service)):
    student = svc.create_student(payload)
    return ok(StudentOut.model_validate(student))


@router.post("/import", summary="批量导入学生（CSV/Excel）")
def import_students(
    file: UploadFile = File(..., description="上传 .csv 或 .xlsx 文件"),
    svc: StudentService = Depends(_get_service),
):
    # 注意：/import 是固定路径，声明在任何 /{student_id} 之前更稳妥，
    # 避免将来新增 POST /{student_id} 时把 "import" 误当路径参数匹配。
    content = file.file.read()
    result: ImportResult = svc.import_students(content, file.filename or "")
    return ok(result.model_dump())


@router.get("", summary="分页查询学生")
def list_students(
    keyword: str | None = Query(default=None, description="模糊匹配姓名/学号/班级"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，1-100"),
    svc: StudentService = Depends(_get_service),
):
    data = svc.list_students(keyword, page, page_size)
    return ok(data)


@router.get("/{student_id}", summary="查询单个学生")
def get_student(student_id: int, svc: StudentService = Depends(_get_service)):
    student = svc.get_student(student_id)
    return ok(StudentOut.model_validate(student))


@router.put("/{student_id}", summary="更新学生")
def update_student(
    student_id: int,
    payload: StudentUpdate,
    svc: StudentService = Depends(_get_service),
):
    student = svc.update_student(student_id, payload)
    return ok(StudentOut.model_validate(student))


@router.delete("/{student_id}", summary="删除学生")
def delete_student(student_id: int, svc: StudentService = Depends(_get_service)):
    svc.delete_student(student_id)
    return ok(message="删除成功")
