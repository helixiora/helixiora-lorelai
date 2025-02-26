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

// Move the deleteConversation function outside of the DOMContentLoaded event listener
async function deleteConversation(conversationId) {
    try {
        const response = await makeAuthenticatedRequest(
            `/api/v1/conversation/${conversationId}/delete`,
            'DELETE'
        );

        console.log('Conversation deleted successfully');
        // Remove the conversation from the list
        const conversationItem = document.querySelector(`.conversation-item[data-conversation-id="${conversationId}"]`);
        if (conversationItem) {
            conversationItem.remove();
        }
        // If we're currently viewing this conversation, clear the chat and reset the URL
        if (window.location.pathname.includes(`/conversation/${conversationId}`)) {
            document.getElementById('messages').innerHTML = '';
            history.pushState(null, '', '/');
        }
    } catch (error) {
        console.error('Error deleting conversation:', error);
        if (error.message === '401') {
            // Token refresh failed, redirect to login
            window.location.href = '/logout';
        } else {
            alert('Failed to delete conversation. Please try again.');
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const sendButton = document.getElementById('sendButton');
    const messageInput = document.getElementById('messageInput');
    const messagesDiv = document.getElementById('messages');

    // Check and refresh token on page load
    checkAndRefreshToken();

    // Add this line at the beginning of the DOMContentLoaded event listener
    const username = document.body.dataset.username;

    function addMessage(content, isUser = true, isHTML = false, isSources = false, timestamp = null) {
        // Convert markdown content to HTML
        content = marked.parse(content);

        const messagesDiv = document.getElementById('messages'); // The main container for all messages

        const messageContainerDiv = document.createElement('div');
        messageContainerDiv.className = 'p-2';

        const messageContentDiv = document.createElement('div');
        if (isSources) {
            // make the sources div with smaller text
            messageContentDiv.className = 'inline-block rounded-lg p-4 bg-white text-sm';
        } else {
            messageContentDiv.className = 'inline-block rounded-lg p-4 bg-white';
        }
        messageContentDiv.style.overflowWrap = 'break-word';

        // Format timestamp
        // Format timestamp and only include dash if timestamp exists
        const timestampSection = timestamp
            ? ` - ${new Date(timestamp).toLocaleString()}: `
            : ': ';

        if (isUser) {
            messageContentDiv.innerHTML = `<strong>${username}</strong>${timestampSection}${content}`;
        } else {
            messageContentDiv.innerHTML = `<strong>Lorelai</strong>${timestampSection}${content}`;
        }
        messageContainerDiv.appendChild(messageContentDiv);
        messagesDiv.appendChild(messageContainerDiv); // Append the message to messagesDiv
        messagesDiv.scrollTop = messagesDiv.scrollHeight; // Scroll to the bottom of the chat
    }
    /**
     * Calculates the delay before making the next poll based on the attempt number.
     *
     * @param {number} attempt The current attempt number.
     * @returns {number} The delay in milliseconds.
     */
    function calculateDelay(attempt) {
        if (attempt <= 5) return 500; // 0.5 seconds == 500
        if (attempt <= 7) return 1000; // 1 second = 1000
        return 1500; // 1.5 seconds for all further attempts
    }

    /**
     * Fetches the result of a chat operation from the server using a provided task ID.
     * It checks the operation status and handles the response accordingly.
     *
     * @param {string} taskId The ID of the task for which to fetch the result.
     * @param {number} attempt The current attempt number.
     */
    async function pollForResponse(job_id, conversation_id, attempt = 1) {
        console.log(`Polling for response: ${job_id}, Attempt: ${attempt}`);
        const delay = calculateDelay(attempt);

        try {
            await new Promise(resolve => setTimeout(resolve, delay));

            const response = await makeAuthenticatedRequest(
                `/api/v1/chat?job_id=${job_id}`,
                'GET'
            );

            const data = await response.json();
            console.log('Response:', data);

            conversation_id = data.conversation_id;
            if (conversation_id) {
                //push the new url to the browser
                history.pushState(null, '', `/conversation/${conversation_id}`);
            }

            if (data.status === 'SUCCESS') {
                console.log('Operation completed successfully.');
                displaySuccessMessage(data.result);
            } else if (data.status === 'FAILED') {
                console.error('Operation failed:', data.error);
                if (data.error.error == 'Index not found. Please index something first.') {
                    displayErrorMessage('It looks like you haven\'t indexed any data yet. \
                        Please index some data first and try again, or use the direct-to-LLM \
                        option to get answers directly from the LLM model');
                } else {
                    displayErrorMessage('Operation failed. Please try again later.');
                }
            } else if (data.status === 'NO_RELEVANT_SOURCE') {
                console.error('No relevant source found.');
                displayErrorMessage('No relevant source found for the question. Please try again \
                    with a different question or ask the question directly to LLM.');
            } else if (attempt < 40) {
                console.log('Operation still in progress. Retrying...');
                pollForResponse(job_id, conversation_id, attempt + 1);
            } else {
                console.error('Error: No successful response after multiple attempts.');
                displayErrorMessage('Error: No successful response after multiple attempts.');
            }
        } catch (error) {
            console.error('Fetch error:', error);
            if (attempt < 20) {
                pollForResponse(job_id, conversation_id, attempt + 1);
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
        console.log('Result:', result);

        content = result.answer

        addMessage(content=content, isUser=false, false); // Display the answer

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
     * Handles 429 "Quota Exceeded" responses with a specific message and retry logic.
     *
     * @param {string} message The text message to send to the server.
     */
    async function sendMessage(message) {
        console.log('Sending message:', message);
        addMessage(message, true);
        showLoadingIndicator();

        try {
            const response = await makeAuthenticatedRequest('/api/v1/chat', 'POST', { message: message });

            if (!response.ok) {
                hideLoadingIndicator();

                if (response.status === 429) {
                    // Handle 429 Quota Exceeded
                    console.warn('Quota exceeded.');
                    hideLoadingIndicator();
                    addMessage('Quota exceeded. Please contact Lorelai support if you need to increase your quota.', false, false);
                } else if (response.status === 401) {
                    addMessage('Your session has expired. Please log in again.', false, false);
                } else {
                    addMessage('Error: Unable to send the message. Please try again later.', false, false);
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return;
            }

            const data = await response.json();

            if (data && data.job) {
                // Handle cases where the server response includes a job ID
                await pollForResponse(data.job, data.conversation_id);
            } else {
                // Handle cases where the server response might not include a job ID
                console.error('Server response did not include a job_id. Data received:', data);
                hideLoadingIndicator();
                addMessage('Error: The message could not be processed at this time. Please try again later.', false, false);
            }
        } catch (error) {
            console.error('Fetch error:', error);
            hideLoadingIndicator();

            if (error.message === 'Unauthorized') {
                addMessage('Your session has expired. Please log in again.', false, false);
            } else if (error.message.includes('429')) {
                addMessage('Quota exceeded. Please contact Lorelai support if you need to increase your quota.', false, false);
            } else {
                addMessage('Error: Unable to send the message. Please try again later.', false, false);
            }
            console.error('Send message error:', error);
            hideLoadingIndicator();
        }
    }

    async function get_conversation(conversationId) {
        try {
            const response = await makeAuthenticatedRequest(
                `/api/v1/conversation/${conversationId}`,
                'GET'
            );

            const data = await response.json();
            if (!data || data.length === 0) {
                console.warn('No messages found for this conversation.');
                window.location.href = '/';
                return;
            }

            for (const message of data) {
                addMessage(
                    content=message.message_content,
                    isUser=(message.sender === "user"),
                    isHTML=true,
                    isSources=false,
                    timestamp = message.created_at
                );
            }
        } catch (error) {
            console.error('Error fetching conversation:', error);
            window.location.href = '/';
        }
    }

    // Add a welcoming message on page load
    const welcomeMessage = `## Welcome to Lorelai!

We are excited to have you here! Feel free to ask any questions you have, we will automatically retrieve the most relevant data from the datasources you have configured.`;
    addMessage(
        content=welcomeMessage,
        isUser=false,
        isHTML=true,
        isSources=false
    );

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

    // if the page is loaded with a conversation_id in the url, load the conversation
    if (window.location.pathname.includes('/conversation/')) {
        const conversationId = window.location.pathname.split('/conversation/')[1];
        console.log('Loading conversation:', conversationId);
        // You may want to add an API call here to fetch the conversation messages
        conversation = get_conversation(conversationId);
    }


});

// New conversation button functionality
document.getElementById('newConversationBtn').addEventListener('click', function() {
    // Clear the chat messages
    document.getElementById('messages').innerHTML = '';
    // Reset the input field
    document.getElementById('messageInput').value = '';
    // You may want to add an API call here to create a new conversation on the server
    window.location.href = '/';
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
        window.location.href = `/conversation/${conversationId}`;
        // set the conversation_id in the session
        session["conversation_id"] = conversationId;
        console.log('Setting conversation_id in session:', session["conversation_id"]);

        // reload the page
        location.reload();
    });
});
