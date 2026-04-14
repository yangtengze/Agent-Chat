from markdownify import markdownify as md
from bs4 import BeautifulSoup
from OcrEngine import get_ppstructure_engine
import re

class HtmlSplitter:

    def __init__(self, file_path):
        self.file_path = file_path
        self.ocr_engine = get_ppstructure_engine()
    
    def __html_file_to_markdown(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')

        for tag in soup(['head', 'script', 'style', 'nav', 'footer']):
            tag.decompose()

        markdown_texts = md(str(soup), heading_style="ATX")
        return markdown_texts
    
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
    
    def __parse_image(self, file_path, ocr_engine):
        output = ocr_engine.predict(file_path)
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
       
    def parse_html(self):
        markdown_texts = self.__html_file_to_markdown()
        for d in markdown_texts.split('\n'):
            images = self.__extract_images_from_markdown(d)
            if images:
                for image in images:
                    texts = self.__parse_image(image['path'], self.ocr_engine)
                    print(texts)
            else:
                print(d)

if __name__ == "__main__":
    file_path = "./text/text_files/text.html"
    splitter = HtmlSplitter(file_path)
    splitter.parse_html()
    