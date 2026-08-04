(function () {
  function api(path, options) {
    var base = window.APP_BASE || "";
    return fetch(base + path, Object.assign({ credentials: "same-origin" }, options || {}));
  }

  function openModal(id) {
    var el = document.getElementById(id);
    if (el) {
      el.setAttribute("aria-hidden", "false");
    }
  }

  function closeModals() {
    document.querySelectorAll(".modal").forEach(function (el) {
      el.setAttribute("aria-hidden", "true");
    });
  }

  document.querySelectorAll("[data-close-modal]").forEach(function (el) {
    el.addEventListener("click", closeModals);
  });

  var loginBtn = document.getElementById("btn-open-login");
  if (loginBtn) {
    loginBtn.addEventListener("click", function () {
      openModal("modal-login");
    });
  }

  var logoutBtn = document.getElementById("btn-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      api("/api/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ csrf_token: window.__CSRF__ || "" }),
      }).then(function () {
        window.location.reload();
      });
    });
  }

  var loginForm = document.getElementById("form-login");
  if (loginForm) {
    loginForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("login-error");
      if (errEl) {
        errEl.hidden = true;
      }
      var fd = new FormData(loginForm);
      api("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          csrf_token: window.__CSRF__ || "",
          username: fd.get("username"),
          password: fd.get("password"),
        }),
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, j: j };
          });
        })
        .then(function (x) {
          if (!x.ok) {
            if (errEl) {
              errEl.textContent = (x.j && x.j.detail) || "ログインに失敗しました。";
              errEl.hidden = false;
            }
            return;
          }
          window.location.reload();
        })
        .catch(function () {
          if (errEl) {
            errEl.textContent = "通信エラーが発生しました。";
            errEl.hidden = false;
          }
        });
    });
  }
})();
