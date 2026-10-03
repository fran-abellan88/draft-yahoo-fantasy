// Development mode only (run_dashboard.py --dev): reload the page when the files change or the server restarts.
// The server sends this file and adds it to the page only in that mode; a normal run never loads it.
(function () {
  var first = null;
  function check() {
    fetch('/api/dev', { cache: 'no-store' })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (first === null) first = data.stamp;
        else if (data.stamp !== first) location.reload();
      })
      .catch(function () { /* the server is restarting: try again */ });
  }
  check();
  setInterval(check, 1000);
})();
