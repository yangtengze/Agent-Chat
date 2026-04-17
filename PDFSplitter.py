import fitz
from PIL import Image
import io
import numpy as np
import re
from bs4 import BeautifulSoup
from OcrEngine import get_ppstructure_engine
from DocumentNode import ChunkType, DocumentNode, flatten_tree

class PDFSpliter:

    def __init__(self, file_path):
        self.file_path = file_path
        self.ocr_engine = get_ppstructure_engine()
        self.chunks = []

    def __parse_text(self, block):
        return block['lines'][0]['spans'][0]['text']
    
    def __parse_text_and_size(self, block):
        """
        不仅提取文本，还要提取该块的最大字号，用于判断是否为标题
        """
        text = ""
        max_size = 0
        for line in block['lines']:
            for span in line['spans']:
                text += span['text']
                if span['size'] > max_size:
                    max_size = span['size']
        return text.strip(), max_size
    
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
    
    def __parse_image(self, image_bytes, ocr_engine):
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img_array = np.array(image)
        output = ocr_engine.predict(img_array)
        markdown_texts = ''
        for res in output:
            text = res.markdown['markdown_texts']

            # 用正则找到所有<table>...</table>，分别转换
            def replace_table(match):
                table_html = match.group(0)
                return self.__html_table_to_markdown(table_html)
            text = re.sub(r'<table.*?</table>', replace_table, text, flags=re.DOTALL)
            # 清理残留的HTML标签（div, html, body等）
            text = re.sub(r'</?(div|html|body)[^>]*>', '', text)
            text = re.sub(r'style="[^"]*"', '', text)

            markdown_texts += text.strip() + '\n'
        return markdown_texts
    
    def __lines_to_markdown(self, lines, y_tolerance=5, x_tolerance=20):
        """
        将PDF解析的lines转换为Markdown表格
        y_tolerance: y坐标差异小于此值视为同一行
        x_tolerance: x坐标差异小于此值视为同一列
        """
        
        # 提取有效文本行（过滤空内容）
        valid_lines = []
        for line in lines:
            text = line['spans'][0]['text']
            if text:
                x0, y0, x1, y1 = line['bbox']
                valid_lines.append({
                    'text': text,
                    'x0': x0,
                    'y0': y0,
                    'x1': x1,
                    'y1': y1
                })
        
        # 按y0分组（同一行）
        rows = []
        current_row = []
        last_y = None
        
        for line in sorted(valid_lines, key=lambda x: (x['y0'], x['x0'])):
            if last_y is None or abs(line['y0'] - last_y) <= y_tolerance:
                current_row.append(line)
            # y0差异大
            else:
                if current_row:
                    rows.append(sorted(current_row, key=lambda x: x['x0']))
                current_row = [line]
            last_y = line['y0']
        # 最后一行数据
        if current_row:
            rows.append(sorted(current_row, key=lambda x: x['x0']))
        
        
        # 确定列数（取最大行的列数）
        max_cols = max(len(row) for row in rows) if rows else 0
        
        md_lines = []
        
        for i, row in enumerate(rows):
            cells = [cell['text'] for cell in row]
            # 补齐列数（空列)
            while len(cells) < max_cols:
                cells.append('')
            md_lines.append('|' + '|'.join(cells) + '|')
            
            # 表头后添加分隔行
            if i == 0:
                md_lines.append('|' + '|'.join(['---'] * max_cols) + '|')
        
        return '\n'.join(md_lines)

    def __parse_table(self, block):
        lines = block['lines']
        markdown_texts = self.__lines_to_markdown(lines)
        return markdown_texts

    def parse_pdf(self):
        doc = fitz.open(self.file_path)
        for page_num in range(len(doc)):
            print(f'----第{page_num + 1}页----')
            page = doc[page_num]
            blocks = page.get_text('dict')['blocks']
            
            for block in sorted(blocks, key=lambda x: (x["bbox"][1], x["bbox"][0])):
                if block['type'] == 0:
                    if len(block['lines']) == 1:
                        t = self.__parse_text(block)
                        print("parse_text:", t)
                    else:
                        t = self.__parse_table(block)
                        print("parse_table:", t)
                        
                elif block['type'] == 1:
                    img_bytes = block['image']
                    t = self.__parse_image(image_bytes=img_bytes, ocr_engine=self.ocr_engine)
                    print("parse_image:", t)

    def parse_to_tree(self) -> DocumentNode:
        """
        解析 PDF 并返回 DocumentNode 结构树
        """
        doc = fitz.open(self.file_path)
        
        # 1. 初始化根节点和栈
        root = DocumentNode(chunk_type=ChunkType.TITLE, chunk_level=0, content="ROOT")
        stack = [root]

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text('dict')['blocks']
            
            for block in sorted(blocks, key=lambda x: (x["bbox"][1], x["bbox"][0])):
                # 记录页码等元数据
                metadata = {"page": page_num + 1, "bbox": block["bbox"]}

                if block['type'] == 0:  # 文本块
                    if len(block['lines']) == 1:
                        # 提取文本和最大字号
                        t, font_size = self.__parse_text_and_size(block)
                        if not t: continue
                        
                        # 根据字号大小来推断层级 (这里的阈值可以根据你的实际文档情况调整)
                        is_title = False
                        level = 0
                        if font_size >= 18:
                            is_title, level = True, 1
                        elif font_size >= 15:
                            is_title, level = True, 2
                        elif font_size >= 13:
                            is_title, level = True, 3
                            
                        if is_title:
                            header_node = DocumentNode(
                                chunk_type=ChunkType.TITLE,
                                chunk_level=level,
                                content=t,
                                metadata=metadata
                            )
                            # 层级栈维护：退栈直到找到比当前级别高的父节点
                            while len(stack) > 1 and stack[-1].chunk_level >= level:
                                stack.pop()
                            
                            stack[-1].children.append(header_node)
                            stack.append(header_node)
                        else:
                            # 判定为普通段落
                            paragraph_node = DocumentNode(
                                chunk_type=ChunkType.PARAGRAPH,
                                chunk_level=0,
                                content=t,
                                metadata=metadata
                            )
                            stack[-1].children.append(paragraph_node)
                            
                    else:
                        # 你的原逻辑：多行判定为表格
                        t = self.__parse_table(block)
                        table_node = DocumentNode(
                            chunk_type=ChunkType.TABLE,
                            chunk_level=0,
                            content=t,
                            metadata=metadata
                        )
                        stack[-1].children.append(table_node)
                        
                elif block['type'] == 1:  # 图片块
                    img_bytes = block['image']
                    t = self.__parse_image(image_bytes=img_bytes, ocr_engine=self.ocr_engine)
                    image_node = DocumentNode(
                        chunk_type=ChunkType.IMAGE,
                        chunk_level=0,
                        content=t,
                        metadata=metadata
                    )
                    stack[-1].children.append(image_node)

        return root

if __name__ == "__main__":
    pdf_path = "./text/text_files/text.pdf"
    splitter = PDFSpliter(pdf_path)
    # splitter.parse_pdf()
    doc_tree_root = splitter.parse_to_tree()
    doc_id_mock = 2002
    chunk_entities = flatten_tree(doc_tree_root, doc_id=doc_id_mock)
    
    print("【PDF展平后的入库 Chunk 实体列表】：")
    for chunk in chunk_entities:
        if chunk.chunk_type == "title" and chunk.content == "ROOT":
            continue
            
        print(f"ID: {chunk.id:02d} | 父亲ID: {str(chunk.parent_id):>4} | "
              f"类型: {chunk.chunk_type:<9} | 层级: {chunk.chunk_level} | "
              f"序号: {chunk.chunk_index:02d} | 页码: {chunk.metadata.get('page')}")
        
        content_preview = chunk.content.replace('\n', '\\n')[:30]
        print(f"    内容: {content_preview}...")