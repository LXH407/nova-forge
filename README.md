# NOVA FORGE

**Hyperdrive Content Forge** —— 全自动大模型 / 应用 / 游戏 / 工具下载器（Windows 单文件 EXE，无服务器架构）。

白色微软商店式界面，把模型、应用、游戏、工具像应用商店一样陈列：图标 + 介绍 + 标签 + 体积 + 积分价格，点击即全自动下载。

## 特性

- **全自动下载**：解析 HuggingFace / ModelScope 仓库文件清单，一键全量下载
- **智能测速 + 自动切镜像**：实时显示下载速度；速度持续过低自动切换国内镜像源（hf-mirror.com）并断点续传
- **网盘分发**：百度网盘 / 夸克 / 阿里云盘等分享链接，一键打开 / 复制
- **积分制**：积分卡兑换积分，1 积分下载 1 个商品；后端可随时修改商品积分价格
- **永久会员**：会员卡输入后自动绑定本机机器码，开通永久会员（下载全部内容免积分）
- **软件内支付**：钱包页展示微信 / 支付宝收款码，支付后登记单号由管理员发放
- **卡密系统**：离线 RSA 验签，无需联网授权；后端可发卡、封禁、解封
- **无服务器更新**：商城清单 / 封禁名单 / 版本更新全部走 GitHub（raw + Releases），无需服务器

## 目录结构

```
app/                客户端核心（配置/清单/商城/授权/下载引擎/更新）
cli/                控制台全自动下载器
backend/            本地管理台（FastAPI，端口 8642）
tools/              打包 / 密钥生成 / 上传向导 / 自测脚本
update/             自更新脚本
assets/             图标 / 公钥
manifest.json       商城清单（单一真源）
banlist.json        封禁名单
.github/workflows/  GitHub Actions 自动构建 Release
```

## 构建 EXE

```bash
pip install -r requirements.txt pyinstaller
python tools/gen_icons.py
pyinstaller --noconfirm NovaForge.spec
# 产物: dist/NovaForge.exe
```

推 `vX.Y.Z` 标签到 GitHub 会自动触发 Actions 构建并发布 Release（见 `.github/workflows/build.yml`）。

## 后端管理台

```bash
cd backend
python server.py
# 打开 http://127.0.0.1:8642 ，默认密码 novaforge-admin（登录后请修改）
```

管理台可：上传内容（含图标 / 介绍 / 积分价格）、签发会员卡 / 积分卡、封禁 / 解封、上传支付收款码、发布版本。

## 无服务器同步说明

- 商城清单：客户端拉取 `raw.githubusercontent.com/{owner}/{repo}/main/manifest.json`
- 封禁名单：同上 `banlist.json`
- 版本更新：`api.github.com/repos/{owner}/{repo}/releases/latest`

## 安全

- 卡密私钥 `keys/private.pem` 仅保存在管理员本地，**切勿上传 GitHub**（已在 .gitignore 排除）
- 后端管理员密码、GitHub PAT 等仅存于本地 `backend/data/`（不入库）
