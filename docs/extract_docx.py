import zipfile, xml.etree.ElementTree as ET

zip_path = r'D:\Master of Engineering\S2\IVP501-xu-li-anh-video\safety_detection\safety_detection\docs\Software Design Document - Safety Detection.docx'
with zipfile.ZipFile(zip_path) as z:
    doc_xml = z.read('word/document.xml')

tree = ET.fromstring(doc_xml)
namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
text = '\n'.join([node.text for node in tree.findall('.//w:t', namespace) if node.text])

with open('extracted_text.txt', 'w', encoding='utf-8') as f:
    f.write(text)
