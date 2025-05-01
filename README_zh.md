# 高可用 Minecraft 游戏服务集群

用 K3s 和 SeaweedFS 让你的 Minecraft 服务 99.9% 可用！

传统的 Minecraft 服务只把游戏服务端部署在一台服务器上，一旦这台机器出现故障（例如进程崩溃、网络中断或者硬件损坏等）整个游戏服务就会不可用，玩家需要等待甚至催促服主尽快修复服务；如果硬盘损坏或数据丢失，那么整个存档都会毁于一旦！相对于传统的单体服务，高可用服务把游戏服务分布式部署在多个地区的不同的服务器上，当节点故障时，Kubernetes 会自动把游戏服务迁移到其他机器上，从而避免服务不可用。

为了获取足够多的不同地区的机器（至少 2 台，建议 3 台以上，不同地区的机器越多服务可用时间越长），服主往往需要征集*志愿者*提供机器并部署服务。志愿者往往不是计算机方面的专业人员，同时可能只有一台家用 PC 而不是专业的机柜服务器。为了征集到足够多的志愿者，这个项目1）使用 Docker 和 k3s 来简化安装过程；2）使用 k3s 来降低维护集群产生的额外开销。**[这个章节](#志愿者志愿者)面向志愿者介绍了如何部署服务。**

这个项目主要解决以下两个问题：
1. 节点故障导致游戏服务端进程不可用：通过 K3s 自动迁移游戏服务进程。
2. 节点硬盘损坏导致存档数据损坏：通过 SeaweedFS 分布式地存储游戏存档文件。

下面分别从服主和志愿者两个视角介绍如何部署服务。

## 服主

服主是游戏服务的管理员，不仅拥有游戏本身的控制权（例如游戏内权限、游戏文件修改等），还拥有 k3s server 节点和 k3s server token 的完全控制权。

### 服务器要求

服主需要拥有一台有公网 IP 的服务器。最好的方式是从云服务厂商购买服务器，他们往往会给服务器附赠一个公网 IP。如果服主是计算机专业人士，也可以用内网穿透等方式给家用 PC 配置一个公网 IP。

服务器的操作系统推荐使用 Linux，当然 Windows 也是可以接受的。另外像[腾讯云](https://cloud.tencent.com/document/product/1207/72665)等厂商会提供预装 K3s 的操作系统镜像，会免去部署 K3s 的步骤。

### 部署 K3s

K3s 的部署有两种方式：
- 裸金属部署：适用于 Linux 机器。
- 容器化部署：适用于任何可以安装 Docker 的机器。

#### 裸金属部署

裸金属部署方式会把 K3s 直接部署在服务器上，而不依赖其他中间件。这要求服务器的操作系统必须是 Linux 系统。

参考 [K3s 的文档](https://docs.k3s.io/zh/quick-start#%E5%AE%89%E8%A3%85%E8%84%9A%E6%9C%AC)运行以下命令来部署 K3s：
```
curl -sfL https://rancher-mirror.rancher.cn/k3s/k3s-install.sh | INSTALL_K3S_MIRROR=cn sh -
```

等待安装完毕后参考[这篇文档](https://docs.k3s.io/zh/networking/distributed-multicloud#embedded-k3s-multicloud-solution)编辑 `/etc/systemd/system/k3s.service` 文件，在末尾的 `ExecStart` 配置项中像下面这样追加`--node-external-ip`参数（其中`xx.xx.xx.xx`是机器的公网 IP 地址）：
```
ExecStart=/usr/local/bin/k3s \
    server \
    --node-external-ip xx.xx.xx.xx \

```

然后使用以下命令更新配置：
```
systemctl daemon-reload
systemctl restart k3s
```

#### 容器化部署

容器化部署方式利用 Docker 作为虚拟化中间件，并使用 K3s 的容器镜像来部署容器。

首先需要安装 Docker，参考官方文档：https://docs.docker.com/get-started/get-docker/

然后使用以下命令启动一个 K3s 容器作为 K3s Server 节点（其中`xx.xx.xx.xx`是机器的公网 IP 地址）：
```
docker run -d --privileged -p 6443:6443 -p 10250:10250 rancher/k3s server --node-external-ip xx.xx.xx.xx
```

确保你的防火墙放行了 6443 和 10250 端口的入流量。

### 获取 token

为了安全性，志愿者的机器在加入集群时需要验证 token。这里的 token 可以由服主通过以下命令生成：
```
k3s token create
```

这个命令会输出一个 token，有效期为 24 小时。可以通过`--ttl`调整有效时间。更多信息参考：https://docs.k3s.io/zh/cli/token

### 部署 SeaweedFS 服务

...

### 部署 Minecraft 游戏服务

...

## 志愿者

志愿者提供了集群中大部分的机器。节点越多，服务可用性越高。从这个角度看，志愿者是整个项目中最有贡献的一群人。

考虑到志愿者往往不具备专业设备和专业知识，所以这里仅考虑在 Windows 系统上使用 Docker 部署服务：

首先需要安装 Docker，参考官方文档：https://docs.docker.com/get-started/get-docker/

然后使用以下命令启动一个 K3s 容器作为 K3s Agent 节点（其中 `myserver` 需要替换成服主机器的域名或公网 IP，`mytoken` 需要替换成服主提供的 token，`mynodename` 可以换成你的游戏 ID）：
```
docker run -d --privileged rancher/k3s agent --token mytoken --server https://myserver:6443 --snapshotter native --node-name mynodename
```

然后等待服主确认你的机器加入了集群。