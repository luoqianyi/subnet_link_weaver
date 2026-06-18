# Subnet Link Weaver

局域网多 IP 配置工具 - 双 IP 挂载方案

## 功能特性

- **新手模式**：一键配置双 IP 挂载，傻瓜式操作
- **进阶模式**：手动配置和 IP 管理，灵活控制
- **自动检测**：自动检测网络适配器和 IP 配置
- **IP 管理**：支持添加、删除、修改额外 IP
- **还原功能**：关闭时自动保存，打开时恢复
- **Loading 界面**：启动时显示加载动画

## 使用场景

两台电脑通过手机热点上网，同时挂载一个固定的局域网 IP（如 192.168.88.X），实现：
- 两台电脑都能正常上网
- 通过新挂载的 IP 互相通信
- 无需改变网络环境

## 快速开始

### 下载

从 [Releases](https://github.com/luoqianyi/subnet_link_weaver/releases) 下载最新版本

### 使用步骤

1. 连接手机热点
2. 运行 `SubnetLinkWeaver.exe`
3. 输入想要挂载的局域网 IP（如 `192.168.88.26`）
4. 点击「一键配置」
5. 在另一台电脑上也运行程序，配置对应的 IP（如 `192.168.88.197`）
6. 测试 ping 连通性

## 工作原理

### 双 IP 挂载方案

1. **固定当前热点 IP**：将 DHCP 动态 IP 转为静态 IP
2. **挂载新的局域网 IP**：在同一网卡上添加额外的 IP 地址
3. **关闭防火墙**：否则会丢弃非原生网段的数据包
4. **测试连通性**：验证两台电脑是否能互相通信

### 为什么需要关闭防火墙？

Windows 防火墙会丢弃非原生网段（如 .88.X）的数据包，必须关闭防火墙才能让两台电脑通过新 IP 互相通信。

## 界面预览

### 新手模式
- 只需输入 IP 地址，一键完成配置
- 自动检测网络适配器
- 自动关闭防火墙

### 进阶模式
- 手动选择适配器
- 自定义子网掩码、网关、DNS
- 防火墙详细管理
- 连通性测试工具

## 开发说明

### 环境要求

- Python 3.10+
- Windows 10/11

### 安装依赖

```bash
uv pip install -r requirements.txt
```

### 运行程序

```bash
uv run python src/main.py
```

### 打包为 exe

```bash
uv run python build.py
```

## 项目结构

```
subnet_link_weaver/
├── src/
│   ├── main.py              # 入口点
│   ├── core/                # 核心逻辑
│   │   ├── network.py       # 网络管理
│   │   ├── firewall.py      # 防火墙管理
│   │   └── ping.py          # 连通性测试
│   ├── gui/                 # GUI 界面
│   │   ├── main_window.py   # 主窗口
│   │   ├── simple_panel.py  # 新手模式
│   │   ├── network_panel.py # 进阶模式
│   │   └── loading_window.py # 加载窗口
│   └── utils/               # 工具函数
│       ├── config.py        # 配置管理
│       └── logger.py        # 日志记录
├── assets/
│   └── icon.svg             # 应用图标
├── dist/                    # 打包输出
└── README.md                # 本文件
```

## 许可证

MIT License
