import pandas as pd

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


if __name__ == "__main__":
    pdf_path = "./text.csv"
    splitter = CsvSplitter(pdf_path)
    splitter.parse_csv()