import re
from bs4 import BeautifulSoup
from OcrEngine import get_ppstructure_engine
from DocumentNode import ChunkType, DocumentNode, flatten_tree
from pathlib import Path


class MdSplitter:
    def __init__(self, file_path):
        self.file_path = file_path
        self.ocr_engine = get_ppstructure_engine()

    def __extract_images_from_markdown(self, md_content):
        """
        从 Markdown 内容中提取所有图片路径
        """
        # 匹配 ![alt](path) 语法
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        
        images = []
        for match in re.finditer(pattern, md_content):
            alt_text = match.group(1)  # 图片描述
            image_path = match.group(2)  # 图片路径
            images.append({
                'alt': alt_text,
                'path': image_path,
                'full_match': match.group(0)
            })
        
        return images
    
    def __html_table_to_markdown(self, html_text):
        """HTML表格转Markdown"""
        soup = BeautifulSoup(html_text, 'html.parser')
        table = soup.find('table')

        rows = []
        for tr in table.find_all('tr'):
            row = []
            for cell in tr.find_all(['td', 'th']):
                text = cell.get_text(strip=True)
                colspan = int(cell.get('colspan', 1))
                row.append(text)
                for _ in range(colspan - 1):
                    row.append('')
            rows.append(row)

        if not rows:
            return ''
        
        max_cols = max(len(r) for r in rows)
        
        md_lines = []
        for i, row in enumerate(rows):
            while len(row) < max_cols:
                row.append('')
            md_lines.append('| ' + ' | '.join(row) + ' |')
            if i == 0:
                md_lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')
        
        return '\n'.join(md_lines)

    def __parse_image(self, file_path, ocr_engine, html_dir=None):
        """OCR识别图片，支持相对路径解析"""
        # 解析为绝对路径
        img_path = Path(file_path)
        if not img_path.is_absolute() and html_dir:
            img_path = (html_dir / img_path).resolve()
        else:
            img_path = img_path.resolve()
        
        # 检查文件是否存在
        if not img_path.exists():
            print(f"警告：图片不存在 {img_path}")
            return f"[图片不存在: {file_path}]"
        
        output = ocr_engine.predict(str(img_path))
        markdown_texts = ''
        for res in output:
            text = res.markdown['markdown_texts']
            def replace_table(match):
                table_html = match.group(0)
                return self.__html_table_to_markdown(table_html)
            text = re.sub(r'<table.*?</table>', replace_table, text, flags=re.DOTALL)
            text = re.sub(r'</?(div|html|body)[^>]*>', '', text)
            text = re.sub(r'style="[^"]*"', '', text)
            markdown_texts += text.strip() + '\n'
        return markdown_texts
    
    def parse_md(self):
        html_dir = Path(self.file_path).parent.resolve()
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = f.readlines()
            for d in data:
                images = self.__extract_images_from_markdown(d)
                if images:
                    for image in images:
                        markdown_texts = self.__parse_image(image['path'], self.ocr_engine, html_dir)
                        print(markdown_texts)
                else:
                    print(d,end='')

    def parse_to_tree(self) -> DocumentNode:
        """
        核心逻辑：结构感知与层次化解析
        将 Markdown 文件解析为一棵 DocumentNode 树。
        """
        html_dir = Path(self.file_path).parent.resolve()
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

        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line_stripped = line.strip()
            
            # --- 1. 处理图片 ---
            images = self.__extract_images_from_markdown(line)
            if images:
                flush_block()
                for img in images:
                    # 传入 html_dir 解析相对路径
                    ocr_text = self.__parse_image(img['path'], self.ocr_engine, html_dir)
                    img_node = DocumentNode(
                        chunk_type=ChunkType.IMAGE,
                        chunk_level=0,
                        content=ocr_text, 
                        metadata={"image_path": str(html_dir / img['path']) if not Path(img['path']).is_absolute() else img['path'], 
                                "alt": img['alt']}
                    )
                    stack[-1].children.append(img_node)
                continue
                
                
            # --- 2. 处理标题 (结构感知的核心) ---
            header_match = re.match(r'^(#{1,6})\s+(.*)', line_stripped)
            if header_match:
                flush_block()
                level = len(header_match.group(1)) # 几个 # 就是几级
                
                header_node = DocumentNode(
                    chunk_type=ChunkType.TITLE,
                    chunk_level=level,
                    content=line_stripped
                )
                
                # 维护层级树：如果当前栈顶的层级 >= 遇到的新层级，说明该回退了（比如遇到 ##，要把之前的 ### 弹出去）
                while len(stack) > 1 and stack[-1].chunk_level >= level:
                    stack.pop()
                
                # 新标题挂在父标题下
                stack[-1].children.append(header_node)
                # 新标题入栈，成为后续段落的新爸爸
                stack.append(header_node)
                continue
                
            # --- 3. 处理表格 ---
            if line_stripped.startswith('|'):
                if current_block_type != ChunkType.TABLE:
                    flush_block()
                    current_block_type = ChunkType.TABLE
                current_block_lines.append(line_stripped)
                continue
                
            # --- 4. 处理列表 ---
            if re.match(r'^[-*+]\s+.*|^\d+\.\s+.*', line_stripped):
                if current_block_type != ChunkType.LIST and current_block_type is not None:
                    flush_block()
                current_block_type = ChunkType.LIST
                current_block_lines.append(line_stripped)
                continue

            # --- 5. 处理空行与普通段落 ---
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
    pdf_path = "./text/text_files/text.md"
    splitter = MdSplitter(pdf_path)
    # splitter.parse_md()
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