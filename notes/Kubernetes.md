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
kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username=landonr --docker-password=<docker-pass> --docker-email=<docker-email>
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
   - ``` kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username=<username> --docker-password=<password> --docker-email=<email> ```
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

      

## Setps to Deploy Remotely


### 1. Create docker secrets  
- `kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username='<username>' --docker-password='<password>' --docker-email='<email>'` 


### 1. Build Dockerfile into image
- `docker build . -t scanerr/server:latest`
- `docker image push scanerr/server:latest`


### 2. Install nginx ingress controler on cluster
- `kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.1.1/deploy/static/provider/do/deploy.yaml`
- Then add and `A` record for domain that points to new loadbalancer


### 3. Update ingress-nginx-controler "Service file" with domain
- add the below annotation 
- `service.beta.kubernetes.io/do-loadbalancer-hostname: "api.scanerr.io"`


### 4. Spin up Scanerr deployments and services
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/app-configs.yaml`
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/redis-deployment.yaml`
- `kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.11.0/keda-2.11.0.yaml`
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/app-deployment.yaml`
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/celery-deployment.yaml`
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/celery-autoscaler.yaml`


#### 4.a  Spin up YLT deploymemt, service, and autoscaler
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/ylt-deployment.yaml`
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/ylt-autoscaler.yaml`


### 5. Add app Ingress
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/app-ingress.yaml`


### 6. Install cert-manager
- `kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml`


### 7. Add cert issure
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/app-cert-issuer.yaml`
- NOTE: May have to wait a bit before running this one
  

### 8. Update app Ingress for TLS 
- Uncomment the "TLS section" & "cert-manager.io/cluster-issuer annotation" then reapply 
- `kubectl apply -f /Users/landon/Documents/Coding/Scanerr/server/k8s/prod/app-ingress.yaml`


### NOTES:
 - When reprovisioning to new domains and SSL certs ensure all `certificates` & `secrets` are deleted
   - `kubectl delete certificate <cert-name>`
   - `kubectl delete secret <sec-name>` ... may have to do this in the k8s dashboard
 - Restart both celery & app deployments for a config-map change:
   - `kubectl rollout restart deployment app-deployment celery-deployment`



---

## Migration Notes for DB:
1. Go to `models.py` and comment out all new additions
2. Spinup staging env locally to create `00001_initial.py` migration as baseline
3. Spin down staging env
4. Un-comment all new additions in `models.py`
5. Spinup staging env locally again and ensure a new migration file is created in `/migrations`
3. Spin down staging env and merge `dev` branch on github