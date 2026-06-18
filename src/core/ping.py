"""连通性测试模块 - Ping 命令封装"""

import subprocess
import re
from dataclasses import dataclass
from typing import Optional


class PingError(Exception):
    """Ping 操作错误"""
    pass


@dataclass
class PingResult:
    """Ping 测试结果"""
    target_ip: str
    success: bool
    packets_sent: int = 0
    packets_received: int = 0
    packet_loss: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0
    average_time: float = 0.0
    error_message: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return (
                f"Ping {self.target_ip}: 成功 "
                f"(发送={self.packets_sent}, 接收={self.packets_received}, "
                f"丢失={self.packet_loss}%, "
                f"平均={self.average_time}ms)"
            )
        else:
            return f"Ping {self.target_ip}: 失败 - {self.error_message}"


class PingTester:
    """连通性测试器"""

    def __init__(self, timeout: int = 10):
        """
        初始化 Ping 测试器

        Args:
            timeout: 超时时间（秒）
        """
        self.timeout = timeout

    def ping(
        self,
        target_ip: str,
        count: int = 4,
        timeout_ms: int = 1000
    ) -> PingResult:
        """
        执行 Ping 测试

        Args:
            target_ip: 目标 IP 地址
            count: 发送的 ping 包数量
            timeout_ms: 超时时间（毫秒）

        Returns:
            Ping 测试结果
        """
        # 构建 ping 命令
        cmd = f"ping -n {count} -w {timeout_ms} {target_ip}"

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            # 解析输出
            return self._parse_ping_output(target_ip, result.stdout, result.returncode)

        except subprocess.TimeoutExpired:
            return PingResult(
                target_ip=target_ip,
                success=False,
                error_message="命令执行超时"
            )
        except Exception as e:
            return PingResult(
                target_ip=target_ip,
                success=False,
                error_message=str(e)
            )

    def _parse_ping_output(
        self,
        target_ip: str,
        output: str,
        return_code: int
    ) -> PingResult:
        """
        解析 Ping 输出

        Args:
            target_ip: 目标 IP 地址
            output: ping 命令输出
            return_code: 返回码

        Returns:
            Ping 测试结果
        """
        # 初始化结果
        result = PingResult(
            target_ip=target_ip,
            success=return_code == 0
        )

        # 解析发送/接收/丢失
        stats_match = re.search(
            r'数据包: 已发送\s*=\s*(\d+),\s*已接收\s*=\s*(\d+),\s*丢失\s*=\s*(\d+)',
            output
        )
        if stats_match:
            result.packets_sent = int(stats_match.group(1))
            result.packets_received = int(stats_match.group(2))
            lost = int(stats_match.group(3))
            if result.packets_sent > 0:
                result.packet_loss = (lost / result.packets_sent) * 100

        # 解析往返时间
        time_match = re.search(
            r'往返行程的估计时间\(以毫秒为单位\):\s*最短\s*=\s*(\d+)ms,\s*最长\s*=\s*(\d+)ms,\s*平均\s*=\s*(\d+)ms',
            output
        )
        if time_match:
            result.min_time = float(time_match.group(1))
            result.max_time = float(time_match.group(2))
            result.average_time = float(time_match.group(3))

        # 检查是否有错误信息
        if "请求超时" in output:
            result.error_message = "请求超时"
        elif "目标主机无法访问" in output:
            result.error_message = "目标主机无法访问"
        elif "TTL 过期" in output:
            result.error_message = "TTL 过期"

        return result

    def quick_test(self, target_ip: str) -> bool:
        """
        快速测试连通性

        Args:
            target_ip: 目标 IP 地址

        Returns:
            是否连通
        """
        result = self.ping(target_ip, count=1, timeout_ms=1000)
        return result.success

    def batch_test(
        self,
        target_ips: list[str],
        count: int = 1
    ) -> dict[str, PingResult]:
        """
        批量测试连通性

        Args:
            target_ips: 目标 IP 地址列表
            count: 每个目标发送的 ping 包数量

        Returns:
            测试结果字典
        """
        results = {}
        for ip in target_ips:
            results[ip] = self.ping(ip, count=count)
        return results
