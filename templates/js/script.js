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
     * Calculates the delay before making the next poll based on the attempt number.
     * 
     * @param {number} attempt The current attempt number.
     * @returns {number} The delay in milliseconds.
     */
    function calculateDelay(attempt) {
        if (attempt <= 5) return 500; // 0.5 seconds
        if (attempt <= 7) return 1000; // 1 second
        return 1500; // 1.5 seconds for all further attempts
    }

    /**
     * Fetches the result of a chat operation from the server using a provided task ID.
     * It checks the operation status and handles the response accordingly.
     * 
     * @param {string} taskId The ID of the task for which to fetch the result.
     * @param {number} attempt The current attempt number.
     */
    async function pollForResponse(taskId, attempt = 1) {
        console.log(`Polling for response: ${taskId}, Attempt: ${attempt}`);
        const delay = calculateDelay(attempt);

        try {
            await new Promise(resolve => setTimeout(resolve, delay));
            const response = await fetch(`/chat?task_id=${taskId}`);
            const data = await response.json();

            if (data.status === 'SUCCESS') {
                console.log('Operation completed successfully.');
                displaySuccessMessage(data.result);
            } else if (data.status === 'FAILED') {
                console.error('Operation failed:', data.error);
                displayErrorMessage('Operation failed. Please try again later.');
            } else if (attempt < 9) {
                console.log('Operation still in progress. Retrying...');
                pollForResponse(taskId, attempt + 1);
            } else {
                console.error('Error: No successful response after multiple attempts.');
                displayErrorMessage('Error: No successful response after multiple attempts.');
            }
        } catch (error) {
            console.error('Fetch error:', error);
            if (attempt < 9) {
                pollForResponse(taskId, attempt + 1);
            } else {
                displayErrorMessage('Error: Unable to retrieve response.');
            }
        }
    }

    /**
     * Displays the success message and any sources if available.
     * 
     * @param {Object} result The result object from the server.
     */
    function displaySuccessMessage(result) {
        hideLoadingIndicator();
        addMessage(result.answer, false, false); // Display the answer

        if (result.source && result.source.length > 0) {
            const sourceText = result.source.map(src => `<li><a href="${src.source}">${src.title} (score: ${src.score})</a></li>`).join('');
            addMessage(`<p><strong>Sources:</strong></p><ol type='1' class='text-left list-decimal'>${sourceText}</ol>`, false, true, true);
        }
    }

    /**
     * Displays an error message to the user.
     * 
     * @param {string} message The error message to display.
     */
    function displayErrorMessage(message) {
        hideLoadingIndicator();
        addMessage(message, false, false);
    }

    
    /**
     * Sends a message to the server and handles the response.
     * Shows a loading indicator while waiting for the server's response.
     * Upon receiving a response, it triggers fetching the result with the provided request ID.
     * If an error occurs during the fetch operation, it logs the error and displays an error message.
     * 
     * @param {string} message The text message to send to the server.
     */
    async function sendMessage(message) {
        console.log('Sending message:', message);
        addMessage(message, true); // Display the message as sent by the user
        showLoadingIndicator(); // Show the loading indicator to indicate that the message is being processed

        fetch('/chat', {
            method: 'POST',
            body: JSON.stringify({message: message}),
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            // Check if the server has accepted the message and is processing it
            if (data.task_id) {
                pollForResponse(data.task_id); // Begin polling for the response based on the provided task ID
            } else {
                // Handle cases where the server response might not include a task_id due to an error or other issue
                console.error('Server response did not include a task_id.');
                hideLoadingIndicator();
                addMessage('Error: The message could not be processed at this time. Please try again later.', false, false); // Display a generic error message
            }
        })
        .catch(error => {
            // Handle network errors or issues with the fetch operation itself
            console.error('Fetch error:', error);
            hideLoadingIndicator(); // Hide the loading indicator as there's been an error
            addMessage('Error: Unable to send the message. Please try again later.', false, false); // Display an error message to the user
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