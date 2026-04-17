from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ChunkType(str, Enum):
    TITLE = "title"           # 标题
    PARAGRAPH = "paragraph"   # 普通正文段落
    TABLE = "table"           # 表格
    LIST = "list"             # 列表
    IMAGE = "image"           # 图片/图表

class DocumentNode(BaseModel):
    chunk_type: ChunkType
    chunk_level: int = 0       # 标题层级：1表示一级标题，2表示二级标题；段落为 0
    content: str               # 纯文本内容
    token_count: int = 0       # 可用 tiktoken 计算
    metadata: Dict[str, Any] = Field(default_factory=dict) # 如页码、表格行数等
    
    # 树形结构核心：子节点（例如“第一章”节点下，包含“1.1标题”和“第一章说明段落”）
    children: List['DocumentNode'] = Field(default_factory=list)
    
class ChunkEntity(BaseModel):
    # 下方字段名对应 Java DTO 和 MySQL 表字段
    id: Optional[int] = None           # 插入 MySQL 后的自增ID（如果你用雪花算法可以在这直接生成）
    doc_id: int                        # 所属的文档ID (MySQL中的 document.id)
    parent_id: Optional[int] = None    # 指向父节点的 ID（核心：支持层级回溯）
    # chunk_type: ChunkType
    chunk_type: str
    chunk_level: int
    chunk_index: int                   # 文档内的全局物理顺序，用于相邻块组装
    content: str
    token_count: int
    vector_id: Optional[str] = None    # 写入 Milvus/Qdrant 后的向量ID
    metadata: Dict[str, Any]

def flatten_tree(node: DocumentNode, doc_id: int, parent_id: int = None, counter: dict = None) -> List[ChunkEntity]:
    if counter is None:
        counter = {"index": 1, "id_gen": 1} # 模拟 ID 生成
        
    current_id = counter["id_gen"]
    counter["id_gen"] += 1
    
    entity = ChunkEntity(
        id=current_id,
        doc_id=doc_id,
        parent_id=parent_id,
        chunk_type=node.chunk_type.value,
        # chunk_type=node.chunk_type,
        chunk_level=node.chunk_level,
        chunk_index=counter["index"],
        content=node.content,
        token_count=node.token_count,
        metadata=node.metadata
    )
    counter["index"] += 1
    
    result = [entity]
    for child in node.children:
        result.extend(flatten_tree(child, doc_id, current_id, counter))
        
    return result