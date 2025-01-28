console.log('base.js loaded');

// Hide flash messages after 4 seconds
setTimeout(function() {
    var alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        alert.style.display = 'none';
    });
}, 5000);


    const logoutUrl = "{{ url_for('logout') }}";

    // Auto logout after a period of inactivity
    let idleTime = 0;
    const maxIdleTime = 35 * 60 * 1000; // 30 minutes

    function resetIdleTime() {
        idleTime = 0;
    }

    window.onload = function() {
        // Increment the idle time counter every minute
        setInterval(timerIncrement, 60000); // 1 minute

        // Reset the idle timer on mouse movement or key press
        window.onmousemove = resetIdleTime;
        window.onkeypress = resetIdleTime;
    };

    function timerIncrement() {
        idleTime += 60000; // 1 minute
        if (idleTime >= maxIdleTime) {
            window.location.href = logoutUrl;
        }
    }