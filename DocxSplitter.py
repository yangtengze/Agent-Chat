from docx import Document
from docx.oxml.ns import qn
from PIL import Image
import io
from bs4 import BeautifulSoup
import re
import numpy as np

from OcrEngine import get_ppstructure_engine

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

if __name__ == "__main__":
    pdf_path = "./text.docx"
    splitter = DocxSplitter(pdf_path)
    splitter.parse_docx()