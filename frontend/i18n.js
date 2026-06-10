/* InesAI — i18n (PT/EN)
   Uso:
     - Elementos HTML: <span data-i18n="chave">texto default</span>
     - Placeholders:   <input data-i18n-placeholder="chave">
     - Títulos:        <button data-i18n-title="chave">
     - JS:             t("chave")  ou  t("chave", {n: 5})
   O idioma é detectado do browser e guardado em localStorage ("lang").
*/

const I18N = {
    pt: {
        // Geral
        app_name: "InesAI",
        app_title: "InesAI - Chat AI",

        // Sidebar
        new_chat: "＋ Novo chat",
        configuration: "Configuração",
        history: "Histórico",
        auto_select: "🤖 AUTO (Selecionar Automaticamente)",
        web_search: "🌐 Pesquisa Web",
        fallback: "🔄 Fallback",
        summarize_context: "📝 Resumir contexto",
        theme_toggle: "Mudar tema",
        logout: "Sair",
        reload_config: "Painel de administração",
        language_toggle: "Switch to English",

        // Chat
        message_placeholder: "Mensagem InesAI...",
        attach: "Anexar",
        send: "Enviar",
        attach_files: "Anexar ficheiro(s)",
        insert_code: "Inserir código",
        insert_code_title: "📝 Inserir Código",
        auto_detect: "Auto-detectar",
        paste_code_here: "Cole o código aqui...",
        cancel: "Cancelar",
        insert: "Inserir",
        hint_newline: "Shift+Enter ↵ nova linha",
        hint_send: "Enter ↵ enviar",
        text_plain: "Texto",

        // Mensagens dinâmicas (app.js)
        ws_not_connected: "WebSocket não conectado. A reconectar...",
        rename_prompt: "Novo nome da conversa:",
        delete_confirm: "Apagar esta conversa?",
        file_too_large: "Imagem demasiado grande (max 5MB): ",
        binary_file: " parece ser um ficheiro binário e não pode ser lido como texto. Tenta converter para PDF ou txt.",
        cant_read_file: "Não consegui ler ",
        rename_title: "Renomear",
        delete_title: "Apagar",

        // Login
        login_title: "InesAI - Login",
        login_subtitle: "Introduz as tuas credenciais para entrar",
        username: "Utilizador",
        username_placeholder: "O teu utilizador",
        password: "Password",
        enter: "Entrar",
        entering: "A entrar...",
        fill_fields: "Preenche o utilizador e a password.",
        login_error: "Erro ao fazer login.",
        connection_error: "Erro de ligação. Tenta novamente.",

        // Admin
        admin_dashboard: "Dashboard",
        admin_users: "Utilizadores",
        admin_providers: "Providers",
        admin_logs: "Logs",
        admin_back_chat: "Voltar ao Chat",
        admin_system_status: "Estado geral do sistema",
        admin_stat_users: "Utilizadores",
        admin_stat_sessions: "Conversas",
        admin_stat_messages: "Mensagens",
        admin_stat_models: "Modelos ativos",
        admin_stat_providers: "Providers ativos",
        admin_stat_ws: "WS ligados",
        admin_reload_title: "Recarregar Configuração",
        admin_reload_btn: "Reload config.json",
        admin_reload_desc: "Aplica alterações ao config.json sem reiniciar o servidor. Activa novos providers, modelos e API keys em tempo real.",
        admin_users_mgmt: "Gestão de contas e permissões",
        admin_users_list: "Lista de utilizadores",
        admin_new_user: "+ Novo utilizador",
        admin_col_role: "Papel",
        admin_col_created: "Criado em",
        admin_col_actions: "Ações",
        admin_providers_desc: "Providers de IA activos e modelos disponíveis",
        admin_logs_desc: "Últimas 100 linhas do backend.log",
        admin_refresh: "↻ Atualizar",
        admin_clear_view: "Limpar vista",
        admin_modal_new_user: "Novo Utilizador",
        admin_make_admin: "Tornar administrador",
        admin_create: "Criar",
        admin_modal_passwd: "Mudar Password",
        admin_new_passwd_for: "Nova password para",
        admin_min_chars: "mínimo 6 caracteres",
        admin_save: "Guardar"
    },

    en: {
        // General
        app_name: "InesAI",
        app_title: "InesAI - AI Chat",

        // Sidebar
        new_chat: "＋ New chat",
        configuration: "Configuration",
        history: "History",
        auto_select: "🤖 AUTO (Select Automatically)",
        web_search: "🌐 Web Search",
        fallback: "🔄 Fallback",
        summarize_context: "📝 Summarize context",
        theme_toggle: "Toggle theme",
        logout: "Log out",
        reload_config: "Admin panel",
        language_toggle: "Mudar para Português",

        // Chat
        message_placeholder: "Message InesAI...",
        attach: "Attach",
        send: "Send",
        attach_files: "Attach file(s)",
        insert_code: "Insert code",
        insert_code_title: "📝 Insert Code",
        auto_detect: "Auto-detect",
        paste_code_here: "Paste your code here...",
        cancel: "Cancel",
        insert: "Insert",
        hint_newline: "Shift+Enter ↵ new line",
        hint_send: "Enter ↵ send",
        text_plain: "Plain text",

        // Dynamic messages (app.js)
        ws_not_connected: "WebSocket not connected. Reconnecting...",
        rename_prompt: "New conversation name:",
        delete_confirm: "Delete this conversation?",
        file_too_large: "Image too large (max 5MB): ",
        binary_file: " appears to be a binary file and cannot be read as text. Try converting to PDF or txt.",
        cant_read_file: "Could not read ",
        rename_title: "Rename",
        delete_title: "Delete",

        // Login
        login_title: "InesAI - Login",
        login_subtitle: "Enter your credentials to sign in",
        username: "Username",
        username_placeholder: "Your username",
        password: "Password",
        enter: "Sign in",
        entering: "Signing in...",
        fill_fields: "Fill in username and password.",
        login_error: "Login failed.",
        connection_error: "Connection error. Please try again.",

        // Admin
        admin_dashboard: "Dashboard",
        admin_users: "Users",
        admin_providers: "Providers",
        admin_logs: "Logs",
        admin_back_chat: "Back to Chat",
        admin_system_status: "System overview",
        admin_stat_users: "Users",
        admin_stat_sessions: "Conversations",
        admin_stat_messages: "Messages",
        admin_stat_models: "Active models",
        admin_stat_providers: "Active providers",
        admin_stat_ws: "WS connected",
        admin_reload_title: "Reload Configuration",
        admin_reload_btn: "Reload config.json",
        admin_reload_desc: "Apply config.json changes without restarting the server. Activates new providers, models and API keys in real time.",
        admin_users_mgmt: "Account and permission management",
        admin_users_list: "User list",
        admin_new_user: "+ New user",
        admin_col_role: "Role",
        admin_col_created: "Created",
        admin_col_actions: "Actions",
        admin_providers_desc: "Active AI providers and available models",
        admin_logs_desc: "Last 100 lines of backend.log",
        admin_refresh: "↻ Refresh",
        admin_clear_view: "Clear view",
        admin_modal_new_user: "New User",
        admin_make_admin: "Make administrator",
        admin_create: "Create",
        admin_modal_passwd: "Change Password",
        admin_new_passwd_for: "New password for",
        admin_min_chars: "minimum 6 characters",
        admin_save: "Save"
    }
};

// ── Engine ──────────────────────────────────────────────────────────────

function getLang() {
    const saved = localStorage.getItem("lang");
    if (saved && I18N[saved]) return saved;
    // Detectar do browser
    const browserLang = (navigator.language || "pt").toLowerCase();
    return browserLang.startsWith("pt") ? "pt" : "en";
}

function setLang(lang) {
    if (!I18N[lang]) return;
    localStorage.setItem("lang", lang);
    applyI18n();
}

function toggleLang() {
    setLang(getLang() === "pt" ? "en" : "pt");
}

function t(key) {
    const lang = getLang();
    return (I18N[lang] && I18N[lang][key]) || (I18N.pt[key]) || key;
}

function applyI18n() {
    const lang = getLang();

    // textContent
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (I18N[lang][key] !== undefined) el.textContent = I18N[lang][key];
    });

    // placeholders
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (I18N[lang][key] !== undefined) el.placeholder = I18N[lang][key];
    });

    // títulos (tooltips)
    document.querySelectorAll("[data-i18n-title]").forEach(el => {
        const key = el.getAttribute("data-i18n-title");
        if (I18N[lang][key] !== undefined) el.title = I18N[lang][key];
    });

    // <title> da página
    const titleKey = document.documentElement.getAttribute("data-i18n-page");
    if (titleKey && I18N[lang][titleKey]) document.title = I18N[lang][titleKey];

    // html lang attribute
    document.documentElement.lang = lang;

    // Botão de idioma mostra o idioma DESTINO
    const langBtn = document.getElementById("lang-toggle");
    if (langBtn) {
        langBtn.textContent = lang === "pt" ? "EN" : "PT";
        langBtn.title = t("language_toggle");
    }
    const langLabel = document.getElementById("lang-label");
    if (langLabel) langLabel.textContent = lang === "pt" ? "EN" : "PT";
}

// Aplicar assim que o DOM estiver pronto
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyI18n);
} else {
    applyI18n();
}
