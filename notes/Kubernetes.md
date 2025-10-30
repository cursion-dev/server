# Kubernetes Guide


Install and run locally on your machine using `Kubernetes`.

> Ensure you have `Docker` and `minikube` installed and running on your machine prior to this step.

&nbsp;


### 1. **Clone the repo**
```shell
$ git clone https://github.com/cursion-dev/server.git
```


### 2. **Export `CURSION_ROOT`**
```shell
echo 'export CURSION_ROOT=<your/path/to/cursion/server>' >> ~/.zshrc  # (or ~/.bash_profile)
```


### 3. Ensure minikube is running
```shell
minikube status 
``` 


### 4. **Update config map**
Prior to running the app, be sure to update `app-configs-example.yaml` with your unique values, and remove the trailing `-example` string from the file.


#### 4.1 Create regcred for Docker Hub 
``` shell
kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username=<your-name> --docker-password=<your-pword> --docker-email=<your-email>
```


### 5. Apply app-configs 
```shell
kubectl apply $CURSION_ROOT/k8s/local/app-configs.yaml 
``` 


### 6. Apply db-deployment
```shell
kubectl apply $CURSION_ROOT/k8s/local/db-deployment.yaml 
``` 


### 7. Apply redis-deployment
```shell
kubectl apply $CURSION_ROOT/k8s/local/redis-deployment.yaml 
```


### 8. Get pod ip of db-deployment
```shell
kubectl get pod -o wide 
```


### 9. Paste db pod IP into app-configs for field "DB_HOST"
```shell
kubectl apply $CURSION_ROOT/k8s/local/app-config.yaml 
``` 


### 10. Apply app-deployment
```shell
kubectl apply $CURSION_ROOT/k8s/local/app-deployment.yaml 
``` 


### 11. Apply celery-deployment
```shell
kubectl apply celery-deployment.yaml
``` 


### 12. Forward Port `8000` to app
```shell
kubectl port-forward service/app-service 8000:8000
```
 
----

&nbsp;

## Update to New Version

> Ensure container version tags are up-to-date in each `.yaml` deployment file.

#### 1. Apply changes 
```shell
kubectl apply -f app-deployment.yaml,celery-deployment.yaml,beat-deployment.yaml
``` 

#### 2. Restart deployments
```shell
kubectl rollout restart deployment app-deployment celery-deployment beat-deployment
```