# Edit Banana - 懒猫微服迁移项目

> [!NOTE]
> 本目录将 [BIT-DataLab/Edit-Banana](https://github.com/BIT-DataLab/Edit-Banana) 迁移为懒猫微服单容器应用。当前路线基于源码构建，没有复用上游官方镜像。

**Edit Banana** 是一个将静态图像转换为可编辑 DrawIO 文件的 SAM3 + OCR 服务。

## 上游信息

- Upstream repo: [BIT-DataLab/Edit-Banana](https://github.com/BIT-DataLab/Edit-Banana)
- Homepage: [github.com/BIT-DataLab/Edit-Banana](https://github.com/BIT-DataLab/Edit-Banana)
- Latest upstream commit used for initial migration: `126f86c479d6d30e96fac93cf7ab4d94bce68630` (`2026-03-09 00:49:25 +0800`)
- Initial LazyCat package version: `1.0.0`
- License used here: `AGPL-3.0`

> [!IMPORTANT]
> 上游 `README.md` 写的是 Apache 2.0，但仓库根目录 `LICENSE` 实际为 AGPL v3。这里按仓库内许可证文件填写和分发。

## 迁移说明

- 运行形态：单容器 FastAPI 服务
- 容器入口：`http://edit-banana:8000/`
- 懒猫入口：应用首页
- 对外能力：
  - `GET /`：内置上传界面，可直接上传文件并下载结果
  - `GET /docs`：FastAPI Swagger UI
  - `GET /health`：健康检查
  - `POST /convert`：上传图片并直接返回生成的 DrawIO 文件

> 当前首页不是上游线上 demo 的原始 Web UI。上游仓库没有公开那套前端代码，这里补的是面向 LazyCat 安装包的简化上传界面。

## 为什么不是直接复用镜像

上游仓库当前没有提供可直接复用的 Docker 镜像、`Dockerfile` 或 `docker-compose.yml`。因此这里采用源码构建，并在构建阶段：

1. 拉取固定 upstream commit 的源码
2. 安装 Python 依赖与系统依赖
3. 注入懒猫专用启动脚本与改造后的 `server_pa.py`

## 数据目录

- `/lzcapp/var/config` -> `/app/config`
- `/lzcapp/var/models` -> `/app/models`
- `/lzcapp/var/output` -> `/app/output`

建议长期保留：

- `config/`：运行配置
- `models/`：SAM3 权重和 BPE 文件
- `output/`：转换结果

## 首次启动前准备

上游开源仓库不包含模型权重。首次使用前，至少需要把以下文件放入 `/lzcapp/var/models/`：

- `sam3.pt`
- `bpe_simple_vocab_16e6.txt.gz`

默认环境变量已经指向：

- `SAM3_CHECKPOINT_PATH=/app/models/sam3.pt`
- `SAM3_BPE_PATH=/app/models/bpe_simple_vocab_16e6.txt.gz`

如果你放在其他路径，请同步调整 manifest 中的环境变量，或者修改挂载目录里的配置文件。

## 关键环境变量

- `OUTPUT_DIR=/app/output`
- `SAM3_CHECKPOINT_PATH=/app/models/sam3.pt`
- `SAM3_BPE_PATH=/app/models/bpe_simple_vocab_16e6.txt.gz`
- `MULTIMODAL_MODE=api`
- `MULTIMODAL_API_KEY=`
- `MULTIMODAL_BASE_URL=`
- `MULTIMODAL_MODEL=`
- `MULTIMODAL_LOCAL_BASE_URL=http://localhost:11434/v1`
- `MULTIMODAL_LOCAL_API_KEY=ollama`
- `MULTIMODAL_LOCAL_MODEL=`
- `MULTIMODAL_FORCE_VLM_OCR=false`
- `MULTIMODAL_MAX_TOKENS=4000`
- `MULTIMODAL_TIMEOUT=60`
- `MULTIMODAL_CA_CERT_PATH=`
- `MULTIMODAL_PROXY=`

## 使用方式

1. 安装并启动应用
2. 打开懒猫应用首页
3. 在首页上传图片或 PDF
4. 等待转换完成后下载 `.drawio.xml` 文件
5. 需要调试接口时再进入 `Swagger docs`

## 已知限制

- 当前迁移针对上游仓库公开的 FastAPI 服务实现，主要验证的是图片转 DrawIO 路径
- 上游 README 提到的 PDF -> PPTX 和在线 Demo 能力并未在当前开源仓库中完整交付
- 未绑定 GPU 时将退化为 CPU 路径，速度会明显下降
- 若模型文件缺失，`POST /convert` 会返回 503 并提示缺少模型配置

## 自动更新

包含 `.github/workflows/update-image.yml`：

- 每 6 小时检查上游默认分支最新 commit
- 以最新 commit SHA 构建镜像
- 推送到 GHCR
- 复制到 `registry.lazycat.cloud`
- 回写 `lzc-manifest.yml` 和 `Dockerfile`
- 按普通 semver 递增 patch 版本号
- 构建 `.lpk` 并创建 GitHub Release

## 本目录文件

- `lzc-manifest.yml`：懒猫应用定义
- `lzc-build.yml`：构建打包配置
- `Dockerfile`：源码构建镜像
- `docker/entrypoint.sh`：启动前生成运行配置
- `docker/server_pa.py`：懒猫增强版 Web API
- `.github/workflows/update-image.yml`：自动跟踪上游 commit 并发布
