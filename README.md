# 🎬 短剧制作平台 (Short Drama Studio)

基于火山引擎的一站式 AI 短剧制作平台，支持从主题/剧本到成品视频的全流程自动化制作。
本平台兼容 **Volcengine (国内版)** 和 **BytePlus (国际版)** 双平台。

## ✨ 功能特点

- **多平台支持**:
  - **Volcengine**: 支持火山引擎国内版服务 (Doubao-pro, CV 等)。
  - **BytePlus**: 支持 BytePlus 国际版服务，无缝切换 API Endpoint。
  - **配置灵活**: 支持在同一套系统中为不同项目指定不同的底层服务平台。
- **全流程自动化**: 
  - **剧本创作**: 支持主题一键扩写或上传现有剧本，并提供智能润色优化功能。
  - **角色/场景设计**: 自动提取剧本中的角色与场景，生成详细描述、提示词及定妆照/概念图，确保视觉一致性。
  - **分镜设计**: 将剧本自动拆解为包含画面描述、运镜、旁白的分镜脚本。
  - **提示词工程**: 基于分镜内容，结合角色与场景的视觉参考，自动生成高质量的绘画与视频提示词。
  - **视觉生成**: 
    - **画面生成**: 支持多风格文生图，批量生成分镜画面。
    - **视频生成**: 基于分镜画面进行图生视频，赋予画面动态效果。
  - **后期合成**: 自动将生成的视频片段按顺序无缝拼接，输出最终成品。
- **灵活的输入模式**:
  - **主题创作**: 仅需输入一个创意主题，AI 自动扩写为完整剧本。
  - **剧本模式**: 支持直接粘贴或上传现有剧本文件。
- **可视化编辑**:
  - Web 界面操作，实时预览生成结果。
  - 支持对任意分镜、角色、场景的文案、图片、视频进行单独编辑和重新生成。
- **项目管理**:
  - **高级过滤**: 支持按状态、平台、类型等多维度筛选和搜索项目。
  - **大屏模式**: 沉浸式项目管理体验。
- **资源管理**:
  - 支持集成 TOS (对象存储) 托管生成资源。
  - 支持本地存储与云端存储无缝切换。
  - 自动统计项目 Token 消耗与生成时长。

## 📋 系统要求

- **Python**: 3.10+ (推荐 3.12)
- **数据库**: SQLite (默认) 或 PostgreSQL (推荐生产环境)
- **缓存**: Redis (可选，用于任务队列和缓存)
- **依赖服务**:
  - 火山引擎 (Volcengine) 或 BytePlus 账号及 API 密钥 (Ark, CV, TOS)
  - FFmpeg (必须，用于视频拼接)

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/your-repo/short-drama-studio.git
cd short-drama-studio

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置文件

项目提供了配置文件模板 `config/config.yaml`。
在使用前，**必须**修改该文件，填入您的 API 密钥和配置信息。

**核心配置项**：
- **Ark API Key**: 用于调用大语言模型 (Doubao-pro 等)。
- **Access Key / Secret Key**: 用于调用图像/视频生成服务及 TOS。
- **Platform**: 指定默认平台 (`volcengine` 或 `byteplus`)。
- **Database**: 默认使用 SQLite，可修改 `database.url` 切换至 PostgreSQL。
- **Allow Settings Edit**: 控制是否允许在 Web 界面修改系统配置（`app.allow_settings_edit`，默认 `false`，界面仅只读）。

### 3. 启动服务

```bash
python run.py
```

服务启动后，请在浏览器访问: `http://localhost:8000`

## 🐳 Docker 部署 (推荐)

项目提供了完整的 Docker Compose 配置，包含应用服务、Nginx 反向代理、PostgreSQL 和 Redis。

### 1. 一键启动

确保已安装 Docker 和 Docker Compose。

```bash
# 构建并启动服务 (后台运行)
docker-compose up -d --build

# 查看日志
docker-compose logs -f app
```

### 2. 访问服务

启动成功后，访问: `http://localhost:8080`
- 8080 端口由 Nginx 代理，提供静态资源缓存和 API 转发。
- 后端 API 服务默认运行在容器内部 8000 端口。

### 3. 数据库切换

Docker Compose 默认启动了 Postgres 和 Redis 服务。要让应用使用它们，请修改 `config/config.yaml` 或设置环境变量：

```yaml
# config/config.yaml
database:
  url: "postgresql://user:password@postgres:5432/short_drama"
redis:
  url: "redis://redis:6379/0"
```

## 🛠️ 技术栈

- **后端**: Python 3.12, Aiohttp (Async Web Framework)
- **数据库**: SQLAlchemy (ORM), SQLite / PostgreSQL
- **缓存/队列**: Redis
- **前端**: HTML5, Tailwind CSS, Vanilla JS
- **AI 能力**: 火山引擎 (Volcengine) / BytePlus SDK (Ark, CV)
- **媒体处理**: MoviePy, FFmpeg

## 📄 许可证

MIT License
