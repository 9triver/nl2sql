# nl2sql

# 环境配置

## llm api

将api key写入环境变量中, 例如:

```bash
export OPENAI_API_KEY=sk-Y************************Mx83q
export GEMINI_API_KEY=AIza************************wYr2c
export CHATGLM_API_KEY=111a***********************114pG
```

> 在config.yaml的model中配置参数: 
> - **api key的环境变量(api_key)** 
> - **模型转发地址的环境变量(base_url)**
> - **模型名称的环境变量(model_name)** .

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


## neo4j数据库配置

> 在config.yaml的database中配置即可



# 启动命令

## 数据库嵌入
> 给数据库中所有节点添加嵌入
```bash
python src/embed.py
```

## 命令行
```bash
python src/cli.py
```

## Gradio GUI
```bash
python src/gui.py
```
会启动一个gradio界面:
 - http://localhost:7861
 - http://0.0.0.0:7861

## Fastapi
```bash
python src/web.py
```


# Docker
## 镜像构建
```bash
docker-compose build
```

## 运行容器
```bash
docker-compose up -d
```

## 进入容器并运行
```bash
docker-compose exec nl2cypher /bin/bash

python src/cli.py
```

## 停止容器
```bash
docker-compose stop nl2cypher
```
