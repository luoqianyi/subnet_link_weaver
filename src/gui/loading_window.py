"""加载窗口模块"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QMovie

from ..core.network import NetworkManager


class LoadAdaptersThread(QThread):
    """加载适配器线程"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, network_manager: NetworkManager):
        super().__init__()
        self.network_manager = network_manager

    def run(self):
        try:
            adapters = self.network_manager.get_adapters()
            self.finished.emit(adapters)
        except Exception as e:
            self.error.emit(str(e))


class LoadingWindow(QWidget):
    """加载窗口"""

    adapters_loaded = pyqtSignal(list)

    def __init__(self):
        super().__init__()

        # 无边框窗口
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 窗口大小
        self.setFixedSize(350, 200)

        # 初始化 UI
        self._init_ui()

        # 居中显示
        self._center_window()

        # 网络管理器
        self.network_manager = NetworkManager()

        # 开始加载
        self._start_loading()

    def _init_ui(self):
        """初始化用户界面"""
        # 主容器
        self.container = QWidget(self)
        self.container.setGeometry(10, 10, 330, 180)
        self.container.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                border-radius: 15px;
                border: 2px solid #34495e;
            }
        """)

        layout = QVBoxLayout(self.container)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 应用名称
        title = QLabel("Subnet Link Weaver")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ecf0f1; background-color: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 加载状态
        self.status_label = QLabel("正在检测网络适配器...")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        self.status_label.setStyleSheet("color: #bdc3c7; background-color: transparent;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 无限进度条
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #34495e;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 提示信息
        hint = QLabel("首次启动可能需要几秒钟...")
        hint.setFont(QFont("Microsoft YaHei", 8))
        hint.setStyleSheet("color: #7f8c8d; background-color: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def _center_window(self):
        """居中显示窗口"""
        screen = self.screen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

    def _start_loading(self):
        """开始加载"""
        self.load_thread = LoadAdaptersThread(self.network_manager)
        self.load_thread.finished.connect(self._on_loaded)
        self.load_thread.error.connect(self._on_error)
        self.load_thread.start()

    def _on_loaded(self, adapters: list):
        """加载完成"""
        self.status_label.setText(f"检测到 {len(adapters)} 个适配器")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        # 延迟关闭，让用户看到结果
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, lambda: self.adapters_loaded.emit(adapters))

    def _on_error(self, error: str):
        """加载失败"""
        self.status_label.setText("检测失败，使用默认配置")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        # 延迟关闭
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, lambda: self.adapters_loaded.emit([]))
