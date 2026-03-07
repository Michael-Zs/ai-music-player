# EPUB 阅读器背景音乐功能

## 功能说明

在 EPUB 阅读器中添加了智能背景音乐功能。当用户开启背景音乐后，系统会：

1. 提取当前阅读位置的文本（约1000词）
2. 调用 AI 生成音乐氛围描述
3. 使用向量搜索匹配合适的音乐
4. 播放音乐
5. 音乐播完后自动循环

## 使用方法

```bash
# 启动服务器
python epub_api.py

# 浏览器访问
http://localhost:8080
```

加载 EPUB 文件后，点击"🎵 开启背景音乐"按钮即可。

## 实现架构

### 后端（epub_api.py）

- FastAPI 服务器，端口 8080
- `POST /api/music-for-reading` - 接收文本，返回匹配音乐
- `GET /audio/{track_id}` - 提供音频流
- 复用现有的 `play.chat()` 和 `embeddingdb.query()` 模块

### 前端

- **index.html** - 添加音乐控制按钮和 audio 元素
- **app.js** - `playNextMusic()` 函数实现循环播放
- **style.css** - 音乐信息显示样式

## 关键代码

音乐播放循环逻辑：

```javascript
audioPlayer.addEventListener('ended', () => {
    if (musicEnabled) playNextMusic();
});
```

每次播放都会重新提取当前页面文本，确保音乐与阅读内容匹配。
