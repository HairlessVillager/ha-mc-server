docker run -d --privileged rancher/k3s agent --token yourtoken --server https://yourserver:6443 --snapshotter native

docker build -t migrater ./migrater
docker tag migrater ccr.ccs.tencentyun.com/ha-mc-server/migrater:latest
docker push ccr.ccs.tencentyun.com/ha-mc-server/migrater:latest
kubectl apply -f k8s/web-test.yaml

java -Xms2G -Xmx8G -XX:+UseG1GC -Dfile.encoding=UTF-8 -jar spigot-1.21.4.jar --nogui --noconsole -W ./save

minikube start --base-image=ccr.ccs.tencentyun.com/kicbase-mirror/kicbase:v0.0.46 --cpus='no-limit' --ha=true --memory='no-limit' --nodes=3
