class MdSplitter:
    def __init__(self, file_path):
        self.file_path = file_path

    def parse_md(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = f.read()
            print(data)
if __name__ == "__main__":
    pdf_path = "./text/text_files/text.md"
    splitter = MdSplitter(pdf_path)
    splitter.parse_md()