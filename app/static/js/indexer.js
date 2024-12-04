function startIndexing(type) {
    $('#statusMessage').hide().removeClass('alert-danger alert-success').addClass('alert-info').text(`Starting ${type} indexing...`).show();

    makeAuthenticatedRequest(`/api/v1/admin/index/${type}`, 'POST')
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
            $('#statusMessage').text(`${type} indexing is in progress...`);

            // Initialize job statuses
            let jobStatuses = data.jobs.map(job => ({ jobId: job, state: 'pending' }));

            // Check the status of each job returned
            jobStatuses.forEach(jobStatus => {
                checkStatus(jobStatus, type, jobStatuses);
            });
        })
        .catch(error => {
            $('#statusMessage').removeClass('alert-info').addClass('alert-danger').text(`Failed to start ${type} indexing: ` + error.message);
        });
}

function checkStatus(jobStatus, type, jobStatuses) {
    console.log(jobStatus);
    makeAuthenticatedRequest(`/api/v1/admin/indexer/job-status/${jobStatus.jobId}`, 'GET')
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

            jobStatus.state = data.state;

            switch (data.state) {
                case 'started':
                    $('#statusMessage').removeClass('alert-danger alert-success').addClass('alert-info').text(`${type} indexing is in progress...`);
                    setTimeout(() => checkStatus(jobStatus, type, jobStatuses), 1000);
                    break;
                case 'pending':
                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`${type} indexing is pending for job ${jobStatus.jobId}.`);

                    setTimeout(() => checkStatus(jobStatus, type, jobStatuses), 1000);
                    break;
                case 'queued':
                    $('#statusMessage').removeClass('alert-info alert-danger').addClass('alert-warning').text(`${type} indexing is queued for job ${jobStatus.jobId}.`);
                    setTimeout(() => checkStatus(jobStatus, type, jobStatuses), 1000);
                    break;
                case 'finished':
                    $('#statusMessage').removeClass('alert-info alert-danger').addClass('alert-success').text(`${type} indexing is finished for job ${jobStatus.jobId}.`);
                    break;
                case 'failed':
                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`${type} indexing failed for job ${jobStatus.jobId}.`);
                    break;
                case 'unknown':
                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`${type} indexing ${data.state} for job ${jobStatus.jobId}.`);
                    break;
                default:
                    $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text(`Unknown error occurred: data.state: ${data.state}.`);
            }

            // Check if all jobs are finished
            if (jobStatuses.every(job => job.state === 'done' || job.state === 'failed')) {
                $('#statusMessage').removeClass('alert-info').addClass('alert-success').text(`${type} indexing completed.`);
            }
        })
        .catch(error => {
            $('#statusMessage').removeClass('alert-info alert-success').addClass('alert-danger').text('Error checking task status.');
        });
}
