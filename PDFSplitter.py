import fitz
from PIL import Image
import io
import numpy as np
import re
from bs4 import BeautifulSoup

from OcrEngine import get_ppstructure_engine

class PDFSpliter:

    def __init__(self, file_path):
        self.file_path = file_path
        self.ocrEngine = get_ppstructure_engine()
        self.chunks = []

    def __parse_text(self, block):
        return block['lines'][0]['spans'][0]['text']
    
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
                    t = self.__parse_image(image_bytes=img_bytes, ocr_engine=self.ocrEngine)
                    print("parse_image:", t)

if __name__ == "__main__":
    pdf_path = "./text.pdf"
    splitter = PDFSpliter(pdf_path)
    splitter.parse_pdf()