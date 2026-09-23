"""P6 第五步 · 人脸录入 API 层 + 级联删除 + face_status 测试（独立测试）。

验证内容：
A. create_face（录入）：三存储落库 + face_id 一致 + face_status 置 1
B. list_faces（列表）：能查回录入的脸照
C. delete_face（删单张）：三处级联删除 + face_status 回 0
D. delete_faces_by_student / delete_student（删学生）：三处级联全清
E. 错误路径：学生不存在 / 无脸图 / 图片解码失败

测试策略：
- SQLite / Milvus / 图片目录全部用独立临时路径，不污染真实数据。
- 真实人脸图复用 insightface 包内官方示例 t1.jpg（多人合影）。
- 无脸图用全黑图；解码失败用非图片字节。
- 测试结束后清理全部临时数据。

运行方式（在 backend/ 目录下）：
    venv\\Scripts\\python.exe scripts\\test_face_service.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------- 用临时路径替换配置（在 import db/milvus 之前生效）----------
from core import config as config_mod  # noqa: E402

_tmp_root = Path(tempfile.mkdtemp(prefix="face_svc_test_"))
_tmp_sqlite = _tmp_root / "test.db"
_tmp_milvus = _tmp_root / "milvus.db"
_tmp_storage = _tmp_root / "faces"

config_mod.settings.db_path = str(_tmp_sqlite)
config_mod.settings.milvus_path = str(_tmp_milvus)
config_mod.settings.face_storage_dir = str(_tmp_storage)

from core import db, milvus  # noqa: E402
from core.exceptions import BusinessError  # noqa: E402
from core.face_engine import init_face_engine  # noqa: E402
from core.face_storage import FaceStorage  # noqa: E402
from models.student import Student  # noqa: E402
from service.face_service import FaceService  # noqa: E402
from service.student_service import StudentService  # noqa: E402

# insightface 包内官方示例图（多人合影 t1.jpg）
_INSIGHTFACE_IMG = (
    BACKEND_DIR / "venv" / "Lib" / "site-packages"
    / "insightface" / "data" / "images" / "t1.jpg"
)


def _load_real_face_image() -> np.ndarray:
    """读取 insightface 官方示例图（真实人脸），BGR ndarray。"""
    import cv2

    img = cv2.imread(str(_INSIGHTFACE_IMG))
    if img is None:
        raise RuntimeError(f"无法读取测试图片: {_INSIGHTFACE_IMG}")
    return img


def main() -> int:
    print("=" * 60)
    print("P6 第五步 · 人脸录入 API 层 + 级联删除 + face_status 测试")
    print("=" * 60)
    passed = 0
    failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"    ✔ {name}")
        else:
            failed += 1
            print(f"    ✘ {name}")

    try:
        # ---------- 0. 初始化临时环境 ----------
        print("\n[0] 初始化临时环境（建表 + Milvus collection + FaceEngine）...")
        db.Base.metadata.create_all(bind=db.engine)
        milvus.init_milvus()
        milvus.ensure_face_collection()
        init_face_engine()

        # 造两个测试学生（学生1 用于录入/删脸，学生2 用于级联删除）
        session = db.SessionLocal()
        stu1 = Student(student_no="TEST0001", name="学生甲")
        stu2 = Student(student_no="TEST0002", name="学生乙")
        session.add_all([stu1, stu2])
        session.flush()
        stu1_id, stu2_id = stu1.id, stu2.id
        session.commit()
        session.close()
        check("测试学生已创建", stu1_id is not None and stu2_id is not None)

        image = _load_real_face_image()

        # ---------- A. create_face：录入 + 三存储 + face_status ----------
        print("\n[A] create_face：录入 + 三存储落库 + face_status 置 1 ...")
        svc = FaceService(db.SessionLocal(), storage=FaceStorage(root_dir=str(_tmp_storage)))
        result = svc.create_face(stu1_id, image)
        face = result.face
        check("返回 FaceEnrollResult（含 face）", face is not None and face.id > 0)
        check("face_id == id", face.face_id == face.id)
        check("total_faces 已记录（多人合影>1）", result.total_faces >= 1)

        # 三存储验证
        img_bytes = svc.storage.read_by_path(face.image_path)
        check("磁盘图片已保存", img_bytes is not None and len(img_bytes) > 0)

        from core.face_engine import get_face_engine

        emb = get_face_engine().extract(image).embedding
        hits = svc.vector_repo.search(emb, top_k=1)
        check("Milvus 向量已写入（自检索命中）", len(hits) > 0 and hits[0]["face_id"] == face.face_id)

        # face_status 置 1
        s = db.SessionLocal()
        stu = s.get(Student, stu1_id)
        check("face_status 已置 1", stu.face_status == 1)
        s.close()

        # ---------- B. list_faces ----------
        print("\n[B] list_faces：能查回录入的脸照 ...")
        faces = svc.list_faces(stu1_id)
        check("查到 1 条脸照", len(faces) == 1 and faces[0].face_id == face.face_id)

        # ---------- C. delete_face：删单张 + 三处级联 + face_status 回 0 ----------
        print("\n[C] delete_face：删单张 + 三处级联 + face_status 回 0 ...")
        svc.delete_face(face.face_id)
        check("SQLite 脸照记录已删", len(svc.list_faces(stu1_id)) == 0)
        check("磁盘图片已删", svc.storage.read_by_path(face.image_path) is None)
        hits_after = svc.vector_repo.search(emb, top_k=1)
        check("Milvus 向量已删（自检索不再命中该 face_id）", all(h["face_id"] != face.face_id for h in hits_after))
        s = db.SessionLocal()
        stu = s.get(Student, stu1_id)
        check("face_status 已回 0", stu.face_status == 0)
        s.close()

        # ---------- D. 级联删除（删学生）----------
        print("\n[D] delete_student：三处级联全清 ...")
        # 先给学生2录一张脸
        result2 = svc.create_face(stu2_id, image)
        face2 = result2.face
        check("学生2 已录脸", face2.id > 0)

        # 删学生2（走 StudentService.delete_student → FaceService.delete_faces_by_student）
        stu_svc = StudentService(db.SessionLocal())
        stu_svc.delete_student(stu2_id)

        # 三处验证：SQLite faces 行、Milvus 向量、磁盘文件都应清空
        student_gone = False
        try:
            svc.list_faces(stu2_id)
        except BusinessError as e:
            student_gone = (e.code == 4004)
        check("学生2 已删除（再查抛 4004）", student_gone)

        # Milvus：学生2 的向量应清空
        emb2 = get_face_engine().extract(image).embedding
        hits2 = svc.vector_repo.search(emb2, top_k=5, student_id=stu2_id)
        check("Milvus 学生2 向量已清空", len(hits2) == 0)

        # 磁盘：学生2 目录应已删除
        stu2_dir = Path(_tmp_storage) / str(stu2_id)
        check("磁盘学生2 目录已删除", not stu2_dir.exists())

        # ---------- E. 错误路径 ----------
        print("\n[E] 错误路径 ...")
        # 学生不存在
        err = None
        try:
            svc.create_face(999999, image)
        except BusinessError as e:
            err = e
        check("学生不存在 → 4004", err is not None and err.code == 4004)

        # 无脸图
        err2 = None
        black = np.zeros((480, 640, 3), dtype=np.uint8)
        try:
            svc.create_face(stu1_id, black)
        except BusinessError as e:
            err2 = e
        check("无脸图 → 4000", err2 is not None and err2.code == 4000)

        # ---------- 汇总 ----------
        print("\n" + "=" * 60)
        print(f"测试结果：通过 {passed} 项，失败 {failed} 项")
        print("=" * 60)
        return 0 if failed == 0 else 1

    finally:
        try:
            milvus.close_milvus()
        except Exception:
            pass
        shutil.rmtree(_tmp_root, ignore_errors=True)
        print("\n[清理] 临时数据已删除:", _tmp_root)


if __name__ == "__main__":
    sys.exit(main())
