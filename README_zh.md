# 高可用 Minecraft 游戏服务集群

用 K3s 和 SeaweedFS 让你的 Minecraft 服务 99.9% 可用！

传统的 Minecraft 服务只把游戏服务端部署在一台服务器上，一旦这台机器出现故障（例如进程崩溃、网络中断或者硬件损坏等）整个游戏服务就会不可用，玩家需要等待甚至催促服主尽快修复服务；如果硬盘损坏或数据丢失，那么整个存档都会毁于一旦！相对于传统的单体服务，高可用服务把游戏服务分布式部署在多个地区的不同的服务器上，当节点故障时，Kubernetes 会自动把游戏服务迁移到其他机器上，从而避免服务不可用。

为了获取足够多的不同地区的机器（至少 2 台，建议 3 台以上，不同地区的机器越多服务可用时间越长），服主往往需要征集*志愿者*提供机器并部署服务。志愿者往往不是计算机方面的专业人员，同时可能只有一台家用 PC 而不是专业的机柜服务器。为了征集到足够多的志愿者，这个项目1）使用 Docker 和 k3s 来简化安装过程；2）使用 k3s 来降低维护集群产生的额外开销。**[这个章节](#志愿者)面向志愿者介绍了如何部署服务。**

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

#### 获取 token

为了安全性，志愿者的机器在加入集群时需要验证 token。这里的 token 可以由服主通过以下命令生成：
```
k3s token create
```

这个命令会输出一个 token，有效期为 24 小时。可以通过`--ttl`调整有效时间。更多信息参考：https://docs.k3s.io/zh/cli/token

### 构建并上传镜像

这个项目没有上传镜像到 DockerHub 或类似的平台，所以需要手动构建并上传镜像到仓库。

#### 构建 Spigot 镜像

这一节以 Minecraft 1.21.4 版本下的 Spigot 为例，其要求的 Java 版本为 24。

如果你希望安装其他版本的 Spigot，请注意修改相关命令中的 Java 版本号和 Spigot 版本号。具体的 Minecraft 和 Java 版本的对应关系可以参考 [Spigot 的文档](https://www.spigotmc.org/wiki/buildtools/#prerequisites)。

##### 编译 sgipot.jar

Spigot 是第三方 Minecraft JE Server，其本体为一个 `spigot-ver.jar` 文件。这里我们使用 Spigot 提供的 BuildTool.jar 来编译得到这个文件。

为了统一环境并且防止污染本地环境，这里使用 Docker 镜像来搭建编译环境并编译。

在项目根目录运行以下命令启动并进入一个 Azul Platform Core 容器：
```
docker run -it --name spigot-build azul/zulu-openjdk:24-latest
```

在容器内依次执行以下命令：
```
apt-get update
apt-get install -y gnupg ca-certificates curl git
curl -o BuildTools.jar https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/artifact/target/BuildTools.jar
java -jar BuildTools.jar --rev 1.21.4
```

编译成功后，使用以下命令拷贝文件到 ./spigot 目录下：
```
docker cp spigot-build:/spigot-1.21.4.jar ./spigot
```

提示拷贝成功之后，使用以下命令删除容器：
```
docker rm spigot-build
```

在项目根目录下运行以下命令来构建 Spigot镜像：
```
docker build -t mc-server --build-arg BASE_IMAGE=azul/zulu-openjdk:24-latest --build-arg SPIGOT_FILE=spigot-1.21.4.jar --build-arg EULA=true ./spigot 
```

#### 构建 Saving-agent 镜像

在项目根目录运行以下命令：
```
docker build -t saving-agent:latest ./saving-agent
```

#### 上传镜像

我们需要把镜像上传到镜像服务上，这里有 2 种选择：
1）上传到 DockerHub 或其他托管服务上；
2）自行部署镜像服务。

以腾讯云的镜像托管服务为例，我们可以参考[腾讯云的文档](https://cloud.tencent.com/document/product/1141/63910)来开通服务并上传镜像。例如你希望上传你刚刚构建的`saving-agent`镜像：
```
docker tag saving-agent:latest ccr.ccs.tencentyun.com/ha-mc-server/saving-agent:latest
docker push ccr.ccs.tencentyun.com/ha-mc-server/saving-agent:latest
```
其他镜像同理。

上传成功后我们接下来需要参考 [Kubernetes 的文档](https://kubernetes.io/zh-cn/docs/tasks/configure-pod-container/pull-image-private-registry/#create-a-secret-by-providing-credentials-on-the-command-line)创建 Secret 来获取私有镜像。

### 部署服务

登录 K3s Server 节点，使用以下命令确认 K3s 正在运行且节点数量符合预期：
```
kubectl get nodes
```

在节点的合适位置克隆本仓库，在仓库根目录下运行以下命令来启动 SeaweedFS 服务：
```
kubectl apply -f ./k8s/seaweedfs/master.yaml
kubectl apply -f ./k8s/seaweedfs/volume.yaml
kubectl apply -f ./k8s/seaweedfs/filer.yaml
```

在启动游戏之前，你可以通过以下方式上传你的初始存档（如果有的话）：
1. 首先启动一个命令行窗口，运行`kubectl port-forward svc/seaweedfs-filer 8888:8888`，把 SeaweedFS Filer 服务暴露到宿主机上；
2. 保持上面的命令运行，然后启动另外一个窗口，在项目的根目录运行`uv run saving-agent/main.py push --local-path <your-save-path> --remote-path /mc-save --filer-url http://localhost:8888`

运行下面的命令启动游戏服务：
```
kubectl apply -f ./k8s/mc-server.yaml
```

然后使用以下命令暴露端口：
```
kubectl port-forward svc/mc-server 25565:25565
```

最后在你的 PC 上启动客户端，加入 xx.xx.xx.xx:25565 服务即可进入游玩。

## 志愿者

志愿者提供了集群中大部分的机器。节点越多，服务可用性越高。从这个角度看，志愿者是整个项目中最有贡献的一群人。

考虑到志愿者往往不具备专业设备和专业知识，所以这里仅考虑在 Windows 系统上使用 Docker 部署服务：

首先需要安装 Docker，参考官方文档：https://docs.docker.com/get-started/get-docker/

然后使用以下命令启动一个 K3s 容器作为 K3s Agent 节点（其中 `myserver` 需要替换成服主机器的域名或公网 IP，`mytoken` 需要替换成服主提供的 token，`mynodename` 可以换成你的游戏 ID）：
```
docker run -d --privileged rancher/k3s agent --token mytoken --server https://myserver:6443 --snapshotter native --node-name mynodename
```

然后等待服主确认你的机器加入了集群。