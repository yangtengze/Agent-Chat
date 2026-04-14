class TxtSplitter:

    def __init__(self, file_path):
        self.file_path = file_path

    def parse_txt(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = f.read().split('\n\n')
            for d in data:
                print(d)
            


if __name__ == "__main__":
    txt_path = "./text/text_files/text.txt"
    splitter = TxtSplitter(txt_path)
    splitter.parse_txt()