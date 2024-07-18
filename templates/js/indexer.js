function startIndexing(type) {
    $('#statusMessage').hide().removeClass('alert-danger alert-success').addClass('alert-info').text(`Starting ${type} indexing...`).show();
    $('#progressBarContainer').hide();
    $('#logArea').val('');
    logMessage(`==> 1. Starting indexing for ${type}...`);

    fetch(`/admin/index/${type}`, { method: 'POST' })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                return response.json().then(data => {
                    throw new Error(data.error || 'Unknown error');
                });
            }
        })
        .then(data => {
            $('#statusMessage').text(`${capitalize(type)} indexing is in progress...`);
            $('#progressBarContainer').show();
            $('#progressBar').css('width', '0%').attr('aria-valuenow', 0).text('0%');
            logMessage(`===> ${capitalize(type)} indexing started.`);

            // Initialize job statuses
            let jobStatuses = data.jobs.map(job => ({ jobId: job, state: 'pending' }));

            // Check the status of each job returned
            jobStatuses.forEach(jobStatus => {
                checkStatus(jobStatus, type, jobStatuses);
            });
        })
        .catch(error => {
            $('#statusMessage').removeClass('alert-info').addClass('alert-danger').text(`Failed to start ${type} indexing: ` + error.message);
            logMessage(`Failed to start ${type} indexing: ${error.message}`);
        });
}

function checkStatus(jobStatus, type, jobStatuses) {
    fetch(`/admin/job-status/${jobStatus.jobId}`)
        .then(response => response.json())
        .then(data => {
            logMessage('==> 2. checkStatus job: ' + jobStatus.jobId + ', type: ' + type + ', state: ' + data.state);

            jobStatus.state = data.state;

            switch (data.state) {
                case 'started':
                    $('#statusMessage').removeClass('alert-danger alert-success').addClass('alert-info').text(`${capitalize(type)} indexing is in progress...`);

                    let current = data.current || 0;
                    let total = data.total || 1; // Default to 1 to avoid division by zero
                    let percent = (current / total) * 100;

                    $('#progressBar').css('width', percent + '%').attr('aria-valuenow', percent).text(Math.round(percent) + '%');

                    setTimeout(() => checkStatus(jobStatus, type, jobStatuses), 1000);
                    break;
                case 'queued':
                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`${capitalize(type)} indexing is queued for job ${jobStatus.jobId}.`);

                    setTimeout(() => checkStatus(jobStatus, type, jobStatuses), 1000);
                    break;
                case 'finished':
                    $('#statusMessage').removeClass('alert-info alert-danger').addClass('alert-success').text(`${capitalize(type)} indexing is finished for job ${jobStatus.jobId}.`);
                    logMessage(`===> Job logs`);
                    updateLogs(data.metadata.logs);
                    logMessage(`===> /Job logs`);

                    logMessage(`${capitalize(type)} indexing completed successfully for job ${jobStatus.jobId}.`);
                    break;
                case 'failed':
                    logMessage(`===> Job logs`);
                    updateLogs(data.metadata.logs);
                    logMessage(`===> /Job logs`);

                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`${capitalize(type)} indexing failed for job ${jobStatus.jobId}.`);
                case 'unknown':
                    logMessage(`===> Job logs`);
                    updateLogs(data.metadata.logs);
                    logMessage(`===> /Job logs`);

                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`${capitalize(type)} indexing ${data.state} for job ${jobStatus.jobId}.`);
                    break;
                default:
                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`Unknown error occurred: data.state: ${data.state}.`);
            }

            // Check if all jobs are finished
            if (jobStatuses.every(job => job.state === 'done' || job.state === 'failed')) {
                $('#statusMessage').removeClass('alert-info').addClass('alert-success').text(`${capitalize(type)} indexing completed.`);
                $('#progressBar').css('width', '100%').attr('aria-valuenow', 100).text('100%');
            }
        }).catch(error => {
            $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text('Error checking task status.');
            logMessage('Error checking task status: ' + error.message);
        });
}

function updateLogs(logs) {
    logs = logs || [];
    logs.forEach(log => logMessage(typeof log === 'object' ? JSON.stringify(log, null, 2) : log));
}

function logMessage(message) {
    let logArea = $('#logArea');
    let formattedMessage;

    if (typeof message === 'object') {
        // If the message is an object, format it as a pretty-printed JSON string
        formattedMessage = 'log (JSON):' + JSON.stringify(message, null, 2);
    } else {
        // Otherwise, treat the message as a plain string
        formattedMessage = 'log:' + message;
    }

    logArea.val(logArea.val() + formattedMessage + '\n');
    logArea.scrollTop(logArea[0].scrollHeight);
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}
