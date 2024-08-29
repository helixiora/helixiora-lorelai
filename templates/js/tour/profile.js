document.addEventListener('DOMContentLoaded', function () {
    lorelai_tour = introJs.tour()
    lorelai_tour.setOptions({
        steps: [
            {
                intro: "This is your profile page. Before you will be able to ask questions, we first need to add a data source and run the indexer on them." },
            {
                element: document.getElementById("authorize_button"),
                intro: "Please connect your google drive here and select some documents to index"
            },
            {
                element: document.getElementById("select_button"),
                intro: "Thanks, now please go and select some files from your Google Drive you would like to have indexed"
            },
            {
                element: document.getElementById("index_button"),
                intro: "Great, you have connected a datasource and selected some files and/or folders to be indexed by Lorelai. Now, let's run the indexer to index the selected files."
            }
        ]
    })

    // Start the tour if it's the first time or after resuming
    if (!sessionStorage.getItem('tourStep')) {
        lorelai_tour.start();
    } else {
        lorelai_tour.goToStep(parseInt(sessionStorage.getItem('tourStep'), 10)).start();
    }

    lorelai_tour.onbeforechange(function(targetElement) {
        if (targetElement.id in ['authorize_button', 'select_button']) {
            sessionStorage.setItem('tourStep', lorelai_tour._currentStep + 1);
        }
        if (targetElement.id === 'index_button') {
            intro.exit(); // Pause the tour
            document.getElementById('index_button').addEventListener('click', function() {
                intro.nextStep(); // Resume the tour after the button click
            }, { once: true }); // Use `{ once: true }` to ensure it only triggers once
        }
    });

    // Clear tour progress when completed
    lorelai_tour.oncomplete(function() {
        sessionStorage.removeItem('tourStep');
    });

    lorelai_tour.start()
});
