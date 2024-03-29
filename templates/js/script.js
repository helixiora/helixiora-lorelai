function typeMessage(message, parentElement, isHTML, callback) {
    if (isHTML) {
        // Immediately set HTML content
        parentElement.innerHTML = message;
        if (callback) callback();
    } else {
        // Proceed with typing animation for plain text
        const typingSpeed = 50;
        let charIndex = 0;

        function typing() {
            if (charIndex < message.length) {
                parentElement.textContent += message[charIndex++];
                setTimeout(typing, typingSpeed);
            } else if (callback) {
                callback();
            }
        }

        typing();
    }
}

// Utility function to escape HTML if necessary
function escapeHTML(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Create a loading indicator that matches the bot message styling
function showLoadingIndicator() {
    // Create the loading container div
    const loadingContainer = document.createElement('div');
    loadingContainer.id = 'loadingContainer';
    loadingContainer.className = 'p-2 text-right';

    // Create the loading div with the dot-pulse class
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'dot-pulse';

    // Append the loading div to the loading container
    loadingContainer.appendChild(loadingDiv);

    // Append the loading container to the messages div
    const messagesDiv = document.getElementById('messages');
    messagesDiv.appendChild(loadingContainer);
    messagesDiv.scrollTop = messagesDiv.scrollHeight; // Scroll to the bottom
}

// Remove the loading indicator from the DOM
function hideLoadingIndicator() {
    const loadingContainer = document.getElementById('loadingContainer');
    if (loadingContainer) {
        loadingContainer.remove();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const sendButton = document.getElementById('sendButton');
    const messageInput = document.getElementById('messageInput');
    const messagesDiv = document.getElementById('messages');

    function addMessage(content, isUser = true, isHTML = false, isSources = false) {
        const messagesDiv = document.getElementById('messages'); // The main container for all messages
    
        const messageContainerDiv = document.createElement('div');
        messageContainerDiv.className = 'p-2 ' + (isUser ? 'text-left' : 'text-right');
    
        const messageContentDiv = document.createElement('div');
        if (isSources) {
            // make the sources div with smaller text
            messageContentDiv.className = 'inline-block rounded-lg p-4 bg-white text-sm';
        } else {
            messageContentDiv.className = 'inline-block rounded-lg p-4 bg-white';
        }
        messageContentDiv.style.overflowWrap = 'break-word';
        if (isHTML) {
            // Use innerHTML for bot messages that need to render HTML content
            console.log('innerHTML:', content);
            messageContentDiv.innerHTML = content;
        } else {
            console.log('textContent:', content);
            messageContentDiv.textContent = content; // Use textContent for user messages to avoid HTML
        }
    
        messageContainerDiv.appendChild(messageContentDiv);
        messagesDiv.appendChild(messageContainerDiv); // Append the message to messagesDiv
        messagesDiv.scrollTop = messagesDiv.scrollHeight; // Scroll to the bottom of the chat
    }

    function extractTextFromJSON(obj) {
        let text = '';
        if (typeof obj === 'object' && !Array.isArray(obj)) {
            // If it's an object, iterate over its properties
            for (let key in obj) {
                if (typeof obj[key] === 'string') {
                    // Add the string value as a paragraph
                    let paragraphs = obj[key].split('. ').join('.\n\n');
                    text += paragraphs.trim() + '\n\n';
                } else {
                    // If it's a nested structure, recursively process it
                    text += extractTextFromJSON(obj[key]);
                }
            }
        } else if (Array.isArray(obj)) {
            // If it's an array, process each element
            obj.forEach(item => {
                text += extractTextFromJSON(item);
            });
        } else if (typeof obj === 'string') {
            // If it's a string, just add it
            let paragraphs = obj.split('. ').join('.\n\n');
            text += paragraphs.trim() + '\n\n';
        }
        return text.replace(/[\r\n]{3,}/g, '\n\n'); // Replace 3 or more newlines with just two
    }


    /**
     * Fetches the result of a chat operation from the server using a provided request ID.
     * It checks the operation status and handles the response accordingly.
     * If the operation is completed, it processes and displays the result.
     * If an error occurred during the operation, it shows an error message.
     * If the operation is still in progress, it retries fetching the result after a delay.
     * 
     * @param {string} requestId The ID of the request for which to fetch the result.
     */
    async function pollForResponse(taskId) {
        console.log('Polling for response:', taskId);
        setTimeout(function() {
            fetch(`/chat?task_id=${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'SUCCESS') {
                    hideLoadingIndicator();
                    // console.log('Response:', data.result);

                    // Extract the text content from the JSON result
                    const text = extractTextFromJSON(data.result);

                    // Format the message and the sources into html
                    let message = data.result.answer;
                    addMessage(message, isUser=false, isHTML=false); // Display the message
                    
                    let sourceText = '';
                    if (data.result.source) {
                        data.result.source.forEach(source => {
                            sourceText += `<li><a href="${source.source}">${source.title}</a></li>`;
                        });
                    }
                    addMessage(message="<p><strong>Sources:</strong></p><ol type='1'>" + sourceText + "</ol>", isUser=false, isHTML=true, isSources=true); 
                } else {
                    pollForResponse(taskId); // Keep polling if pending
                }
            });
        }, 500); // Adjust polling interval as needed
    }


    /**
     * Sends a message to the server and handles the response.
     * Shows a loading indicator while waiting for the server's response.
     * Upon receiving a response, it triggers fetching the result with the provided request ID.
     * If an error occurs, it logs the error and shows an error message to the user.
     * 
     * @param {string} text The text message to send to the server.
     */
    async function sendMessage(message) {
        console.log('Sending message:', message);
        addMessage(message, true);
        showLoadingIndicator();
        fetch('/chat', {
            method: 'POST',
            body: JSON.stringify({message: message}),
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            pollForResponse(data.task_id);
        });
    }

    sendButton.addEventListener('click', function() {
        const text = messageInput.value;
        if (text.trim() !== '') {
            sendMessage(text);
            messageInput.value = '';
        }
    });

    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendButton.click();
        }
    });
});