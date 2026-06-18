"""网络管理模块 - 网络适配器检测与配置"""

import subprocess
import re
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class AdapterStatus(Enum):
    """网络适配器状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


@dataclass
class NetworkAdapter:
    """网络适配器数据模型"""
    name: str
    status: AdapterStatus
    ip_address: str = ""
    subnet_mask: str = ""
    default_gateway: Optional[str] = None
    dns_servers: List[str] = field(default_factory=list)
    is_dhcp: bool = False

    def __str__(self) -> str:
        return f"{self.name} ({self.status.value}) - {self.ip_address}"


class NetworkError(Exception):
    """网络操作错误基类"""
    pass


class AdapterNotFoundError(NetworkError):
    """适配器不存在"""
    pass


class PermissionError(NetworkError):
    """权限不足"""
    pass


class CommandTimeoutError(NetworkError):
    """命令执行超时"""
    pass


class InvalidIPError(NetworkError):
    """无效的 IP 地址"""
    pass


class NetworkManager:
    """网络配置管理器"""

    def __init__(self, timeout: int = 30):
        """
        初始化网络管理器

        Args:
            timeout: 命令执行超时时间（秒）
        """
        self.timeout = timeout

    def _run_command(self, command: str) -> tuple[bool, str, str]:
        """
        执行系统命令

        Args:
            command: 要执行的命令

        Returns:
            (成功标志, 标准输出, 标准错误)
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            raise CommandTimeoutError(f"命令执行超时: {command}")
        except Exception as e:
            raise NetworkError(f"命令执行失败: {e}")

    def get_adapters(self) -> List[NetworkAdapter]:
        """
        获取所有网络适配器

        Returns:
            网络适配器列表
        """
        adapters = []

        # 获取适配器列表
        cmd = "netsh interface show interface"
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"获取适配器列表失败: {stderr}")

        # 解析输出
        lines = stdout.strip().split('\n')
        for line in lines[2:]:  # 跳过标题行
            parts = line.split()
            if len(parts) >= 4:
                admin_state = parts[0]
                state = parts[1]
                name = ' '.join(parts[2:])

                # 确定适配器状态
                if state == "Connected":
                    status = AdapterStatus.CONNECTED
                elif state == "Disconnected":
                    status = AdapterStatus.DISCONNECTED
                else:
                    status = AdapterStatus.UNKNOWN

                # 获取 IP 配置
                ip_info = self._get_ip_config(name)
                adapter = NetworkAdapter(
                    name=name,
                    status=status,
                    ip_address=ip_info.get("ip", ""),
                    subnet_mask=ip_info.get("mask", ""),
                    default_gateway=ip_info.get("gateway"),
                    dns_servers=ip_info.get("dns", []),
                    is_dhcp=ip_info.get("is_dhcp", False)
                )
                adapters.append(adapter)

        return adapters

    def _get_ip_config(self, adapter_name: str) -> dict:
        """
        获取指定适配器的 IP 配置

        Args:
            adapter_name: 适配器名称

        Returns:
            IP 配置字典
        """
        config = {
            "ip": "",
            "mask": "",
            "gateway": None,
            "dns": [],
            "is_dhcp": False
        }

        # 获取 IP 地址
        cmd = f'netsh interface ip show address "{adapter_name}"'
        success, stdout, stderr = self._run_command(cmd)

        if success:
            # 解析 IP 地址
            ip_match = re.search(r'IP 地址:\s+(\d+\.\d+\.\d+\.\d+)', stdout)
            if ip_match:
                config["ip"] = ip_match.group(1)

            # 解析子网掩码
            mask_match = re.search(r'子网掩码:\s+(\d+\.\d+\.\d+\.\d+)', stdout)
            if mask_match:
                config["mask"] = mask_match.group(1)

            # 解析默认网关
            gateway_match = re.search(r'默认网关:\s+(\d+\.\d+\.\d+\.\d+)', stdout)
            if gateway_match:
                config["gateway"] = gateway_match.group(1)

            # 检查是否为 DHCP
            if "DHCP 已启用: 是" in stdout:
                config["is_dhcp"] = True

        # 获取 DNS 服务器
        cmd = f'netsh interface ip show dns "{adapter_name}"'
        success, stdout, stderr = self._run_command(cmd)

        if success:
            dns_matches = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stdout)
            config["dns"] = dns_matches

        return config

    def set_static_ip(
        self,
        adapter_name: str,
        ip_address: str,
        subnet_mask: str,
        default_gateway: Optional[str] = None,
        dns_servers: Optional[List[str]] = None
    ) -> bool:
        """
        设置静态 IP

        Args:
            adapter_name: 适配器名称
            ip_address: IP 地址
            subnet_mask: 子网掩码
            default_gateway: 默认网关（可选）
            dns_servers: DNS 服务器列表（可选）

        Returns:
            操作是否成功
        """
        # 验证 IP 地址格式
        if not self._validate_ip(ip_address):
            raise InvalidIPError(f"无效的 IP 地址: {ip_address}")

        if not self._validate_ip(subnet_mask):
            raise InvalidIPError(f"无效的子网掩码: {subnet_mask}")

        # 设置 IP 地址和子网掩码
        cmd = f'netsh interface ip set address "{adapter_name}" static {ip_address} {subnet_mask}'
        if default_gateway:
            cmd += f" {default_gateway}"

        success, stdout, stderr = self._run_command(cmd)
        if not success:
            raise NetworkError(f"设置 IP 地址失败: {stderr}")

        # 设置 DNS 服务器
        if dns_servers:
            for i, dns in enumerate(dns_servers):
                if i == 0:
                    cmd = f'netsh interface ip set dns "{adapter_name}" static {dns}'
                else:
                    cmd = f'netsh interface ip add dns "{adapter_name}" {dns} index={i + 1}'

                success, stdout, stderr = self._run_command(cmd)
                if not success:
                    raise NetworkError(f"设置 DNS 服务器失败: {stderr}")

        return True

    def add_secondary_ip(
        self,
        adapter_name: str,
        ip_address: str,
        subnet_mask: str
    ) -> bool:
        """
        添加额外的 IP 地址

        Args:
            adapter_name: 适配器名称
            ip_address: 要添加的 IP 地址
            subnet_mask: 子网掩码

        Returns:
            操作是否成功
        """
        # 验证 IP 地址格式
        if not self._validate_ip(ip_address):
            raise InvalidIPError(f"无效的 IP 地址: {ip_address}")

        if not self._validate_ip(subnet_mask):
            raise InvalidIPError(f"无效的子网掩码: {subnet_mask}")

        # 添加 IP 地址
        cmd = f'netsh interface ip add address "{adapter_name}" {ip_address} {subnet_mask}'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"添加 IP 地址失败: {stderr}")

        return True

    def remove_secondary_ip(
        self,
        adapter_name: str,
        ip_address: str
    ) -> bool:
        """
        移除额外的 IP 地址

        Args:
            adapter_name: 适配器名称
            ip_address: 要移除的 IP 地址

        Returns:
            操作是否成功
        """
        cmd = f'netsh interface ip delete address "{adapter_name}" {ip_address}'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"移除 IP 地址失败: {stderr}")

        return True

    def _validate_ip(self, ip: str) -> bool:
        """
        验证 IP 地址格式

        Args:
            ip: IP 地址

        Returns:
            是否有效
        """
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
