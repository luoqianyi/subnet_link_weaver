"""构建脚本 - 使用 PyInstaller 打包应用程序"""

import os
import sys
import subprocess
from pathlib import Path


def build():
    """构建可执行文件"""
    # 获取项目根目录
    project_root = Path(__file__).parent
    src_dir = project_root / "src"
    assets_dir = project_root / "assets"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    # 清理旧的构建文件
    print("清理旧的构建文件...")
    if build_dir.exists():
        import shutil
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        import shutil
        shutil.rmtree(dist_dir)

    # 构建 PyInstaller 命令
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "SubnetLinkWeaver",
        "--distpath", str(dist_dir),
        "--workpath", str(build_dir),
        "--specpath", str(project_root),
    ]

    # 添加图标（如果存在）
    icon_path = assets_dir / "icon.ico"
    if not icon_path.exists() or icon_path.stat().st_size < 1000:
        # 如果 ICO 文件不存在或太小，使用 PNG
        icon_path = assets_dir / "icon.png"
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    # 添加数据文件
    cmd.extend([
        "--add-data", f"{assets_dir};assets",
        "--add-data", f"{project_root / 'config'};config",
    ])

    # 添加隐藏导入
    cmd.extend([
        "--hidden-import", "PyQt6",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
    ])

    # 入口点
    cmd.append(str(src_dir / "main.py"))

    # 执行构建
    print("开始构建...")
    print(f"命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=str(project_root))

    if result.returncode == 0:
        print("\n构建成功！")
        print(f"可执行文件位于: {dist_dir / 'SubnetLinkWeaver.exe'}")
    else:
        print("\n构建失败！")
        sys.exit(1)


if __name__ == "__main__":
    build()
