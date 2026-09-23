"""P6 第二步 · FaceEngine 公共 API 测试脚本（独立测试，非业务代码）。

用途：
    验证 core/face_engine.py 封装后的 FaceEngine 能否：
    1. 成功加载（单例）
    2. 读取真实图片
    3. 检测到人脸
    4. 得到 512 维 embedding

运行方式（在 backend/ 目录下）：
    venv\\Scripts\\python.exe scripts\\test_face_engine_api.py [图片路径]

参数：
    可选传一张人脸图片路径；不传则用默认路径 scripts/test_face.jpg。
    若图片不存在，脚本会明确提示"需要一张真实人脸图片"，不会伪造测试结果。

重要：
    本脚本只验证 FaceEngine 的封装是否正确，不涉及数据库/API/三存储。
"""
import sys
from pathlib import Path

import cv2

# 让脚本能 import 到 backend 下的模块
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.face_engine import init_face_engine, get_face_engine, FaceResult  # noqa: E402

# 默认测试图片：scripts/test_face.jpg（需用户自行放入一张真实人脸照片）
DEFAULT_IMAGE = Path(__file__).resolve().parent / "test_face.jpg"


def main() -> int:
    # 图片路径：优先用命令行参数，否则用默认路径
    image_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IMAGE

    print("=" * 60)
    print("P6 第二步 · FaceEngine 公共 API 测试")
    print("=" * 60)

    # ---------- 1. 检查图片是否存在 ----------
    print(f"\n[1] 测试图片: {image_path}")
    if not image_path.exists():
        print(f"    ❌ 图片不存在：{image_path}")
        print()
        print("    请提供一张真实人脸照片，两种方式任选：")
        print(f"      a. 把图片放到 {DEFAULT_IMAGE}")
        print("      b. 运行时传路径：venv\\Scripts\\python.exe scripts\\test_face_engine_api.py <你的图片路径>")
        print()
        print("    脚本不会伪造测试结果，请放入真实图片后重跑。")
        return 1

    # ---------- 2. 加载 FaceEngine（单例） ----------
    print("\n[2] 加载 FaceEngine ...")
    try:
        init_face_engine()
        engine = get_face_engine()
        assert engine is not None, "get_face_engine() 返回 None，初始化失败"
        print("    ✔ FaceEngine 初始化成功")
    except Exception as e:
        print(f"    ❌ FaceEngine 初始化失败: {type(e).__name__}: {e}")
        return 1

    # 验证单例：再取一次，应该是同一个对象
    engine2 = get_face_engine()
    print(f"    单例校验：两次 get_face_engine() 是同一对象？ {engine is engine2}")

    # ---------- 3. 读取图片 ----------
    print("\n[3] 读取图片 ...")
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"    ❌ 图片无法读取（cv2.imread 返回 None）：{image_path}")
        print("    请确认是有效的图片文件（jpg/png），且路径无中文乱码。")
        return 1
    print(f"    ✔ 图片读取成功，尺寸: {image.shape}（HxWxC）")

    # ---------- 4. 检测人脸 + 提取特征 ----------
    print("\n[4] 检测人脸 + 提取特征 ...")
    result: FaceResult = engine.extract(image)

    print(f"    detected     = {result.detected}")
    print(f"    total_faces  = {result.total_faces}")

    if not result.detected:
        print("    ❌ 未检测到人脸。")
        print("    可能原因：图片里没有人脸 / 人脸太小 / 图片质量太差。")
        print("    请换一张清晰的正脸照片重试。")
        return 1

    # ---------- 5. 校验 embedding 维度 ----------
    print("\n[5] 校验返回结果 ...")
    emb = result.embedding
    print(f"    embedding 维度 = {emb.shape if emb is not None else 'None'}")

    if emb is None or emb.shape[0] != 512:
        print(f"    ❌ embedding 维度不是 512（实际 {emb.shape if emb is not None else 'None'}）")
        return 1
    print("    ✔ embedding 维度 = 512")

    # bbox / landmark
    print(f"    bbox     = {result.bbox}")
    print(f"    landmark = {result.landmark.shape if result.landmark is not None else None}")
    print(f"    det_score = {result.det_score:.4f}")

    # ---------- 6. 汇总 ----------
    print("\n" + "=" * 60)
    print("✅ 测试通过：FaceEngine 封装正确")
    print("=" * 60)
    print("    1. FaceEngine 单例加载成功")
    print("    2. 图片读取成功")
    print("    3. 人脸检测成功")
    print("    4. embedding 维度 = 512")
    print("    下一步可进入 P6 后续开发（faces 模型 + 三存储落库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
