English | [中文简体](./README_zh.md)

# High Availability Minecraft Game Service Cluster

Achieve 99.9% availability for your Minecraft services with K3s and SeaweedFS!

Traditional Minecraft services deploy the game server on a single machine. If this machine fails (e.g., process crashes, network interruptions, or hardware damage), the entire game service becomes unavailable, and players have to wait, sometimes even urging the server owner to fix it quickly. If the hard drive fails or data is lost, the entire game save can be destroyed! Compared to traditional monolithic services, high availability services distribute the game service across multiple servers in different regions. When a node fails, Kubernetes automatically migrates the game service to other machines, preventing service downtime.

To obtain a sufficient number of machines in different regions (at least 2, but it is recommended to have more than 3; the more machines in different regions, the longer the service availability), server owners often need to recruit *volunteers* to provide machines and deploy services. Volunteers are usually not professionals in computer science and may only have a home PC instead of a professional rack server. To attract enough volunteers, this project 1) uses Docker and K3s to simplify the installation process; 2) leverages K3s to reduce the additional overhead of maintaining the cluster. **[This section](#Volunteers) is aimed at volunteers and introduces how to deploy the service.**

This project primarily addresses the following two issues:
1. Node failure causing the game server process to be unavailable: Automatically migrate the game service process with K3s.
2. Node hard drive failure leading to corrupted save data: Distribute game save files using SeaweedFS.

Below, we introduce how to deploy the service from the perspectives of the server owner and volunteers.

## Server Owner

The server owner is the administrator of the game service, having control over the game itself (e.g., in-game permissions, game file modifications) as well as full control over the K3s server nodes and K3s server tokens.

### Server Requirements

The server owner needs a server with a public IP address. The best way is to purchase a server from a cloud service provider, as they usually provide a public IP with the server. If the server owner is a computer professional, they can also use methods like network penetration to configure a public IP for a home PC.

The server's operating system is recommended to be Linux, although Windows is also acceptable. Additionally, vendors like [Tencent Cloud](https://cloud.tencent.com/document/product/1207/72665) offer operating system images pre-installed with K3s, which can save the step of deploying K3s.

### Deploying K3s

There are two ways to deploy K3s:
- Bare-metal deployment: Suitable for Linux machines.
- Containerized deployment: Suitable for any machine that can install Docker.

#### Bare-metal Deployment

Bare-metal deployment installs K3s directly on the server without relying on any middleware. This requires the server's operating system to be Linux.

Refer to the [K3s documentation](https://docs.k3s.io/zh/quick-start#%E5%AE%89%E8%A3%85%E8%84%9A%E6%9C%AC) and run the following command to deploy K3s:
```
curl -sfL https://rancher-mirror.rancher.cn/k3s/k3s-install.sh | INSTALL_K3S_MIRROR=cn sh -
```

After the installation is complete, refer to [this document](https://docs.k3s.io/zh/networking/distributed-multicloud#embedded-k3s-multicloud-solution) to edit the `/etc/systemd/system/k3s.service` file and append the `--node-external-ip` parameter (where `xx.xx.xx.xx` is the public IP address of the machine) to the `ExecStart` configuration item at the end:
```
ExecStart=/usr/local/bin/k3s \
    server \
    --node-external-ip xx.xx.xx.xx \
```

Then use the following commands to update the configuration:
```
systemctl daemon-reload
systemctl restart k3s
```

#### Containerized Deployment

Containerized deployment utilizes Docker as a virtualization middleware and uses the K3s container image to deploy the container.

First, you need to install Docker. Refer to the official documentation: [Docker Installation](https://docs.docker.com/get-started/get-docker/)

Then, use the following command to start a K3s container as the K3s Server node (where `xx.xx.xx.xx` is the public IP address of the machine):
```
docker run -d --privileged -p 6443:6443 -p 10250:10250 rancher/k3s server --node-external-ip xx.xx.xx.xx
```

Make sure your firewall allows inbound traffic on ports 6443 and 10250.

#### Obtaining the Token

For security reasons, volunteers' machines need to verify a token when joining the cluster. The server owner can generate a token using the following command:
```
k3s token create
```

This command outputs a token with a validity period of 24 hours. You can adjust the validity period using the `--ttl` option. For more information, refer to the [K3s Token Documentation](https://docs.k3s.io/zh/cli/token).

### Building and Uploading the Image

This project does not upload images to DockerHub or similar platforms, so you need to manually build and upload the images to the repository.

#### Building the Spigot Image

This section uses Spigot for Minecraft version 1.21.4 as an example, which requires Java version 24.

If you wish to install a different version of Spigot, please note to modify the Java version number and Spigot version number in the relevant commands. The specific correspondence between Minecraft and Java versions can be found in the [Spigot documentation](https://www.spigotmc.org/wiki/buildtools/#prerequisites).

Spigot is a third-party Minecraft JE Server, and its main body is a `spigot-ver.jar` file. Here, we use the BuildTool.jar provided by Spigot to compile this file.

To unify the environment and prevent contamination of the local environment, we use a Docker image to set up the compilation environment and compile it.

Run the following command in the project root directory to start and enter an Azul Platform Core container:
```
docker run -it --name spigot-build azul/zulu-openjdk:24-latest
```

Inside the container, execute the following commands in sequence:
```
apt-get update
apt-get install -y gnupg ca-certificates curl git
curl -o BuildTools.jar https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/artifact/target/BuildTools.jar
java -jar BuildTools.jar --rev 1.21.4
```

After successful compilation, use the following command to copy the file to the `./spigot` directory:
```
docker cp spigot-build:/spigot-1.21.4.jar ./spigot
```

Once the copy is successful, use the following command to delete the container:
```
docker rm spigot-build
```

Run the following command in the project root directory to build the Spigot image:
```
docker build -t mc-server --build-arg BASE_IMAGE=azul/zulu-openjdk:24-latest --build-arg SPIGOT_FILE=spigot-1.21.4.jar --build-arg EULA=true ./spigot
```

#### Building the Saving-agent Image

Run the following command in the project root directory:
```
docker build -t saving-agent:latest ./saving-agent
```

#### Uploading the Image

We need to upload the image to an image service, and there are two options:
1. Upload to DockerHub or other hosting services;
2. Deploy your own image service.

Taking Tencent Cloud's image hosting service as an example, we can refer to [Tencent Cloud's documentation](https://cloud.tencent.com/document/product/1141/63910) to activate the service and upload the image. For example, if you want to upload the `saving-agent` image you just built:
```
docker tag saving-agent:latest ccr.ccs.tencentyun.com/ha-mc-server/saving-agent:latest
docker push ccr.ccs.tencentyun.com/ha-mc-server/saving-agent:latest
```
The same applies to other images.

After successful upload, we need to refer to the [Kubernetes documentation](https://kubernetes.io/zh-cn/docs/tasks/configure-pod-container/pull-image-private-registry/#create-a-secret-by-providing-credentials-on-the-command-line) to create a Secret to access the private image.

### Deploying the Service

#### Labeling Nodes

Log in to the K3s Server node and use the following command to confirm that K3s is running and the number of nodes meets expectations:
```
kubectl get nodes
```

If some nodes in your cluster have insufficient CPU performance and memory size to support the Minecraft Server computing service, you can label these nodes with `limited-computing` to help K8s better allocate resources to the nodes:
```
kubectl label node <your-node-name> limited-com