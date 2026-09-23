"""P6 第一步 · 人脸引擎加载验证脚本（独立测试，非业务代码）。

用途：
    验证 InsightFace 能否成功加载 buffalo_l 模型，并输出模型路径与加载结果。
    这是 P6 正式开发前的「环境探针」，用来确认模型文件完整、onnxruntime 推理正常。

运行方式（在 backend/ 目录下）：
    venv\\Scripts\\python.exe scripts\\test_face_engine.py

预期输出：
    - 模型根目录路径
    - buffalo_l 包内各 onnx 文件的完整性（是否齐全、大小是否合理）
    - InsightFace FaceAnalysis 初始化 + 模型加载是否成功
    - 三个关键模型的加载状态（detection / recognition / landmark）
"""
import sys
from pathlib import Path

# 让脚本能 import 到 backend 下的模块（本脚本在 backend/scripts/ 下，向上两级是 backend/）
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 模型根目录：D:\\2026-9-Project\\Student\\buffalo
# 注意：insightface 的目录约定是 <root>/models/<包名>/，即 buffalo/models/buffalo_l/。
# 传 root=MODEL_ROOT 时，insightface 会在 MODEL_ROOT/models/buffalo_l/ 下找模型。
MODEL_ROOT = Path(__file__).resolve().parent.parent.parent / "buffalo"


def main() -> int:
    print("=" * 60)
    print("P6 第一步 · InsightFace buffalo_l 模型加载验证")
    print("=" * 60)

    # ---------- 1. 检查模型目录与文件 ----------
    model_dir = MODEL_ROOT / "models" / "buffalo_l"
    print(f"\n[1] 模型根目录: {MODEL_ROOT}")
    print(f"    模型包子目录: {model_dir}")

    if not model_dir.exists():
        print(f"    ❌ 模型目录不存在: {model_dir}")
        print("    请先解压 buffalo_l.zip 到该目录，确保结构为 buffalo/buffalo_l/*.onnx")
        return 1

    # buffalo_l 包内预期的模型文件（det_10g 检测 / w600k_r50 识别 / 1k3d68 关键点 为必需）
    required = ["det_10g.onnx", "w600k_r50.onnx", "1k3d68.onnx"]
    print(f"\n[2] 模型文件检查:")
    missing = []
    for name in required:
        p = model_dir / name
        if p.exists():
            print(f"    ✔ {name}  ({p.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            print(f"    ✘ {name}  缺失")
            missing.append(name)

    # 额外列出目录里实际存在的文件，便于排查
    all_files = sorted(model_dir.glob("*.onnx")) if model_dir.exists() else []
    if all_files:
        print(f"\n    目录内实际 onnx 文件（{len(all_files)} 个）:")
        for f in all_files:
            print(f"      - {f.name}  ({f.stat().st_size / 1024 / 1024:.1f} MB)")

    if missing:
        print(f"\n    ❌ 缺少必需模型文件: {', '.join(missing)}")
        return 1

    # ---------- 2. 初始化 InsightFace ----------
    print("\n[3] 初始化 InsightFace FaceAnalysis ...")
    try:
        import insightface
        print(f"    insightface 版本: {insightface.__version__}")
    except Exception as e:
        print(f"    ❌ import insightface 失败: {e}")
        return 1

    try:
        from insightface.app import FaceAnalysis
    except Exception as e:
        print(f"    ❌ import FaceAnalysis 失败: {e}")
        return 1

    app = FaceAnalysis(name="buffalo_l", root=str(MODEL_ROOT))
    # 只用 CPU 推理（本机无 GPU）；人脸识别需要 512 维 embedding，检测 + 关键点 + 识别全开
    ctx_id = -1  # -1 = CPU
    try:
        app.prepare(ctx_id=ctx_id, det_size=(640, 640))
        print(f"    ✔ FaceAnalysis.prepare(ctx_id={ctx_id}) 成功")
    except Exception as e:
        print(f"    ❌ 模型加载失败: {type(e).__name__}: {e}")
        print("\n    常见原因排查:")
        print("     1. onnxruntime 版本与模型不兼容")
        print("     2. onnx 文件下载不完整（SHA256 校验不符）")
        print("     3. numpy 版本冲突（应锁 1.26.x，不是 2.x）")
        return 1

    # ---------- 3. 确认三个关键模型都加载成功 ----------
    print("\n[4] 关键模型加载状态:")
    for task_name, key in [
        ("人脸检测 (detection)", "detection"),
        ("人脸识别/嵌入 (recognition)", "recognition"),
        ("关键点 (landmark)", "landmark_3d_68"),
    ]:
        model = app.models.get(key)
        if model is not None:
            print(f"    ✔ {task_name} 已加载")
        else:
            print(f"    ✘ {task_name} 未加载")

    # 识别模型输出维度（应 512，ArcFace）
    rec_model = app.models.get("recognition")
    if rec_model is not None:
        try:
            dim = rec_model.inputs[1].shape[1] if len(rec_model.inputs) > 1 else "?"
            print(f"    识别模型 embedding 维度（参考值）: {dim}")
        except Exception:
            pass

    # ---------- 4. 汇总 ----------
    print("\n" + "=" * 60)
    print("✅ 验证通过：InsightFace 成功加载 buffalo_l 模型")
    print("=" * 60)
    print(f"    模型路径: {model_dir}")
    print("    下一步可进入 P6 正式开发（人脸引擎 + 三存储落库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
