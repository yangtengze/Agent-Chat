import orjson

class JsonSplitter:
    def __init__(self, file_path):
        self.file_path = file_path


    def __flatten_json(self, obj, parent_key='', sep='.'):
        """
        将嵌套 JSON 展平为键值对
        例如: {"a": {"b": 1}} -> {"a.b": 1}
        """
        items = []
        
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                items.extend(self.__flatten_json(v, new_key, sep).items())
                
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                new_key = f"{parent_key}[{i}]" if parent_key else str(i)
                if isinstance(v, (str, int, float, bool)):
                    items.append((parent_key, ', '.join(str(x) for x in obj)))
                    break
                else:
                    items.extend(self.__flatten_json(v, new_key, sep).items())
                    
        else:
            items.append((parent_key, str(obj)))
            
        return dict(items)


    def parse_json(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            json_bytes = f.read()
        data = orjson.loads(json_bytes)

        flat_data = self.__flatten_json(data)

        lines = [f"{k}: {v}" for k, v in flat_data.items()]
        text = '\n'.join(lines)
        print(text)

if __name__ == "__main__":
    file_path = "./text/text_files/text.json"
    splitter = JsonSplitter(file_path)
    splitter.parse_json()
    