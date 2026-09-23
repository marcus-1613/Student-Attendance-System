"""
枚举容器：班级 / 专业。

数据源是 data/ 下的两个 CSV。设计要点：
1. 启动时用 pandas 读一次，缓存到内存（全局单例），运行时不再碰磁盘。
2. 编码回退：先试 utf-8-sig（带 BOM 的 UTF-8，Windows 记事本常见），
   再试 gbk（Windows Excel 另存 CSV 的默认编码）。这是 Windows 上读
   CSV 的真实坑，不做回退就会 UnicodeDecodeError。
3. CSV 约定单列 `name`，值即枚举项，去空、去重、保序。
4. 修改枚举 = 改 CSV + 重启程序，无需改代码。
"""
import pandas as pd

from core.config import BASE_DIR

# 数据源路径
CLASSES_CSV = BASE_DIR / "data" / "班级.csv"
MAJORS_CSV = BASE_DIR / "data" / "专业.csv"

# 内存缓存
_classes: list[str] = []
_majors: list[str] = []


def _read_names(csv_path) -> list[str]:
    """读 CSV 的 name 列，返回去空去重后的字符串列表。

    编码按 utf-8-sig → gbk 依次尝试。
    """
    for enc in ("utf-8-sig", "gbk"):
        try:
            df = pd.read_csv(csv_path, encoding=enc, dtype=str)
            break
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            # 文件不存在不能静默吞掉——这是配置错误，要抛出来
            raise FileNotFoundError(f"枚举数据源不存在: {csv_path}")
    else:
        raise ValueError(f"无法识别 {csv_path} 的编码（已尝试 utf-8-sig / gbk）")

    if "name" not in df.columns:
        raise ValueError(f"{csv_path} 缺少 'name' 列，实际列: {list(df.columns)}")

    # 去空（NaN / 空串）、去首尾空白、去重、保序
    result: list[str] = []
    seen = set()
    for raw in df["name"]:
        if pd.isna(raw):
            continue
        v = str(raw).strip()
        if v and v not in seen:
            seen.add(v)
            result.append(v)
    return result


def load_enums() -> None:
    """启动时调用一次：从 CSV 加载班级/专业到内存。"""
    global _classes, _majors
    _classes = _read_names(CLASSES_CSV)
    _majors = _read_names(MAJORS_CSV)


def get_classes() -> list[str]:
    return _classes


def get_majors() -> list[str]:
    return _majors
