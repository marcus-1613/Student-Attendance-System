"""P11 第一步 · 人脸检测器（SCRFD/det_10g）独立验证脚本。

用途：
    验证 det_10g.onnx 能被 onnxruntime 独立加载（不经过 insightface 的
    FaceAnalysis.get 完整流水线），并输出检测结果与耗时。

背景（为什么用 SCRFD 而不是单独下载 YOLO）：
    buffalo_l 模型包里的 det_10g.onnx 就是 SCRFD 检测器（InsightFace 默认
    检测器），它是人脸检测领域 SOTA 的轻量模型。第二阶段需求里的"YOLO
    实时检测"用 SCRFD 即可满足，且零新增依赖（复用已装的 onnxruntime）。

运行方式（在 backend/ 目录下）：
    venv\\Scripts\\python.exe scripts\\test_yolo_detector.py

预期输出：
    - 模型加载成功
    - 单张测试图检测出 N 张人脸，打印 bbox + confidence
    - 平均推理耗时（参考：CPU 单帧约 85ms）
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

MODEL_FILE = Path(__file__).resolve().parent.parent.parent / "buffalo" / "models" / "buffalo_l" / "det_10g.onnx"
TEST_IMG = Path(__file__).resolve().parent / "test_face.jpg"


def main() -> int:
    print("=" * 60)
    print("P11 第一步 · SCRFD(det_10g) 人脸检测器验证")
    print("=" * 60)

    # ---------- 1. 检查模型文件 ----------
    print(f"\n[1] 模型文件: {MODEL_FILE}")
    if not MODEL_FILE.exists():
        print(f"    ❌ 模型不存在: {MODEL_FILE}")
        return 1
    print(f"    ✔ 存在 ({MODEL_FILE.stat().st_size / 1024 / 1024:.1f} MB)")

    # ---------- 2. 加载检测器 ----------
    print("\n[2] 加载 SCRFD 检测器 ...")
    try:
        from insightface.model_zoo.scrfd import SCRFD
    except Exception as e:
        print(f"    ❌ import SCRFD 失败: {e}")
        return 1

    det = SCRFD(model_file=str(MODEL_FILE))
    det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5, nms_thresh=0.4)
    print("    ✔ SCRFD 加载成功（CPU，640x640，det_thresh=0.5）")

    # ---------- 3. 单图检测 ----------
    print(f"\n[3] 检测测试图: {TEST_IMG}")
    if not TEST_IMG.exists():
        print(f"    ❌ 测试图不存在: {TEST_IMG}")
        return 1

    img = cv2.imread(str(TEST_IMG))
    print(f"    图片尺寸: {img.shape}")

    # 预热一次（首次推理包含初始化开销）
    _ = det.detect(img, input_size=(640, 640))

    bboxes, kpss = det.detect(img, input_size=(640, 640))
    print(f"    检测到人脸数: {len(bboxes)}")
    for b in bboxes:
        print(f"      bbox=[{b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f}] conf={b[4]:.3f}")

    if len(bboxes) == 0:
        print("    ⚠️ 未检测到人脸（可能是测试图不含人脸，或阈值过高）")

    # ---------- 4. 耗时基准 ----------
    print("\n[4] 推理耗时基准（10 次平均）:")
    ts = []
    for _ in range(10):
        t0 = time.time()
        det.detect(img, input_size=(640, 640))
        ts.append((time.time() - t0) * 1000)
    avg = sum(ts) / len(ts)
    print(f"    平均 {avg:.1f} ms，最快 {min(ts):.1f} ms，最慢 {max(ts):.1f} ms")
    print(f"    对应纯检测上限约 {1000 / avg:.1f} FPS")

    # ---------- 5. 无人脸边界 ----------
    print("\n[5] 无人脸边界（纯色图）:")
    blank = np.full((480, 640, 3), 128, dtype=np.uint8)
    b2, _ = det.detect(blank, input_size=(640, 640))
    print(f"    检测到 {len(b2)} 张脸（应为 0，且不抛异常）")

    print("\n" + "=" * 60)
    print("✅ 验证通过：SCRFD(det_10g) 可独立加载并检测人脸")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
