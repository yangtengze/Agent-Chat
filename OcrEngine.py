from paddleocr import PPStructureV3

ocr_engine = None

def initialize_ppstructure():
    global ocr_engine
    if ocr_engine is None:
        ocr_engine = PPStructureV3()
    return ocr_engine

def get_ppstructure_engine():
    global ocr_engine
    if ocr_engine is None:
        return initialize_ppstructure()
    return ocr_engine 