// ===================================================================
// 1. Basic Setup & Log Message
// ===================================================================
console.log('base.js loaded');

// ===================================================================
// 2. Flash Message Handling
// ===================================================================
// Hide flash messages after 5 seconds
setTimeout(function() {
    var alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        alert.style.display = 'none';
    });
}, 5000);

// ===================================================================
// 3. Auto Logout on Inactivity
// ===================================================================

// URL to logout (rendered from the server)
const logoutUrl = "{{ url_for('logout') }}";

// Variables for tracking idle time
let idleTime = 0;
const maxIdleTime = 35 * 60 * 1000; // 35 minutes (comment noted as 30 minutes in original, but calculation is 35 minutes)

// Function to reset the idle time counter
function resetIdleTime() {
    idleTime = 0;
}

// Increment the idle time counter and log out if the maximum idle time is exceeded
function timerIncrement() {
    idleTime += 60000; // Increase idle time by 1 minute
    if (idleTime >= maxIdleTime) {
        window.location.href = logoutUrl;
    }
}

// Set up the idle time counter and event listeners once the page loads
window.onload = function() {
    // Increment idle time every minute
    setInterval(timerIncrement, 60000); // 1 minute

    // Reset idle timer on mouse movement or key press
    window.onmousemove = resetIdleTime;
    window.onkeypress = resetIdleTime;
};

// ===================================================================
// 4. "Back to Top" Button Functionality
// ===================================================================

// Show or hide the "Back to Top" button when the user scrolls
window.onscroll = function() {
    scrollFunction();
};

function scrollFunction() {
    const topBtn = document.getElementById("topBtn");
    if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
        topBtn.style.display = "block";
    } else {
        topBtn.style.display = "none";
    }
}

// Scroll to the top of the page when the "Back to Top" button is clicked
function topFunction() {
    document.body.scrollTop = 0;             // For Safari
    document.documentElement.scrollTop = 0;    // For Chrome, Firefox, IE, and Opera
}
