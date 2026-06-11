// InesAI WebSocket Client
console.log("=== APP.JS CARREGADO ===");

class InesAIChat {
    constructor() {
        this.ws = null;
        this.currentSession = null;
        this.models = [];
        this.isConnected = false;
        this.isProcessing = false;
        this.uploadedFiles = [];
        this.pendingCode = null;
        this.currentAssistantDiv = null;
        this.currentModelName = "";
        this.fallbackInfoDiv = null;
        this.streamBuffer = "";      // throttle: acumula chunks
        this.streamFull = "";        // throttle: texto completo actual
        this.streamTimer = null;     // throttle: timer de render
        console.log("InesAIChat criado");
        this.init();
    }

    init() {
        console.log("init() chamado");
        this.connectWebSocket();
        this.setupEventListeners();
        this.loadModels();
        this.loadSessions();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = protocol + "//" + window.location.host + "/ws";
        console.log("WebSocket URL:", wsUrl);
        this.ws = new WebSocket(wsUrl);
        this.ws.onopen = () => {
            console.log("WebSocket connected");
            this.isConnected = true;
        };
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        this.ws.onclose = () => {
            console.log("WebSocket disconnected");
            this.isConnected = false;
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        this.ws.onerror = (error) => {
            console.error("WebSocket error:", error);
        };
    }

    handleMessage(data) {
        switch(data.type) {
            case "info":
                this.showInfo(data.content, data.model_name, data.fallback_used);
                if (data.session_id && data.session_id !== this.currentSession) {
                    this.currentSession = data.session_id;
                    this.loadSessions();
                }
                break;
            case "thinking":
                this.showTyping();
                break;
            case "chunk":
                this.hideTyping();
                this.appendChunk(data.content, data.full, data.model_name, data.fallback_used);
                break;
            case "done":
                this.finishStreaming(data.content, data.model_name, data.fallback_used);
                this.currentSession = data.session_id;
                this.loadSessions();
                break;
            case "error":
                this.hideTyping();
                this.showError(data.content, data.model_name, data.fallback_used);
                if (data.session_id) this.loadSessions();
                break;
        }
    }

    showInfo(content, modelName, fallbackUsed) {
        const container = document.getElementById("messages");

        // Se é fallback, guardar referência para remover depois
        if (fallbackUsed || content.includes("alternativo")) {
            // Remover info anterior de fallback se existir
            if (this.fallbackInfoDiv) {
                this.fallbackInfoDiv.remove();
                this.fallbackInfoDiv = null;
            }

            const div = document.createElement("div");
            div.className = "message info-message fallback-info";
            div.innerHTML = `<div class="message-header fallback">🔄 ${this.escapeHtml(content)}</div>`;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;

            // Guardar referência para remover quando receber resposta
            this.fallbackInfoDiv = div;
            return;
        }

        // Info normal (modelo escolhido)
        const oldInfo = document.getElementById("model-info");
        if (oldInfo) oldInfo.remove();

        const div = document.createElement("div");
        div.id = "model-info";
        div.className = "message info-message";
        div.innerHTML = `<div class="message-header info">ℹ️ ${this.escapeHtml(content)}</div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    // NOVO: Remover mensagem de fallback quando recebe resposta
    removeFallbackInfo() {
        if (this.fallbackInfoDiv) {
            this.fallbackInfoDiv.remove();
            this.fallbackInfoDiv = null;
        }
    }

    setupEventListeners() {
        console.log("setupEventListeners() chamado");
        const sendBtn = document.getElementById("send-btn");
        if (sendBtn) {
            sendBtn.addEventListener("click", () => this.handleSendButton());
        }
        const msgInput = document.getElementById("message-input");
        if (msgInput) {
            msgInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    this.handleSendButton();
                }
            });
            msgInput.addEventListener("input", () => {
                msgInput.style.height = "auto";
                msgInput.style.height = Math.min(msgInput.scrollHeight, 200) + "px";
            });
            msgInput.addEventListener("paste", (e) => this.handlePaste(e));
        }
        const newChatBtn = document.getElementById("new-chat-btn");
        if (newChatBtn) {
            newChatBtn.addEventListener("click", () => this.newChat());
        }
        const menuBtn = document.getElementById("menu-btn");
        if (menuBtn) {
            menuBtn.addEventListener("click", () => this.toggleSidebar());
        }
        const overlay = document.getElementById("sidebar-overlay");
        if (overlay) {
            overlay.addEventListener("click", () => this.closeSidebar());
        }
        const btnAttach = document.getElementById("btn-attach");
        if (btnAttach) {
            btnAttach.addEventListener("click", () => this.toggleAttachMenu());
        }
        const attachFile = document.getElementById("attach-file");
        const fileInput = document.getElementById("file-upload");
        if (attachFile && fileInput) {
            attachFile.addEventListener("click", () => {
                fileInput.click();
                this.hideAttachMenu();
            });
            fileInput.addEventListener("change", (e) => this.handleFileUpload(e));
        }
        const attachCode = document.getElementById("attach-code");
        if (attachCode) {
            attachCode.addEventListener("click", () => {
                this.showCodeModal();
                this.hideAttachMenu();
            });
        }
        const codeModalClose = document.getElementById("code-modal-close");
        const codeModalCancel = document.getElementById("code-modal-cancel");
        const codeModalInsert = document.getElementById("code-modal-insert");
        if (codeModalClose) {
            codeModalClose.addEventListener("click", () => this.hideCodeModal());
        }
        if (codeModalCancel) {
            codeModalCancel.addEventListener("click", () => this.hideCodeModal());
        }
        if (codeModalInsert) {
            codeModalInsert.addEventListener("click", () => this.insertCode());
        }
        const codeModal = document.getElementById("code-modal");
        if (codeModal) {
            codeModal.addEventListener("click", (e) => {
                if (e.target === codeModal) this.hideCodeModal();
            });
        }
        const themeToggle = document.getElementById("theme-toggle");
        if (themeToggle) {
            themeToggle.addEventListener("click", () => this.toggleTheme());
            this.loadTheme();
        }
        document.addEventListener("click", (e) => {
            const attachMenu = document.getElementById("attach-menu");
            const btnAttach = document.getElementById("btn-attach");
            if (attachMenu && !attachMenu.classList.contains("hidden")) {
                if (!attachMenu.contains(e.target) && e.target !== btnAttach) {
                    this.hideAttachMenu();
                }
            }
        });
    }

    handleSendButton() {
        if (this.isProcessing) {
            this.stopGeneration();
        } else {
            this.sendMessage();
        }
    }

    stopGeneration() {
        console.log("Parando geração...");
        if (this.streamTimer) {
            clearInterval(this.streamTimer);
            this.streamTimer = null;
        }
        this.streamFull = null;
        this.isProcessing = false;
        document.getElementById("send-btn").disabled = false;
        this.updateSendButton(false);

        if (this.currentAssistantDiv) {
            this.currentAssistantDiv.classList.remove("streaming");
            const headerDiv = this.currentAssistantDiv.querySelector(".message-header");
            if (headerDiv) {
                const currentText = headerDiv.querySelector(".model-tag");
                const modelName = currentText ? currentText.textContent : "";
                headerDiv.innerHTML = `🤖 InesAI <span class="model-tag">${modelName} (parado)</span>`;
            }
            this.currentAssistantDiv = null;
        }

        this.hideTyping();
    }

    updateSendButton(isProcessing) {
        const btn = document.getElementById("send-btn");
        if (!btn) return;

        if (isProcessing) {
            btn.innerHTML = "⏹️";
            btn.title = "Parar geração";
            btn.classList.add("stop-button");
        } else {
            btn.innerHTML = "➤";
            btn.title = "Enviar mensagem";
            btn.classList.remove("stop-button");
        }
    }

    handlePaste(event) {
        const clipboardData = event.clipboardData || window.clipboardData;
        const pastedText = clipboardData.getData("text");
        if (this.detectCode(pastedText)) {
            event.preventDefault();
            this.showCodePastePreview(pastedText);
        }
    }

    detectCode(text) {
        if (!text || text.split("\n").length < 2) return false;
        const codeIndicators = [
            /^(def |class |import |from |function |const |let |var |if |for |while |return |print |console\.)/m,
            /[{\[\]}]/,
            /^(\s{2,}|\t)/m,
            /^(\d+\.\s|\*\s|\-\s)/m,
            /```/,
            /^(SELECT |INSERT |UPDATE |DELETE |CREATE |DROP )/mi,
            /^(<!DOCTYPE|<html|<div|<span|<script|<style)/i,
            /^(body\s*\{|\.class\s*\{|#id\s*\{)/,
        ];
        return codeIndicators.some(pattern => pattern.test(text));
    }

    showCodePastePreview(code) {
        const oldPreview = document.getElementById("code-paste-preview");
        if (oldPreview) oldPreview.remove();
        const inputArea = document.querySelector(".input-area");
        const preview = document.createElement("div");
        preview.id = "code-paste-preview";
        preview.className = "code-paste-preview";
        const lang = this.detectLanguage(code);
        preview.innerHTML = "<button class=\"close-btn\" onclick=\"chat.removeCodePreview()\">✖</button><span class=\"lang-tag\">" + lang + "</span><pre>" + this.escapeHtml(code.substring(0, 500)) + (code.length > 500 ? "..." : "") + "</pre>";
        const inputWrapper = document.querySelector(".input-wrapper");
        inputArea.insertBefore(preview, inputWrapper);
        // Sempre guardar como objecto {lang, code} para consistência com sendMessage
        this.pendingCode = { lang: lang, code: code };
        document.getElementById("message-input").focus();
    }

    removeCodePreview() {
        const preview = document.getElementById("code-paste-preview");
        if (preview) preview.remove();
        this.pendingCode = null;
    }

    detectLanguage(code) {
        if (/^(def |class |import |from |print\(|if __name__)/m.test(code)) return "python";
        if (/^(function |const |let |var |console\.|document\.|=>)/m.test(code)) return "javascript";
        if (/^(<!DOCTYPE|<html|<div|<span|<script)/i.test(code)) return "html";
        if (/^(body\s*\{|\.class\s*\{|#id\s*\{|@media)/m.test(code)) return "css";
        if (/^(SELECT |INSERT |UPDATE |DELETE |CREATE TABLE)/mi.test(code)) return "sql";
        if (/^(package |import java|public class|System\.out)/m.test(code)) return "java";
        if (/^(#include |int main|cout <<)/m.test(code)) return "cpp";
        if (/^(func |package |import |fmt\.)/m.test(code)) return "go";
        if (/^(<?php|echo |\$)/m.test(code)) return "php";
        if (/^(using |namespace |class |void |int |string )/m.test(code)) return "csharp";
        return "text";
    }

    toggleAttachMenu() {
        const menu = document.getElementById("attach-menu");
        if (menu) {
            menu.classList.toggle("hidden");
        }
    }

    hideAttachMenu() {
        const menu = document.getElementById("attach-menu");
        if (menu) {
            menu.classList.add("hidden");
        }
    }

    showCodeModal() {
        const modal = document.getElementById("code-modal");
        if (modal) {
            modal.classList.remove("hidden");
            document.getElementById("code-input").focus();
        }
    }

    hideCodeModal() {
        const modal = document.getElementById("code-modal");
        if (modal) {
            modal.classList.add("hidden");
            document.getElementById("code-input").value = "";
            document.getElementById("code-language").value = "";
        }
    }

    insertCode() {
        const codeInput = document.getElementById("code-input");
        const langSelect = document.getElementById("code-language");
        const code = codeInput.value.trim();
        if (!code) {
            this.hideCodeModal();
            return;
        }
        let lang = langSelect.value;
        if (!lang) {
            lang = this.detectLanguage(code);
        }
        this.pendingCode = {
            code: code,
            lang: lang
        };
        this.showAttachmentChip("📝 " + (lang || "code"), "code");
        this.hideCodeModal();
    }

    async handleFileUpload(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        for (const file of files) {
            if (file.name.toLowerCase().endsWith(".zip")) {
                await this.processZipFile(file);
            } else {
                await this.processSingleFile(file);
            }
        }
        event.target.value = "";
    }

    async processSingleFile(file) {
        const name = file.name.toLowerCase();
        if (!this.uploadedFiles) this.uploadedFiles = [];
        try {
            if (/\.(png|jpe?g|gif|webp|bmp|tiff?|ico|avif|heic|heif)$/.test(name) || file.type.startsWith("image/")) {
                // Imagem: base64 para modelos com visão
                if (file.size > 5 * 1024 * 1024) {
                    this.showError(t("file_too_large") + file.name);
                    return;
                }
                const dataUrl = await this.readFileAs(file, "dataurl");
                this.uploadedFiles.push({ name: file.name, content: dataUrl, type: "image" });
                this.showAttachmentChip("🖼️ " + file.name, "image");
            } else if (name.endsWith(".pdf")) {
                const text = await this.extractPdfText(file);
                this.uploadedFiles.push({ name: file.name, content: text, type: "file" });
                this.showAttachmentChip("📎 " + file.name, "file");
            } else if (name.endsWith(".docx")) {
                const text = await this.extractDocxText(file);
                this.uploadedFiles.push({ name: file.name, content: text, type: "file" });
                this.showAttachmentChip("📎 " + file.name, "file");
            } else if (name.endsWith(".xlsx")) {
                const text = await this.extractXlsxText(file);
                this.uploadedFiles.push({ name: file.name, content: text, type: "file" });
                this.showAttachmentChip("📎 " + file.name, "file");
            } else {
                // Texto/código: validar que é mesmo legível antes de enviar
                const text = await this.readFileAs(file, "text");
                // Detectar binário: se mais de 5% dos primeiros 2000 chars forem nulos ou chars de controlo fora de texto normal
                const sample = text.substring(0, 2000);
                const binaryCount = (sample.match(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]/g) || []).length;
                if (binaryCount > sample.length * 0.05) {
                    this.showError("\"" + file.name + "\"" + t("binary_file"));
                    return;
                }
                this.uploadedFiles.push({ name: file.name, content: text, type: "file" });
                this.showAttachmentChip("📎 " + file.name, "file");
            }
        } catch (err) {
            console.error("Erro a processar ficheiro:", err);
            this.showError(t("cant_read_file") + file.name + ": " + (err.message || err));
        }
    }

    readFileAs(file, mode) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error("Falha na leitura do ficheiro"));
            if (mode === "dataurl") reader.readAsDataURL(file);
            else if (mode === "buffer") reader.readAsArrayBuffer(file);
            else reader.readAsText(file);
        });
    }

    loadScript(url) {
        if (!this._loadedScripts) this._loadedScripts = {};
        if (this._loadedScripts[url]) return this._loadedScripts[url];
        this._loadedScripts[url] = new Promise((resolve, reject) => {
            const s = document.createElement("script");
            s.src = url;
            s.onload = resolve;
            s.onerror = () => reject(new Error("Falha ao carregar biblioteca"));
            document.head.appendChild(s);
        });
        return this._loadedScripts[url];
    }

    async extractPdfText(file) {
        await this.loadScript("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js");
        pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
        const buffer = await this.readFileAs(file, "buffer");
        const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
        let text = "";
        const maxPages = Math.min(pdf.numPages, 50);
        for (let i = 1; i <= maxPages; i++) {
            const page = await pdf.getPage(i);
            const content = await page.getTextContent();
            text += content.items.map(it => it.str).join(" ") + "\n\n";
        }
        if (pdf.numPages > maxPages) text += "\n[... PDF truncado em " + maxPages + " páginas de " + pdf.numPages + "]";
        if (!text.trim()) throw new Error("PDF sem texto extraível (pode ser digitalizado/imagem)");
        return text;
    }

    async extractDocxText(file) {
        await this.loadScript("https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/mammoth.browser.min.js");
        const buffer = await this.readFileAs(file, "buffer");
        const result = await mammoth.extractRawText({ arrayBuffer: buffer });
        if (!result.value.trim()) throw new Error("Documento Word vazio ou ilegível");
        return result.value;
    }

    async extractXlsxText(file) {
        await this.loadScript("https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js");
        const buffer = await this.readFileAs(file, "buffer");
        const wb = XLSX.read(buffer, { type: "array" });
        let text = "";
        wb.SheetNames.forEach(sheetName => {
            text += "=== Folha: " + sheetName + " ===\n";
            text += XLSX.utils.sheet_to_csv(wb.Sheets[sheetName]) + "\n\n";
        });
        if (!text.trim()) throw new Error("Excel vazio ou ilegível");
        return text;
    }

    async processZipFile(file) {
        try {
            const zip = await JSZip.loadAsync(file);
            const files = [];
            const skipPatterns = [/^__MACOSX/, /^\.git\//, /node_modules\//, /\.pyc$/, /\.class$/, /\.exe$/, /\.dll$/, /\.so$/, /\.dylib$/];
            for (const [path, zipEntry] of Object.entries(zip.files)) {
                if (zipEntry.dir) continue;
                if (skipPatterns.some(p => p.test(path))) continue;
                if (files.length >= 50) break;
                try {
                    const content = await zipEntry.async("text");
                    if (content.length > 100000) {
                        files.push({
                            name: path,
                            content: content.substring(0, 100000) + "\n... [truncado, ficheiro muito grande]",
                            type: "file"
                        });
                    } else {
                        files.push({
                            name: path,
                            content: content,
                            type: "file"
                        });
                    }
                } catch (e) {
                    console.log("Ficheiro binario ignorado:", path);
                }
            }
            if (!this.uploadedFiles) this.uploadedFiles = [];
            this.uploadedFiles.push({
                name: file.name,
                files: files,
                type: "zip"
            });
            this.showAttachmentChip("📦 " + file.name + " (" + files.length + " ficheiros)", "zip");
        } catch (error) {
            console.error("Erro ao processar ZIP:", error);
            this.showError("Erro ao processar ZIP: " + error.message);
        }
    }

    showAttachmentChip(label, type) {
        const preview = document.getElementById("attachments-preview");
        if (!preview) return;
        preview.classList.remove("hidden");
        const index = preview.children.length;
        const chip = document.createElement("div");
        chip.className = "attachment-chip";
        chip.dataset.type = type;
        chip.dataset.index = index;
        chip.innerHTML = "<span>" + this.escapeHtml(label) + "</span><button onclick=\"chat.removeAttachment(this)\">✖</button>";
        preview.appendChild(chip);
    }

    removeAttachment(btn) {
        const chip = btn.closest(".attachment-chip");
        if (chip) {
            const type = chip.dataset.type;
            const index = parseInt(chip.dataset.index || "0");
            if (type === "code") this.pendingCode = null;
            if (type === "file" || type === "zip") {
                if (this.uploadedFiles) {
                    this.uploadedFiles.splice(index, 1);
                }
            }
            chip.remove();
        }
        const preview = document.getElementById("attachments-preview");
        if (preview) {
            const chips = preview.querySelectorAll(".attachment-chip");
            chips.forEach((chip, i) => {
                chip.dataset.index = i;
            });
            if (chips.length === 0) {
                preview.classList.add("hidden");
            }
        }
    }

    clearAttachments() {
        const preview = document.getElementById("attachments-preview");
        if (preview) {
            preview.innerHTML = "";
            preview.classList.add("hidden");
        }
    }

    toggleSidebar() {
        const sidebar = document.getElementById("sidebar");
        const overlay = document.getElementById("sidebar-overlay");
        if (sidebar) sidebar.classList.toggle("open");
        if (overlay) overlay.classList.toggle("active");
    }

    closeSidebar() {
        const sidebar = document.getElementById("sidebar");
        const overlay = document.getElementById("sidebar-overlay");
        if (sidebar) sidebar.classList.remove("open");
        if (overlay) overlay.classList.remove("active");
    }

    toggleTheme() {
        const body = document.body;
        const btn = document.getElementById("theme-toggle");
        if (body.classList.contains("light-mode")) {
            body.classList.remove("light-mode");
            if (btn) btn.textContent = "🌙";
            localStorage.setItem("theme", "dark");
        } else {
            body.classList.add("light-mode");
            if (btn) btn.textContent = "☀️";
            localStorage.setItem("theme", "light");
        }
    }

    loadTheme() {
        const saved = localStorage.getItem("theme");
        const btn = document.getElementById("theme-toggle");
        if (saved === "light") {
            document.body.classList.add("light-mode");
            if (btn) btn.textContent = "☀️";
        } else {
            if (btn) btn.textContent = "🌙";
        }
    }

    async loadModels() {
        try {
            const response = await fetch("/api/models");
            const data = await response.json();
            this.models = data.models || [];
            const select = document.getElementById("model-select");
            select.innerHTML = "<option value=\"\">🤖 AUTO (Selecionar Automaticamente)</option>";

            const providerEmoji = {
                cerebras: "⚡", groq: "⚡", google: "🔵", github: "⬛",
                cloudflare: "🟠", openrouter: "🔀", anthropic: "🟣",
                openai: "🟢", deepseek: "🔷", mistral: "🔴", xai: "✖️",
                poe: "💎", moonshot: "🌙"
            };

            // Group by provider → tier
            const byProvider = {};
            this.models.forEach(m => {
                const p = m.provider || "other";
                const t = m.tier || "free";
                if (!byProvider[p]) byProvider[p] = { free: [], paid: [] };
                byProvider[p][t].push(m);
            });

            Object.entries(byProvider).forEach(([provider, tiers]) => {
                const emoji = providerEmoji[provider] || "🤖";
                const label = emoji + " " + provider.charAt(0).toUpperCase() + provider.slice(1);

                // If only one tier has models, flat group
                const hasFree = tiers.free.length > 0;
                const hasPaid = tiers.paid.length > 0;

                if (hasFree && !hasPaid) {
                    const group = document.createElement("optgroup");
                    group.label = label;
                    tiers.free.forEach(m => {
                        const opt = document.createElement("option");
                        opt.value = m.id;
                        opt.textContent = m.name;
                        group.appendChild(opt);
                    });
                    select.appendChild(group);
                } else if (!hasFree && hasPaid) {
                    const group = document.createElement("optgroup");
                    group.label = label + " — Paid";
                    tiers.paid.forEach(m => {
                        const opt = document.createElement("option");
                        opt.value = m.id;
                        opt.textContent = m.name;
                        group.appendChild(opt);
                    });
                    select.appendChild(group);
                } else if (hasFree && hasPaid) {
                    const gFree = document.createElement("optgroup");
                    gFree.label = label + " — Free";
                    tiers.free.forEach(m => {
                        const opt = document.createElement("option");
                        opt.value = m.id;
                        opt.textContent = m.name;
                        gFree.appendChild(opt);
                    });
                    select.appendChild(gFree);
                    const gPaid = document.createElement("optgroup");
                    gPaid.label = label + " — Paid";
                    tiers.paid.forEach(m => {
                        const opt = document.createElement("option");
                        opt.value = m.id;
                        opt.textContent = m.name;
                        gPaid.appendChild(opt);
                    });
                    select.appendChild(gPaid);
                }
            });
        } catch (error) {
            console.error("Error loading models:", error);
        }
    }

    async loadSessions() {
        try {
            const response = await fetch("/api/sessions");
            const data = await response.json();
            const sessions = data.sessions || [];
            const container = document.getElementById("sessions-list");
            container.innerHTML = "";
            sessions.forEach(session => {
                const div = document.createElement("div");
                div.className = "session-item" + (session.id === this.currentSession ? " active" : "");
                div.innerHTML = "<span>" + this.escapeHtml(session.name) + "</span><div class=\"session-actions\"><button title=\"" + t("rename_title") + "\" onclick=\"chat.renameSession(" + session.id + ", this); event.stopPropagation();\">✏️</button><button title=\"" + t("delete_title") + "\" onclick=\"chat.deleteSession(" + session.id + "); event.stopPropagation();\">🗑️</button></div>";
                div.addEventListener("click", () => this.loadSession(session.id));
                container.appendChild(div);
            });
        } catch (error) {
            console.error("Error loading sessions:", error);
        }
    }

    async renameSession(sessionId, btn) {
        const item = btn.closest(".session-item");
        const currentName = item ? item.querySelector("span").textContent : "";
        const newName = prompt(t("rename_prompt"), currentName);
        if (newName === null) return;
        const trimmed = newName.trim();
        if (!trimmed || trimmed === currentName) return;
        try {
            const resp = await fetch("/api/sessions/" + sessionId, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: trimmed })
            });
            if (resp.ok) this.loadSessions();
        } catch (error) {
            console.error("Error renaming session:", error);
        }
    }

    async loadSession(sessionId) {
        this.currentSession = sessionId;
        this.closeSidebar();
        try {
            const response = await fetch("/api/sessions/" + sessionId + "/messages");
            const data = await response.json();
            const messages = data.messages || [];
            document.getElementById("messages").innerHTML = "";
            messages.forEach(msg => {
                this.addMessage(msg.role, msg.content, msg.model);
            });
            this.loadSessions();
        } catch (error) {
            console.error("Error loading session:", error);
        }
    }

    async deleteSession(sessionId) {
        if (!confirm(t("delete_confirm"))) return;
        try {
            await fetch("/api/sessions/" + sessionId, { method: "DELETE" });
            if (this.currentSession === sessionId) {
                this.currentSession = null;
                document.getElementById("messages").innerHTML = "";
            }
            this.loadSessions();
        } catch (error) {
            console.error("Error deleting session:", error);
        }
    }

    sendMessage() {
        const input = document.getElementById("message-input");
        let message = input.value.trim();
        if (this.pendingCode) {
            const lang = this.pendingCode.lang;
            const code = this.pendingCode.code;
            if (message) {
                message = message + "\n\n```" + lang + "\n" + code + "\n```";
            } else {
                message = "```" + lang + "\n" + code + "\n```";
            }
            this.pendingCode = null;
            const codePreview = document.getElementById("code-paste-preview");
            if (codePreview) codePreview.remove();
        }
        let pendingImages = [];
        if (this.uploadedFiles && this.uploadedFiles.length > 0) {
            let filesContent = "";
            for (const file of this.uploadedFiles) {
                if (file.type === "image") {
                    pendingImages.push(file.content);
                    filesContent += "\n\n🖼️ Imagem anexada: " + file.name;
                } else if (file.type === "zip") {
                    filesContent += "\n\n📦 ZIP: " + file.name + "\n";
                    filesContent += "Conteudo (" + file.files.length + " ficheiros):\n";
                    filesContent += "```\n";
                    for (const subFile of file.files) {
                        filesContent += "--- " + subFile.name + " ---\n";
                        filesContent += subFile.content.substring(0, 5000);
                        if (subFile.content.length > 5000) {
                            filesContent += "\n... [truncado]\n";
                        }
                        filesContent += "\n\n";
                    }
                    filesContent += "```";
                } else {
                    filesContent += "\n\n📎 " + file.name + "\n";
                    filesContent += "```\n" + file.content.substring(0, 10000);
                    if (file.content.length > 10000) {
                        filesContent += "\n... [truncado]\n";
                    }
                    filesContent += "\n```";
                }
            }
            if (message) {
                message = message + filesContent;
            } else if (pendingImages.length > 0 && !filesContent.replace(/🖼️ Imagem anexada: [^\n]*/g, "").trim()) {
                message = "Analisa esta imagem." + filesContent;
            } else {
                message = "Analise os seguintes ficheiros:" + filesContent;
            }
            this.uploadedFiles = [];
            this.clearAttachments();
        }
        if (!message || this.isProcessing) return;
        const modelId = document.getElementById("model-select").value;
        const useWebSearch = document.getElementById("web-search").checked;
        const useFallback = document.getElementById("fallback").checked;
        const summarizeContext = document.getElementById("summarize-context").checked;
        this.addMessage("user", message);
        input.value = "";
        input.style.height = "auto";
        this.isProcessing = true;

        this.updateSendButton(true);

        document.getElementById("send-btn").disabled = false;

        this.currentAssistantDiv = this.createAssistantDiv();
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                message: message,
                model_id: modelId,
                session_id: this.currentSession,
                lang: localStorage.getItem("lang") || "pt",
                use_web_search: useWebSearch,
                use_fallback: useFallback,
                summarize_context: summarizeContext,
                lang: getLang(),
                images: pendingImages
            }));
        } else {
            this.showError(t("ws_not_connected"));
            this.isProcessing = false;
            this.updateSendButton(false);
        }
    }

    createAssistantDiv() {
        const container = document.getElementById("messages");
        const div = document.createElement("div");
        div.className = "message assistant streaming";
        div.innerHTML = "<div class=\"message-header\">🤖 InesAI <span class=\"streaming-indicator\">▌</span></div><div class=\"message-content\"></div>";
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
        return div;
    }

    appendChunk(chunk, full, modelName, fallbackUsed) {
        // NOVO: Remover mensagem de fallback quando começa a receber resposta
        if (fallbackUsed) {
            this.removeFallbackInfo();
        }

        if (!this.currentAssistantDiv) {
            this.currentAssistantDiv = this.createAssistantDiv();
        }
        const contentDiv = this.currentAssistantDiv.querySelector(".message-content");
        const headerDiv = this.currentAssistantDiv.querySelector(".message-header");

        if (modelName && headerDiv) {
            let displayName = modelName;
            if (fallbackUsed) {
                displayName = modelName + " (fallback)";
            }
            headerDiv.innerHTML = "🤖 InesAI <span class=\"streaming-indicator\">▌</span> <span class=\"model-tag\">" + this.escapeHtml(displayName) + "</span>";
        }

        contentDiv.innerHTML = this.renderMarkdown(full);
        // Throttle: acumular e renderizar a 50ms para não bloquear UI
        this.streamFull = full;
        if (!this.streamTimer) {
            this.streamTimer = setInterval(() => {
                if (this.currentAssistantDiv && this.streamFull !== null) {
                    const cd = this.currentAssistantDiv.querySelector(".message-content");
                    if (cd) cd.innerHTML = this.renderMarkdown(this.streamFull);
                    const container = document.getElementById("messages");
                    if (container) container.scrollTop = container.scrollHeight;
                }
            }, 50);
        }
    }

    finishStreaming(content, modelName, fallbackUsed) {
        // Parar o timer de throttle e fazer flush final
        if (this.streamTimer) {
            clearInterval(this.streamTimer);
            this.streamTimer = null;
        }
        this.streamFull = null;

        if (fallbackUsed) {
            this.removeFallbackInfo();
        }

        if (this.currentAssistantDiv) {
            this.currentAssistantDiv.classList.remove("streaming");
            const headerDiv = this.currentAssistantDiv.querySelector(".message-header");
            if (headerDiv) {
                let displayName = modelName || "";
                if (fallbackUsed) {
                    displayName = displayName + " (fallback)";
                }
                headerDiv.innerHTML = "🤖 InesAI <span class=\"model-tag\">" + this.escapeHtml(displayName) + "</span>";
            }
            const contentDiv = this.currentAssistantDiv.querySelector(".message-content");
            contentDiv.innerHTML = this.renderMarkdown(content);
            this.currentAssistantDiv = null;
        }
        this.isProcessing = false;

        this.updateSendButton(false);
    }

    renderMarkdown(text) {
        if (!text) return "";
        let html = this.escapeHtml(text);
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
            return "<pre><code class=\"language-" + lang + "\">" + code + "</code></pre>";
        });
        html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
        html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
        html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
        html = html.replace(/^## (.*$)/gim, "<h2>$1</h2>");
        html = html.replace(/^# (.*$)/gim, "<h1>$1</h1>");
        html = html.replace(/^\- (.*$)/gim, "<li>$1</li>");
        html = html.replace(/\n/g, "<br>");
        return html;
    }

    addMessage(role, content, model) {
        const container = document.getElementById("messages");
        const div = document.createElement("div");
        div.className = "message " + role;
        let header = "";
        if (role === "user") {
            header = "<div class=\"message-header\">👤 Tu</div>";
        } else if (role === "assistant") {
            header = "<div class=\"message-header\">🤖 InesAI" + (model ? " <span class=\"model-tag\">" + model + "</span>" : "") + "</div>";
        }
        div.innerHTML = header + "<div class=\"message-content\">" + this.renderMarkdown(content) + "</div>";
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    showTyping() {
        document.getElementById("typing-indicator").classList.remove("hidden");
        const container = document.getElementById("messages");
        container.scrollTop = container.scrollHeight;
    }

    hideTyping() {
        document.getElementById("typing-indicator").classList.add("hidden");
    }

    showError(message, modelName, fallbackUsed) {
        const container = document.getElementById("messages");
        const div = document.createElement("div");
        div.className = "error-message";

        let errorText = "❌ " + message;
        if (modelName) {
            errorText += "\n(Modelo: " + modelName;
            if (fallbackUsed) {
                errorText += " - fallback usado";
            }
            errorText += ")";
        }

        div.innerHTML = errorText.replace(/\n/g, "<br>");
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
        this.isProcessing = false;

        this.updateSendButton(false);
    }

    newChat() {
        this.currentSession = null;
        document.getElementById("messages").innerHTML = "";
        document.getElementById("message-input").focus();
        this.closeSidebar();
        this.clearAttachments();
        this.pendingCode = null;
        this.uploadedFiles = [];

        // Limpar preview de código colado se existir
        const codePreview = document.getElementById("code-paste-preview");
        if (codePreview) codePreview.remove();

        // NOVO: Limpar fallback info
        this.removeFallbackInfo();
    }

    escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
}

// InesAIChat é instanciado pelo auth bootstrap em index.html após validação da sessão
