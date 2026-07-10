<a name="readme-top"></a>

<div align="center">

# MindsHub

**开源模型为你完成任务的统一工作空间。**

_让 AI 真正干活。随时切换模型——你搭建的一切都保留下来。_

[![Release](https://img.shields.io/github/v/release/mindsdb/minds?logo=github&label=release)](https://github.com/mindsdb/minds/releases)
[![Stars](https://img.shields.io/github/stars/mindsdb/minds?logo=github)](https://github.com/mindsdb/minds/stargazers)
[![License: MIT](https://img.shields.io/github/license/mindsdb/minds)](#-许可证)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20–%203.13-brightgreen.svg)](https://www.python.org/downloads/)

[官网](https://mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[文档](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[网页应用](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[定价](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Discord](https://mindshub.ai/discord)

<p align="center">
  <sub>其他语言: <a href="README.md">English</a> · <a href="README.es.md">Español</a> · <a href="README.pt.md">Português</a> · <a href="README.hi.md">हिन्दी</a></sub>
</p>

</div>

<p align="center">
  <img width="640" height="480" alt="cowork" src="https://github.com/user-attachments/assets/048761b8-aa77-4506-9c4d-32e2fdecbb60" />
</p>

**MindsHub Cowork** 是一个统一工作空间,你可以在这里委托完整的项目——应用、网站、调研、分析、报告、定时运维——并获得可直接分享的成品结果。连接你的数据,将工作路由到任意模型(开源或商用),运行开源智能体,并将其产出转化为可发布的网页应用。它是开源的,可以运行在任何地方——你的电脑、你的 VPC,或托管应用中。

本仓库是**平台超级项目(superproject)**:它整合了桌面/网页应用、智能体后端和数据引擎,让你可以从源码构建并运行整套技术栈。

## 快速开始

选择最适合你的方式:

- **网页版 —— 无需安装。** 打开 **[console.mindshub.ai](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)** 并登录。
- **macOS。** [下载桌面应用](https://downloads.mindsdb.com/mindshub-cowork/mac/mindshub-cowork-latest.pkg)(`.pkg`)。
- **Windows。** [下载桌面应用](https://downloads.mindsdb.com/mindshub-cowork/windows/mindshub-cowork-latest.exe)(`.exe`)。
- **Linux。** [从源码构建](#从源码构建)。

免费即可开始使用。Pro 版本解锁全部前沿模型与私有成果物——详见[定价](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)。

## 你能做什么

面向每一位知识工作者——创作者、策略制定者与运营者:

- **自动化**涉及读写的重复性多步骤工作:报告、监控、周期性工作流以及定时运维任务。
- **构建**内部 AI 工具与成果物——应用、仪表盘、演示文稿、文档、分析报告——无需工程开发,并发布到可分享给团队的在线链接。

## 内含功能

- **数据连接。** 安全的密钥库(vault)可连接 BigQuery、Postgres、Gmail、Drive、HubSpot、Notion、Linear 等系统。凭证按连接单独限定范围——智能体永远看不到原始密钥。
- **模型路由(Model Router)。** 在前沿模型(Claude、GPT、Gemini)与开源模型(DeepSeek、Qwen、Kimi)之间自由切换,无需为每个提供方单独配置密钥。
- **开源智能体。** 运行可互换的开源执行引擎(harness)——Anton(默认)与 Hermes——通过下拉菜单即可切换。
- **成果物(Artifacts)。** 将智能体的产出转化为文档、仪表盘、应用与代码,并发布到在线链接。
- **记忆、技能与定时任务。** 跨会话记忆、可复用的技能库,以及按计划运行的任务。

## 从源码构建

**1. 克隆仓库**

```bash
git clone --recurse-submodules https://github.com/mindsdb/minds.git
cd minds
```

**2. 安装依赖**

```bash
make setup
```

**3. 运行**

| 模式 | 命令 |
|---|---|
| 桌面应用(Electron),支持热重载 | `make dev` 或 `make watch` |
| 浏览器网页应用,支持热重载 | `make dev-web` |
| 生产构建 | `make build` |
| 打包 macOS 版本 | `make dist-mac` |
| 打包 Windows 版本 | `make dist-win` |
| 从本地未提交的源码构建 macOS `.app` | `make pack-local` |
| 清除所有本地安装与数据(从零开始) | `make flush` |

> **从零开始:** `make flush` 会移除本地运行环境(`cowork-server` uv 工具及 `backend/*/.venv`),并删除 `~/.anton`(提供方密钥)与 `~/.cowork`(数据库、hermes、项目)中的应用状态。用它来测试从零安装流程,或从损坏的安装中恢复。执行前会要求确认——传入 `FORCE=1` 可跳过确认。之后运行 `make setup` 或启动应用即可重新安装全部内容。⚠️ 此操作会删除你的对话记录和已保存的密钥。

### 在功能分支上开发(子模块)

本仓库是一个超级项目,将每个模块(`frontend`、`backend/core_api`、`backend/core_agent`、`backend/data-vault`)固定(pin)到某个提交。要在模块分支上开发而不污染 `git status` 或与固定版本产生冲突:

**1. 在(已加入 `.gitignore` 的)`dev.env` 中选择你的分支**(从模板复制):

```bash
cp dev.env.example dev.env      # 然后设置 REF=feat/my-thing(或按模块设置 API_REF=…)
```

**2. `make` 会自动读取该配置** —— 一个开关,适用于两种运行方式:

| 命令 | 作用 |
|---|---|
| `make use` | 按 `dev.env` 中的配置检出所有子模块的分支 |
| `make dev` / `make watch` | 以本地源码热重载方式运行 Electron 应用 |
| `make dev-web` | 以本地源码热重载方式运行网页版 SPA |
| `make server` + `make app` | 从配置的分支(重新)安装桌面服务端,然后启动 |
| `make server-local` + `make app-local` | 从**本地未提交的源码**安装桌面服务端,然后启动 |
| `make pack-local` | 从本地未提交的源码构建 macOS `.app`(无需推送) |
| `make refs` | 显示下一次运行将使用的分支引用 |
| `make baseline` | 将子模块重置为固定的提交版本 |
| `make pin` | 将当前子模块提交记录为超级项目的固定版本(一次明确的提交) |

子模块配置了 `ignore = all`,因此你在分支上的工作永远不会显示为超级项目的更改——父仓库的 `git status` 始终保持干净。固定版本**只能**通过 `make pin` 变更。完整流程见 [`CLAUDE.md`](CLAUDE.md)。

## 随处部署

Cowork 的设计支持灵活部署——**云端、VPC、本地部署、离线隔离环境以及混合基础设施**——让你完全掌控自己的基础设施、模型、权限与数据。

## 帮助与支持

- **提出问题** —— 加入 [Discord 社区](https://mindshub.ai/discord)。
- **报告 Bug** —— 提交 [GitHub issue](https://github.com/mindsdb/minds/issues),并附上复现步骤。
- **查阅文档** —— 使用指南、部署说明与 API,见 [docs.mindshub.ai](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)。
- **企业级 SLA 或定制化部署** —— [联系我们](https://mindshub.ai/contact?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)。

## 🤝 参与贡献

Cowork 是开源项目,欢迎任何形式的贡献——代码、集成、文档、Bug 报告与功能建议。阅读[文档](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)完成环境搭建,浏览[已有 issue](https://github.com/mindsdb/minds/issues),也欢迎到 [Discord](https://mindshub.ai/discord) 打个招呼。

## 🔒 安全

发现安全漏洞?请**不要**创建公开 issue。请通过我们的[安全策略](https://github.com/mindsdb/minds/security)私下提交报告。

## 📚 资源

- [文档](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [博客](https://mindshub.ai/blog?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [品牌指南与媒体资料包](https://mindshub.ai/press-kit?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Discord 社区](https://mindshub.ai/discord)

## 📄 许可证

本仓库基于 [MIT 许可证](LICENSE) 发布。所捆绑的组件遵循各自的许可证——详情请参阅各子模块仓库。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>
