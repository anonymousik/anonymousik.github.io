// detect.js

// We give the browser a moment to load everything.
document.addEventListener('DOMContentLoaded', function() {
    // We check for the bait variable after a short delay.
    setTimeout(function() {
        // 'canRunAds' is defined in our bait file, ads.js
        if (typeof canRunAds === 'undefined') {
            // The bait was not loaded, which means an AdBlocker is active.
            // Unleash the modal.
            var modal = document.getElementById('adblock-modal');
            modal.style.display = 'block';

            // We also lock the body's scroll to make the modal more... persuasive.
            document.body.style.overflow = 'hidden';
        } else {
            // No AdBlocker detected. The user is compliant... for now.
            console.log('No AdBlocker detected. Lucky you.');
        }
    }, 500); // 500ms delay
});
