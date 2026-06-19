"""生成应用程序 ICO 图标"""

from PIL import Image, ImageDraw
import os


def create_icon(size: int) -> Image.Image:
    """绘制指定尺寸的图标"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景圆
    margin = size // 12
    draw.ellipse([margin, margin, size - margin, size - margin], fill="#2c3e50")

    center = size // 2
    offset = size // 4
    node = size // 7

    nodes = {
        (center - offset, center - offset): "#3498db",  # A 左上
        (center + offset, center - offset): "#e74c3c",  # B 右上
        (center - offset, center + offset): "#2ecc71",  # C 左下
        (center + offset, center + offset): "#f39c12",  # D 右下
    }

    # 连接线
    line_w = max(1, size // 40)
    pts = list(nodes.keys())
    draw.line([pts[0], pts[1]], fill="#ecf0f1", width=line_w)
    draw.line([pts[2], pts[3]], fill="#ecf0f1", width=line_w)
    draw.line([pts[0], pts[2]], fill="#ecf0f1", width=line_w)
    draw.line([pts[1], pts[3]], fill="#ecf0f1", width=line_w)
    draw.line([pts[0], pts[3]], fill="#bdc3c7", width=max(1, line_w // 2))
    draw.line([pts[1], pts[2]], fill="#bdc3c7", width=max(1, line_w // 2))

    # 节点
    for (x, y), color in nodes.items():
        draw.ellipse([x - node, y - node, x + node, y + node], fill=color)

    return img


def main():
    os.makedirs("assets", exist_ok=True)

    # 用 256x256 高清图作为基准，让 Pillow 内部生成全套尺寸
    base = create_icon(256)
    base.save("assets/icon.png", format="PNG")

    base.save(
        "assets/icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    size = os.path.getsize("assets/icon.ico")
    print(f"icon.ico 生成成功: {size} 字节")

    # 校验包含的尺寸
    ico = Image.open("assets/icon.ico")
    print(f"包含尺寸: {sorted(ico.ico.sizes())}")


if __name__ == "__main__":
    main()
