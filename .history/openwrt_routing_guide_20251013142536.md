
# OpenWrt 跨网段路由配置指南

本文档将指导您如何在 OpenWrt 设备上配置路由，以实现两个不同子网 `192.168.11.0/24` 和 `192.168.13.0/24` 之间的互通。

## 前提条件

1.  您拥有一台已安装 OpenWrt 系统的路由器。
2.  您可以通过 SSH 或 Web 界面 (LuCI) 访问您的 OpenWrt 路由器。
3.  您的路由器至少有两个可用的网络接口（或支持 VLAN），用于连接这两个不同的子网。
4.  本文档中的命令均通过 SSH 连接到 OpenWrt 终端执行。

---

## 配置步骤

我们将使用 OpenWrt 的统一配置接口（UCI）命令来进行配置。这种方法比直接编辑配置文件更安全、更不容易出错。

### 第 1 步：配置网络接口

首先，我们需要为这两个子网创建各自的网络接口。我们假设您使用 `eth0.11` 和 `eth0.13` 这两个 VLAN 接口，如果您的物理接口不同（例如 `eth1`, `eth2`），请相应地修改 `ifname` 选项。

1.  **为 `192.168.11.0/24` 创建接口**

    我们创建一个名为 `lan11` 的新接口，并为其分配静态 IP `192.168.11.1` 作为该网段的网关。

    ```bash
    # 创建新接口 lan11
    uci set network.lan11=interface
    # 设置协议为静态 IP
    uci set network.lan11.proto='static'
    # 分配静态 IP 地址
    uci set network.lan11.ipaddr='192.168.11.1'
    # 设置子网掩码
    uci set network.lan11.netmask='255.255.255.0'
    # 绑定到物理接口 (请根据您的实际情况修改 eth0.11)
    uci set network.lan11.ifname='eth0.11' 
    ```

2.  **为 `192.168.13.0/24` 创建接口**

    同样地，我们创建一个名为 `lan13` 的接口，并为其分配静态 IP `192.168.13.1`。

    ```bash
    # 创建新接口 lan13
    uci set network.lan13=interface
    # 设置协议为静态 IP
    uci set network.lan13.proto='static'
    # 分配静态 IP 地址
    uci set network.lan13.ipaddr='192.168.13.1'
    # 设置子网掩码
    uci set network.lan13.netmask='255.255.255.0'
    # 绑定到物理接口 (请根据您的实际情况修改 eth0.13)
    uci set network.lan13.ifname='eth0.13'
    ```

### 第 2 步：配置防火墙

为了让这两个网络能够互相通信，我们需要在防火墙中进行设置。最安全的方法是为每个网络接口创建一个独立的防火墙区域（Zone），然后设置允许它们之间互相转发流量。

1.  **为 `lan11` 创建防火墙区域**

    ```bash
    # 创建名为 zone11 的新区域
    uci set firewall.zone11=zone
    # 将区域命名为 'lan11_zone'
    uci set firewall.zone11.name='lan11_zone'
    # 将 lan11 接口加入此区域
    uci set firewall.zone11.network='lan11'
    # 设置策略：允许来自该区域的输入、输出和转发
    uci set firewall.zone11.input='ACCEPT'
    uci set firewall.zone11.output='ACCEPT'
    uci set firewall.zone11.forward='ACCEPT'
    ```

2.  **为 `lan13` 创建防火墙区域**

    ```bash
    # 创建名为 zone13 的新区域
    uci set firewall.zone13=zone
    # 将区域命名为 'lan13_zone'
    uci set firewall.zone13.name='lan13_zone'
    # 将 lan13 接口加入此区域
    uci set firewall.zone13.network='lan13'
    # 设置策略：允许来自该区域的输入、输出和转发
    uci set firewall.zone13.input='ACCEPT'
    uci set firewall.zone13.output='ACCEPT'
    uci set firewall.zone13.forward='ACCEPT'
    ```

### 第 3 步：应用配置

在执行完所有 `uci` 命令后，这些更改只是暂存的。我们需要提交更改并重启相关服务来让配置生效。

1.  **提交所有更改**

    ```bash
    uci commit
    ```

2.  **重启网络和防火墙服务**

    ```bash
    /etc/init.d/network restart
    /etc/init.d/firewall restart
    ```

### 第 4 步：配置客户端设备

至此，OpenWrt 路由器端的配置已经完成。最后一步是确保两个子网中的客户端设备使用了正确的网关。

*   对于 `192.168.11.0/24` 网段中的所有设备，其**默认网关**应设置为 `192.168.11.1`。
*   对于 `192.168.13.0/24` 网段中的所有设备，其**默认网关**应设置为 `192.168.13.1`。

您可以在 OpenWrt 上为这两个新接口配置 DHCP 服务，来自动为客户端分配 IP 地址和设置网关，或者在每个客户端设备上手动配置。

---

## 验证

配置完成后，您可以从 `192.168.11.0/24` 网段中的一台设备（例如 `192.168.11.100`）`ping` `192.168.13.0/24` 网段中的另一台设备（例如 `192.168.13.200`），如果能够 `ping` 通，则说明路由配置成功。

```bash
# 在 192.168.11.100 的电脑上执行
ping 192.168.13.200
```

