document.addEventListener('DOMContentLoaded', function () {
    introJs.tour().setOptions({
        steps: [
            {
                intro: "Welcome to Lorelai! Before you get started asking questions about your data, we need to configure the system. Please follow the steps below."
            },
            {
                element: document.querySelector('.profile-link'),
                intro: "Let's go to your profile to connect some data sources."
            },
        ]
    }).onComplete(function() {
        window.location.href = '/profile';
    }).
    start();
});
