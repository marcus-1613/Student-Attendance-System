"""脸库审计相关的 Pydantic DTO。

对应需求文档 10.1 节 + 规划文档 13 节的脸库审计接口。

输出字段说明（规划文档 Q7 采用选项 1，扩展为三字段）：
- duplicates  ：疑似重复登记——两个「不同学号」的人脸相似度 > 0.85，疑似一人多号。
- dirty_faces ：疑似脏录入——「同一学号」的两张脸相似度 < 0.6，大概率录错人。
- clusters    ：层次聚类结果——把两两高相似的人脸聚成「可疑团伙」，信息量比
                两两配对更大（如 3 个学号两两相似，配对法给 3 条边，聚类给 1 个簇）。

这三类都是「嫌疑清单」，不是「判决书」——阈值是经验值，真实系统需人工复核。
"""
from pydantic import BaseModel, Field


class StudentBrief(BaseModel):
    """审计结果里引用的学生简要信息。"""
    id: int
    name: str
    student_no: str


class DuplicateItem(BaseModel):
    """疑似重复登记（一对）。"""
    student_a: StudentBrief
    student_b: StudentBrief
    similarity: float = Field(description="余弦相似度，0~1")


class DirtyFaceItem(BaseModel):
    """疑似脏录入：同一学生的两张差异极大的脸。"""
    student: StudentBrief
    face_a_id: int = Field(description="第一张脸的 face_id")
    face_b_id: int = Field(description="第二张脸的 face_id")
    similarity: float = Field(description="两张脸之间的相似度，越低越可疑")


class ClusterItem(BaseModel):
    """一个可疑团伙（多张两两高相似的脸）。"""
    faces: list[dict] = Field(
        description="簇内每张脸的 {face_id, student_id, student_name, student_no}"
    )


class AuditOut(BaseModel):
    """审计结果总览。"""
    total_faces: int = Field(description="参与审计的人脸总数")
    total_students: int = Field(description="涉及的学生数")
    duplicates: list[DuplicateItem] = Field(default_factory=list)
    dirty_faces: list[DirtyFaceItem] = Field(default_factory=list)
    clusters: list[ClusterItem] = Field(default_factory=list)
