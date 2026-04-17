import pandas as pd
from DocumentNode import ChunkType, DocumentNode, flatten_tree
class CsvSplitter:
    def __init__(self, file_path):
        self.file_path = file_path

    def __parse_line(self, line):
        return '|'+ '|'.join(line) + '|'

    def __parse_header(self, header):
        return '|' + '|'.join(header) + '|\n' + '|' + '---|'* len(header)

    def parse_csv(self):
        doc = pd.read_csv(self.file_path)
        print(self.__parse_header(doc.columns))
        for i in range(doc.shape[0]):
            line = doc.iloc[i,:]
            print(self.__parse_line(line), end='')
            print()
    
    def parse_to_tree(self) -> DocumentNode:
        """
        核心逻辑：结构感知与层次化解析
        将 Csv 文件解析为一棵 DocumentNode 树。
        """
        # 1. 建立一个虚拟的 Root 节点作为树的根基（层级为0）
        root = DocumentNode(chunk_type=ChunkType.TITLE, chunk_level=0, content="ROOT")
        # 2. 使用栈来维护当前的层级关系，初始时只有 root
        stack = [root]
        
        # 用于临时累积多行文本块（如多行段落、多行表格）
        current_block_lines = []
        current_block_type = None

        def flush_block():
            """内部闭包函数：把累积的多行文本打包成一个 Node 挂到树上"""
            nonlocal current_block_lines, current_block_type
            if not current_block_lines:
                return
                
            content = '\n'.join(current_block_lines).strip()
            if content:
                node = DocumentNode(
                    chunk_type=current_block_type or ChunkType.PARAGRAPH,
                    chunk_level=0,  # 段落、表格、列表层级统一算作 0，它们挂在标题下
                    content=content
                )
                # 挂载到当前栈顶的节点（也就是最近的一个父级标题）下
                stack[-1].children.append(node)
                
            current_block_lines = []
            current_block_type = None
        doc = pd.read_csv(self.file_path)
        header_stripped = self.__parse_header(doc.columns).strip()
        if header_stripped.startswith('|'):
            if current_block_type != ChunkType.TABLE:
                flush_block()
                current_block_type = ChunkType.TABLE
            current_block_lines.append(header_stripped)
    
        for i in range(doc.shape[0]):
            line = doc.iloc[i,:]
            line_stripped = self.__parse_line(line).strip()
            
            # --- 1. 处理表格 ---
            if line_stripped.startswith('|'):
                if current_block_type != ChunkType.TABLE:
                    flush_block()
                    current_block_type = ChunkType.TABLE
                current_block_lines.append(line_stripped)
                continue

            # --- 2. 处理空行与普通段落 ---
            if not line_stripped:
                flush_block() # 空行代表段落结束
                continue
                
            if current_block_type not in (ChunkType.PARAGRAPH, None):
                flush_block()
            current_block_type = ChunkType.PARAGRAPH
            current_block_lines.append(line_stripped)
            
        flush_block() # 处理文件末尾残余的最后一块
        return root

if __name__ == "__main__":
    pdf_path = "./text/text_files/text.csv"
    splitter = CsvSplitter(pdf_path)
    # splitter.parse_csv()
    doc_tree_root = splitter.parse_to_tree()
    doc_id_mock = 1001
    chunk_entities = flatten_tree(doc_tree_root, doc_id=doc_id_mock)

    for chunk in chunk_entities:
        # 我们跳过 ROOT 节点不打印
        if chunk.chunk_type == ChunkType.TITLE and chunk.content == "ROOT":
            continue
            
        print(f"ID: {chunk.id:02d} | 父亲ID: {str(chunk.parent_id):>4} | "
              f"类型: {chunk.chunk_type:<9} | 层级: {chunk.chunk_level} | "
              f"序号: {chunk.chunk_index:02d}")
        
        # 截取内容展示
        content_preview = chunk.content.replace('\n', '\\n')[:30]
        print(f"    内容: {content_preview}...")
        if chunk.metadata:
            print(f"    元数据: {chunk.metadata}")
        print("-" * 50)