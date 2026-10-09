from flask import Flask, request, jsonify, render_template_string
import json
import os
import urllib.error
import urllib.request

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ATA AI</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0; font-family: Arial, sans-serif;
    background: #212121; color: #f5f5f5;
    height: 100vh; display: flex;
}
.sidebar { width: 245px; background: #171717; padding: 22px; }
.logo { font-size: 25px; font-weight: bold; margin-bottom: 28px; }
.new-chat {
    padding: 12px; border: 1px solid #444;
    border-radius: 10px; cursor: pointer;
}
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
header { padding: 20px 25px; border-bottom: 1px solid #393939; }
#messages { flex: 1; overflow-y: auto; padding: 25px 15px; }
.message {
    max-width: 760px; margin: 18px auto; line-height: 1.6;
    white-space: pre-wrap; overflow-wrap: anywhere;
}
.user { background: #343434; padding: 13px 17px; border-radius: 17px; }
.assistant { padding: 13px 17px; }
.welcome { text-align: center; margin-top: 15vh; }
.welcome h1 { font-size: 32px; }
.bottom { padding: 15px; }
form {
    max-width: 760px; margin: auto; display: flex; gap: 10px;
    background: #303030; border: 1px solid #494949;
    border-radius: 18px; padding: 10px;
}
input {
    flex: 1; min-width: 0; background: transparent; color: white;
    border: 0; outline: 0; padding: 10px; font-size: 16px;
}
button {
    background: #f5f5f5; color: #111; border: 0;
    border-radius: 12px; padding: 0 17px; cursor: pointer;
    font-size: 17px; font-weight: bold;
}
button:disabled { opacity: .5; }
.note { text-align: center; color: #999; font-size: 12px; margin-top: 10px; }
@media(max-width:600px) {
    .sidebar { display:none; }
    header { padding: 15px; }
    .welcome h1 { font-size: 25px; }
}
</style>
</head>
<body>
<aside class="sidebar">
  <div class="logo">✦ ATA AI</div>
  <div class="new-chat" onclick="newChat()">＋ Yeni sohbet</div>
</aside>
<main class="main">
  <header><b>ATA AI</b> <span style="color:#aaa"> · Yapay zekâ asistanı</span></header>
  <div id="messages">
    <div class="welcome" id="welcome">
      <h1>Bugün sana nasıl yardımcı olabilirim?</h1>
      <p style="color:#aaa">ATA AI'ye bir mesaj yaz.</p>
    </div>
  </div>
  <div class="bottom">
    <form id="chat">
      <input id="prompt" placeholder="ATA AI'ye mesaj gönder..." autocomplete="off" required maxlength="6000">
      <button id="send" type="submit">➤</button>
    </form>
    <div class="note">ATA AI hata yapabilir. Yanıtları kontrol et.</div>
  </div>
</main>
<script>
const messages = document.getElementById('messages');
const form = document.getElementById('chat');
const input = document.getElementById('prompt');
const send = document.getElementById('send');
let history = [];

function addMessage(text, role) {
    document.getElementById('welcome')?.remove();
    const div = document.createElement('div');
    div.className = 'message ' + role;
    div.textContent = (role === 'user' ? 'Sen\\n' : 'ATA AI\\n') + text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

function newChat() {
    history = [];
    messages.innerHTML = '<div class="welcome" id="welcome"><h1>Bugün sana nasıl yardımcı olabilirim?</h1><p style="color:#aaa">ATA AI\\'ye bir mesaj yaz.</p></div>';
    input.focus();
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMessage(text, 'user');
    history.push({role:'user', content:text});
    input.value = '';
    send.disabled = true;
    const replyBox = addMessage('Düşünüyorum...', 'assistant');
    try {
        const response = await fetch('/chat', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({messages:history})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Bir hata oluştu.');
        replyBox.textContent = 'ATA AI\\n' + data.reply;
        history.push({role:'assistant', content:data.reply});
    } catch(err) {
        replyBox.textContent = 'Hata: ' + err.message;
        // İstek başarısız olursa kullanıcı mesajı geçmişte kalır; yeniden denemek için sohbeti sıfırlayabilir.
    } finally {
        send.disabled = false;
        input.focus();
        messages.scrollTop = messages.scrollHeight;
    }
});
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
def chat():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return jsonify({
            "error": "Sunucu henüz yapılandırılmadı: GROQ_API_KEY ortam değişkeni eklenmeli."
        }), 503

    body = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "Lütfen önce bir mesaj yaz."}), 400

    api_messages = [{
        "role": "system",
        "content": (
            "Sen ATA AI adlı yardımcı bir yapay zekâsın. "
            "Türkçe ve açık cevap ver. Bilmediğin şeyleri uydurma."
        )
    }]

    # Keep only recent conversation turns and validate input before sending it to the provider.
    for message in messages[-12:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()[:6000]
        if content:
            api_messages.append({"role": role, "content": content})

    if len(api_messages) == 1:
        return jsonify({"error": "Geçerli bir mesaj bulunamadı."}), 400

    payload = json.dumps({
        "model": "openai/gpt-oss-20b",
        "messages": api_messages,
        "temperature": 0.7,
        "max_completion_tokens": 1200
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
            headers={
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
    "User-Agent": "ATA-AI/1.0"
},
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
        reply = result["choices"][0]["message"]["content"]
        return jsonify({"reply": reply or "Bu sefer yanıt oluşturamadım. Lütfen tekrar dene."})
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        if error.code == 429:
            return jsonify({
                "error": "Ücretsiz kullanım sınırına ulaşıldı. Biraz bekleyip tekrar dene."
            }), 429
        app.logger.warning("AI provider returned HTTP %s: %s", error.code, details[:500])
        return jsonify({
            "error": "Yapay zekâ servisi şu anda yanıt veremiyor. API anahtarını ve model erişimini kontrol et."
        }), 502
    except (urllib.error.URLError, TimeoutError):
        return jsonify({
            "error": "Yapay zekâ servisine bağlanılamadı. Biraz sonra tekrar dene."
        }), 502
    except (KeyError, IndexError, json.JSONDecodeError):
        app.logger.exception("Unexpected response from AI provider")
        return jsonify({"error": "Yapay zekâ servisinden beklenmeyen bir yanıt geldi."}), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
