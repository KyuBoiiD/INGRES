const inputField = document.getElementById("user-input");
const chatBox = document.getElementById("chat-box");

// Send on Enter key
inputField.addEventListener("keypress", function(event) {
    if (event.key === "Enter") sendMessage();
});

async function sendMessage() {
    const text = inputField.value;
    if (!text) return;

    // 1. Add User Message to Chat
    addMessage(text, "user-msg");
    inputField.value = "";
    
    // Show loading...
    const loadingDiv = addMessage("Thinking...", "bot-msg");

    try {
        // 2. Send to Backend
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();
        
        // 3. Update Chat with Response
        loadingDiv.innerHTML = data.response;
        
        // If there's a table (Query result), append it
        if (data.table) {
            loadingDiv.innerHTML += `<div class="table-container">${data.table}</div>`;
        }
        
    } catch (error) {
        loadingDiv.innerHTML = "❌ Error connecting to server.";
    }
}

function addMessage(text, className) {
    const div = document.createElement("div");
    div.className = `message ${className}`;
    div.innerHTML = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight; // Auto scroll to bottom
    return div;
}