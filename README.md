
# Danmaku Auto-Sender (`auto_sending_with_config.py`) — README

A lightweight GUI tool to automatically send danmaku (live chat comments) in Bilibili live rooms. Features include: paste-and-verify cookies, split long text files into message chunks by configurable rules (default 20 characters), save/load configuration, logging, and helpful error messages. **Use responsibly and only for lawful purposes.**

---

## Key Features
- Tkinter GUI for easy use.
- Paste full cookie string (e.g. `SESSDATA=...; bili_jct=...; ...`) and validate login status.
- Manually edit messages (one message per line), or load messages from a file (default `message.txt`) and split according to configurable rules.
- Configurable split length (character units) and optional “ASCII letters/digits count as 0.5” mode for mixed-language text.
- Automatic sending on a background thread with options for interval, randomization, and logging.
- Save/load persistent settings in `config.json`. If `config.json` exists at startup, it will be auto-loaded (but cookie validation is not automatic).
- Logs to the GUI and to `auto_send_log.txt` for easier debugging.

---

## Requirements
- Python 3.8+ (3.9/3.10 recommended)
- `requests` library

Install dependencies:
```bash
pip install requests
```

Run the tool:
```bash
python auto_sending_with_config.py
```

---

## Quick Start
1. Log in to Bilibili in your browser. Open DevTools → Application → Cookies and copy the full cookie string (include `SESSDATA`, `bili_jct`, etc.). Avoid using `document.cookie` only — some cookies are `HttpOnly`.
2. Paste the cookie into the Cookie box in the GUI.
3. Fill in the room ID (room number). The tool will attempt to use what you enter.
4. Optionally, either:
   - Type messages in the message area (one per line), or
   - Enable “Load from file” mode, enter a filename (default `message.txt`), and click **Load & Preview** to split and preview segments.
5. Click **Validate Cookie** (recommended).
6. Click **Test Send 1** to try a single message.
7. If successful, click **Start Auto Send** to begin automatic sending. Use **Stop Auto Send** to stop.

---

## message.txt: Format and Splitting Rules
- Default filename: `message.txt` (customizable in the GUI).
- The tool will remove all whitespace (spaces, newlines, tabs) from the file content, then split the cleaned string into chunks.
- Default split length: 20 units (configurable).
- If “ASCII letters/digits count as 0.5” is enabled:
  - ASCII letters and digits are counted as 0.5 units; other characters count as 1 unit.
  - This is useful for mixed Chinese-English content.
- Example:
  ```
  This is a long test text with English words and some 中文字符12345.
  ```
  After stripping whitespace and splitting, chunks will be generated and shown in the message editor for preview.

---

## config.json (save/load)
The GUI saves settings to `config.json`. Fields:
- `roomid`, `interval`, `randomize`, `messages`, `cookie`, `use_file`, `file`, `chunk_size`, `half_count`.

Example:
```json
{
  "roomid": "123456",
  "interval": 2.0,
  "randomize": false,
  "messages": ["test1", "test2"],
  "cookie": "SESSDATA=...; bili_jct=...;",
  "use_file": true,
  "file": "message.txt",
  "chunk_size": 20,
  "half_count": false
}
```

If `config.json` exists at startup the tool will load values into the GUI (it will not auto-validate cookies).

---

## Logging and Debugging
- The tool shows logs in the GUI and writes the same logs to `auto_send_log.txt`.
- Common issues:
  - **Missing `bili_jct (csrf)`**: your cookie string didn’t include `bili_jct`. Copy full cookies from the Browser Application panel.
  - **`code=-101` or not logged in**: `SESSDATA` expired or cookie is incomplete. Re-login and copy fresh cookies.
  - **`code=10030` (too frequent)**: slow down sending interval; implement exponential backoff. Repeated violations may get your account rate-limited.
  - **HTTP non-JSON responses**: may indicate interception or an HTML error page; check network and cookies.
  - **HTTP 401/403/412/429**: often related to authentication, CSRF, referer mismatch, or anti-abuse controls.

If you share logs (without cookies/SESSDATA), we can help diagnose further.

---

## Sending Emoticons (Platform Emoticons)
To send platform emoticons (rendered as images), additional steps are normally required:
- Use the platform’s `emoticon_unique` (e.g. `upower_[pack_name_emoticon_name]`) as `msg` **and** include `dm_type=1` in the POST payload.
- The emoticon must be available for the user/room (call the emoticon list API to confirm).
- If the built-in text sending behaves like plain text, capture a browser request (DevTools → Network → Copy as cURL or fetch) when sending an emoticon manually, and compare the POST body/headers. Replicate any missing fields or headers in the script if necessary.

The current GUI script sends text messages. If you want the “select and send emoticon” UI integrated, I can add that.

---

## Security & Compliance
- Cookies contain login credentials. **Do not share them publicly.** If leaked, immediately invalidate sessions in your Bilibili account security settings.
- Do not abuse automatic sending; respect the platform's rules and rate limits.
- The author assumes no responsibility for bans or restrictions resulting from misuse.

---

## FAQ
**Q: The GUI shows “sent” but the message doesn't appear. Why?**  
A: Check the log for the returned JSON `code` and `message`. If `code != 0`, the server rejected the message (commonly CSRF/cookie/permission issues). Check cookies, referer, and sending rate.

**Q: How to count mixed English/Chinese properly?**  
A: Enable the “ASCII letters/digits = 0.5” option. If you need different weights (e.g. 0.25), ask and it can be customized.

**Q: Will auto sending block the UI?**  
A: No. Sending runs on a background thread and should not freeze the GUI. To apply new settings, stop and restart the sender.

---

## Possible Extensions (I can implement)
- Show estimated chunk count and total character units in the GUI.
- Customizable character weights (e.g. letters = 0.25).
- Ignore or treat punctuation differently.
- Integrate emoticon listing and point-and-click sending (emoticon_unique with `dm_type=1`).
- Advanced rate limiting and retry policies (exponential backoff per error code).

Tell me which extension you want and I will update the script.

---

## License
For personal/internal use. Do not use for activities that violate site terms of service.

