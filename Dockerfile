# 使用 Python 3.10 Slim 版本作为基础镜像
FROM python:3.12-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    WEB_SERVER_HOST=0.0.0.0

# 安装系统依赖
# ffmpeg: 视频处理 (moviepy 需要)
# libsm6, libxext6: OpenCV 依赖 (虽然主要用 Pillow，但 moviepy 可能间接需要)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app/short_drama_studio

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "run.py"]
