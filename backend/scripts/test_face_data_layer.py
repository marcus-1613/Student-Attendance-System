"""P6 第三步 · 人脸数据层测试（独立测试，非业务代码）。

验证内容（对应本阶段 8 项要求）：
1. Face ORM 记录创建成功
2. 按 student_id 查询人脸记录成功
3. Face 记录删除成功
4. Milvus face_vectors collection 能创建
5. 插入 512 维向量成功
6. search 能返回结果和相似度
7. delete 成功
8. 文件系统保存/删除测试成功

测试策略：
- SQLite 用独立的临时数据库文件（不污染 dev.db）。
- Milvus 用独立临时目录（不污染项目 milvus.db）。
- 文件系统用独立临时目录。
- 测试结束后清理全部临时数据。

运行方式（在 backend/ 目录下）：
    venv\\Scripts\\python.exe scripts\\test_face_data_layer.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------- 用临时路径替换配置，避免污染真实数据 ----------
from core import config as config_mod  # noqa: E402

_tmp_root = Path(tempfile.mkdtemp(prefix="face_dl_test_"))
_tmp_sqlite = _tmp_root / "test.db"
_tmp_milvus = _tmp_root / "milvus.db"
_tmp_storage = _tmp_root / "faces"

# 覆盖 settings 里的路径（在 import db/milvus 之前生效）
config_mod.settings.db_path = str(_tmp_sqlite)
config_mod.settings.milvus_path = str(_tmp_milvus)
config_mod.settings.face_storage_dir = str(_tmp_storage)

from core import db, milvus  # noqa: E402
from core.face_storage import FaceStorage  # noqa: E402
from models.face import Face  # noqa: E402
from models.student import Student  # noqa: E402
from repository.face_repo import FaceRepository  # noqa: E402
from repository.face_vector_repo import FaceVectorRepository  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("P6 第三步 · 人脸数据层测试")
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
        # ---------- 0. 建表 + 初始化 Milvus + collection ----------
        print("\n[0] 初始化临时环境（建表 + Milvus collection）...")
        db.Base.metadata.create_all(bind=db.engine)
        milvus.init_milvus()
        milvus.ensure_face_collection()
        client = milvus.get_milvus_client()
        check("Milvus 客户端已连接", client is not None)
        check("face_vectors collection 已创建", client.has_collection(milvus.FACE_COLLECTION))

        # 先造一个测试学生（faces 有外键依赖 students）
        session = db.SessionLocal()
        stu = Student(student_no="TEST0001", name="测试学生")
        session.add(stu)
        session.flush()
        stu_id = stu.id
        session.commit()
        session.close()

        # ---------- 1. Face ORM 创建 ----------
        print("\n[1] Face ORM 创建 ...")
        face_repo = FaceRepository(db.SessionLocal())
        face = Face(face_id=1, student_id=stu_id, image_path="/faces/TEST0001/a.jpg")
        face = face_repo.create(face)
        face_repo.db.commit()
        check("Face 记录创建成功（id 已分配）", face.id is not None and face.id > 0)

        # ---------- 2. 按 student_id 查询 ----------
        print("\n[2] 按 student_id 查询 ...")
        faces = face_repo.list_by_student_id(stu_id)
        check(f"查到 {len(faces)} 条记录", len(faces) == 1 and faces[0].id == face.id)

        # ---------- 3. Face 记录删除 ----------
        print("\n[3] Face 记录删除 ...")
        face_repo2 = FaceRepository(db.SessionLocal())
        target = face_repo2.get_by_id(face.id)
        face_repo2.delete(target)
        face_repo2.db.commit()
        check("删除后再查为 None", face_repo2.get_by_id(face.id) is None)
        face_repo2.db.close()

        # ---------- 4-7. Milvus 向量 ----------
        print("\n[4-7] Milvus 向量 insert/search/delete ...")
        vec_repo = FaceVectorRepository()

        # 插入两条不同向量（face_id=100, 101）
        v_a = np.random.rand(512).astype(np.float32)
        v_a = v_a / np.linalg.norm(v_a)  # 归一化
        v_b = np.random.rand(512).astype(np.float32)
        v_b = v_b / np.linalg.norm(v_b)

        vec_repo.insert(face_id=100, student_id=stu_id, embedding=v_a)
        vec_repo.insert(face_id=101, student_id=stu_id, embedding=v_b)
        check("插入 512 维向量成功", True)

        # search：用 v_a 查询，应该最相似的是 face_id=100
        results = vec_repo.search(v_a, top_k=2)
        check("search 返回结果", len(results) >= 1)
        if results:
            check("最相似的是 face_id=100", results[0]["face_id"] == 100)
            check("返回了相似度（float）", isinstance(results[0]["similarity"], float))
            print(f"      相似度样例: face_id={results[0]['face_id']} sim={results[0]['similarity']:.4f}")

        # delete 单条
        vec_repo.delete(face_id=100)
        after_del = vec_repo.search(v_a, top_k=2)
        check("delete 后 face_id=100 不再返回", all(r["face_id"] != 100 for r in after_del))

        # delete_by_student_id
        vec_repo.insert(face_id=102, student_id=999, embedding=v_a)  # 造一个别的学生
        vec_repo.delete_by_student_id(stu_id)
        # 该学生剩下的 face_id=101 也应被删；999 学生的还在
        remaining = vec_repo.search(v_b, top_k=5)
        check("delete_by_student_id 后该学生向量已清", all(r["student_id"] != stu_id for r in remaining))

        # ---------- 8. 文件系统 ----------
        print("\n[8] 文件系统保存/删除 ...")
        storage = FaceStorage(root_dir=str(_tmp_storage))
        rel = storage.save(student_id=202301001, filename="x.jpg", data=b"fake-jpeg-bytes")
        check("保存返回相对路径", rel == "/202301001/x.jpg")
        data = storage.read(202301001, "x.jpg")
        check("能按 student_id+filename 读回", data == b"fake-jpeg-bytes")
        ok_del = storage.delete(202301001, "x.jpg")
        check("删除单个文件成功", ok_del is True)
        check("删除后再读为 None", storage.read(202301001, "x.jpg") is None)
        # 目录级删除
        storage.save(student_id=202301001, filename="y.jpg", data=b"yyy")
        storage.delete_student_dir(202301001)
        check("删除学生目录后目录不存在", not (_tmp_storage / "202301001").exists())

        # ---------- 汇总 ----------
        print("\n" + "=" * 60)
        print(f"测试结果：通过 {passed} 项，失败 {failed} 项")
        print("=" * 60)
        return 0 if failed == 0 else 1

    finally:
        # 清理临时资源
        try:
            milvus.close_milvus()
        except Exception:
            pass
        shutil.rmtree(_tmp_root, ignore_errors=True)
        print("\n[清理] 临时数据已删除:", _tmp_root)


if __name__ == "__main__":
    sys.exit(main())
