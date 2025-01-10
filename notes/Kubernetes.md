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


### 1. Ensure minikube is running
```shell
minikube status 
``` 


### 2. **Update config map**
Prior to running the app, be sure to update `app-configs-example.yaml` with your unique values, and remove the trailing `-example` string from the file.


### 3. Apply app-configs 
```shell
kubectl apply $CURSION_ROOT/k8s/local/app-configs.yaml 
``` 


### 4. Apply db-deployment
```shell
kubectl apply $CURSION_ROOT/k8s/local/db-deployment.yaml 
``` 


### 5. Apply redis-deployment
```shell
kubectl apply $CURSION_ROOT/k8s/local/redis-deployment.yaml 
```


### 6. Get pod ip of db-deployment
```shell
kubectl get pod -o wide 
```


### 7. Paste db pod IP into app-configs for field "DB_HOST"
```shell
kubectl apply $CURSION_ROOT/k8s/local/app-config.yaml 
``` 


### 8. Apply app-deployment
```shell
kubectl apply $CURSION_ROOT/k8s/local/app-deployment.yaml 
``` 


### 9. Apply celery-deployment
```shell
kubectl apply celery-deployment.yaml
``` 


### 10. Forward Port `8000` to app
```shell
kubectl port-forward service/app-service 8000:8000
```
  
