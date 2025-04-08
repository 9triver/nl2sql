# nl2sql

## qdrant部署

1. 从Dockerhub下载最新的Qdrant镜像(仅需执行一次)：

```bash
docker pull qdrant/qdrant 
```

2. 从镜像创建一个容器(仅需执行一次):

```bash
docker create --name qdrant_storage -p 6333:6333 -p 6334:6334 -v "$(pwd)/qdrant_storage:/qdrant/storage:z" qdrant/qdrant
```

> - **--name qdrant_storage**: 指定容器名称
> - **-p 6333:6333 -p 6334:6334**: 指定端口
> - **-v "$(pwd)/qdrant_storage:/qdrant/storage:z"**: 指定挂载点在当前工作目录下的./qdrant_storage/ 下
> - **qdrant/qdrant**: 镜像名称

3. 容器的启动和停止

用如下命令启动/停止qdrant容器：

```bash
docker start qdrant_storage
docker stop qdrant_storage
```

> 每次启动之前需先保证qdrant容器正在运行.


## 启动命令

### 命令行
```bash
python src/cli.py
```

### Gradio GUI
```bash
python src/gui.py
```
会启动一个gradio界面:
 - http://localhost:7861
 - http://0.0.0.0:7861

### Fastapi
```bash
python src/web.py
```