# 使用Python 3.10的官方镜像
FROM python:3.12

# 将当前目录下的文件复制到镜像中的 /app 目录
COPY . /app

# 设置工作目录
WORKDIR /app

# 安装依赖包
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 指定入口命令
# CMD ["python", "src/cli.py"]