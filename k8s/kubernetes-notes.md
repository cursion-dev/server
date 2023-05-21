### Create k8s files in yaml (kompose)
```shell
kompose convert -f docker-compose.yml -o ./k8s
```

### Build k8s 
```shell
kubectl apply -f ./k8s/k8s-local.yaml
```

### Delete k8s 
```shell
kubectl delete -f ./k8s/k8s-local.yaml
```

### List containers 
```shell
kubectl get pod
```

### List pods with IPs
```shell
kubectl get pod -o wide
```

### To get all creation events for debugging:
```shell
kubectl get events --sort-by=.metadata.creationTimestamp
```

### SSH into container:
```shell
kubectl exec -it celery-849f76858b-bvmqg -- /bin/sh
```

### Creating secrets for docker:
```shell
kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username=landonr --docker-password=Ljr500103! --docker-email=l.rodden52@gmail.com
```

#### - Then add this to both celery and app containers:
```yaml
spec:
  imagePullSecrets:
    - name: regcred
```

### Start and Stop minikube
```shell
minikube start
minikube stop
```

### Port Forwarding for app
```shell
kubectl port-forward service/app-service 8000:8000
```



## Setps to Deploy localy
1. ensure minikube is running
   - ``` minikube status ``` 
2. create secrets for app image pull from docker
   - ``` kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username=landonr --docker-password=Ljr500103! --docker-email=l.rodden52@gmail.com ```
3. build db-configs-configs 
   - ``` kubectl apply db-configs.yaml ``` 
4. build db-deployment
   - ``` kubectl apply db-deployment.yaml ``` 
5. build redis-deployment
6. get pod ip of db-deployment
   - ``` kubectl get pod  --template '{{.status.podIP}}' ```
   - or ``` kubectl get pod -o wide ```
7. copy ip and paste into app-configs-configs for field "DB_HOST"
8. build app-configs
   - ``` kubectl apply app-config.yaml ``` 
9.  build app-deployment
   - ``` kubectl apply db-deployment.yaml ``` 
10. build celery-deployment
    - ``` kubectl apply db-deployment.yaml ``` 
11. port forwarding to app deployment
   -  ``` kubectl port-forward service/app-service 8000:8000 ```

      