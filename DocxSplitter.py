from docx import Document
from docx.oxml.ns import qn
from PIL import Image
import io
from bs4 import BeautifulSoup
import re
import numpy as np

from OcrEngine import get_ppstructure_engine
from DocumentNode import ChunkType,DocumentNode, flatten_tree
class DocxSplitter:

    def __init__(self, file_path):
        self.file_path = file_path
        self.ocr_engine = get_ppstructure_engine()
        self.xml_base = './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        self.img_xml_base = './/{http://schemas.openxmlformats.org/drawingml/2006/main}'
        self.relationships_xml_base = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

    def __parse_text(self, t_elements):
        return ''.join(t.text for t in t_elements)

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
    
    def __parse_table(self, element):
        markdown_texts = []
        for idx, tr in enumerate(element.findall(self.xml_base + 'tr')):
            texts = ''
            texts += '|'
            for tc in tr.findall(self.xml_base + 'tc'):
                r = tc.find(self.xml_base + 'r')
                t_elements = r.findall(self.xml_base + 't')
                texts += ''.join(t.text for t in t_elements) + '|'
            markdown_texts.append(texts)
            size = len(tr.findall(self.xml_base + 'tc'))
            if idx == 0:
                texts = ''
                texts += '|'
                for _ in range(size):
                    texts += '---|'
                markdown_texts.append(texts)
        return '\n'.join(markdown_texts)
    
    def parse_docx(self):
        doc = Document(self.file_path)
        for element in doc.element.body:
            tag_name = element.tag.split('}')[-1]
            if tag_name == 'p':
                for r in element.findall(self.xml_base + 'r'):
                    t_elements = r.findall(self.xml_base + 't')
                    if t_elements:
                        print('parse_text: ', self.__parse_text(t_elements), end='')
                    drawing = r.find(self.xml_base + 'drawing')
                    if drawing is not None:
                        blip = drawing.find(self.img_xml_base + 'blip')
                        if blip is not None:
                            embed = blip.get(self.relationships_xml_base + 'embed')
                            if embed is not None:
                                image_part = doc.part.related_parts.get(embed)
                                if image_part is not None:
                                    image_bytes = image_part.blob
                                    print('parse_image: ', self.__parse_image(image_bytes,self.ocr_engine), end= '')
            elif tag_name == 'tbl':
                print('parse_table: ')
                markdown_texts = self.__parse_table(element)
                print(markdown_texts)
            print()

    def parse_to_tree(self):
        doc = Document(self.file_path)
        root = DocumentNode(chunk_type=ChunkType.TITLE, chunk_level=0, content="ROOT")
        stack = [root]
        for element in doc.element.body:
            tag_name = element.tag.split('}')[-1]
            
            if tag_name == 'p':
                # 1. 提取当前段落的完整文本（跨越多个 <w:r> 的限制）
                t_elements = element.findall(self.xml_base + 't')
                content = self.__parse_text(t_elements).strip()
                
                # 2. 判断是否是标题以及层级
                is_title = False
                level = 0
                tag_pPr = element.find(self.xml_base + 'pPr')
                if tag_pPr is not None:
                    tag_pStyle = tag_pPr.find(self.xml_base + 'pStyle')
                    if tag_pStyle is not None:
                        val = tag_pStyle.val
                        # 兼容 val="1" 或 val="Heading1" 的情况
                        if val and (val.isdigit() or 'Heading' in val):
                            is_title = True
                            level = int(val.replace('Heading', '').strip()) if 'Heading' in val else int(val)
                
                # 3. 文本节点建树与入栈
                if content:
                    if is_title:
                        header_node = DocumentNode(
                            chunk_type=ChunkType.TITLE,
                            chunk_level=level,
                            content=content
                        )
                        # 层级回溯：如果当前栈顶的层级 >= 遇到的新层级，出栈
                        while len(stack) > 1 and stack[-1].chunk_level >= level:
                            stack.pop()
                        
                        # 新标题挂在父标题下，并成为新的栈顶
                        stack[-1].children.append(header_node)
                        stack.append(header_node)
                    else:
                        paragraph_node = DocumentNode(
                            chunk_type=ChunkType.PARAGRAPH,
                            chunk_level=0,
                            content=content
                        )
                        # 普通段落直接挂在当前栈顶（最近的标题）下
                        stack[-1].children.append(paragraph_node)
                        
                # 4. 提取该段落内嵌入的图片
                drawings = element.findall(self.xml_base + 'drawing')
                for drawing in drawings:
                    blips = drawing.findall(self.img_xml_base + 'blip')
                    for blip in blips:
                        embed = blip.get(self.relationships_xml_base + 'embed')
                        if embed:
                            image_part = doc.part.related_parts.get(embed)
                            if image_part:
                                image_bytes = image_part.blob
                                image_content = self.__parse_image(image_bytes, self.ocr_engine)
                                image_node = DocumentNode(
                                    chunk_type=ChunkType.IMAGE,
                                    chunk_level=0,
                                    content=image_content
                                )
                                # 图片直接作为子节点挂在当前标题下
                                stack[-1].children.append(image_node)
                                
            elif tag_name == 'tbl':
                # 提取表格
                markdown_texts = self.__parse_table(element) # 假设返回的是 MD 格式文本
                table_node = DocumentNode(
                    chunk_type=ChunkType.TABLE,
                    chunk_level=0,
                    content=markdown_texts
                )
                # 表格也挂在当前的栈顶（最近的标题）下
                stack[-1].children.append(table_node)
        return root

if __name__ == "__main__":
    pdf_path = "./text/text_files/text.docx"
    splitter = DocxSplitter(pdf_path)
    # splitter.parse_docx()
    root = splitter.parse_to_tree()
    doc_id_mock = 1001
    chunk_entities = flatten_tree(root, doc_id=doc_id_mock)
    print("\n【展平后的入库 Chunk 实体列表】：")
    for chunk in chunk_entities:
        if chunk.chunk_type == "title" and chunk.content == "ROOT":
            continue
            
        print(f"ID: {chunk.id:02d} | 父亲ID: {str(chunk.parent_id):>4} | "
            f"类型: {chunk.chunk_type:<9} | 层级: {chunk.chunk_level} | "
            f"序号: {chunk.chunk_index:02d}")
        content_preview = chunk.content.replace('\n', '\\n')[:30]
        print(f"    内容: {content_preview}...")