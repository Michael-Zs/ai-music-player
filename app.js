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
