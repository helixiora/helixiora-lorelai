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
        // Use innerHTML for bot messages that need to render HTML content
        if (isUser) {
            // get the user_username from the session
            const username = '{{ session.get('user_username') }}';
            messageContentDiv.innerHTML = '<strong>' + username + '</strong>: ' + content;
        } else {
            messageContentDiv.innerHTML = '<strong>Lorelai</strong>: ' + content;
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
    async function pollForResponse(jobId, attempt = 1) {
        console.log(`Polling for response: ${jobId}, Attempt: ${attempt}`);
        const delay = calculateDelay(attempt);

        try {
            await new Promise(resolve => setTimeout(resolve, delay));
            const response = await fetch(`/api/chat?job_id=${jobId}`);
            const data = await response.json();

            console.log('Response:', data);

            thread_id = data.thread_id;
            if (thread_id) {
                //push the new url to the browser
                history.pushState(null, '', `/conversation/${thread_id}`);
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
            } else if (attempt < 20) {
                console.log('Operation still in progress. Retrying...');
                pollForResponse(jobId, attempt + 1);
            } else {
                console.error('Error: No successful response after multiple attempts.');
                displayErrorMessage('Error: No successful response after multiple attempts.');
            }
        } catch (error) {
            console.error('Fetch error:', error);
            if (attempt < 20) {
                pollForResponse(jobId, attempt + 1);
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

        content = result.answer + '\n\n'

        if (result.datasource == 'Direct') {
            content += '<br/><p><strong>Source:</strong> Direct answer from LLM</p>';
        }
        else if (result.source && result.source.length > 0) {
            const sourceText = result.source.map(src => {
                let score = parseFloat(src.score);
                let scoreDisplay = 'N/A';
                let warningSymbol = '';

                if (!isNaN(score)) {
                    scoreDisplay = score.toFixed(2);
                    warningSymbol = score < 50 ? '⚠️ ' : ''; // Add warning symbol if score is less than 10
                }

                return `<li><a href="${src.source}">${src.title} (score: ${scoreDisplay}${warningSymbol})</a></li>`;
            }).join('');
            content += `<br/><p><strong>Sources (from ${result.datasource}):</strong></p><p><ol type='1' class='text-left list-decimal'>${sourceText}</ol></p>`;
        } else {
            content += 'No sources found.';
        }
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
    const datasourceSelect = document.getElementById('datasourceSelect');
    const selectedDatasource = datasourceSelect.value;
    console.log('Selected Datasource:', selectedDatasource);
    console.log('Sending message:', message);
    addMessage(message, true); // Display the message as sent by the user
    showLoadingIndicator(); // Show the loading indicator to indicate that the message is being processed

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            body: JSON.stringify({message: message, datasource: selectedDatasource}),
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            hideLoadingIndicator();

            if (response.status === 429) {
                // Handle 429 Quota Exceeded
                console.warn('Quota exceeded.');
                hideLoadingIndicator();
                addMessage('Quota exceeded. Please contact Lorelai support if you need to increase your quota.', false, false);
            } else {
                addMessage('Error: Unable to send the message. Please try again later.', false, false);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

        } else {

            const data = await response.json();

            // Check if the server has accepted the message and is processing it
            if (data.job) {
                pollForResponse(data.job); // Begin polling for the response based on the provided job ID
            } else {
                // Handle cases where the server response might not include a job ID due to an error or other issue
                console.error('Server response did not include a job_id. Data received: ', data.job);
                hideLoadingIndicator();
                addMessage('Error: The message could not be processed at this time. Please try again later.', false, false); // Display a generic error message
            }
        }
    } catch (error) {
        // Handle network errors or issues with the fetch operation itself
        console.error('Fetch error:', error);
        hideLoadingIndicator(); // Hide the loading indicator as there's been an error
        addMessage('Error: Unable to send the message. Please try again later.', false, false); // Display an error message to the user
    }
}


async function get_conversation(conversationId) {
    // add an API call here to fetch the conversation messages
    console.log('Fetching conversation:', conversationId);
    // get /api/conversation/conversationId
    fetch(`/api/conversation/${conversationId}`)
        .then(response => response.json())
        .then(data => {
            for (const message of data) {
                if (message.sender == "user") {
                    addMessage(
                        content=message.message_content,
                        isUser=true,
                        isHTML=true,
                        isSources=false
                    );
                } else {
                    addMessage(
                        content=message.message_content,
                        isUser=false,
                        isHTML=true,
                        isSources=false
                    );
                }
            }
        });
}

    // Add a welcoming message on page load
    const welcomeMessage = `## Welcome to Lorelai!

We are excited to have you here! Feel free to ask any questions you have and set the datasource to the datasource you want to use.`;
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
        // set the thread_id in the session
        session["thread_id"] = conversationId;
        console.log('Setting thread_id in session:', session["thread_id"]);

        // reload the page
        location.reload();
    });
});
