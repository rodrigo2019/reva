/* ============================================================
   REVA Global Assistant — JavaScript (AI-powered)
   ============================================================
   Connects to the real AI assistant backend with SSE streaming
   support, voice transcription, and context-aware suggestions.
   ============================================================ */
(function () {
  "use strict";

  // ---- Configuration ----
  const API = {
    send: "/assistant/api/mensagem/",
    voice: "/assistant/api/voz/",
    context: "/assistant/api/contexto/",
    action: "/assistant/api/acao/",
    clear: "/assistant/api/limpar/",
  };

  // ---- State ----
  let isOpen = false;
  let isRecording = false;
  let isStreaming = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let recordingTimer = null;
  let recordingSeconds = 0;
  let screenId = document.body.dataset.screenId || "default";
  let csrfToken = "";
  let suggestions = [];
  let recentActions = [];

  // ---- DOM refs (set after init) ----
  let fab, panel, messagesContainer, inputField, sendBtn, voiceBtn;
  let voiceStatus, voiceTimerEl, welcomeEl, typingEl;

  // ---- Helpers ----
  function getCookie(name) {
    const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return v ? v.pop() : "";
  }

  function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
  }

  function formatTime(s) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

  /**
   * Capture the full page context: URL, title, heading, forms/fields, tables, stats, etc.
   * Sent alongside every message so the AI assistant knows exactly what the user sees.
   */
  function capturePageContext() {
    const ctx = {
      url: window.location.pathname,
      screen_id: screenId,
      page_title: document.title.replace(" — REVA", "").trim(),
      heading: "",
      forms: [],
      tables: [],
      stats: [],
      links: [],
      visible_data: {},
    };

    // Main heading (h1)
    const mainContent = document.querySelector("main") || document.querySelector(".content") || document.body;
    const h1 = mainContent.querySelector("h1");
    if (h1) ctx.heading = h1.textContent.trim();

    // ----- Capture all forms and their field values -----
    const forms = mainContent.querySelectorAll("form");
    forms.forEach((form, fi) => {
      const formData = {
        id: form.id || `form_${fi}`,
        action: form.action ? new URL(form.action, window.location.origin).pathname : "",
        method: (form.method || "GET").toUpperCase(),
        fields: [],
      };

      const fields = form.querySelectorAll("input, select, textarea");
      fields.forEach((field) => {
        // Skip hidden CSRF and unimportant fields
        if (field.name === "csrfmiddlewaretoken") return;
        if (field.type === "hidden" && !field.value) return;

        const label = _findFieldLabel(field);
        const info = {
          name: field.name || "",
          type: field.type || field.tagName.toLowerCase(),
          value: _getFieldValue(field),
        };
        if (label) info.label = label;
        if (field.placeholder) info.placeholder = field.placeholder;
        if (field.required) info.required = true;

        // For select elements, include the options
        if (field.tagName === "SELECT") {
          info.options = [];
          field.querySelectorAll("option").forEach((opt) => {
            if (opt.value) info.options.push({ value: opt.value, text: opt.textContent.trim() });
          });
        }

        formData.fields.push(info);
      });

      if (formData.fields.length > 0) ctx.forms.push(formData);
    });

    // ----- Capture stat cards (common pattern: number + label) -----
    const statCards = mainContent.querySelectorAll(".stat, [class*='stat']");
    statCards.forEach((card) => {
      const valEl = card.querySelector(".stat-value, .text-3xl, .text-4xl, .font-bold");
      const labelEl = card.querySelector(".stat-title, .stat-desc, .text-sm, .opacity-70");
      if (valEl && labelEl) {
        ctx.stats.push({
          label: labelEl.textContent.trim(),
          value: valEl.textContent.trim(),
        });
      }
    });

    // ----- Capture visible tables -----
    const tables = mainContent.querySelectorAll("table");
    tables.forEach((table, ti) => {
      const tbl = { id: table.id || `table_${ti}`, headers: [], rows: [] };
      table.querySelectorAll("thead th").forEach((th) => {
        tbl.headers.push(th.textContent.trim());
      });
      table.querySelectorAll("tbody tr").forEach((tr, ri) => {
        if (ri >= 20) return; // Limit to first 20 rows
        const row = [];
        tr.querySelectorAll("td").forEach((td) => row.push(td.textContent.trim()));
        if (row.length) tbl.rows.push(row);
      });
      if (tbl.headers.length || tbl.rows.length) ctx.tables.push(tbl);
    });

    // ----- Capture card-based data lists (students, workouts, etc.) -----
    const cards = mainContent.querySelectorAll(".card");
    if (cards.length > 0 && cards.length <= 30) {
      const items = [];
      cards.forEach((card) => {
        const title = card.querySelector(".card-title, h2, h3, h4");
        const text = card.querySelector("p, .text-sm");
        if (title) {
          const item = { title: title.textContent.trim() };
          if (text) item.detail = text.textContent.trim();
          // Look for badges
          const badges = card.querySelectorAll(".badge");
          if (badges.length) {
            item.badges = [];
            badges.forEach((b) => item.badges.push(b.textContent.trim()));
          }
          items.push(item);
        }
      });
      if (items.length) ctx.visible_data.cards = items;
    }

    // ----- Capture inline field values outside forms (e.g., detail pages) -----
    const standaloneInputs = mainContent.querySelectorAll(
      "input:not(form input), select:not(form select), textarea:not(form textarea)"
    );
    if (standaloneInputs.length > 0) {
      const standalone = [];
      standaloneInputs.forEach((field) => {
        if (field.name === "csrfmiddlewaretoken") return;
        if (field.closest("#reva-panel")) return; // Skip assistant panel
        const label = _findFieldLabel(field);
        standalone.push({
          name: field.name || field.id || "",
          type: field.type || field.tagName.toLowerCase(),
          value: _getFieldValue(field),
          label: label || "",
        });
      });
      if (standalone.length) ctx.visible_data.standalone_fields = standalone;
    }

    return ctx;
  }

  /** Find the label text for a form field. */
  function _findFieldLabel(field) {
    // Try explicit <label for="...">
    if (field.id) {
      const lbl = document.querySelector(`label[for="${field.id}"]`);
      if (lbl) return lbl.textContent.trim();
    }
    // Try parent label
    const parentLabel = field.closest("label");
    if (parentLabel) {
      const clone = parentLabel.cloneNode(true);
      clone.querySelectorAll("input, select, textarea").forEach((el) => el.remove());
      return clone.textContent.trim();
    }
    // Try previous sibling label
    const prev = field.previousElementSibling;
    if (prev && prev.tagName === "LABEL") return prev.textContent.trim();
    // Try fieldset legend
    const fieldset = field.closest("fieldset");
    if (fieldset) {
      const legend = fieldset.querySelector("legend");
      if (legend) return legend.textContent.trim();
    }
    return "";
  }

  /** Get the effective value of a form field. */
  function _getFieldValue(field) {
    if (field.type === "checkbox") return field.checked;
    if (field.type === "radio") {
      const checked = document.querySelector(`input[name="${field.name}"]:checked`);
      return checked ? checked.value : "";
    }
    if (field.tagName === "SELECT") {
      const opt = field.options[field.selectedIndex];
      return opt ? { value: opt.value, text: opt.textContent.trim() } : "";
    }
    return field.value || "";
  }

  /**
   * Simple Markdown-to-HTML renderer for assistant messages.
   * Handles bold, italic, code blocks, inline code, lists, headings, and links.
   */
  function renderMarkdown(text) {
    let html = escapeHtml(text);

    // Code blocks (```...```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
      return '<pre class="reva-code-block"><code>' + code.trim() + "</code></pre>";
    });

    // Inline code (`...`)
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Bold (**...**)
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    // Italic (*...*)
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

    // Headings
    html = html.replace(/^### (.+)$/gm, '<h4 class="reva-heading">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="reva-heading">$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2 class="reva-heading">$1</h2>');

    // Unordered lists (- item)
    html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

    // Numbered lists (1. item)
    html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

    // Links [text](url)
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>'
    );

    // Line breaks
    html = html.replace(/\n/g, "<br>");

    // Clean up extra <br> around block elements
    html = html.replace(/<br>(<\/?(?:ul|ol|li|pre|h[2-4]))/g, "$1");
    html = html.replace(/(<\/(?:ul|ol|pre|h[2-4])>)<br>/g, "$1");

    return html;
  }

  // ---- Init ----
  function init() {
    csrfToken = getCookie("csrftoken");
    screenId = document.body.dataset.screenId || "default";

    fab = document.getElementById("reva-fab");
    panel = document.getElementById("reva-panel");
    messagesContainer = document.getElementById("reva-messages");
    inputField = document.getElementById("reva-input");
    sendBtn = document.getElementById("reva-send-btn");
    voiceBtn = document.getElementById("reva-voice-btn");
    voiceStatus = document.getElementById("reva-voice-status");
    voiceTimerEl = document.getElementById("reva-voice-timer");
    welcomeEl = document.getElementById("reva-welcome");
    typingEl = document.getElementById("reva-typing");

    if (!fab || !panel) return;

    // Events
    fab.addEventListener("click", togglePanel);
    sendBtn.addEventListener("click", sendMessage);
    voiceBtn.addEventListener("click", toggleVoiceRecording);
    inputField.addEventListener("keydown", handleInputKeydown);
    inputField.addEventListener("input", autoResizeInput);

    document.getElementById("reva-close-btn")?.addEventListener("click", togglePanel);
    document.getElementById("reva-clear-btn")?.addEventListener("click", clearChat);
    document.addEventListener("click", handleExternalPrompt);

    // Delegate: suggestion chips
    panel.addEventListener("click", function (e) {
      const chip = e.target.closest(".reva-suggestion-chip");
      if (chip) {
        inputField.value = chip.textContent.trim();
        inputField.focus();
        sendMessage();
      }
      const actionBtn = e.target.closest(".reva-action-btn");
      if (actionBtn) {
        handleAction(actionBtn.dataset.type, actionBtn.dataset.url, actionBtn.dataset.label);
      }
    });

    // Voice cancel
    document.getElementById("reva-voice-cancel")?.addEventListener("click", cancelRecording);

    // Load initial context
    loadContext();
  }

  // ---- Toggle Panel ----
  function togglePanel() {
    isOpen = !isOpen;
    panel.classList.toggle("open", isOpen);
    fab.classList.toggle("open", isOpen);

    if (isOpen) {
      setTimeout(() => inputField.focus(), 350);
      scrollToBottom();
    }
  }

  function handleExternalPrompt(e) {
    const trigger = e.target.closest("[data-reva-prompt]");
    if (!trigger || !inputField) return;
    e.preventDefault();

    if (!isOpen) togglePanel();
    inputField.value = trigger.dataset.revaPrompt || "";
    autoResizeInput();
    setTimeout(() => inputField.focus(), 50);
  }

  // ---- Load Context ----
  async function loadContext() {
    try {
      const res = await fetch(`${API.context}?screen_id=${encodeURIComponent(screenId)}`, {
        headers: { "X-CSRFToken": csrfToken },
      });
      if (res.ok) {
        const data = await res.json();
        suggestions = data.suggestions || [];
        recentActions = data.recent_actions || [];
        updateContextBadge(data.screen_name || "");
        updateSuggestions();
        updateRecentActions();
      }
    } catch (err) {
      console.warn("[REVA] Context load failed:", err);
    }
  }

  function updateContextBadge(screenName) {
    const badge = document.getElementById("reva-context-name");
    if (badge) badge.textContent = screenName;
  }

  function updateSuggestions() {
    const container = document.getElementById("reva-suggestions");
    if (!container) return;
    container.innerHTML = suggestions
      .map((s) => `<button class="reva-suggestion-chip">${escapeHtml(s)}</button>`)
      .join("");
  }

  function updateRecentActions() {
    const container = document.getElementById("reva-recent-actions");
    if (!container) return;
    if (!recentActions.length) {
      container.innerHTML = "";
      return;
    }
    container.innerHTML = recentActions
      .slice(0, 3)
      .map((action) => {
        const label = action.label || action.type || "Action";
        const status = action.status || "";
        return `<div class="reva-recent-action"><span>${escapeHtml(label)}</span><span class="reva-recent-action-status">${escapeHtml(status)}</span></div>`;
      })
      .join("");
  }

  // ---- Send Message (with SSE streaming) ----
  async function sendMessage() {
    const text = inputField.value.trim();
    if (!text || isStreaming) return;

    // Hide welcome
    if (welcomeEl) welcomeEl.style.display = "none";

    // Add user message
    appendMessage("user", text);
    inputField.value = "";
    autoResizeInput();

    // Show typing
    showTyping();
    isStreaming = true;
    setInputState(false);

    try {
      const res = await fetch(API.send, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ message: text, screen_id: screenId, page_context: capturePageContext() }),
      });

      if (!res.ok) {
        hideTyping();
        isStreaming = false;
        setInputState(true);
        appendMessage(
          "assistant",
          "Desculpe, tive um problema para processar sua mensagem. Tente novamente."
        );
        return;
      }

      // Check if response is SSE stream
      const contentType = res.headers.get("Content-Type") || "";
      if (contentType.includes("text/event-stream")) {
        await handleSSEStream(res);
      } else {
        // Fallback: JSON response
        hideTyping();
        const data = await res.json();
        appendMessage("assistant", data.content, { actions: data.actions, markdown: true });
      }
    } catch (err) {
      hideTyping();
      console.error("[REVA] Send error:", err);
      appendMessage(
        "assistant",
        "Erro de conexão. Verifique sua internet e tente novamente."
      );
    } finally {
      isStreaming = false;
      setInputState(true);
    }
  }

  /**
   * Handle Server-Sent Events stream from the assistant.
   * Creates a single assistant message bubble and appends text chunks in real-time.
   */
  async function handleSSEStream(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    // Create the assistant message bubble for streaming
    hideTyping();
    const { bubble } = createStreamingMessage();

    let fullText = "";
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE lines
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "message";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
            continue;
          }

          if (line.startsWith("data: ")) {
            const data = line.slice(6);

            if (eventType === "end" || data === "end") {
              break;
            }

            try {
              const parsed = JSON.parse(data);
              if (parsed.text) {
                fullText += parsed.text;
                bubble.innerHTML = renderMarkdown(fullText);
                scrollToBottom();
              }
              if (parsed.tool_call) {
                // Show a subtle indicator that a tool is being used
                const toolLabel = parsed.tool_call;
                bubble.innerHTML =
                  renderMarkdown(fullText) +
                  '<div class="reva-tool-indicator"><span class="reva-tool-spinner"></span> ' +
                  escapeHtml(toolLabel) +
                  "</div>";
                scrollToBottom();
              }
              if (parsed.tool_result) {
                // Remove tool indicator once we have a result
                const indicator = bubble.querySelector(".reva-tool-indicator");
                if (indicator) indicator.remove();
              }
            } catch {
              // Non-JSON data, ignore
            }

            eventType = "message";
          }
        }
      }
    } catch (err) {
      console.error("[REVA] Stream error:", err);
      if (!fullText) {
        fullText = "Erro ao receber resposta. Tente novamente.";
        bubble.innerHTML = renderMarkdown(fullText);
      }
    }

    if (!fullText.trim()) {
      bubble.innerHTML = renderMarkdown("Não consegui gerar uma resposta. Tente novamente.");
    }

    bubble.classList.remove("streaming");
    scrollToBottom();
  }

  /**
   * Create an empty assistant message bubble for streaming content into.
   */
  function createStreamingMessage() {
    const msg = document.createElement("div");
    msg.className = "reva-msg assistant";

    const bubble = document.createElement("div");
    bubble.className = "reva-msg-bubble streaming";

    msg.innerHTML = '<div class="reva-msg-avatar">IA</div>';
    const wrapper = document.createElement("div");
    wrapper.appendChild(bubble);
    msg.appendChild(wrapper);

    messagesContainer.appendChild(msg);
    scrollToBottom();

    return { bubble, msgEl: msg };
  }

  // ---- Voice Recording ----
  async function toggleVoiceRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        sendVoiceMessage();
      };

      mediaRecorder.start();
      isRecording = true;
      recordingSeconds = 0;
      voiceBtn.classList.add("recording");

      // Show recording UI
      inputField.style.display = "none";
      sendBtn.style.display = "none";
      voiceStatus.classList.add("active");
      voiceTimerEl.textContent = "0:00";
      recordingTimer = setInterval(() => {
        recordingSeconds++;
        voiceTimerEl.textContent = formatTime(recordingSeconds);
      }, 1000);
    } catch (err) {
      console.error("[REVA] Microphone access denied:", err);
      appendMessage("assistant", "Não foi possível acessar o microfone. Verifique as permissões do navegador.");
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    resetRecordingUI();
  }

  function cancelRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.ondataavailable = null;
      mediaRecorder.onstop = () => {
        mediaRecorder.stream?.getTracks().forEach((t) => t.stop());
      };
      mediaRecorder.stop();
    }
    audioChunks = [];
    resetRecordingUI();
  }

  function resetRecordingUI() {
    isRecording = false;
    voiceBtn.classList.remove("recording");
    inputField.style.display = "";
    sendBtn.style.display = "";
    voiceStatus.classList.remove("active");
    clearInterval(recordingTimer);
  }

  async function sendVoiceMessage() {
    if (!audioChunks.length) return;

    const blob = new Blob(audioChunks, { type: "audio/webm" });
    audioChunks = [];

    // Show user sent audio indication
    if (welcomeEl) welcomeEl.style.display = "none";
    appendMessage("user", "🎤 Mensagem de voz", { isVoice: true });
    showTyping();

    const formData = new FormData();
    formData.append("audio", blob, "voice.webm");
    formData.append("screen_id", screenId);

    try {
      const res = await fetch(API.voice, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });

      hideTyping();

      if (res.ok) {
        const data = await res.json();
        // Show what was transcribed
        if (data.transcription) {
          appendTranscription(data.transcription);
        }
        appendMessage("assistant", data.content, { actions: data.actions, markdown: true });
      } else {
        appendMessage("assistant", "Não consegui processar o áudio. Tente novamente ou digite sua mensagem.");
      }
    } catch (err) {
      hideTyping();
      appendMessage("assistant", "Erro de conexão ao enviar áudio.");
    }
  }

  // ---- Handle Actions ----
  async function handleAction(type, url, label) {
    if (type === "navigate" && url) {
      appendMessage("assistant", `Navegando para: ${label || url}`);
      setTimeout(() => (window.location.href = url), 600);
      return;
    }

    try {
      const res = await fetch(API.action, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ action_type: type, params: { url, label }, screen_id: screenId }),
      });
      if (res.ok) {
        const data = await res.json();
        appendMessage("assistant", data.message);
      }
    } catch (err) {
      appendMessage("assistant", "Não foi possível executar a ação.");
    }
  }

  // ---- DOM: Append Message ----
  function appendMessage(role, content, opts = {}) {
    const msg = document.createElement("div");
    msg.className = `reva-msg ${role}`;

    const avatarLabel = role === "assistant" ? "IA" : "Eu";
    let bubbleContent = opts.markdown ? renderMarkdown(content) : escapeHtml(content);
    let actionsHtml = "";

    if (opts.actions && opts.actions.length) {
      actionsHtml = '<div class="reva-msg-actions">';
      opts.actions.forEach((a) => {
        actionsHtml += `<button class="reva-action-btn" data-type="${escapeHtml(a.type)}" data-url="${escapeHtml(a.url || "")}" data-label="${escapeHtml(a.label || "")}">${escapeHtml(a.label)}</button>`;
      });
      actionsHtml += "</div>";
    }

    msg.innerHTML = `
      <div class="reva-msg-avatar">${avatarLabel}</div>
      <div>
        ${opts.isVoice ? '<div class="reva-transcription"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 016 0v6a3 3 0 01-3 3z"/></svg>Mensagem de voz</div>' : ""}
        <div class="reva-msg-bubble">${bubbleContent}</div>
        ${actionsHtml}
      </div>
    `;

    messagesContainer.appendChild(msg);
    scrollToBottom();
  }

  function appendTranscription(text) {
    // Update the last user message to show what was transcribed
    const lastUserMsg = messagesContainer.querySelector(".reva-msg.user:last-of-type .reva-msg-bubble");
    if (lastUserMsg) {
      lastUserMsg.textContent = text;
    }
  }

  // ---- Typing indicator ----
  function showTyping() {
    if (typingEl) {
      typingEl.style.display = "flex";
      scrollToBottom();
    }
  }
  function hideTyping() {
    if (typingEl) typingEl.style.display = "none";
  }

  // ---- Clear Chat ----
  async function clearChat() {
    // Remove all messages from DOM
    messagesContainer.querySelectorAll(".reva-msg").forEach((el) => el.remove());
    // Show welcome again
    if (welcomeEl) welcomeEl.style.display = "";
    updateSuggestions();

    // Clear server-side session
    try {
      await fetch(API.clear, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({}),
      });
    } catch (err) {
      console.warn("[REVA] Clear session failed:", err);
    }
  }

  // ---- Input state (disable during streaming) ----
  function setInputState(enabled) {
    inputField.disabled = !enabled;
    sendBtn.disabled = !enabled;
    voiceBtn.disabled = !enabled;
    if (enabled) inputField.focus();
  }

  // ---- Input helpers ----
  function handleInputKeydown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function autoResizeInput() {
    inputField.style.height = "auto";
    inputField.style.height = Math.min(inputField.scrollHeight, 100) + "px";
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    });
  }

  // ---- Keyboard shortcut (Ctrl+K or Cmd+K) ----
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      togglePanel();
    }
    if (e.key === "Escape" && isOpen) {
      togglePanel();
    }
  });

  // ---- Boot ----
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
