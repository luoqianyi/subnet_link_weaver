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

    def _run_command(self, command: str, use_powershell: bool = False) -> tuple[bool, str, str]:
        """
        执行系统命令

        Args:
            command: 要执行的命令
            use_powershell: 是否使用 PowerShell 执行

        Returns:
            (成功标志, 标准输出, 标准错误)
        """
        try:
            if use_powershell:
                # 使用 PowerShell 执行命令，设置 UTF-8 编码
                cmd = f'powershell -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}"'
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    timeout=self.timeout
                )
                # 尝试多种编码解码
                for encoding in ['utf-8', 'gbk', 'cp936', 'latin1']:
                    try:
                        stdout = result.stdout.decode(encoding)
                        stderr = result.stderr.decode(encoding)
                        return result.returncode == 0, stdout, stderr
                    except (UnicodeDecodeError, LookupError):
                        continue
                # 如果所有编码都失败，使用 latin1 作为后备
                stdout = result.stdout.decode('latin1')
                stderr = result.stderr.decode('latin1')
                return result.returncode == 0, stdout, stderr
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    timeout=self.timeout
                )
                # 尝试多种编码解码
                for encoding in ['utf-8', 'gbk', 'cp936', 'latin1']:
                    try:
                        stdout = result.stdout.decode(encoding)
                        stderr = result.stderr.decode(encoding)
                        return result.returncode == 0, stdout, stderr
                    except (UnicodeDecodeError, LookupError):
                        continue
                # 如果所有编码都失败，使用 latin1 作为后备
                stdout = result.stdout.decode('latin1')
                stderr = result.stderr.decode('latin1')
                return result.returncode == 0, stdout, stderr
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

        # 使用 PowerShell 获取适配器列表（更可靠的编码处理）
        cmd = "Get-NetAdapter | Select-Object Name, Status, InterfaceDescription | Format-Table -AutoSize"
        success, stdout, stderr = self._run_command(cmd, use_powershell=True)

        if not success:
            # 回退到 netsh 命令
            cmd = "netsh interface show interface"
            success, stdout, stderr = self._run_command(cmd)

            if not success:
                raise NetworkError(f"获取适配器列表失败: {stderr}")

        # 解析输出
        lines = stdout.strip().split('\n')
        for line in lines[2:]:  # 跳过标题行
            parts = line.split()
            if len(parts) >= 2:
                # 检查是否是 PowerShell 输出格式
                if "Format-Table" in stdout or "Name" in lines[0]:
                    # PowerShell 输出格式
                    name = parts[0]
                    status_str = parts[1] if len(parts) > 1 else "Unknown"

                    # 确定适配器状态
                    if status_str.lower() == "up":
                        status = AdapterStatus.CONNECTED
                    elif status_str.lower() == "down":
                        status = AdapterStatus.DISCONNECTED
                    else:
                        status = AdapterStatus.UNKNOWN
                else:
                    # netsh 输出格式
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

        # 使用 PowerShell 获取 IP 配置
        cmd = f'Get-NetIPAddress -InterfaceAlias "{adapter_name}" -AddressFamily IPv4 | Select-Object IPAddress, PrefixLength'
        success, stdout, stderr = self._run_command(cmd, use_powershell=True)

        if success and stdout.strip():
            # 解析 PowerShell 输出
            lines = stdout.strip().split('\n')
            for line in lines[2:]:  # 跳过标题行
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    prefix_length = parts[1]

                    # 验证 IP 地址格式
                    if self._validate_ip(ip):
                        config["ip"] = ip

                        # 将前缀长度转换为子网掩码
                        if prefix_length.isdigit():
                            prefix = int(prefix_length)
                            mask = self._prefix_to_subnet_mask(prefix)
                            config["mask"] = mask
                        break

        # 获取默认网关
        cmd = f'Get-NetRoute -InterfaceAlias "{adapter_name}" -DestinationPrefix "0.0.0.0/0" | Select-Object NextHop'
        success, stdout, stderr = self._run_command(cmd, use_powershell=True)

        if success and stdout.strip():
            lines = stdout.strip().split('\n')
            for line in lines[2:]:
                parts = line.split()
                if parts:
                    gateway = parts[0]
                    if self._validate_ip(gateway):
                        config["gateway"] = gateway
                        break

        # 获取 DNS 服务器
        cmd = f'Get-DnsClientServerAddress -InterfaceAlias "{adapter_name}" -AddressFamily IPv4 | Select-Object ServerAddresses'
        success, stdout, stderr = self._run_command(cmd, use_powershell=True)

        if success and stdout.strip():
            # 解析 DNS 服务器地址（可能以逗号分隔）
            dns_matches = re.findall(r'(\d+\.\d+\.\d+\.\d+)', stdout)
            config["dns"] = dns_matches

        # 检查是否为 DHCP
        cmd = f'Get-NetIPInterface -InterfaceAlias "{adapter_name}" -AddressFamily IPv4 | Select-Object Dhcp'
        success, stdout, stderr = self._run_command(cmd, use_powershell=True)

        if success and stdout.strip():
            if "Enabled" in stdout:
                config["is_dhcp"] = True

        return config

    def _prefix_to_subnet_mask(self, prefix: int) -> str:
        """
        将前缀长度转换为子网掩码

        Args:
            prefix: 前缀长度

        Returns:
            子网掩码
        """
        if prefix < 0 or prefix > 32:
            return "255.255.255.0"

        mask = (0xffffffff >> (32 - prefix)) << (32 - prefix)
        return f"{(mask >> 24) & 0xff}.{(mask >> 16) & 0xff}.{(mask >> 8) & 0xff}.{mask & 0xff}"

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

    def get_all_ips(self, adapter_name: str) -> List[dict]:
        """
        获取指定适配器的所有 IP 地址

        Args:
            adapter_name: 适配器名称

        Returns:
            IP 地址列表
        """
        ips = []

        cmd = f'Get-NetIPAddress -InterfaceAlias "{adapter_name}" -AddressFamily IPv4 | Select-Object IPAddress, PrefixLength'
        success, stdout, stderr = self._run_command(cmd, use_powershell=True)

        if success and stdout.strip():
            lines = stdout.strip().split('\n')
            for line in lines[2:]:  # 跳过标题行
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    prefix_length = parts[1]

                    if self._validate_ip(ip):
                        mask = "255.255.255.0"
                        if prefix_length.isdigit():
                            mask = self._prefix_to_subnet_mask(int(prefix_length))

                        ips.append({
                            "ip": ip,
                            "mask": mask,
                            "prefix": prefix_length
                        })

        return ips

    def set_dhcp(self, adapter_name: str) -> bool:
        """
        设置适配器为 DHCP 自动获取 IP

        Args:
            adapter_name: 适配器名称

        Returns:
            操作是否成功
        """
        # 设置 IP 为 DHCP
        cmd = f'netsh interface ip set address "{adapter_name}" dhcp'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"设置 DHCP 失败: {stderr}")

        # 设置 DNS 为 DHCP
        cmd = f'netsh interface ip set dns "{adapter_name}" dhcp'
        success, stdout, stderr = self._run_command(cmd)

        if not success:
            raise NetworkError(f"设置 DNS DHCP 失败: {stderr}")

        return True
