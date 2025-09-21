/**
 * Main JavaScript for Irene Voice Assistant Web Interface
 */

// Get messages container
const messages = document.getElementById('messages');

/**
 * Add a message to the message display
 * @param {string} text - Message text
 * @param {string} type - Message type ('error' or other)
 */
function addMessage(text, type) {
    const div = document.createElement('div');
    div.className = 'message' + (type === 'error' ? ' error' : '');
    div.textContent = new Date().toLocaleTimeString() + ': ' + text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

/**
 * Send command to the API
 */
async function sendCommand() {
    const input = document.getElementById('commandInput');
    const command = input.value.trim();
    if (command) {
        try {
            const response = await fetch('/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({command: command})
            });
            const result = await response.json();
            addMessage(result.response || result.error || 'Command processed', result.success ? 'info' : 'error');
        } catch (error) {
            addMessage('Error sending command: ' + error.message, 'error');
        }
        input.value = '';
    }
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const commandInput = document.getElementById('commandInput');
    if (commandInput) {
        commandInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendCommand();
        });
    }
});
