import pandas as pd

class ExcelSplitter:
    
    def __init__(self, file_path):
        self.file_path = file_path

    def __parse_excel_df(self, excel_df):
        markdown_text = []
        size = excel_df.shape[1]
        for i in range(excel_df.shape[0]):
            text = '|' + '|'.join(str(x) for x in excel_df.iloc[i,:])  + '|'
            markdown_text.append(text)
            if i == 0:
                text = '|' + '---|' * size
                markdown_text.append(text)
        return '\n'.join(markdown_text)
    
    def parse_excel(self):
        xls = pd.ExcelFile(self.file_path)
        for sheet_name in xls.sheet_names:
            excel_df = pd.read_excel(xls, sheet_name=sheet_name)
            markdown_text = self.__parse_excel_df(excel_df)
            print(markdown_text)

if __name__ == "__main__":
    excel_path = "./text/text_files/text.xlsx"
    splitter = ExcelSplitter(excel_path)
    splitter.parse_excel()