# ImagePrompt 插件 for XXXBot

## 🌟 插件介绍

**ImagePrompt** 是一款 XXXBot 插件，允许用户通过发送图片来获取该图片的描述性提示词。本插件利用 [ImagePrompt.org](https://imageprompt.org/) 提供的服务将图片转换为高质量的文本提示。

这对于 AI 绘画、图像理解或其他需要将视觉内容转化为文本描述的场景非常有用。

## ✨ 功能特性

*   **图片反推提示词**：上传图片，获取描述该图片的文本提示。
*   **多语言支持**：
    *   中文提示词：通过特定命令生成中文描述。
    *   英文提示词：通过特定命令生成英文描述。
*   **简单易用**：通过简单的聊天命令和图片发送即可操作。
*   **基于云服务**：依赖 [ImagePrompt.org](https://imageprompt.org/) API 进行处理。

## 🔧 安装与启用

1.  **下载插件**：
    *   将 `imageprompt` 文件夹放置于 XXXBot 的 `plugins` 目录下。
    *   目录结构应如下所示：
        ```
        plugins/
        └── imageprompt/
            ├── __init__.py
            ├── main.py
            ├── config.toml
            └── README.md
        ```

2.  **安装依赖** (如果插件有特定的Python包需求，通常会在 `requirements.txt` 中列出，但此插件目前的核心依赖 `aiohttp` 和 `tomllib` 通常已包含在 XXXBot 环境中或作为标准库)。

3.  **配置插件**：
    *   打开 `plugins/imageprompt/config.toml` 文件。
    *   根据需要修改配置项（详见下面的"配置说明"部分）。
    *   确保至少将 `enable` 设置为 `true`。

4.  **重启 XXXBot**：
    *   重启 XXXBot 服务以加载新插件。插件加载成功后，控制台日志中应能看到类似 `[ImagePrompt] Plugin loaded.` 的信息。

## 🚀 使用方法

1.  **触发中文反推**：
    *   向机器人发送文本命令：`/反推`
    *   机器人会回复："请发送需要反推提示词的图片。"
    *   接着发送一张图片给机器人。

2.  **触发英文反推**：
    *   向机器人发送文本命令：`/反推 英文`
    *   机器人会回复："Please send the image for which you want to generate a prompt."
    *   接着发送一张图片给机器人。

3.  **接收结果**：
    *   插件会将图片发送到 [ImagePrompt.org](https://imageprompt.org/) 服务进行处理。
    *   处理完成后，机器人会将生成的提示词回复给您。

**注意**：
*   发送命令后，您需要在一定时间内（默认为300秒，可在 `config.toml` 中配置）发送图片，否则请求会超时。
*   确保机器人可以正常访问互联网，以便与 [ImagePrompt.org](https://imageprompt.org/) API 通信。

## ⚙️ 配置说明

插件的配置文件位于 `plugins/imageprompt/config.toml`。

```toml
[basic]
# 是否启用插件
# true: 启用, false: 禁用
enable = true

# 中文提示词的触发指令
trigger_word_zh = "/反推"

# 英文提示词的触发指令
trigger_word_en = "/反推 英文"

# ImagePrompt 服务 API 端点
api_url = "https://imageprompt.org/api/ai/prompts/image"

# 用户状态超时时间（秒）
# 即发送命令后，等待用户发送图片的最大时长
user_state_timeout = 300

# 默认的图像模型 ID (具体含义参考 ImagePrompt.org API 文档)
# 通常 0 是一个通用或默认模型
default_image_model_id = 0
```

**可配置项**：

*   `enable`: 布尔值，`true` 启用插件，`false` 禁用插件。
*   `trigger_word_zh`: 字符串，触发中文提示词生成的命令。
*   `trigger_word_en`: 字符串，触发英文提示词生成的命令。
*   `api_url`: 字符串，ImagePrompt 服务的 API 地址。**请勿随意修改，除非您知道自己在做什么或官方 API 地址变更。**
*   `user_state_timeout`: 整数，用户发送命令后等待图片上传的超时时间（单位：秒）。
*   `default_image_model_id`: 整数，传递给 API 的图像模型 ID。

## 🧑‍💻 开发者信息

*   **作者**：xxxbot团伙
*   **版本**：1.0.0
*   **依赖服务**：[ImagePrompt.org](https://imageprompt.org/)

## ⚠️ 注意事项与限制

*   本插件依赖第三方服务 [ImagePrompt.org](https://imageprompt.org/)。服务的可用性、响应速度、生成质量以及任何使用限制（如每日免费次数）均取决于该第三方服务。
*   请遵守 [ImagePrompt.org](https://imageprompt.org/) 的服务条款。
*   图片上传和处理可能需要一些时间，请耐心等待。
*   如果 API 服务不可用或返回错误，插件会尝试向用户发送相应的错误提示。

## 📝 未来可能改进

*   支持更多 ImagePrompt.org 提供的参数配置。
*   错误处理和用户反馈优化。

## ❓ 问题反馈

如果您在使用过程中遇到任何问题，或有功能建议，欢迎通过 issues 反馈。
