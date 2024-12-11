## Build & Push Instructions
1. Ensure you are in the root of `nginx`
2. Build Dockerfile `docker build --platform linux/amd64 . -t 'cursiondev/nginx:latest'`
3. Push to dock Dockerfile `docker push cursiondev/nginx:latest`