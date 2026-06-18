"""
图片转换脚本 - 将 PNG/JPG 图片转换为 ILI9341 可用的 RGB565 C 数组
使用方法: python scripts/convert_images.py images/ output/
需要安装: pip install pillow
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("请先安装 Pillow: pip install pillow")
    sys.exit(1)

LCD_WIDTH = 240
LCD_HEIGHT = 320


def rgb_to_rgb565(r, g, b):
    """将 RGB888 转换为 RGB565"""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def convert_image(image_path, output_dir, resize=True):
    """转换单张图片为 RGB565 格式的 C 数组"""
    img = Image.open(image_path).convert("RGB")

    if resize:
        # 等比例缩放并居中裁剪到 240x320
        img_ratio = img.width / img.height
        target_ratio = LCD_WIDTH / LCD_HEIGHT

        if img_ratio > target_ratio:
            # 图片更宽，按高度缩放
            new_height = LCD_HEIGHT
            new_width = int(LCD_HEIGHT * img_ratio)
        else:
            # 图片更高，按宽度缩放
            new_width = LCD_WIDTH
            new_height = int(LCD_WIDTH / img_ratio)

        img = img.resize((new_width, new_height), Image.LANCZOS)

        # 居中裁剪
        left = (new_width - LCD_WIDTH) // 2
        top = (new_height - LCD_HEIGHT) // 2
        img = img.crop((left, top, left + LCD_WIDTH, top + LCD_HEIGHT))

    # 转换为 RGB565
    pixels = list(img.getdata())
    rgb565_data = []
    for r, g, b in pixels:
        rgb565_data.append(rgb_to_rgb565(r, g, b))

    # 生成 C 数组 — 用编号命名避免中文/特殊字符问题
    name = Path(image_path).stem
    # 保留原始名用于显示
    original_name = name
    # C 标识符只用 ASCII: img_000, img_001 ...
    # 编号由调用者传入

    output_path = Path(output_dir) / f"{name}.h"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"// 图片: {Path(image_path).name}\n")
        f.write(f"// 尺寸: {LCD_WIDTH}x{LCD_HEIGHT}\n")
        f.write(f"// 格式: RGB565\n")
        f.write(f"// 自动生成，请勿手动修改\n\n")
        f.write(f"#pragma once\n")
        f.write(f"#include <cstdint>\n\n")
        f.write(f"const uint16_t img_{name}_data[{LCD_WIDTH * LCD_HEIGHT}] PROGMEM = {{\n")

        for i in range(0, len(rgb565_data), 16):
            line_data = rgb565_data[i : i + 16]
            hex_values = ", ".join(f"0x{v:04X}" for v in line_data)
            if i + 16 < len(rgb565_data):
                f.write(f"    {hex_values},\n")
            else:
                f.write(f"    {hex_values}\n")

        f.write("};\n")

    print(f"  已生成: {output_path}")
    return name, original_name


def generate_images_header(image_names, output_dir):
    """生成汇总头文件，包含所有图片的引用"""
    output_path = Path(output_dir) / "images.h"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("// 图片汇总头文件 - 自动生成\n")
        f.write("// 中文名仅用于注释和显示，实际变量名为 img_NNN_data\n")
        f.write("#pragma once\n")
        f.write("#include <cstdint>\n\n")

        for idx, (cid, orig) in enumerate(image_names):
            f.write(f'#include "{orig}.h"\n')

        f.write(f"\n// 图片数量\n")
        f.write(f"#define IMAGE_COUNT {len(image_names)}\n\n")

        f.write("// 图片数组指针（数据在 Flash）\n")
        f.write("const uint16_t* images_list[IMAGE_COUNT] = {\n")
        for cid, orig in image_names:
            f.write(f"    img_{orig}_data,\n")
        f.write("};\n\n")

        f.write("// 图片名称（用于调试输出）\n")
        f.write('const char* image_names[IMAGE_COUNT] = {\n')
        for cid, orig in image_names:
            f.write(f'    "{orig}",\n')
        f.write("};\n")

    print(f"\n已生成汇总文件: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/convert_images.py <图片目录> [输出目录]")
        print("示例: python scripts/convert_images.py images/ include/images/")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("include/images")

    if not input_dir.exists():
        print(f"错误: 目录不存在 - {input_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 支持的图片格式
    extensions = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

    image_files = sorted(
        [f for f in input_dir.iterdir() if f.suffix.lower() in extensions]
    )

    if not image_files:
        print(f"错误: 在 {input_dir} 中未找到图片文件")
        print(f"支持的格式: {', '.join(extensions)}")
        sys.exit(1)

    print(f"找到 {len(image_files)} 张图片")
    print(f"输出目录: {output_dir}")
    print()

    image_names = []
    for img_file in image_files:
        print(f"转换: {img_file.name}")
        cid, orig = convert_image(img_file, output_dir)
        image_names.append((cid, orig))

    generate_images_header(image_names, output_dir)

    print(f"\n完成! 共转换 {len(image_names)} 张图片。")
    print(f"请将 include/images/ 目录加入项目中。")


if __name__ == "__main__":
    main()
