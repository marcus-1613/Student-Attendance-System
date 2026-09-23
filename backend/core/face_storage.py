"""人脸图片文件系统基础存储。

职责：只管图片文件在磁盘上的"存 / 读 / 删 / 组织路径"，不含学生业务逻辑。

路径组织（对齐需求文档 5.3 节）：
    <face_storage_dir>/<student_id>/<文件名>
    即 storage/faces/202301001/a1b2c3d4.jpg

说明：
- 这里的"文件名"由上层业务生成（如 uuid4 + .jpg），本模块不关心业务命名规则。
- 只操作文件，不碰 SQLite / Milvus。
"""
from pathlib import Path

from core.config import settings


class FaceStorage:
    """人脸图片文件系统存储。"""

    def __init__(self, root_dir: str | None = None):
        # 根目录默认取 config 的 face_storage_dir，也可显式传入（便于测试用临时目录）
        self.root = Path(root_dir) if root_dir else Path(settings.face_storage_dir)

    def _student_dir(self, student_id: int) -> Path:
        """某学生的图片子目录，不存在则创建。"""
        d = self.root / str(student_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, student_id: int, filename: str, data: bytes) -> str:
        """保存图片文件，返回「磁盘相对路径」（如 /202301001/xxx.jpg）。

        Args:
            student_id: 学号（作为子目录名）。
            filename: 文件名（含扩展名）。
            data: 图片二进制内容。
        """
        d = self._student_dir(student_id)
        filepath = d / filename
        filepath.write_bytes(data)
        return self.to_relative_path(student_id, filename)

    def read(self, student_id: int, filename: str) -> bytes | None:
        """按 student_id + filename 读取图片内容；不存在返回 None。"""
        filepath = self.root / str(student_id) / filename
        if not filepath.exists():
            return None
        return filepath.read_bytes()

    def read_by_path(self, relative_path: str) -> bytes | None:
        """按磁盘相对路径（如 /202301001/xxx.jpg）读取图片；不存在返回 None。"""
        filepath = self.root / relative_path.lstrip("/")
        if not filepath.exists():
            return None
        return filepath.read_bytes()

    def delete(self, student_id: int, filename: str) -> bool:
        """删除单个图片文件；成功返回 True，文件不存在返回 False。"""
        filepath = self.root / str(student_id) / filename
        if not filepath.exists():
            return False
        filepath.unlink()
        return True

    def delete_by_relative_path(self, relative_path: str) -> bool:
        """按相对路径删除图片文件。"""
        filepath = self.root / relative_path.lstrip("/")
        if not filepath.exists():
            return False
        filepath.unlink()
        return True

    def delete_student_dir(self, student_id: int) -> None:
        """删除某学生的整个图片子目录（含内部文件）。目录不存在则静默跳过。"""
        d = self.root / str(student_id)
        if not d.exists():
            return
        for f in d.iterdir():
            if f.is_file():
                f.unlink()
        d.rmdir()

    # ---------- 路径辅助 ----------
    def to_relative_path(self, student_id: int, filename: str) -> str:
        """把 student_id + filename 拼成「磁盘相对路径」字符串。

        注意：这里返回的是相对 face_storage_dir 的真实磁盘路径
        （/<student_id>/<filename>），与 save() 实际写入位置、read_by_path()
        的解析逻辑保持一致。不带 /faces/ 前缀——那是将来给前端静态资源
        URL 挂载时由上层再拼的，不属于文件系统存储层职责。
        """
        return f"/{student_id}/{filename}"
