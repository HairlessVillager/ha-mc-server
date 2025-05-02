docker run -d --privileged rancher/k3s agent --token yourtoken --server https://yourserver:6443 --snapshotter native

docker build -t migrater ./migrater
docker tag migrater ccr.ccs.tencentyun.com/ha-mc-server/migrater:latest
docker push ccr.ccs.tencentyun.com/ha-mc-server/migrater:latest
kubectl apply -f k8s/web-test.yaml
