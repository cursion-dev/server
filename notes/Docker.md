# Docker Guide


Install and run locally on your machine using `Docker`.

> Ensure you have `Docker` and `Docker-desktop` installed and running on your machine prior to begining this guide.

&nbsp;


### 1. **Clone the repo**
```shell
git clone https://github.com/cursion-dev/server.git
```


### 2. **Export `CURSION_ROOT`**
```shell
echo 'export CURSION_ROOT=<your/path/to/cursion/server>' >> ~/.zshrc  # (or ~/.bash_profile)
```


### 3. **Update `.env.local`**
Prior to running the app, be sure to update `.env.local.example` with your unique values, and remove the `.example` extention from the file.


### 4. **Build and Run**
```shell
source ./setup/scripts/local.sh
```
&nbsp;

 
