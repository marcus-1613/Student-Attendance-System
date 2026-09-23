"""学生业务层。

职责：业务规则 + 事务边界 + 编排 Repository。
不写 SQL，不读 HTTP 请求对象。
"""
import io

import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core import enums
from core.exceptions import BusinessError
from models.student import Student
from repository.student_repo import StudentRepository
from schemas.student import (
    StudentCreate,
    StudentUpdate,
    ImportResult,
    ImportRowError,
)


class StudentService:
    """学生业务逻辑。"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = StudentRepository(db)

    # ---------- 校验辅助 ----------

    def _validate_enums(self, class_name: str | None, major: str | None) -> None:
        """校验班级/专业是否在枚举范围内（Q-C 选项1：在 Service 层校验）。"""
        if class_name and class_name not in enums.get_classes():
            raise BusinessError(4001, f"班级「{class_name}」不在允许的枚举范围内")
        if major and major not in enums.get_majors():
            raise BusinessError(4001, f"专业「{major}」不在允许的枚举范围内")

    # ---------- CRUD ----------

    def create_student(self, payload: StudentCreate) -> Student:
        # 1. 学号查重（业务规则，第一道防线，给用户友好提示）
        if self.repo.get_by_student_no(payload.student_no):
            raise BusinessError(4002, f"学号「{payload.student_no}」已存在")

        # 2. 枚举校验
        self._validate_enums(payload.class_name, payload.major)

        # 3. 创建
        student = Student(
            student_no=payload.student_no,
            name=payload.name,
            gender=payload.gender,
            class_name=payload.class_name,
            major=payload.major,
            enroll_year=payload.enroll_year,
            phone=payload.phone,
        )
        try:
            self.repo.create(student)
            self.db.commit()  # 事务边界在此收口
            self.db.refresh(student)  # 重新加载，拿到数据库生成的时间戳
            return student
        except IntegrityError:
            # 第二道防线：并发下 UNIQUE 约束兜底
            self.db.rollback()
            raise BusinessError(4002, f"学号「{payload.student_no}」已存在")

    def get_student(self, student_id: int) -> Student:
        student = self.repo.get_by_id(student_id)
        if student is None:
            raise BusinessError(4004, "学生不存在")
        return student

    def list_students(self, keyword: str | None, page: int, page_size: int):
        total, items = self.repo.list_page(keyword, page, page_size)
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def update_student(self, student_id: int, payload: StudentUpdate) -> Student:
        student = self.get_student(student_id)

        # 枚举校验（只校验传入的非空值）
        self._validate_enums(payload.class_name, payload.major)

        # 只更新传入的字段（exclude_unset 跳过未传的字段）
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(student, field, value)

        self.db.commit()
        self.db.refresh(student)
        return student

    def delete_student(self, student_id: int) -> None:
        student = self.get_student(student_id)

        # 三处级联删除（遵循「先删外部附件，再删权威记录」）：
        # 1. 删该学生的 Milvus 向量 + 磁盘脸照文件 + SQLite faces 行
        # 2. 删 SQLite students 行（faces 行由 ON DELETE CASCADE 兜底）
        # 方法内延迟 import 避免 face_service / student_service 互相 import 成环。
        from service.face_service import FaceService

        face_service = FaceService(self.db)
        face_service.delete_faces_by_student(student_id)

        self.repo.delete(student)
        self.db.commit()

    # ==================== 批量导入 ====================

    # 导入文件的列名约定（中文表头），与 Student 字段的映射
    IMPORT_COLUMNS = {
        "学号": "student_no",
        "姓名": "name",
        "性别": "gender",
        "班级": "class_name",
        "专业": "major",
        "入学年份": "enroll_year",
        "联系方式": "phone",
    }

    def import_students(self, file_bytes: bytes, filename: str) -> ImportResult:
        """批量导入学生（CSV / Excel .xlsx）。

        设计要点（与 P5 设计文档一致）：
        - 逐行校验 + 部分成功：能进的行写入，错的行记录原因跳过。
        - 每行独立 commit，一条失败不影响其他。
        - 复用 _validate_enums / get_by_student_no，不重复造校验逻辑。
        """
        df = self._parse_import_file(file_bytes, filename)
        rows = df.to_dict("records")

        if not rows:
            raise BusinessError(4005, "文件中没有有效数据")

        errors: list[ImportRowError] = []
        success_count = 0
        seen_nos: set[str] = set()  # 文件内部学号去重

        # 行号从 2 开始（第 1 行是表头）
        for i, raw in enumerate(rows, start=2):
            student_no = self._clean_str(raw.get("student_no"))

            # 1. 必填校验
            if not student_no:
                errors.append(ImportRowError(row=i, student_no="", reason="学号不能为空"))
                continue
            name = self._clean_str(raw.get("name"))
            if not name:
                errors.append(ImportRowError(row=i, student_no=student_no, reason="姓名不能为空"))
                continue

            # 2. 文件内部重复
            if student_no in seen_nos:
                errors.append(
                    ImportRowError(row=i, student_no=student_no, reason=f"学号「{student_no}」在文件内重复")
                )
                continue
            seen_nos.add(student_no)

            # 3. 与数据库已有记录重复
            if self.repo.get_by_student_no(student_no):
                errors.append(
                    ImportRowError(row=i, student_no=student_no, reason=f"学号「{student_no}」已存在")
                )
                continue

            # 4. 逐字段解析 + 校验（失败则记录并跳过该行）
            try:
                gender = self._clean_str(raw.get("gender")) or None
                if gender is not None and gender not in ("男", "女"):
                    raise ValueError("性别只能是「男」或「女」")

                class_name = self._clean_str(raw.get("class_name")) or None
                major = self._clean_str(raw.get("major")) or None
                # 批量场景用 ValueError 表达校验失败（而非 _validate_enums 的
                # BusinessError，后者会中断整个导入）。枚举范围判断逻辑保持一致。
                if class_name and class_name not in enums.get_classes():
                    raise ValueError(f"班级「{class_name}」不在允许的枚举范围内")
                if major and major not in enums.get_majors():
                    raise ValueError(f"专业「{major}」不在允许的枚举范围内")

                enroll_year = self._parse_year(raw.get("enroll_year"))
                phone = self._clean_str(raw.get("phone")) or None

                # 5. 落库（每行独立提交）
                student = Student(
                    student_no=student_no,
                    name=name,
                    gender=gender,
                    class_name=class_name,
                    major=major,
                    enroll_year=enroll_year,
                    phone=phone,
                )
                self.repo.create(student)
                self.db.commit()
                success_count += 1
            except ValueError as e:
                self.db.rollback()
                errors.append(ImportRowError(row=i, student_no=student_no, reason=str(e)))
            except IntegrityError:
                # 并发兜底：提交时才发现的唯一约束冲突
                self.db.rollback()
                errors.append(
                    ImportRowError(row=i, student_no=student_no, reason=f"学号「{student_no}」已存在")
                )

        return ImportResult(
            total=len(rows),
            success=success_count,
            failed=len(errors),
            errors=errors,
        )

    # ---------- 导入辅助方法 ----------

    def _parse_import_file(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        """根据扩展名解析 CSV / Excel，返回标准列名的 DataFrame。"""
        lower = filename.lower()
        if lower.endswith(".csv"):
            df = self._read_csv_bytes(file_bytes)
        elif lower.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        else:
            raise BusinessError(4005, "仅支持 .csv 或 .xlsx 文件")

        # 列名标准化：去首尾空格
        df.columns = [str(c).strip() for c in df.columns]

        # 校验必需列
        missing = [cn for cn in self.IMPORT_COLUMNS if cn not in df.columns]
        if missing:
            raise BusinessError(4005, f"缺少必需列：{'、'.join(missing)}")

        # 只取约定的列，并重命名为 Student 字段名
        df = df.rename(columns=self.IMPORT_COLUMNS)
        return df[list(self.IMPORT_COLUMNS.values())]

    @staticmethod
    def _read_csv_bytes(file_bytes: bytes) -> pd.DataFrame:
        """读 CSV 字节流，做 utf-8-sig → gbk 编码回退（复用 enums 的思路）。"""
        for enc in ("utf-8-sig", "gbk"):
            try:
                return pd.read_csv(io.BytesIO(file_bytes), encoding=enc, dtype=str)
            except UnicodeDecodeError:
                continue
        raise BusinessError(4005, "无法识别文件编码（已尝试 utf-8 / gbk）")

    @staticmethod
    def _clean_str(value) -> str:
        """把单元格转成去首尾空白的字符串；空值/NaN 返回空串。"""
        if value is None:
            return ""
        if isinstance(value, float) and pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _parse_year(value) -> int | None:
        """解析入学年份。空返回 None；非法抛 ValueError。"""
        s = StudentService._clean_str(value)
        if not s:
            return None
        # 兼容 Excel 把 2024 读成 "2024" 或 "2024.0"
        if s.endswith(".0"):
            s = s[:-2]
        if not s.isdigit():
            raise ValueError(f"入学年份「{value}」不是有效整数")
        year = int(s)
        if year < 1900 or year > 2100:
            raise ValueError(f"入学年份「{year}」超出 1900-2100 范围")
        return year
