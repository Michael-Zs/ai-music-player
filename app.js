let book, rendition;

document.getElementById('file-input').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
        if (rendition) rendition.destroy();

        book = ePub();
        book.open(event.target.result);

        rendition = book.renderTo('viewer', {
            width: '100%',
            height: '100%',
            allowScriptedContent: true
        });

        rendition.display().catch(err => {
            console.error('显示失败:', err);
            alert('加载 EPUB 失败，请检查文件格式');
        });

        rendition.on('relocated', (location) => {
            window.currentLocation = location;
        });
    };
    reader.readAsArrayBuffer(file);
});

document.getElementById('prev').addEventListener('click', () => {
    if (rendition) rendition.prev();
});

document.getElementById('next').addEventListener('click', () => {
    if (rendition) rendition.next();
});

document.getElementById('font-size').addEventListener('input', (e) => {
    if (rendition) {
        rendition.themes.fontSize(e.target.value + 'px');
    }
});

async function getTextFromLocation(wordLimit = 1000) {
    if (!book || !window.currentLocation) return '';

    let text = '';
    let wordCount = 0;
    const startIndex = book.spine.spineItems.findIndex(item =>
        item.href === window.currentLocation.start.href
    );

    for (let i = startIndex; i < book.spine.length && wordCount < wordLimit; i++) {
        const item = book.spine.get(i);
        await item.load(book.load.bind(book));

        const bodyText = item.document.body.textContent.trim();
        const words = bodyText.split(/\s+/);
        const remaining = wordLimit - wordCount;
        text += words.slice(0, remaining).join(' ') + ' ';
        wordCount += Math.min(words.length, remaining);
    }

    return text.trim();
}

let musicEnabled = false;
const audioPlayer = document.getElementById('audio-player');
const musicInfo = document.getElementById('music-info');

document.getElementById('music-toggle').addEventListener('click', () => {
    musicEnabled = !musicEnabled;
    document.getElementById('music-toggle').textContent = musicEnabled ? '🎵 关闭背景音乐' : '🎵 开启背景音乐';
    if (musicEnabled) playNextMusic();
    else audioPlayer.pause();
});

audioPlayer.addEventListener('ended', () => {
    if (musicEnabled) playNextMusic();
});

async function playNextMusic() {
    const text = await getTextFromLocation(1000);
    if (!text) {
        musicInfo.textContent = '无法获取文本';
        return;
    }

    musicInfo.textContent = '正在查找音乐...';
    try {
        const res = await fetch('http://localhost:8080/api/music-for-reading', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text})
        });
        const data = await res.json();
        audioPlayer.src = data.audio_url;
        audioPlayer.play();
        musicInfo.textContent = `♪ ${data.title} - ${data.artist}`;
    } catch (e) {
        musicInfo.textContent = '音乐加载失败';
        console.error(e);
    }
}
