"""Subnet Link Weaver - 主入口点"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.gui.main_window import MainWindow
from src.utils.logger import setup_logger


def check_admin_rights():
    """检查管理员权限"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def main():
    """主函数"""
    # 设置日志
    logger = setup_logger(
        name="SubnetLinkWeaver",
        log_file="logs/app.log",
        log_level="INFO"
    )

    logger.info("Subnet Link Weaver 启动中...")

    # 检查管理员权限
    if not check_admin_rights():
        logger.warning("未以管理员身份运行，部分功能可能无法正常使用")

    # 创建应用程序
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont

    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setApplicationName("Subnet Link Weaver")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("luoqianyi")

    # 设置默认字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    # 创建主窗口
    window = MainWindow()
    window.show()

    logger.info("主窗口已显示")

    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
