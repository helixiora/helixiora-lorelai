document.addEventListener('DOMContentLoaded', function () {
    const lorelai_tour = introJs().setOptions({
        steps: [
            {
                intro: "Welcome to LorelAI! \n\nThis is your profile page. Before you can ask questions, we first need to add a data source and run the indexer on them."
            },
            {
                element: '#authorize_button',
                intro: "Please connect your Google Drive here and select some documents to index."
            },
            {
                element: '#select_button',
                intro: "Thanks! Now please select some files from your Google Drive that you would like to have indexed."
            },
            {
                element: '#index_button',
                intro: "Great! You have connected a data source and selected files and/or folders to be indexed by LorelAI. Now, let's run the indexer on the selected files."
            }
        ],
        showStepNumbers: true,
        showBullets: false,
        showProgress: true,
        dontShowAgain: true,
        skipLabel: "x",
        doneLabel: "Finish"
    });

    // Start the tour if it's the first time or after resuming
    if (!sessionStorage.getItem('tourStep')) {
        if (!sessionStorage.getItem('tourCompleted')) {
            lorelai_tour.start();
        }
    } else {
        lorelai_tour.goToStep(parseInt(sessionStorage.getItem('tourStep'), 10));
    }

    // This function is called before the tour changes to the next step
    lorelai_tour.onbeforechange(function(targetElement) {

        if (['authorize_button', 'select_button', 'index_button'].includes(targetElement.id)) {
            // Save the current step to session storage
            sessionStorage.setItem('tourStep', lorelai_tour._currentStep + 1);

            // Pause the tour
            lorelai_tour.exit(); // Pause the tour

            // Add a click event listener to the target element
            targetElement.addEventListener('click', function() {
                lorelai_tour.nextStep(); // Resume the tour after the button click
            }, { once: true }); // Use `{ once: true }` to ensure it only triggers once


        }

    });

    // Clear tour progress when completed
    lorelai_tour.oncomplete(function() {
        sessionStorage.removeItem('tourStep');
        sessionStorage.setItem('tourCompleted', 'true');
    });

    // Start the tour
    lorelai_tour.start()
});
