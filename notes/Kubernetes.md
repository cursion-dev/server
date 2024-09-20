# Notes on k8s deployments
---
<br>


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


<div style="margin-top: 8rem; margin-bottom: 8rem"></div>


# Setps to Deploy localy
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
  

---

<div style="margin-top: 8rem; margin-bottom: 8rem"></div>

# Setps to Deploy Remotely

> Ensure you are in the `/server` root directory 

### 1. Create docker secrets  
``` shell
kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username='<username>' --docker-password='<password>' --docker-email='<email>'
```


### 1. Build Dockerfile into image
``` shell
docker build . -t scanerr/server:latest
docker image push scanerr/server:latest
```


### 2. Install nginx ingress controler on cluster
``` shell
kubectl apply -f ./k8s/prod/app-loadbalancer.yaml
```
- Then add and `A` record for domain that points to new loadbalancer
  - ref -> https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.1.1/deploy/static/provider/do/deploy.yaml


### 3. Update ingress-nginx-controler "Service file" with domain - if not already updated.
- add the below annotation 
``` shell
service.beta.kubernetes.io/do-loadbalancer-hostname: "api.scanerr.io"
```


### 4. Spin up Scanerr deployments and services
``` shell
kubectl apply -f ./k8s/prod/app-configs.yaml
kubectl apply -f ./k8s/prod/redis-deployment.yaml
kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.11.0/keda-2.11.0.yaml
kubectl apply -f ./k8s/prod/app-deployment.yaml
kubectl apply -f ./k8s/prod/celery-deployment.yaml
kubectl apply -f ./k8s/prod/celery-autoscaler.yaml
kubectl apply -f ./k8s/prod/beat-deployment.yaml
```


#### 4.a  Spin up YLT deploymemt, service, and autoscaler
``` shell
kubectl apply -f ./k8s/prod/ylt-deployment.yaml
kubectl apply -f ./k8s/prod/ylt-autoscaler.yaml # DEPRECIATE
```


### 5. Add app Ingress
``` shell
kubectl apply -f ./k8s/prod/app-ingress.yaml
```


### 6. Install cert-manager
``` shell
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml
```


### 7. Add cert issure
``` shell
kubectl apply -f ./k8s/prod/app-cert-issuer.yaml
```
> NOTE: May have to wait a bit before running this one
  

### 8. Update app Ingress for TLS 
- Uncomment the "TLS section" & "cert-manager.io/cluster-issuer annotation" then reapply 
``` shell
kubectl apply -f ./k8s/prod/app-ingress.yaml
```


### 9. Install kubeip dameon & service
``` shell
kubectl apply -f ./k8s/prod/kubeip-service.yaml
kubectl apply -f ./k8s/prod/kubeip-daemon.yaml
```


### NOTES:
 - When reprovisioning to new domains and SSL certs ensure all `certificates` & `secrets` are deleted
   - `kubectl delete certificate <cert-name>`
   - `kubectl delete secret <sec-name>` ... may have to do this in the k8s dashboard
 - Restart celery, beat, & app deployments for a config-map change:
   - `kubectl rollout restart deployment app-deployment celery-deployment`
 - Check status of deployment rollout
   - `kubectl rollout status deployment/app-deployment`
 - Get Current IPs for pods:
   - `kubectl exec <container-id> -- curl -s http://checkip.dyndns.org/ | sed 's/[a-zA-Z<>/ :]//g'`
 - Force delete pods that are stuck in `Terminating`:
   - `for p in $(kubectl get pods | grep Terminating | awk '{print $1}'); do kubectl delete pod $p --grace-period=0 --force;done`
 - Stream Logs for all celery-deployments:
   - `kubectl logs -f --all-containers deployment/celery-deployment`
   - `kubectl logs -f --selector=app=celery-deployment --all-containers --max-log-requests=7`



---

<div style="margin-top: 8rem; margin-bottom: 8rem"></div>

# Migration Notes for DB:
1. Go to `models.py` and comment out all new additions
2. Spinup staging env locally to create `00001_initial.py` migration as baseline
   - `docker compose -f docker-compose.stage.yml up --build`
3. Spin down staging env
   - `docker compose -f docker-compose.stage.yml down`
4. Un-comment all new additions in `models.py`
5. Spinup staging env locally again and ensure a new migration file is created in `/migrations`
   - `docker compose -f docker-compose.stage.yml up --build`
6. Spin down staging env
   - `docker compose -f docker-compose.stage.yml down`
7. Merge `dev` branch on github using a pull request