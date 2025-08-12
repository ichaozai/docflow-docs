import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import os


def extract_coordinates_from_parse_result(parse_result):
    """
    从API返回的解析结果中提取每页的宽高、角度和所有detail块的坐标信息
    返回: [{width, height, angle, details: [detail, ...]}, ...]
    """
    result = parse_result.get("result", {})
    pages = result.get("pages", [])
    details = result.get("detail", [])

    # 按页组织details
    page_map = {}
    for page in pages:
        page_id = page.get("page_id", 1)
        page_map[page_id] = {
            "width": page.get("width", 0),
            "height": page.get("height", 0),
            "angle": page.get("angle", 0),
            "details": []
        }
    for d in details:
        page_id = d.get("page_id", 1)
        if page_id in page_map:
            page_map[page_id]["details"].append(d)
    # 保证顺序
    return [page_map[pid] for pid in sorted(page_map.keys())]




def pdf_to_images(pdf_path, output_dir="./temp_images"):
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = 144 / 72 # dpi=144，图片更清晰
    mat = fitz.Matrix(zoom, zoom)
    image_paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        img_path = os.path.join(output_dir, f"page_{i+1}.png")
        pix.save(img_path)
        image_paths.append(img_path)
    doc.close()
    return image_paths

def draw_boxes_on_image(image_path, details, page_width, page_height, color=(26,102,255), line_width=2):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    img_w, img_h = image.size
    # 根据解析时的页面宽高缩放适配，确保绘制坐标准确
    scale_x = img_w / page_width if page_width else 1
    scale_y = img_h / page_height if page_height else 1
    for d in details:
        pos = d.get("position")
        if pos and len(pos) == 8:
            points = [
                (pos[0]*scale_x, pos[1]*scale_y),
                (pos[2]*scale_x, pos[3]*scale_y),
                (pos[4]*scale_x, pos[5]*scale_y),
                (pos[6]*scale_x, pos[7]*scale_y),
                (pos[0]*scale_x, pos[1]*scale_y)
            ]
            draw.line(points, fill=color, width=line_width)
    out_path = image_path.replace('.png', '_boxed.png')
    image.save(out_path)
    return out_path

def annotate_pdf_with_boxes(pdf_path, page_details, output_dir="./annotated_images"):
    os.makedirs(output_dir, exist_ok=True)
    image_paths = pdf_to_images(pdf_path, output_dir=output_dir)
    result_paths = []
    for i, page in enumerate(page_details):
        img_path = image_paths[i]
        out_path = draw_boxes_on_image(
            img_path, 
            page["details"], 
            page["width"], 
            page["height"]
        )
        result_paths.append(out_path)
    return result_paths

# 使用示例
if __name__ == "__main__":
    import json
    PDF_PATH = "文档解析pdf示例.pdf"
    JSON_PATH = "parse-result.json"
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        parse_result = json.load(f)
    page_details = extract_coordinates_from_parse_result(parse_result)
    result_imgs = annotate_pdf_with_boxes(PDF_PATH, page_details)
    print("标注图片：", result_imgs)