// New conversation button functionality
document.getElementById('newConversationBtn').addEventListener('click', function() {
    // Clear the chat messages
    document.getElementById('messages').innerHTML = '';
    // Reset the input field
    document.getElementById('messageInput').value = '';
    // You may want to add an API call here to create a new conversation on the server
});

// Make the textarea auto-expand
const messageInput = document.getElementById('messageInput');
messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// Add click event listeners to conversation items
document.querySelectorAll('.conversation-item').forEach(item => {
    item.addEventListener('click', function() {
        const conversationId = this.dataset.conversationId;
        // Add logic to load the selected conversation
        console.log('Loading conversation:', conversationId);
        // You may want to add an API call here to fetch the conversation messages
    });
});
