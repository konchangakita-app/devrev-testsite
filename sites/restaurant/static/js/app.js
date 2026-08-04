(function () {
  var csrf = window.__CSRF__ || "";
  var base = (window.APP_BASE || "").replace(/\/$/, "");

  function api(path) {
    return base + path;
  }

  function jsonHeaders() {
    return {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
  }

  function openModal(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.setAttribute("aria-hidden", "false");
  }

  function closeModals() {
    document.querySelectorAll(".modal").forEach(function (m) {
      m.setAttribute("aria-hidden", "true");
    });
  }

  document.querySelectorAll("[data-close-modal]").forEach(function (node) {
    node.addEventListener("click", closeModals);
  });

  var loginBtn = document.getElementById("btn-open-login");
  var regBtn = document.getElementById("btn-open-register");
  if (loginBtn) loginBtn.addEventListener("click", function () {
    openModal("modal-login");
  });
  if (regBtn) regBtn.addEventListener("click", function () {
    openModal("modal-register");
  });

  var logoutBtn = document.getElementById("btn-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      fetch(api("/auth/logout"), {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({ csrf_token: csrf }),
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, j: j };
          });
        })
        .then(function (x) {
          if (x.ok && x.j.redirect) {
            window.location.href = x.j.redirect;
          } else {
            window.location.reload();
          }
        })
        .catch(function () {
          window.location.href = api("/");
        });
    });
  }

  var formLogin = document.getElementById("form-login");
  if (formLogin) {
    formLogin.addEventListener("submit", function (e) {
      e.preventDefault();
      var err = document.getElementById("login-error");
      var fd = new FormData(formLogin);
      err.hidden = true;
      fetch(api("/auth/login"), {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          username: fd.get("username"),
          password: fd.get("password"),
          csrf_token: csrf,
        }),
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, status: r.status, j: j };
          });
        })
        .then(function (x) {
          if (x.ok && x.j.redirect) {
            window.location.href = x.j.redirect;
            return;
          }
          err.textContent = x.j.detail || "ログインに失敗しました";
          err.hidden = false;
        })
        .catch(function () {
          err.textContent = "通信エラー";
          err.hidden = false;
        });
    });
  }

  var formReg = document.getElementById("form-register");
  if (formReg) {
    formReg.addEventListener("submit", function (e) {
      e.preventDefault();
      var err = document.getElementById("register-error");
      var fd = new FormData(formReg);
      err.hidden = true;
      fetch(api("/auth/register"), {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          username: fd.get("username"),
          email: fd.get("email"),
          password: fd.get("password"),
          csrf_token: csrf,
        }),
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, j: j };
          });
        })
        .then(function (x) {
          if (x.ok && x.j.redirect) {
            window.location.href = x.j.redirect;
            return;
          }
          var msg = x.j.detail;
          if (typeof msg !== "string" && Array.isArray(x.j.detail)) {
            msg = x.j.detail.map(function (d) {
              return d.msg || d;
            }).join(" ");
          }
          err.textContent = msg || "登録に失敗しました";
          err.hidden = false;
        })
        .catch(function () {
          err.textContent = "通信エラー";
          err.hidden = false;
        });
    });
  }
})();
