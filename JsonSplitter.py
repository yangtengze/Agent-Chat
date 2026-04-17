import orjson
from DocumentNode import ChunkType, DocumentNode, flatten_tree

class JsonSplitter:
    def __init__(self, file_path):
        self.file_path = file_path


    def __flatten_json(self, obj, parent_key='', sep='.'):
        """
        将嵌套 JSON 展平为键值对
        例如: {"a": {"b": 1}} -> {"a.b": 1}
        """
        items = []
        
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                items.extend(self.__flatten_json(v, new_key, sep).items())
                
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                new_key = f"{parent_key}[{i}]" if parent_key else str(i)
                if isinstance(v, (str, int, float, bool)):
                    items.append((parent_key, ', '.join(str(x) for x in obj)))
                    break
                else:
                    items.extend(self.__flatten_json(v, new_key, sep).items())
                    
        else:
            items.append((parent_key, str(obj)))
            
        return dict(items)


    def parse_json(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            json_bytes = f.read()
        data = orjson.loads(json_bytes)

        flat_data = self.__flatten_json(data)

        lines = [f"{k}: {v}" for k, v in flat_data.items()]
        text = '\n'.join(lines)
        print(text)
    def parse_to_tree(self) -> DocumentNode:
        """
        [核心修改]：解析 JSON 并返回 DocumentNode 结构树
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            json_bytes = f.read()
        data = orjson.loads(json_bytes)

        # 初始化虚拟根节点
        root = DocumentNode(chunk_type=ChunkType.TITLE, chunk_level=0, content="ROOT")

        if isinstance(data, dict):
            # 将最外层的 key 视为“标题（章节）”
            for top_key, top_value in data.items():
                # 1. 建立一级标题节点
                title_node = DocumentNode(
                    chunk_type=ChunkType.TITLE,
                    chunk_level=1,
                    content=f'"{top_key}" 对象信息'
                )
                root.children.append(title_node)

                # 2. 对其内部进行打平处理，将叶子节点作为段落挂在标题下
                flat_data = self.__flatten_json(top_value, parent_key=top_key)
                for k, v in flat_data.items():
                    para_node = DocumentNode(
                        chunk_type=ChunkType.PARAGRAPH,
                        chunk_level=0,
                        content=f"{k}: {v}",
                        metadata={"json_path": k}  # 把路径存入元数据，方便溯源
                    )
                    title_node.children.append(para_node)

        elif isinstance(data, list):
            # 如果最外层是数组，把每个元素当作一个“章节”
            for i, item in enumerate(data):
                title_node = DocumentNode(
                    chunk_type=ChunkType.TITLE,
                    chunk_level=1,
                    content=f"列表项 [{i}]"
                )
                root.children.append(title_node)

                flat_data = self.__flatten_json(item, parent_key=f"[{i}]")
                for k, v in flat_data.items():
                    para_node = DocumentNode(
                        chunk_type=ChunkType.PARAGRAPH,
                        chunk_level=0,
                        content=f"{k}: {v}",
                        metadata={"json_path": k}
                    )
                    title_node.children.append(para_node)
        else:
            # 极少情况：根节点直接就是基本数据类型
            node = DocumentNode(
                chunk_type=ChunkType.PARAGRAPH,
                chunk_level=0,
                content=str(data)
            )
            root.children.append(node)

        return root
    
if __name__ == "__main__":
    file_path = "./text/text_files/text.json"
    splitter = JsonSplitter(file_path)
    # splitter.parse_json()

    doc_tree_root = splitter.parse_to_tree()
    doc_id_mock = 3003
    chunk_entities = flatten_tree(doc_tree_root, doc_id=doc_id_mock)
    
    print("【JSON 展平后的入库 Chunk 实体列表】：")
    for chunk in chunk_entities:
        if chunk.chunk_type == "title" and chunk.content == "ROOT":
            continue
            
        print(f"ID: {chunk.id:02d} | 父亲ID: {str(chunk.parent_id):>4} | "
              f"类型: {chunk.chunk_type:<9} | 层级: {chunk.chunk_level} | "
              f"序号: {chunk.chunk_index:02d}")
        print(f"    内容: {chunk.content}")
    