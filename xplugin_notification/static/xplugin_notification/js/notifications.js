$(function () {
    var Notification = function ($el, options) {
        this.$el = $el;
        this.options = options || {};
    }

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = jQuery.trim(cookies[i]);
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    Notification.prototype.render = function (elId, options) {
        return $(elId).template_render$(options);
    }

    /* Displays a spinner in the body of the modal, indicating that a data load is in progress. */
    Notification.prototype.loading = function () {
        return this.$el.html(this.render("#notification_admin_loading", {
            classes: 'loading',
        }));
    }

    /* Action retry for fail. */
    Notification.prototype.retry_action = function (name, callback) {
        xadmin.retry = xadmin.retry || {};
        xadmin.retry[name] = callback;
        return "xadmin.retry['" + name + "']()";
    }

    /* When a data load failure occurs. */
    Notification.prototype.fail = function (action) {
        return this.$el.html(this.render("#notification_admin_retry", {
            classes: 'retry',
            retry: {
                text: gettext("Failed to load data."),
                action: action
            }
        }));
    }

    Notification.prototype.load = function () {
        var self = this;
        return $.ajax({
            url: self.$el.data("list_url"),
            data: {"plugin": "xnotification"},
            beforeSend: function () {
                self.loading();
            }
        }).done(function (data) {
            self.$el.empty();
            $.each(data, function (index, notification) {
                var message = $("#notification_message").template_render$({
                    notification: notification
                });
                self.$el.append(message);
            });
        }).fail(function () {
            self.fail(self.retry_action('xnotification', function () {
                self.load();
            }))
        })
    }

    /* Marca uma notificação como lida via POST e redireciona ao destino */
    $(document).on("click", ".notification-read-link", function (e) {
        e.preventDefault();
        var $link = $(this);
        var $item = $link.closest(".list-group-item");
        var markUrl = $item.data("mark-as-read-url");
        var targetUrl = $link.attr("href");

        if (!markUrl || $item.data("is-read")) {
            // Já lida ou sem URL — redireciona direto
            window.location.href = targetUrl;
            return;
        }

        $.ajax({
            type: "POST",
            url: markUrl,
            data: {"csrfmiddlewaretoken": getCookie('csrftoken')},
            success: function () {
                // Atualiza o badge decrementando
                var $badge = $(".notification-menu .badge-notify");
                var count = parseInt($badge.text(), 10) || 0;
                count = Math.max(0, count - 1);
                if (count > 0) {
                    $badge.text(count);
                } else {
                    $badge.text(0).hide();
                }
                // Marca visualmente como lido
                $item.removeClass("list-group-item-unread");
            },
            complete: function () {
                // Redireciona independente do resultado do mark-as-read
                window.location.href = targetUrl;
            }
        });
    });

    $(".notification-menu").on("show.bs.dropdown", function () {
        var notification = new Notification($(this).find(".dropdown-menu .notification-message-item"));
        notification.load();
    })
})
