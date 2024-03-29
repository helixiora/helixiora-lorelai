function typeMessage(message, parentElement, callback) {
    const typingSpeed = 50; // Milliseconds per character
    let paragraphs = message.split('\n\n'); // Split the message into paragraphs
    let currentParagraphIndex = 0;
    let charIndex = 0;
    let currentParagraphElement = document.createElement('p');
    parentElement.appendChild(currentParagraphElement); // Start with the first paragraph element

    function typing() {
        if (currentParagraphIndex < paragraphs.length) {
            if (charIndex < paragraphs[currentParagraphIndex].length) {
                currentParagraphElement.textContent += paragraphs[currentParagraphIndex][charIndex];
                charIndex++;
                setTimeout(typing, typingSpeed);
            } else {
                // Finished typing the current paragraph
                charIndex = 0;
                currentParagraphIndex++;
                if (currentParagraphIndex < paragraphs.length) {
                    currentParagraphElement = document.createElement('p'); // Start a new paragraph
                    parentElement.appendChild(currentParagraphElement);
                }
                setTimeout(typing, typingSpeed);
            }
        } else if (callback) {
            callback();
        }
    }

    typing();
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

    function addMessage(content, isUser = true) {
        const messagesDiv = document.getElementById('messages'); // The main container for all messages

        if (isUser) {
            // If it's a user message, append directly to messagesDiv
            const userMessageDiv = document.createElement('div');
            userMessageDiv.className = 'p-2 text-left';

            const messageP = document.createElement('p');
            messageP.className = 'inline-block rounded-lg p-4 bg-white';
            messageP.textContent = content; // Use textContent for user messages to avoid HTML
            userMessageDiv.appendChild(messageP);

            messagesDiv.appendChild(userMessageDiv); // Append the user message to messagesDiv
        } else {
            // If it's a bot message, first hide the loading indicator and then append the message
            hideLoadingIndicator();

            const botMessageDiv = document.createElement('div');
            botMessageDiv.className = 'p-2 text-right'; // Align to the right for bot messages

            const messageContentDiv = document.createElement('div');
            messageContentDiv.className = 'inline-block rounded-lg p-4 bg-white';
            messageContentDiv.style.width = '690px';
            messageContentDiv.style.textAlign = 'left';
            messageContentDiv.style.overflowWrap = 'break-word';

            // Use innerHTML to allow for HTML content like <br> in bot messages
            typeMessage(content, messageContentDiv, () => {
                messagesDiv.scrollTop = messagesDiv.scrollHeight; // Scroll to the bottom
            });

            botMessageDiv.appendChild(messageContentDiv); // Append the typed message to the bot message div
            messagesDiv.appendChild(botMessageDiv); // Append the bot message to messagesDiv
        }

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
    async function fetchResult(requestId) {
        try {
            const response = await fetch(`{{ url_for('chat') }}?requestID=${requestId}`);

            // Check if the HTTP response is successful
            if (!response.ok) {
                throw new Error(`Server responded with status ${response.status}`);
            }

            const data = await response.json();

            switch (data.status) {
                case 'completed':
                    hideLoadingIndicator();
                    try {
                        addMessage(data.output, false);
                    } catch (error) {
                        console.error('Error parsing response:', error);
                        addMessage("Error parsing response.", false);
                    }
                    break;
                case 'error':
                    addMessage("Error processing request.", false);
                    break;
                default:
                    // Assume status is pending or in progress, retry after a delay
                    setTimeout(() => fetchResult(requestId), 3000);
                    break;
            }
        } catch (error) {
            // This catch block now handles network errors as well as errors thrown manually
            hideLoadingIndicator();
            console.error('Error fetching result:', error);
            addMessage("Error fetching result.", false);
        }
    }


    /**
     * Sends a message to the server and handles the response.
     * Shows a loading indicator while waiting for the server's response.
     * Upon receiving a response, it triggers fetching the result with the provided request ID.
     * If an error occurs, it logs the error and shows an error message to the user.
     * 
     * @param {string} text The text message to send to the server.
     */
    async function sendMessage(text) {
        try {
            addMessage(text); // Display the message being sent
            showLoadingIndicator(); // Show loading indicator

            // Send the message to the server
            const response = await fetch(`/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: text }),
            });

            // Check if the HTTP response is successful
            if (!response.ok) {
                throw new Error(`Server responded with status ${response.status}`);
            }

            const data = await response.json();

            // Handle the server's response data
            if (data.requestID) {
                fetchResult(data.requestID);
            } else {
                // Handle unexpected response format
                throw new Error("Invalid response format from server");
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage("Error sending request.", false);
        } finally {
            hideLoadingIndicator(); // Always hide the loading indicator, whether the request succeeded or failed
        }
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