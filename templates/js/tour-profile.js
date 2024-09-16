document.addEventListener('DOMContentLoaded', function () {
    let isPaused = false;

    const lorelai_tour = introJs().setOptions({
        steps: [
            {
                intro: "Welcome to LorelAI! \n\nThis is your profile page. Before you can ask questions, we first need to add a data source and run the indexer on them."
            },
            {
                element: '#authorize_button',
                intro: "Please connect your Google Drive by clicking this button.",
                disableInteraction: true
            },
            {
                element: '#select_button',
                intro: "Great! Now that we're connected to Google Drive, please select some folders or documents to index.",
                disableInteraction: true
            },
            {
                element: '#index_user_button',
                intro: "This button will index the selected files for your personal use.",
                disableInteraction: true
            },
            {
                element: '#index_org_button',
                intro: "This button will index the selected files for your entire organization.",
                disableInteraction: true
            }
        ],
        showStepNumbers: true,
        showBullets: false,
        showProgress: true,
        exitOnOverlayClick: false,
        exitOnEsc: false,
        disableInteraction: true
    });

    let currentStep = 0;

    lorelai_tour.onbeforechange(function(targetElement) {
        currentStep = this._currentStep;

        if (currentStep === 1) { // Authorize button
            pauseTour();
            document.getElementById('authorize_button').addEventListener('click', handleAuthorizeClick, { once: true });
        } else if (currentStep === 2) { // Select button
            pauseTour();
            document.getElementById('select_button').addEventListener('click', handleSelectClick, { once: true });
        } else if (currentStep === 3 || currentStep === 4) { // Indexing buttons
            pauseTour();
            document.getElementById('index_user_button').addEventListener('click', handleIndexClick, { once: true });
            document.getElementById('index_org_button').addEventListener('click', handleIndexClick, { once: true });
        }
    });

    function handleAuthorizeClick() {
        // Here you would typically check if the Google Drive connection was successful
        // For this example, we'll just assume it was and continue the tour after a delay
        setTimeout(() => {
            resumeTour();
            lorelai_tour.goToStep(3); // Go to select files step
        }, 1000);
    }

    function handleSelectClick() {
        // Here you would typically check if files were selected
        // For this example, we'll just assume they were and continue the tour after a delay
        setTimeout(() => {
            resumeTour();
            lorelai_tour.goToStep(4); // Go to indexing buttons step
        }, 1000);
    }

    function pauseTour() {
        isPaused = true;
    }

    function resumeTour() {
        isPaused = false;
        if (window.resumeTour) {
            window.resumeTour();
            window.resumeTour = null;
        }
    }

    function handleIndexClick() {
        // Here you would typically start the indexing process
        // For this example, we'll just end the tour and redirect to the main page
        lorelai_tour.exit();
        sessionStorage.setItem('tourCompleted', 'true');
        window.location.href = '/main'; // Replace with your main page URL
    }

    // Start the tour if it's not completed
    if (!sessionStorage.getItem('tourCompleted')) {
        // lorelai_tour.start();
    }
});
