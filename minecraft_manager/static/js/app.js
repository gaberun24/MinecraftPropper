// Minecraft Manager - Client-side JS

// WebSocket console client
class ConsoleClient {
    constructor(outputEl, inputEl) {
        this.output = outputEl;
        this.input = inputEl;
        this.ws = null;
        this.autoScroll = true;
        this.reconnectDelay = 2000;
        this.maxLines = 1000;
    }

    connect() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${location.host}/console/ws`;
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            this.appendLine("[Connected to server console]", "system");
        };

        this.ws.onmessage = (event) => {
            this.appendLine(event.data);
        };

        this.ws.onclose = () => {
            this.appendLine("[Disconnected - reconnecting...]", "system");
            setTimeout(() => this.connect(), this.reconnectDelay);
        };

        this.ws.onerror = () => {
            this.ws.close();
        };
    }

    appendLine(text, cls) {
        const line = document.createElement("div");
        line.className = "log-line" + (cls ? ` ${cls}` : "");
        line.textContent = text;
        this.output.appendChild(line);

        // Trim old lines
        while (this.output.children.length > this.maxLines) {
            this.output.removeChild(this.output.firstChild);
        }

        if (this.autoScroll) {
            this.output.scrollTop = this.output.scrollHeight;
        }
    }

    sendCommand(cmd) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(cmd);
            this.appendLine(`> ${cmd}`, "command");
        }
    }

    setupInput() {
        if (!this.input) return;

        this.input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const cmd = this.input.value.trim();
                if (cmd) {
                    this.sendCommand(cmd);
                    this.input.value = "";
                }
            }
        });
    }
}

// Initialize console if on console page
document.addEventListener("DOMContentLoaded", () => {
    const output = document.getElementById("console-output");
    const input = document.getElementById("console-input");

    if (output && input) {
        const client = new ConsoleClient(output, input);
        client.connect();
        client.setupInput();

        // Toggle auto-scroll
        output.addEventListener("scroll", () => {
            const atBottom = output.scrollHeight - output.scrollTop - output.clientHeight < 50;
            client.autoScroll = atBottom;
        });
    }
});
