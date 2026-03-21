// ==UserScript==
// @name         PayPayフリマ 自動出品
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  amazon-image-toolから商品データを取得してPayPayフリマのフォームを自動入力
// @match        https://paypayfleamarket-sec.yahoo.co.jp/item/add*
// @match        https://paypayfleamarket.yahoo.co.jp/item/add*
// @grant        GM_xmlhttpRequest
// @connect      amazon-image-tool.onrender.com
// ==/UserScript==

(function() {
    'use strict';

    // 浮かぶボタンを作成
    const btn = document.createElement('div');
    btn.innerHTML = '📦 商品データ入力';
    btn.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 99999;
        background: #ff6600; color: white; padding: 12px 18px;
        border-radius: 8px; cursor: pointer; font-size: 14px;
        font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    document.body.appendChild(btn);

    btn.addEventListener('click', () => {
        btn.innerHTML = '⏳ 読み込み中...';
        GM_xmlhttpRequest({
            method: 'GET',
            url: 'https://amazon-image-tool.onrender.com/api/latest_product',
            onload: function(response) {
                try {
                    const data = JSON.parse(response.responseText);
                    if (data.error) {
                        alert('エラー: ' + data.error + '\n先にアプリで商品を取得してください');
                        btn.innerHTML = '📦 商品データ入力';
                        return;
                    }
                    fillForm(data);
                    btn.innerHTML = '✅ 入力完了';
                } catch(e) {
                    alert('データ取得エラー: ' + e.message);
                    btn.innerHTML = '📦 商品データ入力';
                }
            },
            onerror: function() {
                alert('通信エラー: アプリサーバーに接続できません');
                btn.innerHTML = '📦 商品データ入力';
            }
        });
    });

    function setInputValue(el, value) {
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const nativeTextareaSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        if (el.tagName === 'TEXTAREA') {
            nativeTextareaSetter.call(el, value);
        } else {
            nativeInputValueSetter.call(el, value);
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function fillForm(data) {
        // 全inputとtextareaを探して内容を表示（デバッグ用）
        const inputs = document.querySelectorAll('input[type="text"], input[type="number"], textarea');
        console.log('見つかったフォーム要素:', inputs.length);
        inputs.forEach((el, i) => {
            console.log(i, el.tagName, el.name, el.placeholder, el.className);
        });

        // タイトル入力（placeholderや名前で判定）
        inputs.forEach(el => {
            const ph = (el.placeholder || '').toLowerCase();
            const nm = (el.name || '').toLowerCase();
            const cls = (el.className || '').toLowerCase();

            if (ph.includes('タイトル') || ph.includes('商品名') || nm.includes('title') || nm.includes('name')) {
                setInputValue(el, data.title);
            } else if (ph.includes('説明') || nm.includes('description') || nm.includes('detail')) {
                setInputValue(el, data.description);
            } else if (ph.includes('価格') || ph.includes('金額') || nm.includes('price')) {
                setInputValue(el, String(data.price));
            }
        });

        alert(`✅ 入力しました！\nタイトル: ${data.title.substring(0, 30)}...\n価格: ${data.price}円\n\n画像は手動でアップロードが必要です`);
    }
})();
