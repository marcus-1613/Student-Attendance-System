"""人脸相似度阈值标定脚本。

为什么要做标定：
    项目里「录入查重」用的是余弦相似度阈值 0.75，但这个数字是**拍出来的**，
    没有任何实验依据——项目早期的规划文档里也标注过「阈值无依据，需要标定」。

    一个给不出依据的阈值，在面试里是个等着被问倒的坑；标定过之后，
    「同人 >= 0.82、异人 <= 0.61，阈值取 0.75」这样的结论才可以直接讲。

需要的样本（用手机拍就行，不必用公开数据集）
    samples/
      person_01/   1.jpg  2.jpg  3.jpg     # 同一个人，不同角度 / 光照 / 距离
      person_02/   1.jpg  2.jpg  3.jpg
      ...

    建议 15~20 个人，每人 3~5 张。
    **务必覆盖你实际的使用场景**——教室光线、摄像头高度与角度。
    在同一间教室、用同一台摄像头拍出来的样本，标定结果才有意义。

原理：
    insightface 输出的 512 维特征向量**已是 L2 归一化**的，
    因此两条向量的余弦相似度就是它们的点积。

    同人配对的相似度应偏高，异人配对应偏低；两个分布越分得开，阈值越好选。
    若有重叠，则必须在「误拒」与「误放」之间做取舍。

用法：
    python scripts/calibrate_face_threshold.py --samples samples/
    python scripts/calibrate_face_threshold.py --selftest    # 不依赖模型，自检数学部分
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 本脚本位于 backend/scripts/ 下，与项目现有的验证脚本同级。
# 运行方式与它们保持一致：在 backend/ 目录下执行 python scripts/xxx.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


# ============================================================
# 纯计算部分（不依赖任何模型，可单独自检）
# ============================================================

def pair_similarities(
    embeddings: dict[str, list[np.ndarray]],
) -> tuple[list[float], list[float]]:
    """把样本拆成「同人配对」与「异人配对」，分别算出余弦相似度。

    Args:
        embeddings: {人员标识: [该人的若干条特征向量]}

    Returns:
        (同人相似度列表, 异人相似度列表)
    """
    same: list[float] = []
    diff: list[float] = []

    people = sorted(embeddings)
    for person in people:
        for a, b in itertools.combinations(embeddings[person], 2):
            same.append(float(np.dot(a, b)))

    for p1, p2 in itertools.combinations(people, 2):
        for a in embeddings[p1]:
            for b in embeddings[p2]:
                diff.append(float(np.dot(a, b)))

    return same, diff


def error_rates(
    same: list[float], diff: list[float], threshold: float
) -> tuple[float, float]:
    """给定阈值，计算误拒率与误放率（相似度 >= 阈值 视为同一人）。

    - 误拒率 FRR：同一人却被判为不相似——正常学生需要重拍
    - 误放率 FAR：不同人却被判为相似——代打卡被放行
    """
    frr = sum(1 for s in same if s < threshold) / len(same) if same else 0.0
    far = sum(1 for s in diff if s >= threshold) / len(diff) if diff else 0.0
    return frr, far


def find_eer_threshold(
    same: list[float], diff: list[float]
) -> tuple[float, float, float]:
    """扫描候选阈值，找出误拒率与误放率最接近相等的点（EER）。

    EER 是生物识别里衡量两组分布可分性的标准做法：不追求某个错误率最优，
    而是找两个错误代价相等的刻度，作为「分得开不开」的客观指标。

    Returns:
        (阈值, 该点的误拒率, 该点的误放率)
    """
    best = (0.5, 1.0, 1.0)
    best_gap = float("inf")
    for t in np.linspace(0.0, 1.0, 1001):
        frr, far = error_rates(same, diff, float(t))
        if abs(frr - far) < best_gap:
            best_gap = abs(frr - far)
            best = (float(t), frr, far)
    return best


def describe(values: list[float]) -> str:
    """把一组相似度压成一行统计描述。"""
    if not values:
        return "（无样本）"
    arr = np.asarray(values)
    return (
        f"n={len(values):<5} min={arr.min():.3f}  p5={np.percentile(arr, 5):.3f}  "
        f"中位数={np.median(arr):.3f}  p95={np.percentile(arr, 95):.3f}  "
        f"max={arr.max():.3f}"
    )


# ============================================================
# 依赖模型的部分
# ============================================================

def load_samples(samples_dir: Path) -> dict[str, list[Path]]:
    """按 person_xx 子目录收集图片路径。"""
    if not samples_dir.exists():
        raise SystemExit(
            f"样本目录不存在：{samples_dir}\n"
            "请按脚本顶部说明的目录结构准备样本（每个子目录 = 一个人）。"
        )

    people: dict[str, list[Path]] = {}
    for person_dir in sorted(p for p in samples_dir.iterdir() if p.is_dir()):
        images = sorted(
            f for f in person_dir.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES
        )
        if images:
            people[person_dir.name] = images

    if len(people) < 2:
        raise SystemExit(
            f"至少需要 2 个人的样本（当前 {len(people)} 个），否则无法计算异人配对。"
        )
    return people


def extract_embeddings(
    people: dict[str, list[Path]],
) -> dict[str, list[np.ndarray]]:
    """用项目自己的人脸引擎提取特征向量。"""
    import cv2

    from core.config import settings
    from core.face_engine import FaceEngine

    engine = FaceEngine(model_root=settings.face_model_root)
    embeddings: dict[str, list[np.ndarray]] = {}

    for person, paths in people.items():
        vectors: list[np.ndarray] = []
        for path in paths:
            image = cv2.imread(str(path))
            if image is None:
                print(f"  [跳过] 无法读取：{path}")
                continue
            result = engine.extract(image)
            if not result.detected:
                print(f"  [跳过] 未检测到人脸：{path}")
                continue
            vectors.append(result.embedding)
        if vectors:
            embeddings[person] = vectors
            print(f"  {person}: 有效样本 {len(vectors)}/{len(paths)}")

    return embeddings


# ============================================================
# 自检：用合成向量验证纯计算部分（不加载模型）
# ============================================================

def run_selftest() -> int:
    """构造两组可分性已知的合成向量，检查配对与阈值计算是否正确。"""
    rng = np.random.default_rng(42)

    def unit(v: np.ndarray) -> np.ndarray:
        return v / np.linalg.norm(v)

    embeddings: dict[str, list[np.ndarray]] = {}
    # 每人的基准方向不同（模拟"不同人"），同人内部加小噪声（模拟"不同角度"）
    for i in range(5):
        base = unit(rng.normal(size=512))
        embeddings[f"p{i}"] = [
            unit(base + rng.normal(scale=0.05, size=512)) for _ in range(4)
        ]

    same, diff = pair_similarities(embeddings)
    threshold, frr, far = find_eer_threshold(same, diff)

    print(f"同人配对 {len(same)} 组：{describe(same)}")
    print(f"异人配对 {len(diff)} 组：{describe(diff)}")
    print(f"EER 阈值 = {threshold:.3f}（误拒 {frr:.1%} / 误放 {far:.1%}）")

    ok = True
    if len(same) != 5 * 6:
        print(f"✗ 同人配对数量应为 30，实际 {len(same)}")
        ok = False
    if len(diff) != 10 * 16:
        print(f"✗ 异人配对数量应为 160，实际 {len(diff)}")
        ok = False
    if not min(same) > max(diff):
        print("✗ 合成数据本应完全可分，但两个分布出现重叠")
        ok = False
    if not max(diff) < threshold < min(same):
        print(f"✗ EER 阈值 {threshold:.3f} 未落在两分布之间的间隙内")
        ok = False

    print("✓ 自检通过" if ok else "✗ 自检失败")
    return 0 if ok else 1


# ============================================================
# 主流程
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="人脸相似度阈值标定")
    parser.add_argument(
        "--samples", type=Path, default=PROJECT_ROOT / "samples",
        help="样本根目录（默认 <项目根>/samples）",
    )
    parser.add_argument(
        "--selftest", action="store_true",
        help="用合成向量自检数学部分，不加载模型",
    )
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()

    people = load_samples(args.samples)
    print(f"共 {len(people)} 个人，{sum(len(v) for v in people.values())} 张图片")
    print("正在提取特征向量 ...")
    embeddings = extract_embeddings(people)

    same, diff = pair_similarities(embeddings)
    if not same or not diff:
        print("样本不足，无法计算。请检查是否有人的图片全部提取失败。")
        return 1

    threshold, frr, far = find_eer_threshold(same, diff)

    print("\n" + "=" * 68)
    print("标定结果")
    print("=" * 68)
    print(f"同人配对：{describe(same)}")
    print(f"异人配对：{describe(diff)}")
    print()
    print(f"EER 阈值        = {threshold:.3f}   （误拒 {frr:.1%} / 误放 {far:.1%}）")
    print(f"同人最低相似度  = {min(same):.3f}")
    print(f"异人最高相似度  = {max(diff):.3f}")

    if min(same) > max(diff):
        print(
            "\n两个分布**完全分开**：阈值取 "
            f"{max(diff):.3f} ~ {min(same):.3f} 之间任意值都不会出错。"
        )
    else:
        print("\n两个分布**存在重叠**，无法做到零错误。取舍依据业务代价：")
        print("  · 查重场景应偏严——误放（代打卡成功）的代价高于误拒（重拍一次）")
        print(
            f"  · 偏严可取 {np.percentile(diff, 99):.3f} 附近，"
            "此时几乎不放行异人，代价是少量同人需要重拍"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
