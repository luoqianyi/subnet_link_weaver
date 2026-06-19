"""转换 SVG 图标为 ICO 格式"""

def convert_svg_to_ico():
    """使用 Pillow 创建 ICO 图标"""
    try:
        from PIL import Image, ImageDraw
        import os
        import struct

        # 创建一个简单的图标
        def create_icon(size):
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 绘制背景圆
            margin = size // 10
            draw.ellipse([margin, margin, size - margin, size - margin], fill='#2c3e50')

            # 绘制四个节点
            node_size = size // 6
            center_x, center_y = size // 2, size // 2

            # 节点 A (左上)
            draw.ellipse([center_x - size//4 - node_size//2, center_y - size//4 - node_size//2,
                         center_x - size//4 + node_size//2, center_y - size//4 + node_size//2],
                        fill='#3498db')

            # 节点 B (右上)
            draw.ellipse([center_x + size//4 - node_size//2, center_y - size//4 - node_size//2,
                         center_x + size//4 + node_size//2, center_y - size//4 + node_size//2],
                        fill='#e74c3c')

            # 节点 C (左下)
            draw.ellipse([center_x - size//4 - node_size//2, center_y + size//4 - node_size//2,
                         center_x - size//4 + node_size//2, center_y + size//4 + node_size//2],
                        fill='#2ecc71')

            # 节点 D (右下)
            draw.ellipse([center_x + size//4 - node_size//2, center_y + size//4 - node_size//2,
                         center_x + size//4 + node_size//2, center_y + size//4 + node_size//2],
                        fill='#f39c12')

            # 绘制连接线
            line_width = max(1, size // 50)
            draw.line([center_x - size//4, center_y - size//4, center_x + size//4, center_y - size//4],
                     fill='#ecf0f1', width=line_width)
            draw.line([center_x - size//4, center_y + size//4, center_x + size//4, center_y + size//4],
                     fill='#ecf0f1', width=line_width)
            draw.line([center_x - size//4, center_y - size//4, center_x - size//4, center_y + size//4],
                     fill='#ecf0f1', width=line_width)
            draw.line([center_x + size//4, center_y - size//4, center_x + size//4, center_y + size//4],
                     fill='#ecf0f1', width=line_width)

            return img

        # 先保存为 PNG
        png_path = "assets/icon.png"
        img_256 = create_icon(256)
        img_256.save(png_path, format="PNG")

        # 使用 Pillow 转换为 ICO
        # 创建不同尺寸的图像
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        images = []
        for size in sizes:
            img = create_icon(size[0])
            images.append(img)

        # 保存为 ICO
        output_path = "assets/icon.ico"
        # 使用第一个图像作为基础，其他图像作为附加
        images[0].save(
            output_path,
            format="ICO",
            append_images=images[1:],
            sizes=sizes
        )

        # 验证文件
        file_size = os.path.getsize(output_path)
        print(f"图标创建成功: {output_path} ({file_size} 字节)")

        # 同时保存一个大的 PNG 用于预览
        img_256.save("assets/icon_256.png", format="PNG")
        print(f"PNG 图标也已保存: assets/icon_256.png")

        return True

    except Exception as e:
        print(f"创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    convert_svg_to_ico()
