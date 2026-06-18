"""连通性测试面板模块"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QGroupBox, QTextEdit,
    QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from ..core.ping import PingTester, PingResult


class PingTestThread(QThread):
    """Ping 测试线程"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(PingResult)
    error = pyqtSignal(str)

    def __init__(self, ping_tester: PingTester, target_ip: str, count: int):
        super().__init__()
        self.ping_tester = ping_tester
        self.target_ip = target_ip
        self.count = count

    def run(self):
        try:
            # 逐个发送 ping 包并报告进度
            for i in range(1, self.count + 1):
                self.progress.emit(
                    int((i / self.count) * 100),
                    f"正在发送 ping 包 {i}/{self.count}..."
                )

            # 执行完整的 ping 测试
            result = self.ping_tester.ping(self.target_ip, self.count)
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))


class TestPanel(QWidget):
    """连通性测试面板"""

    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str, str)

    def __init__(self, ping_tester: PingTester):
        super().__init__()

        self.ping_tester = ping_tester
        self.test_history = []

        self._init_ui()

    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 测试配置组
        config_group = QGroupBox("测试配置")
        config_layout = QHBoxLayout(config_group)

        # 目标 IP
        config_layout.addWidget(QLabel("目标 IP:"))
        self.target_ip_input = QLineEdit()
        self.target_ip_input.setPlaceholderText("例如: 192.168.88.197")
        self.target_ip_input.setMinimumWidth(200)
        config_layout.addWidget(self.target_ip_input)

        # Ping 次数
        config_layout.addWidget(QLabel("Ping 次数:"))
        self.count_input = QLineEdit("4")
        self.count_input.setMaximumWidth(80)
        config_layout.addWidget(self.count_input)

        # 测试按钮
        self.test_btn = QPushButton("开始测试")
        self.test_btn.setMinimumHeight(35)
        self.test_btn.clicked.connect(self._start_test)
        config_layout.addWidget(self.test_btn)

        config_layout.addStretch()
        layout.addWidget(config_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.status_label)

        # 测试结果组
        result_group = QGroupBox("测试结果")
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        result_layout.addWidget(self.result_text)

        # 清除历史按钮
        clear_layout = QHBoxLayout()
        clear_layout.addStretch()
        self.clear_btn = QPushButton("清除历史")
        self.clear_btn.clicked.connect(self._clear_history)
        clear_layout.addWidget(self.clear_btn)
        result_layout.addLayout(clear_layout)

        layout.addWidget(result_group)

    def _start_test(self):
        """开始测试"""
        target_ip = self.target_ip_input.text().strip()
        if not target_ip:
            QMessageBox.warning(self, "警告", "请输入目标 IP 地址")
            return

        # 验证 IP 格式
        if not self._validate_ip(target_ip):
            QMessageBox.warning(self, "警告", "请输入有效的 IP 地址")
            return

        # 获取 ping 次数
        try:
            count = int(self.count_input.text())
            if count < 1 or count > 100:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "警告", "Ping 次数必须在 1-100 之间")
            return

        # 禁用测试按钮
        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中...")

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 更新状态
        self.status_label.setText(f"正在测试与 {target_ip} 的连通性...")
        self.status_message.emit(f"开始测试: {target_ip}")

        # 在后台线程中执行
        self.test_thread = PingTestThread(
            self.ping_tester,
            target_ip,
            count
        )
        self.test_thread.progress.connect(self._on_progress)
        self.test_thread.finished.connect(self._on_test_finished)
        self.test_thread.error.connect(self._on_test_error)
        self.test_thread.start()

    def _on_progress(self, value: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def _on_test_finished(self, result: PingResult):
        """测试完成"""
        # 启用测试按钮
        self.test_btn.setEnabled(True)
        self.test_btn.setText("开始测试")

        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 更新状态
        if result.success:
            self.status_label.setText(
                f"测试成功: 平均延迟 {result.average_time}ms"
            )
            self.status_message.emit(f"测试成功: {result.target_ip}")
        else:
            self.status_label.setText(f"测试失败: {result.error_message}")
            self.status_message.emit(f"测试失败: {result.target_ip}")

        # 记录测试历史
        self.test_history.append(result)
        self._update_result_display()

    def _on_test_error(self, error: str):
        """测试失败"""
        # 启用测试按钮
        self.test_btn.setEnabled(True)
        self.test_btn.setText("开始测试")

        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 更新状态
        self.status_label.setText(f"测试出错: {error}")
        self.error_message.emit("测试失败", error)
        self.status_message.emit("测试出错")

    def _update_result_display(self):
        """更新结果显示"""
        self.result_text.clear()

        # 显示所有测试历史
        for i, result in enumerate(self.test_history, 1):
            if result.success:
                text = (
                    f"[{i}] {result.target_ip}\n"
                    f"    状态: 成功\n"
                    f"    发送: {result.packets_sent} 包\n"
                    f"    接收: {result.packets_received} 包\n"
                    f"    丢失: {result.packet_loss}%\n"
                    f"    延迟: 最小={result.min_time}ms, "
                    f"最大={result.max_time}ms, "
                    f"平均={result.average_time}ms\n"
                )
            else:
                text = (
                    f"[{i}] {result.target_ip}\n"
                    f"    状态: 失败\n"
                    f"    错误: {result.error_message}\n"
                )

            self.result_text.append(text)
            self.result_text.append("-" * 50)

    def _clear_history(self):
        """清除测试历史"""
        self.test_history.clear()
        self.result_text.clear()
        self.status_message.emit("测试历史已清除")

    def _validate_ip(self, ip: str) -> bool:
        """验证 IP 地址格式"""
        import re
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        if not match:
            return False

        # 检查每个 octet 的范围
        for i in range(1, 5):
            octet = int(match.group(i))
            if octet < 0 or octet > 255:
                return False

        return True
